"""P4a step 3 — deterministic retrieval gold set (the "retrieval part of the Q&A gold set").

The full 250-question Q&A gold set is built after P4b (plan §12.1), but the P4a gate is
`retrieval_recall_at_20 >= 0.85`, so P4a needs its own labelled retrieval questions now. These
are built mechanically from the KB so the labels are exact chunk ids, not judgements:

  vessel_entity   55  "what was reported about <vessel>"      gold = chunks carrying that entity id
  company_entity  35  same for companies (SEC-heavy)          gold = tagged chunks
  numeric_series  60  "what was <measurement> for <x> on <date>" gold = the single chunk in that
                                                              document whose text holds the printed cell
  section_lookup  50  "what does <publisher>'s <doc> say about <heading>"  gold = that section's chunks

Every query is emitted with the filters the pipeline may use, and each gold hit carries its
source document path so the gate report can print real provenance. Seed = seed_for("P4a"), so a
rerun on the same KB reproduces the same questions. Reused/refreshed later by the full gold set.

Run: python kb/p4a_recall_set.py
"""
from __future__ import annotations

import calendar
import json
import random
import re
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2_known_values import find_token  # noqa: E402
from tripwire import seed_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
OUT = ROOT / "kb/reports/p4a_recall_set.json"
LOG = ROOT / "kb/logs/p4a_recall_set.log"

TARGETS = {"vessel_entity": 55, "company_entity": 35, "numeric_series": 60, "section_lookup": 50}
# Gold sets are uncapped on purpose: every chunk that answers the question is a valid answer.
# The earlier LIMIT 20 was an artificial false-negative source (vessel "Supra" appears in 288
# chunks, so returning a correct chunk outside the arbitrary first 20 counted as a miss).
UNIT_PARTS = re.compile(r"^(usd|usd/.*|eur|eur/.*|index|idx|pct|%|per.*|unit|units|days?)$", re.I)
DOC_KIND = {"broker_weekly": "weekly report", "broker_daily": "daily report",
            "broker_monthly": "monthly report", "book": "book"}
# report spellings for internal series-name tokens (queries must read like a real question)
MEAS_WORDS = {
    "iopi65": "IOPi65", "iopi58": "IOPi58", "iou62": "IOU62", "c3": "C3", "c5": "C5",
    "c7": "C7", "eq": "Eq", "cfr": "CFR", "fob": "FOB", "usd": "USD", "rmb": "RMB",
    "cny": "CNY", "dmt": "DMT", "wmt": "WMT", "pct": "percent", "wow": "week-on-week",
    "mom": "month-on-month", "qoq": "quarter-on-quarter", "m_minus_1": "month minus one",
    "m_plus_1": "month plus one", "vs": "vs", "tf": "total feeder", "index": "index",
    "premium": "premium", "discount": "discount", "differential": "differential",
}


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def humanise(name: str, definition: dict | None) -> str:
    """Turn an internal series name into words a person would ask with.

    Raw series names carry internal tokens (`iopi65_eq_usd_dmt`, `change_wow`, `m_minus_1`).
    Questions built from them verbatim ("what was the iopi65 eq usd dmt for 1-Oct-21 vector
    estimate") are not questions any analyst would ask and they embed badly, so this expands
    the token vocabulary into report spellings while keeping every discriminating token.
    """
    measurement = ""
    sig = ""
    if definition:
        measurement = str(definition.get("measurement") or "")
        sig = str(definition.get("entity_signature") or "")
    if not sig and "|" in name:
        sig = name.split("|", 1)[1]
    parts = [p.strip() for p in sig.split("\x1f") if p.strip()]
    keep = [p for p in parts if not UNIT_PARTS.match(p.replace("_", " "))]
    if not keep:
        keep = parts[:1]
    detail = " ".join(phrase(p) for p in keep[:3]).strip()
    meas = phrase(measurement)
    if meas:
        return f"{meas} for {detail}".strip() if detail else meas
    return detail or name.replace("_", " ")


def phrase(raw: str) -> str:
    """`change_wow` -> 'change week-on-week'; `iopi65_eq_usd_dmt` -> 'IOPi65 Eq USD DMT'."""
    if not raw:
        return ""
    if raw in MEAS_WORDS:
        return MEAS_WORDS[raw]
    words = []
    for tok in raw.split("_"):
        if not tok:
            continue
        words.append(MEAS_WORDS.get(tok, tok))
    return " ".join(words)


def month_window(day) -> tuple[str, str]:
    """First and last ISO date of the calendar month containing `day`."""
    last = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1).isoformat(), day.replace(day=last).isoformat()


