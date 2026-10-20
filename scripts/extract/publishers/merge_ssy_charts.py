"""ssy - stack the weekly chart extractions into one weekly index series, gated per report.

Each SSY report (Atlantic and Pacific, weekly) draws its index as two or three yearly
lines. run_ssy_charts.py reads every vertex off the vector strokes. This script decides
which reports to trust and stacks their readings into one row per route and week.

THE GATE: EVERY REPORT IS CHECKED AGAINST THE PRINTED INDEX
-----------------------------------------------------------
Every report also PRINTS the index (current and previous week) in its table, and those
tables are in ssy_capesize_index_time_series.csv for every week since July 2021. A chart
vertex dated to a printed week must read that week's printed value. Per report, the median
relative error over its matched vertices is the calibration measure:

    accepted  when  median error <= GATE_MAX_ERR  over  >= GATE_MIN_MATCHES vertices

A report that fails is left out entirely (its lines for older years too), and is listed.
Measured 2026-10-20 after the axis fixes in run_ssy_charts.py: chart against print within
about 0.5% where the ladder and dates are right. Before them, every reading sat a constant
amount low (labels read by their top edge, not the gridline) and dates ran 3-12 days early.

BASES: ONE REAL REBASING, ONE MISPRINTED PAGE
---------------------------------------------
Until 2026-10-20 this script split the series into a "basis" at every break in the printed
index chain. Checked against the PDFs, the breaks are:

  * Atlantic 2023-06-26: a real rebasing (basket change, Hampton Roads/Rotterdam replaced
    by Seven Islands/Rotterdam). The 2023-06-26 issue prints the previous week as 7,387
    where the 2023-06-19 issue printed 7,827, and every chart drawn after it shows all
    history on the new basis. Rows carry `basis` = 2015-07-17 or 2023-06-26 (BASES).
  * Pacific 2025-01-03: a publisher error, not a rebasing. It prints 16,263 / 21,348 and
    draws its 2023/2024 lines up to 90,279; SSY's next issue prints that week as 4,367.
    The gate keeps that chart out. The Pacific was never rebased.
  * The rest are single misprinted cells (see PRE_GRAPHRAG_OPEN_ITEMS) or the 2023-10
    switch from Monday to Friday assessments (one week listed under both dates).

KEYS
----
One row per (route, basis, week). A vertex is dated by run_ssy_charts.py (`iso_date`). It
is snapped to the printed assessment date when one exists, so readings of the same week
from different reports land on one key. Friday-dated vertices (grid and month layouts)
snap forward first, to the Monday or holiday Tuesday that was assessed before 2023-10.
Weeks before July 2021 (the 2019, 2020 and early-2021 lines) have no printed table in the
corpus: slot-dated vertices step back a week at a time, month-dated ones keep their date.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

try:                                    # sibling module, same directory
    import chart_series_incremental as inc
except ImportError:                     # pragma: no cover - imported as a package
    from scripts.extract.publishers import chart_series_incremental as inc

REPO = Path(__file__).resolve().parents[3]
CHARTS = REPO / "data" / "extracted" / "charts" / "ssy"
OUT = REPO / "data" / "extracted" / "series"
CSV_NAME = "ssy_capesize_index_series.csv"
TIME_SERIES_NAME = "ssy_capesize_index_time_series.csv"
CSV_COLS = ["route", "basis", "date", "n_reports", "value", "min", "max", "value_sd",
            "printed_index"]
GATE_MAX_ERR = 0.02
GATE_MIN_MATCHES = 4
GATE_RECENT_WEEKS = 8
MATCH_DAYS = 3

# Index definition dates ("The latest update was on ..."), from the pages. SSY rebased the
# Atlantic index on 26 June 2023 (basket change: Hampton Roads/Rotterdam replaced by Seven
# Islands/Rotterdam). Its 2023-06-26 issue prints the previous week as 7,387 where the
# 2023-06-19 issue had printed 7,827, and every chart drawn after it shows all history on
# the new basis (the 2022 line ~445 points below what was printed in 2022). The pages
# from 2023-10-20 to 2024-01-12 (the new template) print "17 July 2015" again although the
# chain runs straight through them, a template slip corrected on 2024-01-19, so the basis
# is assigned by issue date, not read off the page. The Pacific was never rebased.
BASES = {"ATLANTIC": [(dt.date(2023, 6, 26), "2023-06-26")]}
BASE_DEFAULT = "2015-07-17"


def basis_of(route, report_date):
    b = BASE_DEFAULT
    for start, name in BASES.get(route, []):
        if report_date is not None and report_date >= start:
            b = name
    return b


def _collapse(weeks):
    """One date per assessment: the 2023 switch from Monday to Friday lists one assessment
    under both (Atlantic 2023-10-13 and 2023-10-16, both 11,587). The earlier is kept."""
    out = []
    for w in sorted(weeks):
        if out and (w - out[-1]).days <= MATCH_DAYS:      # Mon 10-09 / Fri 10-13 are 4 apart
            continue
        out.append(w)
    return out


def printed_weeks(ts_rows):
    """(dates, values): every assessed week per ROUTE, and {(ROUTE, basis): {date: value}}.

    A value belongs to the basis of the report that printed it (current column wins)."""
    raw = defaultdict(set)
    vals = defaultdict(dict)
    for col_d, col_v in (("rates_date_prev", "calculated_index_prev"),
                         ("rates_date_curr", "calculated_index_curr")):
        for r in ts_rows:
            try:
                route = r["basin"].upper()
                d = dt.date.fromisoformat(r[col_d])
                rep = dt.date.fromisoformat(r["rates_date_curr"])
            except (KeyError, ValueError, TypeError):
                continue
            raw[route].add(d)
            try:
                vals[(route, basis_of(route, rep))][d] = float(r[col_v])
            except (ValueError, TypeError):
                continue
    dates = {route: _collapse(ws) for route, ws in raw.items()}
    for key, by in vals.items():
        keep = dates.get(key[0], [])
        for d in sorted(by):
            if d in keep:
                continue
            near = [q for q in keep if abs((q - d).days) <= MATCH_DAYS]
            if near:                                 # a collapsed twin date: file under the kept one
                by.setdefault(near[0], by[d])
            del by[d]
    return dates, vals


def report_dates(ts_rows):
    """source_file -> the report's own (current) rates date, from the printed table."""
    out = {}
    for r in ts_rows:
        try:
            out[r["source_file"]] = dt.date.fromisoformat(r["rates_date_curr"])
        except (KeyError, ValueError, TypeError):
            continue
    return out


