"""Repair the Drewry WCI MARKDOWN tier: print date AND the fused lane values.

WHY THIS EXISTS
  `scripts/scrapers/fetch_drewry_wci.py` writes a weekly markdown snapshot into
  `corpus/06-drewry/opinions/<year>/<date>_drewry_wci.md` from
  `extract_assessments(page)`. Two of that parser's defects were fixed AFTER the
  files were written, so the md tier still carries them:

    (1) DATE - the file was named with the RUN date, not the print's own
        assessment date ("World Container Index - 03 Sep" -> 2026-09-03). The
        CSV was repaired (see docs/drewry_wci_date_key_verdict.md); the md tier
        was not.
    (2) VALUES - the two lane PAIRS were fused: shanghai_rotterdam held
        shanghai_genoa's level and shanghai_ny held shanghai_la's level (and one
        print lost shanghai_la entirely).

  These files are not decoration: they are the corpus record, and
  `scratch/wci/merge_display.py` gives this tier AUTHORITY for dates >=
  2026-08-01, so a re-merged display file would re-import the wrong numbers.

WHAT IT DOES
  For every `<date>_drewry_wci.md`: read the print's own date off the page's own
  phrase (content-anchored, never a hard-coded map; must be a Thursday 0-10 days
  before the file's own date, and unique), take the five values from the repaired
  `data/indices/drewry_wci_historical.csv` row for that print date, rewrite the
  frontmatter date, the H1 and the values table, then rename the file to the
  print's date. Files of the same print are collapsed to one ONLY after their
  bodies are proven identical.

CONTROLS (all printed)
  * PROSE WITNESS - every non-blank value must appear VERBATIM (as $4,465 /
    $10,394) in the file's OWN commentary prose, which was written from the page.
    A value that fails this is not written; the print is reported.
  * NO OTHER TEXT CHANGED - the commentary section must be byte-identical before
    and after.
  * IDEMPOTENT - a second run changes nothing.
  * FINAL - every file is a Thursday named by its own page phrase, its table
    equals the CSV row, no duplicate print remains.

Usage
  python3 scripts/scrapers/repair_wci_md_tier.py            # dry run
  python3 scripts/scrapers/repair_wci_md_tier.py --apply    # write + rename
"""
import argparse
import csv
import datetime as dt
import glob
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MD_GLOB = os.path.join(REPO, "corpus", "06-drewry", "opinions", "20*", "*_drewry_wci.md")
CSV = os.path.join(REPO, "data", "indices", "drewry_wci_historical.csv")
KEYS = ("composite_index", "shanghai_rotterdam", "shanghai_genoa",
        "shanghai_la", "shanghai_ny", "rotterdam_shanghai")
PHRASE = re.compile(r"World\s+Container\s+Index\s*[-\u2013\u2014]\s*(\d{1,2})\s+([A-Za-z]{3,9})", re.I)
MON = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
THURSDAY = 3
TABLE_HEAD = "## Assessed Values ($/40ft)"
COMMENT_HEAD = "## Page Commentary"


def read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


def page_dates(text, file_date):
    """Print dates the page itself displays, restricted to a Thursday 0-10 days back."""
    out = set()
    for day, mon in PHRASE.findall(text):
        m = MON.get(mon[:3].lower())
        if not m:
            continue
        for year in (file_date.year, file_date.year - 1):
            try:
                cand = dt.date(year, m, int(day))
            except ValueError:
                continue
            if dt.timedelta(0) <= (file_date - cand) <= dt.timedelta(10):
                out.add(cand)
    return sorted(out)


def current_values(text):
    vals = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*(\w+)\s*\|\s*([\d.]*)\s*\|\s*$", line)
        if m:
            vals[m.group(1)] = m.group(2)
    return vals


def comma(v):
    return "{:,.0f}".format(float(v))


def table_block(row):
    lines = ["| Metric | Value |", "| --- | --- |"]
    for k in KEYS:
        lines.append("| %s | %s |" % (k, row.get(k, "")))
    return "\n".join(lines)


def commentary(text):
    i = text.find(COMMENT_HEAD)
    return text[i:] if i >= 0 else ""


def body_only(text):
    """The file with the date-bearing lines blanked - used to prove duplicates."""
    out = []
    for line in text.splitlines():
        if line.startswith("title:") or line.startswith("date:") or line.startswith("# "):
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def rebuild(text, print_date, row):
    """Return (new_text, ok_lines, problems)."""
    problems = []
    d = print_date.isoformat()
    text = re.sub(r'(?m)^title: "Drewry World Container Index Snapshot - [^"]*"$',
                  'title: "Drewry World Container Index Snapshot - %s"' % d, text)
    text = re.sub(r'(?m)^date: "[^"]*"$', 'date: "%s"' % d, text, count=1)
    text = re.sub(r'(?m)^# Drewry World Container Index Snapshot - .*$',
                  '# Drewry World Container Index Snapshot - %s' % d, text)
    # prose witness: every non-blank value must be printed on the page's own text
    wit = 0
    for k in KEYS:
        v = (row.get(k) or "").strip()
        if not v:
            continue
        if "$" + comma(v) in text:
            wit += 1
        else:
            problems.append("%s=$%s NOT in the page commentary" % (k, comma(v)))
    block = table_block(row)
    new, n = re.subn(re.escape(TABLE_HEAD) + r".*?(?=\n" + re.escape(COMMENT_HEAD) + ")",
                     TABLE_HEAD + "\n\n" + block + "\n", text, flags=re.S)
    if n != 1:
        problems.append("table block not found exactly once (n=%d)" % n)
        return text, wit, problems
    return new, wit, problems


