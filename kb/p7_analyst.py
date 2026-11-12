"""P7 analyst mode: cycle indicators, cited rules, forecast ledger, labelled judgment.

Design (task doc item 5, build plan §9):
1. Indicators are COMPUTED in SQL from the DB (earnings percentile, asset P/E, newbuild-
   secondhand-scrap spread, orderbook/fleet, scrapping, broker sentiment, asset-vs-earnings);
   each carries the obs/txn ids it came from, so every number is traceable.
2. Book principles are retrieved as cited chunks (tools.search) — never invented.
3. Forecast ledger: which publisher's directional claims in this segment were later right.
4. The LLM writes only (a) narrative over computed facts and indicators, (b) the judgment
   with reasoning, confidence and counter-argument. Every number it prints is checked
   against the computed values; a judgment is labelled a judgment, never a fact.
5. Backtest: run the analyst "as known on" >=20 past dates, score the directional call
   against the realised move afterwards, report the hit rate.
"""
from __future__ import annotations

import json
import math
import re
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ask as A  # noqa: E402
import tools as T  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
P7_DIR = ROOT / "kb" / "state" / "p7"
ANALYST_LOG = P7_DIR / "analyst.jsonl"
JUDGE_MODEL = "openai/gpt-oss-120b"
SEGMENT_ALIASES = {
    "capesize": ["capesize", "cape", "bci"],
    "panamax": ["panamax", "pnmx", "bpi"],
    "supramax": ["supramax", "ultramax", "bsi"],
    "handysize": ["handysize", "handy", "bhs"],
    "vlcc": ["vlcc"],
    "suezmax": ["suezmax"],
    "aframax": ["aframax", "lr2"],
    "mr_lr": ["mr", "lr1"],
    "lng": ["lng", "liquefied natural"],
    "lpg": ["lpg"],
    "container": ["container", "teu"],
    "snp": ["secondhand", "resale", "sale and purchase"],
    "demolition": ["demolition", "scrap", "scrapping"],
    "newbuilding": ["newbuilding", "newbuild", "orderbook"],
    "iron_ore": ["iron ore", "c3", "c5"],
    "coal": ["coal"],
    "grains": ["grain", "wheat", "corn", "soy"],
    "bunkers": ["bunker", "vlsfo", "hfo"],
}
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split((text or "").strip()) if s.strip()]
BOOK_QUERIES = {
    "contrarian": "old owners buy ships when earnings are terrible sell when great counter-cyclical timing",
    "cycle": "shipping cycle stages peak trough asset values newbuilding orderbook",
    "deals": "best deals worst cash flow asset play value buying secondhand",
}
BOOK_K = 4
MIN_HISTORY = 12
HORIZON_DAYS = 90
FLAT_BAND = 0.05
SENTIMENT_WINDOW = 90
BACKTEST_DATES = 20

JUDGE_PROMPT = """You grade an analyst-mode answer from a maritime research system.
Rubric (0..1 each): facts_cited (every factual sentence has a [cite:...] handle),
indicators_correct (numbers match the given indicator table), judgment_reasoned (judgment
explains reasoning and is labelled a judgment, not a fact), counter_argument_present.
Return JSON only: {"facts_cited":0-1,"indicators_correct":0-1,"judgment_reasoned":0-1,
"counter_argument_present":0-1,"score":0-1,"notes":"..."}"""

ANALYST_PROMPT = """You are the analyst layer of a maritime knowledge base. You may use ONLY
the supplied computed facts, indicators and book quotes. Rules:
- (a) FACTS: 1-3 sentences, each ending with one or more [cite:kind:id] handles copied from the
  evidence. Never print a number that is not in the evidence.
- (b) INDICATORS: 1-3 sentences naming the computed indicators, with the printed values; each ends
  with the matching [cite:...] handle.
- (c) JUDGMENT: 2-4 sentences. State the view, the reasoning, then CONFIDENCE: <0-1>.
  Then COUNTER_ARGUMENT: the strongest argument against the view. Label the view "judgment".
- If the evidence is too thin to judge, answer exactly NOT_ENOUGH_DATA.
Format exactly:
FACTS: ...
INDICATORS: ...
JUDGMENT: ...
CONFIDENCE: 0.0
COUNTER_ARGUMENT: ..."""


