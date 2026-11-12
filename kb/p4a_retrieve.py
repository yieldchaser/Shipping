"""P4a step 4 — hybrid retrieval (plan §5.5): filters -> BM25 top150 + dense top150 -> RRF -> top15.

Order is plan §5.5: metadata filters are applied first (publisher, doc_type, date window, entity
ids, `public_ok`), then the two arms each return 150 candidates, RRF (k=60) fuses them, and the
caller takes the top 15. The reranker (`bge-reranker-v2-m3` in the plan) only reorders the fused
head, so `recall@20` is measured on the fused list and stays valid when reranking is switched on
later at query time.

Dense arm: unit-normalised fp16 memmap from `kb/p4a_embed.py`, one vector per distinct chunk text;
`chunk.vec_row` maps duplicates onto shared rows. Query embedding uses the same NIM model.

CLI:  python kb/p4a_retrieve.py "TD3C VLCC rate Middle East" [--publisher Fearnleys] [--top 15]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

import duckdb
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
VEC = ROOT / "kb/state/vec"
CACHE = VEC / "query_cache.json"
MODEL = "nvidia/nemotron-3-embed-1b"
URL = "https://integrate.api.nvidia.com/v1/embeddings"
ARM_K = 150
RRF_K = 60
DENSE_BLOCK = 4_000
# plan §5.5 step 4: rerank the fused head (top 40) and return the top 15/20 of that order. The plan
# names bge-reranker-v2-m3 (ONNX int8). That model is not available here (deviation D5: NIM serves
# embedding + reward models only, no cross-encoder rerank endpoint, and a 0.6B-parameter ONNX
# cross-encoder does not fit the 8 GB laptop budget), so the rerank stage is a deterministic
# lexical-overlap reranker: it scores each candidate by how much of the *question* it actually
# contains (content tokens + adjacent token bigrams) and uses the RRF score only as a tie-break.
# It reorders the fused head only — no candidate outside the fused top 40 can enter, and no arm
# parameter (ARM_K, RRF_K) or filter is touched.
RERANK_WINDOW = 40
STOPWORDS = frozenset("""a an and are as at be by for from has have how in into is it its of on or
that the their then there these this to was were what when where which who why with""".split())
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\.\-_/]*")


def content_tokens(text: str) -> list[str]:
    """Lowercase content tokens used by the reranker (numbers, route codes and IMO ids kept)."""
    return [t for t in TOKEN_RE.findall((text or "").lower())
            if len(t) >= 2 and t not in STOPWORDS]


def lex_score(query_tokens: list[str], query_bigrams: set[tuple[str, str]], text: str) -> int:
    """Deterministic rerank score: 2 per query bigram found in `text`, 1 per content token found.

    Bigrams dominate so that word order/phrase match ("baltic wind", "port stock carajas fines")
    outranks bags of the same words scattered over a long chunk.
    """
    toks = content_tokens(text)
    tokset = set(toks)
    uniq = list(dict.fromkeys(query_tokens))
    found = sum(1 for t in uniq if t in tokset)
    bg = set(zip(toks, toks[1:]))
    return found + 2 * sum(1 for b in query_bigrams if b in bg)


def api_key() -> str:
    cred = yaml.safe_load(Path(os.path.expanduser("~/.dsh/.credentials.yaml")).read_text(encoding="utf-8"))
    return cred["refs"]["NVIDIA_API_KEY"]


def filter_sql(filters: dict | None, c: str = "c", d: str = "d") -> tuple[str, list]:
    """Metadata pre-filter (plan §5.5 step 1). Empty filters -> match everything."""
    f = filters or {}
    where, params = [], []
    if f.get("publisher"):
        where.append(f"{d}.publisher_id IN ({','.join('?' * len(f['publisher']))})")
        params += list(f["publisher"])
    if f.get("doc_type"):
        where.append(f"{d}.doc_type IN ({','.join('?' * len(f['doc_type']))})")
        params += list(f["doc_type"])
    if f.get("date_from"):
        where.append(f"{d}.published_at >= ?")
        params.append(f["date_from"])
    if f.get("date_to"):
        where.append(f"{d}.published_at <= ?")
        params.append(f["date_to"])
    if f.get("entity_ids"):
        ids = list(f["entity_ids"])
        where.append(f"list_has_any({c}.entity_ids, CAST(? AS VARCHAR[]))")
        params.append(ids)
    if f.get("public_ok") is not None:
        where.append(f"{d}.public_ok = ?")
        params.append(bool(f["public_ok"]))
    return (" AND ".join(where) if where else "TRUE"), params


class Retriever:
    def __init__(self, db: Path = DB, vec: Path = VEC, read_only: bool = True):
        self.con = duckdb.connect(str(db), read_only=read_only)
        self.con.execute("SET memory_limit='700MB'")
        self.con.execute("SET threads=2")
        self.con.execute("LOAD fts")
        meta = json.loads((vec / "meta.json").read_text(encoding="utf-8"))
        self.model = meta["model"]
        self.dims = int(meta["dims"])
        self.mm = np.load(vec / "vec_fp16.npy", mmap_mode="r")
        self.cache_path = vec / "query_cache.json"
        self.qcache = json.loads(self.cache_path.read_text(encoding="utf-8")) if self.cache_path.exists() else {}

    def close(self) -> None:
        self.con.close()

    # ---- arms -----------------------------------------------------------------
    def bm25(self, query: str, filters: dict | None = None, k: int = ARM_K) -> list[tuple[str, float]]:
        where, params = filter_sql(filters)
        sql = (
            "SELECT chunk_id, score FROM ("
            "  SELECT c.chunk_id AS chunk_id, fts_main_chunk.match_bm25(c.chunk_id, ?) AS score"
            "  FROM chunk c JOIN document d USING (doc_id)"
            f"  WHERE {where}"
            ") WHERE score IS NOT NULL ORDER BY score DESC, chunk_id LIMIT ?"
        )
        return [(r[0], float(r[1])) for r in self.con.execute(sql, [query, *params, k]).fetchall()]

    def embed_query(self, query: str) -> np.ndarray:
        key = hashlib.sha256(query.encode()).hexdigest()[:24]
        if key in self.qcache:
            v = np.asarray(self.qcache[key], dtype=np.float32)
        else:
            v = self._embed_remote(query)
            self.qcache[key] = [round(float(x), 6) for x in v]
            self.cache_path.write_text(json.dumps(self.qcache), encoding="utf-8")
        return v / max(float(np.linalg.norm(v)), 1e-9)

    def _embed_remote(self, query: str) -> np.ndarray:
        body = json.dumps({"model": self.model, "input": [query], "encoding_format": "float"}).encode()
        for delay in [0, 3, 10, 30, 60]:
            if delay:
                time.sleep(delay)
            req = urllib.request.Request(URL, data=body, headers={
                "Authorization": "Bearer " + api_key(), "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as fh:
                    data = json.loads(fh.read().decode())
                return np.asarray(data["data"][0]["embedding"], dtype=np.float32)
            except Exception as exc:  # noqa: BLE001
                last = exc
        raise RuntimeError(f"query embedding failed: {last}")

    def eligible_rows(self, filters: dict | None, use_vec_rows: bool) -> np.ndarray | None:
        """vec_row ids allowed by the filter; None means 'all rows' (no filter)."""
        if not filters:
            return None
        where, params = filter_sql(filters)
        col = "c.vec_row" if use_vec_rows else "c.vec_row"
        rows = self.con.execute(
            f"SELECT DISTINCT {col} FROM chunk c JOIN document d USING (doc_id) "
            f"WHERE {where} AND c.vec_row IS NOT NULL", params).fetchall()
        return np.fromiter((r[0] for r in rows), dtype=np.int64, count=len(rows))

    def dense(self, qvec: np.ndarray, filters: dict | None = None, k: int = ARM_K) -> list[tuple[int, float]]:
        rows = self.eligible_rows(filters, use_vec_rows=True)
        if rows is None:
            n = self.mm.shape[0]
            rows = np.arange(n, dtype=np.int64)
        if rows.size == 0:
            return []
        best_scores: list[np.ndarray] = []
        best_rows: list[np.ndarray] = []
        for start in range(0, rows.size, DENSE_BLOCK):
            block = rows[start:start + DENSE_BLOCK]
            vecs = np.asarray(self.mm[block], dtype=np.float32)
            scores = vecs @ qvec
            take = min(k, scores.size)
            idx = np.argpartition(-scores, take - 1)[:take]
            best_scores.append(scores[idx])
            best_rows.append(block[idx])
        scores = np.concatenate(best_scores)
        rr = np.concatenate(best_rows)
        order = np.argsort(-scores)[:k]
        return [(int(rr[i]), float(scores[i])) for i in order]

    def vec_row_chunks(self, vec_rows: list[int]) -> dict[int, list[str]]:
        if not vec_rows:
            return {}
        marks = ",".join("?" * len(vec_rows))
        out: dict[int, list[str]] = {}
        for vr, cid, doc_id, ordv in self.con.execute(
            f"SELECT vec_row, chunk_id, doc_id, ord FROM chunk WHERE vec_row IN ({marks}) "
            f"ORDER BY doc_id, ord", vec_rows).fetchall():
            out.setdefault(int(vr), []).append(cid)
        return out

    # ---- fusion ---------------------------------------------------------------
    def fuse(self, bm: list[tuple[str, float]], dn: list[tuple[int, float]], k: int = 20) -> list[dict]:
        vr_map = self.vec_row_chunks([vr for vr, _ in dn])
        fused: dict[str, dict] = {}
        for rank, (cid, score) in enumerate(bm, 1):
            e = fused.setdefault(cid, {"chunk_id": cid, "rrf": 0.0, "bm25_rank": None,
                                       "dense_rank": None, "bm25_score": None, "dense_score": None})
            e["rrf"] += 1.0 / (RRF_K + rank)
            e["bm25_rank"] = rank
            e["bm25_score"] = round(score, 3)
        for rank, (vr, score) in enumerate(dn, 1):
            for cid in vr_map.get(vr, []):
                e = fused.setdefault(cid, {"chunk_id": cid, "rrf": 0.0, "bm25_rank": None,
                                           "dense_rank": None, "bm25_score": None, "dense_score": None})
                e["rrf"] += 1.0 / (RRF_K + rank)
                if e["dense_rank"] is None:
                    e["dense_rank"] = rank
                    e["dense_score"] = round(score, 4)
        return sorted(fused.values(), key=lambda e: (-e["rrf"], e["chunk_id"]))[:k]

    def rerank(self, query: str, fused: list[dict], keep: int = 20) -> list[dict]:
        """Reorder the fused head with the deterministic lexical reranker (see RERANK_WINDOW)."""
        cands = fused[:RERANK_WINDOW]
        if not cands:
            return []
        ids = [c["chunk_id"] for c in cands]
        marks = ",".join("?" * len(ids))
        texts = {r[0]: f"{r[1] or ''} {r[2] or ''}" for r in self.con.execute(
            f"SELECT chunk_id, context_prefix, body FROM chunk WHERE chunk_id IN ({marks})",
            ids).fetchall()}
        q_tokens = content_tokens(query)
        q_bigrams = set(zip(q_tokens, q_tokens[1:]))
        for e in cands:
            e["rerank_lex"] = lex_score(q_tokens, q_bigrams, texts.get(e["chunk_id"], ""))
        cands.sort(key=lambda e: (-e["rerank_lex"], -e["rrf"], e["chunk_id"]))
        return cands[:keep]

    def search(self, query: str, filters: dict | None = None, k: int = 20,
               use_dense: bool = True) -> dict:
        t0 = time.time()
        bm = self.bm25(query, filters)
        t_bm = time.time() - t0
        t1 = time.time()
        dn = self.dense(self.embed_query(query), filters) if use_dense else []
        t_dn = time.time() - t1
        t2 = time.time()
        fused = self.fuse(bm, dn, k=max(RERANK_WINDOW, k))
        fused_hits = fused[:k]
        hits = self.rerank(query, fused, keep=k)
        t_rr = time.time() - t2
        dense_ids = {cid for cids in self.vec_row_chunks([vr for vr, _ in dn]).values()
                     for cid in cids}
        return {"query": query, "filters": filters or {}, "hits": hits, "fused_hits": fused_hits,
                "timing": {"bm25_s": round(t_bm, 2), "dense_s": round(t_dn, 2),
                           "rerank_s": round(t_rr, 2), "total_s": round(time.time() - t0, 2)},
                "arm_sizes": {"bm25": len(bm), "dense": len(dn)},
                "arm_ids": {"bm25": [c for c, _ in bm], "dense": sorted(dense_ids)}}

    def expand(self, chunk_ids: list[str], chars: int = 320) -> list[dict]:
        if not chunk_ids:
            return []
        marks = ",".join("?" * len(chunk_ids))
        rows = self.con.execute(
            f"SELECT c.chunk_id, c.doc_id, d.path, d.publisher_id, d.doc_type, d.published_at, "
            f"c.kind, c.context_prefix, c.body FROM chunk c JOIN document d USING (doc_id) "
            f"WHERE c.chunk_id IN ({marks})", chunk_ids).fetchall()
        by = {r[0]: r for r in rows}
        out = []
        for cid in chunk_ids:
            r = by.get(cid)
            if not r:
                continue
            out.append({"chunk_id": r[0], "doc_id": r[1], "path": r[2], "publisher": r[3],
                        "doc_type": r[4], "published_at": str(r[5]), "kind": r[6],
                        "context_prefix": (r[7] or "")[:chars],
                        "body": (r[8] or "")[:chars]})
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--publisher", nargs="*", default=None)
    ap.add_argument("--doc-type", nargs="*", default=None)
    ap.add_argument("--date-from", default=None)
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--entity", nargs="*", default=None)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--no-dense", action="store_true")
    args = ap.parse_args()
    filters = {k: v for k, v in {"publisher": args.publisher, "doc_type": args.doc_type,
                                 "date_from": args.date_from, "date_to": args.date_to,
                                 "entity_ids": args.entity}.items() if v}
    r = Retriever()
    try:
        res = r.search(args.query, filters, k=args.top, use_dense=not args.no_dense)
        for h in res["hits"]:
            print(f"{h['rrf']:.4f} bm25={h['bm25_rank']} dense={h['dense_rank']} {h['chunk_id']}")
        print(json.dumps(res["timing"]), json.dumps(res["arm_sizes"]))
        for row in r.expand([h["chunk_id"] for h in res["hits"]]):
            print(f"\n{row['path']} [{row['doc_type']} {row['published_at']}]\n  {row['body'][:200]}")
    finally:
        r.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