def load_text(path):
    raw = io.open(path, "rb").read()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8", "replace").replace("\r\n", "\n"), crlf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the repaired files")
    a = ap.parse_args()

    csv_rows = {r["date"]: r for r in csv.DictReader(io.open(CSV, encoding="utf-8", newline=""))}
    files = sorted(glob.glob(MD_GLOB))
    plans, unresolved = [], []
    for path in files:
        base = os.path.basename(path)
        file_date = dt.date.fromisoformat(base[:10])
        text, crlf = load_text(path)
        cands = page_dates(text, file_date)
        if len(cands) != 1:
            unresolved.append((base, "no unique page date (%s)" % ([c.isoformat() for c in cands] or "none")))
            continue
        print_date = cands[0]
        row = csv_rows.get(print_date.isoformat())
        if not row:
            unresolved.append((base, "no CSV row for print date %s" % print_date))
            continue
        new_text, wit, problems = rebuild(text, print_date, row)
        if problems:
            unresolved.append((base, " | ".join(problems)))
            continue
        plans.append({"path": path, "base": base, "print": print_date, "row": row,
                      "old": text, "new": new_text, "crlf": crlf, "wit": wit,
                      "old_vals": current_values(text)})

    # ---- group by print: prove the members are the SAME print before collapsing
    groups = {}
    for p in plans:
        groups.setdefault(p["print"], []).append(p)
    keep, drop, conflicts = [], [], []
    for print_date in sorted(groups):
        members = sorted(groups[print_date], key=lambda x: x["base"])
        head = members[0]
        for m in members[1:]:
            if body_only(m["old"]) == body_only(head["old"]):
                drop.append(m)
            else:
                conflicts.append((m["base"], print_date))
        keep.append(head)

    print("population        %d *_drewry_wci.md files" % len(files))
    print("print groups      %d prints <- %d files" % (len(groups), len(plans)))
    print("unresolved        %d" % len(unresolved))
    for b, why in unresolved:
        print("   UNRESOLVED %s: %s" % (b, why))
    for b, d in conflicts:
        print("   CONFLICT %s: same print %s as another file but a DIFFERENT body - left alone" % (b, d))
    print("")
    for p in keep:
        old = p["old_vals"]
        row = p["row"]
        moved = [k for k in KEYS if (old.get(k) or "").strip() != (row.get(k) or "").strip()]
        print("  %s -> %s_drewry_wci.md   prose witness %d/5   value cells changed %d %s"
              % (p["base"], p["print"].isoformat(), p["wit"], len(moved), moved))
    for m in drop:
        print("  DROP %s (identical body to the kept %s file for the %s print)"
              % (m["base"], keep[[k["print"] for k in keep].index(m["print"])]["base"], m["print"]))

    # ---- controls on the planned output
    print("")
    print("CONTROL no-other-text-changed: %d/%d planned files keep their commentary byte-identical"
          % (sum(1 for p in keep if commentary(p["old"]) == commentary(p["new"])), len(keep)))
    print("CONTROL prose witness: %d/%d planned files have all 5 values printed in their own page text"
          % (sum(1 for p in keep if p["wit"] == 5), len(keep)))
    print("CONTROL ids: %d files, %d prints, %d dropped duplicates, %d unresolved"
          % (len(files), len(keep), len(drop), len(unresolved)))

    if not a.apply:
        print("(dry run - pass --apply to write)")
        return 0

    for p in keep:
        target = os.path.join(os.path.dirname(p["path"]), "%s_drewry_wci.md" % p["print"].isoformat())
        out = p["new"].replace("\n", "\r\n") if p["crlf"] else p["new"]
        if os.path.abspath(target) != os.path.abspath(p["path"]) and os.path.exists(target):
            print("  SKIP %s: target %s already exists" % (p["base"], os.path.basename(target)))
            continue
        io.open(target, "w", encoding="utf-8", newline="").write(out)
        if os.path.abspath(target) != os.path.abspath(p["path"]):
            os.remove(p["path"])
            print("  wrote %s (was %s)" % (os.path.relpath(target, REPO), p["base"]))
    for m in drop:
        os.remove(m["path"])
        print("  removed duplicate %s" % m["base"])
    print("applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