# --------------------------------------------------------------------------- utils
def as_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def pct_rank(values: list[float], value: float) -> float | None:
    vals = [v for v in values if v is not None and math.isfinite(v)]
    if len(vals) < MIN_HISTORY or value is None:
        return None
    below = sum(1 for v in vals if v <= value)
    return round(below / len(vals), 4)


def median(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None and math.isfinite(v)]
    return round(statistics.median(vals), 4) if vals else None


def segment_terms(segment: str) -> list[str]:
    return SEGMENT_ALIASES.get((segment or "").lower(), [segment])


def _like_any(col: str, terms: list[str]) -> tuple[str, list]:
    sql = " OR ".join([f"{col} ILIKE ?"] * len(terms))
    return f"({sql})", [f"%{t}%" for t in terms]


def connect(db=None):
    return T.connect(T.KB_DB if db is None else db)


# --------------------------------------------------------------------------- indicators
def earnings_series(con, segment: str, as_of: date | None) -> list[tuple[date, float, str]]:
    terms = segment_terms(segment)
    where, params = _like_any("route", terms)
    cutoff = (as_of or date.today()).isoformat()
    rows = T._query(
        f"SELECT period_to, value, obs_id FROM v_rate WHERE {where} AND period_to <= ? "
        f"AND value IS NOT NULL AND value > 0 ORDER BY period_to",
        con=con, params=params + [cutoff]).get("rows", [])
    return [(as_date(r[0]), float(r[1]), f"obs:{r[2]}") for r in rows if as_date(r[0])]


def indicator_earnings(con, segment: str, as_of: date | None) -> dict:
    ser = earnings_series(con, segment, as_of)
    if len(ser) < MIN_HISTORY:
        return {"name": "earnings", "status": "insufficient", "n": len(ser), "cites": []}
    latest = ser[-1]
    values = [v for _d, v, _c in ser]
    return {"name": "earnings", "status": "ok", "period_to": latest[0].isoformat(),
            "value": round(latest[1], 4), "percentile": pct_rank(values, latest[1]),
            "n": len(values), "median": median(values[-365:]), "cites": [latest[2]]}


def _sale_prices(con, segment: str, as_of: date | None) -> list[tuple[date, float, str]]:
    terms = segment_terms(segment)
    where, params = _like_any("vessel_name", terms)
    cutoff = (as_of or date.today()).isoformat()
    rows = T._query(
        f"SELECT date_from, TRY_CAST(replace(CAST(price AS VARCHAR), chr(34), '') AS DOUBLE) AS p, txn_id FROM v_sale WHERE {where} "
        f"AND date_from <= ? AND TRY_CAST(replace(CAST(price AS VARCHAR), chr(34), '') AS DOUBLE) > 0 ORDER BY date_from",
        con=con, params=params + [cutoff]).get("rows", [])
    out = []
    for d, p, txn in rows:
        p = float(p)
        if p < 1000:      # broker convention: millions of USD
            p *= 1e6
        if as_date(d):
            out.append((as_date(d), p, f"txn:{txn}"))
    return out


def indicator_asset_pe(con, segment: str, as_of: date | None, earn: dict) -> dict:
    sales = _sale_prices(con, segment, as_of)
    if len(sales) < 5 or earn.get("status") != "ok" or not earn.get("value"):
        return {"name": "asset_pe", "status": "insufficient", "n": len(sales),
                "cites": [s[2] for s in sales[-3:]]}
    recent = [p for _d, p, _c in sales[-20:]]
    sh = median(recent)
    annual_tce = earn["value"] * 365.0
    pe = round(sh / annual_tce, 3) if annual_tce else None
    return {"name": "asset_pe", "status": "ok", "secondhand_usd": sh, "annual_tce_usd": round(annual_tce, 2),
            "pe_years": pe, "n": len(recent), "cites": [s[2] for s in sales[-3:]] + earn.get("cites", [])}


