"""Build a queryable table database from extraction output.

Turns the per-document tables.jsonl (nested rows) into a normalised, long-format
cell store plus a table-level catalogue, written as Parquet and registered in a
DuckDB database so time series can be built with SQL.

Layout:
  data/extracted/db/tables.parquet      one row per CELL
      source, doc, doc_stem, page, table_idx, engine, row_idx, col_idx, value,
      is_numeric, num_value, text_verified
  data/extracted/db/catalogue.parquet   one row per TABLE
      source, doc, page, table_idx, engine, n_rows, n_cols, text_verified,
      extraction_ts
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

NUM = re.compile(r"^-?[\d,]*\.?\d+$")


def to_number(v):
    s = str(v).strip().replace(",", "").replace("$", "").replace("£", "") \
        .replace("%", "").replace("+", "")
    s = s.replace("(", "-").replace(")", "")
    if NUM.match(s):
        try:
            return float(s)
        except ValueError:
            return None
    return None


def iter_tables(out_root):
    for tpath in glob.glob(os.path.join(out_root, "*", "*", "tables.jsonl")):
        doc_dir = os.path.dirname(tpath)
        doc = f"{os.path.basename(os.path.dirname(doc_dir))}/{os.path.basename(doc_dir)}"
        try:
            with open(tpath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield doc, json.loads(line)
                    except json.JSONDecodeError:
                        continue
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
    for doc, t in iter_tables(a.out):
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
        idx = t.get("_table_idx", 0)
        cat_rows.append({
            "source": source, "doc": doc, "doc_stem": stem,
            "page": t.get("page"), "table_idx": idx,
            "engine": t.get("engine"),
            "n_rows": n_rows, "n_cols": n_cols,
            "text_verified": t.get("text_verified"),
            "acc": t.get("acc"), "extraction_ts": ts,
        })
        for ri, row in enumerate(rows):
            for ci, val in enumerate(row):
                sv = "" if val is None else str(val).strip()
                if not sv:
                    continue
                num = to_number(sv)
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
