"""Repair COLLECTION-DATE rows in the displayed Drewry WCI index.

WHY THIS EXISTS
  The WCI is assessed on a THURSDAY. Until 2026-09-29 fetch_drewry_wci.py's date
  parser fell back to the RUN date whenever it could not find the page's own
  assessment date, so a live run on a Friday or Sunday stamped that day as the
  row's date. Measured 2026-09-30 on the displayed file: 7 of 109 rows were not
  Thursdays and 5 of those were the SAME WEEKLY PRINT as a row already held
  (the 3 Sep print appeared 4x, 10 Sep 2x, 17 Sep 2x) - the app drew
  observations on days the publisher made no assessment.

WHAT IT DOES
  For every row whose date is NOT a Thursday, read the print's own date off the
  publisher's page ("World Container Index - 3 Sep"), relabel the row to it, and
  drop rows that duplicate a print already held - but ONLY after checking the
  dropped row's five values are identical to the kept row's. Values are never
  rewritten; only the date key and exact duplicate rows change. Any row it
  cannot derive is left alone and REPORTED, never guessed.

  Derivation is content-anchored (the page's own phrase, never a hard-coded
  map); the year comes from the row, rolled back if the phrase would land in the
  future. The derived date must be a Thursday, be 0-10 days BEFORE the row's own
  date, and the page must print exactly one such phrase.

Usage
  python3 scripts/scrapers/repair_wci_collection_dates.py            # dry run
  python3 scripts/scrapers/repair_wci_collection_dates.py --apply    # write
"""
import argparse, csv, datetime as dt, io, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV = os.path.join(REPO, "data", "indices", "drewry_wci_historical.csv")
MD_DIR = os.path.join(REPO, "corpus", "06-drewry", "opinions")
KEYS = ("composite_index", "shanghai_rotterdam", "shanghai_genoa", "shanghai_la", "shanghai_ny")
COLS = ["date"] + list(KEYS) + ["rotterdam_shanghai"]
PHRASE = re.compile(r"World\s+Container\s+Index\s*[-\u2013\u2014]\s*(\d{1,2})\s+([A-Za-z]{3,9})", re.I)
MON = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
THURSDAY = 3


def page_phrase_dates(path, row_date):
    """Print dates the page itself displays, as date objects. [] if none."""
    try:
        text = io.open(path, encoding="utf-8", errors="replace").read()
    except IOError:
        return []
    out = set()
    for day, mon in PHRASE.findall(text):
        m = MON.get(mon[:3].lower())
        if not m:
            continue
        for year in (row_date.year, row_date.year - 1):
            try:
                cand = dt.date(year, m, int(day))
            except ValueError:
                continue
            if dt.timedelta(0) <= (row_date - cand) <= dt.timedelta(10):
                out.add(cand)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the repaired CSV")
    a = ap.parse_args()
    rows = list(csv.DictReader(io.open(CSV, encoding="utf-8", newline="")))
    pre = len(rows)
    fixed, kept, changes, unresolved, targets = [], {}, [], [], {}

    for orig in rows:
        d = dt.date.fromisoformat(orig["date"])
        target, r = d.isoformat(), orig
        if d.weekday() != THURSDAY:
            md = os.path.join(MD_DIR, str(d.year), "%s_drewry_wci.md" % d.isoformat())
            cands = page_phrase_dates(md, d) if os.path.exists(md) else []
            if len(cands) != 1 or cands[0].weekday() != THURSDAY:
                unresolved.append((orig["date"], "no unambiguous page date (%s)" % (cands or "none")))
            else:
                target = cands[0].isoformat()
                if target in kept:
                    if all((orig[k] or "") == (kept[target][k] or "") for k in KEYS):
                        targets[orig["date"]] = target
                        changes.append((orig["date"], target, "DROPPED duplicate of the %s print" % target))
                        continue
                    unresolved.append((orig["date"], "duplicate of %s with DIFFERENT values - left as is" % target))
                    target = d.isoformat()
                else:
                    r = dict(orig)
                    r["date"] = target
                    changes.append((orig["date"], target, "RELABELLED"))
        kept.setdefault(target, r)
        targets[orig["date"]] = target
        fixed.append(r)

    fixed.sort(key=lambda r: r["date"])
    by_date = {r["date"]: r for r in fixed}

    def dup_groups(rs):
        sig = {}
        for r in rs:
            sig.setdefault(tuple(r[k] for k in KEYS), []).append(r["date"])
        return {t: v for t, v in sig.items() if len(v) > 1}

    ng_pre = sum(1 for r in rows if dt.date.fromisoformat(r["date"]).weekday() != THURSDAY)
    ng_post = sum(1 for r in fixed if dt.date.fromisoformat(r["date"]).weekday() != THURSDAY)
    print("rows              %d -> %d" % (pre, len(fixed)))
    print("non-Thursday      %d -> %d" % (ng_pre, ng_post))
    print("dup value-groups  %d -> %d" % (len(dup_groups(rows)), len(dup_groups(fixed))))
    dates = [r["date"] for r in fixed]
    print("dates unique/increasing: %s" % (len(set(dates)) == len(dates) and dates == sorted(dates)))
    for old, new, note in changes:
        print("  %s -> %s  %s" % (old, new, note))
    for d, why in unresolved:
        print("  UNRESOLVED %s: %s" % (d, why))
    # VALUE CONTROL: every input row must be found at its target date carrying
    # the SAME five values - this script moves dates, it never edits a value.
    bad = []
    for orig in rows:
        got = by_date.get(targets[orig["date"]])
        if got is None or any((orig[k] or "") != (got[k] or "") for k in KEYS):
            bad.append(orig["date"])
    print("VALUE CONTROL: rows whose five values differ from their input: %d %s" % (len(bad), bad[:5]))

    if not a.apply:
        print("(dry run - pass --apply to write)")
        return 0
    out = io.StringIO(newline="")
    w = csv.DictWriter(out, fieldnames=COLS, lineterminator="\n")
    w.writeheader()
    for r in fixed:
        w.writerow({k: r.get(k, "") for k in COLS})
    io.open(CSV, "w", encoding="utf-8", newline="").write(out.getvalue())
    print("written: %s" % os.path.relpath(CSV, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