def indicator_spreads(con, segment: str, as_of: date | None) -> dict:
    terms = segment_terms(segment)
    cutoff = (as_of or date.today()).isoformat()
    where, params = _like_any("vessel_name", terms)
    nb = T._query(f"SELECT TRY_CAST(replace(CAST(price AS VARCHAR), chr(34), '') AS DOUBLE) FROM v_newbuilding WHERE {where} AND date_from <= ? "
               f"AND TRY_CAST(replace(CAST(price AS VARCHAR), chr(34), '') AS DOUBLE) > 0", con=con, params=params + [cutoff]).get("rows", [])
    dm = T._query(f"SELECT TRY_CAST(replace(CAST(price AS VARCHAR), chr(34), '') AS DOUBLE) FROM v_demolition WHERE {where} AND date_from <= ? "
               f"AND TRY_CAST(replace(CAST(price AS VARCHAR), chr(34), '') AS DOUBLE) > 0", con=con, params=params + [cutoff]).get("rows", [])
    sh = _sale_prices(con, segment, as_of)
    nb_p = median([(p * 1e6 if p < 1000 else p) for (p,) in nb])
    dm_p = median([float(p) for (p,) in dm])
    sh_p = median([p for _d, p, _c in sh[-20:]])
    spread = round(sh_p - nb_p, 2) if (sh_p and nb_p) else None
    return {"name": "newbuild_secondhand_scrap", "status": "ok" if (nb_p or dm_p) else "insufficient",
            "newbuild_usd": nb_p, "secondhand_usd": sh_p, "scrap_price_printed": dm_p,
            "secondhand_minus_newbuild_usd": spread, "n_newbuild": len(nb), "n_demolition": len(dm),
            "cites": [c for _d, _p, c in sh[-2:]]}


def indicator_orderbook(con, segment: str, as_of: date | None) -> dict:
    terms = segment_terms(segment)
    where, params = _like_any("vessel_name", terms)
    cutoff = (as_of or date.today()).isoformat()
    rows = T._query(f"SELECT date_from, txn_id FROM v_newbuilding WHERE {where} AND date_from <= ?",
                 con=con, params=params + [cutoff]).get("rows", [])
    if len(rows) < 5:
        return {"name": "orderbook", "status": "insufficient", "n": len(rows), "cites": []}
    end = as_of or date.today()
    start = end - timedelta(days=365)
    by_month = defaultdict(int)
    for d, _t in rows:
        dd = as_date(d)
        if dd:
            by_month[(dd.year, dd.month)] += 1
    recent = sum(1 for d, _t in rows if (dd := as_date(d)) and start <= dd <= end)
    hist = [by_month[k] for k in sorted(by_month)][:-1] or [0]
    return {"name": "orderbook", "status": "ok", "orders_last_12m": recent,
            "prior_month_counts": hist[-12:], "percentile": pct_rank([float(x) for x in hist], float(recent)),
            "n": len(rows), "cites": [f"txn:{r[1]}" for r in rows[-3:]]}


def indicator_scrapping(con, segment: str, as_of: date | None) -> dict:
    terms = segment_terms(segment)
    where, params = _like_any("vessel_name", terms)
    cutoff = (as_of or date.today()).isoformat()
    rows = T._query(f"SELECT date_from, txn_id FROM v_demolition WHERE {where} AND date_from <= ?",
                 con=con, params=params + [cutoff]).get("rows", [])
    if not rows:
        return {"name": "scrapping", "status": "insufficient", "n": 0, "cites": []}
    end = as_of or date.today()
    start = end - timedelta(days=365)
    recent = [r for r in rows if (d := as_date(r[0])) and start <= d <= end]
    return {"name": "scrapping", "status": "ok", "demolitions_last_12m": len(recent),
            "demolitions_total": len(rows), "cites": [f"txn:{r[1]}" for r in recent[-3:]]}


