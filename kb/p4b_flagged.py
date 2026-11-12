"""Build the C1 review packet for P4b: a seeded 30-item sample of the flagged extraction records.

Plan §10.2 says the two reference models' disagreements are adjudicated by a third family and that
C1 reviews 30 flagged items. `p4b_run.py` decides *which* reference records enter the reference set;
this script re-derives the same union so the reviewer sees the records as the adjudicator saw them:
the quote the extractor cited, the record JSON, both references' verdicts and the judge's reason.

Output: kb/reports/p4b_flagged.json (machine) + kb/reports/p4b_flagged.md (C1 packet).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import p4b_run as B  # noqa: E402
import runner as R  # noqa: E402

PHASE = "P4B_FLAGGED"
SAMPLE = 30
DROP_SHARE = 0.5  # half drops / half keeps, so the reviewer sees both error directions


def seed_for(phase: str) -> int:
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


def ref_verdicts(items: list[dict], adj: dict) -> list[dict]:
    """Every single-reference record, with the adjudicator's decision and both models' quotes."""
    refs = {m: B.evaluate(B.PASS_REF, m, items) for m in B.REFERENCE_MODELS}
    out = []
    for item in items:
        cid = item["chunk_id"]
        sents = [(int(s), t) for s, t in item["sentences"]]
        union: list[dict] = []
        for m in B.REFERENCE_MODELS:
            g = refs[m]["chunks"].get(cid)
            for rec in (B.flat_records(g, sents) if g else []):
                hit = None
                for u in union:
                    if B.records_match(rec[0], u["sig"], rec[1], u["quote"]):
                        hit = u
                        break
                if hit is None:
                    union.append({"sig": rec[0], "quote": rec[1], "kind": rec[2], "rec": rec[3],
                                  "models": {m}})
                else:
                    hit["models"].add(m)
        flagged = [u for u in union if len(u["models"]) < 2]
        for i, u in enumerate(flagged):
            dec, why = adj.get((cid, i), ("unadjudicated", ""))
            rec = u["rec"]
            out.append({
                "chunk_id": cid,
                "flagged_idx": i,
                "doc_id": item["doc_id"],
                "title": item["title"],
                "publisher": item["publisher"],
                "published_at": item["published_at"],
                "doc_type": item["doc_type"],
                "source_path": item.get("source_path") or item.get("rel_path") or item["doc_id"],
                "single_reference_model": sorted(u["models"]),
                "kind": u["kind"],
                "type": u["sig"][1],
                "entities": sorted(str(e) for e in u["sig"][2]),
                "evidence_quote": u["quote"][:600],
                "record_json": json.dumps(rec.model_dump() if hasattr(rec, "model_dump") else rec)[:1500],
                "adjudicator_decision": dec,
                "adjudicator_why": why,
            })
    return out


def pick(flagged: list[dict], seed: int) -> list[dict]:
    """Deterministic stratified sample: half judge-drops, half judge-keeps, spread over chunks."""
    rng = random.Random(seed)
    drops = [f for f in flagged if f["adjudicator_decision"] == "drop"]
    keeps = [f for f in flagged if f["adjudicator_decision"] == "keep"]
    n_drop = min(len(drops), int(round(SAMPLE * DROP_SHARE)))
    n_keep = min(len(keeps), SAMPLE - n_drop)
    chosen, seen_chunks = [], set()
    for pool, n in ((drops, n_drop), (keeps, n_keep)):
        pool = pool[:]
        rng.shuffle(pool)
        take = []
        # first pass: one record per chunk, so the sample is not dominated by one dense document
        for f in pool:
            if len(take) >= n:
                break
            if f["chunk_id"] not in seen_chunks:
                take.append(f)
                seen_chunks.add(f["chunk_id"])
        for f in pool:
            if len(take) >= n:
                break
            if f not in take:
                take.append(f)
        chosen.extend(take)
    rng.shuffle(chosen)
    return chosen


def main() -> int:
    items = B.load_items()
    adj_doc = json.loads((B.STATE / "adjudication.json").read_text(encoding="utf-8"))
    adj = {(d["meta"]["chunk_id"], d["meta"].get("idx")): (d.get("decision"), d.get("why") or "")
           for d in adj_doc.get("items", [])}
    flagged = ref_verdicts(items, adj)
    seed = seed_for(PHASE)
    sample = pick(flagged, seed)
    # real corpus paths for the reviewer (items carry doc_id only; `document.path` is authoritative)
    import duckdb  # local import: only the packet build touches DuckDB

    con = duckdb.connect(str(B.DB), read_only=True)
    con.execute("SET memory_limit='700MB'")
    con.execute("SET threads=2")
    paths: dict[str, str] = {}
    for f in sample:
        if f["doc_id"] not in paths:
            row = con.execute("select d.path from document d where d.doc_id=?", [f["doc_id"]]).fetchone()
            paths[f["doc_id"]] = row[0] if row else "?"
        f["source_path"] = paths[f["doc_id"]]
    con.close()
    counts = {d: sum(1 for f in flagged if f["adjudicator_decision"] == d)
              for d in ("keep", "drop", "unadjudicated")}
    doc = {
        "phase": PHASE,
        "sample_seed": seed,
        "selection_rule": ("flagged reference records = admitted by exactly one of the two reference "
                           "models; stratified half adjudicator-drops / half adjudicator-keeps, one "
                           "record per chunk first, seeded shuffle"),
        "scope": {"gold_chunks": len(items), "flagged_pool": len(flagged), "pool_by_decision": counts,
                  "sample_size": len(sample)},
        "adjudicator": adj_doc.get("adjudicator"),
        "reference_models": B.REFERENCE_MODELS,
        "items": sample,
    }
    out_json = KB / "reports" / "p4b_flagged.json"
    out_json.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")

    lines = ["# P4b flagged-extraction sample (C1 review packet)\n",
             f"Seed {seed} (`seed_for(\"{PHASE}\")`), {len(sample)} of {len(flagged)} flagged "
             f"reference records ({counts}). Flagged = exactly one reference model extracted it; the "
             f"third-family adjudicator ({doc['adjudicator']}) decided keep/drop.\n",
             "Review question per item: does the quote support the record as written? Mark "
             "`ok / over-claim / wrong entity / wrong number / missing (should have been extraced)`.\n"]
    for n, f in enumerate(sample, 1):
        lines.append(f"### {n}. {f['adjudicator_decision'].upper()} -> "
                     f"{f['publisher']} {f['published_at']} ({f['doc_type']})\n")
        lines.append(f"- chunk `{f['chunk_id']}` doc `{f['doc_id']}` ord-packed gold item; "
                     f"source {f['source_path']}")
        lines.append(f"- flagged by `{f['single_reference_model'][0]}`: `{f['kind']}` type "
                     f"`{f['type']}`, entities {f['entities']}")
        lines.append(f"- quote: \"{f['evidence_quote'].strip()[:400]}\"")
        lines.append(f"- record: `{f['record_json']}`")
        lines.append(f"- adjudicator: {f['adjudicator_decision']} - {f['adjudicator_why']}\n")
    (KB / "reports" / "p4b_flagged.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_json} ({len(sample)} items, pool {len(flagged)}, {counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
