"""Lion Shipbrokers weekly: stack each issue's demometer into lion_demolition_series.csv (append-only).

The series was built once from the .tables.json sidecars; issues ingested by CI afterwards reached the MD but
never the series. This reads the sidecar "demometer" block of every issue with the same row rules (country
upper-case, trend lower-case, value_kind single / range, issue = the MD stem). CI-named sidecars
(lion_DD_MM_YYYY_..._week_NN_YYYY) carry no issue date or week, so those come from the file name.

    python scripts/extract/publishers/lion_series.py --check
    python scripts/extract/publishers/lion_series.py --new-only
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MD = ROOT / "data" / "extracted" / "md" / "lion"
CSV = ROOT / "data" / "extracted" / "series" / "lion_demolition_series.csv"


def issue_of(side: Path, d: dict) -> tuple[str, int] | None:
    date, week = d.get("issue_date"), d.get("report_week")
    m = re.match(r"lion_(\d\d)_(\d\d)_(\d{4})_.*_week_(\d+)_\d{4}$", side.name.removesuffix(".tables.json"))
    if m and not (date and week):
        date, week = f"{m.group(3)}-{m.group(2)}-{m.group(1)}", int(m.group(4))
    w = re.search(r"-W(\d\d?)\.tables\.json$", side.name)       # the file name's week wins (W08 sidecar says 7)
    if w:
        week = int(w.group(1))
    return (date, int(week)) if date and week else None


def build(side: Path) -> tuple[str, list[list[str]]] | None:
    d = json.loads(side.read_text(encoding="utf-8"))
    iss = issue_of(side, d)
    if not iss:
        return None
    date, week = iss
    stem = side.name.removesuffix(".tables.json")
    rows = []
    for r in (d.get("tables") or {}).get("demometer") or []:
        lo, hi, pt = r.get("price_low"), r.get("price_high"), r.get("price_point")
        if pt is None:
            continue
        rows.append([date, str(week), str(r.get("country", "")).upper(), r.get("vessel_type", ""), str(float(lo)),
                     str(float(hi)), str(float(pt)), str(r.get("trend", "")).lower(), r.get("unit", ""),
                     "single" if lo == hi else "range", stem])
    return date, rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="rebuild issues already in the series and compare")
    g.add_argument("--new-only", action="store_true", help="append issues not in the series yet")
    a = ap.parse_args(argv)
    raw = CSV.read_bytes()
    body = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))[1:]
    have: dict[str, list[list[str]]] = {}
    for r in body:
        if r:
            have.setdefault(r[0], []).append(r)
    ok, diff, added = 0, [], []
    for side in sorted(MD.rglob("*.tables.json")):
        b = build(side)
        if not b or not b[1]:
            continue
        date, rows = b
        if date in have:
            if sorted(rows) == sorted(have[date]):
                ok += 1
            else:
                diff.append((side.name, len(rows), len(have[date])))
        elif a.new_only and date not in {r[0] for r in added}:
            added.extend(rows)
            print(f"  + {date} W{rows[0][1]} {len(rows)} rows <- {side.name}")
    if a.check:
        print(f"lion_demolition: {ok} issues identical, {len(diff)} differ")
        for x in diff[:10]:
            print("   differs", x)
        return 1 if diff else 0
    if added:
        nl = "\r\n" if raw.split(b"\n", 1)[0].endswith(b"\r") else "\n"
        with open(CSV, "a", encoding="utf-8", newline="") as fh:
            if not raw.endswith(b"\n"):
                fh.write(nl)
            csv.writer(fh, lineterminator=nl).writerows(added)
    print(f"lion_demolition: +{len(added)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
