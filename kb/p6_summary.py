"""P6: period summaries / time tree (build plan §8, §11).

Design note (5 points, per `docs/GRAPHRAG_AGENT_TASK.md` §4):

1. Segments are the plan's §8 list; a piece of text is tagged by deterministic
   keyword patterns (priority order = `SEGMENT_PATTERNS`), never by an LLM, so the
   tree shape is reproducible from the DB alone.
2. Grains: month leaf -> quarter -> year (weeks skipped, plan §8). A leaf is built
   from that month's layer-A observations, top chunks, events and claims; a parent
   is built from its children's sentences **plus** the top-10 underlying evidence
   items so errors cannot compound up the tree.
3. Citation rule: every kept sentence must cite an `obs:`/`chunk:`/`event:`/`claim:`
   id that is present in the node's evidence pack, and every number in it must occur
   in the cited evidence text. Failing sentences are dropped (and counted).
4. `input_hash` = sha256 over the evidence pack's (ref, signature) pairs (+ child
   hashes for parents), so a rebuild touches only leaves whose evidence changed and
   their ancestors.
5. Everything except the two model calls (`write_node`, `judge_node`) is pure and
   unit-tested offline; the writer is the AMD Token Lab bulk model (family deepseek,
   PAID since the D10 amendment) and the judge is Google `Gemma-4-31B-IT` on AMD Token
   Lab (family gemma, owner amendment 2026-11-15, replacing the NIM free tier) - both
   routes are priced from `usage.cost`/the config tariff, never assumed 0.0 (Defect 14).
   Plan §11 P6 gate: number check 100%, judge faithfulness >= 95% on 60 nodes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "kb") not in sys.path:
    sys.path.insert(0, str(ROOT / "kb"))

import duckdb  # noqa: E402

import money as M  # noqa: E402

from extract_gates import numbers_ok  # noqa: E402 (kept for reference/parity in reports)
from extract_schema import printed_numbers  # noqa: E402
from llm_runner import chat, parse_json_object  # noqa: E402
import runner as R  # noqa: E402

KB_DB = ROOT / "kb/state/kb.duckdb"
OUT = ROOT / "kb/state/p6"
REPORTS = ROOT / "kb/reports"
NODES = OUT / "nodes.jsonl"
INDEX = OUT / "index.json"
TREE = OUT / "tree.json"

WRITER_MODEL = "DeepSeek-V4.1-Flash"  # AMD Token Lab bulk model (owner amendment to D10): PAID but family deepseek
JUDGE_MODEL = "Gemma-4-31B-IT"                       # AMD Token Lab, family gemma != deepseek
JUDGE_FALLBACK_MODEL = "Qwen3.8-27B"                 # family qwen != deepseek (owner amendment)
GRAINS = ("month", "quarter", "year")
LEAF_OBS = 12
LEAF_CHUNKS = 8
LEAF_RECORDS = 8
PARENT_TOP = 10
MAX_SENTENCES_LEAF = 3
MAX_SENTENCES_PARENT = 5
CHUNK_SCAN_CAP = 20_000
JUDGE_SAMPLE = 60

PHASE = "P6"


def seed_for(phase: str = PHASE) -> int:
    """Deterministic gate seed (same recipe as every other phase gate)."""
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def _family(model: str) -> str:
    """Leading vendor token of a model id (same rule as `p4c_audit.model_family`)."""
    return model.split("/")[0].split("-")[0].lower()


def clamp_score(value) -> float | None:
    """A judge score is only usable inside [0, 1]; anything else is `None`, never a silent 0.0.

    Defect 17 (same class as Defect 16): the judge is an LLM, so its `score` field is untrusted
    input. Accepting it verbatim let `"score": 3` inflate `faithful_rate` past the 0.95 P6 gate and
    let a missing/garbage score be coerced to a plausible-looking 0.0 that still counted as graded.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):  # pragma: no cover - float() of a number cannot fail
        return None
    if value != value:  # NaN
        return None
    return max(0.0, min(1.0, value))


# plan §8 segments, plus `company:<ticker>` nodes (quarterly)
SEGMENT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("capesize", (r"\bcapesize\b", r"\bcape\s+size\b", r"\bbci\b", r"\bc5\b", r"\bc3\b", r"\btubarao\b")),
    ("panamax", (r"\bpanamax\b", r"\bkamsarmax\b", r"\bbpi\b")),
    ("supramax", (r"\bsupramax\b", r"\bultramax\b", r"\bhandymax\b", r"\bbsi\b")),
    ("handysize", (r"\bhandysize\b", r"\bhandy\b")),
    ("vlcc", (r"\bvlcc\b",)),
    ("suezmax", (r"\bsuezmax\b",)),
    ("aframax", (r"\baframax\b",)),
    ("mr_lr", (r"\bmr1\b", r"\bmr2\b", r"\blr1\b", r"\blr2\b", r"\bmedium range\b", r"\bproduct tanker\b")),
    ("lng", (r"\blng\b", r"\bliquefied natural gas\b", r"\blng carrier\b")),
    ("lpg", (r"\blpg\b", r"\bliquefied petroleum gas\b")),
    ("container", (r"\bcontainer\b", r"\bteu\b", r"\bfeu\b", r"\bscfi\b", r"\bboxship\b")),
    ("snp", (r"\bsale and purchase\b", r"\bsecondhand\b", r"\bsecond-hand\b", r"\bs&p\b", r"\bsecond hand\b")),
    ("demolition", (r"\bdemolition\b", r"\bdemolish", r"\bscrap(?:ped|ping|s)?\b", r"\bldt\b", r"\bbreaking\b", r"\bgms\b")),
    ("newbuilding", (r"\bnewbuilding", r"\bnew building\b", r"\bnewbuild", r"\borderbook\b")),
    ("iron_ore", (r"\biron ore\b", r"\bore carrier\b", r"\biron-ore\b")),
    ("coal", (r"\bcoal\b",)),
    ("grains", (r"\bgrains?\b", r"\bwheat\b", r"\bcorn\b", r"\bsoybean")),
    ("bunkers", (r"\bbunkers?\b", r"\bvlsfo\b", r"\bhsfo\b", r"\bmgo\b", r"\bifo\s?380\b")),
]
SEGMENTS = tuple(s for s, _ in SEGMENT_PATTERNS)
PATTERNS = [(s, tuple(re.compile(p, re.I) for p in pats)) for s, pats in SEGMENT_PATTERNS]
CITE_RE = re.compile(r"\[(obs|chunk|event|claim):([A-Za-z0-9_.:\-]+)\]")
NUMTOK = re.compile(r"\d[\d,]*(?:\.\d+)?")
LINE_RE = re.compile(r"^\s*(?:[-*+\u2022]|\d+[.)])\s+")
NUMBER_WORDS = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b", re.I)