def align_slots(doc, weeks, rep_date):
    """Re-date the slot-dated (2021-23 layout) vertices onto the weeks SSY actually assessed.

    That layout has one x slot per published assessment, and a week SSY did not assess has
    NO slot: measured on the 2023 Atlantic line, no 2023-02-20 assessment, so counting slots
    from the second Monday of January dated every later vertex a week early (2023-08-21
    read 7,064, which is the printed 2023-08-29 value 7,081). The printed tables list the
    weeks that were assessed, so each line is aligned from its END: its last vertex is the
    last assessed week of that year up to the report (verified: the current-year line ends
    on the report's own printed index), and earlier vertices take the earlier assessed
    weeks in order. Vertices older than the printed record (before July 2021) step back a
    week at a time from the first aligned one.

    A year with no printed week at all (the 2019 and 2020 lines) is dated by vertex ORDER
    from the second Monday of January, one week per vertex. Dating those by x position
    drifted a week over the year (the slot step is measured, not printed): the same 51
    vertices of 2019 ended on 2019-12-23 in the Atlantic reports and 2019-12-30 in the
    Pacific ones, and single reports (A/P20211220, four 2022 issues) a week off the rest.
    Ordered from slot 0, both basins and all reports agree. That assumes no week of
    2019-20 went unassessed, which the corpus cannot check.
    """
    if rep_date is None:
        return
    for s in doc.get("series", []):
        yr = s.get("year")
        pts = s.get("points") or []
        if not yr or not str(yr).isdigit() or not pts or pts[0].get("dating") != "slot":
            continue
        dates = [w for w in weeks if w.year == int(yr)
                 and w <= rep_date + dt.timedelta(days=MATCH_DAYS)]
        if not dates:
            if int(yr) < min(weeks, default=rep_date).year:
                first = _second_monday(int(yr))
                for j, p in enumerate(pts):
                    p["iso_date"] = (first + dt.timedelta(days=7 * j)).isoformat()
            continue
        for j, p in enumerate(reversed(pts)):
            if j < len(dates):
                d = dates[-1 - j]
            else:
                d = dates[0] - dt.timedelta(days=7 * (j - len(dates) + 1))
            p["iso_date"] = d.isoformat()


def _second_monday(year):
    d = dt.date(year, 1, 1)
    return d + dt.timedelta(days=(7 - d.weekday()) % 7 + 7)


