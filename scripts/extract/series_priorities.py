"""Which recurring report tables are worth turning into time series?

Three filters, applied in order, because failing any one makes the work pointless:

  1. IS IT STILL PUBLISHING?  A broker report that ended years ago cannot extend a
     series forward. Continuity is measured from the documents themselves: date
     span, documents per year, the largest gap, and recency.
  2. DOES IT CARRY A RECURRING TABLE?  A table whose row-label set repeats across
     many documents is a series generator. One-off tables are content, not series.
  3. DO WE ALREADY HAVE THE DATA?  If a live feed publishes the same quantity, a
     PDF-derived version is a worse copy and the work is wasted. This is the
     filter that stops effort being spent re-deriving SGX iron ore prices we
     already hold as 95,895 rows by contract.

Books are excluded by design: they carry business logic and fundamentals, not
repeatable observations, so they belong to the knowledge layer rather than the
series layer.

Output is a ranked worklist: source, recurring table, continuity, feed status,
priority.

usage:
    python scripts/extract/series_priorities.py
    python scripts/extract/series_priorities.py --json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

# concepts a live feed already publishes (see coverage_audit.py for the evidence)
FEED_CONCEPTS = {
    "sgx iron ore futures": ("iopi", "iosi", "iron ore", "fef", "62%", "65%", "m65"),
    # Baltic publishes the index AND its route sub-indices; data/indices holds 22
    # histories. An earlier pass missed these and wrongly ranked BCI TC average and
    # the C10/C14 routes as CONSTRUCT, when we already have them.
    "baltic indices": ("bdi", "bci", "bpi", "bsi", "bhsi", "baltic",
                       "tc average", "c10 ", "c14 ", "c5 ", "c3 ", "c7 ",
                       "pacific r/v", "china-brazil", "china - brazil"),
    "baltic tanker indices": ("bcti", "bdti"),
    "bunker prices": ("bunker", "vlsfo", "mgo", "ifo"),
    "container indices": ("wci", "drewry", "container index", "teu"),
    "fearnleys benchmark": ("fearnleys", "benchmark"),
    "tanker rates (gibson)": ("gibson", "tanker rate"),
}
# table shapes that are genuinely proprietary - a feed does NOT publish these
PROPRIETARY_HINTS = ("fines", "lump", "ssf", "yandi", "caofeidian", "jingtang",
                     "qingdao", "rizhao", "tianjin", "beilun", "bayuquan",
                     "dalian", "brand", "colour coated", "crc ", "gi st")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect("data/extracted/corpus/db/corpus.duckdb", read_only=True)

    # ---- 1. continuity per source, from doc date coverage
    rows = con.execute("""
        select source, doc_stem, count(*) n
        from cells group by 1,2""").fetchall()

    ISO = re.compile(r"(19|20)\d\d-[01]\d-[0-3]\d")
    week = re.compile(r"((?:19|20)\d\d)[_-]?[Ww](\d{1,2})(?![0-9])")
    per_source: dict[str, list[dt.date]] = {}
    for src, stem, _n in rows:
        d = None
        m = ISO.search(stem or "")
        if m:
            try:
                d = dt.date.fromisoformat(m.group(0))
            except ValueError:
                d = None
        if d is None:
            m = week.search(stem or "")
            if m and 1 <= int(m.group(2)) <= 53:
                try:
                    d = dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
                except ValueError:
                    d = None
        if d:
            per_source.setdefault(src, []).append(d)

    today = dt.date.today()
    cont = []
    for src, ds in per_source.items():
        ds.sort()
        gaps = [(ds[i + 1] - ds[i]).days for i in range(len(ds) - 1)]
        cont.append({
            "source": src, "docs_dated": len(ds),
            "first": str(ds[0]), "last": str(ds[-1]),
            "span_days": (ds[-1] - ds[0]).days,
            "max_gap_days": max(gaps) if gaps else 0,
            "days_since_last": (today - ds[-1]).days,
            "active": (today - ds[-1]).days <= 45,
        })
    cont.sort(key=lambda x: (not x["active"], -x["docs_dated"]))

    print("=" * 100)
    print("1. CONTINUITY - is the publication still running?")
    print("=" * 100)
    print(f"{'source':<22}{'docs':>7}{'first':>12}{'last':>12}{'span_d':>8}"
          f"{'gap_d':>7}{'since':>7}  status")
    for c in cont[:26]:
        print(f"{c['source'][:20]:<22}{c['docs_dated']:>7}{c['first']:>12}{c['last']:>12}"
              f"{c['span_days']:>8}{c['max_gap_days']:>7}{c['days_since_last']:>7}"
              f"  {'ACTIVE' if c['active'] else 'ended'}")

    # ---- 2. recurring table shapes
    shapes = con.execute("""
        with lbl as (
            select doc, page, table_idx,
                   string_agg(distinct lower(trim(label)), '|' order by lower(trim(label))) labels
            from label_series group by 1,2,3
        )
        select min(labels) as label_sample, count(distinct doc) as ndocs
        from lbl group by md5(labels)
        having count(distinct doc) >= 15
        order by ndocs desc limit 60""").fetchall()

    # ---- 3. feed filter + priority
    worklist = []
    for sample, docs in shapes:
        s = (sample or "").lower()
        proprietary = any(h in s for h in PROPRIETARY_HINTS)
        feed_hit = None
        for concept, keys in FEED_CONCEPTS.items():
            if any(k in s for k in keys):
                feed_hit = concept
                break
        # ORDER MATTERS: feed coverage is checked FIRST. A table can mention a
        # brand AND a Baltic route (broker reports mix them), and if the feed
        # already publishes the quantity then building it from PDFs is wasted work
        # regardless of what else the table contains. An earlier version tested
        # proprietary first and wrongly ranked "bci tc average | c10 pacific r/v"
        # as CONSTRUCT when data/indices already holds those route histories.
        if feed_hit:
            verdict = f"SKIP - feed already publishes ({feed_hit})"
            prio = 3
        elif proprietary:
            verdict = "CONSTRUCT - proprietary, no feed equivalent"
            prio = 1
        else:
            verdict = "REVIEW - not in a feed, but not clearly proprietary"
            prio = 2
        worklist.append({"labels": sample[:90], "docs": docs, "priority": prio,
                         "verdict": verdict})

    worklist.sort(key=lambda x: (x["priority"], -x["docs"]))
    print("\n" + "=" * 100)
    print("2/3. RECURRING TABLES x FEED COVERAGE -> WHAT IS WORTH BUILDING")
    print("=" * 100)
    for w in worklist[:30]:
        print(f"  p{w['priority']} {w['docs']:>5} docs  {w['labels'][:52]:<54} {w['verdict'][:38]}")

    from collections import Counter
    print("\n  summary:", dict(Counter(w["verdict"].split(" - ")[0] for w in worklist)))

    if a.json:
        json.dump({"continuity": cont, "worklist": worklist},
                  open("data/extracted/series_priorities.json", "w", encoding="utf-8"),
                  indent=1)
        print("\nwrote data/extracted/series_priorities.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
