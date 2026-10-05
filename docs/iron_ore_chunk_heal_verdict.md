# Iron-ore knowledge chunk heal + `parse_number` ×1000 regression (2026-10-05 overnight)

Trigger: the 2026-10-04 23:5x run filed "heal the empty/partial hellenic chunk shards"
as the next non-paid target. This run re-measured the tier and acted.

## 1. State change since the 00:20 note (measured this run)

- The 11 EMPTY shards listed on 2026-10-04 (hellenic shipbuilding 2014/2021-2024,
  vessel_valuations 2014/2021-2025) are **already healed** - commit `0924975de`
  (2026-10-05, "restore 1:1 file mirror in reports/") rewrote them. On-disk chunks
  went 89,151 -> 92,299 before this run's work.
- Remaining short shards at run start = **3**, ALL `hellenic_iron_ore`:
  - `hellenic_iron_ore_2021.jsonl` declared 9,539 / disk 9,332 (all 114 docs present;
    the gap was a -2/doc count artefact, 0 docs missing)
  - `hellenic_iron_ore_2022.jsonl` declared 17,380 / disk 6,544 (**155 of 235 docs
    entirely absent**)
  - `hellenic_iron_ore_2026.jsonl` declared 4,908 / disk 1,752 (**116 of 184 docs
    entirely absent**)
  - All three are referenced by `index.html` QA_CHUNK_FILES (ironOre tab: 2022 =
    deep_historical, 2026 = recent) -> silent Q&A coverage loss.

There were **0 docs declared>0 with 0 chunks anywhere** for 2021 (count artefact only);
155 and 116 real doc-level gaps in 2022/2026.

## 2. What was run

`python3 scripts/repair_hellenic_shards.py --categories iron_ore`
- resolves each stale `reports/hellenic/...` `source_path` through the
  `corpus/02-hellenic/...` override (measured: `reports/hellenic` holds the html but
  **0** linked `.jpg`/pdf assets; `corpus/02-hellenic` holds both - so only the corpus
  path is lossless), LLM OFF (reuses stored metadata).
- **533/533 processed, 0 errors**.

Chunks after (SERVED tier, correct):
- 2021: 9,332 -> 9,540 lines
- 2022: 6,544 -> 17,381 lines
- 2026: 1,752 -> 4,911 lines
- Re-audit: **short shards = 0; docs declared>0 with 0 chunks anywhere = 0**;
  total on-disk chunks 92,299 -> 106,514.
- The chunk text carries the RAW page numbers, verified correct: e.g. `30.43`
  (C3 Tubarao-Qingdao USD/t) and `13.21` (C5 W.Australia-Qingdao) appear as printed;
  **no ×1000 tokens** in any of the 3 shards.

## 3. REGRESSION found and reverted: `parse_number` ×1000 corrupts decimal values

The same run regenerated the `knowledge/docs|trees/hellenic/iron_ore/**` md through
`process_knowledge.parse_number`, which since commit `35b468aa6` (2026-06-23,
"Fix spot scaling...") multiplies **any** decimal in `[5.0, 100.0)` by 1000:

```python
if "." in match.group(0) and 5.0 <= val < 100.0:
    val *= 1000.0
```

For iron ore that is catastrophic and verified against the source PDF
(`corpus/02-hellenic/iron_ore/pdfs/2022/...2022-05-09...pdf`, page 1, read with pymupdf):

| page ground truth | old md (HEAD) | regenerated md |
|---|---|---|
| `30.43` C3 Tubarao-Qingdao USD/t | `30.43` OK | `30430.0` WRONG |
| `13.21` C5 W.Australia-Qingdao | `13.21` OK | `13210.0` WRONG |
| `5.78%` (prose) | `5.78` OK | `5780.0` WRONG |
| `87.4`, `93.75` | correct | `87400.0`, `93750.0` WRONG |

Control (doc that predates the repair, `2022-01-04`): HEAD md `87400`=0 / `93750`=0,
regenerated md `87400`=2 / `93750`=2. So the regression is **introduced by the
re-ingest**, not pre-existing.

**Action taken:** `git checkout HEAD -- knowledge/docs/hellenic/iron_ore
knowledge/trees/hellenic/iron_ore` (518 docs + 518 trees restored to the reviewed,
correct md). The CHUNK heal was KEPT (chunks are raw text, correct, and are what the
app serves). `knowledge/manifests/documents.jsonl` was KEPT (533 iron_ore rows updated:
`source_path` -> `corpus/02-hellenic`, `chunk_count` -> actual; 10,202 rows, 0 dup
paths - only iron_ore rows changed).

Known cosmetic residue: the reverted md frontmatter says `source_path: reports/...`
while the manifest now says `corpus/02-hellenic/...`. Both paths exist.

## 4. Root cause / next-run target (NOT applied - needs per-source decision)

`parse_number`'s ×1000 rule is a GLOBAL heuristic. It is right for the OCR case it was
written for (`9.750` meaning 9750, i.e. a *three*-decimal token) but fires on every
two-decimal value in [5,100) - iron ore's C3/C5 freight rates and its percentages.
A scoped fix would distinguish by SHAPE (exactly 3 decimals after the dot) rather than
by the float value, but that must be validated per source before changing a shared
parser (the user's "numbers are PER SOURCE" rule). Do NOT re-run
`repair_hellenic_shards.py --categories iron_ore` until that is decided, or the md
tier will be re-corrupted.

Nothing else was mutated this run; the unrelated sibling edit
`scripts/extract/publishers/run_fearnleys_normalized.py` was left untouched.
