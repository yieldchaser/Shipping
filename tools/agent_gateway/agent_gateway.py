"""Agent gateway: one local OpenAI-compatible endpoint for the coding agent (dsh).

For every chat request, try the upstreams in this order:

  1. Ultrafast (free DeepSeek V4.1 Flash 1017, thinking mode on). It serves one request at a time.
     A 429 with Retry-After means "you are in the queue". The gateway waits and
     retries by itself. While it waits on a streaming request, it sends SSE
     keep-alive comments so the client does not time out.
  2. Enclave router (paid, DeepSeek V4 Pro). Used when any of these is true:
       - Ultrafast waited longer than FALLBACK_AFTER_S,
       - Ultrafast failed 3 times,
       - the prompt is too large for Ultrafast,
       - Ultrafast's daily output budget is used up.
     Enclave spend is hard-capped at AGENT_CAP_USD. The usage log on disk keeps
     the total across restarts.

Keys:
  - Ultrafast: ULTRAFAST_API_KEY env, else refs.ULTRAFAST_API_KEY in ~/.dsh/.credentials.yaml
  - Enclave:   ENCLAVE_API_KEY env, else refs.ENCLAVE_API_KEY in the same file
Keys are never printed or logged.

Run:   python tools/agent_gateway/agent_gateway.py      (listens on 127.0.0.1:4100)
Stats: GET http://127.0.0.1:4100/stats
"""
import asyncio
import json
import os
import re
import time
from pathlib import Path

import yaml
from aiohttp import ClientSession, ClientTimeout, web

HERE = Path(__file__).resolve().parent
USAGE_LOG = Path(os.environ.get("AGENT_GATEWAY_LOG", str(HERE / "agent_gateway_usage.jsonl")))
PORT = int(os.environ.get("AGENT_GATEWAY_PORT", "4100"))

UF_BASE = os.environ.get("ULTRAFAST_BASE_URL", "https://ultrafast.trytokenfactory.dev/v1")
UF_MODEL = os.environ.get("ULTRAFAST_MODEL", "deepseek-v4.1-flash-1017-ultrafast")
UF_DAILY_OUT = int(os.environ.get("ULTRAFAST_DAILY_OUTPUT", "4800000"))  # site budget: 5M output tokens/day
UF_MAX_PROMPT_TOK = 120_000                                              # site limit: about 128k prompt tokens
UF_MAX_OUT = 16_000                                                      # site limit: 16k output tokens per request
UF_LONG_WAIT_S = 300   # a Retry-After longer than this is not a queue turn (e.g. daily budget used): skip Ultrafast until then

EN_BASE = os.environ.get("ENCLAVE_BASE_URL", "https://router.enclave.ai/v1")
EN_MODEL = os.environ.get("ENCLAVE_MODEL", "cyberouter/deepseek-v4.1-flash")
EN_PRICE_IN, EN_PRICE_OUT = 0.30, 1.20
AGENT_CAP_USD = float(os.environ.get("AGENT_CAP_USD", "76"))
# Routing by requested model id (owner 11-09):
#   "deepseek-v4-pro"     -> Enclave V4 Pro first while the cap lasts, then Ultrafast  (main agent: planning/design)
#   "deepseek-v4.1-flash" -> Ultrafast first (free, thinking on), then Enclave V4 Pro  (subagents: bulk coding)
# AGENT_PRIMARY=enclave|ultrafast forces one order for every request.
PRIMARY = os.environ.get("AGENT_PRIMARY", "")

UF_THINKING = os.environ.get("ULTRAFAST_THINKING", "1") == "1"            # reasoning on: better code, free
FALLBACK_AFTER_S = float(os.environ.get("FALLBACK_AFTER_S", "900"))
KEEPALIVE_S = 15