def indicator_sentiment(con, segment: str, as_of: date | None) -> dict:
    terms = segment_terms(segment)
    where, params = _like_any("quote", terms)
    end = as_of or date.today()
    start = end - timedelta(days=SENTIMENT_WINDOW)
    try:
        rows = T._query(f"SELECT direction, claim_id FROM claim WHERE {where} AND published_at <= ? "
                     f"AND published_at >= ?", con=con,
                     params=params + [end.isoformat(), start.isoformat()]).get("rows", [])
    except T.ToolError:
        return {"name": "sentiment", "status": "unavailable", "cites": []}
    if not rows:
        return {"name": "sentiment", "status": "insufficient", "n": 0, "cites": []}
    c = defaultdict(int)
    for direction, _cid in rows:
        c[(direction or "none").lower()] += 1
    up, down = c.get("up", 0), c.get("down", 0)
    net = round((up - down) / max(1, up + down), 4)
    return {"name": "sentiment", "status": "ok", "up": up, "down": down, "net": net,
            "window_days": SENTIMENT_WINDOW, "cites": [f"claim:{r[1]}" for r in rows[-3:]]}


def indicators(con, segment: str, as_of: date | None = None) -> dict:
    earn = indicator_earnings(con, segment, as_of)
    out = [earn, indicator_asset_pe(con, segment, as_of, earn),
           indicator_spreads(con, segment, as_of), indicator_orderbook(con, segment, as_of),
           indicator_scrapping(con, segment, as_of), indicator_sentiment(con, segment, as_of)]
    ok = [i for i in out if i.get("status") == "ok"]
    return {"segment": segment, "as_of": (as_of or date.today()).isoformat(),
            "indicators": out, "ok": len(ok), "cites": sorted({c for i in ok for c in i.get("cites", [])})}


def valuation_label(inds: dict) -> str | None:
    earn = next((i for i in inds["indicators"] if i["name"] == "earnings"), {})
    pe = next((i for i in inds["indicators"] if i["name"] == "asset_pe"), {})
    ep, pp = earn.get("percentile"), pe.get("pe_years")
    if ep is None or pp is None:
        return None
    if ep >= 0.75:
        return "earnings high in history: late-cycle, asset values vulnerable"
    if ep <= 0.25:
        return "earnings low in history: contrarian buy window per book principles"
    return "mid-cycle: earnings mid-range"


# --------------------------------------------------------------------------- rules + ledger
def book_rules(con, segment: str, chat=None) -> list[dict]:
    out = []
    for topic, q in BOOK_QUERIES.items():
        try:
            res = T.search(f"{q} {segment}", {"doc_type": "book"}, k=BOOK_K, con=con)
        except T.ToolError:
            res = {"results": []}
        for r in res.get("results", [])[:2]:
            out.append({"topic": topic, "chunk_id": r["chunk_id"], "path": r["path"],
                        "quote": (r.get("snippet") or "")[:300], "cite": f"chunk:{r['chunk_id']}"})
    return out


