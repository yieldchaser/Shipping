"""Rebuild the three MMi iron ore CHART series from the (patched) MD tables, labelled by how each value was read.

  hellenic_iron_ore_pdf_freight_rates_series.csv      <- ## Dry Bulk Freight Rates Historical Line Data (USD/MT)
  hellenic_iron_ore_pdf_import_volumes_series.csv     <- ## Total China Iron Ore Import Volumes (Million Tonnes)
  hellenic_iron_ore_pdf_index_comparisons_series.csv  <- ## Historical Iron Ore Index Comparisons (USD/DMT)

The reports print no numbers for these charts. scripts/md_cleanup/iron_ore_vector_charts_patch.py replaced each table
with values computed from the chart's vector geometry where the chart reads cleanly ("Estimate" note) and labelled
the rest "Approximate" (values read visually by the original parser). This rebuild carries that label into a new
`value_source` column (vector_estimate | visual_estimate). Rows are replaced per source document; rows of documents
that have no MD here are kept as they are.

    python scripts/md_cleanup/iron_ore_chart_series_rebuild.py            # dry run
    python scripts/md_cleanup/iron_ore_chart_series_rebuild.py --apply
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERIES = ROOT / "data" / "extracted" / "series"
SPEC = {
    "freight": ("## Dry Bulk Freight Rates Historical Line Data (USD/MT)", "hellenic_iron_ore_pdf_freight_rates_series.csv",
                ["date", "year", "chart_date", "c5_waust_usd_t", "c3_tubarao_usd_t", "source_file", "value_source"]),
    "imports": ("## Total China Iron Ore Import Volumes (Million Tonnes)", "hellenic_iron_ore_pdf_import_volumes_series.csv",
                ["date", "year", "period", "volume_mt", "source_file", "value_source"]),
    "comparisons": ("## Historical Iron Ore Index Comparisons (USD/DMT)", "hellenic_iron_ore_pdf_index_comparisons_series.csv",
                    ["date", "year", "chart_date", "iosi62_usd_dmt", "iopi62_eq_usd_dmt", "iosi65_usd_dmt", "iopi65_eq_usd_dmt",
                     "source_file", "value_source"]),
}


def num(s: str) -> str:
    s = s.strip().replace(",", "")
    try:
        return repr(float(s)) if s not in ("", "-") else ""
    except ValueError:
        return ""


def section_rows(md: str, heading: str) -> tuple[list[list[str]], str] | None:
    i = md.find(heading)
    if i < 0:
        return None
    m = re.compile(r"[^\n]*\n(> \*\*(Estimate|Approximate)\.\*\*[^\n]*\n\n)?((?:\|[^\n]*\n)+)").match(md, i)
    if not m:
        return None
    label = {"Estimate": "vector_estimate", "Approximate": "visual_estimate"}.get(m.group(2) or "", "visual_estimate")
    rows = []
    for line in m.group(3).splitlines()[2:]:          # skip header + separator
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows, label


def main() -> int:
    apply = "--apply" in sys.argv
    out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z", "data/extracted/md/hellenic/iron_ore_pdf"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    mds = sorted(f for f in out.split("\0") if f.endswith(".md") and (ROOT / f).exists())
    new_rows = {k: [] for k in SPEC}
    covered: set[str] = set()
    stat = Counter()
    for rel in mds:
        md = (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")
        sf = re.search(r'^source_file:\s*"?([^"\n]+\.pdf)', md, re.M)
        issue = re.search(r'^issue_date:\s*"?(\d{4}-\d{2}-\d{2})', md, re.M)
        if not sf or not issue:
            stat["md without source_file/issue_date"] += 1
            continue
        src, date = Path(sf.group(1)).name, issue.group(1)
        covered.add(src)
        for key, (heading, _, cols) in SPEC.items():
            got = section_rows(md, heading)
            if not got:
                continue
            rows, label = got
            stat[f"{key}: {label} sections"] += 1
            for r in rows:
                if key == "imports" and len(r) >= 2:
                    new_rows[key].append([date, date[:4], r[0], num(r[1]), src, label])
                elif key == "freight" and len(r) >= 3:
                    new_rows[key].append([date, date[:4], r[0], num(r[1]), num(r[2]), src, label])
                elif key == "comparisons" and len(r) >= 5:
                    new_rows[key].append([date, date[:4], r[0], num(r[1]), num(r[2]), num(r[3]), num(r[4]), src, label])
    for key, (_, fname, cols) in SPEC.items():
        p = SERIES / fname
        with open(p, encoding="utf-8", newline="") as fh:
            old = list(csv.reader(fh))
        hdr, body = old[0], old[1:]
        si = hdr.index("source_file")
        kept = [r + [""] * (len(cols) - len(r)) if "value_source" not in hdr else r for r in body if r and r[si] not in covered]
        rows = sorted(kept + new_rows[key], key=lambda r: r[0])   # stable: chart order within an issue
        print(f"{fname}: {len(body)} rows -> {len(rows)} ({len(new_rows[key])} from MDs, {len(kept)} kept from documents without an MD)")
        if apply:
            with open(p, "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, lineterminator="\n")
                w.writerow(cols)
                w.writerows(rows)
    for k, v in sorted(stat.items()):
        print(f"{v:6}  {k}")
    print("APPLIED" if apply else "dry run (use --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
