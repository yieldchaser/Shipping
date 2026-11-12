"""P4b gold chunks: the 120-chunk stratified sample the extraction bake-off is scored on (plan §10.2).

Scope is plan §7.1 exactly: prose, `chunk.extract`, not boilerplate, SEC only for the five in-scope
items, and at least one tagged entity or event keyword. Stratification follows `kb/gates.yaml`
`sampling.min_strata` (publisher, doc_type, year):

  1. 120 slots are spread over (doc_type, year) strata by largest-remainder, proportional to the
     in-scope corpus (no floor, so no tiny stratum is over-represented).
  2. A coverage repair swaps chunks in until every publisher, doc_type, year and section class seen
     in scope is represented at least once, never removing the last representative of anything.
  3. The sample is then read off exactly `target` chunks.

Sampling is deterministic from `gates.seed_for("P4B")`; every candidate sees the same 120 chunks,
which is what makes the side-by-side metrics comparable.

Outputs (gitignored):
  kb/state/gold/p4b_chunks.json   the 120 picks + their strata + scope stats
  kb/state/gold/p4b_items.json    ready-to-send payloads (sentences, known entities, doc meta)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

import duckdb

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

ROOT = KB.parent
DB = ROOT / "kb/state/kb.duckdb"
OUT = ROOT / "kb/state/gold"

TARGET = 120
EVENT_KEYWORDS = ("fixture|charter|sale|demoli|order|newbuild|rate|freight|congestion|sanction|strike|"
                  "disrupt|guidance|forecast|cargo|tonne|vessel|fleet|delivery")
DIMS = (
    ("publisher", lambda r: r["publisher"]),
    ("doc_type", lambda r: r["doc_type"]),
    ("year", lambda r: str(r["year"])),
    ("section_class", lambda r: r["section_class"]),
)


def seed_for(phase: str = "P4B") -> int:
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def scope_sql() -> str:
    """One row per chunk in extraction scope, with the stratified sample's keys."""
    return f"""
    select c.chunk_id, c.doc_id, c.ord, c.tokens, coalesce(len(c.entity_ids),0) n_ent,
           d.doc_type, d.publisher_id, d.published_at, d.title,
           extract(year from d.published_at) yr,
           case when d.doc_type like 'sec%' then
             case when starts_with(coalesce(s.sec_item,''),'item_1') then 'business'
                  when starts_with(coalesce(s.sec_item,''),'item_7') then 'md_a'
                  when starts_with(coalesce(s.sec_item,''),'item_9') then 'subsequent'
                  when coalesce(s.sec_item,'')='press_release' then 'press_release'
                  when coalesce(s.sec_item,'')='fleet' then 'fleet' else 'other_sec' end
             else coalesce(s.kind,'prose') end section_class,
           coalesce(s.sec_item,'') sec_item
    from chunk c join document d using(doc_id) left join section s using(section_id)
    where c.kind='prose' and c.extract
      and coalesce(s.kind,'prose') <> 'boilerplate'
      and (not (d.doc_type like 'sec%')
           or starts_with(coalesce(s.sec_item,''),'item_1')
           or starts_with(coalesce(s.sec_item,''),'item_7')
           or starts_with(coalesce(s.sec_item,''),'item_9')
           or coalesce(s.sec_item,'') in ('press_release','fleet'))
      and (coalesce(len(c.entity_ids),0) > 0
           or regexp_matches(c.body, '(?i)({EVENT_KEYWORDS})'))
    """


def load_scope(db: Path = DB) -> list[dict]:
    con = duckdb.connect(str(db), read_only=True)
    con.execute("SET memory_limit='700MB'")
    con.execute("SET threads=2")
    cols = ["chunk_id", "doc_id", "ord", "tokens", "n_ent", "doc_type", "publisher", "published_at",
            "title", "year", "section_class", "sec_item"]
    rows = [dict(zip(cols, r)) for r in con.execute(scope_sql()).fetchall()]
    con.close()
    return rows