def forecast_ledger(con, segment: str, as_of: date | None) -> dict:
    terms = segment_terms(segment)
    where, params = _like_any("c.quote", terms)
    end = as_of or date.today()
    try:
        rows = T._query(
            f"SELECT c.direction, c.published_at, d.publisher_id, c.claim_id FROM claim c "
            f"LEFT JOIN document d ON d.doc_id = c.doc_id WHERE {where} AND c.kind = 'forecast' "
            f"AND c.published_at <= ?", con=con, params=params + [end.isoformat()]).get("rows", [])
    except T.ToolError:
        return {"status": "unavailable", "publishers": [], "cites": []}
    if not rows:
        return {"status": "no_claims", "publishers": [], "cites": []}
    ser = earnings_series(con, segment, end)
    # realised direction = sign of the median earnings move over HORIZON_DAYS after each claim
    realised = []
    for i, (d, v, _c) in enumerate(ser):
        later = [x for x in ser[i + 1:] if (x[0] - d).days >= HORIZON_DAYS]
        realised.append((d, (later[0][1] - v) / v if later and v else None))
    by_pub = defaultdict(lambda: {"right": 0, "scored": 0})
    for direction, pubdate, pub, _cid in rows:
        pd_ = as_date(pubdate)
        if not pd_:
            continue
        nxt = [r for dd, r in realised if dd >= pd_ and r is not None]
        if not nxt or (direction or "").lower() not in ("up", "down"):
            continue
        right = (nxt[0] > FLAT_BAND) if direction.lower() == "up" else (nxt[0] < -FLAT_BAND)
        key = pub or "unknown"
        by_pub[key]["scored"] += 1
        by_pub[key]["right"] += int(right)
    pubs = [{"publisher": k, "scored": v["scored"], "right": v["right"],
             "hit_rate": round(v["right"] / v["scored"], 3)} for k, v in by_pub.items() if v["scored"] >= 3]
    pubs.sort(key=lambda x: (-x["scored"], x["publisher"]))
    return {"status": "ok" if pubs else "thin", "publishers": pubs, "claims": len(rows),
            "cites": []}


# --------------------------------------------------------------------------- judgment
def _evidence_lines(inds: dict, rules: list[dict], ledger: dict) -> list[str]:
    lines = []
    for i in inds["indicators"]:
        if i.get("status") != "ok":
            lines.append(f"INDICATOR {i['name']}: insufficient data ({i.get('n', 0)} rows)")
            continue
        bits = ", ".join(f"{k}={v}" for k, v in i.items()
                         if k not in ("name", "status", "cites") and v is not None)
        lines.append(f"INDICATOR {i['name']}: {bits} [cite:{i['cites'][0]}]" if i.get("cites")
                     else f"INDICATOR {i['name']}: {bits}")
    for r in rules:
        lines.append(f"BOOK {r['topic']}: \"{r['quote']}\" [{r['cite']}]")
    for p in ledger.get("publishers", [])[:5]:
        lines.append(f"LEDGER {p['publisher']}: {p['right']}/{p['scored']} directional calls right "
                     f"(hit {p['hit_rate']})")
    return lines


def compose_analyst(question: str, segment: str, as_of: date | None, inds: dict,
                    rules: list[dict], ledger: dict, model: str, chat=None) -> tuple[str, dict, float]:
    chat = chat or A._chat
    val = valuation_label(inds)
    user = (f"Question: {question}\nSegment: {segment}\nAs of: {(as_of or date.today()).isoformat()}\n"
            f"Valuation read: {val or 'unknown'}\n\nEvidence:\n" + "\n".join(_evidence_lines(inds, rules, ledger))
            + "\n\n" + ANALYST_PROMPT)
    text, usage, cost = chat(model, [{"role": "system", "content": ANALYST_PROMPT},
                                     {"role": "user", "content": user}], 900)
    return text, usage or {}, float(cost or 0.0)


def parse_analyst(text: str) -> dict:
    out = {"status": "empty", "facts": "", "indicators": "", "judgment": "", "confidence": None,
           "counter_argument": "", "sentences": []}
    if not text:
        return out
    if "NOT_ENOUGH_DATA" in text:
        out["status"] = "not_enough_data"
        return out
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        head = line.split(":", 1)[0].strip().lower()
        if head in ("facts", "indicators", "judgment", "confidence", "counter_argument"):
            cur = head
            val = line.split(":", 1)[1].strip() if ":" in line else ""
            if cur == "confidence":
                try:
                    out["confidence"] = max(0.0, min(1.0, float(val.split()[0])))
                except (ValueError, IndexError):
                    out["confidence"] = None
            else:
                out[cur] = (out[cur] + " " + val).strip()
        elif cur and cur not in ("confidence",):
            out[cur] = (out[cur] + " " + line).strip()
    ok = bool(out["facts"] and out["indicators"] and out["judgment"] and out["counter_argument"]
              and out["confidence"] is not None)
    out["status"] = "ok" if ok else "malformed"
    for part in ("facts", "indicators", "judgment"):
        for s in split_sentences(out[part]):
            out["sentences"].append({"part": part, "sentence": s})
    return out


