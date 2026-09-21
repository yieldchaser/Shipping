# Extraction overnight log (deep-review agent)

## 2026-09-21 23:40 IST (18:10 UTC) - validation fire

Verdict: **FIXED** (three code fixes committed, no corpus data touched) with one
unexplained data-destroying defect escalated as **NEEDS HUMAN DECISION**.

Run state at review time: checkpoint 1,700 / 7,816 planned, status ok 1,626,
error 71 (not-a-pdf, correct quarantine), timeout 3. Live `run_batch` pid 7376
with 2 `batch_worker` children: normal, single batch, lock honoured, zero
duplicate checkpoint rows.

### Tooling (asked for explicitly)

| Tool | Worked | Notes |
|---|---|---|
| `verify_extraction.py` | yes | JSON output; exit 0 before the fix, exit 1 with named actions after it |
| reading document outputs | yes | read text/tables/pages/charts meta for 1,634 doc dirs |
| `git` | yes | branch + 3 commits, verified with `git show --stat` |
| `python3` on PATH | intermittent | the documented prefix alone is not enough; it needs `Microsoft/WindowsApps` (or call `Python314/python.exe` directly) |
| `du` / `find` over the corpus tree | **fails** | timed out at 180 s on ~20k files under MSYS; use an `os.scandir` walk instead (1.9 s for the whole tree) |

### Measurements (not estimates)

* Output: 1,634 doc dirs, 1.06 GB, 25 sources. Tables read: 33,698 with 2,562,359 non-empty cells.
* Per source, tables / text_verified mean: hellenic 25,107 / 0.804, seabrokers 4,290 / 0.919,
  drybulk 2,035 / **1.000**, Lloyds Atlas 3,183 / 0.720, breakwave 283 / 0.954.
* Page routes across 10,041 pages: text 7,384, image-heavy 2,150, garbled 316, scanned 175, empty 16.
* Reconciliation is live and does find real dropped values: 11,938 page-level
  `values_only_in_text` entries; e.g. Amplify BDRY page 0 holds `6.46, 38.64, 51.52, 115.47`
  that no grid captured. It is also noisy: 9,274 of those are bare integers, many
  are page numbers (`13`, `7`, `3`) or DOI fragments (`0000`, `0001`) from the
  journal PDF, plus chart-axis round numbers.
* Golden gate re-run after the changes: Star Asia 15/15 table cells via
  pymupdf-text and pdfplumber-text, camelot-stream 13/15 (its documented 87%),
  SSY 100%, Breakwave 100% via text. No regression;
  `scripts/analysis/golden_matrix.json` unchanged.

### Finding 1 (fixed): glyph-mojibake was invisible to every counter

The Hellenic lineage (51% of the corpus by count) embeds a subset font with no
usable ToUnicode map for part of its content. Raw evidence from
`2021-07-14_mmi-daily-iron-ore-index-report`, table on page 1, engine
camelot-stream, `text_verified_cells: 53/53`:

    'ĞǆƉĞĐƚĂƟŽŶƐ͘ W& Ăƚ ^ŚĂŶĚŽŶŐ ƉŽƌƚ ĚĞĂůƚ ϭϰϴϬǇƵĂŶͬŵƚ͕' = "expectations. PP& at Shandong port dealt 1480yuan/mt,"
    'ŽƌĞ ŝŵƉŽƌƚĞĚ ĨĞůů ƐůŝŐŚƚůǇ ďǇ Ϭ͘ϰϮй DŽD ƚŽ ϴϵ͘ϰϭϳ Dƚ'       = "ore imported fell slightly by 0.42% MoM to 89.417 Mt"
    '/ZKE KZ WKZd ^dKZ< /E Y  ;/KW/Ϳ'                             = "IRON ORE PORT STOCK INDEX (IOPI)"

Those cells hold no ASCII digit, and `text_verified` only checks cells matching
a digit, so they are excluded from reconciliation entirely: the metric reported
full confidence on a table whose values are unreadable. Scale: 22,550 garbled
cells of 732,783 in hellenic, of which 6,091 contain glyph-encoded digits; 6,152
of 23,694 hellenic tables (26%) hold at least one; zero tables are entirely
mojibake, and ASCII-digit data cells (761, 885, 708, 924, 132.71) are clean.
Predicate precision measured corpus-wide: 19,257 / 284,690 hellenic blocks
(6.8%) and **0 / 103,243 blocks in every other source**, so accented Latin-1
(Portuguese/Danish Seabrokers) does not false-positive.

Fixed as accounting, not as routing: `garbled_blocks` per page and per document,
`garbled_cells` per table, plus an OCR-queue flag for majority-mojibake pages.
Routing deliberately untouched: those pages still yield tables, and the tables
are where their numeric values actually come from.

### Finding 2 (fixed): `--resume` cannot retry a failure and said it could

