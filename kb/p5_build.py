"""P5 (plan §11): gate P4c kept records into `edge`/`event`/`claim`, resolve ids, attach to
transactions, export the PPR graph.

Design note (why this shape):

1. Input is P4c's gated stream, one row per chunk; the ladder is applied here by taking the *first*
   file that carries a chunk (`--gated` paths are ordered highest rung first, default: the union
   export, then bulk/glean/retry/esc/glm2). Every kept record of that row is a candidate.
2. The quote is re-sliced by code from `chunk.body` + `sentence` offsets (§7.4 rule 2, D7). A record
   whose sids no longer slice, whose printed number is not in the re-sliced quote, or whose entity
   ref does not resolve after provisioning is *dropped and counted*, never inserted. Gate one is an
   independent re-slice audit over the inserted rows, not a re-read of the build's own counters.
3. Ids: `status='merged'` registry rows are replaced by `attrs.merged_into` (chain-followed, <8
   hops). Extractor-declared `type:new:slug` ids become `entity` rows (`provisional`,
   `created_by='p5_records'`) plus one `alias`. Anything still absent from `entity` drops the record
   and counts in gate two.
4. "Attach to transactions": a record links to a `transaction` row when one of its entity refs is
   that row's `vessel_id` and the dates are within TXN_WINDOW_DAYS; links land in `record_txn` (a
   P5-owned table) so the frozen layer-A schema is untouched.
5. PPR export: `ppr_nodes.parquet` + `ppr_edges.parquet` over entity/chunk/event/claim nodes,
   weighted by confidence x recency (half-life 180 days) and carrying published_at + validity so P7
   can window the graph.

Cost: $0, no model calls. Idempotent: every batch is deleted by chunk_id before it is re-inserted,
row ids are content-addressed, and `--limit` slices a dry run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kb"))

import duckdb  # noqa: E402

from extract_gates import MAX_QUOTE_SENTENCES, numbers_ok, resolve_printed  # noqa: E402

KB_DB = ROOT / "kb/state/kb.duckdb"
OUT = ROOT / "kb/state/p5"
REPORTS = ROOT / "kb/reports"
GATED_DIR = ROOT / "kb/state/p4c"
KINDS = ("state_facts", "events", "claims")
PREFIX = {"state_facts": "e:", "events": "ev:", "claims": "c:"}
TABLE = {"state_facts": "edge", "events": "event", "claims": "claim"}
ENTITY_TYPES = ("vessel", "company", "port", "route", "index", "commodity", "country", "publisher", "person")
TXN_WINDOW_DAYS = 120
TXN_MAX_PER_RECORD = 10
REF_DATE_FALLBACK = dt.date(2026, 11, 13)
HALF_LIFE_DAYS = 180.0
BATCH = 400
SCAN = 5_000

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS edge (
        edge_id VARCHAR NOT NULL, type VARCHAR NOT NULL, src VARCHAR, dst VARCHAR,
        attrs_printed JSON, attrs JSON, valid_from DATE, valid_to DATE,
        published_at DATE NOT NULL, doc_id VARCHAR, chunk_id VARCHAR, sids INTEGER[],
        quote VARCHAR NOT NULL, extractor VARCHAR NOT NULL, confidence FLOAT, status VARCHAR)""",
    """CREATE TABLE IF NOT EXISTS event (
        event_id VARCHAR NOT NULL, type VARCHAR, summary VARCHAR, occurred_from DATE,
        occurred_to DATE, published_at DATE, location VARCHAR, magnitude_printed VARCHAR,
        doc_id VARCHAR, chunk_id VARCHAR, sids INTEGER[], quote VARCHAR NOT NULL,
        extractor VARCHAR, confidence FLOAT)""",
    """CREATE TABLE IF NOT EXISTS event_role (
        event_id VARCHAR, role VARCHAR, entity_id VARCHAR)""",
    """CREATE TABLE IF NOT EXISTS claim (
        claim_id VARCHAR NOT NULL, kind VARCHAR, subject_ids VARCHAR[], text_printed VARCHAR,
        horizon VARCHAR, direction VARCHAR, published_at DATE, doc_id VARCHAR, chunk_id VARCHAR,
        sids INTEGER[], quote VARCHAR NOT NULL, extractor VARCHAR, confidence FLOAT)""",
    """CREATE TABLE IF NOT EXISTS record_txn (
        record_kind VARCHAR NOT NULL, record_id VARCHAR NOT NULL, txn_id VARCHAR NOT NULL,
        chunk_id VARCHAR, via VARCHAR, days_apart INTEGER)""",
]

