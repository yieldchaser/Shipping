"""P4c step 1: build the deterministic packed calls for the whole frozen prose scope.

Plan §7.2 fixes the call shape: one document per call, consecutive chunks, <=3,500 chunk tokens,
<=6 chunk blocks, byte-identical system prompt. P4b measured the bake-off on exactly this shape;
P4c now applies it to every chunk in scope (86,607 chunks, 16,945 documents), so this script is a
pure function of `kb/state/kb.duckdb` and the pack constants below - no model calls, no sampling,
no randomness. It streams the scope ordered by (doc_id, ord) and writes one JSON line per pack to
`kb/state/p4c/packs.jsonl`, plus the coverage/stats record the P4c gate reports
(`coverage_of_frozen_scope_reported`).

Memory: the scope is streamed in fetchmany() batches; bodies/sentences/known entities are fetched
per batch of packs, so the process stays well under the 700 MB DuckDB cap. Runs read-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import duckdb  # noqa: E402

from p4b_gold import scope_sql  # noqa: E402  (same frozen scope definition P4a/P4b used)

ROOT = KB.parent
DB = ROOT / "kb/state/kb.duckdb"
OUT = ROOT / "kb/state/p4c"

PACK_MAX_TOKENS = 3500   # plan §7.2
PACK_MAX_CHUNKS = 6      # plan §7.2
KNOWN_MAX = 60           # bound for <known_entities>; deterministic by entity_id
STREAM_BATCH = 4000      # scope rows per fetch; the stream cursor lives across batches

SCOPE_DOCS = 16945       # frozen prose-only scope, plan §7.1
SCOPE_CHUNKS = 86607

SCOPE_COLS = ["chunk_id", "doc_id", "ord", "tokens", "n_ent", "doc_type", "publisher",
              "published_at", "title", "year", "section_class", "sec_item"]


def pack_rows(rows: list[dict]) -> list[list[dict]]:
    """Group scope rows (already ordered by doc_id, ord) into packed calls.

    Pure: same rows in, same packs out. A pack never crosses a document, never exceeds
    PACK_MAX_CHUNKS blocks, and never exceeds PACK_MAX_TOKENS chunk tokens (a single oversized
    chunk still forms its own pack - dropping it would shrink the frozen scope).
    """
    packs: list[list[dict]] = []
    cur: list[dict] = []
    tok = 0
    for row in rows:
        same_doc = bool(cur) and cur[0]["doc_id"] == row["doc_id"]
        fits = tok + int(row["tokens"] or 0) <= PACK_MAX_TOKENS and len(cur) < PACK_MAX_CHUNKS
        if cur and not (same_doc and fits):
            packs.append(cur)
            cur, tok = [], 0
        cur.append(row)
        tok += int(row["tokens"] or 0)
    if cur:
        packs.append(cur)
    return packs


def pack_record(n: int, rows: list[dict]) -> dict:
    """Pack envelope with everything except the chunk text (filled by enrich())."""
    first = rows[0]
    used = sum(int(r["tokens"] or 0) for r in rows)
    return {
        "n": n, "pack_id": f"p{n:06d}",
        "doc_id": first["doc_id"], "ord_first": int(first["ord"] or 0),
        "key": f"{first['doc_id']}|{'+'.join(r['chunk_id'] for r in rows)}",
        "chunk_ids": [r["chunk_id"] for r in rows],
        "tokens": used,
        "doc": {"publisher": first["publisher"], "doc_type": first["doc_type"],
                "published_at": str(first["published_at"])[:10] if first["published_at"] else None,
                "heading": str(first.get("title") or "")},  # title is DATE for some broker docs
        "year": first.get("year"),
        "section_class": first.get("section_class"),
    }


def enrich(con: duckdb.DuckDBPyConnection, packs: list[dict]) -> list[dict]:
    """Add numbered sentences + known entities to a batch of packs (one round trip each)."""
    cids = [c for p in packs for c in p["chunk_ids"]]
    ph = ",".join("?" * len(cids))
    bodies = dict(con.execute(f"select chunk_id, body from chunk where chunk_id in ({ph})",
                              cids).fetchall())
    sents: dict[str, list] = {}
    for cid, sid, a, b in con.execute(
            f"select chunk_id, sid, start_char, end_char from sentence where chunk_id in ({ph}) "
            "order by chunk_id, sid", cids).fetchall():
        sents.setdefault(cid, []).append([int(sid), bodies.get(cid, "")[a:b]])

    ent_ids: dict[str, list] = {}
    for cid, ids in con.execute(f"select chunk_id, entity_ids from chunk where chunk_id in ({ph})",
                                cids).fetchall():
        ent_ids[cid] = list(ids or [])
    all_ids = sorted({e for ids in ent_ids.values() for e in ids})
    ent: dict[str, dict] = {}
    if all_ids:
        ph2 = ",".join("?" * len(all_ids))
        for eid, etype, name, attrs in con.execute(
                "select entity_id, type, canonical_name, attrs from entity where entity_id in "
                f"({ph2})", all_ids).fetchall():
            try:
                a = json.loads(attrs) if isinstance(attrs, str) else (attrs or {})
            except ValueError:
                a = {}
            key = a.get("imo") or a.get("ticker") or a.get("cik") or ""
            ent[eid] = {"id": eid, "type": etype, "name": name, "key": str(key)}

    for p in packs:
        blocks = []
        known: dict[str, dict] = {}
        for i, cid in enumerate(p["chunk_ids"], start=1):
            blocks.append({"cid": f"c{i}", "sentences": sents.get(cid) or []})
            for k in ent_ids.get(cid) or []:
                if k in ent:
                    known.setdefault(k, ent[k])
        p["blocks"] = blocks
        p["known"] = [known[k] for k in sorted(known)][:KNOWN_MAX]
        p["known_ids"] = list(known)
    return packs


def stream_rows(con: duckdb.DuckDBPyConnection, batch_rows: int = STREAM_BATCH):
    """Yield scope rows ordered by (doc_id, ord) in `batch_rows` batches.

    The cursor stays open across yields, so the caller must not run another query on `con` while
    iterating: DuckDB invalidates a result when a new query starts on the same connection. That is
    why `iter_packs` takes a second, distinct read-only connection for the enrich queries - with a
    single connection the stream silently stopped after the first batch (4,000 of 86,607 chunks).
    """
    cur = con.execute(scope_sql() + " order by c.doc_id, c.ord")
    while True:
        batch = cur.fetchmany(batch_rows)
        if not batch:
            return
        rows = [dict(zip(SCOPE_COLS, r)) for r in batch]
        for r in rows:
            r["tokens"] = int(r["tokens"] or 0)
            r["ord"] = int(r["ord"] or 0)
        yield rows


def iter_packs(con: duckdb.DuckDBPyConnection, enrich_con: duckdb.DuckDBPyConnection,
               limit_docs: int = 0, batch_rows: int = STREAM_BATCH):
    """Yield enriched, numbered packs in (doc_id, ord) order. Streams; memory stays flat.

    `enrich_con` must be a second read-only connection to the same DB (see `stream_rows`): the scope
    cursor on `con` dies the moment another query runs on it.
    """
    n = 0
    carry: list[dict] = []
    docs_seen: set[str] = set()
    pending: list[dict] = []
    for rows in stream_rows(con, batch_rows):
        rows = carry + rows
        docs_seen.update(r["doc_id"] for r in rows)
        carry = []
        packs = pack_rows(rows)
        if packs and packs[-1][-1]["doc_id"] == rows[-1]["doc_id"]:
            carry = packs.pop()
        for pr in packs:
            pending.append(pack_record(n + len(pending), pr))
        if len(pending) >= 200:
            yield from enrich(enrich_con, pending)
            n += len(pending)
            pending = []
        if limit_docs and len(docs_seen) >= limit_docs:
            break
    if carry:
        pending.append(pack_record(n + len(pending), carry))
    if pending:
        yield from enrich(enrich_con, pending)


def add_pack(st: dict, p: dict) -> None:
    st["packs"] += 1
    st["chunks"] += len(p["chunk_ids"])
    st["tokens"] += p["tokens"]
    st["max_pack_tokens"] = max(st["max_pack_tokens"], p["tokens"])
    st["max_pack_chunks"] = max(st["max_pack_chunks"], len(p["chunk_ids"]))
    st["publishers"].add(p["doc"]["publisher"])
    st["doc_types"].add(p["doc"]["doc_type"])
    if p["year"] is not None:
        st["years"].add(int(p["year"]))
    st["docs"].add(p["doc_id"])


def initial_stats() -> dict:
    return {"packs": 0, "chunks": 0, "tokens": 0, "max_pack_tokens": 0, "max_pack_chunks": 0,
            "publishers": set(), "doc_types": set(), "years": set(), "docs": set()}


def summarise(st: dict, out_path: Path | None = None) -> dict:
    stats = {
        "packs": st["packs"], "chunks": st["chunks"], "docs": len(st["docs"]),
        "tokens": st["tokens"],
        "mean_pack_depth": round(st["chunks"] / st["packs"], 3) if st["packs"] else 0,
        "mean_pack_tokens": round(st["tokens"] / st["packs"], 1) if st["packs"] else 0,
        "max_pack_tokens": st["max_pack_tokens"], "max_pack_chunks": st["max_pack_chunks"],
        "publishers": len(st["publishers"]), "doc_types": len(st["doc_types"]),
        "years": sorted(st["years"]),
        "frozen_scope": {"chunks": SCOPE_CHUNKS, "docs": SCOPE_DOCS},
        "coverage_complete": (st["chunks"] == SCOPE_CHUNKS and len(st["docs"]) == SCOPE_DOCS),
    }
    if out_path:
        stats["out"] = str(out_path)
    return stats


def build(limit_docs: int = 0, out_path: Path | None = None, db: Path = DB) -> dict:
    """Stream the scope, pack it, enrich, and write packs.jsonl + stats. Returns the stats dict."""
    con = duckdb.connect(str(db), read_only=True)
    con.execute("SET memory_limit='700MB'")
    con.execute("SET threads=2")
    enrich_con = duckdb.connect(str(db), read_only=True)
    enrich_con.execute("SET memory_limit='700MB'")
    enrich_con.execute("SET threads=2")
    out_path = out_path or (OUT / "packs.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size:
        raise SystemExit(f"refusing to append: {out_path} already exists (delete it first)")
    st = initial_stats()
    with out_path.open("a", encoding="utf-8") as fh:
        for p in iter_packs(con, enrich_con, limit_docs):
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
            add_pack(st, p)
    con.close()
    enrich_con.close()
    stats = summarise(st, out_path)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pack_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-docs", type=int, default=0, help="dry run: first N documents only")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or (OUT / ("packs_dry.jsonl" if args.limit_docs else "packs.jsonl"))
    st = build(limit_docs=args.limit_docs, out_path=out)
    print("packs", st["packs"], "chunks", st["chunks"], "docs", st["docs"],
          "mean depth", st["mean_pack_depth"], "mean tokens", st["mean_pack_tokens"])
    print("max tokens", st["max_pack_tokens"], "max chunks", st["max_pack_chunks"],
          "publishers", st["publishers"], "doc_types", st["doc_types"], "years", st["years"])
    print("coverage_complete", st["coverage_complete"], "chunks", st["chunks"], "/",
          st["frozen_scope"]["chunks"], "docs", st["docs"], "/", st["frozen_scope"]["docs"])
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
