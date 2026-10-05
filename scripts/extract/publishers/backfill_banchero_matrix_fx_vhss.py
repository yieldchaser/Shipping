"""Backfill weeks into the Banchero secondhand-matrix / VHSS / FX / container-fixtures series.

WHY (measured 2026-10-05): these series were built by
scripts/extract/build_banchero_series.py, which parses HTML <table> elements
from the md tier. The current md tier emits GFM markdown tables instead, so the
builder finds 0 tables on the newest md and cannot advance these series (its
sandboxed re-run reproduces the shipped rows and stops at 2026-09-14). The
modern md consumer (run_banchero_world_class_llama.extract_structured_tables_from_md)
recovers the secondhand/VHSS/FX tables but DROPS their W-o-W / Y-o-Y columns, so
neither existing tool can extend them. Container fixtures were a REPORTED
FIXTURES table through W24 and became a templated PROSE paragraph from W25 on,
which no builder ever consumed.

This script parses the GFM tables (and the fixtures prose) directly from the
canonical md, using the SAME row schema and the SAME date convention as
build_banchero_series.py (report_week = the filename week; issue_date = the ISO
Monday of that week), then UNION-appends only weeks absent from the series.
Existing rows are never rewritten and prefix equality is asserted before writing.

Usage:
  python scripts/extract/publishers/backfill_banchero_matrix_fx_vhss.py --year 2026 --weeks 39 [--dry-run]
"""
import sys, re, json, pathlib, datetime as dt, argparse
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
MD = ROOT / "data" / "extracted" / "md" / "banchero_costa"
SER = ROOT / "data" / "extracted" / "series"

PCT_CLEAN = re.compile(r"[~*#\s]+")
VCLASSES = ("capesize","newcastlemax","kamsarmax","panamax","ultramax","supramax",
            "handysize","vlcc","suezmax","aframax","lr2","lr1","mr")


def pct(tok):
    return re.sub(r"[~*#\s]+", "", str(tok)).replace("+/-", "")


def strip_label(s):
    return str(s).strip().strip("*#").strip()


def stem_week(stem):
    m = re.search(r"((?:19|20)\d\d)[_-]?[Ww](\d{1,2})(?![0-9])", stem)
    if not m:
        return None, None
    y, wk = int(m.group(1)), int(m.group(2))
    return dt.date.fromisocalendar(y, wk, 1).isoformat(), wk