NUMBER_ONLY_RE = re.compile(r"^[-+]?\d+(?:\.\d+)?$")
CURRENCY_RE = re.compile(r"^(?:usd|us\$|\$|eur|gbp|cny|rmb)\s*", re.I)
SUFFIX_RE = re.compile(r"^([-+]?\d+(?:\.\d+)?)\s*(m|mn|bn|b|k|%)?$", re.I)
SCALES = {"m": 1e6, "mn": 1e6, "bn": 1e9, "b": 1e9, "k": 1e3}


# ------------------------------------------------------------------ helpers
def seed_for(phase: str) -> int:
    """Same rule as kb/tripwire.py: no hand-picked samples."""
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def connect(db: Path = KB_DB, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(db), read_only=read_only)
    con.execute("SET memory_limit='700MB'")
    con.execute("SET threads=2")
    return con


def ensure_schema(con) -> None:
    for stmt in SCHEMA:
        con.execute(stmt)


def as_date(value):
    """Coerce a printed/JSON date to date; None stays None (never guessed)."""
    if value in (None, "", "null"):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_float(text: str) -> float | None:
    """Parse `USD 26 M` / `12.5%` / `1,200` only when the whole string is one number + optional scale."""
    s = CURRENCY_RE.sub("", str(text or "").strip()).replace(",", "").strip()
    if NUMBER_ONLY_RE.match(s):
        return float(s)
    m = SUFFIX_RE.match(s)
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit == "%":
        return val / 100.0
    return val * SCALES.get(unit, 1.0)


def parse_attrs(attrs_printed) -> dict:
    """Printed values are stored verbatim; `attrs` only carries unambiguous numeric parses (§6.1)."""
    out = {}
    for a in attrs_printed or []:
        key = (a or {}).get("key") if isinstance(a, dict) else None
        printed = (a or {}).get("value_as_printed") if isinstance(a, dict) else None
        if not key:
            continue
        parsed = _parse_float(printed)
        out[str(key)] = {"printed": printed, "value": parsed} if parsed is not None else {"printed": printed}
    return out


def slice_quote(sentences: list[tuple[int, str]], sids) -> tuple[str, list[int]]:
    """Rule 2, re-done from the DB: max MAX_QUOTE_SENTENCES cited sentences, joined by code."""
    by_sid = dict(sentences or [])
    keep = sorted({int(s) for s in (sids or []) if int(s) in by_sid})[:MAX_QUOTE_SENTENCES]
    return " ".join(by_sid[s] for s in keep), keep


def printed_values(kind: str, rec: dict) -> list[str]:
    """Rule 3 inputs, dict flavour of extract_gates.printed_values."""
    vals: list[str] = []
    if kind == "state_facts":
        vals = [a.get("value_as_printed") for a in rec.get("attrs_printed") or [] if isinstance(a, dict)]
        vals += [rec.get("valid_from_printed"), rec.get("valid_to_printed")]
    elif kind == "events":
        vals = [rec.get("when_printed"), rec.get("magnitude_printed")]
    else:
        vals = [rec.get("horizon_printed")]
    return [v for v in vals if v and str(v).strip()]


