#!/usr/bin/env python3
"""GraphRAG phase P2 §4.6 — seed corpus_known_gaps from the cadence audit + open-items ledger.

Gaps are asserted, not inferred from the KB here: they come from docs/PRE_GRAPHRAG_OPEN_ITEMS.md
and corpus/CORPUS_REGISTRY_AND_CADENCE_AUDIT.md, plus the per-source cadence table below. The
rule (`missing period > 1.5x median cadence`) is applied by the deterministic seeder where the
ledger states a concrete stop date; Seabrokers cadence is set from the registry (monthly, issue
dated 1st of the month, published start of next month), never inferred.

`scope` in {series, publisher, source}. `key` names the series stem or publisher/source id.
`gap_from` is the first missing period; `gap_to` is NULL (ongoing) unless a resume is known.
Idempotent: DELETEs the seeded rows it owns (source in SEED_SOURCES) and re-inserts.

No LLM. Does not read the corpus DB. Reads only the two docs (never the corpus data dirs).
Usage: python kb/p2_gaps.py
"""
import json
import sys
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb" / "state" / "kb.duckdb"
REPORTS = ROOT / "kb" / "reports"
SRC_OPEN_ITEMS = "PRE_GRAPHRAG_OPEN_ITEMS"
SRC_CADENCE = "CORPUS_REGISTRY_AND_CADENCE_AUDIT"

# (scope, key, gap_from, gap_to, reason, source)  — ledger-derived, deterministic.
SEEDS = [
    # --- per-country partner shares (open items L211-219, still [ ]) ---
    ("series", "china_partner_usd_share_iron_ore", "2026-09-01", None,
     "GACC bulletin has no country split; chinadata.live API retired; stats.customs.gov.cn JS challenge; Comtrade CN stops 2024-12",
     SRC_OPEN_ITEMS),
    ("series", "china_partner_usd_share_coal", "2026-09-01", None,
     "GACC bulletin has no country split; chinadata.live API retired; stats.customs.gov.cn JS challenge; Comtrade CN stops 2024-12",
     SRC_OPEN_ITEMS),
    ("series", "china_partner_usd_share_crude", "2026-09-01", None,
     "GACC bulletin has no country split; chinadata.live API retired; stats.customs.gov.cn JS challenge; Comtrade CN stops 2024-12",
     SRC_OPEN_ITEMS),
    ("series", "china_partner_usd_share_lng", "2026-09-01", None,
     "GACC bulletin has no country split; chinadata.live API retired; stats.customs.gov.cn JS challenge; Comtrade CN stops 2024-12",
     SRC_OPEN_ITEMS),
    ("series", "china_partner_usd_share_soybeans", "2026-09-01", None,
     "GACC bulletin has no country split; chinadata.live API retired; stats.customs.gov.cn JS challenge; Comtrade CN stops 2024-12",
     SRC_OPEN_ITEMS),
    ("series", "china_partner_usd_share_fertilizers", "2026-09-01", None,
     "GACC bulletin has no country split; chinadata.live API retired; stats.customs.gov.cn JS challenge; Comtrade CN stops 2024-12",
     SRC_OPEN_ITEMS),
    # --- SEC tables still stacked / text-only (open items L235-262, still [ ]) ---
    ("publisher", "sec_text_only_exhibits", "2026-01-01", None,
     "9 PDF-origin exhibits are one text line (RIO 20-F 2022/2023, VALE 6-K); 2 real stacked blocks left (VALE 20-F 2023, VALE 6-K 2026-07-31) — searchable/quotable, not facts",
     SRC_OPEN_ITEMS),
    ("publisher", "sec_stacked_cells_converter", "2026-01-01", None,
     "127 filings kept as stored (108 not better, 15 words lost, 4 numbers lost in reconvert) — statement facts may be missing",
     SRC_OPEN_ITEMS),
    # --- publisher cadence gaps (registry status lines; DUE > 1.5x weekly cadence) ---
    # Seabrokers: monthly, issue dated 1st; cadence set from registry (never inferred).
    # Latest issue 2026-10-01 stored and CURRENT (9d) as of 2026-11-10 -> no gap, nothing seeded.
    ("publisher", "gibson_shipbrokers", "2026-10-30", None,
     "Latest 2026-10-30, DUE (11d vs weekly) at audit 2026-11-10",
     SRC_CADENCE),
    ("publisher", "poten_tanker_opinions", "2026-10-30", None,
     "Latest 2026-10-30, DUE (11d vs weekly) at audit 2026-11-10",
     SRC_CADENCE),
    ("publisher", "drewry_ais", "2026-10-27", None,
     "Latest Week 43 2026-10-27, DUE (14d vs weekly Tuesday) at audit 2026-11-10",
     SRC_CADENCE),
    # --- SSY chart series gap (open items L174-175) ---
    ("series", "ssy_capesize_index_pacific", "2026-10-02", "2026-10-02",
     "Pacific 2026-10-02 not published on HSN (404, no post)",
     SRC_OPEN_ITEMS),
]

SEED_SOURCES = {SRC_OPEN_ITEMS, SRC_CADENCE}


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='128MB'")
    con.execute("SET checkpoint_threshold='16MB'")
    con.execute("SET threads=1")
    con.execute("SET enable_external_access=false")
    con.execute(
        "CREATE TABLE IF NOT EXISTS corpus_known_gaps "
        "(scope VARCHAR, key VARCHAR, gap_from DATE, gap_to DATE, reason VARCHAR, source VARCHAR)")
    # idempotent: drop only rows this seeder owns, then re-insert
    con.execute("DELETE FROM corpus_known_gaps WHERE source IN (?, ?)",
                [SRC_OPEN_ITEMS, SRC_CADENCE])
    rows = [(s, k, date.fromisoformat(gf) if gf else None,
             date.fromisoformat(gt) if gt else None, r, src)
            for (s, k, gf, gt, r, src) in SEEDS]
    con.executemany(
        "INSERT INTO corpus_known_gaps (scope, key, gap_from, gap_to, reason, source) "
        "VALUES (?,?,?,?,?,?)", rows)
    n = con.execute("SELECT count(*) FROM corpus_known_gaps").fetchone()[0]
    con.commit()
    con.close()
    report = {"phase": "P2_gaps", "seeded": len(rows), "total_known_gaps": n,
      }
    (REPORTS / "p2_gaps.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"p2_gaps: seeded={len(rows)} total_known_gaps={n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
