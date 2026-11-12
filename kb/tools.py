"""P7 tools (plan §9): typed, read-only accessors the answer engine may call.

Design note (5 lines):
1. Every tool is a plain function over `kb/state/kb.duckdb` opened read-only, so the
   answer engine can never mutate the knowledge base and tests can run offline.
2. `sql` is restricted to the `v_*` views with a hard 500-row cap and a 10 s watchdog
   (plan §9); any write keyword or non-`v_` relation is rejected before execution.
3. `search` reuses the P4a BM25 arm (FTS index in the KB DB) and optionally the embedding
   arm; results are chunk-level and always carry doc path, publisher and published_at.
4. `graph` does a bounded BFS (hops <= 2) over the P5 `edge` table; `ppr` uses the P5
   `ppr_nodes.parquet` export when present and falls back to a local power iteration.
5. `summary` reads the P6 time tree (index.json), `gaps` reads `v_gaps`, `cite` returns
   path/quote for any obs/chunk/event/claim/document handle.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
KB_DB = ROOT / "kb/state/kb.duckdb"
P5_DIR = ROOT / "kb/state/p5"
P6_INDEX = ROOT / "kb/state/p6/index.json"
VEC_DIR = ROOT / "kb/state/vec"

ROW_CAP = 500
TIMEOUT_S = 10.0
MAX_HOPS = 2
BFS_NODE_CAP = 400

WRITE_WORDS = re.compile(
    r"\b(insert|update|delete|create|alter|drop|attach|detach|copy|export|import|pragma|"
    r"install|load|call|set|reset|checkpoint|vacuum|truncate|replace)\b", re.I)
RELATION_RE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][\w.]*)", re.I)
CTE_RE = re.compile(r"\b(?:with|,)\s*(?:recursive\s+)?([A-Za-z_]\w*)\s+as\s*\(", re.I)


class ToolError(Exception):
    """A tool rejected the call or could not answer it."""


def connect(db: Path | str = KB_DB, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db), read_only=read_only)
    con.execute("SET memory_limit='700MB'")
    con.execute("SET threads=2")
    return con


# --------------------------------------------------------------------- sql
def _guard_sql(query: str) -> str:
    q = (query or "").strip().rstrip(";")
    if not q:
        raise ToolError("empty query")
    if ";" in q:
        raise ToolError("one statement only")
    if WRITE_WORDS.search(q):
        raise ToolError("only read-only SELECT on v_* views is allowed")
    if not re.match(r"^\s*(select|with)\b", q, re.I):
        raise ToolError("query must start with SELECT or WITH")
    rels = RELATION_RE.findall(q)
    if not rels:
        raise ToolError("query must read from a v_* view")
    ctes = {name.lower() for name in CTE_RE.findall(q)}
    for rel in rels:
        base = rel.split(".")[-1]
        if base.lower() in ctes:
            continue
        if not base.lower().startswith("v_"):
            raise ToolError(f"relation {rel!r} is not a v_* view")
    return q


def _run_with_timeout(con, sql: str, params: list[Any], timeout_s: float = TIMEOUT_S):
    """Run one statement, interrupt it if it exceeds `timeout_s`."""
    fired = {"hit": False}

    def _kill():
        fired["hit"] = True
        try:
            con.interrupt()
        except Exception:  # noqa: BLE001 - interrupt is best effort
            pass

    timer = threading.Timer(timeout_s, _kill)
    timer.daemon = True
    timer.start()
    try:
        return con.execute(sql, params).fetchall()
    except Exception as exc:  # noqa: BLE001
        if fired["hit"]:
            raise ToolError(f"query exceeded {timeout_s:.0f}s") from exc
        raise ToolError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        timer.cancel()


def sql(query: str, con=None, cap: int = ROW_CAP, timeout_s: float = TIMEOUT_S,
        params: list | None = None) -> dict:
    """Run a read-only query against the `v_*` views. Returns columns + rows (capped)."""
    q = _guard_sql(query)
    return _query(q, con=con, cap=cap, timeout_s=timeout_s, params=params)


def _query(query: str, con=None, cap: int = ROW_CAP, timeout_s: float = TIMEOUT_S,
           params: list | None = None) -> dict:
    """Internal executor for trusted modules (no view guard). Never LLM-facing."""
    own = con is None
    con = con or connect()
    try:
        wrapped = f"SELECT * FROM ({query}) _q LIMIT {int(cap)}"
        rows = _run_with_timeout(con, wrapped, list(params or []), timeout_s)
        cols = [d[0] for d in con.description]
        return {"columns": cols, "rows": [list(r) for r in rows], "truncated": len(rows) >= cap}
    finally:
        if own:
            con.close()


# ------------------------------------------------------------------ search
_FILTER_COLUMNS = {
    "publisher": "d.publisher_id",
    "publisher_id": "d.publisher_id",
    "doc_type": "d.doc_type",
    "published_from": "d.published_at",
    "published_to": "d.published_at",
    "doc_id": "d.doc_id",
    "year": "year(d.published_at)",
}


def filter_sql(filters: dict | None, c: str = "c", d: str = "d") -> tuple[str, list]:
    """Translate a filter dict into a WHERE fragment + params (shared with p4a)."""
    parts, params = ["1=1"], []
    for key, val in (filters or {}).items():
        col = _FILTER_COLUMNS.get(key)
        if col is None:
            raise ToolError(f"unknown filter {key!r}")
        col = col.replace("d.", f"{d}.").replace("c.", f"{c}.")
        if key == "published_from":
            parts.append(f"{col} >= ?")
            params.append(val)
        elif key == "published_to":
            parts.append(f"{col} <= ?")
            params.append(val)
        elif isinstance(val, (list, tuple, set)):
            if not val:
                continue
            parts.append(f"{col} IN ({','.join('?' * len(val))})")
            params.extend(list(val))
        else:
            parts.append(f"{col} = ?")
            params.append(val)
    return " AND ".join(parts), params


SNIPPET_CHARS = 420


def search(query: str, filters: dict | None = None, k: int = 20, con=None) -> dict:
    """Lexical (BM25) search over chunk text, with optional metadata filters."""
    if not (query or "").strip():
        raise ToolError("empty query")
    k = max(1, min(int(k), 50))
    own = con is None
    con = con or connect()
    try:
        try:
            con.execute("LOAD fts")
        except Exception:  # fts already loaded or unavailable
            pass
        where, params = filter_sql(filters)
        sql_txt = (
            "SELECT c.chunk_id, c.doc_id, d.path, d.publisher_id, d.doc_type, d.published_at,"
            "       c.body, fts_main_chunk.match_bm25(c.chunk_id, ?) AS score"
            "  FROM chunk c JOIN document d USING (doc_id)"
            f" WHERE {where} AND c.body IS NOT NULL"
            " ORDER BY score DESC NULLS LAST, c.chunk_id LIMIT ?")
        try:
            rows = con.execute(sql_txt, [query, *params, k]).fetchall()
        except Exception as exc:  # noqa: BLE001 - FTS index missing -> lexical fallback
            terms = [t for t in re.findall(r"[a-z0-9]{3,}", query.lower())][:6]
            if not terms:
                raise ToolError(f"search failed: {exc}") from exc
            like = " OR ".join(["c.body ILIKE ?"] * len(terms))
            rows = con.execute(
                "SELECT c.chunk_id, c.doc_id, d.path, d.publisher_id, d.doc_type, d.published_at,"
                "       c.body, 0.0 AS score"
                "  FROM chunk c JOIN document d USING (doc_id)"
                f" WHERE {where} AND {like} LIMIT ?",
                [*params, *[f"%{t}%" for t in terms], k]).fetchall()
        out = []
        for r in rows:
            body = r[6] or ""
            out.append({"chunk_id": r[0], "doc_id": r[1], "path": r[2], "publisher": r[3],
                        "doc_type": r[4], "published_at": str(r[5]) if r[5] else None,
                        "score": round(float(r[7] or 0.0), 4),
                        "snippet": body[:SNIPPET_CHARS].replace("\n", " ")})
        return {"query": query, "results": out}
    finally:
        if own:
            con.close()


# ------------------------------------------------------------------- graph
def _adjacency(con, window: tuple[str | None, str | None] | None, types: list[str] | None) -> list[dict]:
    where, params = ["e.status = 'active'"], []
    if window:
        lo, hi = window
        if lo:
            where.append("(e.valid_to IS NULL OR e.valid_to >= ?)")
            params.append(lo)
        if hi:
            where.append("e.valid_from <= ?")
            params.append(hi)
    if types:
        where.append(f"e.type IN ({','.join('?' * len(types))})")
        params.extend(types)
    try:
        rows = con.execute(
            "SELECT e.src, e.dst, e.type, e.valid_from, e.valid_to, e.doc_id, e.chunk_id"
            f"  FROM edge e WHERE {' AND '.join(where)} LIMIT 5000", params).fetchall()
    except Exception as exc:  # noqa: BLE001 - table absent on older DBs
        raise ToolError(f"graph unavailable: {exc}") from exc
    return [{"src": r[0], "dst": r[1], "type": r[2],
             "valid_from": str(r[3]) if r[3] else None,
             "valid_to": str(r[4]) if r[4] else None,
             "doc_id": r[5], "chunk_id": r[6]} for r in rows]


def graph(entity_id: str, window: tuple[str | None, str | None] | None = None,
          hops: int = 1, types: list[str] | None = None, con=None) -> dict:
    """Bounded BFS around `entity_id` over the P5 edge table."""
    hops = max(1, min(int(hops), MAX_HOPS))
    own = con is None
    con = con or connect()
    try:
        edges = _adjacency(con, window, types)
        frontier, seen_nodes, seen_edges, depth_of = [entity_id], {entity_id}, [], {entity_id: 0}
        for _ in range(hops):
            nxt = []
            for node in frontier:
                for e in edges:
                    if e["src"] == node and e["dst"] not in seen_nodes:
                        nxt.append(e["dst"])
                        depth_of[e["dst"]] = depth_of[node] + 1
                    if e["dst"] == node and e["src"] not in seen_nodes:
                        nxt.append(e["src"])
                        depth_of[e["src"]] = depth_of[node] + 1
                    if node in (e["src"], e["dst"]) and e not in seen_edges:
                        seen_edges.append(e)
            seen_nodes |= set(nxt)
            if len(seen_nodes) > BFS_NODE_CAP:
                break
            frontier = nxt
            if not frontier:
                break
        nodes = []
        for nid in sorted(seen_nodes):
            name = nid
            row = con.execute(
                "SELECT type, canonical_name FROM entity WHERE entity_id = ? LIMIT 1", [nid]).fetchone()
            if row:
                name = f"{row[1]} ({row[0]})"
            nodes.append({"entity_id": nid, "label": name, "depth": depth_of.get(nid, 0)})
        return {"seed": entity_id, "hops": hops, "nodes": nodes[:BFS_NODE_CAP],
                "edges": seen_edges[:BFS_NODE_CAP]}
    finally:
        if own:
            con.close()


# --------------------------------------------------------------------- ppr
def _fallback_ppr(edges: list[dict], seeds: list[str], alpha: float = 0.85, iters: int = 20) -> dict:
    nodes = sorted({e["src"] for e in edges} | {e["dst"] for e in edges} | set(seeds))
    if not nodes:
        return {"nodes": [], "edges": []}
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    import numpy as np
    A = np.zeros((n, n), dtype=np.float64)
    for e in edges:
        if e["src"] in idx and e["dst"] in idx and e["src"] != e["dst"]:
            A[idx[e["src"]], idx[e["dst"]]] = 1.0
            A[idx[e["dst"]], idx[e["src"]]] = 1.0
    deg = A.sum(axis=1, keepdims=True)
    deg[deg == 0] = 1.0
    W = A / deg
    p = np.zeros(n)
    for s in seeds:
        if s in idx:
            p[idx[s]] = 1.0 / len(seeds)
    if p.sum() == 0:
        p[:] = 1.0 / n
    for _ in range(iters):
        p = alpha * (W.T @ p) + (1.0 - alpha) * p
    order = np.argsort(-p)[:40]
    return {"nodes": [{"entity_id": nodes[i], "score": round(float(p[i]), 6)} for i in order],
            "edges": edges[:200], "method": "power_iteration"}


def ppr(seed_entities: list[str] | str, window: tuple[str | None, str | None] | None = None,
        con=None) -> dict:
    """Personalised PageRank over the edge graph (P5 parquet export when available)."""
    seeds = [seed_entities] if isinstance(seed_entities, str) else list(seed_entities or [])
    if not seeds:
        raise ToolError("ppr needs at least one seed entity")
    nodes_path = P5_DIR / "ppr_nodes.parquet"
    edges_path = P5_DIR / "ppr_edges.parquet"
    if nodes_path.exists() and edges_path.exists():
        own = con is None
        con = con or connect()
        try:
            placeholders = ",".join("?" * len(seeds))
            rows = con.execute(
                "SELECT * FROM read_parquet(?) WHERE entity_id IN (" + placeholders + ") LIMIT 40",
                [str(nodes_path), *seeds]).fetchall()
            if rows:
                cols = [d[0] for d in con.description]
                return {"nodes": [dict(zip(cols, r)) for r in rows],
                        "edges": [], "method": "p5_ppr_export"}
        except Exception:  # noqa: BLE001 - fall through to local iteration
            pass
        finally:
            if own:
                con.close()
    own = con is None
    con = con or connect()
    try:
        return _fallback_ppr(_adjacency(con, window, None), seeds)
    finally:
        if own:
            con.close()


# ----------------------------------------------------------------- summary
def _p6_index(path: Path | str | None = None) -> dict:
    path = Path(path) if path is not None else P6_INDEX
    if not path.exists():
        raise ToolError("P6 time tree not built yet (kb/state/p6/index.json missing)")
    return json.loads(path.read_text(encoding="utf-8"))


def summary(segment: str | None = None, grain: str | None = None, period: str | None = None,
            index: dict | None = None, limit: int = 12) -> dict:
    """Return P6 time-tree nodes: summary text, citations and input hashes."""
    idx = index if index is not None else _p6_index()
    want_seg = (segment or "").lower()
    out = []
    for nid, meta in idx.items():
        if want_seg and (meta.get("segment") or "").lower() != want_seg:
            continue
        if grain and meta.get("grain") != grain:
            continue
        if period and meta.get("period") != period:
            continue
        out.append({"node_id": nid, "segment": meta.get("segment"), "grain": meta.get("grain"),
                    "period": meta.get("period"), "summary": meta.get("summary"),
                    "cites": [f"{c.get('kind')}:{c.get('ref')}" if isinstance(c, dict) else c
                              for c in (meta.get("cites") or [])]})
    order = {"month": 2, "quarter": 1, "year": 0}
    out.sort(key=lambda r: (order.get(r["grain"], 9), r["period"] or ""), reverse=True)
    return {"segment": segment, "grain": grain, "period": period, "nodes": out[:limit]}


# -------------------------------------------------------------------- gaps
def gaps(scope: str | None = None, key: str | None = None, window: tuple[str | None, str | None] | None = None,
         con=None) -> dict:
    """Declared coverage gaps (P2 `v_gaps`) for a scope/key/window."""
    where, params = ["1=1"], []
    if scope:
        where.append("scope = ?")
        params.append(scope)
    if key:
        where.append("key ILIKE ?")
        params.append(f"%{key}%")
    if window:
        lo, hi = window
        if lo:
            where.append("(gap_to IS NULL OR gap_to >= ?)")
            params.append(lo)
        if hi:
            where.append("gap_from <= ?")
            params.append(hi)
    own = con is None
    con = con or connect()
    try:
        rows = con.execute(
            "SELECT scope, key, gap_from, gap_to, reason, source FROM v_gaps"
            f" WHERE {' AND '.join(where)} LIMIT 200", params).fetchall()
        return {"gaps": [{"scope": r[0], "key": r[1], "gap_from": str(r[2]) if r[2] else None,
                          "gap_to": str(r[3]) if r[3] else None, "reason": r[4],
                          "source": r[5]} for r in rows]}
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f"gaps unavailable: {exc}") from exc
    finally:
        if own:
            con.close()


# -------------------------------------------------------------------- cite
CITE_KINDS = ("obs", "chunk", "event", "claim", "doc", "series", "txn")


def parse_cite(handle: str) -> tuple[str, str]:
    if ":" not in (handle or ""):
        raise ToolError(f"bad cite handle {handle!r} (want kind:id)")
    kind, ident = handle.split(":", 1)
    kind = kind.strip().lower()
    if kind not in CITE_KINDS:
        raise ToolError(f"unknown cite kind {kind!r}")
    if not ident.strip():
        raise ToolError("empty cite id")
    return kind, ident.strip()


def cite(handle: str, con=None) -> dict:
    """Resolve a citation handle to its source path, locator and quote."""
    kind, ident = parse_cite(handle)
    own = con is None
    con = con or connect()
    try:
        if kind == "obs":
            row = con.execute(
                "SELECT o.obs_id, o.series_id, o.period_from, o.period_to, o.value, o.unit, o.raw_cell,"
                "       o.published_at, d.path, d.publisher_id"
                "  FROM observation o LEFT JOIN document d USING (doc_id) WHERE o.obs_id = ? LIMIT 1",
                [int(ident)]).fetchone()
            if not row:
                raise ToolError(f"observation {ident} not found")
            return {"kind": kind, "id": ident, "path": row[8], "publisher": row[9],
                    "published_at": str(row[7]) if row[7] else None,
                    "locator": {"series_id": row[1], "period_from": str(row[2]) if row[2] else None,
                                "period_to": str(row[3]) if row[3] else None},
                    "quote": f"{row[6] if row[6] is not None else row[4]} {row[5] or ''}".strip()}
        if kind == "chunk":
            row = con.execute(
                "SELECT c.chunk_id, d.path, d.publisher_id, d.published_at, c.body, c.section_id, c.ord"
                "  FROM chunk c JOIN document d USING (doc_id) WHERE c.chunk_id = ? LIMIT 1",
                [ident]).fetchone()
            if not row:
                raise ToolError(f"chunk {ident} not found")
            return {"kind": kind, "id": ident, "path": row[1], "publisher": row[2],
                    "published_at": str(row[3]) if row[3] else None,
                    "locator": {"section_id": row[5], "ord": row[6]}, "quote": (row[4] or "")[:1500]}
        if kind == "event":
            row = con.execute(
                "SELECT e.event_id, e.type, e.summary, e.occurred_from, e.occurred_to, e.quote,"
                "       d.path, d.publisher_id"
                "  FROM event e LEFT JOIN document d USING (doc_id) WHERE e.event_id = ? LIMIT 1",
                [ident]).fetchone()
            if not row:
                raise ToolError(f"event {ident} not found")
            return {"kind": kind, "id": ident, "path": row[6], "publisher": row[7],
                    "locator": {"type": row[1], "occurred_from": str(row[3]) if row[3] else None,
                                "occurred_to": str(row[4]) if row[4] else None},
                    "quote": row[5] or row[2]}
        if kind == "claim":
            row = con.execute(
                "SELECT c.claim_id, c.kind, c.text_printed, c.horizon, c.direction, c.quote,"
                "       d.path, d.publisher_id"
                "  FROM claim c LEFT JOIN document d USING (doc_id) WHERE c.claim_id = ? LIMIT 1",
                [ident]).fetchone()
            if not row:
                raise ToolError(f"claim {ident} not found")
            return {"kind": kind, "id": ident, "path": row[6], "publisher": row[7],
                    "locator": {"kind": row[1], "horizon": row[3], "direction": row[4]},
                    "quote": row[5] or row[2]}
        if kind == "doc":
            row = con.execute(
                "SELECT doc_id, path, publisher_id, doc_type, published_at, title FROM document"
                " WHERE doc_id = ? OR path = ? LIMIT 1", [ident, ident]).fetchone()
            if not row:
                raise ToolError(f"document {ident} not found")
            return {"kind": kind, "id": ident, "path": row[1], "publisher": row[2],
                    "published_at": str(row[4]) if row[4] else None,
                    "locator": {"doc_type": row[3], "title": row[5]}, "quote": row[5]}
        if kind == "series":
            row = con.execute(
                "SELECT series_id, name, unit, currency, basis FROM series WHERE series_id = ? LIMIT 1",
                [ident]).fetchone()
            if not row:
                raise ToolError(f"series {ident} not found")
            return {"kind": kind, "id": ident, "path": None, "publisher": None, "published_at": None,
                    "locator": {"unit": row[2], "currency": row[3], "basis": row[4]}, "quote": row[1]}
        row = con.execute(
            "SELECT txn_id, kind, vessel_id, date_from, date_to, terms, status FROM transaction"
            " WHERE txn_id = ? LIMIT 1", [ident]).fetchone()
        if not row:
            raise ToolError(f"transaction {ident} not found")
        return {"kind": kind, "id": ident, "path": None, "publisher": None,
                "published_at": str(row[4]) if row[4] else None,
                "locator": {"kind": row[1], "vessel_id": row[2], "date_from": str(row[3]) if row[3] else None},
                "quote": str(row[5])}
    finally:
        if own:
            con.close()


# ------------------------------------------------------------------ registry
TOOLS = [
    {"name": "search", "description": "Lexical search over document chunks; returns chunk ids, doc ids, paths, publishers, dates and snippets.",
     "parameters": {"query": "str", "filters?": "dict", "k?": "int"}},
    {"name": "sql", "description": "Read-only SQL over the v_* views (rates, fixtures, sales, demolitions, newbuildings, TC assessments, commodity flows, series, gaps). Max 500 rows.",
     "parameters": {"query": "str"}},
    {"name": "graph", "description": "Entity neighbourhood (hops<=2) over typed edges with optional date window.",
     "parameters": {"entity_id": "str", "window?": "[from,to]", "hops?": "int", "types?": "[str]"}},
    {"name": "ppr", "description": "Personalised PageRank around seed entities; ranks related entities.",
     "parameters": {"seed_entities": "[str]", "window?": "[from,to]"}},
    {"name": "summary", "description": "Time-tree summary nodes (segment x month/quarter/year) with citations.",
     "parameters": {"segment?": "str", "grain?": "str", "period?": "str"}},
    {"name": "gaps", "description": "Declared coverage gaps for a scope/key/window; use to say what the data does not cover.",
     "parameters": {"scope?": "str", "key?": "str", "window?": "[from,to]"}},
    {"name": "cite", "description": "Resolve an obs/chunk/event/claim/doc/series/txn handle to path, locator and quote.",
     "parameters": {"handle": "str"}},
]
TOOL_NAMES = [t["name"] for t in TOOLS]


def dispatch(name: str, args: dict | None = None, con=None) -> dict:
    """Call one tool by name with a JSON-ish argument dict."""
    args = dict(args or {})
    if name == "search":
        return search(args.get("query", ""), args.get("filters"), int(args.get("k", 20)), con=con)
    if name == "sql":
        return sql(args.get("query", ""), con=con)
    if name == "graph":
        window = args.get("window")
        return graph(args["entity_id"], tuple(window) if window else None,
                     int(args.get("hops", 1)), args.get("types"), con=con)
    if name == "ppr":
        window = args.get("window")
        return ppr(args.get("seed_entities") or args.get("entity_id") or [],
                   tuple(window) if window else None, con=con)
    if name == "summary":
        return summary(args.get("segment"), args.get("grain"), args.get("period"))
    if name == "gaps":
        window = args.get("window")
        return gaps(args.get("scope"), args.get("key"), tuple(window) if window else None, con=con)
    if name == "cite":
        return cite(args.get("handle", ""), con=con)
    raise ToolError(f"unknown tool {name!r}; known: {', '.join(TOOL_NAMES)}")