def record_id(kind: str, payload: dict) -> str:
    """Content-addressed id: a rerun of the same record keeps the same row id."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return PREFIX[kind] + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def load_gated(paths: list[Path], limit: int = 0) -> dict[str, dict]:
    """Chunk rows from highest-precedence file first; a chunk is taken once (the ladder rung)."""
    picked: dict[str, dict] = {}
    label_of = {str(p): p.stem for p in paths}
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                cid = row.get("chunk_id")
                if not cid or cid in picked:
                    continue
                row["_pass"] = label_of[str(path)]
                picked[cid] = row
                if limit and len(picked) >= limit:
                    return picked
    return picked


def default_gated_paths() -> list[Path]:
    """Union export first, then each rung; missing files are skipped by `load_gated`."""
    return [
        GATED_DIR / "union/gated_union.jsonl",
        GATED_DIR / "gated.jsonl",
        GATED_DIR / "rungs/p4c_bulk.jsonl",
        GATED_DIR / "rungs/p4c_bulk_retry.jsonl",
        GATED_DIR / "rungs/p4c_esc.jsonl",
        GATED_DIR / "rungs/p4c_glm2.jsonl",
    ]


def chunk_mismatch(record: dict, cid: str) -> bool:
    """A record is unusable if its cited chunk is not the chunk row it arrived in."""
    return bool(record.get("chunk")) and str(record["chunk"]) != str(cid)


# ------------------------------------------------------------------ entity resolution
def entity_map(con, ids: set[str]) -> dict[str, dict]:
    """entity_id -> {type, name, status, merged_into} for a batch of refs."""
    ids = {i for i in ids if i}
    if not ids:
        return {}
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), SCAN):
        part = ids[i:i + SCAN]
        ph = ",".join("?" * len(part))
        rows = con.execute(
            f"select entity_id, type, canonical_name, status, attrs from entity where entity_id in ({ph})",
            part).fetchall()
        for eid, typ, name, status, attrs in rows:
            merged = None
            if status == "merged":
                try:
                    merged = (json.loads(attrs) if isinstance(attrs, str) else (attrs or {})).get("merged_into")
                except ValueError:
                    merged = None
            out[eid] = {"type": typ, "name": name, "status": status, "merged_into": merged}
    return out


def resolve_refs(con, refs: set[str], depth: int = 8) -> dict[str, str]:
    """Follow merged rows to the surviving id; unknown refs map to themselves (gate two decides)."""
    refs = {r for r in refs if r}
    seen: dict[str, str] = {}
    frontier = set(refs)
    for _ in range(depth):
        if not frontier:
            break
        info = entity_map(con, frontier - set(seen))
        nxt = set()
        for ref in sorted(frontier - set(seen)):
            seen[ref] = info.get(ref, {}).get("merged_into") or ref
            if ref in info and info[ref].get("merged_into"):
                nxt.add(info[ref]["merged_into"])
        frontier = nxt
    for ref in refs:
        seen.setdefault(ref, ref)
    return seen


def case_new(ref: str) -> dict | None:
    """`type:new:slug` ref -> {type, name-slug} so it can be provisioned as provisional."""
    parts = str(ref or "").split(":")
    if len(parts) >= 3 and parts[1] == "new" and parts[0] in ENTITY_TYPES:
        return {"type": parts[0], "slug": ":".join(parts[2:])}
    return None


def provision_new_entities(con, rows: list[dict]) -> dict[str, str]:
    """Insert provisional `entity` + `alias` rows for declared new entities; return {id: name}."""
    wanted: dict[str, str] = {}
    for row in rows:
        ok = row.get("new_entities_ok") or {}
        names = row.get("new_names") or {}
        for eid, good in ok.items():
            if not good:
                continue
            name = names.get(eid)
            if not name:
                continue
            info = case_new(eid)
            if not info:
                continue
            wanted.setdefault(eid, name)
    if not wanted:
        return {}
    existing = entity_map(con, set(wanted))
    new_rows, alias_rows = [], []
    for eid, name in sorted(wanted.items()):
        if eid in existing:
            continue
        info = case_new(eid)
        attrs = json.dumps({"provisional": True, "origin": "p4c_new_entity"})
        new_rows.append((eid, info["type"], name, attrs, "provisional", "p5_records"))
        alias_rows.append((name, name.upper(), eid, "p5_records", 1.0, None, None, None))
    if new_rows:
        con.executemany(
            "INSERT INTO entity (entity_id, type, canonical_name, attrs, status, created_by) "
            "VALUES (?,?,?,?,?,?)", new_rows)
        con.executemany(
            "INSERT INTO alias (alias, alias_norm, entity_id, source, confidence, merged_by, "
            "valid_from, valid_to) VALUES (?,?,?,?,?,?,?,?)", alias_rows)
    return wanted


# ------------------------------------------------------------------ row builders
def chunk_sentences(con, cids: list[str]) -> dict[str, list[tuple[int, str]]]:
    """[(sid, text)] per chunk, cut by code from body + sentence offsets (D7)."""
    out: dict[str, list[tuple[int, str]]] = {}
    cids = [c for c in cids if c]
    for i in range(0, len(cids), BATCH):
        part = cids[i:i + BATCH]
        ph = ",".join("?" * len(part))
        bodies = dict(con.execute(f"select chunk_id, body from chunk where chunk_id in ({ph})", part).fetchall())
        sents = con.execute(
            f"select chunk_id, sid, start_char, end_char from sentence where chunk_id in ({ph}) "
            "order by chunk_id, sid", part).fetchall()
        for cid, sid, start, end in sents:
            body = bodies.get(cid)
            if body is None:
                continue
            out.setdefault(cid, []).append((int(sid), (body[start:end] or "").strip()))
        for cid in bodies:
            out.setdefault(cid, [])
    return out


def doc_paths(con, doc_ids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    doc_ids = [d for d in doc_ids if d]
    for i in range(0, len(doc_ids), SCAN):
        part = doc_ids[i:i + SCAN]
        ph = ",".join("?" * len(part))
        for doc_id, path in con.execute(f"select doc_id, path from document where doc_id in ({ph})", part).fetchall():
            out[doc_id] = path
    return out


def build_rows(rows: list[dict], sents: dict[str, list[tuple[int, str]]],
               resolved: dict[str, str], known: set[str]) -> tuple[dict, Counter]:
    """Turn kept records of one batch into edge/event/claim/event_role rows (pure)."""
    out = {"edge": [], "event": [], "claim": [], "event_role": []}
    drops: Counter = Counter()
    refs_by_record: list[tuple[str, str, str, set[str]]] = []
    for row in rows:
        cid = row["chunk_id"]
        published = as_date(row.get("published_at"))
        doc_id = row.get("doc_id")
        sentences = sents.get(cid) or []
        for kind in KINDS:
            for rec in (row.get("kept") or {}).get(kind) or []:
                if chunk_mismatch(rec, cid):
                    drops["chunk_mismatch"] += 1
                    continue
                quote, keep = slice_quote(sentences, rec.get("sids"))
                if not quote:
                    drops["quote_empty"] += 1
                    continue
                ok_nums, _missing = numbers_ok(printed_values(kind, rec), quote)
                if not ok_nums:
                    drops["number_not_in_quote"] += 1
                    continue
                if published is None:
                    drops["no_published_at"] += 1
                    continue
                resolved_refs = {}
                dangling = False
                for ref in record_refs(kind, rec):
                    target = resolved.get(ref, ref)
                    if target not in known:
                        dangling = True
                        drops[("dangling_entity:" + str(ref))[:60]] += 1
                        break
                    resolved_refs[ref] = target
                if dangling:
                    continue
                extractor = row.get("_pass") or "p4c"
                if kind == "state_facts":
                    payload = {"type": rec.get("type"), "src": resolved_refs.get(rec.get("src"), rec.get("src")),
                               "dst": resolved_refs.get(rec.get("dst"), rec.get("dst")),
                               "attrs": rec.get("attrs_printed"), "chunk": cid, "sids": keep}
                    rid = record_id(kind, payload)
                    vf = resolve_printed(rec.get("valid_from_printed"), published)
                    vt = resolve_printed(rec.get("valid_to_printed"), published)
                    out["edge"].append((
                        rid, rec.get("type"), payload["src"], payload["dst"],
                        json.dumps(rec.get("attrs_printed") or []), json.dumps(parse_attrs(rec.get("attrs_printed"))),
                        as_date((vf or {}).get("start")), as_date((vt or {}).get("end")),
                        published, doc_id, cid, keep, quote, extractor,
                        rec.get("confidence"), "active"))
                    refs_by_record.append((kind, rid, cid, {payload["src"], payload["dst"]} - {None, ""}))
                elif kind == "events":
                    when = resolve_printed(rec.get("when_printed"), published)
                    eid = record_id(kind, {"type": rec.get("type"), "summary": rec.get("summary"),
                                           "roles": rec.get("roles"), "chunk": cid, "sids": keep})
                    out["event"].append((
                        eid, rec.get("type"), rec.get("summary"), as_date((when or {}).get("start")),
                        as_date((when or {}).get("end")), published, None, rec.get("magnitude_printed"),
                        doc_id, cid, keep, quote, extractor, rec.get("confidence")))
                    role_refs = set()
                    for role in rec.get("roles") or []:
                        ent = resolved_refs.get(role.get("entity"), role.get("entity"))
                        out["event_role"].append((eid, role.get("role"), ent))
                        if ent:
                            role_refs.add(ent)
                    refs_by_record.append((kind, eid, cid, role_refs))
                else:
                    subs = [resolved_refs.get(s, s) for s in rec.get("subjects") or []]
                    claim_id = record_id(kind, {"kind": rec.get("kind"), "subjects": subs,
                                                "direction": rec.get("direction"), "chunk": cid, "sids": keep})
                    out["claim"].append((
                        claim_id, rec.get("kind"), subs, quote, rec.get("horizon_printed"),
                        rec.get("direction"), published, doc_id, cid, keep, quote,
                        extractor, rec.get("confidence")))
                    refs_by_record.append((kind, claim_id, cid, set(subs)))
    return {"rows": out, "record_refs": refs_by_record}, drops


def record_refs(kind: str, rec: dict) -> list[str]:
    if kind == "state_facts":
        return [r for r in (rec.get("src"), rec.get("dst")) if r]
    if kind == "events":
        return [r.get("entity") for r in rec.get("roles") or [] if r.get("entity")]
    return [s for s in rec.get("subjects") or [] if s]


# ------------------------------------------------------------------ transactions
def txn_index(con, entity_ids: set[str]) -> dict[str, list[tuple[str, dt.date | None, dt.date | None]]]:
    """vessel entity id -> [(txn_id, date_from, date_to)] for the txn-attach step."""
    out: dict[str, list[tuple[str, dt.date | None, dt.date | None]]] = defaultdict(list)
    ids = [i for i in entity_ids if i]
    for i in range(0, len(ids), BATCH):
        part = ids[i:i + BATCH]
        ph = ",".join("?" * len(part))
        for vessel, txn, d1, d2 in con.execute(
                f"select vessel_id, txn_id, date_from, date_to from transaction where vessel_id in ({ph})",
                part).fetchall():
            out[vessel].append((txn, d1, d2))
    return out


def attach_transactions(con, record_refs: list[tuple[str, str, str, set[str]]],
                        txn_by_entity: dict, published_by_record: dict[str, dt.date]) -> int:
    """record -> transaction links inside TXN_WINDOW_DAYS; capped per record."""
    links = []
    for kind, rid, cid, refs in record_refs:
        anchor = published_by_record.get(rid)
        if anchor is None:
            continue
        cands: dict[tuple[str, str], int] = {}
        for ref in refs:
            for txn, d1, d2 in txn_by_entity.get(ref, []):
                for d in (d1, d2):
                    if d is None:
                        continue
                    days = abs((d - anchor).days)
                    if days <= TXN_WINDOW_DAYS:
                        key = (txn, ref)
                        if key not in cands or days < cands[key]:
                            cands[key] = days
        ranked = sorted((days, txn, ref) for (txn, ref), days in cands.items())
        for days, txn, ref in ranked[:TXN_MAX_PER_RECORD]:
            links.append((kind, rid, txn, cid, ref, int(days)))
    if links:
        con.executemany(
            "INSERT INTO record_txn (record_kind, record_id, txn_id, chunk_id, via, days_apart) "
            "VALUES (?,?,?,?,?,?)", links)
    return len(links)


# ------------------------------------------------------------------ PPR export
def export_ppr(con, out: Path, ref_date: dt.date) -> dict:
    """entity/chunk/event/claim nodes + weighted edges, windowable by published_at."""
    out.mkdir(parents=True, exist_ok=True)
    nodes_path = out / "ppr_nodes.parquet"
    edges_path = out / "ppr_edges.parquet"
    con.execute("DROP TABLE IF EXISTS _ppr_nodes")
    con.execute("DROP TABLE IF EXISTS _ppr_edges")
    con.execute("""
        CREATE TABLE _ppr_nodes AS
        SELECT entity_id AS node_id, 'entity' AS node_kind, type AS type,
               canonical_name AS label, NULL::DATE AS published_at, status AS status FROM entity
        UNION ALL
        SELECT chunk_id, 'chunk', 'chunk', NULL, d.published_at, NULL
        FROM chunk c LEFT JOIN document d USING (doc_id)
        WHERE c.chunk_id IN (SELECT chunk_id FROM edge UNION SELECT chunk_id FROM event
                             UNION SELECT chunk_id FROM claim)
        UNION ALL
        SELECT event_id, 'event', type, summary, published_at, NULL FROM event
        UNION ALL
        SELECT claim_id, 'claim', kind, text_printed, published_at, NULL FROM claim
    """)
    half = float(HALF_LIFE_DAYS)
    weight = f"0.5 ** (date_diff('day', published_at, DATE '{ref_date.isoformat()}') / {half})"
    con.execute(f"""
        CREATE TABLE _ppr_edges AS
        SELECT src AS src_id, dst AS dst_id, 'edge:' || type AS type,
               coalesce(confidence, 0.5) * {weight} AS weight,
               published_at, valid_from, valid_to FROM edge WHERE src IS NOT NULL AND dst IS NOT NULL
        UNION ALL
        SELECT event_id, entity_id, 'event_role:' || role, 0.5, e.published_at, NULL, NULL
        FROM event_role r JOIN event e USING (event_id) WHERE entity_id IS NOT NULL
        UNION ALL
        SELECT claim_id, s AS src_id, 'claim_subject', 0.5, published_at, NULL, NULL
        FROM (SELECT claim_id, unnest(subject_ids) AS s, published_at FROM claim)
        UNION ALL
        SELECT chunk_id, src, 'chunk_mention', coalesce(confidence, 0.5), published_at, NULL, NULL
        FROM edge WHERE src IS NOT NULL
        UNION ALL
        SELECT chunk_id, dst, 'chunk_mention', coalesce(confidence, 0.5), published_at, NULL, NULL
        FROM edge WHERE dst IS NOT NULL
        UNION ALL
        SELECT chunk_id, event_id, 'chunk_event', 1.0, published_at, NULL, NULL FROM event
        UNION ALL
        SELECT chunk_id, claim_id, 'chunk_claim', 1.0, published_at, NULL, NULL FROM claim
    """)
    con.execute(f"COPY (SELECT * FROM _ppr_nodes) TO '{nodes_path.as_posix()}' (FORMAT PARQUET)")
    con.execute(f"COPY (SELECT * FROM _ppr_edges) TO '{edges_path.as_posix()}' (FORMAT PARQUET)")
    n_nodes, n_edges = con.execute("select (select count(*) from _ppr_nodes), (select count(*) from _ppr_edges)").fetchone()
    con.execute("DROP TABLE _ppr_nodes")
    con.execute("DROP TABLE _ppr_edges")
    return {"nodes": int(n_nodes), "edges": int(n_edges),
            "nodes_path": str(nodes_path), "edges_path": str(edges_path)}


# ------------------------------------------------------------------ gates
def dangling_count(con) -> dict:
    """Gate two: every id a record points at must be a live `entity` row."""
    edge_bad = con.execute("""
        SELECT count(*) FROM edge WHERE (src IS NOT NULL AND src <> '' AND src NOT IN (SELECT entity_id FROM entity))
           OR (dst IS NOT NULL AND dst <> '' AND dst NOT IN (SELECT entity_id FROM entity))
    """).fetchone()[0]
    role_bad = con.execute("""
        SELECT count(*) FROM event_role WHERE entity_id IS NOT NULL AND entity_id <> ''
          AND entity_id NOT IN (SELECT entity_id FROM entity)
    """).fetchone()[0]
    claim_bad = con.execute("""
        SELECT count(*) FROM (SELECT unnest(subject_ids) AS s FROM claim)
        WHERE s IS NOT NULL AND s <> '' AND s NOT IN (SELECT entity_id FROM entity)
    """).fetchone()[0]
    return {"edge": int(edge_bad), "event_role": int(role_bad), "claim": int(claim_bad),
            "total": int(edge_bad) + int(role_bad) + int(claim_bad)}


def audit_quotes(db: Path = KB_DB, scan: int = SCAN) -> dict:
    """Gate one: re-slice every inserted record's quote from chunk.body independently of the build.

    Two connections: one streams the records, one looks up sentence offsets (DuckDB invalidates a
    streaming result when the same connection runs another query).
    """
    rows_con = connect(db, read_only=True)
    look_con = connect(db, read_only=True)
    try:
        checked = 0
        bad: list[dict] = []
        chunks: dict[str, list[tuple[int, str]]] = {}
        for table, id_col in (("edge", "edge_id"), ("event", "event_id"), ("claim", "claim_id")):
            res = rows_con.execute(f"select {id_col}, chunk_id, sids, quote from {table}")
            while True:
                batch = res.fetchmany(scan)
                if not batch:
                    break
                need = [b[1] for b in batch if b[1] and b[1] not in chunks]
                if need:
                    chunks.update(chunk_sentences(look_con, sorted(set(need))))
                for rid, cid, sids, quote in batch:
                    checked += 1
                    expected, _keep = slice_quote(chunks.get(cid) or [], sids or [])
                    if not quote or " ".join(str(quote).split()) != " ".join(expected.split()):
                        if len(bad) < 50:
                            bad.append({"table": table, "id": rid, "chunk_id": cid, "quote": str(quote)[:120]})
        return {"checked": checked, "bad": len(bad), "samples": bad}
    finally:
        rows_con.close()
        look_con.close()


# ------------------------------------------------------------------ build
def build(gated_paths: list[Path] | None = None, db: Path = KB_DB, out: Path | None = None,
          limit: int = 0, do_ppr: bool = True, progress: bool = True) -> dict:
    """One resumable-by-batch build pass. Returns the report payload (also used by `--report`)."""
    t0 = time.time()
    out = Path(out or OUT)
    out.mkdir(parents=True, exist_ok=True)
    paths = list(gated_paths or default_gated_paths())
    picked = load_gated(paths, limit=limit)
    if not picked:
        raise SystemExit(f"no gated chunk rows found in {[str(p) for p in paths]}")
    con = connect(db)
    ensure_schema(con)
    ref_date = as_date(con.execute("select max(published_at) from document").fetchone()[0]) or REF_DATE_FALLBACK
    known = {r[0] for r in con.execute("select entity_id from entity").fetchall()}
    stats: Counter = Counter()
    drops: Counter = Counter()
    inserts: Counter = Counter()
    chunks_done = 0
    cids = list(picked)
    for i in range(0, len(cids), BATCH):
        batch_ids = cids[i:i + BATCH]
        rows = [picked[c] for c in batch_ids]
        sents = chunk_sentences(con, batch_ids)
        provisioned = provision_new_entities(con, rows)
        known |= set(provisioned)
        refs: set[str] = set()
        for row in rows:
            for kind in KINDS:
                for rec in (row.get("kept") or {}).get(kind) or []:
                    refs |= set(record_refs(kind, rec))
        resolved = resolve_refs(con, refs)
        known |= set(entity_map(con, set(resolved.values())))
        built, d = build_rows(rows, sents, resolved, known)
        rows_out = built["rows"]
        pub_by_chunk = {r["chunk_id"]: as_date(r.get("published_at")) for r in rows}
        published_by_record = {rid: pub_by_chunk.get(cid) for _kind, rid, cid, _refs in built["record_refs"]}
        ph = ",".join("?" * len(batch_ids))
        con.execute(f"DELETE FROM edge WHERE chunk_id IN ({ph})", batch_ids)
        con.execute(f"DELETE FROM event WHERE chunk_id IN ({ph})", batch_ids)
        con.execute(f"DELETE FROM claim WHERE chunk_id IN ({ph})", batch_ids)
        con.execute(f"DELETE FROM record_txn WHERE chunk_id IN ({ph})", batch_ids)
        if rows_out["event"]:
            eids = [r[0] for r in rows_out["event"]]
            eph = ",".join("?" * len(eids))
            con.execute(f"DELETE FROM event_role WHERE event_id IN ({eph})", eids)
        if rows_out["edge"]:
            con.executemany("INSERT INTO edge VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows_out["edge"])
        if rows_out["event"]:
            con.executemany("INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows_out["event"])
        if rows_out["event_role"]:
            con.executemany("INSERT INTO event_role VALUES (?,?,?)", rows_out["event_role"])
        if rows_out["claim"]:
            con.executemany("INSERT INTO claim VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows_out["claim"])
        ents: set[str] = set()
        for _kind, _rid, _cid, refs_ in built["record_refs"]:
            ents |= refs_
        txns = txn_index(con, ents)
        links = attach_transactions(con, built["record_refs"], txns, published_by_record)
        inserts["edge"] += len(rows_out["edge"])
        inserts["event"] += len(rows_out["event"])
        inserts["claim"] += len(rows_out["claim"])
        inserts["event_role"] += len(rows_out["event_role"])
        inserts["record_txn"] += links
        drops.update(d)
        stats.update({f"kept_{k}": sum(len((r.get("kept") or {}).get(k) or []) for r in rows) for k in KINDS})
        stats["chunks"] += len(rows)
        chunks_done += len(rows)
        if progress:
            print(f"[p5] chunks {chunks_done}/{len(cids)} inserted "
                  f"e={inserts['edge']} ev={inserts['event']} c={inserts['claim']} links={inserts['record_txn']}",
                  flush=True)
    ppr = export_ppr(con, out, ref_date) if do_ppr else {}
    counts = {t: int(con.execute(f"select count(*) from {t}").fetchone()[0])
              for t in ("edge", "event", "event_role", "claim", "record_txn")}
    dangling = dangling_count(con)
    con.close()
    audit = audit_quotes(db)
    wall = round(time.time() - t0, 1)
    sample = sample_records(db, seed=seed_for("P5"))
    report = {
        "phase": "P5",
        "sample_seed": seed_for("P5"),
        "gated_files": [{"path": str(p), "exists": p.exists()} for p in paths],
        "chunks_in": len(picked),
        "chunks_processed": chunks_done,
        "inserted": dict(inserts),
        "table_counts": counts,
        "kept_by_kind": {k: stats[f"kept_{k}"] for k in KINDS},
        "drops": dict(drops),
        "dangling": dangling,
        "quote_audit": {k: audit[k] for k in ("checked", "bad")},
        "quote_audit_samples": audit["samples"],
        "ppr": ppr,
        "records_without_code_sliced_quote": int(audit["bad"]),
        "dangling_entity_ids": int(dangling["total"]),
        "sample_records": sample,
        "spend_usd": 0.0,
        "wall_seconds": wall,
        "ref_date": ref_date.isoformat(),
    }
    (out / "build_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def sample_records(db: Path = KB_DB, seed: int = 0, n: int = 10, scan: int = SCAN) -> list[dict]:
    """Deterministic 10-record sample with the source path for each (report requirement §4)."""
    con = connect(db, read_only=True)
    try:
        rows = []
        per = max(1, n // 3)
        for table, id_col in (("edge", "edge_id"), ("event", "event_id"), ("claim", "claim_id")):
            res = con.execute(f"select {id_col}, chunk_id, doc_id, published_at from {table} order by {id_col}")
            all_rows = res.fetchall()
            if not all_rows:
                continue
            rng = random.Random(seed + len(table))
            rows += [{"table": table, "record_id": a, "chunk_id": b, "doc_id": c,
                      "published_at": str(d)} for a, b, c, d in rng.sample(all_rows, min(per, len(all_rows)))]
        paths = doc_paths(con, [r["doc_id"] for r in rows])
        for r in rows:
            r["source_path"] = paths.get(r["doc_id"], "")
        rng = random.Random(seed)
        rng.shuffle(rows)
        return rows[:n]
    finally:
        con.close()


# ------------------------------------------------------------------ report
def _md(report: dict) -> str:
    counts = report["table_counts"]
    return "\n".join([
        "# P5 graph build report",
        "",
        "Gate `records_without_code_sliced_quote` = "
        f"{report['records_without_code_sliced_quote']} (must be 0)",
        "Gate `dangling_entity_ids` = "
        f"{report['dangling_entity_ids']} (must be 0)",
        "",
        f"- chunks read {report['chunks_in']}, processed {report['chunks_processed']}",
        f"- inserted {report['inserted']}",
        f"- table counts {counts}",
        f"- drops {report['drops']}",
        f"- quote audit {report['quote_audit']} over {counts['edge'] + counts['event'] + counts['claim']} rows",
        f"- PPR {report.get('ppr')}",
        f"- spend ${report['spend_usd']:.4f}, wall {report['wall_seconds']}s, ref_date {report['ref_date']}",
        "",
        "## Sample records (deterministic seed)",
        "",
    ] + [f"- `{r['record_id']}` ({r['table']}, {r['published_at']}) <- {r['source_path']}"
         for r in report["sample_records"]])


def write_report(report: dict, json_path: Path | None = None, md_path: Path | None = None) -> dict:
    json_path = Path(json_path or REPORTS / "P5.json")
    md_path = Path(md_path or REPORTS / "P5.md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_md(report), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


# ------------------------------------------------------------------ cli
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P5: gate P4c records into the KB graph")
    ap.add_argument("--gated", action="append", default=None,
                    help="gated jsonl file, highest ladder rung first (repeatable)")
    ap.add_argument("--db", default=str(KB_DB))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--limit", type=int, default=0, help="dry run: stop after N chunks")
    ap.add_argument("--no-ppr", action="store_true")
    ap.add_argument("--report", action="store_true", help="write kb/reports/P5.json + P5.md")
    args = ap.parse_args(argv)
    paths = [Path(p) for p in args.gated] if args.gated else default_gated_paths()
    report = build(paths, db=Path(args.db), out=Path(args.out), limit=args.limit,
                   do_ppr=not args.no_ppr)
    print(json.dumps({k: report[k] for k in ("chunks_processed", "records_without_code_sliced_quote",
                                             "dangling_entity_ids", "spend_usd", "wall_seconds")}, indent=2))
    if args.report:
        print(write_report(report))
    gate_ok = report["records_without_code_sliced_quote"] == 0 and report["dangling_entity_ids"] == 0
    print("P5 GATE", "PASSED" if gate_ok else "FAILED")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
