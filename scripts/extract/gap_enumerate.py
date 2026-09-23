"""Enumerate every CSV under data/ (feed + auxiliary) and the corpus series inventory.

Step 1 of the gap matrix: what raw material actually exists on each side.
Feed = non-recursive top-level CSV in coverage_audit.FEED_DIRS (the 120 files the
repo already treats as "the live feeds"). Everything else under data/ is auxiliary
(raw holdings, derived products, caches, quarantine) and is NOT a feed.

Date handling: the date column is detected from the header sample (ISO, DD/MM/YYYY,
D-Mon-YYYY, M/D/YYYY, YYYYMMDD), then parsed for the whole file so the reported
date range and frequency are real rather than "no ISO date col".

usage: python scripts/extract/gap_enumerate.py
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import json
import os
import re
import statistics
import sys

FEED_DIRS = ["commodities", "futures", "ffa_live", "indices", "bunkers", "flows",
             "supply", "congestion", "demolition", "macro", "etf", "equities",
             "clarksons", "cargo", "geospatial", "reference"]
ISO = re.compile(r"^(19|20)\d\d-[01]\d-[0-3]\d")
DME = re.compile(r"^[0-3]?\d[-/]([01]?\d|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[-/](19|20)?\d\d$",
                 re.I)
MDY = re.compile(r"^[01]?\d/[0-3]?\d/(19|20)\d\d$")
YMD = re.compile(r"^(19|20)\d\d[01]\d[0-3]\d$")
MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}


def parse_date(s: str):
    """Never raises: a malformed cell must not truncate a file's row count."""
    try:
        return _parse_date(s)
    except Exception:  # noqa: BLE001
        return None


def _parse_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    if ISO.match(s):
        return dt.date.fromisoformat(s[:10])
    if YMD.match(s):
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    m = DME.match(s)
    if m:
        d, mo, y = s.split(s[1] if not s[1].isdigit() else ("-" if "-" in s else "/"))
        d = int(d)
        mo = MONTHS[mo.lower()] if not mo.isdigit() else int(mo)
        yy = int(y if len(y) == 4 else ("20" + y if int(y) < 70 else "19" + y))
        try:
            return dt.date(yy, mo, d)
        except ValueError:
            return None
    if MDY.match(s):
        a, b, y = s.split("/")
        try:
            return dt.date(int(y), int(a), int(b))
        except ValueError:
            return None
    return None


def sniff(path: str) -> dict:
    rows = 0
    header = ""
    dates: set[dt.date] = set()
    entity_sample: list[str] = []
    chosen_col = None
    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            rdr = csv.reader(f)
            buf = []
            for i, row in enumerate(rdr):
                if i == 0:
                    header = ",".join(row)[:200]
                    continue
                rows += 1
                if rows <= 200:
                    buf.append(row)
                if rows == 200 and chosen_col is None and buf:
                    best, best_hits = None, 0
                    ncol = max(len(r) for r in buf)
                    for c in range(ncol):
                        hits = sum(1 for r in buf if c < len(r) and parse_date(r[c]))
                        if hits > best_hits:
                            best, best_hits = c, hits
                    if best_hits >= 0.8 * len(buf):
                        chosen_col = best
                if row and len(entity_sample) < 3 and row[0].strip():
                    entity_sample.append(",".join(c.strip() for c in row[:3])[:90])
                if chosen_col is not None or rows <= 200:
                    try:
                        cand = row[chosen_col] if (chosen_col is not None and chosen_col < len(row)) else None
                        d = parse_date(cand) if cand else None
                        if d is None:
                            for cell in row[:6]:
                                d = parse_date(cell)
                                if d:
                                    break
                        if d:
                            dates.add(d)
                    except Exception:  # noqa: BLE001 - a bad cell must not truncate the file count
                        pass
    except Exception as e:  # noqa: BLE001
        header = f"<error {e}>"

    freq = "unknown"
    first = last = None
    if dates:
        ds = sorted(dates)
        first, last = str(ds[0]), str(ds[-1])
        if len(ds) > 2:
            gaps = [g for g in ((ds[i + 1] - ds[i]).days for i in range(len(ds) - 1)) if g > 0]
            if gaps:
                med = statistics.median(gaps)
                freq = ("daily" if med <= 1.5 else "weekly" if med <= 8 else
                        "monthly" if med <= 32 else "quarterly" if med <= 95 else
                        "annual" if med <= 370 else "multi-year")
    return {"rows": rows, "header": header, "first": first, "last": last,
            "freq": freq, "n_dates": len(dates), "sample": entity_sample,
            "date_col": chosen_col}


def main() -> int:
    all_csv = sorted(glob.glob("data/**/*.csv", recursive=True))
    feed_paths = set()
    for d in FEED_DIRS:
        feed_paths.update(glob.glob(os.path.join("data", d, "*.csv")))

    feeds, aux = [], []
    for p in all_csv:
        info = sniff(p)
        rec = {"path": p.replace("\\", "/"), **info,
               "is_feed": p in feed_paths,
               "dir": os.path.dirname(p).replace("\\", "/")}
        (feeds if p in feed_paths else aux).append(rec)

    print(f"CSV under data/ (recursive): {len(all_csv)}")
    print(f"  canonical feed CSVs       : {len(feeds)}  rows={sum(f['rows'] for f in feeds):,}")
    print(f"  auxiliary CSVs            : {len(aux)}  rows={sum(a['rows'] for a in aux):,}")
    print(f"  TOTAL rows                : {sum(f['rows'] for f in feeds) + sum(a['rows'] for a in aux):,}")
    nodate = [f["path"] for f in feeds if not f["first"]]
    print(f"  feeds without a parseable date column: {len(nodate)}")
    for p in nodate:
        print("     ", p)

    os.makedirs("scratch", exist_ok=True)
    json.dump({"feed_dirs": FEED_DIRS, "csv_total": len(all_csv),
               "feed_count": len(feeds), "feed_rows": sum(f["rows"] for f in feeds),
               "aux_count": len(aux), "aux_rows": sum(a["rows"] for a in aux),
               "feeds": feeds, "aux": aux},
              open("scratch/gap_feeds.json", "w", encoding="utf-8"), indent=1)
    print("wrote scratch/gap_feeds.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
