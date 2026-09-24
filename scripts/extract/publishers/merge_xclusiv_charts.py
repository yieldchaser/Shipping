"""Merge the xclusiv chart series into ONE long-run time series.

The six annual snapshots hold the same family of series in two different shapes:

  2021-2025 (wide):    one table per chart, first column Month
      Month | VLCC 1y TC (Eco) | SUEZMAX 1y TC (Eco) | AFRAMAX 1y TC (Eco)
      Month | VLCC (TD3C)    | SUEZMAX (TD20)    | AFRAMAX (TD7)
      Month | LR2 1y TC (Eco)| LR1 1y TC (Eco)   | MR2 1y TC (Eco)
      Month | LR2(TC1)       | LR1 (TC5)         | ATL. BASKET | PAC. BASKET

  2026 (long):          one table, Date | Panel | TCE | Average | Min | Max
      Date | Panel | TCE ($/day) | ...
      with 5 panels x 13 dates

Both are normalised here to a single tidy shape so the series concatenate:

    report_date, chart_series, panel, period_label, value_usd_per_day

Two honest caveats, carried from docs/xclusiv_charts_ROLLOUT_VERDICT.md:
  * the charts expose only ~13-15 LABELLED x-positions, so values are SAMPLED at the
    labelled dates, not the full weekly line;
  * consecutive reports re-sample the same window rather than extending it, so a later
    report supersedes an earlier one for overlapping dates. The `superseded_by` column
    records that, and `latest` is written for unambiguous use.
"""
import collections
import csv
import glob
import json
import os
import re
from pathlib import Path

# NOTE: the file lives at scripts/extract/publishers/, so the repo root is parents[3].
# parents[2] lands in scripts/ and silently yields SRC/ROOT that do not exist - which
# produced an EMPTY series file with no error. Same off-by-one class as the earlier
# intermodal import bug: assert the path exists rather than trusting the index.
ROOT = Path(__file__).resolve().parents[3]
assert (ROOT / "data" / "extracted" / "llamaparse_xclusiv_charts").exists(), \
    f"wrong ROOT: {ROOT}"
SRC = ROOT / "data" / "extracted" / "llamaparse_xclusiv_charts"
OUT = ROOT / "data" / "derived"

# only the six ANNUAL snapshot documents; the ad-hoc capability tests are excluded
ANNUAL = {}
for f in glob.glob(str(SRC / "xclusiv_20*.tables.json")):
    b = os.path.basename(f)
    m = re.search(r"xclusiv_(\d{4})", b)
    if not m:
        continue
    if any(tag in b for tag in ("12_19", "12_27", "08_31", "21st")):
        continue                      # earlier ad-hoc runs, kept for provenance
    ANNUAL[f] = m.group(1)

# report date from the filename
def report_date(path):
    b = os.path.basename(path)
    m = re.search(r"(\d{4})[_-](\d{2})[_-](\d{2})", b)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"xclusiv_(\d{4})_xclusiv-(\d{4})_(\d{2})_(\d{2})", b)
    if m:
        return f"{m.group(2)}-{m.group(3)}-{m.group(4)}"
    m = re.search(r"(\d{4})[_-](\d{2})[_-](\d{2})", b)
    return m.group(0).replace("_", "-") if m else ""


def to_usd(v):
    if v is None:
        return ""
    s = str(v).strip().replace(",", "")
    if not s or s in ("-", "N/A", "n/a"):
        return ""
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        x = float(s)
    except ValueError:
        return ""
    if neg:
        x = -x
    return str(int(round(x)))


# The same series is spelled differently across eras: 'AFRAMAX 1y TC (Eco)' in 2022,
# 'Aframax 1y TC' in 2021, 'Aframax TCE' in 2026. Without canonical names the series
# split into 27 fragments that cannot be concatenated, which defeats the whole point.
# Canonicalisation is explicit and one-to-one; anything unmatched keeps its own name
# rather than being silently merged into a wrong series.
CANON = {
    "VLCC (TD3C)": "VLCC spot", "SUEZMAX (TD20)": "Suezmax spot",
    "SUEZMAX (TD6)": "Suezmax spot", "AFRAMAX (TD7)": "Aframax spot",
    "LR2(TC1)": "LR2 spot", "LR1 (TC5)": "LR1 spot",
    "ATL. BASKET (TC2/TC14)": "MR Atlantic Basket spot",
    "PAC. BASKET (TC12/TC11)": "MR Pacific Basket spot",
    "VLCC 1y TC": "VLCC 1y TC", "VLCC 1y TC (Eco)": "VLCC 1y TC",
    "SUEZMAX 1y TC": "Suezmax 1y TC", "SUEZMAX 1y TC (Eco)": "Suezmax 1y TC",
    "Suezmax 1y TC": "Suezmax 1y TC",
    "AFRAMAX 1y TC": "Aframax 1y TC", "AFRAMAX 1y TC (Eco)": "Aframax 1y TC",
    "Aframax 1y TC": "Aframax 1y TC",
    "LR2 1y TC": "LR2 1y TC", "LR2 1y TC (Eco)": "LR2 1y TC",
    "LR1 1y TC": "LR1 1y TC", "LR1 1y TC (Eco)": "LR1 1y TC",
    "MR2 1y TC": "MR2 1y TC", "MR2 1y TC (Eco)": "MR2 1y TC",
    "VLCC TCE": "VLCC spot", "Suezmax TCE": "Suezmax spot",
    "Aframax TCE": "Aframax spot",
    "MR Atlantic Basket": "MR Atlantic Basket spot",
    "MR Pacific Basket": "MR Pacific Basket spot",
}


