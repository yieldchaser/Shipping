"""Banchero Costa weekly: stack each issue's tables into the bancosta_* series (append-only).

The series were built by build_banchero_series.py from raw LlamaParse output that no longer exists, then
extended by hand with backfill_banchero_matrix_fx_vhss.py --weeks N, so issues ingested by CI after 2026-09-28
reached the MD but never the series. This reads the curated MD of every issue (historical and CI, whose files
are named banchero_costa_DD_MM_YYYY_..._week_NN_YYYY.md) with the row rules of those builders:

  * secondhand matrix, VHSS, FX, container fixtures: backfill_banchero_matrix_fx_vhss.parse_doc;
    issue_date = the ISO Monday of the report week;
  * indicative newbuilding prices (record_type indicative_price) and Baltic ship recycling assessments
    (record_type recycling_assessment): the M-o-M / W-o-W tables; issue_date = the MD's issue_date.

The sales series is kept by the CI orchestrator and the prose newbuilding orders are not rebuilt here.
--check rebuilds every issue already in a series and compares it row for row (the control); --new-only
appends issues whose week is not in a series yet and never rewrites existing rows.

    python scripts/extract/publishers/bancosta_series.py --check
    python scripts/extract/publishers/bancosta_series.py --new-only
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backfill_banchero_matrix_fx_vhss import VCLASSES, cells, num, parse_doc, pct, strip_label  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
MD = ROOT / "data" / "extracted" / "md" / "banchero_costa"
SER = ROOT / "data" / "extracted" / "series"

FILES = {
    "secondhand_matrix": "bancosta_secondhand_matrix_series.csv",
    "vhss": "bancosta_vhss_series.csv",
    "fx": "bancosta_fx_series.csv",
    "fixtures": "bancosta_container_fixtures_series.csv",
    "newbuilding": "bancosta_newbuilding_series.csv",
    "demolition": "bancosta_demolition_series.csv",
}
# the record types this script owns in the shared newbuilding / demolition files
OWNED = {"newbuilding": "indicative_price", "demolition": "recycling_assessment"}
REPAIRABLE = ("secondhand_matrix", "vhss", "fx", "fixtures", "newbuilding", "demolition")


def front(text: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---", text.replace("\r\n", "\n"), re.S)
    out = {}
    for ln in (m.group(1).splitlines() if m else []):
        k, _, v = ln.partition(":")
        out[k.strip()] = v.strip().strip('"')
    return out


def fnum(tok) -> str:
    v = num(tok)
    return "" if v is None else str(v)


def tables(lines: list[str]) -> list[tuple[list[str], list[list[str]]]]:
    """Every GFM table: (header cells, body rows)."""
    out = []
    for i, ln in enumerate(lines):
        if ln.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|")                 and not set(lines[i + 1].replace(" ", "")) - set("|-:") and not (i and lines[i - 1].startswith("|")):
            body = []
            for ln2 in lines[i + 2:]:
                if not ln2.startswith("|"):
                    break
                body.append(cells(ln2))
            out.append((cells(ln), body))
    return out


def pick(tabs, change_col: str, unit_rx: str):
    """The table with a <change_col> column whose rows are priced in <unit_rx> (headers vary: "Vessel Class",
    "Category", "Segment", "Commodity / Fuel"; several tables share a header, so the rows decide)."""
    for hdr, rows in tabs:
        if len(hdr) >= 6 and any(x.upper() == change_col for x in hdr)                 and any(len(r) > 1 and re.fullmatch(unit_rx, r[1].strip(), re.I) for r in rows):
            return hdr, rows
    return None, []


def build(md: Path) -> tuple[int, int, dict[str, list[dict]]] | None:
    """(year, week, rows per family) for one issue MD."""
    text = md.read_text(encoding="utf-8")
    fm = front(text)
    try:
        year, week = int(fm["year"]), int(fm["report_week"])
    except (KeyError, ValueError):
        return None
    monday = dt.date.fromisocalendar(year, week, 1).isoformat()
    out = parse_doc(md)
    src = fm.get("source_file") or out_src(out)
    for fam in ("secondhand_matrix", "vhss", "fx", "fixtures"):
        for r in out[fam]:
            r.update({"issue_date": monday, "report_week": week, "source_file": src})
    tabs = tables(text.splitlines())
    if not out["secondhand_matrix"]:      # parse_doc takes the first "Category" table, not always this one
        h, rows = pick(tabs, "W-O-W", r"usd mln")
        for r in rows:
            vt = strip_label(r[0])
            cur = num(r[2])
            if vt.lower().startswith(VCLASSES) and cur is not None and 10.0 <= cur <= 250.0 and len(r) >= 6:
                out["secondhand_matrix"].append({
                    "issue_date": monday, "report_week": week, "vessel_type": vt, "unit": "usd mln",
                    "price_current_usd_m": cur, "price_previous_usd_m": num(r[3]),
                    "pct_change_wow": pct(r[4]), "pct_change_yoy": pct(r[5]), "source_file": src})
    out["newbuilding"], out["demolition"] = [], []
    h, rows = pick(tabs, "M-O-M", r"usd mln")
    for r in rows:
        if len(r) < 6 or num(r[2]) is None:
            continue
        out["newbuilding"].append({
            "issue_date": fm.get("issue_date", ""), "report_week": week, "record_type": "indicative_price",
            "vessel_type": strip_label(r[0]), "unit": r[1], "price_current": fnum(r[2]),
            "price_previous": fnum(r[3]), "period_current": h[2], "period_previous": h[3],
            "m_o_m": pct(r[4]), "y_o_y": pct(r[5]), "source_file": src})
    h, rows = pick(tabs, "W-O-W", r"usd/l[i]?dt")
    for r in rows:
        if len(r) < 6 or num(r[2]) is None:
            continue
        out["demolition"].append({
            "issue_date": fm.get("issue_date", ""), "report_week": week, "record_type": "recycling_assessment",
            # "usd/lidt" in some 2021 issues is a printed slip for usd/ldt
            "segment_location": strip_label(r[0]), "unit": r[1].lower().replace("lidt", "ldt"), "price_current": fnum(r[2]),
            "price_previous": fnum(r[3]), "period_current": h[2], "period_previous": h[3],
            "w_o_w": pct(r[4]), "y_o_y": pct(r[5]), "source_file": src})
    return year, week, out


def out_src(out: dict) -> str:
    for rows in out.values():
        for r in rows:
            return r.get("source_file", "")
    return ""


def read(path: Path) -> tuple[list[str], list[list[str]], bytes]:
    raw = path.read_bytes()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rd = csv.reader(fh)
        hdr = next(rd)
        return hdr, [r for r in rd if r], raw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="rebuild issues already in the series and compare")
    g.add_argument("--new-only", action="store_true", help="append issues not in the series yet")
    g.add_argument("--repair", nargs="+", choices=REPAIRABLE, metavar="FAMILY",
                   help="replace, in place, the rows of issues whose rebuild differs (table families only)")
    a = ap.parse_args(argv)

    series = {fam: read(SER / f) for fam, f in FILES.items()}
    have: dict[str, dict[tuple[str, int], list[list[str]]]] = {}
    for fam, (hdr, body, _) in series.items():
        have[fam] = {}
        for r in body:
            k = row_key(fam, hdr, r)
            if k:
                have[fam].setdefault(k, []).append(r)

    seen: set[tuple[int, int]] = set()
    added = {fam: [] for fam in FILES}
    fixes: dict[str, dict[tuple[str, int], list[list[str]]]] = {fam: {} for fam in FILES}
    stats = {fam: [0, []] for fam in FILES}
    for md in sorted(MD.rglob("*.md")):
        b = build(md)
        if b is None:
            continue
        year, week, out = b
        if (year, week) in seen:          # one MD per issue (re-ingests keep the first, by name)
            continue
        seen.add((year, week))
        for fam, rows in out.items():
            hdr = series[fam][0]
            got = [[("" if r.get(c) is None else str(r[c])) for c in hdr] for r in rows]
            if not got:
                continue
            key = (got[0][0], week)
            if key in have[fam]:
                if sorted(got) == sorted(have[fam][key]):
                    stats[fam][0] += 1
                else:
                    stats[fam][1].append((md.name, len(got), len(have[fam][key])))
                    fixes[fam][key] = got
                continue
            if a.new_only and year >= 2026:
                added[fam].extend(got)
                print(f"  + {fam}: {year} W{week} {len(got)} rows <- {md.name}")

    if a.check:
        bad = 0
        for fam, (ok, diff) in stats.items():
            print(f"{fam}: {ok} issues identical, {len(diff)} differ")
            for d in diff[:6]:
                print("   differs", d)
            bad += len(diff)
        return 1 if bad else 0
    if a.repair:
        for fam in a.repair:
            hdr, body, raw = series[fam]
            out, done = [], set()
            for r in body:
                k = row_key(fam, hdr, r)
                if k in fixes[fam]:
                    if k not in done:
                        out.extend(fixes[fam][k])
                        done.add(k)
                    continue
                out.append(r)
            write(SER / FILES[fam], hdr, out, raw)
            print(f"{fam}: {len(done)} issues replaced from their MD")
        return 0
    for fam, rows in added.items():
        if not rows:
            continue
        hdr, body, raw = series[fam]
        nl = "\r\n" if raw.split(b"\n", 1)[0].endswith(b"\r") else "\n"
        with open(SER / FILES[fam], "a", encoding="utf-8", newline="") as fh:
            if not raw.endswith(b"\n"):
                fh.write(nl)
            csv.writer(fh, lineterminator=nl).writerows(rows)
    print("bancosta series: " + ", ".join(f"{fam} +{len(r)}" for fam, r in added.items()))
    return 0


def row_key(fam: str, hdr: list[str], r: list[str]) -> tuple[str, int] | None:
    """(issue_date, report week) of a series row this script owns."""
    if "record_type" in hdr and r[hdr.index("record_type")] != OWNED[fam]:
        return None
    try:
        return r[0], int(r[hdr.index("report_week")])
    except ValueError:
        return None


def write(path: Path, hdr: list[str], body: list[list[str]], raw: bytes) -> None:
    nl = "\r\n" if raw.split(b"\n", 1)[0].endswith(b"\r") else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=nl).writerows([hdr] + body)
    tmp = path.with_suffix(".csv.tmp")
    tmp.write_bytes((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + buf.getvalue().encode("utf-8"))
    os.replace(tmp, path)

if __name__ == "__main__":
    sys.exit(main())