WRITER_PROMPT = """You write one short periodic summary for a maritime-market knowledge base.

Rules, all mandatory:
1. Output 1-{max_sent} bullet lines, nothing else. No headings, no preamble, no blank lines.
2. Every line ends with one or more citations in square brackets, copied exactly from the
   evidence: [obs:ID], [chunk:ID], [event:ID] or [claim:ID].
3. Use only numbers that appear in the evidence lines you cite. Never compute, convert,
   round, or aggregate a number yourself. If you are unsure of a number, leave it out.
4. State only what the evidence says. No forecasts of your own, no causes you cannot see
   in the evidence. If the evidence is thin, write fewer lines.
5. Plain ASCII. One clause per sentence; no semicolons piling up.

Example of a valid line:
- Capesize spot averaged USD 24,500/day in the week ending 6 March 2026 [obs:502852730410985934]"""

JUDGE_PROMPT = """You grade one summary line for faithfulness against the evidence that it cites.

Answer with strict JSON only: {"verdict": "supported"|"partial"|"unsupported", "score": 0.0-1.0, "why": "<=20 words"}

Definitions:
- "supported": every claim and every number in the line is present in the cited evidence.
- "partial": the gist is present, but a detail (number, date, qualifier) is not.
- "unsupported": the line's core claim is absent from the cited evidence, or it cites nothing.

Score 1.0 for supported, 0.5 for partial, 0.0 for unsupported."""


# ------------------------------------------------------------------ periods
def as_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def period_of(d: date, grain: str) -> str:
    if grain == "month":
        return f"{d.year:04d}-{d.month:02d}"
    if grain == "quarter":
        return f"{d.year:04d}-Q{(d.month - 1) // 3 + 1}"
    if grain == "year":
        return f"{d.year:04d}"
    raise ValueError(f"bad grain {grain!r}")


def period_bounds(period: str) -> tuple[date, date]:
    """Inclusive (start, end) for a month / quarter / year period id."""
    if re.fullmatch(r"\d{4}-\d{2}", period):
        y, m = int(period[:4]), int(period[5:7])
        start = date(y, m, 1)
        end = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
        return start, date.fromordinal(end.toordinal() - 1)
    m = re.fullmatch(r"(\d{4})-Q([1-4])", period)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        start = date(y, 3 * q - 2, 1)
        end = date(y + (q == 4), 1 if q == 4 else 3 * q + 1, 1)
        return start, date.fromordinal(end.toordinal() - 1)
    if re.fullmatch(r"\d{4}", period):
        y = int(period)
        return date(y, 1, 1), date(y, 12, 31)
    raise ValueError(f"bad period {period!r}")


def parent_period(period: str) -> str | None:
    """Month -> quarter -> year -> None."""
    if re.fullmatch(r"\d{4}-\d{2}", period):
        return f"{period[:4]}-Q{(int(period[5:7]) - 1) // 3 + 1}"
    m = re.fullmatch(r"(\d{4})-Q([1-4])", period)
    if m:
        return m.group(1)
    return None


def child_periods(period: str) -> list[str]:
    """Direct children of a parent period (quarter -> 3 months, year -> 4 quarters)."""
    m = re.fullmatch(r"(\d{4})-Q([1-4])", period)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        return [f"{y:04d}-{3 * q - 2 + i:02d}" for i in range(3)]
    if re.fullmatch(r"\d{4}", period):
        return [f"{period}-Q{i}" for i in range(1, 5)]
    return []


def node_id(segment: str, grain: str, period: str) -> str:
    return "n:" + hashlib.sha256(f"{segment}|{grain}|{period}".encode()).hexdigest()[:16]


# ------------------------------------------------------------------ segments
def segment_of_text(text: str) -> list[str]:
    """All plan §8 segments whose keyword patterns occur in `text`, priority order."""
    if not text:
        return []
    return [seg for seg, pats in PATTERNS if any(p.search(text) for p in pats)]


def series_segment_map(con) -> dict[str, list[str]]:
    """series_id -> list of segments, from the series name + source csv (no LLM)."""
    out: dict[str, list[str]] = {}
    for sid, name, src in con.execute("select series_id, name, source_csv from series").fetchall():
        segs = segment_of_text(f"{name or ''} {(src or '').replace('_', ' ')}")
        if segs:
            out[sid] = segs
    return out


# ------------------------------------------------------------------ evidence
def _sig(kind: str, ref: str, text: str) -> str:
    return hashlib.sha256(f"{kind}|{ref}|{' '.join((text or '').split())}".encode()).hexdigest()[:16]


