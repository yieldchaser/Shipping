"""Corpus audit: what we captured, what it is worth, and what to tag it with.

Answers four questions in one pass, from the corpus rather than from intent:

  1. BREADTH   - documents, pages, tables, cells, series per source
  2. TABLE SERIES - recurring table SHAPES (a table whose label-set repeats across
                    many documents is a series generator; a one-off table is not)
  3. VALUE     - rank series by whether a live feed already covers them. A
                    proprietary index that exists only in these PDFs is worth
                    more than a restatement of a feed value, because the feed
                    version is authoritative and free.
  4. TAGS      - emit a per-series manifest carrying source, entity, measurement,
                    unit-guess, coverage, and value class, so the downstream
                    processing phase has clean inputs.

Table-shape fingerprinting is the useful trick: hash the sorted set of row labels
in each table. Tables that share a fingerprint across documents are the same
publication table recurring weekly, which is what makes a time series possible at
all.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

UNIT_HINTS = [
    (re.compile(r"\bUSD/?\s*(?:dry\s*)?(?:tonne|ton|t|dmt)\b", re.I), "USD/t"),
    (re.compile(r"\bRMB/?\s*(?:tonne|ton|t|mt)\b", re.I), "RMB/t"),
    (re.compile(r"\bUSD/?\s*(?:teu|feu)\b", re.I), "USD/TEU"),
    (re.compile(r"\bUSD/?\s*(?:day|d)\b", re.I), "USD/day"),
    (re.compile(r"\b(?:ws|worldscale)\b", re.I), "Worldscale"),
    (re.compile(r"\bUSD/?\s*(?:bbl|barrel)\b", re.I), "USD/bbl"),
    (re.compile(r"\b(?:pct|percent|%)\b", re.I), "%"),
    (re.compile(r"\b(?:000|'000|k|thousand)\s*(?:mt|t|tonnes?|bbl|teu)\b", re.I), "k units"),
    (re.compile(r"\b(?:dwt|tdwt|deadweight)\b", re.I), "DWT"),
    (re.compile(r"\b(?:cbm|m3|m³)\b", re.I), "cbm"),
]


def guess_unit(text: str) -> str | None:
    for rx, u in UNIT_HINTS:
        if rx.search(text or ""):
            return u
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/extracted/corpus/db/corpus.duckdb")
    ap.add_argument("--out", default="data/extracted/corpus_audit.json")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect(a.db, read_only=True)

    report: dict = {}

    # ---------- 1. breadth
    print("=" * 90)
    print("1. BREADTH - what we hold")
    print("=" * 90)
    breadth = con.execute("""
        select c.source,
               count(distinct c.doc) docs,
               count(distinct (c.doc||'|'||c.page)) pages,
               count(distinct (c.doc||'|'||c.page||'|'||c.table_idx||'|'||c.engine)) grids,
               count(*) cells
        from cells c group by 1 order by 5 desc""").fetchall()
    print(f"{'source':<18}{'docs':>7}{'pages':>8}{'grids':>8}{'cells':>13}")
    for s, d, p, g, cl in breadth:
        print(f"{s[:16]:<18}{d:>7,}{p:>8,}{g:>8,}{cl:>13,}")
    report["breadth"] = [
        {"source": s, "docs": d, "pages": p, "grids": g, "cells": cl}
        for s, d, p, g, cl in breadth]

    # ---------- 2. table series (recurring table SHAPES)
    print("\n" + "=" * 90)
    print("2. TABLE SERIES - table shapes that recur across documents")
    print("=" * 90)
    shapes = con.execute("""
        -- label_series joins on engine but does not expose it, so the shape
        -- fingerprint is per (doc, page, table_idx) rather than per engine.
        with lbl as (
            select doc, page, table_idx,
                   string_agg(distinct lower(trim(label)), '|' order by lower(trim(label))) as labels
            from label_series group by 1,2,3
        )
        select md5(labels) as fp, min(labels) as sample, count(*) n,
               count(distinct doc) docs
        from lbl group by 1
        having count(distinct doc) >= 20
        order by docs desc, n desc
        limit ?""", [a.top]).fetchall()
    print(f"{'docs':>6}{'instances':>11}  label-set (first 70 chars)")
    for fp, sample, n, docs in shapes:
        print(f"{docs:>6,}{n:>11,}  {str(sample)[:70]}")
    report["table_shapes"] = [
        {"fingerprint": fp, "sample_labels": sample, "instances": n, "docs": docs}
        for fp, sample, n, docs in shapes]

    # ---------- 3 & 4. series value class + tags
    print("\n" + "=" * 90)
    print("3/4. SERIES TAGS - value class, unit guess, coverage")
    print("=" * 90)
    srows = con.execute("""
        select series_id, source, entity, measurement, points, first_date, last_date
        from series order by points desc""").fetchall()

    # a feed file whose name shares a concept means the aggregate is already free
    feed = []
    for d in ("futures", "indices", "commodities", "bunkers", "clarksons", "reference"):
        dd = os.path.join("data", d)
        if os.path.isdir(dd):
            feed += [f.lower() for f in os.listdir(dd)]
    feedblob = " ".join(feed)

    tags = []
    for sid, src, ent, meas, pts, f0, f1 in srows:
        blob = f"{ent} {meas}".lower()
        unit = guess_unit(meas)
        # proprietary = a named brand/port/route, which a feed does not publish
        proprietary = bool(re.search(
            r"fines|lump|ssf|\bbrand\b|caofeidian|jingtang|qingdao|tianjin|rizhao|beilun|bayuquan",
            blob))
        # NOTE: must test the SERIES text against the feed concepts. An earlier
        # version tested `k in feedblob`, which is constant-true whenever the feed
        # contains that keyword at all, so every series was mislabelled
        # "feed-covered" (4,653 of them).
        feed_covered = any(k in blob for k in
                           ("iron ore", "bdi", "baltic", "bunker", "fef",
                            "m65", "capesize", "panamax", "supramax")) or \
                       any(k in feedblob for k in ("iron_ore",)) and \
                       any(k in blob for k in ("iopi", "iosi"))
        if proprietary:
            vclass = "proprietary-brand-or-port"
        elif feed_covered:
            vclass = "feed-covered (cross-check only)"
        else:
            vclass = "source-unique"
        tags.append({"series_id": sid, "source": src, "entity": ent,
                     "measurement": meas, "unit_guess": unit or "unknown",
                     "points": pts, "first_date": str(f0), "last_date": str(f1),
                     "value_class": vclass})

    from collections import Counter
    c = Counter(t["value_class"] for t in tags)
    for k, v in c.most_common():
        pts = sum(t["points"] for t in tags if t["value_class"] == k)
        print(f"   {k:<32}{v:>6} series  {pts:>10,} observations")
    c2 = Counter(t["unit_guess"] for t in tags)
    print("\n   unit coverage:")
    for k, v in c2.most_common():
        print(f"     {k:<20}{v:>6}")

    report["series_tags"] = tags
    json.dump(report, open(a.out, "w", encoding="utf-8"), indent=1)
    print(f"\nwrote {a.out}  ({len(tags):,} series tags)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
