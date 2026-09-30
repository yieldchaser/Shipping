"""Build a queryable table database from extraction output.

Turns the per-document tables.jsonl (nested rows) into a normalised, long-format
cell store plus a table-level catalogue, written as Parquet and registered in a
DuckDB database so time series can be built with SQL.

Layout:
  data/extracted/db/tables.parquet      one row per CELL
      source, doc, doc_stem, page, table_idx, engine, row_idx, col_idx, value,
      is_numeric, num_value, text_verified
  data/extracted/db/catalogue.parquet   one row per TABLE
      source, doc, page, table_idx, engine, n_rows, n_cols, n_cells, shape,
      text_verified, extraction_ts
      table_idx = ordinal within (doc, page, engine) in tables.jsonl order;
      shape in {grid, onecol, blob, single_cell, empty}
  data/extracted/db/corpus.duckdb       both registered as views + a
      v_time_series helper view that pivots first-column labels against
      numeric cells

Usage:
  python scripts/extract/build_table_db.py            # incremental (new docs)
  python scripts/extract/build_table_db.py --rebuild  # reparse everything
"""
import argparse
import glob
import json
import os
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(REPO, "data", "extracted")
DB_DIR = os.path.join(DEFAULT_OUT, "db")

# Leading currency marker + any whitespace before a value. Measured
# 2026-09-23: 65,700 shipbroker cells print "$ 15,648" (symbol, then a
# SPACE, then the number), and stripping only the symbol left the leading
# space in place, so NUM never matched and 38,149 cells across 469
# documents were read as non-numeric - every $/day TCE rate column in the
# Allied/xclusiv weeklies among them. Ground truth: the PDF text layer of
# allied_2022_W12 page 1 reads "the BCI 5TC finally closing on Friday at
# US$  15,648/day, 27.6% lower" against the cell "$ 15,648".
CUR = re.compile(r"^(-?)(?:US\$|USD|EUR|GBP|\$|£|€)\s*")
# 2026-09-23 (b): the sign can sit BEFORE the symbol ("-$ 1,498", a
# weekly-change column). The marker regex only anchored at the symbol,
# so 2,245 such cells stayed non-numeric. The leading sign is captured
# and re-emitted rather than swallowed with the marker.
NUM = re.compile(r"^-?[\d,]*\.?\d+$")

# ---------------------------------------------------------------- the period
# Whether "." is a thousands separator or a decimal point is a PER-PUBLISHER
# convention, so this is a measured whitelist rather than a heuristic applied
# to every source. Settled 2026-09-23 by reading the page text layer of one
# document per publisher - the only method that works, because "3.370" parsed
# as 3.37 is a well-formed float of a plausible magnitude and every automated
# check passes while the value is 1000x wrong.
#
#   advanced_shipping  W38 2026 p1 text: "BDI 3.370 3.507 -3,91% / BCI 5.768
#                      6.080 / BPI 2.251 2.407", the chart's own y-axis ticks
#                      "1.000 2.000 ... 7.000", "Daily T/C Avg Capesize 52.315
#                      55.139" ($52,315/day) and "Kamsarmax Bora 81.682"
#                      (81,682 dwt). Comma decimals elsewhere ("-3,91%").
#   star_asia          2024 W02 p2 text: "BDI 1.460 2,086 763 -30.01% +91.35%"
#                      - one row mixing a period-thousands level with a
#                      comma-thousands level, so both mean thousands; its dwt
#                      cells ("KAI HANG 3 3.905", "AFRICAN JACANA 58.753") agree.
#   agora              2026-09-18 p2 text: "BDI 3.336", "BCI T/C - 182.000 dwt",
#                      "$47.793", alongside comma decimals ("-5,25%"). Cross
#                      check: that same week's BDI prints as 3.370 in
#                      advanced_shipping's report of 18-Sep.
#
# Deliberately NOT listed - their d.ddd cells are DECIMALS, read from the page:
#   xclusiv    "EUR/USD 1.154", "USD/JPY 154.520", "Natural gas 4.045"
#   intermodal FX levels in the same table as "200.23"
#   anchor     mixed: "BDI 3.285" but demolition prices "572.000"/"538.333"
# Adding a publisher here without reading a page of its own would inflate its
# values 1000x in the opposite direction - the same error, mirrored.
PERIOD_IS_THOUSANDS = ("advanced_shipping", "star_asia", "agora")