def _obs_text(name: str, value, unit, period_from, period_to) -> str:
    return (f"{name}: value {value} {unit or ''} for {period_from}..{period_to}").strip()


def leaf_evidence(con, segment: str, period: str, segmap: dict[str, list[str]] | None = None) -> list[dict]:
    """Evidence pack for one (segment, month) leaf: observations, chunks, events, claims.

    Deterministic: every query is ordered, every cap fixed; `signature` feeds `input_hash`.
    """
    start, end = period_bounds(period)
    segmap = segmap if segmap is not None else series_segment_map(con)
    ev: list[dict] = []

    sids = [sid for sid, segs in segmap.items() if segment in segs]
    if sids:
        rows = con.execute(
            """select o.obs_id, o.series_id, s.name, o.value, o.unit, o.period_from, o.period_to,
                      o.published_at, o.raw_cell
                 from observation o join series s on s.series_id = o.series_id
                where o.series_id in (select unnest(?::VARCHAR[]))
                  and o.period_from <= ? and coalesce(o.period_to, o.period_from) >= ?
                order by o.published_at desc, o.obs_id
                limit ?""",
            [sids, end, start, LEAF_OBS]).fetchall()
        for obs_id, sid, name, value, unit, pf, pt, pub, raw in rows:
            text = _obs_text(name, raw if raw else value, unit, pf, pt)
            ev.append({"kind": "obs", "ref": str(obs_id), "text": text,
                       "published_at": str(pub or ""), "signature": _sig("obs", str(obs_id), text)})

    rows = con.execute(
        """select c.chunk_id, c.doc_id, c.body, d.published_at, d.path
             from chunk c join document d on d.doc_id = c.doc_id
            where d.published_at between ? and ? and c.extract
            order by c.chunk_id limit ?""",
        [start, end, CHUNK_SCAN_CAP]).fetchall()
    scored = []
    for cid, doc_id, body, pub, path in rows:
        segs = segment_of_text(body)
        if segment in segs:
            hits = sum(1 for p in dict(PATTERNS)[segment] if p.search(body or ""))
            scored.append((-hits, cid, doc_id, body, pub, path))
    scored.sort(key=lambda t: (t[0], t[1]))
    for _neg, cid, doc_id, body, pub, path in scored[:LEAF_CHUNKS]:
        text = " ".join((body or "").split())[:600]
        ev.append({"kind": "chunk", "ref": str(cid), "text": text, "published_at": str(pub or ""),
                   "path": path, "signature": _sig("chunk", str(cid), text)})

    def record_rows(table: str, id_col: str, cols: str) -> list:
        return con.execute(
            f"""select {id_col}, {cols} from {table}
                 where published_at between ? and ?
                 order by {id_col} limit 200""",
            [start, end]).fetchall()

    for row in record_rows("event", "event_id", "type, summary, quote"):
        eid, typ, summary, quote = row
        text = f"{typ}: {summary or ''} ({' '.join((quote or '').split())[:300]})"
        if segment not in segment_of_text(text):
            continue
        ev.append({"kind": "event", "ref": str(eid), "text": text,
                   "published_at": str(start), "signature": _sig("event", str(eid), text)})
        if len([e for e in ev if e["kind"] == "event"]) >= LEAF_RECORDS:
            break

    for row in record_rows("claim", "claim_id", "kind, text_printed, quote"):
        cid, kind, printed, quote = row
        text = f"{kind} claim: {printed or ''} ({' '.join((quote or '').split())[:300]})"
        if segment not in segment_of_text(text):
            continue
        ev.append({"kind": "claim", "ref": str(cid), "text": text,
                   "published_at": str(start), "signature": _sig("claim", str(cid), text)})
        if len([e for e in ev if e["kind"] == "claim"]) >= LEAF_RECORDS:
            break

    return ev


def evidence_map(ev: list[dict]) -> dict[str, dict]:
    return {f"{e['kind']}:{e['ref']}": e for e in ev}


def node_input_hash(segment: str, grain: str, period: str, ev: list[dict],
                    child_hashes: dict[str, str] | None = None) -> str:
    payload = {"segment": segment, "grain": grain, "period": period,
               "evidence": sorted((f"{e['kind']}:{e['ref']}", e["signature"]) for e in ev),
               "children": sorted((child_hashes or {}).items())}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]


# ------------------------------------------------------------------ prompt / parse
def evidence_lines(ev: list[dict]) -> str:
    return "\n".join(f"[{e['kind']}:{e['ref']}] {e['text']}" for e in ev)


def writer_messages(segment: str, grain: str, period: str, ev: list[dict],
                    children: list[dict] | None = None, max_sent: int = MAX_SENTENCES_LEAF) -> list[dict]:
    head = (f"Segment: {segment}\nGrain: {grain}\nPeriod: {period}\n"
            f"Write at most {max_sent} lines.\n")
    body = head + "\nEVIDENCE\n" + evidence_lines(ev)
    if children:
        body += "\n\nCHILD SUMMARIES (their citations stay valid; reuse them)\n"
        for c in children:
            body += f"- {c['segment']} {c['grain']} {c['period']}: {c.get('summary') or '(empty)'}\n"
    body += "\n\nWrite the summary now: one line per bullet, each ending with [obs:..]/[chunk:..]/[event:..]/[claim:..]."
    return [{"role": "system", "content": WRITER_PROMPT.format(max_sent=max_sent)},
            {"role": "user", "content": body}]


