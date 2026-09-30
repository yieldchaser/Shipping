#!/usr/bin/env python
"""Audit the cell store for rows whose MERGED cell pushed values into the wrong column.

WHY
---
camelot / pdfplumber occasionally put two or more page columns into one cell.
When that happens the row has fewer cells than the page has value columns, so
every value after the merge sits one column to the LEFT of its real header, and
a series keyed on (row label, column header) carries a number under the wrong
measurement. text_verified cannot see it: the reconciliation only asks whether a
value EXISTS in the page text, never whether it is in the right column.

Worked example, ground truth read from the page's own positioned words - the
MMI daily iron-ore report, page index 5 (1,205 of the 1,237 hellenic documents
with a fused row carry this page):

    header  y=78.7   65% Fe Fines | 62% Fe Fines | 58% Fe Fines | 62.5% Fe Lump
    data    y=91.4   Fe % | 65.00 | 62.00 | 58.00 | 62.50

    store   ['Fe %', '65.00\n62.00\n58.00', '62.50']

Three page columns are fused into one cell, so 62.50 (the 62.5% Fe Lump column)
is stored as the third cell of the row - under the 62% Fe Fines header.

Measured 2026-09-28 over a uniform random sample of 120 of the 20,825 fused
label_series-eligible rows in the store (2,659 documents): 71 SHIFT (59%; 76% of
the 93 rows the detector could resolve), 22 NO_MERGE, 20 NO_LABEL_CELL,
4 NO_BAND_TOKENS, 2 UNRESOLVED, 1 LABEL_NOT_FOUND. 3 of the 71 are printed
ranges (6000 - 10000) whose two endpoints sit in different x-clusters, so treat
68-71 as the measured range. 10 of the 71 merged three or more columns; the
median shifted row lost 2 columns. Sources: hellenic 50, shipbrokers 19, ppa 2.
Only 4 of the 21 SHIFT rows found in an earlier 30-row sample had an aligned
twin in the store, i.e. the misaligned copy is usually the only copy.

METHOD
------
Ground truth is the page's own text layer, never another extractor: the row is
anchored on its label, the page words on that y-band are clustered in x to
recover the page's value columns, each extracted cell's tokens are matched
left-to-right to those words, and a cell whose tokens land in TWO different
x-clusters is a merge. A row is SHIFT when a merged cell occupies more clusters
than the row has numeric cells.

LIMITATION
----------
Read-only: this measures and names the defect; it does not repair it. Repair
needs the page x-positions inside the extractor and changes how already-extracted
documents are interpreted, so it is a human decision.

usage
-----
    python scripts/extract/column_shift_audit.py --sample 120 --seed 4242
    python scripts/extract/column_shift_audit.py --json
    python scripts/extract/column_shift_audit.py --doc hellenic/<stem> --page 5 \
        --engine camelot-stream --table-idx 0 --row-idx 4
"""
import argparse
import collections
import json
import os
import random
import re
import statistics
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(REPO, "data", "extracted", "corpus", "db", "corpus.duckdb")
PDF_ROOT = os.path.join(REPO, "corpus")

TOK = re.compile(r"^[-+]?[0-9][0-9,.]*[%kKxX]?$")

FUSED_SQL = r"""
create or replace temp table fused as
select doc, page, engine, table_idx, row_idx, count(*) filter (where nc >= 2) as n_fused
from (
  select doc, page, engine, table_idx, row_idx, value,
         len(list_filter(regexp_split_to_array(trim(value), '\s+'),
                         x -> regexp_matches(x, '[0-9]'))) as nc,
         regexp_matches(value, '^[0-9,.\s%+\-/()$]*$') as numericish
  from cells
)
where numericish
group by 1, 2, 3, 4, 5
having n_fused >= 1
"""

ELIGIBLE_SQL = r"""
create or replace temp table elig as
select distinct c.doc, c.page, c.table_idx, c.row_idx, c.engine
from cells c
join cells l
  on l.doc = c.doc and l.page = c.page and l.engine = c.engine
 and l.table_idx = c.table_idx and l.row_idx = c.row_idx
 and l.col_idx = 0 and not l.is_numeric
where c.is_numeric and c.col_idx > 0
  and length(l.value) between 1 and 40
  and l.value not like '%' || chr(10) || '%'
  and l.value not like '%. %'
"""