# A thousands group is exactly three digits AND the leading group cannot be
# zero, so a real 3-decimal value ("0.008", 22 cells in this corpus) is never
# read as 8.
THOUSANDS_PERIOD = re.compile(r"^[1-9]\d{0,2}(?:\.\d{3})+$")

# A number carrying TWO OR MORE period groups cannot be a decimal literal -
# no decimal number has two decimal points - so this shape is a thousands
# separator for EVERY publisher and needs no whitelist. Measured 2026-09-24:
# 1,768 cells in 101 golden_destiny documents, 0 of them numeric today, all in
# the "Invested Capital" column of the weekly S&P report. golden_destiny
# writes that SAME column with commas in its 2021/2022 era ("468,300,000",
# "1,345,600,000") and with periods from 2023 ("149.200.000", "120.000.000",
# "1.040.000.000"), and only the comma era was being read. The comma form is
# already handled below by stripping commas (5,200 such cells, all numeric),
# so the two forms were asymmetric: one era parsed, the other was dropped.
MULTI_THOUSANDS_PERIOD = re.compile(r"^[1-9]\d{0,2}(?:\.\d{3}){2,}$")

# A CELL UNDER A TONNAGE HEADER is written with period thousands whatever the
# publisher. Measured 2026-09-28 by reading the pages (text layer, not another
# extractor): golden_destiny_2022_W31 page 5 demolition table reads
# "OKRA | Dwt 171.199 | 1999 | JAPAN | LDT 21.018 | Price($) 11.118.522 |
# 529 $/ldt" - and 21.018 LDT x 529 $/ldt = 11,118,522, which is the printed
# Price and is ALREADY converted by MULTI_THOUSANDS_PERIOD above. Read as
# decimals the identity fails by 1000x, so DWT/LDT are integers in thousands.
# Scope measured over the whole corpus (period-shaped cells whose nearest
# non-numeric text ABOVE, same column, is a tonnage header): golden_destiny
# 5,409 of 7,288 cells, carriers 31 of 2,981, advanced_shipping 13,137 of
# 28,686 (already converted by the whitelist), star_asia 51 of 65 (likewise).
# Deliberately NOT included: "$/ldt" and "Price $/ldt" price columns (6 cells,
# no page read) - a rate per LDT is a different unit from a tonnage.
TONNAGE_HEADER = re.compile(
    r"^\s*(?:in\s+|total\s+)?(?:dwt|ldt)\s*"
    r"(?:[\(\[]\s*(?:mt|lt|ton|tonnage)\s*[\)\]])?"
    r"(?:\s*/\s*(?:mt|lt|ton|tonnage))?\s*$", re.I)

# What a header is NOT: any cell that looks like a number.
NUMERIC_LOOKING = re.compile(r"^[+-]?\d[\d.,]*$")


def column_headers(rows):
    """For every cell, the nearest non-empty, non-numeric text cell ABOVE it in
    the same column - that column's own header.

    One backward carry per column, so this is O(rows*cols) and reproduces
    exactly the rule the page measurement above was taken with.
    """
    n_cols = max((len(r) for r in rows), default=0)
    cols = []
    for ci in range(n_cols):
        carry = ""
        col = []
        for row in rows:
            col.append(carry)
            if ci < len(row):
                v = str(row[ci]).strip()
                if v and len(v) <= 40 and not NUMERIC_LOOKING.match(v):
                    carry = v
        cols.append(col)
    return cols




def publisher_of(stem):
    """The publisher whose number convention applies to this document stem.

    Prefix match only, and only against PERIOD_IS_THOUSANDS. Measured across
    the corpus 2026-09-23: every stem these three publishers produce starts
    with their own name (advanced_shipping 248/248 documents, star_asia 190/190,
    agora 211/211) and no other publisher's stem does, so the match cannot
    fire on a document whose convention was not read.
    """
    s = stem or ""
    for pub in PERIOD_IS_THOUSANDS:
        if s.startswith(pub):
            return pub
    return None