def week_of(point, weeks):
    """The week of a vertex: snapped to an assessed week within MATCH_DAYS, else its own date."""
    try:
        d = dt.date.fromisoformat(point["iso_date"])
    except (KeyError, TypeError, ValueError):
        return None
    if point.get("dating") in ("grid", "month"):
        # These layouts date a vertex to its Friday (+-1 day), and before October 2023 that
        # week's assessment was the FOLLOWING Monday, or Tuesday after a bank holiday
        # (measured: shift +3 days matches print to 0.6%, -4 days to 4.9%). Nearest-date
        # snapping pulled the next Friday back onto a holiday Tuesday (Pacific 2022-08-30,
        # 2023-04-11), so these snap forward first.
        ahead = [((q - d).days, q) for q in weeks if 0 <= (q - d).days <= MATCH_DAYS + 2]
        if ahead:
            return min(ahead)[1]
        if weeks and d < weeks[0]:
            # Before the printed record (pre-July 2021) there is no week to snap to: the
            # assessment was that following Monday, so the key is the Monday, the same key
            # the slot-dated (2021-23 layout) readings of that week have.
            return d + dt.timedelta(days=(7 - d.weekday()) % 7)
    near = [(abs((q - d).days), q) for q in weeks if abs((q - d).days) <= MATCH_DAYS]
    return min(near)[1] if near else d


def gate(doc, weeks, printed, rep_date=None):
    """(accepted, median error, matched vertices) of one report against the printed index.

    Calibration is checked on the report's most recent GATE_RECENT_WEEKS printed weeks of
    the same basis, read off the current-year line and, in January when that line is a few
    weeks long, the previous year's: that is what proves the ladder and the dates were read
    right. Older lines are not used: after a rebasing they are drawn on the new basis and
    were printed on the old one.
    """
    years = {str(rep_date.year), str(rep_date.year - 1)} if rep_date else None
    matched = []
    for s in doc.get("series", []):
        if not s.get("year") or (years and s["year"] not in years):
            continue
        for p in s["points"]:
            v = p.get("index_value")
            wk = week_of(p, weeks)
            pv = printed.get(wk) if v is not None else None
            if pv:
                matched.append((wk, abs(v - pv) / pv))
    errs = [e for _, e in sorted(matched)[-GATE_RECENT_WEEKS:]]
    if len(errs) < GATE_MIN_MATCHES:
        return False, None, len(errs)
    med = statistics.median(errs)
    return med <= GATE_MAX_ERR, med, len(errs)


def dedupe_docs(docs):
    """Drop re-drops of one issue (same route, report date, printed index and change).

    The same weekly PDF is routinely collected twice under different file names.
    """
    seen, out = set(), []
    for f, d in docs:
        chk = d.get("check") or {}
        k = (d.get("route"), d.get("report_date"), chk.get("printed_calculated_index"),
             chk.get("change_on_previous"), chk.get("series_last"))
        if k in seen:
            continue
        seen.add(k)
        out.append((f, d))
    return out


def collect(docs, weeks_by_route, printed_by_key, rep_dates):
    """(readings, gate report): readings[(ROUTE, basis, date)] -> [(value, file)], accepted only."""
    readings = defaultdict(list)
    report = []
    for _f, d in docs:
        route = d.get("route")
        rep_date = rep_dates.get(d["file"])
        basis = basis_of(route, rep_date)
        weeks = weeks_by_route.get(route, [])
        printed = printed_by_key.get((route, basis), {})
        align_slots(d, weeks, rep_date)
        ok, med, n = gate(d, weeks, printed, rep_date)
        report.append((d["file"], route, ok, med, n))
        if not ok:
            continue
        for s in d["series"]:
            if not s.get("year"):
                continue
            pts = s["points"]
            if (pts and pts[0].get("dating") == "grid" and rep_date
                    and s["year"] != str(rep_date.year)):
                continue          # older lines on the weekly-grid layout: see run_ssy_charts
            # One reading per line per week, the earlier vertex kept. The 2024+ charts draw
            # their 2022 line with an extra point on the UK holiday Fridays 2022-04-15 and
            # 2022-06-03 (8,999 and 11,690 Atlantic), right after the real assessment (9,603
            # and 12,548), and both snap to the same assessed week. Where a printed value
            # exists the earlier vertex is the right one in 112 of 113 such collisions.
            seen = set()
            for p in pts:
                v = p.get("index_value")
                day = week_of(p, weeks)
                if v is None or day is None or day in seen:
                    continue
                seen.add(day)
                readings[(route, basis, day)].append((v, d["file"]))
    return readings, report