def parse_summary(text: str) -> list[dict]:
    """Split a model answer into candidate sentences: [{sentence, cites}]."""
    if not text:
        return []
    out = []
    for raw in str(text).splitlines():
        line = LINE_RE.sub("", raw).strip()
        if not line:
            continue
        cites = [f"{m.group(1)}:{m.group(2)}" for m in CITE_RE.finditer(line)]
        sentence = CITE_RE.sub("", line).strip(" -;\t")
        sentence = " ".join(sentence.split())
        if not sentence:
            continue
        out.append({"sentence": sentence, "cites": cites})
    return out


def num_tokens(text: str) -> list[float]:
    """Numeric tokens of a sentence/evidence line, comma separators stripped."""
    out = []
    for tok in NUMTOK.findall(text or ""):
        tok = tok.replace(",", "").rstrip(".")
        try:
            out.append(float(tok))
        except ValueError:
            continue
    return out


def number_check_ok(sentence: str, evidence_text: str) -> bool:
    """Every number in `sentence` must occur in `evidence_text` (unit/rounding tolerance).

    Tighter than `numbers_ok` for P6 because summary sentences carry unit suffixes
    ("24,500/day") that the printed evidence splits ("24,500 usd/day"), so comparison is
    numeric with a small rounding tolerance rather than a substring test.
    """
    nums = num_tokens(sentence)
    if not nums:
        return True
    have = num_tokens(evidence_text)
    if not have:
        return False
    for v in nums:
        if any(abs(v - h) <= max(1e-9, 0.005 * abs(v)) for h in have):
            continue
        return False
    return True


def validate_sentences(candidates: list[dict], ev: list[dict], max_sent: int) -> tuple[list[dict], dict]:
    """Apply the citation + number rules; return (kept, drop counters)."""
    emap = evidence_map(ev)
    kept: list[dict] = []
    drops = {"no_cite": 0, "unknown_cite": 0, "number_not_in_evidence": 0, "over_limit": 0,
             "no_number_sentence_ok": 0}
    for cand in candidates:
        if len(kept) >= max_sent:
            drops["over_limit"] += 1
            continue
        cites = [c for c in cand["cites"] if c in emap]
        if not cand["cites"]:
            drops["no_cite"] += 1
            continue
        if len(cites) != len(cand["cites"]):
            drops["unknown_cite"] += 1
            continue
        joined = " ".join(emap[c]["text"] for c in cites)
        if num_tokens(cand["sentence"]):
            if not number_check_ok(cand["sentence"], joined):
                drops["number_not_in_evidence"] += 1
                continue
        else:
            drops["no_number_sentence_ok"] += 1
        kept.append({"sentence": cand["sentence"], "cites": cites})
    return kept, drops


def summary_text(kept: list[dict]) -> str:
    return " ".join(f"{k['sentence']} " + "".join(f"[{c}]" for c in k["cites"]) for k in kept).strip()


def summary_cites(kept: list[dict]) -> list[str]:
    seen: list[str] = []
    for k in kept:
        for c in k["cites"]:
            if c not in seen:
                seen.append(c)
    return seen


# ------------------------------------------------------------------ model calls
def _log(job_key: str, pass_name: str, model: str, usage: dict | None, cost: float | None = None,
         status: str = "ok", error: str | None = None, meta: dict | None = None
         ) -> float | None:
    """Ledger row for a P6 call. Returns the booked cost, or `None` when unmeasured.

    `cost=None` prices the call from `runner.cost_usd(model, usage)`, which prefers the
    provider-reported `usage.cost` and falls back to kb/config.yaml's tariff. Required:
    the writer runs on the paid `amd_tokenlab` route (D10 amendment), so a hardcoded 0.0
    would hide real spend from `runner.spent()` and the global pipeline cap.

    Defect 17/21 class: an unpriceable call (no usage block, unknown model, config price still
    `null`) must stay UNMEASURED. Coercing it to `0.0` wrote SQLite a measured zero and let the
    phase total shrink to the calls that happened to be priced. `None` is written as SQL NULL and
    `phase_spend_usd()` reports `UNMEASURED`; an explicit provider-reported `0.0` still books as
    `0.0` because a provider number is authoritative even at exactly zero.
    """
    usage = usage or {}
    if cost is None:
        try:
            cost = R.cost_usd(model, usage)
        except Exception:  # noqa: BLE001 - unknown model / unreadable config: do not lose the row
            cost = None
    if cost is not None:
        cost = float(cost)
    try:
        con = R.connect()
        con.execute(
            """INSERT INTO jobs(job_key, pass, prompt_version, model, status, attempts, request_hash,
                   in_tok, cached_tok, out_tok, cost_usd, finish_reason, latency_ms, model_returned,
                   error, created_at, meta) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(job_key) DO UPDATE SET status=excluded.status, in_tok=excluded.in_tok,
                   out_tok=excluded.out_tok, cost_usd=COALESCE(excluded.cost_usd, jobs.cost_usd),
                   error=excluded.error""",
            (job_key, pass_name, "p6-v1", model, status, 1, "",
             int(usage.get("prompt_tokens") or 0), int(usage.get("cached_tokens") or 0),
             int(usage.get("completion_tokens") or 0), cost, None, 0, None, error,
             time.strftime("%Y-%m-%dT%H:%M:%S"), json.dumps(meta or {})[:2000]))
        con.commit()
        con.close()
    except Exception:  # ledger write is best-effort; the cost is still returned and counted
        pass
    return cost


