"""P4a step 2 — dense vectors for every distinct chunk text (plan §5.4/§5.5).

Dedup first: 318,232 chunks share 220,150 distinct `norm_sha` values, so one vector per
distinct text and `chunk.vec_row` points duplicates at the same row (29% of chunks are repeats,
so this saves ~98k embeddings = ~31% of the compute).

Embedding model: `nvidia/nemotron-3-embed-1b` (2048-d) on the free NVIDIA NIM API, same model
for documents and queries, id + dims recorded in kb/state/vec/meta.json. This is a logged
deviation from plan D4 (`Qwen3-Embedding-0.6B`, 1024-d int8 CPU): 220k x ~350 tok = 77M tokens
at ~1.2 GFLOP/token is >90 PFLOP, i.e. >100 h on the 2-core i3-1215U, while NIM runs it in
~1.5 h at $0. Vectors are unit-normalised fp16 in a memmap, so a later model swap is a rerun
plus a vec_row rewrite, not a schema change.

Run:  python kb/p4a_embed.py                 # resumable full run (background)
      python kb/p4a_embed.py --max-rows 512  # dry run on a small slice
      python kb/p4a_embed.py --link          # write chunk.vec_row (needs the DB write lock)
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
VEC = ROOT / "kb/state/vec"
REPORT = ROOT / "kb/reports/p4a_embed.json"
LOG = ROOT / "kb/logs/p4a_embed.log"

MODEL = "nvidia/nemotron-3-embed-1b"
DIMS = 2048
URL = "https://integrate.api.nvidia.com/v1/embeddings"
MAX_ITEMS = 96
MAX_TOKENS = 42_000          # tokens per HTTP request (model context is far larger; keeps latency low)
MAX_CHARS = 12_000           # hard truncation per chunk text (~3k tokens)
WORKERS = 2
RETRY = [3, 8, 20, 45, 90]


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def api_key() -> str:
    cred = yaml.safe_load((Path(os.path.expanduser("~/.dsh/.credentials.yaml"))).read_text(encoding="utf-8"))
    return cred["refs"]["NVIDIA_API_KEY"]


def load_rows(con: duckdb.DuckDBPyConnection, max_rows: int | None) -> pa.Table:
    """One row per distinct text, ordered by norm_sha so the order is reproducible."""
    sql = ("SELECT norm_sha, min(chunk_id) AS chunk_id, count(*) AS n_chunks "
           "FROM chunk GROUP BY norm_sha ORDER BY norm_sha")
    if max_rows:
        sql = f"SELECT * FROM ({sql}) LIMIT {int(max_rows)}"
    tbl = con.execute(sql).arrow()
    if hasattr(tbl, "read_all"):
        tbl = tbl.read_all()
    log(f"distinct texts: {tbl.num_rows:,} (duplicate chunks: {int(sum(tbl['n_chunks'].to_pylist())) - tbl.num_rows:,})")
    return tbl


def fetch_texts(con: duckdb.DuckDBPyConnection, ids: list[str]) -> dict[str, str]:
    marks = ",".join("?" * len(ids))
    rows = con.execute(
        f"SELECT chunk_id, context_prefix, body FROM chunk WHERE chunk_id IN ({marks})", ids
    ).fetchall()
    out = {}
    for cid, pref, body in rows:
        text = ((pref or "") + " " + (body or "")).strip()
        out[cid] = text[:MAX_CHARS]
    return out


def make_batches(rows: pa.Table, con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Deterministic batches — resume correctness depends on this being stable."""
    batches, cur, cur_tok = [], [], 0
    ids = rows["chunk_id"].to_pylist()
    for start in range(0, len(ids), 4096):
        texts = fetch_texts(con, ids[start:start + 4096])
        for off in range(start, min(start + 4096, len(ids))):
            cid = ids[off]
            text = texts.get(cid) or ""
            est = max(1, len(text) // 4)
            if cur and (cur_tok + est > MAX_TOKENS or len(cur) >= MAX_ITEMS):
                batches.append({"row0": cur[0][0], "items": cur})
                cur, cur_tok = [], 0
            cur.append((off, text))
            cur_tok += est
    if cur:
        batches.append({"row0": cur[0][0], "items": cur})
    return batches


def embed_batch(batch: list[str], key: str, stats: dict) -> np.ndarray:
    body = json.dumps({"model": MODEL, "input": batch, "encoding_format": "float"}).encode()
    for attempt, delay in enumerate([0, *RETRY]):
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(URL, data=body, headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as fh:
                data = json.loads(fh.read().decode())
            vecs = np.asarray([d["embedding"] for d in data["data"]], dtype=np.float32)
            if vecs.shape != (len(batch), DIMS):
                raise ValueError(f"unexpected shape {vecs.shape}")
            stats["requests"] = stats.get("requests", 0) + 1
            stats["tokens"] = stats.get("tokens", 0) + int((data.get("usage") or {}).get("total_tokens") or 0)
            return vecs
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:300]
            stats["errors"] = stats.get("errors", 0) + 1
            if exc.code == 400 and len(batch) > 1:      # too long: split
                log(f"400 on batch of {len(batch)}; splitting ({detail[:120]})")
                half = len(batch) // 2
                return np.vstack([embed_batch(batch[:half], key, stats),
                                  embed_batch(batch[half:], key, stats)])
            log(f"HTTP {exc.code} attempt {attempt}: {detail}")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            stats["errors"] = stats.get("errors", 0) + 1
            log(f"error attempt {attempt}: {str(exc)[:160]}")
    raise RuntimeError("embedding request failed after retries")


def load_checkpoint() -> int:
    f = VEC / "checkpoint.json"
    if f.exists():
        return int(json.loads(f.read_text(encoding="utf-8")).get("next_batch", 0))
    return 0


def save_checkpoint(next_batch: int, stats: dict) -> None:
    VEC.mkdir(parents=True, exist_ok=True)
    (VEC / "checkpoint.json").write_text(json.dumps(
        {"next_batch": next_batch, "model": MODEL, "dims": DIMS,
         "requests": stats.get("requests", 0), "tokens": stats.get("tokens", 0),
         "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}), encoding="utf-8")


def run(max_rows: int | None) -> int:
    VEC.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    try:
        con.execute("SET memory_limit='700MB'")
        con.execute("SET threads=2")
        rows = load_rows(con, max_rows)
        pq.write_table(rows, VEC / "vec_rows.parquet")
        n = rows.num_rows
        batches = make_batches(rows, con)
    finally:
        con.close()
    log(f"{len(batches):,} batches for {n:,} rows (max {MAX_ITEMS} items / {MAX_TOKENS:,} est tokens each)")

    vec_path = VEC / "vec_fp16.npy"
    if vec_path.exists():
        mm = np.lib.format.open_memmap(vec_path, mode="r+")
        if mm.shape != (n, DIMS):
            raise SystemExit(f"existing memmap shape {mm.shape} != {(n, DIMS)}; delete {vec_path} to rebuild")
    else:
        mm = np.lib.format.open_memmap(vec_path, mode="w+", dtype=np.float16, shape=(n, DIMS))
    (VEC / "meta.json").write_text(json.dumps(
        {"model": MODEL, "dims": DIMS, "rows": n, "dtype": "float16", "normalised": True,
         "built": time.strftime("%Y-%m-%dT%H:%M:%S")}), encoding="utf-8")

    start_batch = load_checkpoint()
    prior = load_checkpoint_stats() if start_batch else {}
    if start_batch:
        log(f"resume at batch {start_batch:,}/{len(batches):,}")
    key = api_key()
    stats: dict = {}
    t0 = time.time()
    done = start_batch

    def work(idx: int) -> tuple[int, np.ndarray]:
        batch = batches[idx]["items"]
        return idx, embed_batch([t for _, t in batch], key, stats)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pending = [pool.submit(work, i) for i in range(start_batch, min(start_batch + 2 * WORKERS, len(batches)))]
        nxt = start_batch + 2 * WORKERS
        while pending:
            fut = pending.pop(0)
            idx, vecs = fut.result()
            vecs /= np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9)
            row0 = batches[idx]["row0"]
            mm[row0:row0 + len(vecs)] = vecs.astype(np.float16)
            done += 1
            if done % 10 == 0 or done == len(batches):
                mm.flush()
                save_checkpoint(done, stats)
            if nxt < len(batches):
                pending.append(pool.submit(work, nxt))
                nxt += 1
            if done % 40 == 0 or done == len(batches):
                el = time.time() - t0
                rate = (done - start_batch) / max(el, 1e-9)
                left = (len(batches) - done) / max(rate, 1e-9)
                log(f"batch {done:,}/{len(batches):,} rows {row0 + len(vecs):,}/{n:,} "
                    f"{rate:.2f} batch/s eta {left / 60:.1f} min errors {stats.get('errors', 0)}")
    mm.flush()
    save_checkpoint(done, stats)
    wall = time.time() - t0
    res = {"model": MODEL, "dims": DIMS, "rows": n, "batches": len(batches),
           "requests_total": stats.get("requests", 0) + int(prior.get("requests", 0)),
           "tokens_total": stats.get("tokens", 0) + int(prior.get("tokens", 0)),
           "errors": stats.get("errors", 0), "wall_seconds": round(wall, 1),
           "rows_per_second": round((done - start_batch) / max(wall, 1e-9), 1),
           "vec_bytes": vec_path.stat().st_size, "money_spent_usd": 0.0,
           "provider": "NIM free tier", "phase": "P4a"}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    log(f"done: {res['rows']:,} rows, {res['requests_total']:,} requests, "
        f"{res['tokens_total']:,} tokens, {res['vec_bytes'] / 1e9:.2f} GB, {wall / 60:.1f} min")
    return 0


def load_checkpoint_stats() -> dict:
    f = VEC / "checkpoint.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def link() -> int:
    """Point every chunk at its text's vector row (needs the write lock)."""
    ids = pq.read_table(VEC / "vec_rows.parquet")
    chunk_ids = ids.column("chunk_id").to_pylist()
    con = duckdb.connect(str(DB))
    try:
        con.execute("SET memory_limit='900MB'")
        con.execute("SET threads=2")
        con.execute("CREATE OR REPLACE TABLE _vec_map (chunk_id VARCHAR, row INTEGER)")
        con.register("_vec_map_df", pa.table(
            {"chunk_id": chunk_ids, "row": list(range(len(chunk_ids)))},
            schema=pa.schema([("chunk_id", pa.string()), ("row", pa.int32())])))
        con.execute("INSERT INTO _vec_map SELECT * FROM _vec_map_df")
        con.execute("UPDATE chunk SET vec_row = m.row FROM _vec_map m WHERE chunk.chunk_id = m.chunk_id")
        n_null = con.execute("SELECT count(*) FROM chunk WHERE vec_row IS NULL").fetchone()[0]
        n_vec = con.execute("SELECT count(DISTINCT vec_row) FROM chunk").fetchone()[0]
        con.execute("DROP TABLE _vec_map")
        log(f"linked: distinct vec_row {n_vec:,}, unlinked chunks {n_null:,}")
        (REPORT.with_name("p4a_embed_link.json")).write_text(json.dumps(
            {"distinct_vec_rows": int(n_vec), "unlinked_chunks": int(n_null), "rows": len(chunk_ids)}, indent=1),
            encoding="utf-8")
        return 0
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-rows", type=int, default=0)
    ap.add_argument("--link", action="store_true")
    args = ap.parse_args()
    if args.link:
        return link()
    return run(args.max_rows or None)


if __name__ == "__main__":
    raise SystemExit(main())
