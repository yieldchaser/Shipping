"""
Repair the hellenic knowledge chunk shards that are EMPTY or PARTIAL.

Background (docs/text_audit_recheck_verdict.md): commit 87ca94041 left 11
hellenic chunk shards at zero bytes and 6 more partially written; daily runs
never healed them because artifacts_current() only tested file existence.

The 2026-09-23 remediation ("re-run the chunk compiler") does not work as
literally written: the reports/hellenic -> corpus/02-hellenic migration left
documents.jsonl source_path pointing at reports/hellenic (a partial tree whose
linked pdfs/assets are missing), so BOTH the source resolution AND the
in-document linked-asset resolution fail there.  Measured this run: with the
reports/hellenic source a re-ingest DROPS every `## Linked asset:` section
(corpus/02-hellenic holds the linked pdfs/assets, reports/hellenic does not);
with the corpus/02-hellenic source the re-ingest is LOSSLESS (the only delta is
the `Source asset:` path prefix, reports -> corpus, i.e. a stale-path fix).

So this repair resolves each hellenic source through corpus/02-hellenic, keeps
the LLM off (reuses stored metadata), re-ingests the affected documents, then
compacts the touched shards (dedup by chunk_id; drop stale doc_ids).

Usage:
    python scripts/repair_hellenic_shards.py --categories shipbuilding vessel_valuations [--dry-run]
    python scripts/repair_hellenic_shards.py --categories iron_ore            # separate two-writer family
"""

import argparse
import sys
import traceback
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import process_knowledge as pk

MIN_SHARD_BYTES = 64
CORPUS_PREFIX = "reports/hellenic/"


def resolve_source(sp: str) -> Path | None:
    """Prefer corpus/02-hellenic (holds html + linked pdfs/assets); fall back."""
    if sp.startswith(CORPUS_PREFIX):
        alt = pk.REPO_ROOT / ("corpus/02-hellenic/" + sp[len(CORPUS_PREFIX):])
        if alt.exists():
            return alt
    primary = pk.REPO_ROOT / sp
    if primary.exists():
        return primary
    return None


def disk_chunk_count(p: Path) -> int:
    if not p.exists():
        return -1
    n = 0
    for row in pk.load_jsonl(p):
        if isinstance(row, dict):
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", nargs="+", default=["shipbuilding", "vessel_valuations"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sources-file", default=None,
                    help="Explicit newline list of hellenic source_path values to re-ingest.")
    args = ap.parse_args()

    rows = pk.load_manifest_rows()
    index = {row.get("source_path"): row for row in rows}

    declared = defaultdict(int)
    shard_rows = defaultdict(list)
    for row in rows:
        if row.get("source") != "hellenic":
            continue
        if row.get("category") not in args.categories:
            continue
        cf = row.get("chunk_file") or ""
        if not cf:
            continue
        declared[cf] += int(row.get("chunk_count") or 0)
        shard_rows[cf].append(row)

    short = {}
    for cf, decl in declared.items():
        p = pk.REPO_ROOT / cf
        got = disk_chunk_count(p)
        if got < decl:
            short[cf] = (decl, got)

    print(f"[REPAIR] categories={args.categories}")
    print(f"[REPAIR] short shards: {len(short)}")
    for cf in sorted(short):
        d, g = short[cf]
        print(f"    {cf}: declared={d} disk={g} rows={len(shard_rows[cf])}")

    victims = []
    for cf in short:
        for row in shard_rows[cf]:
            src = resolve_source(row.get("source_path") or "")
            if src is None:
                print(f"[SKIP] missing source: {row.get('source_path')}")
                continue
            victims.append((row, src))
    if args.sources_file:
        wanted = {ln.strip() for ln in Path(args.sources_file).read_text(encoding="utf-8").splitlines() if ln.strip()}
        by_sp = {row.get("source_path"): row for row in rows if row.get("source") == "hellenic"}
        victims = []
        for sp in wanted:
            row = by_sp.get(sp)
            if row is None:
                print(f"[SKIP] no manifest row for {sp}")
                continue
            src = resolve_source(sp)
            if src is None:
                print(f"[SKIP] missing source: {sp}")
                continue
            victims.append((row, src))

    print(f"[REPAIR] documents to re-ingest: {len(victims)}")
    if args.dry_run:
        resolved_corpus = sum(1 for _, s in victims if "02-hellenic" in str(s))
        print(f"[DRY-RUN] resolved via corpus override: {resolved_corpus}/{len(victims)}")
        return 0
    if not victims:
        return 0

    processed = errored = 0
    touched_chunks = set()
    stale_doc_ids = defaultdict(set)
    path_mismatch = []
    for row, src in victims:
        rel = row["source_path"]
        try:
            existing_metadata = pk.load_existing_metadata(row) or {}
            adapted = pk.adapt_source_file(
                row["source"], row["category"], src, False, existing_metadata=existing_metadata
            )
            out_meta, _chunks, manifest_row = pk.process_file(
                src, adapted, source_hash_value=pk.source_hash(src)
            )
            new_doc_path = manifest_row.get("doc_path")
            if new_doc_path and new_doc_path != row.get("doc_path"):
                path_mismatch.append((rel, row.get("doc_path"), new_doc_path))
            old_doc_id = row.get("doc_id")
            new_doc_id = manifest_row.get("doc_id")
            chunk_rel = manifest_row.get("chunk_file")
            if chunk_rel:
                touched_chunks.add(chunk_rel)
                if old_doc_id and new_doc_id and old_doc_id != new_doc_id:
                    stale_doc_ids[chunk_rel].add(old_doc_id)
            index[rel] = manifest_row
            processed += 1
            if processed % 25 == 0:
                print(f"[REPAIR] progress: {processed} docs")
        except Exception as exc:
            errored += 1
            pk.log_error(src, f"repair_hellenic_shards: {exc}\n{traceback.format_exc()}")
            print(f"[ERR] {rel}: {exc}")

    for chunk_rel, remove_ids in stale_doc_ids.items():
        pk.compact_chunk_file(pk.REPO_ROOT / chunk_rel, remove_doc_ids=remove_ids)
    for chunk_rel in touched_chunks:
        pk.compact_chunk_file(pk.REPO_ROOT / chunk_rel)

    if not args.dry_run:
        pk.write_manifest_rows(list(index.values()))

    print(f"[REPAIR] md path divergence: {len(path_mismatch)}")
    for rel, old, new in path_mismatch[:10]:
        print(f"    {rel}: old={old} new={new}")

    for cf in sorted(short):
        p = pk.REPO_ROOT / cf
        size = p.stat().st_size if p.exists() else 0
        got = disk_chunk_count(p)
        print(f"[REPAIR] {cf}: declared={short[cf][0]} now={got} bytes={size:,}")

    print(f"[DONE] processed={processed} errors={errored}")
    return 1 if errored > max(1, len(victims) // 4) else 0


if __name__ == "__main__":
    raise SystemExit(main())
