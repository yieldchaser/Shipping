"""Build data/derived/time_charter_rates.csv from its three sources, one owner per cell.

Ownership (each row's `source` names every source that wrote a cell in it):

* ``alibra_ocr`` - the printed weekly Alibra grids on Hellenic Shipping News
  (data/extracted/series/hellenic_alibra_{dry,tanker}_tc_series.csv). On a printed
  issue date it owns EVERY rate column; nothing else writes into that row.
* ``fearnleys`` - Fearnleys 1-year T/C (data/derived/time_charter_rates_fearnleys.csv)
  for 2000-01-01 up to the first printed issue: dry ``*_1y_avg`` plus
  ``vlcc_1y`` / ``suezmax_1y`` / ``aframax_1y``. Fearnleys has no ATL/PAC split.
* ``alibra_archive`` - Alibra's website dry trend archive (docs/alibra_data/
  dry_bulk_archive_{atl,pac}). It is the 4/6-month T/C series: it matches the printed
  4/6 MOS cells on ~98% of shared dates and the printed 1 YR cells on ~6%, so it
  fills ``*_4_6m_atl`` / ``*_4_6m_pac`` / ``*_4_6m_avg`` only, and only on dates
  with no printed grid. It never writes a 1-year column.

A date carrying both a Fearnleys and an archive value is labelled
``fearnleys+alibra_archive``.

The file is rebuilt from these inputs on every run, so a re-run is idempotent and a
wrong cell from an earlier writer cannot survive.
"""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TC_CSV = ROOT / "data" / "derived" / "time_charter_rates.csv"
FEARNLEYS_CSV = ROOT / "data" / "derived" / "time_charter_rates_fearnleys.csv"
DRY_SERIES = ROOT / "data" / "extracted" / "series" / "hellenic_alibra_dry_tc_series.csv"
WET_SERIES = ROOT / "data" / "extracted" / "series" / "hellenic_alibra_tanker_tc_series.csv"
ARCHIVE_DIR = ROOT / "docs" / "alibra_data"

FEARNLEYS_START = "2000-01-01"
ARCHIVE_START = "2008-01-01"

DRY_SEGMENTS = ["capesize", "panamax", "supramax", "handysize"]
DRY_TENORS = ["4_6m", "1y", "2y"]
WET_SEGMENTS = ["vlcc", "suezmax", "aframax", "mr", "lr1", "lr2", "handytanker"]
WET_TENORS = ["1y", "2y", "3y", "5y"]

TC_COLS = (
    ["date", "source"]
    + [f"{s}_{t}_{b}" for s in DRY_SEGMENTS for t in DRY_TENORS for b in ("atl", "pac", "avg")]
    + [f"{s}_{t}" for s in WET_SEGMENTS for t in WET_TENORS]
)

FEARNLEYS_COLS = [
    "capesize_1y_avg", "panamax_1y_avg", "supramax_1y_avg", "handysize_1y_avg",
    "vlcc_1y", "suezmax_1y", "aframax_1y",
]

ARCHIVE_COLS = {"HANDYSIZE": "handysize", "SMAX/ULTRA": "supramax", "PANAMAX": "panamax", "CAPESIZE": "capesize"}


def norm_dry_class(c):
    """Printed dry row label -> column segment, or None when the row has no column.

    The 2021-07-07..2022-01-05 grids print SUPRAMAX and ULTRAMAX as separate rows;
    the supramax columns take SUPRAMAX only (later grids print one SMAX/ULTRA row).
    ULTRAMAX and the one-off HANDY (30K dwt) row stay in the extracted series only.
    """
    c = str(c).upper().strip()
    if "CAPE" in c:
        return "capesize"
    if "PANA" in c:
        return "panamax"
    if c == "ULTRAMAX":
        return None
    if "SUPRA" in c or "SMAX" in c:
        return "supramax"
    if "HANDY" in c:
        return None if "30K" in c else "handysize"
    raise ValueError(f"unknown dry vessel class {c!r}")


def norm_dry_tenor(t):
    t = str(t).upper().strip()
    mapping = {"4/6 MOS": "4_6m", "6 MOS": "4_6m", "1 YR": "1y", "2 YR": "2y"}
    if t not in mapping:
        raise ValueError(f"unknown dry tenor {t!r}")
    return mapping[t]


def norm_dry_basin(b):
    b = str(b).upper().strip()
    if b not in ("ATL", "PAC"):
        raise ValueError(f"unknown dry basin {b!r}")
    return b.lower()


def norm_wet_class(c):
    c = str(c).upper().strip()
    if c.startswith("VLCC"):
        return "vlcc"
    if c.startswith("SUEZ"):
        return "suezmax"
    if c.startswith("AFRA"):
        return "aframax"
    if c.startswith("LR1"):
        return "lr1"
    if c.startswith("LR2"):
        return "lr2"
    if c.startswith("MR"):
        return "mr"
    if c.startswith("HANDY"):
        return "handytanker"
    raise ValueError(f"unknown tanker vessel class {c!r}")


def norm_wet_tenor(t):
    t = str(t).upper().strip()
    mapping = {"1 YR": "1y", "2 YR": "2y", "3 YR": "3y", "5 YR": "5y"}
    if t not in mapping:
        raise ValueError(f"unknown tanker tenor {t!r}")
    return mapping[t]