def write_node(messages: list[dict], model: str = WRITER_MODEL, max_tokens: int = 400,
               retries: int = 3, job_key: str = "") -> dict:
    """One writer call (injectable in tests). Returns {status, text, usage, error}."""
    last = ""
    for attempt in range(1, retries + 1):
        try:
            data = chat(model, messages, max_tokens=max_tokens, temperature=0.0, timeout_s=300)
            txt = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            usage = data.get("usage") or {}
            # Defect 18: same collision class as the judge row. `job_key` is a stable per-node id
            # (`f"p6:{nid}"`), so a retry inside this loop, or a `--force` re-run of the node,
            # overwrote the previous paid row and its spend. Suffix the attempt on the retry path.
            wkey = job_key or f"p6:{hashlib.sha256(json.dumps(messages).encode()).hexdigest()[:16]}"
            if attempt > 1:
                wkey = f"{wkey}#a{attempt}"
            _log(wkey, "p6_summary", model, usage)
            if txt.strip():
                return {"status": "ok", "text": txt, "usage": usage, "error": None}
            last = "blank"
        except Exception as exc:  # network / 429 / parse
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(min(20, attempt * 2))
    return {"status": "error", "text": "", "usage": {}, "error": last}


def judge_node(summary: str, ev: list[dict], model: str = JUDGE_MODEL, retries: int = 3) -> dict:
    """Judge one node's summary for faithfulness (0..1). Returns {score, verdict, why, error}.

    Owner architectural amendment (2026-11-15): the judge is Google `Gemma-4-31B-IT` on AMD Token
    Lab, replacing the rate-limited NIM free tier. No `provider=` is passed: the model id resolves
    through `llm_runner._provider_spec` to `amd_tokenlab`. The route is PAID, so `_log` is left to
    price the call (Defect 14) instead of booking an assumed 0.0. On the last attempt we fall back
    to the owner's `Qwen3.8-27B` before giving up.
    """
    msgs = [{"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": "EVIDENCE\n" + evidence_lines(ev) + "\n\nSUMMARY\n" + summary}]
    last = ""
    for attempt in range(1, retries + 1):
        try:
            active = model if attempt < retries else (JUDGE_FALLBACK_MODEL or model)
            data = chat(active, msgs, max_tokens=200, temperature=0.0, timeout_s=300)
            txt = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            # Defect 18: key the row by the whole request (model + evidence + summary + attempt),
            # not by the summary text alone. Every attempt is a separately invoiced call; a shared
            # key made `ON CONFLICT(job_key) DO UPDATE` overwrite the earlier paid row, so retry
            # spend silently vanished from `runner.spent()` and the §7.5 pipeline cap. Retries are
            # routine here: an unusable score is retried (Defect 17) and the last attempt runs on a
            # different (fallback) model id.
            jkey = "p6judge:" + hashlib.sha256(
                json.dumps([active, msgs, attempt]).encode()).hexdigest()[:16]
            _log(jkey, "p6_judge", active, data.get("usage") or {})
            # Defect 16: Gemma fences its JSON; keep tolerating a leading sentence too.
            obj = parse_json_object(txt)
            if obj:
                score = clamp_score(obj.get("score"))
                if score is None:
                    # Defect 17: the judge answered but its score is unusable (missing, non-numeric,
                    # or outside [0, 1]). `float(obj.get("score") or 0.0)` used to coerce that to a
                    # silent 0.0 (dropping a bad grade into `mean_score`) while `float("score": 3)`
                    # inflated `faithful_rate` past the 0.95 gate. Neither may be graded: retry, and
                    # if every attempt is unusable the row is returned with error='bad_score' so
                    # `run_judge` counts it as ungraded instead of scoring it.
                    last = f"bad_score:{obj.get('score')!r}"
                    continue
                return {"score": score, "verdict": obj.get("verdict"),
                        "why": obj.get("why"), "error": None}
            last = "no_json"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(min(20, attempt * 2))
    # Defect 21: an exhausted judge returns `score=None`, NOT 0.0. `run_judge` classifies the
    # ungraded rows by `r["score"] is None`, so the old 0.0 landed in `scores` as a *graded* zero:
    # a dead judge reported `graded=sampled, ungraded=0, ungraded_errors=[]`, and the gate's
    # `not judge_ungraded` guard never engaged. The outage then surfaced only as a low
    # `faithful_rate` -- i.e. it was misreported as unfaithfulness. The sentinel the classifier
    # tests for must be the sentinel the producer emits.
    return {"score": None, "verdict": None, "why": None, "error": last}


# ------------------------------------------------------------------ tree build
def load_index() -> dict:
    if INDEX.exists():
        try:
            return json.loads(INDEX.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def save_index(index: dict) -> None:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, indent=0, sort_keys=True), encoding="utf-8")


def append_node(node: dict) -> None:
    NODES.parent.mkdir(parents=True, exist_ok=True)
    with NODES.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(node, default=str) + "\n")


def choose_leaves(con, months_back: int = 0, segments: list[str] | None = None,
                  month_from: str | None = None) -> list[tuple[str, str]]:
    """Candidate (segment, month) leaves: every segment x every month that has documents."""
    segs = segments or list(SEGMENTS)
    rows = con.execute(
        """select distinct strftime(published_at, '%Y-%m') m from document
            where published_at is not null order by m""").fetchall()
    months = [r[0] for r in rows if r[0]]
    if month_from:
        months = [m for m in months if m >= month_from]
    if months_back:
        months = months[-months_back:]
    return [(seg, m) for m in months for seg in segs]


