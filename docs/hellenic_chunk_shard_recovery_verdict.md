# Hellenic chunk shards: 17 zeroed on disk, recovered + root-caused (2026-10-05 22:5x)

## What was found (measured)
On the first check this run, **17 hellenic knowledge chunk shards** were 0 bytes on
disk, every one with mtime `2026-10-05 22:06`. `git diff --numstat` showed
`0 lines added, N lines removed` for each - a pure truncation, no rewrite.

| shard | bytes in HEAD | rows lost |
|---|---:|---:|
| hellenic_iron_ore_2021.jsonl | 26,536,423 | 9,540 |
| hellenic_iron_ore_2022.jsonl | 48,090,172 | 17,381 |
| hellenic_iron_ore_2026.jsonl | 13,991,625 | 4,911 |
| hellenic_shipbuilding_2014 | 905 | 1 |
| hellenic_shipbuilding_2021..2026 | ~6.3 MB | 2,134 |
| hellenic_vessel_valuations_2014 | 932 | 1 |
| hellenic_vessel_valuations_2021..2026 | ~2.6 MB | 1,142 |

Totals: **97,950,982 bytes (98.0 MB), 35,110 rows** lost; the content still existed in
HEAD and was declared in `knowledge/chunks/index.json` (e.g. iron_ore_2021 declared
25,013,851 bytes).

## Recovery
Targeted `git checkout HEAD -- <the 17 paths>` (not a broad checkout). Verified: every
byte size and row count now matches the removed counts exactly, and
`git status --short knowledge/chunks/` is clean (0 modified). The recovery is
byte-identical to HEAD, so it is independent of any commit.

## Root cause (proven mechanism)
`scripts/process_knowledge.py::compact_chunk_file()` truncated the live shard **in
place** and then re-appended rows one at a time:

    path.write_text("", encoding="utf-8", newline="
")
    for row in deduped_rows:
        append_jsonl(path, row)

Any interruption after the truncation loses the *entire* shard. Both
`process_knowledge.py` (daily CI + local runs) and `scripts/repair_hellenic_shards.py`
(created 2026-10-05 11:09 for exactly this family) call it. 17 shards at exactly 0
bytes means the append loop never executed on each - i.e. the writer died between
truncation and the first append.

The 6 zero-byte *bare* parent shards (hellenic_demolition.jsonl etc., mtime
2026-06-22) are a different, older, intentional state - left untouched.

## Fix (applied, uncommitted)
`compact_chunk_file()` now writes the deduped rows to `*.compact.tmp` and
`os.replace()`s it onto the target, so an interrupted run leaves the previous shard
intact. This is the skill lesson "long extractions must persist partial output" /
never truncate in place.

Verified by direct unit test against the patched function:
- dedup keeps the LAST row per chunk_id (b, a) and writes 2 rows - correct;
- no `.compact.tmp` left behind on success;
- **simulated mid-write crash: the original 78-byte file is preserved intact**
  (before the fix it was truncated to 0). A leftover `.compact.tmp` on crash is inert.

`python -m py_compile scripts/process_knowledge.py` OK.

## Honest limits
- **Which process zeroed them is inferred, not measured**: no python process was alive
  at 22:47 (only the Hermes gateway, litellm and code_review_graph serve). The
  22:06 writer had already exited. The *mechanism* (truncate-first) is proven; the
  *trigger* (an interrupted `process_knowledge.py` or `repair_hellenic_shards.py` run)
  is the only consistent explanation.
- The served QA tier is unaffected: `knowledge/chunks/index.json` `generated_at` is
  still `2026-09-29T17:23:36Z` (the daily knowledge commit is frozen by the CI
  `Validate knowledge artifacts` failure), so nothing was serving these shards live.

## Loose ends
- The prior run's mirror-dedupe fix in `process_knowledge.py`
  (`prune_superseded_mirror_rows` / `dedupe_manifest_rows_by_doc_id`) and this
  durability fix are both in the working tree/index on `main`, **uncommitted**
  (a parallel automation is active on `main`). HEAD does not carry either, so the CI
  `Validate knowledge artifacts` step will keep failing until one of them lands on
  `main`.
- `scripts/repair_hellenic_shards.py` should not be re-run as-is until the durability
  fix is on `main`; it inherits the same truncate-first hazard through
  `pk.compact_chunk_file` (it now inherits the safe version).
