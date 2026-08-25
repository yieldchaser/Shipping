#!/usr/bin/env python3
"""
Australia DISR Resources and Energy Quarterly (REQ) — REAL quarterly export volumes/values.

Authoritative source: DISR "Resources and Energy Quarterly" Historical Tables XLSX
(sheet 16 = quarterly export VOLUMES, sheet 17 = quarterly export VALUES $m).
Published by the Office of the Chief Economist.

Acquisition order (data-provenance policy):
  1. Live industry.gov.au URL (may be geo/bot-walled in some environments).
  2. Internet Archive Wayback mirror of the same published artifact.
  3. Local cached copy (scratch/req_jun2026_hist.xlsx) if present.
If every route fails -> exit loudly; NO editorial estimates are written.

Parsed commodities -> frontend schema (data/commodities/australia_req_commodity_exports.csv):
    Iron Ore, Metallurgical Coal, Thermal Coal, Bauxite, LNG
Volumes converted to Mt; values converted to A$ billion.
primary_vessel_class is a static factual descriptor of the dominant carrier class
(industry fact, not a measured series).
"""
import logging
import os
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "commodities"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / "australia_req_commodity_exports.csv"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# June-2026 edition (published Jul-2026; quarterly data through Mar-2026 actuals).
EDITIONS = [
    {
        "tag": "jun2026",
        "urls": [
            "https://www.industry.gov.au/sites/default/files/2026-07/resources-and-energy-quarterly-jun-2026-historical-data.xlsx",
            "https://www.industry.gov.au/sites/default/files/2026-07/resources-and-energy-quarterly-june-2026-historical-data.xlsx",
            "https://web.archive.org/web/20260727061548if_/https://www.industry.gov.au/sites/default/files/2026-07/resources-and-energy-quarterly-june-2026-historical-data.xlsx",
        ],
        "cache": ROOT / "scratch" / "req_jun2026_hist.xlsx",
    },
]

VOLUME_SHEET = "16"
VALUE_SHEET = "17"
HEADER_ROW = 6          # row holding quarter-end datetimes ('unit' sits beside them)
FIRST_DATA_COL = 7      # first quarter column in sheet 16 (sheet 17 shifts by -1)

# label prefix in col 5 -> canonical commodity name (+ its dominant carrier class, factual)
TARGETS = [
    {"label_prefix": "Bauxite",       "commodity": "Bauxite",             "vessel": "Capesize / Ultramax"},
    {"label_prefix": "Iron ore",      "commodity": "Iron Ore",            "vessel": "Capesize (C5/C3)"},
    {"label_prefix": "Metallurgical", "commodity": "Metallurgical Coal",  "vessel": "Panamax / Capesize"},
    {"label_prefix": "Thermal",       "commodity": "Thermal Coal",        "vessel": "Panamax / Supramax"},
    {"label_prefix": "LNG",           "commodity": "LNG",                 "vessel": "LNG Carrier (174k)"},
]


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120, context=_CTX) as r:
            raw = r.read()
        if len(raw) < 100_000:  # xlsx is ~3.6MB; anything smaller is an error page
            logging.warning("Suspiciously small payload (%d bytes) from %s", len(raw), url[:80])
            return False
        dest.write_bytes(raw)
        return True
    except Exception as e:  # noqa: BLE001
        logging.warning("Fetch failed %s: %s", url[:90], e)
        return False


def _acquire_workbook() -> tuple[Path, str]:
    """Return (local_path, source_tag); raises if nothing obtainable."""
    tmp = ROOT / "scratch" / "req_live.xlsx"
    tmp.parent.mkdir(exist_ok=True)
    for ed in EDITIONS:
        if ed["cache"].exists() and ed["cache"].stat().st_size > 100_000:
            return ed["cache"], f"{ed['tag']}+cache"
        for i, u in enumerate(ed["urls"]):
            tag = f"{ed['tag']}+{'wayback' if 'web.archive.org' in u else 'live'}"
            if _download(u, tmp):
                return tmp, tag
            _ = i  # noqa
    raise SystemExit("REQ historical workbook unobtainable (live + archive + cache all failed). "
                     "NO data written — investigate network or update EDITIONS.")


def _find_row(df: pd.DataFrame, label_prefix: str, col: int = 5, start: int = 7) -> int | None:
    for i in range(start, len(df)):
        v = df.iloc[i, col]
        if pd.notna(v) and str(v).strip().startswith(label_prefix):
            return i
    return None