def allocate(counts: dict[str, int], target: int) -> dict[str, int]:
    """Largest-remainder allocation, no floor: small strata may get zero slots."""
    total = sum(counts.values())
    if not total:
        return {k: 0 for k in counts}
    raw = {k: target * counts[k] / total for k in counts}
    base = {k: int(math.floor(raw[k])) for k in counts}
    left = target - sum(base.values())
    for k in sorted(counts, key=lambda k: (-(raw[k] - base[k]), -counts[k], k))[: max(0, left)]:
        base[k] += 1
    return base


def _rep_counts(picks: list[dict]) -> Counter:
    c: Counter = Counter()
    for p in picks:
        for name, fn in DIMS:
            c[(name, fn(p))] += 1
    return c


def _sample_strata(rows: list[dict], target: int, rng: random.Random) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(f"{r['doc_type']}|{r['year']}", []).append(r)
    quota = allocate({k: len(v) for k, v in groups.items()}, target)
    picks: list[dict] = []
    for k in sorted(groups):
        if not quota.get(k):
            continue
        pool = sorted(groups[k], key=lambda r: r["chunk_id"])
        picks.extend(rng.sample(pool, min(quota[k], len(pool))))
    return picks


def _repair(rows: list[dict], picks: list[dict], target: int, rng: random.Random) -> list[dict]:
    """Force one chunk per publisher / doc_type / year / section_class, then trim to `target`."""
    reps = _rep_counts(picks)
    pool_by: dict[tuple, list[dict]] = {}
    for r in rows:
        for name, fn in DIMS:
            pool_by.setdefault((name, fn(r)), []).append(r)
    picks = list(picks)
    for name, _fn in DIMS:
        vals = sorted({fn(r) for _n, fn in DIMS if _n == name for r in rows})
        for v in vals:
            if reps[(name, v)]:
                continue
            taken = {p["chunk_id"] for p in picks}
            pool = [r for r in sorted(pool_by[(name, v)], key=lambda r: r["chunk_id"])
                    if r["chunk_id"] not in taken]
            donors = [i for i, p in enumerate(picks) if all(reps[(n, f(p))] > 1 for n, f in DIMS)]
            if not pool or not donors:
                continue
            cand = rng.choice(pool)
            i = max(donors, key=lambda i: picks[i]["chunk_id"])
            for n, f in DIMS:
                reps[(n, f(picks[i]))] -= 1
            picks[i] = cand
            for n, f in DIMS:
                reps[(n, f(cand))] += 1
    while len(picks) > target:
        donors = [i for i, p in enumerate(picks) if all(reps[(n, f(p))] > 1 for n, f in DIMS)]
        if not donors:
            break
        i = max(donors, key=lambda i: picks[i]["chunk_id"])
        for n, f in DIMS:
            reps[(n, f(picks[i]))] -= 1
        picks.pop(i)
    return picks


def select(rows: list[dict], target: int = TARGET, seed: int | None = None) -> dict:
    """Pick `target` chunks, deterministic given `seed`. Returns picks + coverage report."""
    seed = seed if seed is not None else seed_for("P4B")
    rng = random.Random(seed)
    picks = _sample_strata(rows, target, rng)
    picks = _repair(rows, picks, target, rng)
    picks.sort(key=lambda r: (str(r["publisher"]), r["doc_type"], str(r["year"]), r["chunk_id"]))
    picks = picks[:target]
    cov = {
        "publishers": sorted({r["publisher"] for r in picks}),
        "doc_types": sorted({r["doc_type"] for r in picks}),
        "years": sorted({str(r["year"]) for r in picks}),
        "section_classes": sorted({r["section_class"] for r in picks}),
        "sec_items": sorted({r["sec_item"] for r in picks if r["sec_item"]}),
    }
    scope_cov = {name: len({fn(r) for r in rows}) for name, fn in DIMS}
    stats = {
        "seed": seed, "target": target,
        "strata_dim": "(doc_type, year)",
        "strata_total": len({f"{r['doc_type']}|{r['year']}" for r in rows}),
        "strata_used": len({f"{r['doc_type']}|{r['year']}" for r in picks}),
        "scope_chunks": len(rows),
        "scope_dim_values": scope_cov,
        "sample_dim_values": {name: len({fn(r) for r in picks}) for name, fn in DIMS},
        "mean_tokens": round(sum(r["tokens"] or 0 for r in picks) / max(1, len(picks)), 1),
        "mean_entities": round(sum(r["n_ent"] for r in picks) / max(1, len(picks)), 2),
        "by_doc_type": dict(sorted(Counter(r["doc_type"] for r in picks).items())),
        "by_year": dict(sorted(Counter(str(r["year"]) for r in picks).items())),
    }
    return {"picks": picks, "coverage": cov, "stats": stats}