def num(tok):
    if tok is None:
        return None
    t = PCT_CLEAN.sub("", str(tok)).replace(",", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def num_cell(tok):
    if tok is None:
        return ""
    t = str(tok).replace("*", "").strip()
    if t.startswith("TEU"):
        t = t[3:]
    if t.startswith("@14"):
        t = t[3:]
    return t.replace(",", "").strip()


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_gfm_table(lines, header_pred):
    for i, ln in enumerate(lines):
        if not ln.startswith("|"):
            continue
        hdr = cells(ln)
        if not header_pred(hdr):
            continue
        if i + 1 >= len(lines) or not lines[i + 1].strip().startswith("|"):
            continue
        if set(lines[i + 1].replace(" ", "")) - set("|-:"):
            continue
        rows = []
        for ln2 in lines[i + 2:]:
            if not ln2.startswith("|"):
                break
            rows.append(cells(ln2))
        return hdr, rows
    return None, []


FIX_RX = re.compile(
    r"(?P<name>[A-Z0-9][A-Za-z0-9 .'&/\-]+?),\s*blt\s*(?P<built>\d{4}),\s*"
    r"(?P<teu>[\d,]+)\s*teu,\s*(?:(?P<teu14>[\d,]+)\s*@14,\s*)?"
    r"(?P<gear>geared|gless|gearless),\s*"
    r"(?:Fixed to|Extended with|Fixed with|Extended to)\s+(?P<account>.+?)\s+for\s+"
    r"(?P<period>\d+(?:\s*-\s*\d+)?)\s*mos?\s+at\s+USD\s+(?P<rate>[\d,]+)")


def parse_fixtures_prose(lines):
    text = "\n".join(lines)
    m = re.search(r"Some reported fixtures:(.*?)(?:\n#|\Z)", text, re.S)
    if not m:
        return []
    seg = re.sub(r"[*_]", "", m.group(1))
    out = []
    for mm in FIX_RX.finditer(seg):
        g = mm.groupdict()
        out.append({
            "vessel_name": g["name"].strip(),
            "built": g["built"],
            "teu": g["teu"].replace(",", ""),
            "teu_14": (g["teu14"] or "").replace(",", ""),
            "gear": "YES" if g["gear"] == "geared" else "NO",
            "account": g["account"].strip(),
            "period_mos": re.sub(r"\s*-\s*", "-", g["period"]),
            "rate_usd_day": g["rate"].replace(",", ""),
        })
    return out


def parse_doc(md_path):
    stem = md_path.stem
    issue_date, week = stem_week(stem)
    src = f"corpus/01-brokers/banchero_costa/{md_path.parent.name}/{stem}.pdf"
    lines = md_path.read_text(encoding="utf-8").splitlines()
    out = {"secondhand_matrix": [], "vhss": [], "fx": [], "fixtures": []}

    h, rows = parse_gfm_table(
        lines, lambda c: c and c[0].upper() in ("VESSEL CLASS", "CATEGORY") and any(x.upper() == "W-O-W" for x in c))
    for r in rows:
        vt = strip_label(r[0])
        if not vt.lower().startswith(VCLASSES):
            continue
        cur, prev = num(r[2]), num(r[3])
        if cur is None or not (10.0 <= cur <= 250.0):
            continue
        out["secondhand_matrix"].append({
            "issue_date": issue_date, "report_week": week, "vessel_type": vt,
            "unit": "usd mln", "price_current_usd_m": cur, "price_previous_usd_m": prev,
            "pct_change_wow": pct(r[4]), "pct_change_yoy": pct(r[5]), "source_file": src})

    h, rows = parse_gfm_table(lines, lambda c: c and c[0].upper() == "VHSS")
    for r in rows:
        seg = strip_label(r[0])
        if seg.upper() in ("VHSS", "UNIT", "INDEX"):
            continue
        cur, prev = num(r[2]), num(r[3])
        if cur is None:
            continue
        out["vhss"].append({
            "issue_date": issue_date, "report_week": week, "segment": seg,
            "unit": r[1], "value_current": cur, "value_previous": prev,
            "pct_change_wow": pct(r[4]), "pct_change_yoy": pct(r[5]),
            "source_file": src})

    h, rows = parse_gfm_table(lines, lambda c: c and c[0].upper() == "CURRENCIES")
    for r in rows:
        if not r[0]:
            continue
        out["fx"].append({
            "issue_date": issue_date, "report_week": week, "currency_pair": strip_label(r[0]),
            "rate_current": num(r[1]), "rate_previous": num(r[2]),
            "pct_change_wow": pct(r[3]), "pct_change_yoy": pct(r[4]), "source_file": src})

    # Container fixtures: REPORTED FIXTURES table (<=W24) ...
    h, rows = parse_gfm_table(lines, lambda c: c and c[0].replace("'", "").upper().startswith("VESSELS NAME"))
    for r in rows:
        if len(r) < 8:
            continue
        out["fixtures"].append({
            "vessel_name": strip_label(r[0]), "built": r[1], "teu": r[2].replace(",", ""),
            "teu_14": num_cell(r[3]), "gear": r[4].upper(), "account": strip_label(r[5]),
            "period_mos": r[6], "rate_usd_day": r[7].replace(",", ""),
            "issue_date": issue_date, "report_week": week, "source_file": src})
    # ... then the templated PROSE paragraph (>=W25).
    for rec in parse_fixtures_prose(lines):
        rec.update({"issue_date": issue_date, "report_week": week, "source_file": src})
        out["fixtures"].append(rec)
    return out


FAMILIES = {
    "secondhand_matrix": "bancosta_secondhand_matrix_series.csv",
    "vhss": "bancosta_vhss_series.csv",
    "fx": "bancosta_fx_series.csv",
    "fixtures": "bancosta_container_fixtures_series.csv",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--weeks", type=int, nargs="+", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    def pick_md(year, week):
        pat = re.compile(rf"banchero_costa_{year}_W0*{week}_Bancosta-Weekly-{year}-\d+(?!\d)\.md$")
        hits = sorted(p for p in MD.rglob("*.md") if pat.search(p.name))
        return hits[0] if hits else None

    added = {k: [] for k in FAMILIES}
    for wk in args.weeks:
        p = pick_md(args.year, wk)
        if p is None:
            print(f"W{wk}: no canonical md - SKIP")
            continue
        d = parse_doc(p)
        print(f"{p.name}: matrix={len(d['secondhand_matrix'])} vhss={len(d['vhss'])} "
              f"fx={len(d['fx'])} fixtures={len(d['fixtures'])}")
        for k in FAMILIES:
            added[k].extend(d[k])

    report = {}
    for k, f in FAMILIES.items():
        cur = pd.read_csv(SER / f, dtype=str, keep_default_na=False)
        cols = list(cur.columns)
        add = pd.DataFrame(added[k])
        if len(add):
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
    print(json.dumps(report, indent=1), "(dry-run)" if args.dry_run else "(written)")


if __name__ == "__main__":
    main()
