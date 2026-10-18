"""Rebuild data/extracted/series/hellenic_iron_ore_pdf_dashboard_series.csv from the iron ore MDs.

The MMi dashboard (page 1: index tiles, exchange contracts, freight, steel, inventories) is the
"## Executive Summary & Core Daily Indicators" section of each MD. Every number in it was checked
against the page-1 text layer (52,468 of 52,474; the one bad issue, 2022-01-31, was rebuilt by hand).
The MMi history was lost when the SMM writer rewrote this file in its own long schema, so it is
derived from the MDs here. Rows written by run_smm_iron_ore_daily.py (the SMM-format daily) are kept.

One long schema for both writers:

    date,year,indicator,contract,value,unit,change,change_pct,as_of,source_file

indicator is a stable name per tile (IOPI62, DCE iron ore front month, C3 freight, ...); contract is
the printed contract label for exchange tiles; as_of is the tile's own date line (freight and weekly
tiles lag the issue date). A HOLIDAY tile is not written.

    python scripts/extract/publishers/iron_ore_dashboard_from_md.py [--check]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MD_DIR = ROOT / "data/extracted/md/hellenic/iron_ore_pdf"
CSV_PATH = ROOT / "data/extracted/series/hellenic_iron_ore_pdf_dashboard_series.csv"
FIELDS = ["date", "year", "indicator", "contract", "value", "unit", "change", "change_pct", "as_of", "source_file"]
# (heading, column of value, change, change %, date/session) per dashboard table
TABLES = {
    "### Iron Ore Benchmark Price Indices": (4, 5, 6, 7),
    "### Exchange Traded Futures & Derivatives": (3, 4, 5, 6),
    "### Dry Bulk Freight Rates, Spot Steel & Inventories": (2, 3, 4, 5),
}
EXCHANGE = {"DCE": "DCE iron ore 62% front month", "SGX": "SGX iron ore 62% front month",
            "SHFE": "SHFE rebar front month"}
OTHER = {"C3 Freight": "C3 freight Tubarao-Qingdao", "C5 Freight": "C5 freight W Australia-Qingdao",
         "Steel Rebar": "China steel rebar", "Steel HRC": "China steel HRC",
         "Port Iron Ore Inventory": "Iron ore inventory 35 China ports",
         "Steel Inventory": "China steel inventory", "Total Steel Inventory": "China steel inventory"}


def _num(s: str) -> str:
    s = s.replace(",", "").replace("%", "").strip().split(" ")[0]
    return s.lstrip("+") if re.fullmatch(r"[+-]?\d+(\.\d+)?", s) else ""


def _rows(text: str, head: str) -> list[list[str]]:
    at = text.find(head)
    if at < 0:
        return []
    out = []
    for line in text[at:].split("\n")[3:]:
        if not line.startswith("|"):
            break
        out.append([c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")])
    return out


def md_rows(md: Path) -> list[dict]:
    text = md.read_text(encoding="utf-8")
    date = re.search(r'^issue_date:\s*"?(\d{4}-\d{2}-\d{2})', text, re.M)
    src = re.search(r'^source_file:\s*"?([^"\n]+)', text, re.M)
    if not date:
        return []
    out = []
    for head, (vi, ci, pi, di) in TABLES.items():
        for r in _rows(text, head):
            if len(r) <= di:
                continue
            value = _num(r[vi])
            if not value:
                continue
            contract, unit = "", ""
            if head.startswith("### Iron Ore Benchmark"):
                indicator = {"IOPLI": "IOPLI62"}.get(r[0], r[0])
                unit = r[3]
            elif head.startswith("### Exchange"):
                indicator = EXCHANGE.get(r[1], r[0])
                contract, unit = r[0], r[2]
            else:
                indicator = OTHER.get(r[0], r[0])
                unit = " ".join(r[vi].split(" ")[1:])
            out.append({"date": date.group(1), "year": date.group(1)[:4], "indicator": indicator,
                        "contract": contract, "value": value, "unit": unit, "change": _num(r[ci]),
                        "change_pct": _num(r[pi]), "as_of": r[di],
                        "source_file": Path(src.group(1)).name if src else ""})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report counts, write nothing")
    a = ap.parse_args()
    mmi = [r for md in sorted(MD_DIR.rglob("*.md")) for r in md_rows(md)]
    dates = {r["date"] for r in mmi}
    kept = []
    if CSV_PATH.exists():
        with open(CSV_PATH, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("date") and r["date"] not in dates:   # SMM-format issues
                    kept.append({k: r.get(k, "") for k in FIELDS})
    rows = sorted(mmi + kept, key=lambda r: (r["date"], r["indicator"]))
    print(f"{len(mmi)} MMi rows from {len(dates)} issues, {len(kept)} SMM rows kept")
    if a.check:
        return 0
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {CSV_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