def clusters(xs, gap_frac=0.45):
    """Group x positions into page columns: split where the gap exceeds a
    fraction of the band's own median gap, so the threshold comes from the page
    rather than from a hardcoded column width."""
    xs = sorted(xs)
    if len(xs) < 2:
        return [[x] for x in xs]
    gaps = [b - a for a, b in zip(xs, xs[1:]) if b - a > 1.0]
    med = statistics.median(gaps) if gaps else 10.0
    thr = max(4.0, gap_frac * med)
    out, cur = [], [xs[0]]
    for x in xs[1:]:
        if x - cur[-1] > thr:
            out.append(cur)
            cur = [x]
        else:
            cur.append(x)
    out.append(cur)
    return out


def pdf_index():
    idx = {}
    for dirpath, _dirnames, filenames in os.walk(PDF_ROOT):
        for fn in filenames:
            if fn.lower().endswith(".pdf"):
                idx.setdefault(fn.lower(), os.path.join(dirpath, fn))
    return idx


def pdf_for(doc, index):
    stem = doc.split("/", 1)[1] if "/" in doc else doc
    return index.get(stem.lower() + ".pdf")


def analyse(pdf_path, pno, row_cells, tol=3.5):
    """row_cells: [(col_idx, value)]. Returns the evidence dict for one row."""
    import pymupdf
    label = None
    for _c, v in row_cells:
        if str(v).strip() and not re.search(r"[0-9]", str(v)):
            label = str(v).strip()
            break
    if not label:
        return {"verdict": "NO_LABEL_CELL"}
    doc = pymupdf.open(pdf_path)
    if pno >= doc.page_count:
        return {"verdict": "PAGE_MISSING"}
    page = doc[pno]
    words = page.get_text("words")
    lab_words = [w for w in re.split(r"\s+", label) if w]
    best = None                      # (numeric words on that line, y centre)
    for i in range(len(words) - len(lab_words) + 1):
        if [words[i + j][4] for j in range(len(lab_words))] != lab_words:
            continue
        yc = sum((words[i + j][1] + words[i + j][3]) / 2.0
                 for j in range(len(lab_words))) / len(lab_words)
        nnum = sum(1 for w in words
                   if abs((w[1] + w[3]) / 2.0 - yc) <= tol and TOK.match(w[4]))
        if best is None or nnum > best[0]:
            best = (nnum, yc)
    if best is None:
        return {"verdict": "LABEL_NOT_FOUND", "label": label}
    yc = best[1]
    band = sorted((round((w[0] + w[2]) / 2.0, 1), w[4]) for w in words
                  if abs((w[1] + w[3]) / 2.0 - yc) <= tol and TOK.match(w[4]))
    if not band:
        return {"verdict": "NO_BAND_TOKENS", "label": label, "y": round(yc, 1)}
    cl = clusters([x for x, _t in band])
    cid = {x: i for i, grp in enumerate(cl) for x in grp}
    band_cid = [cid[x] for x, _t in band]
    used = [False] * len(band)
    cursor = -1.0
    per_cell = []
    for c, v in sorted(row_cells):
        toks = [t for t in re.split(r"\s+", str(v).replace("\n", " ")) if TOK.match(t)]
        got = []
        for t in toks:
            pick = None
            for i, (x, bt) in enumerate(band):
                if used[i] or bt != t or x <= cursor:
                    continue
                if pick is None or x < band[pick][0]:
                    pick = i
            if pick is None:                       # fall back: any unused match
                for i, (x, bt) in enumerate(band):
                    if used[i] or bt != t:
                        continue
                    if pick is None or x < band[pick][0]:
                        pick = i
            if pick is None:
                continue
            used[pick] = True
            cursor = band[pick][0]
            got.append(band_cid[pick])
        per_cell.append((c, str(v).replace("\n", "|"), sorted(set(got)), len(toks)))
    numeric = [pc for pc in per_cell if pc[3] > 0]
    merged = [pc for pc in numeric if len(pc[2]) >= 2]
    occupied = set()
    for pc in numeric:
        occupied.update(pc[2])
    out = {"verdict": "NO_MERGE", "label": label, "y": round(yc, 1),
           "page_cols": len(cl), "page_tokens": [t for _x, t in band],
           "page_x": [x for x, _t in band],
           "ext_numeric_cells": len(numeric), "cols_occupied": len(occupied),
           "per_cell": per_cell, "merged_cells": [pc[1] for pc in merged],
           "unmatched_band_tokens": [band[i][1] for i in range(len(band)) if not used[i]]}
    if merged and len(occupied) > len(numeric):
        out["verdict"] = "SHIFT"
    elif merged:
        out["verdict"] = "MERGED_SAME_COLSPAN"
    return out


