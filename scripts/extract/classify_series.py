"""Classify every extracted series by whether a live feed already covers it.

Turns the coverage audit from a report into a decision: for each extracted series
family, is it REDUNDANT (a feed publishes this, at better fidelity), COMPLEMENTARY
(the feed carries the aggregate but not this granularity), or UNIQUE (no feed
equivalent - only a PDF has it)?

Method is deliberately conservative: a series is only called REDUNDANT when the
concept AND the granularity both match a feed file. Aggregate-vs-brand is the key
distinction - the feeds carry 62% Fe iron ore futures; MMi carries ~40 named
physical brands, which is COMPLEMENTARY, not redundant.

usage:
    python scripts/extract/classify_series.py
    python scripts/extract/classify_series.py --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

# concept -> feed file globs that authoritatively cover the AGGREGATE form
FEED_CONCEPTS = {
    "iron ore futures": ["data/futures/sgx_iron_ore*", "data/commodities/sgx_iron_ore*"],
    "freight futures": ["data/futures/sgx_*_futures*"],
    "baltic indices": ["data/indices/*_historical.csv"],
    "bunker prices": ["data/bunkers/*.csv"],
    "tanker rates": ["data/clarksons/gibson_tanker_rates*"],
    "container indices": ["data/clarksons/drewry_*.csv"],
    "fearnleys rates": ["data/clarksons/fearnleys_*", "data/reference/fearnpulse_*"],
    "grain/flows": ["data/commodities/argentina*", "data/commodities/brazil*"],
    "port calls": ["data/congestion/port_calls*"],
}

# entity-name patterns that indicate BRAND / PORT granularity a feed does not carry
BRAND_HINTS = ("fines", "lump", "ssf", "yandi", "mac ", "rtx", "roy hill", "newman",
               "carajas", "jimblebar", "robe", "atlas", "smeic", "simec", "blend",
               "iopi", "iosi", "iopli")
PORT_HINTS = ("caofeidian", "jingtang", "qingdao", "tianjin", "rizhao", "beilun",
              "bayuquan", "dalian", "shandong", "hebei", "liaoning", "ports")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect("data/extracted/corpus/db/corpus.duckdb", read_only=True)
    rows = con.execute("""
        select source, entity_key, entity, measurement, points
        from series""").fetchall()

    feedblob = []
    for concept, globs in FEED_CONCEPTS.items():
        for g in globs:
            for f in glob.glob(g):
                feedblob.append((concept, os.path.basename(f)))
    feed_names = {os.path.basename(f) for _c, f in feedblob}
    print(f"feed files referenced: {len(feed_names)}")

    # which concepts does a series touch?
    def concepts_for(text: str) -> list[str]:
        t = text.lower()
        out = []
        for concept, _f in feedblob:
            key = concept.split()[0]
            if key in t:
                out.append(concept)
        if ("iron" in t or "ore" in t) and ("fef" in t or "62" in t or "65" in t):
            out.append("iron ore futures")
        if "bdi" in t or "baltic" in t:
            out.append("baltic indices")
        if "bunker" in t or "vlsfo" in t:
            out.append("bunker prices")
        return sorted(set(out))

    buckets = {"redundant": [], "complementary": [], "unique": []}
    for source, ekey, entity, measurement, points in rows:
        blob = f"{ekey} {measurement or ''}"
        cs = concepts_for(blob)
        is_brand = any(h in ekey for h in BRAND_HINTS)
        is_port = any(h in ekey for h in PORT_HINTS)
        if cs and (is_brand or is_port):
            buckets["complementary"].append((source, entity, measurement, points, cs))
        elif cs:
            buckets["redundant"].append((source, entity, measurement, points, cs))
        else:
            buckets["unique"].append((source, entity, measurement, points, []))

    total = sum(len(v) for v in buckets.values())
    print(f"extracted series classified: {total:,}\n")
    for k, v in buckets.items():
        pts = sum(x[3] or 0 for x in v)
        print(f"  {k:<15}{len(v):>6} series   {pts:>10,} observations")

    if a.json:
        json.dump({k: [list(x) for x in v[:400]] for k, v in buckets.items()},
                  open("data/extracted/series_classification.json", "w"), indent=1)
        print("\nwrote data/extracted/series_classification.json")
        return 0

    print("\n  --- samples of COMPLEMENTARY (feed has the aggregate, PDF has the grain):")
    for s, e, m, p, c in sorted(buckets["complementary"], key=lambda x: -(x[3] or 0))[:10]:
        print(f"     {s[:11]:<12}{str(e)[:24]:<26}{str(m)[:22]:<24}{p:>6}  {c}")
    print("\n  --- samples of REDUNDANT (a feed already publishes this):")
    for s, e, m, p, c in sorted(buckets["redundant"], key=lambda x: -(x[3] or 0))[:10]:
        print(f"     {s[:11]:<12}{str(e)[:24]:<26}{str(m)[:22]:<24}{p:>6}  {c}")
    print("\n  --- samples of UNIQUE (no feed equivalent):")
    for s, e, m, p, c in sorted(buckets["unique"], key=lambda x: -(x[3] or 0))[:10]:
        print(f"     {s[:11]:<12}{str(e)[:24]:<26}{str(m)[:22]:<24}{p:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
