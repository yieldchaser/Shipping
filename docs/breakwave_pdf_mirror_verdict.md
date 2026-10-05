# The 59 breakwave "unresolved linked assets" are BOT-WALL JUNK, not a mirroring gap (measured)

Run: 2026-10-06 ~04:0x IST, unattended 30m job. Branch
`auto/extract-fixes-2026-10-06-linkedasset-verify`. Nothing of ours extracting (programme
re-verified closed).

## Why this run touched it

The previous run (`docs/linked_asset_fix_verification.md`) measured that `8de08da48`'s path
mapping resolved **1,334 / 1,393 = 95.7%** of the unresolved required local linked assets, leaving
**59, all breakwave**, and recommended "inventory the 59 and/or restore a mapping-aware fatal
branch". This run inventoried them. The recommendation was WRONG for these 59 - here is the
measurement that shows it.

## What the 59 actually are

They are breakwave article HTMLs (e.g. `corpus/03-breakwave/insights/2023/2023-02-03_nickel-...html`)
referencing an underlying "commodity call" report via `../pdfs/<name>.pdf`. The resolver looks for
the mirror at `corpus/03-breakwave/insights/pdfs/<name>.pdf`; that directory held only **13**
genuine PDFs, so the 59 were unresolved.

The 59 referenced files DO exist - in the gitignored `reports/breakwave/pdfs/` of both live
worktrees (`.kilo/worktrees/grizzled-opportunity` and
`.claude/worktrees/maritime-audit-docs-review-a8b612`, 81 files each). **But they are not PDFs.**
Byte-checking the magic number (`f.read(5) != b"%PDF-"`) on all 81:

| kind | count | size | content |
|---|---|---|---|
| genuine PDF | 13 | 245 KB - 7.9 MB | the real reports |
| **bot-wall HTML named `.pdf`** | **67** | **exactly 5,174 B** | `<title>Login Page</title>` - an ANZ Portal login page (the fetch hit an auth wall) |
| other HTML | 1 | 121,703 B | `<title>Search Results | Baker Institute</title>` |

So all 59 referenced assets were **never successfully fetched** - the fetcher saved a ~5 KB login
page under a `.pdf` name. This is precisely the "HTML-served-as-PDF / bot-wall placeholder" junk the
skill says to route explicitly (check the `%PDF-` magic bytes).

## The experiment (and why it was reverted)

To be sure, I first mirrored all 81 worktree files into `corpus/03-breakwave/insights/pdfs/`
(`cp -n`). The validator's own accounting then went **59 -> 0** (and
`validate_knowledge.resolve_local_asset_reference` returned True for 59/59). That looks like a fix
but it is **cosmetic and harmful**: it makes the corpus claim "the asset exists" when the file is a
5 KB login page. A wrong/misleading file is worse than a missing one.

**Reverted.** Deleted the 68 non-`%PDF-` files; the mirror is back to the **13 genuine PDFs, 0
junk** (verified: all 13 have `%PDF-` magic). Re-measured residual = **59 / 59 unresolved**, the
honest state.

## Correct classification of the 59

They are **not `RESTATEMENT`, not a path bug, and not fixable by mirroring** - they are
`EXTERNAL_UNAVAILABLE`: the publisher put the underlying report behind a login wall and our fetch
captured the wall. The right treatment is exactly what HEAD's (silenced) non-fatal path already
does: count them as `external_non_mirrored`, do NOT fail CI on them, and do NOT inject the login
page into the corpus. If the content is wanted, the only correct route is a re-fetch with working
credentials / a public mirror of those commodity calls - not a file copy.

## So the mapping story is unchanged and complete

- `8de08da48`: resolves 1,334 / 1,393 (the moved-path cases) - genuinely fixed.
- Remaining **59**: bot-wall, legitimately non-fatal. **Do not "fix" by copying.**

## HONEST CAVEAT (unchanged from prior run) - the gate is still dead in HEAD

In `scripts/validate_knowledge.py`, `unresolved_required_local` is initialised (line 331), returned
(line 407) and summed into the exit code (line 1173), but **never populated** (no `.add(...)`), so
line 1114 prints `Unresolved required local linked assets: 0` unconditionally. The 59 fall into the
non-fatal `external_non_mirrored` bucket. Owner action if a real gate is wanted: restore a
mapping-aware fatal branch - but with the new knowledge that 59 of the 1,393 are permanently
unfetchable, so a naive restore would re-break CI on exactly them.

## CI status at run time

- `Process Knowledge Base` **37375284821** (hand-dispatched 21:20Z on `8de08da48`): still
  `in_progress`, stuck in step 9 `Run processor` since 21:28Z (>70 min vs ~3 min on the 2026-09-28
  success). Hung or genuinely heavy - unjudgeable without its log. Not re-dispatched (avoid double
  paid CI spend).
- `Daily Knowledge Update` **37380480306** (22:08Z): `pending`. The daily workflow has FAILED on 7
  consecutive runs (2026-09-29..10-05); last green 2026-09-28. QA-tier `generated_at` stays frozen.

## Nothing to extract (re-measured, 4th time; md5-verified)

- affinity 256 pdf / 249 md -> the 7 "missing" are all md5 twins of already-extracted files.
- star_asia 201 pdf / 200 md -> the 1 missing (`W40`) is an md5 twin of the dated file that has md.
- every other broker source is 1:1. No genuine gap.