`run_batch.load_done` keeps every recorded path, so all 74 non-ok rows (71
not-a-pdf, 3 timeouts) were in the done-set: `--resume` skipped 74 of 74
failures. The batch still printed "rerun the same command with --resume to retry
the failures", and the runbook says for accumulating timeouts to raise
`--timeout`. The 3 timeouts died at `secs: 900.2` against `--timeout 900`, so
that advice is provably insufficient: the documented remedy does nothing. Added
`--retry-failed` (measured: the default keeps 74 as done, `--retry-failed`
releases all 74) and the closing message now states what resume actually does.

### Finding 3 (fixed): the hourly verifier audited 39% of the tree and hid silent failures

`check_outputs` scanned `dirs[:600]` of 1,634 doc dirs. Measured both ways on the
same corpus: capped reported `empty_unexpected: 0`, uncapped reported 11 real
silent failures plus 3 timeout victims plus 2 in-flight docs. At 7,816 docs the
cap would have covered under 8%. Now uncapped (0.4 s) and classified against the
checkpoint, so it alarms on defects rather than on documents being written.

### Finding 4 (NOT fixed, escalated): 11 documents recorded ok with no artefacts

All Hellenic MMi dailies: 2022-11-21..24, 2023-01-09..12, 2023-01-31..02-02.
Each carries `status: ok, blocks: 706, tables: 36, images: 2, secs: 44.9` in the
checkpoint, yet the directory holds only `charts/*.jpeg`. Missing: text.jsonl,
tables.jsonl, pages.jsonl and charts/meta.jsonl, i.e. every file written at the
end of `process_one`, while the per-page images written during the page loop
survive. 11 of 432 MMi docs, in 4 bursts of 3-4 consecutive docs between 22:46
and 23:00 IST. The class grew during the review (6 -> 9 -> 11), so it may still
be growing.

Cause not established, and I did not guess one into the code. What is excluded:
re-extracting 2022-11-21 now reproduces a complete output in 42.9 s (706 blocks,
36 tables); one inventory entry, one checkpoint row and one dir per document; no
path collision; no code in `scripts/extract/` deletes artefacts (the only
removals are of the batch lockfile, plus an atomic `os.replace` of the state
file); the parent directory mtime (22:48:39) is not later than its checkpoint
row, so nothing touched that directory afterwards.

### Concurrent-session interference (please read)

Another agent is working the same checkout. Its reflog: commit 23:04:58, "reset:
moving to HEAD" 23:07:43, rebase onto origin/main 23:08:31-34, `git stash` and
`git reset --hard` at 23:10:31-33, `stash@{0}: On main: bot data churn during sp2
rebase`. Effects felt here: my working-tree edits to `scripts/extract/*.py` were
reverted mid-verification (the first scratch document showed the fix, the next
two did not), and `git add` failed once on a live `.git/index.lock`. I did not
touch their processes, stash or branch. My commits are safe on
`auto/extract-fixes-2026-09-21`, and the working tree still carries them.
Anyone re-running verification should hash `scripts/extract/*.py` before and
after, as done here (`32283ef9717f`, `1617128da942`, `71205c01058c`).

### Changes

Branch `auto/extract-fixes-2026-09-21` (not pushed, not merged):

* `26dc82134` fix(extract): make glyph-mojibake and timeout-killed outputs
  visible; stop resume lying about retries. `extract_all.py` +72,
  `run_batch.py` +28/-2, `verify_extraction.py` +8/-1.
* `c604c3809` fix(verify): classify empty output dirs against the checkpoint.
  `verify_extraction.py` +48/-9.
* this log entry.

Verified before committing: the patched extractor re-run on 3 documents
(hellenic mojibake, drybulk clean, seabrokers accented) wrote outputs identical
to their corpus counterparts on text.jsonl / tables.jsonl / pages.jsonl once the
new keys are ignored, so nothing but instrumentation changed. New keys behave:
hellenic garbled_blocks 66 and garbled_cells 78; drybulk and seabrokers 0.
Scratch out-dir `data/extracted/scratch_review` deleted afterwards.

### Deliberately NOT changed

* Nothing was re-extracted and no already-extracted data was rewritten. The new
  counters apply from now on; the existing 1,634 docs keep the old schema
  (absent key means not measured).
* Mojibake repair for the 1,026 already-extracted hellenic docs: not attempted.
  Making 22,550 garbled cells readable is a font-level decoding change with a
  real blast radius, so it is a human decision.
* `route_page`'s garbled threshold untouched: changing it would suppress table
  extraction on those pages, which is where their values come from.
* No commit to main, no push, no touching of the corpus dir, the checkpoint, or
  the running batch.

### For the human (decisions, with exact commands)