def build_leaf(con, index: dict, segment: str, period: str,
               segmap: dict[str, list[str]], writer=write_node, force: bool = False,
               dry: bool = False) -> dict:
    ev = leaf_evidence(con, segment, period, segmap)
    nid = node_id(segment, "month", period)
    ih = node_input_hash(segment, "month", period, ev)
    prior = index.get(nid) or {}
    node = {"node_id": nid, "segment": segment, "grain": "month", "period": period,
            "input_hash": ih, "evidence": ev, "children": [], "summary": "",
            "sentences": [], "drops": {}, "status": "empty"}
    if not ev:
        node["status"] = "no_evidence"
        return node
    if prior.get("input_hash") == ih and prior.get("status") == "ok" and not force:
        node.update({"summary": prior.get("summary", ""), "sentences": prior.get("sentences", []),
                     "status": "ok", "cached": True})
        return node
    if dry:
        node["status"] = "dry"
        return node
    msgs = writer_messages(segment, "month", period, ev)
    res = writer(msgs, job_key=f"p6:{nid}")
    cands = parse_summary(res.get("text") or "")
    kept, drops = validate_sentences(cands, ev, MAX_SENTENCES_LEAF)
    node.update({"sentences": kept, "drops": drops, "summary": summary_text(kept),
                 "status": "ok" if kept else "no_sentences", "call": res.get("status"),
                 "error": res.get("error")})
    return node


def build_parent(con, index: dict, segment: str, grain: str, period: str,
                 children: list[dict], ev_top: list[dict], writer=write_node,
                 force: bool = False, dry: bool = False) -> dict:
    nid = node_id(segment, grain, period)
    child_hashes = {c["node_id"]: c["input_hash"] for c in children}
    ih = node_input_hash(segment, grain, period, ev_top, child_hashes)
    prior = index.get(nid) or {}
    node = {"node_id": nid, "segment": segment, "grain": grain, "period": period,
            "input_hash": ih, "evidence": ev_top, "children": [c["node_id"] for c in children],
            "summary": "", "sentences": [], "drops": {}, "status": "empty"}
    usable = [c for c in children if c.get("status") == "ok" and c.get("summary")]
    if not usable:
        node["status"] = "no_evidence"
        return node
    if prior.get("input_hash") == ih and prior.get("status") == "ok" and not force:
        node.update({"summary": prior.get("summary", ""), "sentences": prior.get("sentences", []),
                     "status": "ok", "cached": True})
        return node
    if dry:
        node["status"] = "dry"
        return node
    max_sent = MAX_SENTENCES_PARENT
    msgs = writer_messages(segment, grain, period, ev_top, children=usable, max_sent=max_sent)
    res = writer(msgs, job_key=f"p6:{nid}")
    cands = parse_summary(res.get("text") or "")
    kept, drops = validate_sentences(cands, ev_top, max_sent)
    node.update({"sentences": kept, "drops": drops, "summary": summary_text(kept),
                 "status": "ok" if kept else "no_sentences", "call": res.get("status"),
                 "error": res.get("error")})
    return node


def build_tree(con, months_back: int = 0, segments: list[str] | None = None,
               month_from: str | None = None, limit: int = 0, dry: bool = False,
               force: bool = False, writer=write_node, progress: bool = True) -> dict:
    """Build leaves then parents. Resumable: `INDEX` skips nodes whose input_hash matches."""
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    index = load_index()
    segmap = series_segment_map(con)
    leaves = choose_leaves(con, months_back=months_back, segments=segments, month_from=month_from)
    if limit:
        leaves = leaves[:limit]
    done: dict[tuple[str, str], dict] = {}
    counts = {"leaves": 0, "parents_q": 0, "parents_y": 0, "cached": 0, "empty": 0,
              "sentences": 0, "dropped": 0}
    for i, (seg, month) in enumerate(leaves, 1):
        node = build_leaf(con, index, seg, month, segmap, writer=writer, force=force, dry=dry)
        done[(seg, month)] = node
        counts["leaves"] += 1
        counts["cached"] += int(bool(node.get("cached")))
        counts["empty"] += int(node["status"] in ("empty", "no_evidence", "no_sentences"))
        counts["sentences"] += len(node.get("sentences") or [])
        counts["dropped"] += sum((node.get("drops") or {}).values())
        if not dry:
            append_node(node)
            if node["status"] == "ok":
                index[node["node_id"]] = {"input_hash": node["input_hash"], "status": "ok",
                                          "summary": node["summary"],
                                          "sentences": node["sentences"],
                                          "segment": seg, "grain": "month", "period": month}
        if progress and i % 50 == 0:
            print(f"[p6] leaves {i}/{len(leaves)} sentences={counts['sentences']} "
                  f"empty={counts['empty']} wall={time.time() - t0:.0f}s", flush=True)

    quarter_nodes: dict[tuple[str, str], dict] = {}
    for seg in {s for s, _m in leaves}:
        months = [m for (s, m) in leaves if s == seg]
        qps = sorted({parent_period(m) for m in months if parent_period(m)})
        for qp in qps:
            children = [done[(seg, cm)] for cm in child_periods(qp) if (seg, cm) in done]
            ev_top = top_evidence([c for c in children], PARENT_TOP)
            node = build_parent(con, index, seg, "quarter", qp, children, ev_top,
                                writer=writer, force=force, dry=dry)
            quarter_nodes[(seg, qp)] = node
            counts["parents_q"] += 1
            counts["cached"] += int(bool(node.get("cached")))
            counts["empty"] += int(node["status"] in ("empty", "no_evidence", "no_sentences"))
            counts["sentences"] += len(node.get("sentences") or [])
            counts["dropped"] += sum((node.get("drops") or {}).values())
            if not dry:
                append_node(node)
                if node["status"] == "ok":
                    index[node["node_id"]] = {"input_hash": node["input_hash"], "status": "ok",
                                              "summary": node["summary"],
                                              "sentences": node["sentences"], "segment": seg,
                                              "grain": "quarter", "period": qp}

    for seg in {s for s, _m in leaves}:
        year_nodes: dict[str, dict] = {}
        qps = sorted({qp for (s, qp) in quarter_nodes if s == seg})
        years = sorted({qp[:4] for qp in qps})
        for year in years:
            children = [quarter_nodes[(seg, qp)] for qp in child_periods(year) if (seg, qp) in quarter_nodes]
            ev_top = top_evidence(children, PARENT_TOP)
            node = build_parent(con, index, seg, "year", year, children, ev_top,
                                writer=writer, force=force, dry=dry)
            year_nodes[year] = node
            counts["parents_y"] += 1
            counts["cached"] += int(bool(node.get("cached")))
            counts["empty"] += int(node["status"] in ("empty", "no_evidence", "no_sentences"))
            counts["sentences"] += len(node.get("sentences") or [])
            counts["dropped"] += sum((node.get("drops") or {}).values())
            if not dry:
                append_node(node)
                if node["status"] == "ok":
                    index[node["node_id"]] = {"input_hash": node["input_hash"], "status": "ok",
                                              "summary": node["summary"],
                                              "sentences": node["sentences"], "segment": seg,
                                              "grain": "year", "period": year}
    if not dry:
        save_index(index)
        tree = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "months_back": months_back, "month_from": month_from,
                "segments": sorted({s for s, _ in leaves}),
                "nodes": {nid: {k: v for k, v in meta.items() if k != "sentences"}
                          for nid, meta in index.items()}}
        TREE.write_text(json.dumps(tree, indent=0, default=str), encoding="utf-8")
    return {"counts": counts, "wall_seconds": round(time.time() - t0, 1), "dry": dry}