def rows_from_readings(readings, printed_by_key):
    rows = []
    for (route, basis, day), vals in sorted(readings.items()):
        xs = [v for v, _ in vals]
        pv = printed_by_key.get((route, basis), {}).get(day)
        rows.append({
            "route": route, "basis": basis, "date": day.isoformat(), "n_reports": len(vals),
            "value": round(statistics.median(xs), 1),
            "min": round(min(xs), 1), "max": round(max(xs), 1),
            "value_sd": round(statistics.pstdev(xs), 2) if len(xs) > 1 else 0.0,
            "printed_index": "" if pv is None else round(pv, 1),
        })
    return rows


def row_key(r):
    return (str(r["route"]), str(r["basis"]), str(r["date"]))


def print_gate(report):
    acc = [r for r in report if r[2]]
    rej = [r for r in report if not r[2]]
    meds = sorted(r[3] for r in acc)
    print(f"gate: {len(acc)} of {len(report)} report(s) accepted "
          f"(median error <= {GATE_MAX_ERR:.0%} over >= {GATE_MIN_MATCHES} printed weeks)")
    if meds:
        print(f"  accepted: median error {statistics.median(meds):.4f}, worst {meds[-1]:.4f}")
    for f, route, _ok, med, n in sorted(rej):
        why = f"median error {med:.3f}" if med is not None else f"only {n} printed week(s) to check"
        print(f"  REJECTED {f} ({route}): {why}")


def load_docs(charts_dir):
    files = sorted(Path(charts_dir).glob("*.charts.json"))
    return files, dedupe_docs([(f, json.loads(f.read_text(encoding="utf-8"))) for f in files])


def merge_new_only(charts_dir=None, out_dir=None):
    """Upsert the gated readings of the chart files in `charts_dir` into the series CSV.

    Never rewrites history: keys already in the CSV are kept as they are, unseen keys are
    appended. `charts_dir` holds only the NEW reports' extractions (run_ssy_charts
    --new-only --out-dir).
    """
    out_dir = Path(out_dir or OUT)
    files, docs = load_docs(charts_dir or CHARTS)
    if not files:
        print("new-only: no chart extractions to merge")
        return 0
    _, existing = inc.read_rows(OUT / CSV_NAME)
    _, ts_rows = inc.read_rows(OUT / TIME_SERIES_NAME)
    weeks, printed = printed_weeks(ts_rows)
    readings, report = collect(docs, weeks, printed, report_dates(ts_rows))
    print_gate(report)
    produced = rows_from_readings(readings, printed)
    merged, added, kept = inc.upsert_new_keys(existing, produced, row_key, CSV_COLS,
                                              row_key)
    inc.write_rows(out_dir / CSV_NAME, CSV_COLS, merged)
    print(f"new-only: {len(files)} report(s), {len(produced)} weeks produced: "
          f"+{added} appended, {kept} already present kept -> {out_dir / CSV_NAME} "
          f"({len(merged)} rows)")
    return 0


def main(argv=()):
    if "--new-only" in argv:
        charts = Path(argv[argv.index("--charts-dir") + 1]) if "--charts-dir" in argv else CHARTS
        out = Path(argv[argv.index("--out-dir") + 1]) if "--out-dir" in argv else OUT
        return merge_new_only(charts, out)
    charts = Path(argv[argv.index("--charts-dir") + 1]) if "--charts-dir" in argv else CHARTS
    files, docs = load_docs(charts)
    if not files:
        print("no chart extractions found", file=sys.stderr)
        return 1
    _, ts_rows = inc.read_rows(OUT / TIME_SERIES_NAME)
    weeks, printed = printed_weeks(ts_rows)
    readings, report = collect(docs, weeks, printed, report_dates(ts_rows))
    print_gate(report)

    # Cross-report agreement: one week read from several reports must agree.
    spreads = sorted((max(v for v, _ in vals) - min(v for v, _ in vals))
                     / statistics.median([v for v, _ in vals])
                     for vals in readings.values() if len(vals) > 1)
    if spreads:
        n = len(spreads)
        print(f"agreement: {n} weeks read by >1 report, median spread {spreads[n // 2]:.4f}, "
              f"p90 {spreads[int(n * 0.9)]:.4f}, within 2% {sum(s <= 0.02 for s in spreads)}")
    rows = rows_from_readings(readings, printed)
    inc.write_rows(OUT / CSV_NAME, CSV_COLS, rows)
    print(f"wrote {len(rows)} rows -> {OUT / CSV_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
