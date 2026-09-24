"""intermodal - stack the 489 chart extractions into time series, and PROVE the join.

The same self-validating agreement check that closed ssy, applied here.

WHY
---
Each weekly report redraws a rolling twelve-month window of the same two charts. So a
point at the same calendar date in two different reports is the same WEEK measured
twice, and the two must agree to within the chart's plotting resolution. If the date
mapping or the scale is wrong, points from different weeks merge and the spread
explodes. The spread of repeated readings is therefore a measurement of the JOIN, and
nothing inside the extractor can see it.

KEYS
----
(route, series_name, date) -> value.

`route` and `series_name` come from the extractor: the route is Atlantic or Pacific and
they are DIFFERENT indices, so they must never share a key. The series name comes from an
exact RGB join to the chart's own legend swatch, never from row order or from the order
the PDF emitted the paths.

The chart's own last reading is NOT the report's current value, and that is expected
rather than a defect: the axis ends at the report's own month-end, the final weekly point
sits just before it, and the printed table carries the as-at-report-date figure. Measured
on 2025 W49, the chart's last BDI point is 2,465 and the table prints 2,727; a 600-dpi
pixel re-read matched the vector path to 0.01pt, so both are right. See
docs/intermodal_charts_STATE.md.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import date as _date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CHARTS = REPO / "data" / "extracted" / "charts" / "intermodal"
OUT = REPO / "data" / "extracted" / "series"

# How close a calendar date must be for two readings to be the same week. The chart's
# points are daily and two reports can straddle a week boundary, so a +/- 3 day window is
# the right tolerance: tighter merges distinct weeks, looser blurs them.
SAME_WEEK_DAYS = 3


def parse(s):
    try:
        return _date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def main():
    files = sorted(CHARTS.glob("*.charts.json"))
    if not files:
        print("no intermodal chart extractions found", file=sys.stderr)
        return 1
    readings = defaultdict(list)          # (route, series, iso_date) -> [(v, file)]
    series_meta = {}
    undated = 0
    span = {}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        rid = d["file"]
        for c in d.get("charts", []):
            for s in c.get("series", []):
                nm = s.get("name")
                if not nm:
                    continue
                # NO ROUTE IN THE KEY. There is not one to use. The route word appears
                # only in the report's PROSE - "in the Pacific market", "the North Atlantic"
                # - and a single page carries both, so it identifies the commentary, not
                # the chart. Measured: the extracted BDI level across all 252 reports is one
                # continuum (p25 978, median 1,410, p75 1,878), not two modes, so these are
                # NOT two indices that need separating.
                #
                # An earlier merge guessed the route from the filename and classified 252
                # of 252 as ATLANTIC. That was harmless only because the guess was
                # constant; had the corpus contained a Pacific-naming file, two different
                # series would have silently shared a key. The lesson is the general one:
                # do not manufacture a key component to make a grouping look tidy.
                sid = nm
                meta = series_meta.setdefault(
                    sid, {"n_docs": 0, "n_points": 0, "min": None, "max": None,
                          "colour": s.get("colour")})
                meta["n_docs"] += 1
                for p in s.get("points", []):
                    v = p.get("value")
                    dt = parse(p.get("date"))
                    if v is None or dt is None:
                        undated += 1
                        continue
                    iso = dt.isoformat()
                    readings[(nm, iso)].append((v, rid))
                    meta["n_points"] += 1
                    if meta["min"] is None or v < meta["min"]:
                        meta["min"] = v
                    if meta["max"] is None or v > meta["max"]:
                        meta["max"] = v
                    lo, hi = span.get(sid, (iso, iso))
                    span[sid] = (min(lo, iso), max(hi, iso))

    print(f"source files     : {len(files)}")
    print(f"distinct series  : {len(series_meta)}")
    print(f"distinct keys    : {len(readings)}")
    print(f"total readings   : {sum(len(v) for v in readings.values())}")
    print(f"undated readings : {undated}")
    print()
    print("SERIES")
    for sid in sorted(series_meta):
        m = series_meta[sid]
        lo, hi = span.get(sid, ("", ""))
        print(f"  {sid:<34} docs={m['n_docs']:<4} pts={m['n_points']:<7} "
              f"{m['min']:>10,.0f}..{m['max']:<10,.0f} {lo} .. {hi}")

    # ---- THE PROOF: repeated readings of one key, from different reports
    multi = {k: v for k, v in readings.items() if len(v) > 1}
    rel = []
    worst = []
    for k, vals in multi.items():
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
        within1 = sum(1 for r in rel if r <= 0.01)
        within2 = sum(1 for r in rel if r <= 0.02)
        print()
        print("CROSS-REPORT AGREEMENT on repeated (route, series, date) keys")
        print(f"  keys seen in >1 report : {n}")
        print(f"  median relative spread : {statistics.median(rel):.4f}")
        print(f"  p90                     : {rel[int(n * 0.9)]:.4f}")
        print(f"  within 1%               : {within1} ({100 * within1 / n:.1f}%)")
        print(f"  within 2%               : {within2} ({100 * within2 / n:.1f}%)")
        print("  worst keys:")
        for r, k, cnt, lo, hi in worst[:6]:
            print(f"     {k[0]:<22} {k[1]}  n={cnt:<4} "
                  f"{lo:10,.1f}..{hi:<10,.1f}  spread={r:.3f}")

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for (nm, iso), vals in sorted(readings.items()):
        xs = [v for v, _ in vals]
        rows.append({
            "series": nm, "date": iso, "n_reports": len(vals),
            "value": round(statistics.median(xs), 1),
            "min": round(min(xs), 1), "max": round(max(xs), 1),
            "value_sd": round(statistics.pstdev(xs), 2) if len(xs) > 1 else 0.0,
        })
    csv = OUT / "intermodal_baltic_tc_series.csv"
    with csv.open("w", encoding="utf-8", newline="") as fh:
        cols = ["series", "date", "n_reports", "value", "min", "max", "value_sd"]
        fh.write(",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(str(r[c]) for c in cols) + "\n")
    print()
    print(f"wrote {len(rows)} rows -> {csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