def _num(val):
    s = str(val if val is not None else "").strip().replace(",", "").replace("$", "")
    if not s or s.upper() in ("#N/A", "N/A", "NAN", "-", "NULL"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _read_csv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _set_avgs(cells, tenors):
    for seg in DRY_SEGMENTS:
        for tenor in tenors:
            atl = cells.get(f"{seg}_{tenor}_atl")
            pac = cells.get(f"{seg}_{tenor}_pac")
            if atl is not None and pac is not None:
                cells[f"{seg}_{tenor}_avg"] = (atl + pac) / 2.0
            elif atl is not None or pac is not None:
                cells[f"{seg}_{tenor}_avg"] = atl if atl is not None else pac


def load_printed(dry_path=DRY_SERIES, wet_path=WET_SERIES):
    """{issue_date: {column: value}} from the printed weekly grids."""
    out = {}
    for r in _read_csv(dry_path):
        seg = norm_dry_class(r["vessel_class"])
        tenor = norm_dry_tenor(r["tenor"])
        basin = norm_dry_basin(r["basin"])
        cells = out.setdefault(r["issue_date"], {})
        if seg is None:
            continue
        col = f"{seg}_{tenor}_{basin}"
        if col in cells:
            raise ValueError(f"{r['issue_date']}: two printed dry rows map to {col}")
        cells[col] = _num(r["rate_usd_pdpr"])
    for cells in out.values():
        _set_avgs(cells, DRY_TENORS)
    for r in _read_csv(wet_path):
        col = f"{norm_wet_class(r['vessel_class'])}_{norm_wet_tenor(r['tenor'])}"
        cells = out.setdefault(r["issue_date"], {})
        if col in cells:
            raise ValueError(f"{r['issue_date']}: two printed tanker rows map to {col}")
        cells[col] = _num(r["rate_usd_pdpr"])
    return out


def load_fearnleys(path=FEARNLEYS_CSV, end_before="9999-12-31"):
    """{date: {column: value}} for Fearnleys dates in [FEARNLEYS_START, end_before)."""
    out = {}
    for r in _read_csv(path):
        d = (r.get("date") or "").strip()
        if not (FEARNLEYS_START <= d < end_before):
            continue
        cells = {c: _num(r.get(c)) for c in FEARNLEYS_COLS}
        cells = {c: v for c, v in cells.items() if v is not None}
        if cells:
            out[d] = cells
    return out


def parse_archive_file(path):
    """{iso_date: {segment: rate}} from one Alibra dry trend archive CSV.

    Rows whose date is printed more than once with different values (e.g. weeks
    28-31 of 2019 all stamped 10 Jul 2019) cannot be placed on a date and are dropped.
    """
    seen = {}
    conflicted = set()
    for row in _read_csv(path):
        tag = list(row.values())[-1] if row else ""
        m = re.search(r"(\d{4}-\d{2}-\d{2})", str(tag or ""))
        if not m:
            continue
        d = m.group(1)
        if d < ARCHIVE_START:
            continue
        vals = {seg: _num(row.get(col)) for col, seg in ARCHIVE_COLS.items()}
        if d in seen and seen[d] != vals:
            conflicted.add(d)
        seen[d] = vals
    for d in conflicted:
        del seen[d]
    return seen


def load_archive(archive_dir=ARCHIVE_DIR):
    """{date: {column: value}} of 4/6-month ATL/PAC cells from the latest archive files."""
    out = {}
    for basin in ("atl", "pac"):
        files = sorted((archive_dir / f"dry_bulk_archive_{basin}").glob("*.csv"))
        if not files:
            continue
        for d, vals in parse_archive_file(files[-1]).items():
            cells = out.setdefault(d, {})
            for seg, v in vals.items():
                if v is not None:
                    cells[f"{seg}_4_6m_{basin}"] = v
    for cells in out.values():
        _set_avgs(cells, ["4_6m"])
    return {d: c for d, c in out.items() if c}


def compose(printed, fearnleys, archive):
    """Merge the three sources into sorted output rows (see module docstring)."""
    rows = []
    for d in sorted(set(printed) | set(fearnleys) | set(archive)):
        row = {c: "" for c in TC_COLS}
        row["date"] = d
        if d in printed:
            row["source"] = "alibra_ocr"
            row.update({c: v for c, v in printed[d].items() if v is not None})
        else:
            sources = []
            if d in fearnleys:
                sources.append("fearnleys")
                row.update(fearnleys[d])
            if d in archive:
                sources.append("alibra_archive")
                row.update(archive[d])
            row["source"] = "+".join(sources)
        rows.append(row)
    return rows


def build_time_charter_rates(out_path=TC_CSV):
    printed = load_printed()
    first_printed = min(printed) if printed else "9999-12-31"
    fearnleys = load_fearnleys(end_before=first_printed)
    archive = load_archive()
    rows = compose(printed, fearnleys, archive)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TC_COLS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    print(f"Wrote {out_path} ({len(rows)} rows): {counts}")
    return rows


def main():
    build_time_charter_rates()


if __name__ == "__main__":
    main()
