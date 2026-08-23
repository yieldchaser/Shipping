"""
One-off repair: regenerate the hellenic iron-ore chunk shards for 2023-2025
that were truncated to zero bytes by commit 87ca94041 ("partial knowledge
build"). Daily runs never healed them because artifacts_current() only checks
file existence, and an empty shard still exists.

Re-ingests every archived iron_ore report whose yearly shard is empty,
reusing stored LLM metadata (no LLM calls), then compacts the rebuilt shards.
Derived outputs are refreshed afterwards via `process_knowledge.py
--derived-only` (search indexes included through the B1 hook).
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import process_knowledge as pk

TARGET_YEARS = {"2023", "2024", "2025"}
MIN_SHARD_BYTES = 64


def main() -> int:
    rows = pk.load_manifest_rows()
    index = {row.get("source_path"): row for row in rows}
    meta_index = pk.build_existing_metadata_index(pk.load_manifest_rows())

    victims = []
    empty_shards = {}
    for rel, row in index.items():
        if row.get("source") != "hellenic" or row.get("category") != "iron_ore":
            continue
        chunk_rel = row.get("chunk_file") or ""
        year = chunk_rel.rsplit("_", 1)[-1].replace(".jsonl", "")
        if year not in TARGET_YEARS:
            continue
        shard = pk.REPO_ROOT / chunk_rel if chunk_rel else None
        size = shard.stat().st_size if shard and shard.exists() else 0
        if size < MIN_SHARD_BYTES:
            empty_shards[chunk_rel] = size
            src = pk.REPO_ROOT / row["source_path"]
            if src.exists():
                victims.append((rel, row))
            else:
                print(f"[SKIP] missing source: {row['source_path']}")

    print(f"[REPAIR] empty shards: { {k: v for k, v in sorted(empty_shards.items())} }")
    print(f"[REPAIR] documents to re-ingest: {len(victims)}")
    if not victims:
        return 0

    processed = errored = 0
    touched_chunks = set()
    stale_doc_ids = {}
    for rel, row in victims:
        path = pk.REPO_ROOT / rel
        try:
            existing_metadata = meta_index.get(rel) or {}
            adapted = pk.adapt_source_file(
                row["source"], row["category"], path, False, existing_metadata=existing_metadata
            )
            _, _, manifest_row = pk.process_file(
                path, adapted, source_hash_value=pk.source_hash(path)
            )
            old_doc_id = row.get("doc_id")
            new_doc_id = manifest_row.get("doc_id")
            chunk_rel = manifest_row.get("chunk_file")
            if chunk_rel:
                touched_chunks.add(chunk_rel)
                if old_doc_id and new_doc_id and old_doc_id != new_doc_id:
                    stale_doc_ids.setdefault(chunk_rel, set()).add(old_doc_id)
            index[rel] = manifest_row
            processed += 1
            if processed % 25 == 0:
                print(f"[REPAIR] progress: {processed} docs")
        except Exception as exc:
            errored += 1
            pk.log_error(path, f"repair_iron_ore_shards: {exc}\n{traceback.format_exc()}")
            print(f"[ERR] {path.name}: {exc}")

    for chunk_rel, remove_ids in stale_doc_ids.items():
        pk.compact_chunk_file(pk.REPO_ROOT / chunk_rel, remove_doc_ids=remove_ids)
    for chunk_rel in touched_chunks:
        pk.compact_chunk_file(pk.REPO_ROOT / chunk_rel)

    pk.write_manifest_rows(list(index.values()))
    for chunk_rel in sorted(empty_shards):
        shard = pk.REPO_ROOT / chunk_rel
        size = shard.stat().st_size if shard.exists() else 0
        print(f"[REPAIR] {chunk_rel}: {size:,} bytes after rebuild")

    print(f"[DONE] processed={processed} errors={errored}")
    return 1 if errored > len(victims) // 4 else 0


if __name__ == "__main__":
    raise SystemExit(main())
