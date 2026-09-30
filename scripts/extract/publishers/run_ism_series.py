"""
ISM (Metal Expert Coasters & Mini Bulkers) - Time Series Stacking Pipeline.

Stacks the 112 extracted vector charts (.charts.json) across 2021-2026 into a clean,
deduplicated weekly time series:
  - data/extracted/series/ism_coaster_freight_series.csv

Handles rolling 52-week axes and explicit multi-year comparative curves:
  1. Damietta - Seville / Seville - Damietta (Urea, Steel) in $/t
  2. Izmail / Reni - Alexandria / Beirut (Corn, Soybeans, Wheat) in $/t
  3. Rostov / Azov - Marmara / Samsun (Coal, Wheat, Steel billets) in $/t
  4. Average coaster & mini-bulker TCEs in $/day (CVB, Danube/POC)
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
ISM_DIR = ROOT / "data" / "extracted" / "md" / "ism"
OUT_COASTER_CSV = ROOT / "data" / "extracted" / "series" / "ism_coaster_freight_series.csv"
OUT_HANDY_CSV = ROOT / "data" / "extracted" / "series" / "ism_handy_freight_series.csv"


def parse_doc_meta(p: Path, data: Dict[str, Any]) -> Tuple[int, int]:
    """Extract report_year and report_week from file or data['date']."""
    d_str = data.get("date", "")
    m = re.search(r"(20\d\d)\s*W(\d{1,2})", d_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    fn = p.name
    m = re.search(r"(\d{1,2})_(\d{1,2})_(20\d\d)", fn)
    if m:
        yr = int(m.group(3))
        mo = int(m.group(2))
        d = int(m.group(1))
        iso_wk = dt.date(yr, mo, d).isocalendar()[1]
        return yr, iso_wk
    m = re.search(r"(20\d\d).*?week[-_ ]?(\d{1,2})", fn, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 2024, 1


def week_to_iso(year: int, week: int) -> Optional[str]:
    """Convert year and week number to ISO date string (Monday)."""
    try:
        if week < 1:
            week = 1
        elif week > 53:
            week = 53
        return dt.date.fromisocalendar(year, week, 1).isoformat()
    except Exception:
        return None


CFR_MEAS = "% of freight costs in CFR price"
_UNIT_TAIL = re.compile(r",\s*(\$/(?:t|day)|EUR/t)\s*$", re.I)


def _norm_entity(txt: str) -> str:
    txt = _UNIT_TAIL.sub("", txt.strip())
    txt = txt.replace("calc. ", "").replace("calc.", "")
    return re.sub(r"\s+", " ", txt).strip(" ,")


def chart_entity(labels: List[str]) -> str:
    """Entity (cargo + destination/route) of a chart, from its SIBLING labels.

    The chart TITLE is not a stable entity key: the same cargo appears under
    "Russian billets: weight of freight in CFR Marmara price" AND "Russian steel
    billets: ...", while one title ("Ukrainian corn: weight of freight in CFR
    Egypt price") is reused across different cargoes. The identity lives in the
    sibling labels, so prefer those; fall back to the route label; else ''.
    """
    cfrs = [l for l in labels if "CFR" in l and CFR_MEAS not in l]
    if cfrs:
        return _norm_entity(cfrs[0])
    frs = [l for l in labels if l.lower().startswith("freight rate")]
    if frs:
        return _norm_entity(frs[0])
    return ""





def axis_range(chart) -> Tuple[Optional[float], Optional[float]]:
    """The chart's OWN printed y-axis span, from its tick labels."""
    ax = (chart.get("axes") or {}).get("primary") or {}
    vals = []
    for t in ax.get("raw") or []:
        t = str(t).replace("%", "").replace(",", "").strip()
        try:
            vals.append(float(t))
        except Exception:
            pass
    if not vals:
        return None, None
    return min(vals), max(vals)


