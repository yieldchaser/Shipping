#!/usr/bin/env python3
"""
Backfill data/commodities/usda_ytd_grain_inspections_top20.csv from USDA FGIS raw
certificate files (https://fgisonline.ams.usda.gov/ExportGrainReport/CY{year}.csv).

Why: the agtransport Socrata dataset (5sxb-qe7q) only starts 2025-01-02 and itself has no
weeks between 2025-09-11 and 2025-12-31. FGIS raw files have every week.
Validated: FGIS aggregates reproduce Socrata monthly Gulf totals to 0.01 Mt and the
2026-09-10 week to 1 tonne per region.

Only weeks absent from the existing CSV are appended (existing rows are never touched).
"""
import io
import logging
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "commodities" / "usda_ytd_grain_inspections_top20.csv"
FGIS = "https://fgisonline.ams.usda.gov/ExportGrainReport/CY{y}.csv"
LB_PER_MT = 2204.62262


def load_year(y):
    logging.info("Downloading FGIS export grain report for CY%d...", y)
    raw = urllib.request.urlopen(urllib.request.Request(FGIS.format(y=y), headers={"User-Agent": "Mozilla/5.0"}), timeout=180).read()
    d = pd.read_csv(io.BytesIO(raw), low_memory=False, encoding="latin1")
    d.columns = [c.strip() for c in d.columns]
    return d


def to_repo_schema(f):
    date = pd.to_datetime(f["Thursday"].astype(str), format="%Y%m%d")
    cert = pd.to_datetime(f["Cert Date"].astype(str), format="%Y%m%d", errors="coerce")
    wk = date.dt.isocalendar().week.astype(int) - 1          # matches USDA 'week' numbering
    s = lambda c: f[c].astype(str).str.strip().replace({"nan": ""})
    out = pd.DataFrame({
        "date": date.dt.strftime("%Y-%m-%dT00:00:00.000"),
        "grain": s("Grain"),
        "class": s("Class"),
        "subclass": s("SubClass"),
        "destination": s("Destination"),
        "ams_reg": s("AMS Reg"),
        "mt": (pd.to_numeric(f["Pounds"], errors="coerce") / LB_PER_MT).round().astype("Int64"),
        "week": wk.where(wk > 0, 53),
        "month": cert.dt.month.fillna(date.dt.month).astype(int),
        "year": date.dt.year,
    })
    return out[out["mt"] > 0]


def main(years):
    if not OUT.exists():
        logging.error("Target file does not exist: %s", OUT)
        return
    cur = pd.read_csv(OUT)
    have = set(pd.to_datetime(cur["date"]).dt.normalize())
    add = []
    for y in years:
        try:
            f = to_repo_schema(load_year(y))
            f = f[~pd.to_datetime(f["date"]).dt.normalize().isin(have)]
            logging.info("[fgis] CY%d: %d missing weeks, %d rows to append", y, f["date"].nunique(), len(f))
            if not f.empty:
                add.append(f)
        except Exception as e:
            logging.error("Failed loading FGIS CY%d: %s", y, e)

    if not add:
        logging.info("[fgis] No new weeks to append; CSV is up to date.")
        return

    new = pd.concat([cur] + add, ignore_index=True).sort_values("date", ascending=False)
    new.to_csv(OUT, index=False, lineterminator="\n")
    logging.info("[fgis] wrote %d total rows -> %s", len(new), OUT)


if __name__ == "__main__":
    years = [int(a) for a in sys.argv[1:] if a.isdigit()]
    if not years:
        # Default to current and previous year
        now_y = datetime.now().year
        years = [now_y - 1, now_y]
    main(years)
