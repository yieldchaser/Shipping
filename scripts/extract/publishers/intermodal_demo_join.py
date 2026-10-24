"""Intermodal weekly: join reported demolition sales that reached the sidecar after the series upsert.

The CI orchestrator upserts intermodal_demo_sales / intermodal_demolition from the sidecar it has just
written; intermodal_table_rebuild.py runs later in the same job and fills tables the parse left empty, among
them the reported-sales table (W42 2026: ASIA CEMENT NO. 3, FOTEX). Those rows never reached the series. This
appends the reported sales of every issue that has none in intermodal_demo_sales yet, to both series, with
the column sets of run_intermodal_full.py. Issues already in the series are never touched.

    python scripts/extract/publishers/intermodal_demo_join.py           # dry run: list what would be added
    python scripts/extract/publishers/intermodal_demo_join.py --apply
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_intermodal_full import DEMO_COLUMNS, DEMO_SALES_COLUMNS  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
MD = ROOT / "data" / "extracted" / "md" / "intermodal"
SER = ROOT / "data" / "extracted" / "series"


def append(path: Path, cols: list[str], rows: list[dict]) -> None:
    raw = path.read_bytes()
    nl = "\r\n" if raw.split(b"\n", 1)[0].endswith(b"\r") else "\n"
    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator=nl).writerows(
        [{c: ("" if r.get(c) is None else r.get(c)) for c in cols} for r in rows])
    with open(path, "a", encoding="utf-8", newline="") as fh:
        if not raw.endswith(b"\n"):
            fh.write(nl)
        fh.write(buf.getvalue())


def main(argv: list[str]) -> int:
    sales_csv, demo_csv = SER / "intermodal_demo_sales_series.csv", SER / "intermodal_demolition_series.csv"
    with open(sales_csv, encoding="utf-8-sig", newline="") as fh:
        have = {r["issue_date"] for r in csv.DictReader(fh)}
    add = []
    for side in sorted(MD.rglob("*.tables.json")):
        d = json.loads(side.read_text(encoding="utf-8"))
        tbls = d.get("tables") if isinstance(d, dict) else None
        sales = (tbls or {}).get("demolition_sales") if isinstance(tbls, dict) else None
        if sales and sales[0].get("issue_date") and sales[0]["issue_date"] not in have:
            add.extend(sales)
            have.add(sales[0]["issue_date"])
            print(f"  + {sales[0]['issue_date']} W{sales[0].get('report_week')}: {len(sales)} reported sales <- {side.name}")
    if add and "--apply" in argv:
        append(sales_csv, DEMO_SALES_COLUMNS, add)
        append(demo_csv, DEMO_COLUMNS, add)
    print(f"intermodal demo join: {len(add)} rows" + ("" if "--apply" in argv else " (dry run)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
