"""P4a step 1 — persistent DuckDB FTS5 index over the chunk retrieval unit.

Design (plan §5.5): the lexical arm of hybrid retrieval is DuckDB's FTS extension with
`stemmer='none'` so shipping codes (TD3C, P1A_82, C5, IMO numbers, tickers) survive as whole
tokens; `strip_accents=false` keeps names as printed. The indexed unit is
`context_prefix + body` (plan §5.3 prefix plus §5.2 chunk text), so publisher, title, date,
heading path and tagged entity names are searchable — without them a section-level question
("what does the X weekly say about <heading>") cannot reach the chunk at all, because headings
live only in the prefix. One index over 318,232 chunks; it is additive and droppable with `--drop`.

Run:  python kb/p4a_index.py            # build (idempotent: drops+rebuilds unless --keep)
      python kb/p4a_index.py --drop     # remove the index
      python kb/p4a_index.py --probe    # query latency only (needs an existing index)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
REPORT = ROOT / "kb/reports/p4a_index.json"
LOG = ROOT / "kb/logs/p4a_index.log"

PROBES = [
    "TD3C VLCC Middle East China rate",
    "Panamax 82000 dwt delivery Singapore",
    "Scorpio Tankers sale and purchase",
    "Baltic Dry Index capesize",
]


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def drop(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("LOAD fts")
    try:
        con.execute("PRAGMA drop_fts_index('chunk')")
        log("dropped existing fts index")
    except Exception as exc:  # noqa: BLE001 - absent index is fine
        log(f"no index to drop ({str(exc)[:80]})")


def db_file_bytes() -> int:
    return DB.stat().st_size if DB.exists() else 0


def index_tables_present(con: duckdb.DuckDBPyConnection) -> bool:
    row = con.execute(
        "SELECT count(*) FROM duckdb_tables() WHERE table_name = 'fts_main_chunk'"
    ).fetchone()
    return bool(row and row[0])


def build(con: duckdb.DuckDBPyConnection) -> dict:
    n_chunks = con.execute("SELECT count(*) FROM chunk").fetchone()[0]
    t0 = time.time()
    con.execute("INSTALL fts")
    con.execute("LOAD fts")
    drop(con)
    con.execute("CHECKPOINT")
    pre_bytes = db_file_bytes()
    t1 = time.time()
    con.execute(
        "PRAGMA create_fts_index('chunk', 'chunk_id', 'body', 'context_prefix', "
        "stemmer='none', strip_accents=false, lower=1, overwrite=1)"
    )
    t2 = time.time()
    con.execute("CHECKPOINT")
    post_bytes = db_file_bytes()
    size = max(post_bytes - pre_bytes, 0)
    log(f"indexed {n_chunks:,} chunks (body+context_prefix) in {t2 - t1:.1f}s,"
        f" index grew DB by {size / 1e9:.2f} GB")
    return {"chunks": int(n_chunks), "indexed_columns": ["body", "context_prefix"],
            "build_seconds": round(t2 - t1, 1), "setup_seconds": round(t1 - t0, 1),
            "index_bytes": size, "db_file_bytes": post_bytes}


def probe(con: duckdb.DuckDBPyConnection) -> list[dict]:
    con.execute("LOAD fts")
    out = []
    for q in PROBES:
        t0 = time.time()
        hits = con.execute(
            "SELECT chunk_id, score FROM ("
            "  SELECT chunk_id, fts_main_chunk.match_bm25(chunk_id, ?) AS score FROM chunk"
            ") WHERE score IS NOT NULL ORDER BY score DESC LIMIT 150",
            [q],
        ).fetchall()
        out.append({"query": q, "hits": len(hits), "seconds": round(time.time() - t0, 3),
                    "top": hits[0][0] if hits else None})
        log(f"probe {q!r}: {len(hits)} hits in {out[-1]['seconds']}s")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--keep", action="store_true", help="do not rebuild an existing index")
    args = ap.parse_args()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    try:
        con.execute("SET memory_limit='900MB'")
        con.execute("SET threads=2")
        if args.drop:
            drop(con)
            log("done (drop)")
            return 0
        if args.probe:
            res = {"probes": probe(con)}
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps(res, indent=1), encoding="utf-8")
            return 0
        if args.keep:
            if index_tables_present(con):
                log("index present; probing only")
                res = {"kept": True, "db_file_bytes": db_file_bytes(), "probes": probe(con)}
                REPORT.parent.mkdir(parents=True, exist_ok=True)
                REPORT.write_text(json.dumps(res, indent=1), encoding="utf-8")
                return 0
            log("no index present; building despite --keep")
        res = build(con)
        res["probes"] = probe(con)
        res["db_bytes"] = db_file_bytes()
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(res, indent=1), encoding="utf-8")
        log(f"wrote {REPORT.relative_to(ROOT)}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
