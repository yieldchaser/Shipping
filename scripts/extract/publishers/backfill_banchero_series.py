"""Backfill missing weeks into the Banchero Costa freight/ffa/commodity series.

ROOT CAUSE (measured 2026-10-05): the md->tables parser in
run_banchero_world_class_llama.py::extract_structured_tables_from_md detected a
markdown table by looking for the substrings "| ---", "|:---" or "|---" in the
row below the header. The md tier later began emitting GFM *aligned* separators
("| :--- | :--- |"), which none of those match, so the function returned 0 rows
for EVERY category on the current md. That is why bancosta_freight_rates /
_ffa / _commodities_ series could not be regenerated and froze at build time.
Fix (this commit): match on the separator row with spaces removed, accepting
"|---" and "|:---". Verified: W38 freight 0 -> 90 (== the value already in the
series), and a full 248-doc re-extraction is byte-identical to the manual
work-around.

This script re-extracts the frozen three families from the canonical md and
UNION-appends only weeks that are absent from the series (existing rows are
never rewritten; prefix equality is asserted before writing).

Usage:
  python scripts/extract/publishers/backfill_banchero_series.py --weeks 36 37 [--dry-run]
"""
import sys, json, re, pathlib, datetime as dt, argparse
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
import run_banchero_world_class_llama as wc  # noqa: E402

MD = ROOT / "data" / "extracted" / "md" / "banchero_costa"
SER = ROOT / "data" / "extracted" / "series"
FAMILIES = {
    "freight_benchmarks": "bancosta_freight_rates_series.csv",
    "ffa_assessments": "bancosta_ffa_series.csv",
    "commodity_prices": "bancosta_commodities_series.csv",
}
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def body_of(txt):
    if txt.startswith("---"):
        parts = txt.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
    return txt


def issue_date_for(txt, body, stem):
    """The publisher's own cover date. Frontmatter first, then the cover range
    end (e.g. 'Week 36/2026 (31 Aug - 07 Sep)' -> 2026-09-07), then ISO+7d."""
    fm = re.search(r'issue_date:\s*"([^"]+)"', txt)
    if fm:
        return fm.group(1)
    mm = re.search(r"Week\s*\d{1,2}/20\d\d\s*\(([^)]*)\)", body)
    if mm:
        m2 = re.search(r"(\d{1,2})\s*([A-Za-z]{3})[^0-9]*$", mm.group(1))
        yy = re.search(r"20\d\d", stem)
        if m2 and yy:
            return f"{int(yy.group(0)):04d}-{MONTHS[m2.group(2).lower()[:3]]:02d}-{int(m2.group(1)):02d}"
    mm = re.search(r"((?:19|20)\d\d)[_-]?[Ww](\d{1,2})(?![0-9])", stem)
    if mm:
        return (dt.date.fromisocalendar(int(mm.group(1)), int(mm.group(2)), 1)
                + dt.timedelta(days=7)).isoformat()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--weeks", type=int, nargs="+", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # The canonical md naming; skip the duplicate re-parse copies.
    def pick_md(year, week):
        pat = re.compile(rf"banchero_costa_{year}_W0*{week}_Bancosta-Weekly-{year}-\d+(?!\d)\.md$")
        hits = sorted(p for p in MD.rglob("*.md") if pat.search(p.name))
        return hits[0] if hits else None

    added = {k: [] for k in FAMILIES}
    for wk in args.weeks:
        p = pick_md(args.year, wk)
        if p is None:
            print(f"W{wk}: no canonical md found - SKIP")
            continue
        txt = p.read_text(encoding="utf-8")
        body = body_of(txt)
        idate = issue_date_for(txt, body, p.stem)
        out = wc.extract_structured_tables_from_md(body, idate, wk, p.stem + ".pdf")
        print(f"{p.name}: issue_date={idate} wk={wk} freight={len(out['freight_benchmarks'])} "
              f"ffa={len(out['ffa_assessments'])} commod={len(out['commodity_prices'])}")
        for k in FAMILIES:
            added[k].extend(out[k])

    report = {}
    for k, f in FAMILIES.items():
        cur = pd.read_csv(SER / f, dtype=str, keep_default_na=False)
        cols = list(cur.columns)
        add = pd.DataFrame(added[k])
        if len(add):
            for c in ("change_wow", "change_yoy", "pct_change_wow", "pct_change_yoy"):
                if c in add.columns:
                    add[c] = add[c].astype(str).str.replace("+/-", "", regex=False)
            add = add.reindex(columns=cols).fillna("").astype(str)
            curs = set(map(tuple, cur.astype(str).values))
            add = add[[tuple(r) not in curs for r in add.astype(str).values]]
        else:
            add = cur.iloc[0:0]
        out = pd.concat([cur, add], ignore_index=True)
        assert out.iloc[:len(cur)].astype(str).values.tolist() == cur.astype(str).values.tolist()
        report[f] = {"before": len(cur), "added": len(add), "after": len(out),
                     "weeks": sorted(set(add["report_week"].astype(int))) if len(add) else []}
        if not args.dry_run:
            out.to_csv(SER / f, index=False)
    print(json.dumps(report, indent=1), "(dry-run, not written)" if args.dry_run else "(written)")


if __name__ == "__main__":
    main()
