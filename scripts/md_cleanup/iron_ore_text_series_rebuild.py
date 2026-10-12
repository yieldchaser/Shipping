"""Rebuild the MMi rows of two iron ore series from the PDF text layer.

  data/extracted/series/hellenic_iron_ore_pdf_futures_series.csv
      the MMi rows had no price (blanked by the SMM runner's upsert, see
      docs/iron_ore_two_writer_verdict.md) and "change" held the open-positions change
  data/extracted/series/hellenic_iron_ore_pdf_port_inventories_series.csv
      Tianjin and Rizhao were missing for ~410 issues

One row per issue date and exchange / port, read by scripts/extract/publishers/mmi_text_tables.py
from the PDF each iron ore MD names (twins of one date: the last path wins, as before). Rows that
do not come from an MMi PDF (the SMM runner's) are kept as they are. Existing columns keep their
names and meaning; the futures file gains the other printed columns at the end.

    python scripts/md_cleanup/iron_ore_text_series_rebuild.py [--apply]
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.extract.publishers.mmi_text_tables import read_futures, read_port_inventories  # noqa: E402
from scripts.md_cleanup.iron_ore_text_tables_patch import pdf_for  # noqa: E402

SERIES = ROOT / "data" / "extracted" / "series"
FUT = SERIES / "hellenic_iron_ore_pdf_futures_series.csv"
INV = SERIES / "hellenic_iron_ore_pdf_port_inventories_series.csv"
FUT_EXTRA = ["closing_date", "vol_traded_k_lots", "vol_change", "vol_change_pct", "open_positions_k_lots",
             "open_positions_change", "open_positions_change_pct", "day_low", "day_low_change",
             "day_low_change_pct", "day_high", "day_high_change", "day_high_change_pct", "holiday", "value_source"]
INV_EXTRA = ["week_ending", "value_source"]


def f(x):
    """Printed number -> the series' plain float text ('1,017.50' -> '1017.5', '-2.50%' -> '-2.5');
    a cell the print leaves blank -> ''."""
    return "" if x is None else str(float(str(x).replace(",", "").replace("%", "")))


def main():
    apply = "--apply" in sys.argv
    out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z", "data/extracted/md/hellenic/iron_ore_pdf"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    mds = sorted(p for p in out.split("\0") if p.endswith(".md"))
    fut, inv, miss = {}, {}, {"futures": 0, "ports": 0, "pdf": 0}
    for n, rel in enumerate(mds, 1):
        md = (ROOT / rel).read_bytes().decode("utf-8")
        if "### Iron Ore Benchmark Price Indices" not in md:
            continue
        pdf = pdf_for(md)
        if pdf is None:
            miss["pdf"] += 1
            continue
        date = re.search(r'^issue_date:\s*"?([\d-]+)', md, re.M).group(1)
        doc = pymupdf.open(pdf)
        fu = read_futures(doc)
        if fu:
            for i, col in enumerate(fu["columns"]):
                v = {r["metric"]: r["cells"][3 * i:3 * i + 3] for r in fu["rows"]}
                cp, vol, oi = v["Closing Price"], v["Vol traded ('000 lots)"], v["Open positions ('000 lots)"]
                lo, hi = v["Day Low"], v["Day High"]
                fut[(date, col["exchange"])] = {
                    "date": date, "year": date[:4], "exchange": col["exchange"], "contract": col["contract"],
                    "price": f(cp[0]), "unit": col["unit"], "change": f(cp[1]), "change_pct": f(cp[2]),
                    "settlement": "", "source_file": pdf.name, "closing_date": col["closing_date"],
                    "vol_traded_k_lots": f(vol[0]), "vol_change": f(vol[1]), "vol_change_pct": f(vol[2]),
                    "open_positions_k_lots": f(oi[0]), "open_positions_change": f(oi[1]),
                    "open_positions_change_pct": f(oi[2]), "day_low": f(lo[0]), "day_low_change": f(lo[1]),
                    "day_low_change_pct": f(lo[2]), "day_high": f(hi[0]), "day_high_change": f(hi[1]),
                    "day_high_change_pct": f(hi[2]), "holiday": "yes" if col.get("holiday") else "",
                    "value_source": "pdf_text"}
        else:
            miss["futures"] += 1
        pi = read_port_inventories(doc)
        if pi:
            for r in pi["rows"]:
                inv[(date, r["terminal"])] = {
                    "date": date, "year": date[:4], "terminal": r["terminal"], "inventory_mt": f(r["inventory_mt"]),
                    "change_pct": f(r["change_pct"]), "low_12m": f(r["low_12m"]), "high_12m": f(r["high_12m"]),
                    "source_file": pdf.name, "week_ending": (pi["week_ending"] or "").replace("Week ending ", ""),
                    "value_source": "pdf_text"}
        else:
            miss["ports"] += 1
        if n % 200 == 0:
            print(n, len(fut), len(inv), miss, flush=True)
    for path, rows, extra, key in ((FUT, fut, FUT_EXTRA, ("date", "exchange")), (INV, inv, INV_EXTRA, ("date", "terminal"))):
        with open(path, encoding="utf-8", newline="") as fh:
            rd = csv.DictReader(fh)
            head = list(rd.fieldnames)
            old = list(rd)
        mmi_dates = {k[0] for k in rows}
        # keep: rows not from an MMi PDF, and MMi rows of dates this run could not read
        # (a row with neither a date nor a source file cannot be placed; the SMM runner wrote two)
        keep = [r for r in old if (r["date"] or r["source_file"])
                and (not r["source_file"].lower().endswith(".pdf") or r["date"] not in mmi_dates)]
        fields = head + [c for c in extra if c not in head]
        new = keep + list(rows.values())
        new.sort(key=lambda r: tuple(str(r.get(k, "")) for k in key))
        print(f"{path.name}: {len(old)} rows -> {len(new)} ({len(rows)} from the PDFs, {len(keep)} kept)")
        if apply:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
                w.writeheader()
                w.writerows(new)
    print("not read:", miss, "(applied)" if apply else "(dry run)")


if __name__ == "__main__":
    main()