# --- packed sampling (plan §7.2: one call carries several chunks of the SAME document) ---------
PACK_MAX_TOKENS = 3500
PACK_MAX_CHUNKS = 6
PACK_MIN_DEPTH = 2


def _doc_windows(rows: list[dict], rng: random.Random, max_chunks: int = PACK_MAX_CHUNKS,
                 max_tokens: int = PACK_MAX_TOKENS) -> list[list[dict]]:
    """Consecutive chunk windows inside one document, in document order, token-capped."""
    by_doc: dict[str, list[dict]] = {}
    for r in rows:
        by_doc.setdefault(r["doc_id"], []).append(r)
    windows = []
    for doc_id, rs in by_doc.items():
        rs.sort(key=lambda r: (int(r.get("ord") or 0), r["chunk_id"]))
        i = 0
        while i < len(rs):
            # a random start offset varies which part of long documents is sampled
            span, tok = [], 0
            j = i
            while j < len(rs) and len(span) < max_chunks:
                t = int(rs[j]["tokens"] or 0)
                if span and tok + t > max_tokens:
                    break
                span.append(rs[j])
                tok += t
                j += 1
            if len(span) >= PACK_MIN_DEPTH:
                windows.append(span)
            i = max(i + 1, j)
    rng.shuffle(windows)
    return windows


ERAS = (("pre2011", 0, 2010), ("2011_2019", 2011, 2019), ("2020_2023", 2020, 2023),
        ("2024_2026", 2024, 9999))


def era_of(year) -> str:
    y = int(year or 0)
    for name, lo, hi in ERAS:
        if lo <= y <= hi:
            return name
    return ERAS[-1][0]


