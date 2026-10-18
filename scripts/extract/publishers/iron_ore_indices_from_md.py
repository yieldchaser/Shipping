"""Rebuild data/extracted/series/hellenic_iron_ore_pdf_indices_series.csv from the iron ore MDs.

The MD benchmark table ("## MMi Detailed Iron Ore Benchmark Assessments") is the corrected record: its
numbers are rebuilt from the PDF text layer by scripts/md_cleanup/iron_ore_text_tables_patch.py. The
*.tables.json sidecars the MMi runner used to stack this file from are gitignored and hold the
pre-correction numbers, so the series is derived from the MDs instead.

Rows written by run_smm_iron_ore_daily.py (the SMM-format daily, market_type set) are kept as they are.
One schema for both writers:

    date,year,index_name,market,market_type,fe_content,unit,price,change,change_pct,mtd,ytd,low_52w,high_52w,source_file

A cell under the print's HOLIDAY box is empty; a row with no printed number at all is not written.

    python scripts/extract/publishers/iron_ore_indices_from_md.py [--check]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MD_DIR = ROOT / "data/extracted/md/hellenic/iron_ore_pdf"
CSV_PATH = ROOT / "data/extracted/series/hellenic_iron_ore_pdf_indices_series.csv"
HEADING = "## MMi Detailed Iron Ore Benchmark Assessments"
FIELDS = ["date", "year", "index_name", "market", "market_type", "fe_content", "unit", "price", "change",
          "change_pct", "mtd", "ytd", "low_52w", "high_52w", "source_file"]
NUMS = ["price", "change", "change_pct", "mtd", "ytd", "low_52w", "high_52w"]


def _num(cell: str) -> str:
    s = cell.strip().replace(",", "").rstrip("%")
    if not re.fullmatch(r"[+-]?\d+(\.\d+)?", s):
        return ""
    return s.lstrip("+")


def md_rows(md: Path) -> list[dict]:
    text = md.read_text(encoding="utf-8")
    date = re.search(r'^issue_date:\s*"?(\d{4}-\d{2}-\d{2})', text, re.M)
    src = re.search(r'^source_file:\s*"?([^"\n]+)', text, re.M)
    at = text.find(HEADING)
    if not date or at < 0:
        return []
    out = []
    for line in text[at:].split("\n")[3:]:
        if not line.startswith("|"):
            break
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) != 11:
            continue
        vals = dict(zip(NUMS, (_num(x) for x in c[4:])))
        if not any(vals.values()):
            continue
        out.append({"date": date.group(1), "year": date.group(1)[:4], "index_name": c[0].strip("*"),
                    "market": c[1], "market_type": "", "fe_content": c[2], "unit": c[3], **vals,
                    "source_file": Path(src.group(1)).name if src else ""})
    return out


def smm_rows() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    rows = []
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("market_type"):
                if not r.get("price") and r.get("value"):
                    r["price"] = r["value"]
                rows.append({k: r.get(k, "") for k in FIELDS})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report counts, write nothing")
    a = ap.parse_args()
    mmi = [r for md in sorted(MD_DIR.rglob("*.md")) for r in md_rows(md)]
    smm = smm_rows()
    keys = {(r["date"], r["index_name"]) for r in mmi}
    rows = mmi + [r for r in smm if (r["date"], r["index_name"]) not in keys]
    rows.sort(key=lambda r: (r["date"], r["index_name"]))
    print(f"{len(mmi)} MMi rows from {len({r['date'] for r in mmi})} issues, {len(smm)} SMM rows kept")
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