1. **Re-extract the 11 silent-empty docs** (they are recorded ok, so `--resume`
   will never revisit them):

       python scripts/extract/run_batch.py --all --workers 2 --timeout 900 \
           --resume --retry-failed --out data/extracted/corpus \
           --checkpoint data/extracted/corpus_checkpoint.jsonl \
           --state data/extracted/corpus_state.json

   `--retry-failed` releases all 74 non-ok rows, not only the timeouts, and
   appends a second checkpoint row per retried path (a duplicate-row comment
   from the verifier would be expected). If the silent-empty cause recurs it
   will now be visible: the verifier names each document.
2. **The 3 timeout documents** (`Maritime economics 3rd edition.pdf`,
   `The Business of Shipping ...`, `The Sea and Civilization ...`) need a ceiling
   above 900 s, which the runbook does not currently say. They are textbooks, not
   time-series, so accepting the loss is a defensible alternative.
3. **Decide on the mojibake**: either accept it as a documented gap (values come
   from tables, labels are unreadable) or commission a font-level decoder plus a
   controlled re-extraction of the 1,026 hellenic docs. Do not re-extract the
   whole corpus for this.
4. **Disk**: free space fell 36.9 GB -> 29 GB between 22:36 and 23:35 while the
   extractor holds only 1.06 GB of output, so roughly 8 GB/h is coming from
   something else on this box. The verifier alarms at 5 GB free; at this rate
   that is about 3 h away, and the batch has roughly 11 h of ETA left.

### Update 23:58 IST (18:28 UTC) - fix is live, silent-empty class stable

The running batch picked the changes up without a restart (every new document is
a fresh `batch_worker` subprocess): 56 checkpoint rows written since the patch
already carry `garbled_blocks`. All 56 read 0, which fits the era pin - the run
is currently in the May 2023 MMi files, while the mojibake measured above is in
the earlier (2021-2023) era. `empty_after_ok_status` has held at exactly 11 for
35 minutes (it went 6 -> 9 -> 11 between 22:45 and 23:00 and has not moved
since), so the damage may have been a transient window rather than a continuing
leak; it is now detectable either way. Batch healthy: pid 7376 with 2 workers,
state 4.0 min old, 1,709 checkpoint rows, 6.4 s/doc, ETA ~11 h.

---

## 2026-09-22 00:05 IST (18:35 UTC) - orchestrator follow-up

### Finding 4 RESOLVED: all 11 silent-empty docs re-extracted

Ran each of the 11 through `batch_worker.py` directly into
`data/extracted/corpus` - deliberately NOT via `--retry-failed`, and NOT touching
`corpus_checkpoint.jsonl`, because the live batch holds that file open for
append and replacing it would silently lose completed rows.

Result: 11/11 restored, all four artefacts present (`text.jsonl`,
`tables.jsonl`, `pages.jsonl`, `charts/meta.jsonl`), and the recovered
`blocks`/`tables` counts **match the checkpoint row exactly** for every one of
them (706/36, 706/38, 704/36, 706/36, 695/36, 696/39, 694/38, 696/38, 694/36,
674/35, 676/36). That match is the useful part: extraction is reproducible, so
this was lost output rather than bad output.

### Cause: still not proven, but the exposure is now closed

`data/extracted/` was **untracked and NOT gitignored** at the time of the loss,
which makes generated output vulnerable to any `git clean`/`reset` side effect
from the other agent session working this same checkout. That is a plausible
mechanism, not a proven one - the loss window (22:46-23:00) predates the
recorded git operations (23:04-23:10), so it is recorded as a hypothesis.

Closed regardless: `.gitignore` now ignores all of `data/extracted/`, so
generated output can never again be deleted by git housekeeping. The verifier's
`check_outputs` is now uncapped and classifies against the checkpoint, so a
recurrence is named immediately rather than sitting outside a 600-dir window.

### Protection for the three fixes

The checkout was left on `auto/extract-fixes-2026-09-21`, and another agent
session is running `git reset --hard`/`stash` on this same working tree - a
reset while checked out would move that branch pointer and orphan the fixes.
Mitigation, since `git push` keeps failing (HTTP 408, then pack-objects killed:
the repo is large and the link is slow):

* tag `extract-fixes-2026-09-21` at `388b06c5a` - tags are not moved by a branch
  reset, so the three commits stay reachable
* push retried in the background; if it still fails the work is safe locally on
  the tag and the branch, and the files are live in the working tree

### Still for the human

1. Mojibake repair for the 1,026 extracted hellenic docs - unchanged, needs a
   decision (see Finding 1).
2. The 3 timeout textbooks - unchanged, accept or raise the ceiling.
3. Disk: measured stable at 29 GB free across three checks, no process writing
   >2 MB/s, and the remaining ~6,000 docs need roughly 5 GB. The 8 GB/h the
   earlier entry reported has not reproduced; still worth watching.