def select_packed(rows: list[dict], target: int = TARGET, seed: int | None = None) -> dict:
    """Pick `target` chunks grouped into packs of one document each (`plan §7.2` call shape).

    The bake-off must measure the packed call the P4c bulk run will actually issue, so the 120 gold
    chunks are drawn document-first: a window of 2-6 consecutive chunks per document, spread over
    (doc_type, 4-era) strata in proportion to their in-scope chunk counts, with every doc_type
    guaranteed at least one window. Depth-1 documents are not eligible (they cannot exercise
    packing), so mean pack depth is reported next to the corpus mean for cost projection.
    """
    seed = seed if seed is not None else seed_for("P4B")
    rng = random.Random(seed)
    windows = _doc_windows(rows, rng)
    by_id = {id(w): w for w in windows}
    strata: dict[str, list[list[dict]]] = {}
    for w in windows:
        key = f"{w[0]['doc_type']}|{era_of(w[0]['year'])}"
        strata.setdefault(key, []).append(w)
    scope_counts: Counter = Counter(f"{r['doc_type']}|{era_of(r['year'])}" for r in rows)
    # min one window (2 chunks) per doc_type, the rest proportional to in-scope chunk share
    doc_types = sorted({r["doc_type"] for r in rows})
    floor_total = PACK_MIN_DEPTH * len(doc_types)
    quota = allocate(dict(scope_counts), target - floor_total)
    for dt in doc_types:
        keys = [k for k in quota if k.startswith(dt + "|")]
        big = max(keys, key=lambda k: (scope_counts[k], k))
        quota[big] = quota.get(big, 0) + PACK_MIN_DEPTH
    pools: dict[str, list[list[dict]]] = {k: sorted(ws, key=lambda w: -len(w))
                                          for k, ws in strata.items()}
    picks: list[dict] = []
    packs: list[dict] = []
    taken: set[int] = set()

    def add(win: list[dict]) -> None:
        taken.add(id(win))
        packs.append({"doc_id": win[0]["doc_id"], "chunk_ids": [r["chunk_id"] for r in win]})
        picks.extend(win)

    def take(pool: list[list[dict]], budget: int) -> list[dict] | None:
        for w in pool:
            if id(w) not in taken and len(w) <= budget:
                return w
        return None

    # strata quota: deepest window that fits wins because every extra chunk in a call amortises the
    # same ~2.5k-token static prompt; leftover windows (unused strata, quota residues) top up after.
    for key in sorted(quota):
        pool = pools.get(key) or []
        got = 0
        while got < quota[key]:
            budget = min(quota[key] - got, target - len(picks))
            if budget <= 0:
                break
            win = take(pool, budget)
            if win is None:
                break
            add(win)
            got += len(win)
    rest = [w for k in sorted(pools) for w in pools[k]]
    while len(picks) < target:
        win = take(rest, target - len(picks))
        if win is None:
            break
        add(win)
    if len(picks) < target:
        used = {r["chunk_id"] for r in picks}
        singles = [r for r in rows if r["chunk_id"] not in used]
        rng.shuffle(singles)
        for r in singles[: target - len(picks)]:
            add([r])
    picks.sort(key=lambda r: (str(r["publisher"]), r["doc_type"], str(r["year"]),
                              r["doc_id"], int(r.get("ord") or 0)))
    packs.sort(key=lambda p: (str(p["doc_id"]), p["chunk_ids"][0]))
    cov = {
        "publishers": sorted({r["publisher"] for r in picks}),
        "doc_types": sorted({r["doc_type"] for r in picks}),
        "years": sorted({str(r["year"]) for r in picks}),
        "section_classes": sorted({r["section_class"] for r in picks}),
        "sec_items": sorted({r["sec_item"] for r in picks if r["sec_item"]}),
    }
    depths = [len(p["chunk_ids"]) for p in packs]
    tok_by_id = {r["chunk_id"]: int(r["tokens"] or 0) for r in picks}
    docs: dict[str, int] = {}
    for r in rows:
        docs[r["doc_id"]] = docs.get(r["doc_id"], 0) + 1
    stats = {
        "seed": seed, "target": target, "sampling": "packed_doc_windows",
        "pack_max_tokens": PACK_MAX_TOKENS, "pack_max_chunks": PACK_MAX_CHUNKS,
        "strata_dim": "(doc_type, era4)",
        "strata_total": len({f"{r['doc_type']}|{era_of(r['year'])}" for r in rows}),
        "strata_used": len({f"{r['doc_type']}|{era_of(r['year'])}" for r in picks}),
        "scope_chunks": len(rows),
        "scope_docs": len(docs),
        "scope_mean_doc_depth": round(len(rows) / max(1, len(docs)), 2),
        "scope_dim_values": {name: len({fn(r) for r in rows}) for name, fn in DIMS},
        "sample_dim_values": {name: len({fn(r) for r in picks}) for name, fn in DIMS},
        "packs": len(packs), "mean_pack_depth": round(sum(depths) / max(1, len(depths)), 2),
        "pack_depth_hist": dict(sorted(Counter(depths).items())),
        "mean_pack_tokens": round(
            sum(sum(tok_by_id[c] for c in p["chunk_ids"]) for p in packs) / max(1, len(packs)), 1),
        "mean_tokens": round(sum(r["tokens"] or 0 for r in picks) / max(1, len(picks)), 1),
        "mean_entities": round(sum(r["n_ent"] for r in picks) / max(1, len(picks)), 2),
        "by_doc_type": dict(sorted(Counter(r["doc_type"] for r in picks).items())),
        "by_doc_type_share": {k: round(v / max(1, len(picks)), 3)
                              for k, v in sorted(Counter(r["doc_type"] for r in picks).items())},
        "scope_by_doc_type_share": {k: round(v / max(1, len(rows)), 3)
                                    for k, v in sorted(Counter(r["doc_type"] for r in rows).items())},
        "by_year": dict(sorted(Counter(str(r["year"]) for r in picks).items())),
    }
    return {"picks": picks, "packs": packs, "coverage": cov, "stats": stats}