# Date labels are written differently by era ('Apr-20', 'Apr 21', 'Sept 21'), so they
# must be normalised to sort and to be comparable across reports. Without this, a
# four-letter 'Sept' slipped through the three-letter map and the spot series appeared to
# stop at 2021.
_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
           "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}


def period_key(label):
    """'Sept 21' / 'Apr-20' / 'Apr 21'  ->  '2021-09' style sort key."""
    s = str(label).strip()
    m = re.match(r"([A-Za-z]{3,4})[\s-]?(\d{2})$", s)
    if not m:
        return "9999-" + s
    mm = _MONTHS.get(m.group(1).lower())
    if not mm:
        return "9999-" + s
    yy = int(m.group(2))
    yy += 2000 if yy < 70 else 1900
    return f"{yy:04d}-{mm:02d}"


def period_sort(label):
    return period_key(label)


def chart_series_from_panel(panel):
    """The 2026 LONG-format tables also describe a SPOT benchmark, so they share the
    'spot' family rather than a separate 'tce' label."""
    return "1y_tc" if ("1y" in canon(panel) or "3y" in canon(panel)) else "spot"


def canon(panel):
    p = str(panel).strip()
    return CANON.get(p, CANON.get(p.title(), p))


rows = []
for path, year in sorted(ANNUAL.items()):
    tabs = json.load(open(path, encoding="utf-8"))
    rdate = report_date(path)
    for t in tabs:
        if not t:
            continue
        hdr = [str(c).strip() for c in t[0]]
        first = hdr[0].lower()
        # A table is WIDE when every column after the first is a NAMED SERIES (a header
        # cell, not a number). It is LONG when it carries an explicit 'Panel' column.
        #
        # 2021 is the trap: it labels its date column 'Date' (not 'Month') and is WIDE -
        # Date | VLCC (TD3C) | SUEZMAX (TD20) | AFRAMAX (TD7). Branching on the first
        # cell alone sent it down the LONG path, where the missing 'Panel' header made
        # the code read column 1 as the panel name, inventing series called '-10000',
        # '0' and '250000'. 2026 is the genuinely LONG one (Date | Panel | TCE | ...).
        is_long = any(h.lower() == "panel" for h in hdr)
        if first.startswith("month") or (first.startswith("date") and not is_long):
            # wide: one series per data column
            for ci in range(1, len(hdr)):
                panel = hdr[ci]
                if not panel or panel.lower() in ("month", "date", "panel"):
                    continue
                # a header cell, not a spilled value
                if re.fullmatch(r"-?[\d,.]+", panel):
                    continue
                # chart family: a PERIOD (1y/3y TC) versus a SPOT benchmark. Derived
                # from the panel name after canonicalisation, because the raw label
                # varies by era and tagging by the pre-canonical text produced four
                # different values for the same series across years.
                pcanon = canon(panel)
                chart = "1y_tc" if "1y" in pcanon or "3y" in pcanon else "spot"
                for r in t[1:]:
                    if not r or not r[0]:
                        continue
                    v = to_usd(r[ci] if ci < len(r) else None)
                    if v == "":
                        continue
                    rows.append({
                        "report_date": rdate, "report_year": year,
                        "chart_series": chart, "panel": canon(panel),
                        "period_label": str(r[0]).strip(), "value_usd_per_day": v,
                        "source_file": os.path.basename(path),
                    })
        elif is_long:
            # long: one row per (date, panel). The Date cell is a MERGED cell, so it is
            # populated only on the first row of each date group and BLANK on the
            # continuation rows. A blank date means "same date as the row above" - it
            # does NOT mean the row is junk. Getting this wrong produced series named
            # after numbers (-10000, 0, 250000), because the panel index slid when the
            # empty first cell was skipped.
            pi = hdr.index("Panel") if "Panel" in hdr else 1
            last_date = ""
            for r in t[1:]:
                if not r or len(r) < 3:
                    continue
                if r[0] and str(r[0]).strip():
                    last_date = str(r[0]).strip()
                panel = str(r[pi]).strip()
                v = to_usd(r[pi + 1])
                if v == "" or not last_date:
                    continue
                rows.append({
                    "report_date": rdate, "report_year": year,
                    "chart_series": chart_series_from_panel(panel),
                    "panel": canon(panel),
                    "period_label": last_date, "value_usd_per_day": v,
                    "source_file": os.path.basename(path),
                })

# mark superseded rows: same (chart_series, panel, period_label) from a later report
latest = {}
for r in rows:
    k = (r["chart_series"], r["panel"], r["period_label"])
    if k not in latest or r["report_date"] > latest[k]["report_date"]:
        latest[k] = r
for r in rows:
    k = (r["chart_series"], r["panel"], r["period_label"])
    r["is_latest"] = "1" if latest[k] is r else "0"

rows.sort(key=lambda r: (r["chart_series"], r["panel"], period_sort(r["period_label"]),
                         r["report_date"]))
OUT.mkdir(parents=True, exist_ok=True)
dest = OUT / "xclusiv_chart_series.csv"
with open(dest, "w", newline="", encoding="utf-8") as f:
    for r in rows:
        r["period"] = period_key(r["period_label"])
    w = csv.DictWriter(f, fieldnames=["period", "report_date", "report_year",
                                       "chart_series", "panel", "period_label",
                                       "value_usd_per_day", "is_latest",
                                       "source_file"])
    w.writeheader()
    w.writerows(rows)

series = collections.Counter((r["chart_series"], r["panel"]) for r in rows)
print(f"wrote {dest.relative_to(ROOT)}")
print(f"  rows              : {len(rows)}")
print(f"  named series      : {len(series)}")
print(f"  rows marked latest: {sum(1 for r in rows if r['is_latest']=='1')}")
print()
print("series inventory:")
for (cs, panel), n in sorted(series.items()):
    print(f"  {cs:<12} {panel:<34} {n:>3} points")