def pick_observation(obs, iso_dt: str):
    """The publisher's statement of a week, from the BEST issue that carries it.

    ism redraws every chart every week over a rolling 52-week window, so one
    (route, label, week) is restated by up to 45 issues. The restatements are
    NOT interchangeable (measured on the TCT chart: 24.6% of restated points
    differ by >2% between the week's own issue and the latest one, 14.6% by
    >10%), and both window edges are unreliable - the newest point of the week's
    own issue is provisional (2024-W21 prints 17,035 for a week every later
    issue prints as 19,546) and the oldest point of a later issue is expiring.

    Convention, in order:
      1. prefer an observation that is NOT the first/last point of its series;
      2. among those, the issue nearest the observation date (ties -> earlier);
      3. if every observation is an edge, fall back to the nearest issue anyway.
    The chosen value is verbatim from the named issue; the full restatement band
    is kept in min_value/max_value/value_sd/n_reports.
    """
    try:
        tgt = dt.date.fromisoformat(iso_dt)
    except Exception:
        tgt = None

    def dist(o):
        try:
            return abs((dt.date.fromisoformat(o[1]) - tgt).days) if tgt else 0
        except Exception:
            return 10 ** 6

    interior = [o for o in obs if not o[6]]
    pool = interior or obs
    return min(pool, key=lambda o: (dist(o), o[1]))


def unit_for(title: str, labels: List[str]) -> str:
    """Unit of a chart, derived from the PAGE (label suffix, else title).

    The old code read a leaked loop variable `title` inside build_rows, so the
    unit came from whichever chart happened to be processed LAST: measured
    16,985 of 29,948 rows (57%) carried unit='$/day' on a chart whose own title
    and series label both end in '$/t'.
    """
    joined = " ".join(labels)
    if "%" in joined:
        return "%"
    low = title.lower()
    if "$/day" in joined:
        return "$/day"
    if "$/t" in joined or "eur/t" in joined.lower():
        return "EUR/t" if "eur/t" in joined.lower() else "$/t"
    if "$/day" in low or "tce" in low or "tct" in low or "rates dynamics" in low:
        return "$/day"
    if "eur" in low or "€" in title:
        return "EUR/t"
    if "$/t" in low:
        return "$/t"
    return "$/t"