def build_items(db: Path = DB, picks: list[dict] | None = None) -> list[dict]:
    """Ready-to-send extraction payloads: chunk text, numbered sentences, known entities."""
    data = json.loads((OUT / "p4b_chunks.json").read_text(encoding="utf-8"))
    picks = picks or data["picks"]
    con = duckdb.connect(str(db), read_only=True)
    con.execute("SET memory_limit='700MB'")
    con.execute("SET threads=2")
    items = []
    for p in picks:
        cid = p["chunk_id"]
        body = con.execute("select body from chunk where chunk_id=?", [cid]).fetchone()[0]
        sents = [(s, body[a:b]) for s, a, b in
                 con.execute("select sid, start_char, end_char from sentence where chunk_id=? order by sid",
                             [cid]).fetchall()]
        ids = con.execute("select entity_ids from chunk where chunk_id=?", [cid]).fetchone()[0] or []
        known = []
        if ids:
            rows = con.execute(
                "select entity_id, type, canonical_name, attrs from entity where entity_id in (%s)"
                % ",".join("?" * len(ids)), list(ids)).fetchall()
            for eid, etype, name, attrs in sorted(rows, key=lambda r: r[0]):
                try:
                    a = json.loads(attrs) if isinstance(attrs, str) else (attrs or {})
                except ValueError:
                    a = {}
                key = a.get("imo") or a.get("ticker") or a.get("cik") or ""
                known.append({"id": eid, "type": etype, "name": name, "key": str(key)})
        items.append({
            "chunk_id": cid, "doc_id": p["doc_id"], "ord": int(p.get("ord") or 0),
            "doc_type": p["doc_type"],
            "publisher": p["publisher"], "year": p["year"], "section_class": p["section_class"],
            "published_at": str(p["published_at"])[:10] if p["published_at"] else None,
            "title": p["title"], "tokens": p["tokens"], "sentences": sents, "known": known,
            "known_ids": [k["id"] for k in known],
        })
    con.close()
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=TARGET)
    ap.add_argument("--stats-only", action="store_true")
    ap.add_argument("--unpacked", action="store_true",
                    help="legacy single-chunk-per-call sample (pre-packing attempts only)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_scope()
    print(f"scope chunks: {len(rows)}  publishers: {len({r['publisher'] for r in rows})}  "
          f"doc_types: {len({r['doc_type'] for r in rows})}")
    sel = select(rows, args.target) if args.unpacked else select_packed(rows, args.target)
    print(json.dumps(sel["stats"], indent=2, default=str))
    print("coverage publishers:", len(sel["coverage"]["publishers"]),
          "doc_types:", sel["coverage"]["doc_types"],
          "years:", sel["coverage"]["years"])
    if args.stats_only:
        return 0
    if len(sel["picks"]) != args.target:
        print(f"FATAL: got {len(sel['picks'])} picks, wanted {args.target}")
        return 1
    (OUT / "p4b_chunks.json").write_text(json.dumps(sel, indent=2, default=str), encoding="utf-8")
    items = build_items(picks=sel["picks"])
    (OUT / "p4b_items.json").write_text(json.dumps(items, indent=2), encoding="utf-8")
    print(f"wrote {OUT/'p4b_chunks.json'} and p4b_items.json ({len(items)} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
