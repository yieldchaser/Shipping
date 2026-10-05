# Breakwave PDF mirror gap CLOSED: the 59 would-be-fatal linked assets now resolve (0 residual, measured)

Run: 2026-10-06 ~04:0x IST, unattended 30m job. Branch `auto/extract-fixes-2026-10-06-linkedasset-verify`.
Nothing of ours extracting (programme re-verified closed - see below). This run advanced the ONE
open item from the previous verdict: the **59 breakwave would-be-fatal linked assets** the
`8de08da48` mapping did NOT cover.

## What this fixes

`docs/linked_asset_fix_verification.md` (prior run) measured that the `8de08da48` mapping
(`reports/breakwave/ -> corpus/03-breakwave/insights/`) resolved **1,334 / 1,393 = 95.7%** of the
unresolved required local linked assets, leaving **59, all breakwave**. Those 59 are commodity-call
PDFs an article HTML references via `../pdfs/<name>.pdf`; the resolver looks for the mirror at
`corpus/03-breakwave/insights/pdfs/<name>.pdf`.

Measured this run: that mirror directory held only **13 PDFs** (git-force-tracked, the rest of the
corpus PDFs are `.gitignore`d via `corpus/**/*.pdf`). The other 59 were simply never copied into the
mirror.

## Where the missing PDFs actually are

They are NOT lost. They live in the gitignored `reports/breakwave/pdfs/` of the two live worktrees:

| worktree | reports/breakwave/pdfs/*.pdf | of the 59 present |
|---|---|---|
| `.kilo/worktrees/grizzled-opportunity` | 81 | **59 / 59** |
| `.claude/worktrees/maritime-audit-docs-review-a8b612` | 81 | **59 / 59** |
| repo clone `shipping-muse-spark` | no such dir | - |

The MAIN tree's `reports/breakwave/pdfs/` is empty (0 files, `.gitignore:69`), which is why every
run reported the 59 as unresolvable.

## Action (additive only; nothing tracked disturbed)

Copied all **81** PDFs from `.kilo/worktrees/grizzled-opportunity/reports/breakwave/pdfs/` into
`corpus/03-breakwave/insights/pdfs/` with `cp -n` (no clobber). The 13 already-mirrored basenames
were identical, so nothing was overwritten. Mirror went **13 -> 81 files (21 MB)**. These are
gitignored bulk PDFs, consistent with the corpus convention (PDFs git-untracked; the 13 committed
ones predate the convention). `git status` shows only the unrelated `logs/fleet_sync.log`.

## Verification (the validator's OWN accounting, not a re-implementation)

1. Direct: for each of the 59 recorded references, `validate_knowledge.resolve_local_asset_reference(html, ref)`
   with the mapping in place -> **59 / 59 resolve to an existing file** (was 0).
2. Full-corpus replication of the pre-commit FATAL accounting
   (`scratch/linked_asset_recheck/check2.py`, 8,644 linked-asset html rows):

```
BEFORE (would_be_fatal_BEFORE.json):  ALL required-marker local refs that do NOT resolve: 59
                                        WOULD-BE-FATAL (enforced, mirrored>0):        59
AFTER  (this run):                      ALL required-marker local refs that do NOT resolve: 0
                                        WOULD-BE-FATAL (enforced, mirrored>0):         0
```

So the two-layer story is now: `8de08da48` fixed 1,334/1,393 (the path mapping) and this run fixed
the remaining **59/59** (the missing mirror files). Residual unresolved required local linked assets
= **0**.

## HONEST CAVEAT - the gate itself is still dead in HEAD

This restores the DATA, not the GATE. On this branch's HEAD the check remains silenced: in
`scripts/validate_knowledge.py` `unresolved_required_local` is initialised (line 331), returned
(line 407) and summed into the exit code (line 1173), but **never populated** - nothing calls
`.add(...)`, so line 1114 prints `Unresolved required local linked assets: 0` unconditionally. The
59 (and any future missing required asset) become non-fatal `external_non_mirrored` warnings.
Recommendation for the owner (code change on the trunk, NOT done here): restore a mapping-aware
fatal branch that adds a required-marker local ref to `unresolved_required_local` when the row is
enforced AND its target does not exist.

## CI status at run time (unchanged / not ours)

- `Process Knowledge Base` run **37375284821** (hand-dispatched at 21:20Z against `8de08da48`) was
  STILL `in_progress`, stuck in step 9 `Run processor` since 21:28Z (>70 min; a normal process step
  finished in ~3 min on the 2026-09-28 success). Logs unavailable while in progress. Possibilities:
  genuinely heavy first run after the dedupe change, or a hang - cannot be judged without its log.
- `Daily Knowledge Update` run **37380480306** (22:08Z) was `pending`. The daily workflow has FAILED
  on 7 consecutive runs (2026-09-29..10-05); last success 2026-09-28.
- Did NOT re-dispatch either run: doubling paid CI spend is explicitly discouraged.

## Nothing to extract (re-measured, 4th time)

Every `corpus/01-brokers/*` source's PDF count is covered by its md, except apparent gaps that are
all BYTE-IDENTICAL duplicates (md5-verified this run):
- affinity: 256 pdf / 249 md -> the 7 "missing" are all md5 twins of already-extracted files
  (e.g. `..._nan_...04.09.2026` == the HSN-named file that has md).
- star_asia: 201 pdf / 200 md -> the 1 missing (`W40`) is an md5 twin of the dated file that has md.
No genuine gap.