def _cred(name):
    if os.environ.get(name):
        return os.environ[name]
    f = Path.home() / ".dsh" / ".credentials.yaml"
    if f.exists():
        try:
            return ((yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("refs") or {}).get(name)
        except Exception:
            return None
    return None


UF_KEY, EN_KEY = _cred("ULTRAFAST_API_KEY"), _cred("ENCLAVE_API_KEY")


def _load_usage():
    spent, day_out = 0.0, {}
    if USAGE_LOG.exists():
        for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            spent += r.get("cost_usd", 0.0)
            if r.get("upstream") == "ultrafast":
                d = r["ts"][:10]
                day_out[d] = day_out.get(d, 0) + r.get("completion_tokens", 0)
    return spent, day_out


STATE = {}
STATE["enclave_spent"], STATE["uf_day_out"] = _load_usage()


def _today():
    return time.strftime("%Y-%m-%d", time.gmtime())


def _log(entry):
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    if entry["upstream"] == "enclave":
        STATE["enclave_spent"] += entry.get("cost_usd", 0.0)
    else:
        d = entry["ts"][:10]
        STATE["uf_day_out"][d] = STATE["uf_day_out"].get(d, 0) + entry.get("completion_tokens", 0)


def _approx_prompt_tokens(body):
    text = json.dumps(body.get("messages", []), ensure_ascii=False) + json.dumps(body.get("tools", []), ensure_ascii=False)
    return len(text) // 3


# A streamed answer has really started once a delta carries text, reasoning or a tool call.
OUTPUT_RE = re.compile(rb'"(?:content|reasoning|reasoning_content)"\s*:\s*"[^"]|"tool_calls"\s*:\s*\[\s*\{')


class Usage:
    """Collects token usage from a JSON body or from SSE lines."""

    def __init__(self):
        self.p = self.c = self.cached = 0
        self.cost = None  # router-reported cost (Enclave sends usage.cost)
        self.buf = b""

    def take(self, u):
        if u:
            self.p = u.get("prompt_tokens") or self.p
            self.c = u.get("completion_tokens") or self.c
            self.cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens") or self.cached
            if isinstance(u.get("cost"), (int, float)):
                self.cost = float(u["cost"])

    def feed_sse(self, chunk):
        self.buf += chunk
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            line = line.strip()
            if line.startswith(b"data:") and line[5:].strip() not in (b"", b"[DONE]"):
                try:
                    self.take(json.loads(line[5:]).get("usage"))
                except (ValueError, AttributeError):
                    pass


async def _open(session, base, key, model, body):
    b = dict(body, model=model)
    if base == UF_BASE:
        if UF_THINKING:
            b["chat_template_kwargs"] = dict(b.get("chat_template_kwargs") or {}, thinking=True)
        for k in ("max_tokens", "max_completion_tokens"):
            if isinstance(b.get(k), int) and b[k] > UF_MAX_OUT:
                b[k] = UF_MAX_OUT
    if b.get("stream"):
        b["stream_options"] = dict(b.get("stream_options") or {}, include_usage=True)
    return await session.post(f"{base}/chat/completions", json=b, headers={"Authorization": f"Bearer {key}"})


async def chat(request):
    body = await request.json()
    stream = bool(body.get("stream"))
    t0 = time.monotonic()
    out = {"resp": None}  # StreamResponse once headers are sent (streaming only)

    async def headers_sent():
        if out["resp"] is None:
            out["resp"] = web.StreamResponse(status=200, headers={
                "Content-Type": "text/event-stream", "Cache-Control": "no-cache"})
            await out["resp"].prepare(request)
        return out["resp"]

    async def keepalive():
        if stream:
            await (await headers_sent()).write(b": waiting in queue\n\n")

    async def relay(upstream_resp, name, model):
        """Forward the upstream answer. Returns None (nothing sent to the client) when the upstream stream
        broke or ended before any real output, so the caller can retry instead of failing the agent's turn."""
        u = Usage()
        if stream:
            resp = await headers_sent()
            # Hold the WHOLE answer before sending any of it (keep-alive comments meanwhile), so a stream
            # that breaks at any point - before or after output started - can be retried cleanly.
            held, last_ka = [], time.monotonic()
            try:
                async for chunk in upstream_resp.content.iter_any():
                    u.feed_sse(chunk)
                    held.append(chunk)
                    if time.monotonic() - last_ka > KEEPALIVE_S:
                        await resp.write(b": generating\n\n")
                        last_ka = time.monotonic()
            except Exception as e:
                _log({"upstream": name, "model": model, "status": "broken_stream",
                      "error": type(e).__name__, "prompt_tokens": u.p, "completion_tokens": u.c,
                      "cached_tokens": u.cached, "cost_usd": 0.0, "wait_s": round(time.monotonic() - t0, 1),
                      "stream": True})
                return None
            body_bytes = b"".join(held)
            if not OUTPUT_RE.search(body_bytes) and u.c == 0:
                _log({"upstream": name, "model": model, "status": "empty_stream", "prompt_tokens": u.p,
                      "completion_tokens": 0, "cached_tokens": u.cached, "cost_usd": 0.0,
                      "wait_s": round(time.monotonic() - t0, 1), "stream": True})
                return None
            if b"[DONE]" not in body_bytes and u.c == 0:
                _log({"upstream": name, "model": model, "status": "truncated_stream", "prompt_tokens": u.p,
                      "completion_tokens": 0, "cached_tokens": u.cached, "cost_usd": 0.0,
                      "wait_s": round(time.monotonic() - t0, 1), "stream": True})
                return None
            await resp.write(body_bytes)
            await resp.write_eof()
        else:
            data = await upstream_resp.read()
            try:
                u.take(json.loads(data).get("usage"))
            except (ValueError, AttributeError):
                pass
            resp = web.Response(body=data, status=upstream_resp.status, content_type="application/json")
        cost = 0.0 if name == "ultrafast" else (u.cost if u.cost is not None else (u.p * EN_PRICE_IN + u.c * EN_PRICE_OUT) / 1e6)
        _log({"upstream": name, "model": model, "status": upstream_resp.status,
              "prompt_tokens": u.p, "completion_tokens": u.c, "cached_tokens": u.cached,
              "cost_usd": round(cost, 6), "wait_s": round(time.monotonic() - t0, 1), "stream": stream})
        return resp

    async def fail(msg, status):
        err = {"error": {"message": msg, "type": "agent_gateway"}}
        if stream and out["resp"] is not None:
            await out["resp"].write(b"data: " + json.dumps(err).encode() + b"\n\n")
            await out["resp"].write_eof()
            return out["resp"]
        return web.json_response(err, status=status)

    async with ClientSession(timeout=ClientTimeout(total=None, sock_read=600)) as s:
        # 0) Enclave first while its cap lasts (PRIMARY == "enclave")
        primary = PRIMARY or ("enclave" if "pro" in str(body.get("model", "")).lower() else "ultrafast")
        if primary == "enclave" and EN_KEY and STATE["enclave_spent"] < AGENT_CAP_USD:
            for attempt in range(5):
                if attempt:
                    for _ in range(5 * attempt // KEEPALIVE_S + 1):
                        await keepalive()
                        await asyncio.sleep(min(KEEPALIVE_S, 5 * attempt))
                try:
                    r = await _open(s, EN_BASE, EN_KEY, EN_MODEL, body)
                except Exception:
                    continue
                if r.status == 200:
                    done = await relay(r, "enclave", EN_MODEL)
                    if done is not None:
                        return done
                    continue
                r.release()
                if r.status in (401, 402, 403):
                    break          # key or credit problem: go to Ultrafast
        # 1) Ultrafast (free, queued, one at a time)
        # When Enclave cannot take over (cap used up or no key), Ultrafast is the only road: wait in line
        # as long as it takes and tolerate more errors, instead of failing the agent's turn after 15 min.
        en_can = bool(EN_KEY) and STATE["enclave_spent"] < AGENT_CAP_USD
        deadline_s = FALLBACK_AFTER_S if en_can else float("inf")
        max_err = 3 if en_can else 30
        uf_ok = (UF_KEY and _approx_prompt_tokens(body) <= UF_MAX_PROMPT_TOK
                 and STATE["uf_day_out"].get(_today(), 0) < UF_DAILY_OUT
                 and (not en_can or time.time() >= STATE.get("uf_blocked_until", 0)))
        if uf_ok:
            errors = 0
            lock = request.app["uf_lock"]
            while time.monotonic() - t0 < deadline_s and errors < max_err:
                try:
                    await asyncio.wait_for(lock.acquire(), timeout=KEEPALIVE_S)
                except asyncio.TimeoutError:
                    await keepalive()
                    continue
                try:
                    while time.monotonic() - t0 < deadline_s and errors < max_err:
                        try:
                            r = await _open(s, UF_BASE, UF_KEY, UF_MODEL, body)
                        except Exception:
                            errors += 1
                            await asyncio.sleep(5 if en_can else 20)
                            continue
                        if r.status == 200:
                            done = await relay(r, "ultrafast", UF_MODEL)
                            if done is not None:
                                return done
                            errors += 1
                            continue
                        r.release()
                        if r.status == 429:
                            try:
                                wait = float(r.headers.get("Retry-After") or 10)
                            except ValueError:
                                wait = 10.0
                            if wait > UF_LONG_WAIT_S and en_can:
                                STATE["uf_blocked_until"] = time.time() + wait
                                errors = max_err
                                break
                            end = time.monotonic() + min(max(wait, 1.0), 60.0 if en_can else 300.0)
                            while time.monotonic() < end:
                                await keepalive()
                                await asyncio.sleep(min(KEEPALIVE_S, max(0.1, end - time.monotonic())))
                            continue
                        errors += 1
                        await asyncio.sleep(5 if en_can else 20)
                finally:
                    lock.release()

        # 2) Enclave (paid, hard-capped)
        if not EN_KEY:
            return await fail("Ultrafast unavailable and no Enclave key", 502)
        if STATE["enclave_spent"] >= AGENT_CAP_USD:
            return await fail(f"Ultrafast unavailable and the agent's Enclave cap ${AGENT_CAP_USD:.0f} is used up", 402)
        r, last_err = None, "no response"
        for attempt in range(3):
            if attempt:
                await keepalive()
                await asyncio.sleep(10 * attempt)
            try:
                r = await _open(s, EN_BASE, EN_KEY, EN_MODEL, body)
            except Exception as e:
                r, last_err = None, type(e).__name__
                continue
            if r.status != 200:
                break
            done = await relay(r, "enclave", EN_MODEL)
            if done is not None:
                return done
            r, last_err = None, "empty or broken stream"
        if r is None:
            return await fail(f"Enclave request failed: {last_err}", 502)
        if r.status != 200:
            data = await r.read()
            if stream and out["resp"] is not None:
                await out["resp"].write(b"data: " + data + b"\n\n")
                await out["resp"].write_eof()
                return out["resp"]
            return web.Response(body=data, status=r.status, content_type="application/json")
        return await relay(r, "enclave", EN_MODEL)


async def models(_):
    return web.json_response({"object": "list", "data": [
        {"id": "deepseek-v4-pro", "object": "model", "owned_by": "agent-gateway"},
        {"id": "deepseek-v4.1-flash", "object": "model", "owned_by": "agent-gateway"}]})


async def stats(_):
    return web.json_response({
        "enclave_spent_usd": round(STATE["enclave_spent"], 4), "enclave_cap_usd": AGENT_CAP_USD,
        "ultrafast_output_today": STATE["uf_day_out"].get(_today(), 0), "ultrafast_daily_cap": UF_DAILY_OUT,
        "ultrafast_blocked_for_s": max(0, int(STATE.get("uf_blocked_until", 0) - time.time())),
        "primary": PRIMARY or "by model (pro -> enclave first, flash -> ultrafast first)",
        "ultrafast_key_found": bool(UF_KEY), "enclave_key_found": bool(EN_KEY)})


async def _init(app):
    app["uf_lock"] = asyncio.Lock()


def make_app():
    app = web.Application(client_max_size=64 * 1024 * 1024)
    app.on_startup.append(_init)
    app.router.add_post("/v1/chat/completions", chat)
    app.router.add_get("/v1/models", models)
    app.router.add_get("/stats", stats)
    return app


if __name__ == "__main__":
    print(f"agent gateway on http://127.0.0.1:{PORT}/v1  ultrafast_key={bool(UF_KEY)} "
          f"enclave_key={bool(EN_KEY)}  enclave_spent=${STATE['enclave_spent']:.2f}/${AGENT_CAP_USD:.0f}")
    web.run_app(make_app(), host="127.0.0.1", port=PORT, print=None)