def top_evidence(children: list[dict], n: int) -> list[dict]:
    """Top-n underlying evidence items from children (one item per ref, first wins)."""
    out: list[dict] = []
    seen: set[str] = set()
    for child in children:
        for e in child.get("evidence") or []:
            key = f"{e['kind']}:{e['ref']}"
            if key in seen:
                continue
            seen.add(key)
            out.append(e)
            if len(out) >= n:
                return out
    return out


# ------------------------------------------------------------------ judge / report
def judge_sample(index: dict, n: int = JUDGE_SAMPLE, seed: int = 0) -> list[str]:
    ids = sorted(index)
    rng = random.Random(seed)
    return rng.sample(ids, min(n, len(ids)))


def iter_nodes(path: Path = NODES):
    """Stream node records; a later line for the same node_id wins (rebuild overwrite)."""
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def load_nodes(ids: set[str], path: Path = NODES) -> dict[str, dict]:
    """Latest node record for each wanted node_id (streams the file once)."""
    out: dict[str, dict] = {}
    for node in iter_nodes(path):
        nid = node.get("node_id")
        if nid in ids:
            out[nid] = node
    return out


def run_judge(index: dict, n: int = JUDGE_SAMPLE, seed: int | None = None,
              judge=judge_node, path: Path = NODES) -> dict:
    if seed is None:
        seed = seed_for(PHASE)
    ids = judge_sample(index, n=n, seed=seed)
    nodes = load_nodes(set(ids), path=path)
    rows = []
    for nid in ids:
        node = nodes.get(nid) or {}
        sentences = node.get("sentences") or index.get(nid, {}).get("sentences") or []
        if not sentences:
            continue
        text = " ".join(f"{s['sentence']} " + "".join(f"[{c}]" for c in s["cites"]) for s in sentences)
        ev = node.get("evidence") or []
        res = judge(text, ev)
        rows.append({"node_id": nid, "segment": node.get("segment"), "grain": node.get("grain"),
                     "period": node.get("period"), "score": res.get("score"),
                     "verdict": res.get("verdict"), "error": res.get("error")})
    scores = [r["score"] for r in rows if r["score"] is not None]
    ungraded = [r for r in rows if r["score"] is None]
    # Defect 17: rows the judge could not score used to vanish from every statistic, so a judge that
    # never answered reported `sampled=60, faithful_rate=1.0` off the few rows it did answer -- the
    # silent-zero class. `ungraded_*` makes that visible and `gate_passed` requires it to be zero.
    return {"sampled": len(rows), "seed": seed,
            "graded": len(scores), "ungraded": len(ungraded),
            "ungraded_rate": round(len(ungraded) / len(rows), 4) if rows else None,
            "ungraded_errors": sorted({str(r.get("error")) for r in ungraded}),
            # Defect 21 corollary: with no graded row there is no mean and no rate -- `if scores
            # else 0.0` printed `faithful_rate 0.0` for a judge that graded nothing, which reads as
            # "the writer was unfaithful" instead of "the judge did not run". None keeps the outage
            # distinct from a measured zero, and `build_report` already treats a None rate as a
            # failed gate rather than a passing one.
            "mean_score": round(sum(scores) / len(scores), 4) if scores else None,
            "faithful_rate": round(sum(1 for s in scores if s >= 0.5) / len(scores), 4) if scores else None,
            "rows": rows}


def phase_spend_usd() -> float | None:
    """Cumulative ledger spend for the P6 passes, or None if the ledger is unreadable.

    Defect 17: `build_report` hardcoded `spend_usd: 0.0`. After the owner's amendment both P6 models
    run on the PAID `amd_tokenlab` route, so a literal 0.0 told the gate report, the §7.5 global cap
    ($82) and the owner's `/stats` view that P6 cost nothing. Measured from `jobs`, best-effort so a
    missing/locked ledger degrades to None (explicitly "unmeasured") instead of a false 0.0.
    """
    try:
        return R.spent_exact(passes=["p6_summary", "p6_judge"])
    except Exception:  # noqa: BLE001 - a report must never fail on accounting
        return None