def _decimal_sep(s):
    """Which character is the decimal separator in the numeric string `s`.

    A thousands group is exactly three digits, so a comma followed by any
    other count of digits cannot be a thousands separator and must be a
    decimal comma. Measured 2026-09-22: the shipbroker weeklies print
    European decimals. The PDF text layer and "the publisher's own markdown"
    mirror of `advanced_shipping_19_09_2026` both print
    "Diana Shipping Inc (DSX) NYSE 3,07 2,92 5,14%" - a NYSE share price, so
    3.07 and not 307 - and "Brent Crude (BZ) 104,82 107,63 -2,61%" (104.82,
    not 10,482). Ambiguous case left as-is: a bare "1,234" is read as 1234
    (thousands), the US convention and the pre-existing behaviour.
    """
    if "," in s and "." in s:
        return "," if s.rfind(",") > s.rfind(".") else "."
    if "," in s:
        return "." if len(s.rsplit(",", 1)[1]) == 3 else ","
    return "."


def to_number(v, publisher=None, unit_thousands=False):
    """Parse a table cell to a number, honouring the document convention.

    Fixed 2026-09-22: this used to strip every comma, so a European-decimal
    cell was inflated 100x (10000x for 4-decimal FX quotes) and a
    "1.234,56" cell was deflated 1000x. Measured against
    data/extracted/corpus/db: 43,928 cells in 558 documents (all
    `shipbrokers`) are affected. Rebuild the derived DB to pick this up for
    documents extracted before the fix.

    Fixed 2026-09-23: a leading currency marker followed by whitespace
    ("$ 15,648") defeated NUM, so the $/day rate columns of the broker
    weeklies were all non-numeric. CUR strips the marker AND the space.
    Rebuild the derived DB to pick this up for existing documents.

    Fixed 2026-09-24: a value with two or more period groups ("149.200.000")
    was not numeric at all, so golden_destiny's 2023+ Invested Capital column
    was invisible while its 2021/2022 comma-written twin was already read.
    Rebuild the derived DB to pick this up for existing documents.
    """

    s = CUR.sub(r"\1", str(v).strip()).replace("$", "").replace("£", "") \
        .replace("%", "").replace("+", "")
    s = s.replace("(", "-").replace(")", "")
    # PERIOD AS THOUSANDS, for the publishers where that was measured (see
    # PERIOD_IS_THOUSANDS). "3.370" is 3370, not 3.37: measured 2026-09-23,
    # 28,686 advanced_shipping cells + 988 agora + 65 star_asia, and the value
    # reached the promoted layer (shipbrokers|bdi|current|b1 carried 1.46 on
    # 2024-01-08 for a BDI of 1,460 - star_asia_2024_W02 page 2).
    # TONNAGE COLUMN, publisher-independent (see TONNAGE_HEADER): "81.682" under
    # a Dwt header is 81,682 dwt. It sits before the whitelist because it is the
    # narrower, page-proven rule for the publishers the whitelist cannot cover:
    # carriers writes "117.536" in its "Price in $m" column (a decimal) on the
    # same page as "111.933" in its "VLCC TCE in $" column (thousands), so no
    # publisher-level answer exists for that document.
    if unit_thousands and THOUSANDS_PERIOD.match(s):
        s = s.replace(".", "")
    if publisher and publisher in PERIOD_IS_THOUSANDS and THOUSANDS_PERIOD.match(s):
        s = s.replace(".", "")
    # PUBLISHER-INDEPENDENT: two period groups cannot be a decimal, so this
    # shape is thousands whatever the publisher (see MULTI_THOUSANDS_PERIOD).
    if MULTI_THOUSANDS_PERIOD.match(s):
        s = s.replace(".", "")
    # normalise the separator BEFORE matching: a European full form like
    # "1.234,56" does not match NUM while the comma is still in place.
    if _decimal_sep(s) == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    if NUM.match(s):
        try:
            return float(s)
        except ValueError:
            return None
    return None