def _header_dates(df: pd.DataFrame, header_row: int, first_col: int) -> list[tuple[int, datetime]]:
    out = []
    for j in range(first_col, df.shape[1]):
        v = df.iloc[header_row, j]
        if isinstance(v, datetime):
            out.append((j, v))
    return out


def parse_workbook(xlsx_path: Path, tag: str) -> pd.DataFrame:
    xl = pd.ExcelFile(xlsx_path)

    vol = xl.parse(VOLUME_SHEET, header=None)
    val = None
    if VALUE_SHEET in xl.sheet_names:
        val = xl.parse(VALUE_SHEET, header=None)

    dates_vol = _header_dates(vol, HEADER_ROW, FIRST_DATA_COL)
    if len(dates_vol) < 20:
        raise SystemExit(f"Unexpected sheet {VOLUME_SHEET} layout: only {len(dates_vol)} quarter columns found")

    # sheet 17 header: labels in col 5, values start col 6 (one left of sheet 16)
    dates_val = _header_dates(val, HEADER_ROW, FIRST_DATA_COL - 1) if val is not None else []

    def value_lookup(commodity_label_prefixes: list[str]) -> dict[datetime, float]:
        """Map quarter-end -> $m value from sheet 17 for the matching row."""
        out: dict[datetime, float] = {}
        if val is None:
            return out
        for pref in commodity_label_prefixes:
            r = _find_row(val, pref)
            if r is None:
                continue
            for j, d in dates_val:
                v = val.iloc[r, j]
                if pd.notna(v):
                    try:
                        out[d] = float(v)
                    except (TypeError, ValueError):
                        pass
                    break_flag = True
            if out:
                break
        return out

    rows = []
    for t in TARGETS:
        r_vol = _find_row(vol, t["label_prefix"])
        if r_vol is None:
            logging.warning("Row '%s' not found in sheet %s — skipped", t["label_prefix"], VOLUME_SHEET)
            continue
        unit = str(vol.iloc[r_vol, FIRST_DATA_COL - 1]).strip().lower() if pd.notna(vol.iloc[r_vol, FIRST_DATA_COL - 1]) else ""
        div = 1000.0 if unit.startswith("kt") else 1.0  # kt -> Mt ; Mt stays
        vals = {}
        for j, d in dates_vol:
            v = vol.iloc[r_vol, j]
            if pd.notna(v):
                try:
                    vals[d] = float(v) / div
                except (TypeError, ValueError):
                    pass
        # value rows use slightly different label text; try both prefixes
        val_pref = {"Iron Ore": ["Iron ore"], "Bauxite": ["Bauxite"],
                    "Metallurgical Coal": ["Metallurgical"], "Thermal Coal": ["Thermal"],
                    "LNG": ["LNG"]}[t["commodity"]]
        vmap = value_lookup(val_pref)

        for d, mt in sorted(vals.items()):
            q = f"{d.year} Q{(d.month - 1)//3 + 1}"
            aud_b = round(vmap[d] / 1000.0, 3) if d in vmap else ""
            rows.append({
                "date": d.strftime("%Y-%m-%d"),
                "quarter": q,
                "commodity": t["commodity"],
                "export_volume_mt": round(mt, 3),
                "export_value_aud_b": aud_b,
                "primary_vessel_class": t["vessel"],
                "provenance": f"live_disr_{tag}",
            })

    df = pd.DataFrame(rows).drop_duplicates(subset=["date", "commodity"]) \
        .sort_values(["date", "commodity"]).reset_index(drop=True)
    if df.empty:
        raise SystemExit("Parsed zero rows from REQ workbook — layout changed? NO data written.")
    return df


def main() -> pd.DataFrame:
    path, tag = _acquire_workbook()
    logging.info("Parsing %s (%s)", path.name, tag)
    df = parse_workbook(path, tag)
    df.to_csv(OUT_FILE, index=False)
    span = f"{df['date'].min()} .. {df['date'].max()}"
    logging.info("Wrote %d REAL DISR rows (%s) -> %s", len(df), span, OUT_FILE.name)
    for c in sorted(df["commodity"].unique()):
        sub = df[df["commodity"] == c]
        last = sub.iloc[-1]
        logging.info("  %-20s last: %s  %s Mt", c, last["quarter"], last["export_volume_mt"])
    return df


if __name__ == "__main__":
    main()