def build_report(index: dict, build: dict, judge: dict | None = None) -> dict:
    nodes = [{"node_id": nid, **{k: v for k, v in meta.items() if k != "sentences"}}
             for nid, meta in sorted(index.items())]
    by_grain = {}
    for nd in nodes:
        by_grain.setdefault(nd["grain"], 0)
        by_grain[nd["grain"]] += 1
    total_sentences = sum(len(m.get("sentences") or []) for m in index.values())
    report = {
        "phase": PHASE,
        "sample_seed": seed_for(PHASE),
        "counts": build["counts"],
        "wall_seconds": build["wall_seconds"],
        "nodes_by_grain": by_grain,
        "sentences_kept": total_sentences,
        "number_check": {
            "sentences_kept": total_sentences,
            "kept_sentences_with_number_failure": 0,  # dropped by construction (§8 citation rule)
            "silent_drop": "none: every rule failure is counted in the per-node drops",
            "pass_rate": 1.0,
        },
        "judge": judge or {"sampled": 0, "mean_score": None, "faithful_rate": None},
        "writer_model": WRITER_MODEL,
        "writer_family": _family(WRITER_MODEL),
        "judge_model": JUDGE_MODEL,
        # Derived, never hardcoded: the owner swapped the judge (NIM openai -> AMD gemma) and a frozen
        # literal would have kept certifying a family that is no longer running (Defect 15).
        "judge_family": _family(JUDGE_MODEL),
        "judge_family_differs_from_writer": _family(JUDGE_MODEL) != _family(WRITER_MODEL),
        "spend_usd": phase_spend_usd(),
        "sample_nodes": nodes[:10],
    }
    # Defect 17: ungraded rows must block the gate. `run_judge` reports them; a judge that answered
    # only a handful of nodes otherwise showed a `faithful_rate` computed over that handful.
    judge_ungraded = (judge or {}).get("ungraded")
    report["gate_passed"] = bool(judge and judge.get("faithful_rate") is not None
                                 and judge["faithful_rate"] >= 0.95
                                 and report["number_check"]["pass_rate"] == 1.0
                                 and not judge_ungraded)
    return report


def _md(report: dict) -> str:
    c = report["counts"]
    j = report["judge"]
    return "\n".join([
        "# P6 time-tree summary report",
        "",
        "Design note",
        "",
        "- Segments tagged by deterministic keyword patterns (§8 list), grains month -> quarter -> year,",
        "  parents built from children plus the top-10 underlying evidence items.",
        "- Every kept sentence cites an obs/chunk/event/claim id from its evidence pack and every number",
        "  in it must occur in the cited evidence text; failing sentences are dropped and counted.",
        "- `input_hash` over the evidence pack (plus child hashes) makes rebuilds incremental.",
        "- Writer = AMD bulk model (family deepseek); judge = Google `Gemma-4-31B-IT` on AMD Token Lab",
        "  (family gemma, owner amendment 2026-11-15 replacing the NIM free tier), so the judge family",
        "  differs from the writer family (§11 P6).",
        "",
        f"- leaves {c['leaves']}, quarter nodes {c['parents_q']}, year nodes {c['parents_y']}",
        f"- cached {c['cached']}, empty {c['empty']}",
        f"- sentences kept {report['sentences_kept']}, rule-dropped {c['dropped']}",
        f"- automatic number check: pass rate {report['number_check']['pass_rate']} "
        f"(kept-sentence failures {report['number_check']['kept_sentences_with_number_failure']})",
        f"- judge faithfulness: {j.get('faithful_rate')} over {j.get('sampled')} nodes "
        f"(mean score {j.get('mean_score')}, need >= 0.95)",
        f"- judge graded {j.get('graded', j.get('sampled'))} · ungraded {j.get('ungraded', 0)} "
        f"(rate {j.get('ungraded_rate')}; ungraded rows block the gate)",
        "- spend "
        + M.fmt_usd(report.get("spend_usd"), unmeasured="UNMEASURED (ledger unreadable)")
        + f", wall {report['wall_seconds']}s",
        f"- gate: {'PASSED' if report['gate_passed'] else 'FAILED'}",
        "",
        "## Sample nodes",
        "",
    ] + [f"- `{n['node_id']}` {n['segment']} {n['grain']} {n['period']}: {str(n.get('summary'))[:160]}"
         for n in report["sample_nodes"]])


def connect(db: Path = KB_DB, read_only: bool = True):
    con = duckdb.connect(str(db), read_only=read_only)
    con.execute("SET memory_limit='700MB'")
    con.execute("SET threads=2")
    return con


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P6: time-tree period summaries")
    ap.add_argument("--months-back", type=int, default=0)
    ap.add_argument("--month-from", default=None)
    ap.add_argument("--segment", action="append", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--db", default=str(KB_DB))
    args = ap.parse_args(argv)
    con = connect(Path(args.db))
    try:
        build = build_tree(con, months_back=args.months_back, segments=args.segment,
                           month_from=args.month_from, limit=args.limit, dry=args.dry,
                           force=args.force)
    finally:
        con.close()
    index = load_index()
    judge = run_judge(index) if args.judge else None
    report = build_report(index, build, judge)
    print(json.dumps({"counts": report["counts"], "judge": report["judge"],
                      "gate_passed": report["gate_passed"]}, indent=2, default=str))
    if args.report:
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "P6.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        (REPORTS / "P6.md").write_text(_md(report), encoding="utf-8")
        print("wrote kb/reports/P6.json + P6.md")
    return 0 if (not args.report or report["gate_passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
