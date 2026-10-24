"""Agora "Snapshot of Commercial Indicators": stack each issue's tables into agora_indicators_series.csv.

The series was extended by an untracked scratch script with hardcoded weeks, so issues ingested by CI after
2026-09-25 reached the MD and sidecar but never the series. Rows are built from the `.tables.json` sidecar that
run_agora writes for every issue (historical and CI), with the row rule of that scratch builder:

  * issue_date = the Friday of the report's ISO week (212/213 shipped dates are a Friday; report_week equals
    the ISO week of the date on every row);
  * one row per table row on the data pages; values are the sidecar's typed values, as written.

--check rebuilds every issue already in the series and compares it row for row (the control); --new-only
appends issues whose week is not in the series yet and never rewrites existing rows.

    python scripts/extract/publishers/agora_series.py --check
    python scripts/extract/publishers/agora_series.py --new-only
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MD_DIR = ROOT / "data" / "extracted" / "md" / "agora"
CSV = ROOT / "data" / "extracted" / "series" / "agora_indicators_series.csv"

VALCOLS = ["% 4-weekly", "Actual last", "% weekly", "IFO380", "VLSFO", "MGO"]
HDR = (["issue_date", "report_week", "section", "label", "name", "period", "source_file"]
       + ["val_" + c for c in VALCOLS])


def front(md: Path) -> dict[str, str]:
    head = md.read_text(encoding="utf-8", errors="ignore")[:3000]
    m = re.match(r"---\n(.*?)\n---", head.replace("\r\n", "\n"), re.S)
    out = {}
    for ln in (m.group(1).splitlines() if m else []):
        k, _, v = ln.partition(":")
        out[k.strip()] = v.strip().strip('"')
    return out


def issue_of(md: Path) -> tuple[str, int] | None:
    """(Friday of the report's ISO week, week) from the frontmatter's year and report_week."""
    fm = front(md)
    try:
        wk = int(fm["report_week"])
        yr = int(fm.get("year") or fm["issue_date"][:4])
        return dt.date.fromisocalendar(yr, wk, 5).isoformat(), wk
    except (KeyError, ValueError):
        return None


def rows_for(md: Path, issue_date: str, week: int, source_rel: str) -> list[list[str]]:
    side = json.loads(md.with_suffix(".tables.json").read_text(encoding="utf-8"))
    out = []
    # run_agora writes {"sections": {page: ...}}; the CI ingest writes {"tables": {"page_N": ...}}, same rows
    for _, sections in (side.get("sections") or side.get("tables") or {}).items():
        for name, sec in sections.items():
            for row in sec["rows"]:
                vals = row.get("values") or {}
                out.append([issue_date, str(week), name, row.get("label", ""), row.get("name", ""),
                            row.get("period") or "", source_rel]
                           + ["" if vals.get(c) is None else str(vals[c]) for c in VALCOLS])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="rebuild issues already in the series and compare")
    g.add_argument("--new-only", action="store_true", help="append issues not in the series yet")
    a = ap.parse_args(argv)

    raw = CSV.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    with open(CSV, encoding="utf-8-sig", newline="") as fh:
        rd = csv.reader(fh)
        hdr = next(rd)
        pre = [x for x in rd if x]
    assert hdr == HDR, "series header drift"
    by_date: dict[str, list[list[str]]] = {}
    for x in pre:
        by_date.setdefault(x[0], []).append(x)
    stems = {Path(x[6]).stem for x in pre}

    added, ok, bad, skipped = [], 0, [], []
    for md in sorted(MD_DIR.rglob("*.md")):
        if not md.with_suffix(".tables.json").is_file():
            continue
        iss = issue_of(md)
        if iss is None:
            skipped.append(f"{md.name}: no report_week/year in frontmatter")
            continue
        d, wk = iss
        if d in by_date:
            if a.check:
                src = by_date[d][0][6]
                got = rows_for(md, d, wk, src)
                if sorted(got) == sorted(by_date[d]):
                    ok += 1
                elif Path(src).stem == Path(front(md).get("source_file", "")).stem or len(by_date[d]) == len(got):
                    bad.append((d, md.name, len(got), len(by_date[d])))
            continue
        src = front(md).get("source_file", "")
        if Path(src).stem in stems:
            skipped.append(f"{md.name}: its PDF is already in the series under another date")
            continue
        got = rows_for(md, d, wk, src)
        if not got:
            skipped.append(f"{md.name}: sidecar has no table rows")
            continue
        added.extend(got)
        by_date[d] = got
        print(f"  + {d} W{wk}: {len(got)} rows <- {md.name}")

    for s in skipped:
        print("  skip", s)
    if a.check:
        print(f"control: {ok} issues identical, {len(bad)} differ")
        for b in bad[:20]:
            print("   differs", b)
        return 1 if bad else 0
    if added:
        with open(CSV, "a", encoding="utf-8", newline="") as fh:
            if not raw.endswith(b"\n"):
                fh.write(nl)
            csv.writer(fh, lineterminator=nl).writerows(added)
    print(f"agora_indicators_series: +{len(added)} rows ({len(pre)} kept)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
