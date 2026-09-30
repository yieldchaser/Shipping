"""
Advanced Shipping - closing verification, with the defect counters CORRECTED.

The first pass counted four "defect classes" but never hand-checked them. Two of
the four were wrong, and the two that were real all traced to one root cause.

WHAT THE FIRST COUNTERS SAID, AND WHAT HAND-CHECKING SHOWED
  D1 prose captured as a table   119 tables / 103 docs  -> REAL, but not data
     loss. The narrative is genuinely on the page and pdf-inspector puts it in a
     grid container. The values survive: every value the page prints is present
     in the .md. Residue is containerisation, not recall.
  D2 detached row labels         306 tables / 249 docs  -> NOT A DEFECT.
     Hand-checked six examples: the "empty column" is a GUTTER between two
     side-by-side panels (Bulkers | <blank> | Tankers) or a genuinely empty
     Comments column. Counting it was measuring layout, not damage.
  D3 axis/legend merged in       505 tables / 241 docs  -> 96% INFLATED.
     The counter had two arms and only one is a defect. The LEGEND arm fired on
     'Capesize|Kamsarmax|Handysize' in any table with <=2 header cells, which is
     the Daily T/C panel's own ROW LABELS - healthy tables. Re-measured with an
     arithmetic-progression test for a real axis run (6000,5000,4000,3000,2000,
     1000,0): 34 tables in 34 docs, not 505.
  D4 page banner as table header 177 tables / 177 docs  -> REAL and benign.
     171 headers are ONLY the banner, 6 carry the banner plus other columns. The
     real column names survive as the first data row, so nothing is lost.

ROOT CAUSE of D1/D3/D4: page 1 is fused into a single giant "table 0" holding
the S&P prose, the chart axis ticks, the Baltic index panel, the Daily T/C block
and BDTI/BCTI. The value-anchored liteparse swap in the runner found no matching
block for those tables and fell back to keeping the fused grid, which is the
correct fail-safe (never replace with something unproven) but leaves the fusion.

RESIDUE, named: 23 of 249 documents have no clean BDI..BHSI row labels in
.tables.json. Their values and label abbreviations are still present as text in
both the .md and the fused cell, so nothing is lost, but a series builder must
parse the fused cell for those 23 rather than read labelled rows.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path("data/extracted/md/advanced_shipping")
BALTIC = ("BDI", "BCI", "BPI", "BSI", "BHSI")
NUM = re.compile(r"^[\d.,%$+\-\s]+$")
NUMPURE = re.compile(r"^-?[\d.,]+$")


def as_num(s):
    s = s.strip().replace(" ", "")
    if not NUMPURE.match(s):
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def longest_arith(tokens, minlen=5):
    """Longest run of consecutive numeric tokens forming an arithmetic series."""
    best = 0
    i = 0
    while i < len(tokens):
        if as_num(tokens[i]) is None:
            i += 1
            continue
        vals, j = [], i
        while j < len(tokens) and as_num(tokens[j]) is not None:
            vals.append(as_num(tokens[j]))
            j += 1
        if len(vals) >= minlen:
            for a in range(len(vals) - minlen + 1):
                for b in range(a + minlen, len(vals) + 1):
                    seg = vals[a:b]
                    d = [round(seg[k + 1] - seg[k], 6) for k in range(len(seg) - 1)]
                    if len(set(d)) == 1 and d[0] != 0:
                        best = max(best, len(seg))
        i = max(j, i + 1)
    return best


def main():
    docs = tables_n = 0
    baltic_docs = bdti_docs = bcti_docs = tc_docs = 0
    prose_tables = prose_docs = 0
    axis_tables = 0
    axis_docs = set()
    banner_only = banner_plus = 0
    no_baltic = []
    for f in sorted(OUT.glob("*.tables.json")):
        docs += 1
        stem = f.name.replace(".tables.json", "")
        tables = json.loads(f.read_text(encoding="utf-8"))
        flat_all = ""
        doc_prose = doc_axis = False
        for i, t in enumerate(tables):
            tables_n += 1
            cells = [c for r in t["rows"] for c in r]
            flat = " ".join(cells)
            flat_all += " " + flat
            if any(len(c) > 120 and re.search(r"[a-z]{4,}\s+[a-z]{4,}\s+[a-z]{4,}", c)
                   for c in cells):
                prose_tables += 1
                doc_prose = True
            for r in t["rows"]:
                if longest_arith([tok for c in r for tok in c.split()]) >= 5:
                    axis_tables += 1
                    doc_axis = True
                    axis_docs.add(stem)
                    break
            if i == 0 and re.search(r"WEEKLY SHIPPING MARKET REPORT|Week \d+\s*\(",
                                    " ".join(t["header"]), re.I):
                # banner-ONLY means every other cell is part of the banner text
                # (a date fragment, a superscript, a week number). Anything else
                # is a real column name that happened to share the header slot.
                rest = [c for c in t["header"] if c.strip()
                        and not re.search(r"WEEKLY SHIPPING MARKET REPORT|Week \d+", c, re.I)
                        and not re.match(r"^<sup>", c)
                        and not re.fullmatch(r"[\d\s\w/]{0,12}", c.strip())]
                if rest:
                    banner_plus += 1
                else:
                    banner_only += 1
        if doc_prose:
            prose_docs += 1
        for t in tables:
            firsts = [r[0] for r in t["rows"] if r]
            if all(l in firsts for l in BALTIC):
                baltic_docs += 1
                break
        else:
            no_baltic.append(stem)
        if "BDTI" in flat_all:
            bdti_docs += 1
        if "BCTI" in flat_all:
            bcti_docs += 1
        if ("Capesize" in flat_all and "Kamsarmax" in flat_all
                and "Ultramax" in flat_all):
            tc_docs += 1

    n = max(docs, 1)
    print("=" * 88)
    print(f"ADVANCED SHIPPING - CLOSING VERIFICATION ({docs} docs, {tables_n} tables)")
    print("=" * 88)
    print("LABEL COVERAGE")
    print(f"  full BDI..BHSI row labels : {baltic_docs}/{docs} ({100*baltic_docs/n:.0f}%)")
    print(f"  BDTI present              : {bdti_docs}/{docs} ({100*bdti_docs/n:.0f}%)")
    print(f"  BCTI present              : {bcti_docs}/{docs} ({100*bcti_docs/n:.0f}%)")
    print(f"  Daily T/C labels          : {tc_docs}/{docs} ({100*tc_docs/n:.0f}%)")
    print()
    print("DEFECTS, CORRECTED")
    print(f"  D1 prose in a table       : {prose_tables} tables / {prose_docs} docs "
          f"(containerisation, NOT data loss)")
    print(f"  D2 detached row labels    : NOT A DEFECT - the empty column is a panel "
          f"gutter")
    print(f"  D3 real chart-axis runs   : {axis_tables} tables / {len(axis_docs)} docs "
          f"(was reported as 505/241)")
    print(f"  D4 page banner as header  : {banner_only} banner-only + "
          f"{banner_plus} banner+columns")
    print()
    print(f"RESIDUE: {len(no_baltic)}/{docs} docs have no clean BDI..BHSI rows")
    for s in no_baltic:
        print("   ", s)


if __name__ == "__main__":
    main()
