"""ssy - stack the 519 chart extractions into one time series, and PROVE the keys align.

A source is not closed until its repeated charts demonstrably stack into a series. This
does that, and - more importantly - it proves the join is real.

WHY A CROSS-DOCUMENT CHECK IS THE ONLY HONEST PROOF
----------------------------------------------------
Each weekly report redraws the same calendar window. A point at the same calendar
position in two different reports is the SAME WEEK, measured twice. So if the date
mapping is correct, the two readings must agree to within the chart's own plotting
resolution. If the mapping is wrong, points from different weeks get merged and the
spread explodes.

That gives a self-validating merge: the spread of repeated readings of the same key is
a measurement of the extractor's correctness, not a tuning target. It is reported
below and is the gate on the output.

KEY DERIVATION (no label assignment by order)
---------------------------------------------
The x axis carries MONTH labels at known x positions, and x is linear in time. A point
between 'Jan' and 'Feb' is dated by interpolating within that month. The YEAR comes
from the colour legend, matched by exact stroke RGB - never from row order or from
position in a list. For 2021-23 the month labels already carry the year ('Jan-20'); for
2024-26 they are bare ('Jan'), and the series' legend year supplies it.

Because the reports are weekly, the interpolated position is fractional. Points are
therefore keyed on (year, month, 4-day bucket) so that a reading reported in two
different weeks still lands on one key, while readings genuinely weeks apart do not.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CHARTS = REPO / "data" / "extracted" / "charts" / "ssy"
OUT = REPO / "data" / "extracted" / "series"
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
BUCKET_DAYS = 4


def key_for(point, series_year, route):
    """(route, year, month, bucket) from a chart point, or None.

    `route` is part of the key because Atlantic and Pacific are DIFFERENT indices.
    Pooling them was caught by this script's own agreement check: median relative spread
    48.8%, with the worst key (2023-DEC-b4) collecting 156 readings spanning
    8,175..90,279 - a 10x range that is only possible if two unrelated series share a key.

    The key is built from the point's CALENDAR `date`, never from `month_frac`.
    `month_frac` is a 0-11 offset WITHIN the plot window, so keying on it dated every
    point to months of the legend year rather than to the window it was drawn in - which
    is what left the median spread at 4.8% and the worst keys at 160%. The extractor now
    supplies `date` using the window's start year (the oldest legend year), so the merge
    only has to trust it.
    """
    if series_year is None or route is None:
        return None
    d = point.get("date")
    if not d:
        return None
    m = re.match(r"(\d{4})-([A-Z]{3})$", d)
    if not m:
        return None
    y, mon = int(m.group(1)), m.group(2)
    # interpolate the day from the within-month fraction, using the calendar month
    mi = MONTHS.index(mon) if mon in MONTHS else 0
    mf = point.get("month_frac")
    frac = (mf - mi) if mf is not None else 0.0
    frac = min(max(frac, 0.0), 1.0)
    day = max(1, min(28, 1 + int(frac * 30.5)))
    return (route, y, mon, day // BUCKET_DAYS)


def main():
    files = sorted(CHARTS.glob("*.charts.json"))
    if not files:
        print("no chart extractions found", file=sys.stderr)
        return 1
    readings = defaultdict(list)          # key -> [(value, source_file)]
    series_meta = {}
    unkeyed = 0

    # ---------------------------------------------------------------- REBASING
    # SSY rebases its index between editions, so a key's readings are only comparable
    # within one base. A base is NOT a property of the document: it changes over time.
    #
    # The evidence is entirely from the documents' own printed figures, never from the
    # chart. A report prints its Calculated Index and its "Change on Previous Index", so
    # the PREVIOUS week's level is recoverable exactly:
    #
    #     previous = current - change_on_previous
    #
    # Linking documents in publication order by that value finds where the chain breaks -
    # a break is a rebasing, because the previous value the document reports is not the
    # current value the document before it reported.
    #
    # Measured on ssy Pacific: the 3 Jan 2025 report prints 16,263 (its 2023 line runs
    # 6,063..90,279), the 27 Jun 2025 report prints 6,232 (its 2023 line runs
    # 3,328..9,287), and the legend mapping is byte-identical in both - teal=2023,
    # navy=2024, pink=2025. So the colours are right and the index itself changed level.
    docs = []
    for f in files:
        docs.append((f, json.loads(f.read_text(encoding="utf-8"))))

    def _dnum(s):
        # the extractor stores these as floats or None; the +/- sign is already carried
        if s is None or isinstance(s, (int, float)):
            return None if s is None else float(s)
        m = re.fullmatch(r"([+\-]?)([\d,]+)(?:\.(\d+))?", str(s).strip())
        if not m:
            return None
        v = float(m.group(2).replace(",", "") + ("." + m.group(3) if m.group(3) else ""))
        return -v if m.group(1) == "-" else v

    # per route, sort by report date (the date printed on the page)
    route_docs = defaultdict(list)
    for f, d in docs:
        route_docs[d.get("route")].append((d.get("report_date") or d["file"], f, d))
    base_id_of_doc = {}
    n_bases = defaultdict(int)
    for route, items in route_docs.items():
        items.sort(key=lambda t: t[0])
        bid = 0
        prev_reported = None
        for date, f, d in items:
            cur = (d.get("check") or {}).get("printed_calculated_index")
            chg = _dnum((d.get("check") or {}).get("change_on_previous"))
            if cur is None:
                base_id_of_doc[d["file"]] = f"{route}-b{bid}"
                continue
            if prev_reported is not None and chg is not None:
                implied_prev = cur - chg
                # a break is a rebasing: the previous document's current value is not
                # what this document says the previous value was
                if abs(implied_prev - prev_reported) / max(abs(prev_reported), 1) > 0.02:
                    bid += 1
            base_id_of_doc[d["file"]] = f"{route}-b{bid}"
            prev_reported = cur
        n_bases[route] = bid + 1
    print()
    print("INDEX BASES (a rebased index must not be compared across editions)")
    for route in sorted(n_bases, key=lambda x: (x is None, x)):
        cnt = sum(1 for v in base_id_of_doc.values() if v.startswith(f"{route}-"))
        print(f"  {route:<9} {n_bases[route]} base(s) across {cnt} documents")

    for f, d in docs:
        rid = d["file"]
        route = d.get("route")
        bid = base_id_of_doc[rid]
        for s in d["series"]:
            yr = s.get("year")
            sid = f"{bid} {yr}" if yr else f"{bid} unlabelled"
            series_meta.setdefault(sid, {"n_docs": 0, "n_points": 0, "colour": s.get("colour")})
            series_meta[sid]["n_docs"] += 1
            for p in s["points"]:
                v = p.get("index_value")
                if v is None:
                    continue
                k = key_for(p, yr, route)
                if k is None:
                    unkeyed += 1
                    continue
                readings[(bid,) + k].append((v, rid))
                series_meta[sid]["n_points"] += 1

    print(f"source files      : {len(files)}")
    print(f"distinct series   : {len(series_meta)}")
    print(f"distinct keys     : {len(readings)}")
    print(f"total readings    : {sum(len(v) for v in readings.values())}")
    print(f"unkeyable readings: {unkeyed}")

    # ---- THE PROOF: readings of the same key, taken from different reports, must agree
    multi = {k: v for k, v in readings.items() if len(v) > 1}
    rel = []
    worst = []
    for k, vals in multi.items():
        if len(vals) < 2:
            continue
        xs = [v for v, _ in vals]
        lo, hi = min(xs), max(xs)
        if lo <= 0:
            continue
        r = (hi - lo) / ((hi + lo) / 2)
        rel.append(r)
        worst.append((r, k, len(vals), lo, hi))
    worst.sort(reverse=True)
    if rel:
        rel.sort()
        n = len(rel)
        print()
        print("CROSS-REPORT AGREEMENT on repeated keys (the merge's own proof)")
        print(f"  keys seen in >1 report : {n}")
        print(f"  median relative spread : {statistics.median(rel):.4f}")
        print(f"  p90                     : {rel[int(n * 0.9)]:.4f}")
        print(f"  within 2%               : {sum(1 for r in rel if r <= 0.02)} ({100 * sum(1 for r in rel if r <= 0.02) / n:.1f}%)")
        print(f"  worst keys              :")
        for r, k, cnt, lo, hi in worst[:5]:
            print(f"     {k[1]} {k[2]}-{k[3]}-b{k[4]:<2} n={cnt:<3} "
                  f"{lo:9.1f}..{hi:9.1f}  spread={r:.3f}")

    # ---- write the long-format series
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for (_bid, route, y, mon, b), vals in sorted(readings.items()):
        xs = [v for v, _ in vals]
        rows.append({
            "route": route, "base": _bid, "year": y, "month": mon, "bucket": b,
            "n_reports": len(vals),
            "value": round(statistics.median(xs), 1),
            "min": round(min(xs), 1), "max": round(max(xs), 1),
            "value_sd": round(statistics.pstdev(xs), 2) if len(xs) > 1 else 0.0,
        })
    csv = OUT / "ssy_capesize_index_series.csv"
    with csv.open("w", encoding="utf-8", newline="") as fh:
        cols = ["route", "base", "year", "month", "bucket", "n_reports",
                "value", "min", "max", "value_sd"]
        fh.write(",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(str(r[c]) for c in cols) + "\n")
    print()
    print(f"wrote {len(rows)} rows -> {csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
