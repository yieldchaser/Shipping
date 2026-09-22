"""Coverage audit: what do the live feeds already give us, and what does PDF
extraction uniquely add?

Why this exists
---------------
Before extracting a series out of a PDF, check whether an authoritative feed
already publishes it. Measured on this repo: `data/futures/sgx_iron_ore_fef_history.csv`
alone holds 95,895 rows of every SGX 62% Fe contract with price, volume and open
interest, and `data/indices/` carries 22 Baltic index histories. Re-deriving
those from monthly PDF tables would be strictly worse - lower fidelity, poorer
coverage, more parsing risk.

So extraction should target what the feeds do NOT have:
  * brand/port-level granularity (the feeds carry 62/65/lump; MMi carries ~40
    physical brands plus Chinese port stocks)
  * historical backfill where a feed is shallow
  * narrative/qualitative content (broker commentary, textbooks)
  * sources with no feed at all

This script inventories the feeds (rows, date range) and the extracted series,
then reports the overlap so priorities can be set from data rather than instinct.
"""
from __future__ import annotations

import csv
import glob
import io
import os
import re
import sys

FEED_DIRS = ["commodities", "futures", "ffa_live", "indices", "bunkers", "flows",
             "supply", "congestion", "demolition", "macro", "etf", "equities",
             "clarksons", "cargo", "geospatial", "reference"]
DATE_RE = re.compile(r"\b(19|20)\d\d-[01]\d-[0-3]\d\b")


def sniff(path: str) -> dict:
    """Rows, header, and the date range found in the file (first/last ISO date)."""
    rows = 0
    header = ""
    first_date = last_date = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            rdr = csv.reader(f)
            for i, row in enumerate(rdr):
                if i == 0:
                    header = ",".join(row)[:110]
                    continue
                rows += 1
                if not row:
                    continue
                m = DATE_RE.search(row[0]) or DATE_RE.search(",".join(row[:3]))
                if m:
                    d = m.group(0)
                    if first_date is None:
                        first_date = d
                    last_date = d
    except Exception as e:
        header = f"<error {e}>"
    return {"rows": rows, "header": header, "first": first_date, "last": last_date}


def main() -> int:
    print("=" * 96)
    print("WHAT THE LIVE FEEDS ALREADY PROVIDE")
    print("=" * 96)
    total_files = total_rows = 0
    feed = []
    for d in FEED_DIRS:
        dd = os.path.join("data", d)
        if not os.path.isdir(dd):
            continue
        files = sorted(glob.glob(os.path.join(dd, "*.csv")))
        if not files:
            continue
        print(f"\n-- data/{d}  ({len(files)} csv)")
        for f in files:
            info = sniff(f)
            total_files += 1
            total_rows += info["rows"]
            rng = f"{info['first']}..{info['last']}" if info["first"] else "no ISO date col"
            print(f"   {os.path.basename(f)[:46]:<48}{info['rows']:>9,} rows  {rng}")
            feed.append({"dir": d, "file": os.path.basename(f), **info})

    print(f"\nfeed files: {total_files}   feed rows: {total_rows:,}")

    # what the extraction produced, for contrast
    try:
        import duckdb
        con = duckdb.connect("data/extracted/corpus/db/corpus.duckdb", read_only=True)
        n_series = con.execute("select count(*) from series").fetchone()[0]
        n_points = con.execute("select count(*) from series_points").fetchone()[0]
        by_src = con.execute(
            "select source, count(*) n, sum(points) p from series group by 1 order by 2 desc").fetchall()
        print("\n" + "=" * 96)
        print("WHAT PDF EXTRACTION ADDS")
        print("=" * 96)
        print(f"   series: {n_series:,}   observations: {n_points:,}")
        for s, n, p in by_src:
            print(f"     {s:<18}{n:>7} series  {int(p):>10,} observations")

        # keyword overlap between extracted entity names and feed file names
        ents = [r[0] for r in con.execute(
            "select distinct entity_key from series where length(entity_key)>3").fetchall()]
        feedblob = " ".join(f["file"].lower() for f in feed)
        OVERLAP = ["iron", "ore", "fef", "m65", "lump", "baltic", "bdi", "cape",
                   "panamax", "supramax", "handysize", "bunker", "container",
                   "wci", "drewry", "tanker", "vlcc", "lng", "orderbook", "fleet"]
        print("\n   extracted entities whose concept also exists as a feed file:")
        hits = sorted({o for o in OVERLAP if o in feedblob and any(o in e for e in ents)})
        print("     ", ", ".join(hits) if hits else "(none)")
    except Exception as e:
        print(f"\n(could not read the extracted DB: {str(e)[:120]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