def table_content_sig(rows):
    """Content signature of a table, or None when it holds no non-empty cell.

    Added 2026-09-28. camelot-stream returns the SAME table region more than
    once on some pages. Measured on intermodal_2023_W20 page 1: camelot returns
    3 tables, two of them byte-identical, with bounding boxes
    (4.16, 338.16, 587.81, 783.77) and (7.53, 338.16, 586.52, 783.77) - the same
    region detected twice with a 3.4 pt difference in x. Every extractor call is
    recorded, so the duplicate reaches the store: 1,721 (doc, page, engine)
    groups hold identical content twice, 3,132 redundant table copies and
    382,072 duplicated cells (5.5% of 6,946,400), and label_series carries the
    duplicate points. Dropping a copy whose cell content is identical to another
    table on the SAME page and engine is content-preserving by construction: no
    value can be lost, because an identical twin keeps it.
    """
    norm = [[("" if c is None else str(c)) for c in r] for r in (rows or [])]
    if not any(c.strip() for r in norm for c in r):
        return None                      # empty tables carry no content to dedup
    return json.dumps(norm, ensure_ascii=False)


def iter_tables(out_root):
    """Yield (doc, table_record, table_idx) in file order.

    table_idx is the ordinal of the record within its (doc, page, engine) group.
    Fixed 2026-09-22: this used to be read from a `_table_idx` key that no
    producer writes (grep: the only occurrence in the repo was this read), so
    every table on a page got index 0. Both dedup keys below are
    (doc, page, table_idx, engine), and label_series joins on table_idx, so the
    collapse silently dropped 147 of 229 tables and 2,036 of 9,257 cells on a
    5-document pool, and paired labels from one table with values from another
    (778 of 2,208 label_series rows on that pool). Deriving the ordinal from
    file order needs no change to the extraction artefacts and is stable for
    any document that is rewritten identically.
    """
    for tpath in sorted(glob.glob(os.path.join(out_root, "*", "*", "tables.jsonl"))):
        doc_dir = os.path.dirname(tpath)
        doc = f"{os.path.basename(os.path.dirname(doc_dir))}/{os.path.basename(doc_dir)}"
        counts = {}
        seen_sig = set()
        try:
            with open(tpath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = (rec.get("page"), rec.get("engine"))
                    sig = table_content_sig(rec.get("rows"))
                    if sig is not None:
                        if (key, sig) in seen_sig:
                            continue     # exact duplicate of a table already emitted
                        seen_sig.add((key, sig))
                    idx = rec.get("_table_idx")
                    if idx is None:
                        idx = counts.get(key, 0)
                        counts[key] = idx + 1
                    yield doc, rec, idx
        except OSError:
            continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    db_dir = os.path.join(a.out, "db")
    os.makedirs(db_dir, exist_ok=True)

    import pandas as pd

    cells_path = os.path.join(db_dir, "tables.parquet")
    cat_path = os.path.join(db_dir, "catalogue.parquet")
    seen_docs = set()
    if not a.rebuild and os.path.exists(cat_path):
        try:
            seen_docs = set(pd.read_parquet(cat_path)["doc"].unique())
        except Exception:
            seen_docs = set()

    cell_rows, cat_rows = [], []
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    docs = 0
    table_records = 0
    counted = set()
    for doc, t, idx in iter_tables(a.out):
        if doc in seen_docs:
            continue
        table_records += 1
        if doc not in counted:
            counted.add(doc)
            docs += 1
        source = doc.split("/")[0]
        stem = doc.split("/")[1]
        rows = t.get("rows") or []
        if not rows:
            continue
        n_rows = len(rows)
        n_cols = max((len(r) for r in rows), default=0)
        cells = [c for r in rows for c in r if str(c).strip()]
        # shape: measured 2026-09-22 on a 300-doc seeded sample, 11.0% of table
        # records hold <=1 non-empty cell (a grid skeleton with no content) and
        # 3.8% are a single column holding the whole page (a blob, not a table);
        # 74.7% are real multi-column grids. Both are extraction artefacts, so
        # they are labelled here rather than silently counted as tables.
        if not cells:
            shape = "empty"
        elif len(cells) <= 1:
            shape = "single_cell"
        elif n_cols == 1:
            shape = "blob" if max(len(str(c)) for c in cells) > 300 else "onecol"
        else:
            shape = "grid"
        cat_rows.append({
            "source": source, "doc": doc, "doc_stem": stem,
            "page": t.get("page"), "table_idx": idx,
            "engine": t.get("engine"),
            "n_rows": n_rows, "n_cols": n_cols,
            "n_cells": len(cells), "shape": shape,
            "text_verified": t.get("text_verified"),
            "acc": t.get("acc"), "extraction_ts": ts,
        })
        hdrs = column_headers(rows)
        for ri, row in enumerate(rows):
            for ci, val in enumerate(row):
                sv = "" if val is None else str(val).strip()
                if not sv:
                    continue
                hdr = hdrs[ci][ri] if ci < len(hdrs) else ""
                num = to_number(sv, publisher_of(stem),
                                unit_thousands=bool(hdr and TONNAGE_HEADER.match(hdr)))
                cell_rows.append({
                    "source": source, "doc": doc, "doc_stem": stem,
                    "page": t.get("page"), "table_idx": idx,
                    "engine": t.get("engine"), "row_idx": ri, "col_idx": ci,
                    "value": sv, "is_numeric": num is not None,
                    "num_value": num, "text_verified": t.get("text_verified"),
                })

    if not cell_rows:
        print("no new tables found; nothing to write")
        return 0

    new_cat = pd.DataFrame(cat_rows)
    new_cells = pd.DataFrame(cell_rows)
    if os.path.exists(cells_path) and not a.rebuild:
        new_cells = pd.concat([pd.read_parquet(cells_path), new_cells],
                              ignore_index=True)
        new_cat = pd.concat([pd.read_parquet(cat_path), new_cat],
                            ignore_index=True)
    new_cells.drop_duplicates(
        subset=["doc", "page", "table_idx", "engine", "row_idx", "col_idx"],
        keep="last", inplace=True)
    new_cat.drop_duplicates(
        subset=["doc", "page", "table_idx", "engine"], keep="last", inplace=True)

    new_cells.to_parquet(cells_path, index=False, compression="zstd")
    new_cat.to_parquet(cat_path, index=False, compression="zstd")

    # DuckDB views + a first-column-label time-series helper
    try:
        import duckdb
        db = os.path.join(db_dir, "corpus.duckdb")
        con = duckdb.connect(db)
        con.execute(f"CREATE OR REPLACE VIEW cells AS "
                    f"SELECT * FROM read_parquet('{cells_path.replace(os.sep, '/')}')")
        con.execute(f"CREATE OR REPLACE VIEW catalogue AS "
                    f"SELECT * FROM read_parquet('{cat_path.replace(os.sep, '/')}')")
        con.execute("""
            CREATE OR REPLACE VIEW label_series AS
            SELECT c.source, c.doc, c.doc_stem, c.page, c.table_idx, c.row_idx,
                   l.value AS label,
                   c.col_idx, c.num_value, c.text_verified
            FROM cells c
            JOIN cells l
              ON l.doc = c.doc AND l.page = c.page
             AND l.engine = c.engine
             AND l.table_idx = c.table_idx AND l.row_idx = c.row_idx
             AND l.col_idx = 0 AND NOT l.is_numeric
            WHERE c.is_numeric AND c.col_idx > 0
              AND length(l.value) BETWEEN 1 AND 40
              AND l.value NOT LIKE '%\n%'
              AND l.value NOT LIKE '%. %'
        """)
        con.close()
        db_ok = db
    except ImportError:
        db_ok = None

    print(f"docs={docs} table_records={table_records} "
          f"catalogue={len(new_cat)} cells={len(new_cells)}")
    print(f"cells -> {cells_path}")
    print(f"catalogue -> {cat_path}")
    print(f"duckdb -> {db_ok or 'duckdb not installed (pip install duckdb)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
