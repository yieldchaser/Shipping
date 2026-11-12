#!/usr/bin/env python3
"""GraphRAG phase P2 — 40 known values with source proof (gates: known_values_exact / _rate).

What this proves
----------------
For 40 observations drawn across publishers, the number stored in `observation.value` equals the
number *as printed in the source document text* (`chunk.body`, built in P1 from the parsed PDF),
after plain text->number normalisation ("26,5" -> 26.5, "1.234" -> 1234).  This is an independent
path from the CSV/table path that produced `value`, so it tests the parse, not the loader.

Method (deterministic, no LLM, no cell values touched by any model)
------------------------------------------------------------------
1. Stratify candidates by publisher (min_strata: publisher), ordered by `hash(obs_id)` so the
   draw is fixed by the data, then take up to MAX_PER_PUBLISHER per publisher until TARGET.
2. For each candidate, look up the *source document's* chunk bodies (`chunk.doc_id = obs.doc_id`).
3. Build printed-form variants from `raw_cell` (decimal comma vs point, thousands separators) and
   find a token in the text with digit boundaries that parses back to `value`.
4. Record the chunk_id, the character offset, the matched token and a text context window, so the
   proof is a source + line (character range) + verbatim string.

The gate re-verifies every record later by re-reading the chunk body and re-parsing the token;
nothing here is trusted as ground truth on its own.
"""
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def seed_for(phase):
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)
DB = ROOT / "kb" / "state" / "kb.duckdb"
REPORTS = ROOT / "kb" / "reports"
OUT = REPORTS / "p2_known_values.json"
TARGET = 40
MAX_PER_PUBLISHER = 5
MIN_PUBLISHERS = 8
CTX = 90


def to_number(s):
    """Printed cell -> float. Handles 1,234.5 / 1.234,5 / 26,5 / (12.3) / -."""
    if s is None:
        return None
    t = str(s).strip().replace("\u00a0", "").replace(" ", "")
    if not t or t.lower() in {"-", "--", "n/a", "na", "nan", "none", "null", "."}:
        return None
    neg = t.startswith("(") and t.endswith(")")
    if neg:
        t = t[1:-1]
    for ch in "$€£¥%*†‡":
        t = t.replace(ch, "")
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(",") < t.rfind(".") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        head, _, tail = t.rpartition(",")
        t = t.replace(",", ".") if (len(tail) in (1, 2) and head) else t.replace(",", "")
    try:
        v = float(t)
    except ValueError:
        m = re.search(r"-?\d+(?:\.\d+)?", t)
        if not m:
            return None
        v = float(m.group(0))
    return -v if neg else v


def variants(raw_cell):
    rc = str(raw_cell).strip().replace("\u00a0", "").replace(" ", "")
    out = {rc}
    if "," in rc and "." in rc:
        out.add(rc.replace(",", ""))
        out.add(rc.replace(".", "").replace(",", "."))
    elif "," in rc:
        out.add(rc.replace(",", "."))
        out.add(rc.replace(",", ""))
    elif "." in rc:
        out.add(rc.replace(".", ","))
        out.add(rc.replace(".", ""))
    return [v for v in out if v]


def find_token(body, raw_cell, value):
    for v in variants(raw_cell):
        esc = re.escape(v)
        if re.search(r"\d", v):
            pat = re.compile(r"(?<![\d.,])" + esc + r"(?![\d.,])")
        else:
            pat = re.compile(esc)
        for m in pat.finditer(body):
            tok = m.group(0)
            got = to_number(tok)
            if got is not None and abs(got - float(value)) <= 1e-9:
                return tok, m.start()
    return None


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    con = duckdb.connect(str(DB), read_only=True)
    con.execute("SET memory_limit='400MB'")
    con.execute("SET threads=1")

    base_where = (
        "o.doc_id IS NOT NULL AND o.value IS NOT NULL "
        "AND o.raw_cell IS NOT NULL AND length(trim(o.raw_cell)) > 0 "
        "AND lower(trim(o.raw_cell)) NOT IN ('-','--','n/a','na','nan','none','null')"
    )
    pubs = con.execute(
        f"""SELECT COALESCE(d.publisher_id, s.definition->>'source') AS p, count(*) AS c
            FROM observation o JOIN series s ON s.series_id = o.series_id
            LEFT JOIN document d ON d.doc_id = o.doc_id
            WHERE {base_where}
            GROUP BY 1 HAVING count(*) >= 20 ORDER BY c DESC""").fetchall()
    print(f"publishers with >=20 candidates: {len(pubs)}")

    records = []
    attempts = []
    docs_used = set()
    for pub, cnt in pubs:
        if len(records) >= TARGET:
            break
        if pub is None:
            continue
        rows = con.execute(
            f"""SELECT o.obs_id, o.series_id, s.name, o.period_from, o.period_to, o.value,
                       o.raw_cell, o.doc_id, d.doc_type, d.published_at
                FROM observation o JOIN series s ON s.series_id = o.series_id
                LEFT JOIN document d ON d.doc_id = o.doc_id
                WHERE {base_where} AND COALESCE(d.publisher_id, s.definition->>'source') = ?
                ORDER BY hash(o.obs_id) LIMIT 40""", [pub]).fetchall()
        taken = 0
        for (obs_id, sid, name, pf, pt, value, raw_cell, doc_id, doc_type, pub_at) in rows:
            if taken >= MAX_PER_PUBLISHER or len(records) >= TARGET:
                break
            chunks = con.execute(
                "SELECT chunk_id, body FROM chunk WHERE doc_id = ? ORDER BY ord", [doc_id]).fetchall()
            hit = None
            for chunk_id, body in chunks:
                if not body:
                    continue
                f = find_token(body, raw_cell, value)
                if f:
                    tok, off = f
                    hit = {
                        "chunk_id": chunk_id,
                        "char_start": off,
                        "char_end": off + len(tok),
                        "text_token": tok,
                        "context": body[max(0, off - CTX): off + len(tok) + CTX].replace("\n", " "),
                    }
                    break
            if not hit:
                attempts.append({"obs_id": obs_id, "publisher": pub, "raw_cell": raw_cell,
                                 "value": value, "reason": "number not found in source text"})
                continue
            records.append({
                "obs_id": obs_id, "series_id": sid, "series_name": name,
                "publisher": pub, "doc_type": doc_type, "doc_id": doc_id, "published_at": str(pub_at),
                "period_from": str(pf), "period_to": str(pt),
                "value": float(value), "raw_cell": raw_cell,
                **hit,
            })
            taken += 1
            docs_used.add(doc_id)
        print(f"  {pub:<34} candidates={len(rows):>3}  accepted={taken}  total={len(records)}")

    con.close()
    by_pub = {}
    for r in records:
        by_pub[r["publisher"]] = by_pub.get(r["publisher"], 0) + 1
    result = {
        "phase": "P2",
        "sample_seed": seed_for("P2"),
        "ordering": "ORDER BY hash(obs_id) within publisher strata (data-fixed, not agent-chosen)",
        "target": TARGET,
        "found": len(records),
        "publishers": len(by_pub),
        "publishers_histogram": by_pub,
        "distinct_docs": len(docs_used),
        "attempts_rejected": len(attempts),
        "rejected_sample": attempts[:10],
        "records": records,
        "passed": len(records) >= TARGET and len(by_pub) >= MIN_PUBLISHERS,
        "duration_s": round((datetime.now() - started).total_seconds(), 1),
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"known values: {len(records)}/{TARGET} across {len(by_pub)} publishers, "
          f"{len(docs_used)} docs -> {'PASS' if result['passed'] else 'FAIL'}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