def check_analyst(parsed: dict, have_numbers: list[float], resolve) -> tuple[dict, dict]:
    """Every number in the narrative must exist in computed evidence; every fact/indicator
    sentence must carry a resolvable cite. Judgment sentences are exempt from number checks
    (they may reference the computed values only)."""
    drops = {"no_cite": 0, "cite_unresolved": 0, "number_not_in_evidence": 0}
    kept = []
    for s in parsed.get("sentences", []):
        cites = A.CITE.findall(s["sentence"])
        handles = list(cites)
        if s["part"] in ("facts", "indicators"):
            if not handles:
                drops["no_cite"] += 1
                continue
            resolved = [resolve(h) for h in handles]
            if not any(resolved):
                drops["cite_unresolved"] += 1
                continue
        ok, _missing = A.numbers_supported(s["sentence"], have_numbers)
        if not ok:
            drops["number_not_in_evidence"] += 1
            continue
        kept.append(s)
    parsed = dict(parsed)
    parsed["sentences"] = kept
    parsed["dropped"] = drops
    if not kept:
        parsed["status"] = "not_in_data"
    return parsed, drops


def evidence_numbers(inds: dict) -> list[float]:
    vals = []
    for i in inds["indicators"]:
        for k, v in i.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals.append(float(v))
            elif isinstance(v, list):
                vals.extend(float(x) for x in v if isinstance(x, (int, float)))
    return vals


def render(parsed: dict) -> str:
    parts = []
    for s in parsed["sentences"]:
        parts.append(s["sentence"])
    body = " ".join(parts)
    tail = f" CONFIDENCE: {parsed['confidence']}"
    if parsed.get("counter_argument"):
        tail += f" COUNTER_ARGUMENT: {parsed['counter_argument']}"
    return (body + tail).strip()