def classify(ev):
    v = ev.get("verdict")
    if v == "NO_MERGE" and not ev.get("cols_occupied") and \
            len(ev.get("unmatched_band_tokens") or []) >= 3:
        return "UNRESOLVED"          # anchored nowhere useful; no claim either way
    return v


def population(con):
    con.execute(FUSED_SQL)
    con.execute(ELIGIBLE_SQL)
    return con.execute("""
        select e.doc, e.page, e.engine, e.table_idx, e.row_idx
        from elig e join fused f using (doc, page, table_idx, row_idx)
    """).fetchdf()


def row_cells(con, doc, page, engine, table_idx, row_idx):
    df = con.execute("""select col_idx, value from cells
        where doc = ? and page = ? and engine = ? and table_idx = ? and row_idx = ?
        order by col_idx""", [doc, page, engine, table_idx, row_idx]).fetchdf()
    return [(int(r.col_idx), str(r.value)) for r in df.itertuples()]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--sample", type=int, default=0,
                    help="uniformly sample N fused rows (0 = population count only)")
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--doc")
    ap.add_argument("--page", type=int)
    ap.add_argument("--engine", default="camelot-stream")
    ap.add_argument("--table-idx", type=int, default=0)
    ap.add_argument("--row-idx", type=int)
    args = ap.parse_args(argv)
    try:
        import duckdb
    except ImportError:
        print("duckdb not installed (pip install duckdb)", file=sys.stderr)
        return 2
    con = duckdb.connect(args.db, read_only=True)
    index = pdf_index()
    if args.doc is not None and args.row_idx is not None:
        cells = row_cells(con, args.doc, args.page, args.engine, args.table_idx, args.row_idx)
        pdf = pdf_for(args.doc, index)
        ev = analyse(pdf, args.page, cells) if pdf else {"verdict": "NO_PDF"}
        ev["cells"] = [str(v) for _c, v in cells]
        ev["pdf"] = pdf
        print(json.dumps(ev, indent=1, default=str))
        con.close()
        return 0
    df = population(con)
    pop = [r._asdict() for r in df.itertuples()]
    report = {"population_rows": len(pop), "population_docs": int(df.doc.nunique())}
    if not args.sample:
        if args.json:
            print(json.dumps(report, indent=1))
        else:
            print("fused label_series-eligible rows: %d in %d documents"
                  % (report["population_rows"], report["population_docs"]))
        con.close()
        return 0
    random.seed(args.seed)
    sample = random.sample(pop, min(args.sample, len(pop)))
    rows = []
    for r in sample:
        cells = row_cells(con, r["doc"], int(r["page"]), r["engine"], int(r["table_idx"]),
                          int(r["row_idx"]))
        pdf = pdf_for(r["doc"], index)
        ev = analyse(pdf, int(r["page"]), cells) if pdf else {"verdict": "NO_PDF"}
        verdict = classify(ev)
        rows.append(dict(r, verdict=verdict, merged=ev.get("merged_cells"),
                         page_cols=ev.get("page_cols"), cols_occupied=ev.get("cols_occupied"),
                         ext_cells=ev.get("ext_numeric_cells"),
                         cells=[str(v) for _c, v in cells]))
    tally = collections.Counter(r["verdict"] for r in rows)
    resolved = tally["SHIFT"] + tally["NO_MERGE"] + tally["MERGED_SAME_COLSPAN"]
    report.update({
        "sample": len(rows), "seed": args.seed, "tally": dict(tally),
        "resolved": resolved,
        "shift_share_of_sample": round(tally["SHIFT"] / max(1, len(rows)), 4),
        "shift_share_of_resolved": round(tally["SHIFT"] / max(1, resolved), 4),
        "shift_by_source": dict(collections.Counter(r["doc"].split("/")[0] for r in rows
                                                    if r["verdict"] == "SHIFT")),
        "shift_docs": len({r["doc"] for r in rows if r["verdict"] == "SHIFT"}),
        "rows": rows if args.json else None})
    if args.json:
        print(json.dumps(report, indent=1, default=str))
    else:
        print("population: %d fused label_series-eligible rows in %d documents"
              % (report["population_rows"], report["population_docs"]))
        print("sample %d (seed %d)" % (report["sample"], args.seed))
        for k, v in tally.most_common():
            print("  %-18s %d" % (k, v))
        print("SHIFT share: %.1f%% of the sample, %.1f%% of the %d resolved rows"
              % (100 * report["shift_share_of_sample"],
                 100 * report["shift_share_of_resolved"], resolved))
        print("SHIFT by source: %s" % report["shift_by_source"])
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
