#!/usr/bin/env python3
"""Signal Ocean ballaster vessel-count series (BESPOKE, per-source).

Measured 2026-10-03: signal_vessel_counts_series.csv shipped HEADER-ONLY (0 rows).
The upstream HTML-table path in run_signal.py keyed on <table> headers named
'Vessel Class' / 'Ballasters' / 'Number of Vessels'. Those strings exist in
corpus/07-signal/html/ ONLY in prose and figure captions - a structural scan
found ZERO <th>/<td> cells containing them, and only 4 of 446 signal documents
produced any HTML table at all. Signal's vessel counts are PROSE, not a table.

Recoverable (measured over all 256 monitors):
  * 2023-2025: qualitative narrative only (no per-class numeric count). Not parsed.
  * 2026 weeks 32/35/36/37/38 (5 docs): a structured template giving a per-class
    global ballaster count + a regional breakdown. 20 global counts, all verified
    against the source HTML.

SELF-VALIDATING CONTROL: in a full-breakdown block the stated regional counts sum
EXACTLY to the stated global count (Capesize 236+154+125+47+27 = 589). That
identity flags each block's regional set complete/partial, and caught the
number-before-region phrasing bug. 12/20 blocks complete, all 12 match to the unit.

run_signal.py delegates to this module (see run_pipeline).
"""

import os
import re
import csv
import glob

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MD_DIR = os.path.join(REPO, "data", "extracted", "md", "signal", "monitors")
SERIES_PATH = os.path.join(REPO, "data", "extracted", "series", "signal_vessel_counts_series.csv")

CLASSES = ["Capesize", "Panamax", "Kamsarmax", "Post-Panamax", "Supramax", "Ultramax", "Handysize"]
REGIONS = ["Indian Ocean/South Africa", "FEAST/NOPAC", "North Atlantic",
           "South Atlantic", "Australasia", "Med/Black Sea"]
HEAD = re.compile(r"^\*\*(Ballaster positioning|Ballasters vs the previous week)\.\*\*", re.I)

HEADERS = ["issue_date", "year", "week", "sector", "vessel_class", "metric",
           "region", "count", "regions_complete", "source_file"]


def _num_after(text, pos, maxwin=70):
    """First integer after pos NOT immediately followed by '%' (skips WoW deltas)."""
    for m in re.finditer(r"[0-9][0-9,]*", text[pos:pos + maxwin]):
        if text[pos + m.end():pos + m.end() + 2].startswith("%"):
            continue
        return int(m.group(0).replace(",", ""))
    return None


def _region_counts(line):
    """Associate each known region token with its count.

    Two content-anchored forms:
      A: '212 in the Indian Ocean/South Africa'  (number BEFORE region; W38 Panamax)
      B: 'Australasia fell 11% WoW to 196'       (region BEFORE number)
    Prefer A; fall back to B. A number followed by '%' is a WoW delta -> skipped.
    """
    line = re.sub(r",\s*including[^,]*?,", " ,", line, flags=re.I)
    regs = {}
    for r in REGIONS:
        a = None
        for m in re.finditer(r"([0-9][0-9,]*)\s+(?:in|at|to)\s+(?:the\s+)?" + re.escape(r), line, re.I):
            a = int(m.group(1).replace(",", ""))
            break
        b = None
        for rm in re.finditer(re.escape(r), line):
            pre = line[max(0, rm.start() - 14):rm.start()].lower()
            if r == "Med/Black Sea" and "including" in pre:
                continue
            b = _num_after(line, rm.end())
            break
        if a is not None:
            regs[r] = a
        elif b is not None:
            regs[r] = b
    return regs


def _frontmatter(text):
    d = {}
    for m in re.finditer(r"^(issue_date|year|week):\s*\"?([^\"\n]+)\"?\s*$", text, re.M):
        d[m.group(1)] = m.group(2).strip()
    return d


def _sector(slug):
    s = slug.lower()
    if "dry" in s:
        return "Dry Bulk"
    if "tanker" in s:
        return "Tankers"
    return "Dry Bulk"


def extract_blocks(md_dir=MD_DIR):
    """Return one dict per (document, vessel_class) ballaster block."""
    blocks = []
    for f in sorted(glob.glob(os.path.join(md_dir, "*.md"))):
        text = open(f, encoding="utf-8", errors="ignore").read()
        fm = _frontmatter(text)
        if not fm.get("issue_date"):
            continue
        slug = os.path.splitext(os.path.basename(f))[0]
        for line in text.splitlines():
            if not HEAD.match(line):
                continue
            cm = re.search(r"(" + "|".join(CLASSES) + r")\b[^.]{0,40}?ballaster", line, re.I)
            if not cm:
                continue
            cls = cm.group(1)
            gpos = line.lower().find("ballaster", cm.start())
            global_count = _num_after(line, gpos)
            if global_count is None:
                continue
            regs = _region_counts(line)
            nreg = len([r for r in regs if r != "Med/Black Sea"])
            complete = (nreg >= 5 and sum(regs.values()) == global_count)
            if nreg >= 5 and not complete:
                regs, complete = {}, False   # full-looking set that does not reconcile
            blocks.append({
                "issue_date": fm["issue_date"], "year": fm.get("year", ""),
                "week": fm.get("week", ""), "sector": _sector(slug),
                "vessel_class": cls, "global": global_count, "regions": regs,
                "regions_complete": complete,
                "source_file": "corpus/07-signal/html/%s.html" % slug,
            })
    return blocks


def build_rows(blocks):
    rows = []
    for b in blocks:
        flag = "True" if b["regions_complete"] else "False"
        rows.append([b["issue_date"], b["year"], b["week"], b["sector"], b["vessel_class"],
                     "Ballaster Count", "Global", b["global"], flag, b["source_file"]])
        for region, cnt in sorted(b["regions"].items()):
            rows.append([b["issue_date"], b["year"], b["week"], b["sector"], b["vessel_class"],
                         "Regional Ballaster Count", region, cnt, flag, b["source_file"]])
    rows.sort(key=lambda r: (r[0], r[4], r[5], r[6]))
    return rows


def write_series(rows, path=SERIES_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(rows)
    return len(rows)


def main():
    blocks = extract_blocks()
    rows = build_rows(blocks)
    n = write_series(rows)
    n_global = sum(1 for r in rows if r[5] == "Ballaster Count")
    n_regional = n - n_global
    n_complete = sum(1 for b in blocks if b["regions_complete"])
    print("[signal_vessel_counts] blocks=%d docs=%d" % (
        len(blocks), len(set(b["source_file"] for b in blocks))))
    print("  rows=%d (global=%d, regional=%d); complete-breakdown blocks=%d/%d" % (
        n, n_global, n_regional, n_complete, len(blocks)))
    print("  -> %s" % SERIES_PATH)


if __name__ == "__main__":
    main()