# --------------------------------------------------------------------------- backtest
def backtest_dates(con, segment: str, n: int = BACKTEST_DATES) -> list[date]:
    ser = earnings_series(con, segment, None)
    if len(ser) < n:
        return []
    step = max(1, len(ser) // (n + 2))
    picks = [ser[i * step][0] for i in range(1, n + 1) if i * step < len(ser)]
    return picks[:n]


def realised_move(con, segment: str, as_of: date, horizon_days: int = HORIZON_DAYS) -> float | None:
    ser = earnings_series(con, segment, None)
    before = [x for x in ser if x[0] <= as_of]
    after = [x for x in ser if (x[0] - as_of).days >= horizon_days]
    if not before or not after:
        return None
    a, b = before[-1][1], after[0][1]
    return round((b - a) / a, 4) if a else None


def call_direction(text: str) -> str | None:
    low = (text or "").lower()
    up = any(w in low for w in ("firm", "upside", "rise", "improve", "higher", "buy", "tight"))
    down = any(w in low for w in ("soft", "downside", "fall", "weaken", "lower", "sell", "oversupply"))
    if up and not down:
        return "up"
    if down and not up:
        return "down"
    return None


def score_calls(rows: list[dict]) -> dict:
    scored = [r for r in rows if r.get("call") and r.get("realised") is not None]
    hits = [r for r in scored if (r["realised"] > FLAT_BAND if r["call"] == "up"
                                  else r["realised"] < -FLAT_BAND)]
    return {"n": len(scored), "hits": len(hits),
            "hit_rate": round(len(hits) / len(scored), 4) if scored else None}


# --------------------------------------------------------------------------- entry points
def analyse(question: str, segment: str, as_of: date | None = None, model: str = A.DEFAULT_MODEL,
            escalate: bool = True, con=None, chat=None, db=None) -> dict:
    own = con is None
    con = con or connect(db)
    try:
        inds = indicators(con, segment, as_of)
        rules = book_rules(con, segment)
        ledger = forecast_ledger(con, segment, as_of)
        if inds["ok"] == 0 and not rules:
            return {"status": "not_in_data", "answer": A.NOT_IN_DATA, "segment": segment,
                    "as_of": (as_of or date.today()).isoformat(), "indicators": inds,
                    "cost_usd": 0.0}
        record = {"question": question, "segment": segment,
                  "as_of": (as_of or date.today()).isoformat(), "model": model, "escalated": False}
        parsed = {"status": "empty", "sentences": [], "confidence": None, "counter_argument": ""}
        cost = 0.0
        for attempt_model in ([model, A.ESCALATION_MODEL] if escalate else [model]):
            text, _usage, c = compose_analyst(question, segment, as_of, inds, rules, ledger,
                                             attempt_model, chat=chat)
            cost += c
            parsed = parse_analyst(text)
            if parsed["status"] in ("ok", "not_enough_data"):
                record["model"] = attempt_model
                record["escalated"] = attempt_model != model
                break
            record["model"] = attempt_model
            record["escalated"] = attempt_model != model
        resolve = A._resolver(con, {})
        parsed, drops = check_analyst(parsed, evidence_numbers(inds), resolve)
        parsed["dropped"] = drops
        record.update({"status": parsed["status"],
                       "answer": render(parsed) if parsed["status"] == "ok" else A.NOT_IN_DATA,
                       "facts": parsed.get("facts", ""), "indicators_text": parsed.get("indicators", ""),
                       "judgment": parsed.get("judgment", ""), "confidence": parsed.get("confidence"),
                       "counter_argument": parsed.get("counter_argument", ""),
                       "cites": [], "cost_usd": round(cost, 6), "indicators": inds,
                       "rules": rules, "ledger": ledger, "dropped": drops})
        for s in parsed.get("sentences", []):
            record["cites"].extend(A.CITE.findall(s["sentence"]))
        return record
    finally:
        if own:
            con.close()


def judge_answer(question: str, record: dict, model: str = JUDGE_MODEL, chat=None) -> dict:
    chat = chat or A._chat
    ind_lines = [f"{i['name']}: {i.get('value', i.get('orders_last_12m', i.get('net', '')))}"
                 for i in record.get("indicators", {}).get("indicators", []) if i.get("status") == "ok"]
    user = (f"Question: {question}\nAnswer:\n{record.get('answer', '')}\n\n"
            f"Indicator table:\n" + "\n".join(ind_lines) + "\n\n" + JUDGE_PROMPT)
    text, usage, cost = chat(model, [{"role": "system", "content": JUDGE_PROMPT},
                                     {"role": "user", "content": user}], 500)
    return json.loads(text, strict=False) if text else {}


def run_backtest(segment: str, n: int = BACKTEST_DATES, con=None, chat=None, db=None) -> dict:
    own = con is None
    con = con or connect(db)
    try:
        rows = []
        for d in backtest_dates(con, segment, n):
            rec = analyse(f"Where will {segment} be from {d.isoformat()}?", segment, d,
                          con=con, chat=chat, escalate=False)
            call = call_direction(rec.get("judgment") or rec.get("answer") or "")
            rows.append({"as_of": d.isoformat(), "call": call,
                         "confidence": rec.get("confidence"), "status": rec["status"],
                         "realised": realised_move(con, segment, d),
                         "cost_usd": rec.get("cost_usd", 0.0)})
        return {"segment": segment, "dates": len(rows), "rows": rows, **score_calls(rows)}
    finally:
        if own:
            con.close()


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="kb.p7_analyst", description="analyst mode + backtest")
    ap.add_argument("question", nargs="?")
    ap.add_argument("--segment", default="capesize")
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--dates", type=int, default=BACKTEST_DATES)
    ap.add_argument("--model", default=A.DEFAULT_MODEL)
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.backtest:
        res = run_backtest(a.segment, a.dates, db=a.db)
    else:
        if not a.question:
            ap.error("question required unless --backtest")
        res = analyse(a.question, a.segment, as_date(a.as_of), model=a.model, db=a.db)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str))
    return 0 if res.get("status", "ok") in ("ok", "not_in_data", "not_enough_data") else 1