def main() -> None:
    # md tier is organised by YEAR subdirectory (2023/, 2024/, ...); a non-recursive
    # glob silently finds 0 charts and rewrites both CSVs empty. Found 2026-09-30.
    chart_files = sorted(ISM_DIR.rglob("*.charts.json"))
    print(f"[ism] Processing {len(chart_files)} .charts.json files from {ISM_DIR}...")

    # (segment, route_title, series_label, iso_date) -> list of (value, report_iso, unit)
    readings_coaster: Dict[Tuple[str, str, str, str], List[Tuple[float, str, str, str, Optional[float], Optional[float], bool]]] = defaultdict(list)
    readings_handy: Dict[Tuple[str, str, str, str], List[Tuple[float, str, str, str, Optional[float], Optional[float], bool]]] = defaultdict(list)
    raw_points_count = 0

    for cf in chart_files:
        try:
            data = json.loads(cf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Error reading {cf.name}: {e}")
            continue

        rep_yr, rep_wk = parse_doc_meta(cf, data)
        rep_iso = week_to_iso(rep_yr, rep_wk) or cf.name
        is_handy_doc = "handy" in cf.name.lower() or "supramax" in cf.name.lower()

        for ch in data.get("charts", []):
            title = ch.get("title", "").strip()
            if not title:
                continue

            # Route segment
            if is_handy_doc or any(k in title.lower() for k in ["supramax", "handysize", "ultramax", "tct", "corn", "scrap"]):
                segment = "Handysize/Supramax"
                target_readings = readings_handy
            else:
                segment = "Coaster"
                target_readings = readings_coaster

            labels_all = [(x.get("label") or "").strip() for x in ch.get("series", [])]
            entity = chart_entity(labels_all)
            panel = entity or title          # entity when known, else the chart title

            for s in ch.get("series", []):
                label = (s.get("label") or "").strip()
                if not label:
                    continue
                # unit is a property of the SERIES, not the chart: a CFR-weight
                # chart carries a '%' line AND a 'Freight rate, ..., $/t' line.
                chart_unit = unit_for(title, [label])
                ax_lo, ax_hi = axis_range(ch)

                weeks = s.get("weeks", [])
                vals = s.get("values", [])

                m_yr = re.search(r"\b(202\d)\b", label)
                fixed_year = int(m_yr.group(1)) if m_yr else None

                # A multi-year COMPARATIVE chart plots several years on one
                # repeating 52-week x axis (ticks 1,9,...,49 then 5,13,...,45
                # - a 52-point period, confirmed by the tick pitch itself), so
                # a 154-point series is 52+52+50 = 2021,2022,2023. Assigning the
                # year from the week number alone (the old behaviour) crammed
                # all three years onto one date and fused 2021/2022/2023 values
                # into a single "series" - which is what made the agreement gate
                # report 10-180% spreads on a chart that is perfectly extracted.
                span = re.search(r'(20\d\d)\s*[-–]\s*(20\d\d)', title)
                multi = bool(span) and len(vals) > 60
                for idx, (wk, val) in enumerate(zip(weeks, vals)):
                    if wk is None or val is None:
                        continue
                    try:
                        wk_int = int(wk)
                        val_float = float(val)
                    except (ValueError, TypeError):
                        continue

                    if fixed_year:
                        pt_yr = fixed_year
                    elif multi:
                        pt_yr = int(span.group(1)) + idx // 52
                    else:
                        if wk_int > rep_wk:
                            pt_yr = rep_yr - 1
                        else:
                            pt_yr = rep_yr

                    iso_dt = week_to_iso(pt_yr, wk_int)
                    if not iso_dt:
                        continue

                    target_readings[(segment, panel, label, iso_dt)].append(
                        (val_float, rep_iso, cf.name, chart_unit, ax_lo, ax_hi,
                         idx == 0 or idx == len(vals) - 1))
                    raw_points_count += 1

    print(f"[ism] Total raw points extracted: {raw_points_count:,}")
    print(f"[ism] Distinct coaster keys: {len(readings_coaster):,}, handy keys: {len(readings_handy):,}")

    def build_rows(readings_dict: Dict[Tuple[str, str, str, str], List[Tuple[float, str, str, str, Optional[float], Optional[float], bool]]]) -> List[Dict[str, Any]]:
        rows = []
        for (seg, panel, label, iso_dt), obs in sorted(readings_dict.items()):
            # A point drawn OUTSIDE its own chart's printed axis is an
            # extrapolation, not a value the publisher stated: measured 14 such
            # observations corpus-wide, all negative freight rates.
            inr = [o for o in obs
                   if o[4] is None or o[5] is None or (o[4] <= o[0] <= o[5])]
            if not inr:
                continue
            obs = inr
            vals = [o[0] for o in obs]
            min_val = round(min(vals), 2)
            max_val = round(max(vals), 2)
            stdev = round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0

            # The value is the one the publisher printed in the best issue
            # carrying that week (see pick_observation) - verbatim, never a
            # median across restatements that contradict each other.
            chosen = pick_observation(obs, iso_dt)
            value = round(chosen[0], 2)
            value_report = chosen[2]

            units = [o[3] for o in obs]
            unit = max(set(units), key=units.count)

            rows.append({
                "date": iso_dt,
                "segment": seg,
                "route_title": panel,
                "series_name": label,
                "value": value,
                "unit": unit,
                "n_reports": len(obs),
                "value_edge": int(bool(chosen[6])),
                "value_report": value_report,
                "min_value": min_val,
                "max_value": max_val,
                "value_sd": stdev,
            })
        return rows

    fieldnames = [
        "date", "segment", "route_title", "series_name", "value", "unit",
        "n_reports", "value_edge", "value_report", "min_value", "max_value", "value_sd"
    ]

    # 1. Write Coaster series
    coaster_rows = build_rows(readings_coaster)
    OUT_COASTER_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_COASTER_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(coaster_rows)
    print(f"[ism] Successfully wrote {len(coaster_rows):,} coaster rows -> {OUT_COASTER_CSV}")

    # 2. Write Handy series
    handy_rows = build_rows(readings_handy)
    with open(OUT_HANDY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(handy_rows)
    print(f"[ism] Successfully wrote {len(handy_rows):,} handy rows -> {OUT_HANDY_CSV}")


if __name__ == "__main__":
    main()