def heading_tail(heading: str) -> str:
    """Last component of a ' > '-joined heading path."""
    parts = [h.strip() for h in re.split(r"[>\u203a/|]", heading or "") if h.strip()]
    return parts[-1] if parts else (heading or "").strip()


def doc_month(published) -> str:
    return published.strftime("%B %Y") if published else ""


def gold_of(con: duckdb.DuckDBPyConnection, chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    marks = ",".join("?" * len(chunk_ids))
    rows = con.execute(
        f"""SELECT c.chunk_id, c.doc_id, d.path, d.doc_type
            FROM chunk c JOIN document d USING (doc_id) WHERE c.chunk_id IN ({marks})""",
        chunk_ids).fetchall()
    return [{"chunk_id": r[0], "doc_id": r[1], "path": r[2], "doc_type": r[3]} for r in rows]


def vessel_entity(con, rng, seed):
    tagged = con.execute(
        """WITH t AS (SELECT unnest(entity_ids) AS eid FROM chunk)
           SELECT eid, count(*) AS c FROM t GROUP BY 1 HAVING count(*) BETWEEN 2 AND 400
           ORDER BY hash(eid || ?) LIMIT 600""", [seed]).fetchall()
    pool = [(e, c) for e, c in tagged if e.startswith("vessel:")]
    rng.shuffle(pool)
    out = []
    for eid, _ in pool:
        if len(out) >= TARGETS["vessel_entity"]:
            break
        name = con.execute("SELECT canonical_name FROM entity WHERE entity_id = ?", [eid]).fetchone()
        if not name:
            continue
        name = name[0]
        if len(name) < 5 or name.lower() in {"unknown", "unnamed"}:
            continue
        ids = [r[0] for r in con.execute(
            "SELECT chunk_id FROM chunk WHERE list_contains(entity_ids, ?) ORDER BY ord",
            [eid]).fetchall()]
        gold = gold_of(con, ids)
        if not gold:
            continue
        q = f"What did the market report say about the vessel {name}?"
        out.append({"stratum": "vessel_entity", "query": q, "entity_id": eid,
                    "filters": {}, "gold": gold})
    return out


def company_entity(con, rng, seed):
    tagged = con.execute(
        """WITH t AS (SELECT unnest(entity_ids) AS eid FROM chunk)
           SELECT eid, count(*) AS c FROM t GROUP BY 1 HAVING count(*) BETWEEN 2 AND 400
           ORDER BY hash(eid || ?) LIMIT 600""", [seed]).fetchall()
    pool = [(e, c) for e, c in tagged if e.startswith("company:")]
    rng.shuffle(pool)
    out = []
    for eid, _ in pool:
        if len(out) >= TARGETS["company_entity"]:
            break
        row = con.execute("SELECT canonical_name FROM entity WHERE entity_id = ?", [eid]).fetchone()
        if not row or len(row[0]) < 4:
            continue
        name = row[0]
        ids = [r[0] for r in con.execute(
            "SELECT chunk_id FROM chunk WHERE list_contains(entity_ids, ?) ORDER BY ord",
            [eid]).fetchall()]
        gold = gold_of(con, ids)
        if not gold:
            continue
        months = sorted({doc_month(con.execute("SELECT published_at FROM document WHERE doc_id = ?",
                                              [g["doc_id"]]).fetchone()[0]) for g in gold[:3]})
        when = f" in {months[0]}" if months and months[0] else ""
        q = f"What has {name} reported{when}?"
        out.append({"stratum": "company_entity", "query": q, "entity_id": eid,
                    "filters": {"entity_ids": [eid]}, "gold": gold})
    return out


def numeric_series(con, rng, seed):
    cands = con.execute(
        """SELECT o.obs_id, s.series_id, s.name, s.definition, o.value, o.raw_cell, o.doc_id,
                  o.period_from, d.published_at, d.publisher_id, d.doc_type
           FROM observation o JOIN series s USING (series_id) JOIN document d USING (doc_id)
           WHERE length(trim(o.raw_cell)) >= 3 AND o.value IS NOT NULL
             AND lower(trim(o.raw_cell)) NOT IN ('-','--','n/a','na','nan','none','null')
           ORDER BY hash(o.obs_id || ?) LIMIT 4000""", [seed]).fetchall()
    out, seen_docs = [], set()
    for (obs_id, sid, name, definition, value, raw_cell, doc_id, period, published,
         publisher, doc_type) in cands:
        if len(out) >= TARGETS["numeric_series"]:
            break
        if doc_id in seen_docs:
            continue
        try:
            definition = json.loads(definition) if isinstance(definition, str) else definition
        except json.JSONDecodeError:
            definition = None
        chunks = con.execute("SELECT chunk_id, body FROM chunk WHERE doc_id = ? ORDER BY ord",
                             [doc_id]).fetchall()
        hits = []
        for chunk_id, body in chunks:
            if body and find_token(body, raw_cell, value):
                hits.append(chunk_id)
        if len(hits) != 1:
            continue
        gold = gold_of(con, hits)
        if not gold:
            continue
        seen_docs.add(doc_id)
        when = f" on {published.strftime('%d %B %Y')}" if published else ""
        q = f"What was the {humanise(name, definition)}{when}?"
        filters = {}
        if published:
            filters["date_from"] = published.isoformat()
            filters["date_to"] = published.isoformat()
        out.append({"stratum": "numeric_series", "query": q, "entity_id": None,
                    "filters": filters, "gold": gold, "obs_id": int(obs_id)})
    return out


def section_gold(con, publisher, doc_type, published, tail: str,
                 limit: int | None = None) -> list[str]:
    """Every chunk that answers the question, not just the week it was sampled from.

    A section heading such as "Maritime Stock Data" repeats in every weekly report of the month,
    so a single-chunk label would mark a correct hit in a sibling week as a miss. The valid answer
    set is the heading's chunks in all documents the question's filters admit (same publisher,
    doc_type and month).
    """
    rows = con.execute(
        """SELECT s.section_id, array_to_string(s.heading_path, ' > ') AS heading,
                  d.published_at
           FROM section s JOIN document d USING (doc_id)
           WHERE s.kind = 'prose' AND d.publisher_id = ? AND d.doc_type = ?
             AND d.published_at IS NOT NULL
             AND date_trunc('month', d.published_at) = date_trunc('month', CAST(? AS DATE))
           ORDER BY d.published_at, s.section_id""",
        [publisher, doc_type, published]).fetchall()
    ids: list[str] = []
    for section_id, heading, _pub in rows:
        if heading_tail(heading).lower() != tail.lower():
            continue
        ids.extend(r[0] for r in con.execute(
            "SELECT chunk_id FROM chunk WHERE section_id = ? ORDER BY ord", [section_id]).fetchall())
        if limit is not None and len(ids) >= limit:
            break
    return ids if limit is None else ids[:limit]


def section_lookup(con, rng, seed):
    cands = con.execute(
        """SELECT s.section_id, array_to_string(s.heading_path, ' > ') AS heading, s.doc_id,
                  d.path, d.publisher_id, d.doc_type, d.published_at, d.title
           FROM section s JOIN document d USING (doc_id)
           WHERE length(array_to_string(s.heading_path, ' > ')) > 12 AND s.kind = 'prose'
             AND d.doc_type IN ('broker_weekly','broker_daily','broker_monthly','book')
           ORDER BY hash(s.section_id || ?) LIMIT 1500""", [seed]).fetchall()
    out, seen = [], set()
    for (section_id, heading, doc_id, path, publisher, doc_type, published, title) in cands:
        if len(out) >= TARGETS["section_lookup"]:
            break
        tail = heading_tail(heading)
        if len(tail) < 6 or doc_id in seen or not publisher or not published:
            continue
        seen.add(doc_id)
        ids = section_gold(con, publisher, doc_type, published, tail)
        gold = gold_of(con, ids)
        if not gold:
            continue
        kind = DOC_KIND.get(doc_type, "report")
        when = f" ({doc_month(published)})" if published else ""
        q = f"What does the {publisher} {kind}{when} say about {tail}?"
        start, end = month_window(published)
        filters = {"publisher": [publisher], "date_from": start, "date_to": end}
        out.append({"stratum": "section_lookup", "query": q, "entity_id": None,
                    "filters": filters, "gold": gold})
    return out


def main() -> int:
    seed = seed_for("P4a")
    rng = random.Random(seed)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    con = duckdb.connect(str(DB), read_only=True)
    con.execute("SET memory_limit='700MB'")
    con.execute("SET threads=2")
    try:
        queries = []
        for fn in (vessel_entity, company_entity, numeric_series, section_lookup):
            got = fn(con, rng, seed)
            log(f"{fn.__name__}: {len(got)}/{TARGETS[fn.__name__]}")
            if len(got) < TARGETS[fn.__name__]:
                log(f"WARNING short stratum {fn.__name__}: {len(got)}")
            queries.extend(got)
    finally:
        con.close()
    for i, q in enumerate(queries):
        q["qid"] = f"P4a-{i:03d}"
    counts: dict[str, int] = {}
    for q in queries:
        counts[q["stratum"]] = counts.get(q["stratum"], 0) + 1
    payload = {"phase": "P4a", "sample_seed": seed, "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "wall_seconds": round(time.time() - t0, 1), "counts": counts,
               "queries": queries}
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    log(f"wrote {OUT.relative_to(ROOT)}: {len(queries)} queries {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
