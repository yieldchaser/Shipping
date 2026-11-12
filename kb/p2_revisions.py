#!/usr/bin/env python3
"""GraphRAG phase P2 §4.5 — revision / restatement links.

A restated number is kept as its own `observation` row (PLAN §4.5): the row with the later
`published_at` gets `supersedes` pointing at the row it replaced, so "latest known" is
`ORDER BY published_at DESC` and "as known on D" is `published_at <= D`.

Chaining rule (deterministic, no LLM):
  * group observations by (series_id, period_from, period_to) — one reported period of one series;
  * walk the group in published_at order;
  * when a later row reports a *different* `value` than the previous row, it is a restatement:
    `supersedes = previous.obs_id`, and it becomes the new head of the chain;
  * a re-sighting of the identical value is not a restatement (it is a duplicate publication),
    it simply becomes the new head without a link.

Idempotent: clears then recomputes `supersedes` for every multi-row period group.
"""
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb" / "state" / "kb.duckdb"
REPORTS = ROOT / "kb" / "reports"
BATCH = 5000


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='300MB'")
    con.execute("SET checkpoint_threshold='16MB'")
    con.execute("SET threads=1")
    con.execute("SET enable_external_access=false")
    con.execute("UPDATE observation SET supersedes = NULL WHERE supersedes IS NOT NULL")

    cur = con.execute(
        "SELECT obs_id, series_id, period_from, period_to, value, published_at "
        "FROM observation ORDER BY series_id, period_from, period_to, published_at, obs_id")
    stats = Counter()
    pairs = []          # (supersedes_obs_id, obs_id)
    chain_len = Counter()
    key = None
    prev = None         # (obs_id, value, published_at)
    head_len = 0
    while True:
        rows = cur.fetchmany(BATCH)
        if not rows:
            break
        for obs_id, sid, pf, pt, value, pub in rows:
            k = (sid, pf, pt)
            if k != key:
                if head_len:
                    chain_len[head_len] += 1
                key = k
                prev = None
                head_len = 0
                stats["groups"] += 1
            else:
                stats["extra_rows"] += 1
            if prev is not None:
                if value != prev[1]:
                    pairs.append((prev[0], obs_id))
                    head_len += 1
                    stats["revisions"] += 1
                else:
                    stats["resightings"] += 1
            prev = (obs_id, value, pub)
    if head_len:
        chain_len[head_len] += 1

    for i in range(0, len(pairs), BATCH):
        con.executemany("UPDATE observation SET supersedes = ? WHERE obs_id = ?", pairs[i:i + BATCH])
        con.commit()

    # ---- verification (gate-honest, recomputed from the DB, not from the counters above) ----
    n_sup = con.execute("SELECT count(*) FROM observation WHERE supersedes IS NOT NULL").fetchone()[0]
    bad_missing = con.execute(
        "SELECT count(*) FROM observation o LEFT JOIN observation p ON p.obs_id = o.supersedes "
        "WHERE o.supersedes IS NOT NULL AND p.obs_id IS NULL").fetchone()[0]
    bad_order = con.execute(
        "SELECT count(*) FROM observation o JOIN observation p ON p.obs_id = o.supersedes "
        "WHERE o.published_at < p.published_at").fetchone()[0]
    bad_period = con.execute(
        "SELECT count(*) FROM observation o JOIN observation p ON p.obs_id = o.supersedes "
        "WHERE o.series_id <> p.series_id OR o.period_from <> p.period_from "
        "  OR o.period_to <> p.period_to").fetchone()[0]
    bad_same = con.execute(
        "SELECT count(*) FROM observation o JOIN observation p ON p.obs_id = o.supersedes "
        "WHERE o.value = p.value").fetchone()[0]
    n_obs = con.execute("SELECT count(*) FROM observation").fetchone()[0]
    con.close()

    result = {
        "phase": "P2_revisions",
        "rows_scanned": n_obs,
        "period_groups": stats["groups"],
        "extra_rows_in_groups": stats["extra_rows"],
        "revisions": stats["revisions"],
        "resightings_same_value": stats["resightings"],
        "supersedes_rows": n_sup,
        "supersedes_missing_target": bad_missing,
        "supersedes_wrong_order": bad_order,
        "supersedes_wrong_period": bad_period,
        "supersedes_same_value": bad_same,
        "chain_len_histogram": {str(k): v for k, v in sorted(chain_len.items())},
        "as_known_on_supported": True,
        "duration_s": round((datetime.now() - started).total_seconds(), 1),
    }
    result["passed"] = (bad_missing == 0 and bad_order == 0 and bad_period == 0 and bad_same == 0)
    import json
    (REPORTS / "p2_revisions.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"p2_revisions: revisions={result['revisions']:,} supersedes={n_sup:,} "
          f"groups={result['period_groups']:,} resightings={result['resightings_same_value']:,} "
          f"bad(missing/order/period/same)={bad_missing}/{bad_order}/{bad_period}/{bad_same} "
          f"-> {'PASS' if result['passed'] else 'FAIL'}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
