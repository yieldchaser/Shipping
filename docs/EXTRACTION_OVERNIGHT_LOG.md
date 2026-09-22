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



---

## 2026-09-22 02:52 IST (21:22 UTC) - deep review: trailing-dot stems were losing whole documents

### What I measured (not estimated)

`verify_extraction.py --json`: done 3,670 / 7,816 (ok 3,595, error 72, timeout 3),
6.0 s/doc, ETA 414 min, mean `text_verified` 0.995, median 14 blocks / 1 table /
6 images per recent doc, `empty_unexpected` 0, 25.2 GB free. Liveness: ONE
`run_batch` (pid 7376, started 20:32 local) plus 2 `batch_worker` children
(spawned 02:31) - normal shape. The checkpoint advanced 3,670 -> 3,721 lines
during this review, so progress is real, not a `ps` artefact.

Full-corpus table-shape scan, 67,149 tables across the 7 recurring sources:
19.2% (12,921) are single-column (no grid at all), 8.8% (5,907) contain no digit
in any cell, and 62.8% of all cells are empty. hellenic alone holds 53,248 of
the 67,149 tables (79%), i.e. ~26 tables per document.

### Finding 5 (FIXED): a document stem ending in 2+ dots or a trailing space fails outright

Reproduced on the file named in the checkpoint, then in isolation:

    stem='One-Dot.'         makedirs=OK
    stem='Four-Dots-....'   makedirs=FAIL FileNotFoundError: [WinError 3]
    stem='Two-Dots..'       makedirs=FAIL FileNotFoundError: [WinError 3]
    stem='Space-End '       makedirs=FAIL FileNotFoundError: [WinError 3]
    on disk after the failures: ['Four-Dots-', 'One-Dot', 'Space-End', 'Two-Dots']

So `os.makedirs(<stem>/charts)` creates the dot-stripped PARENT and then refuses
to create the child, because the intermediate component (`...Feeling-....`) does
not exist under its literal name. One trailing dot is fine; a run of two or more,
or a trailing space, is fatal. The whole document then lands in the checkpoint as
an error with no artefacts.

Blast radius, measured over the 9,912-row inventory: exactly 3 files end that way.

| file | outcome |
|---|---|
| `reports/poten/pdfs/2016/Weekly-Opinion-19-August-2016-That-Sinking-Feeling-....pdf` | lost: `status error`, 0.6 s, "FileNotFoundError ...\charts", no artefacts |
| `reports/shipbrokers/other/2021/other_2021_09-July-2021..pdf` | not yet reached by the batch; would have failed the same way |
| `reports/hellenic/iron_ore/pdfs/2025-12-24_20251224180037..pdf` | extracted fine (single dot), but its checkpoint `doc` key keeps the dot while the directory on disk does not - a 1-document key mismatch between checkpoint and the dir-derived `doc` in the DB |

Fix (minimal, `scripts/extract/extract_all.py`): new `safe_stem()` strips trailing
dots/spaces and replaces the characters Windows forbids, and is applied to the
directory name and to `dkey` together, so `doc` now always equals the directory
that actually exists. The raw stem is untouched in the checkpoint's `path` field,
so provenance is unchanged and `--resume` (which keys on `path`) is unaffected.

Evidence after the fix, same files, scratch out-dir then the real one:

    poten/Weekly-Opinion-19-August-2016-That-Sinking-Feeling-   {"pages":1,"blocks":21,"tables":1,"images":4}
    shipbrokers/other_2021_09-July-2021                         {"pages":3,"blocks":117,"tables":22,"images":3}

The lost document was then re-extracted directly into `data/extracted/corpus/`
(single `batch_worker` call, checkpoint NOT touched, per the standing rule) and
now holds text.jsonl (7,040 B), tables.jsonl (5,321 B), pages.jsonl and charts/.
The live batch picks the fix up on its own: every document is a fresh
`batch_worker` subprocess.

Golden gate: `scripts/analysis/golden_matrix.py` regenerated
`scripts/analysis/golden_matrix.json` **byte-identical to HEAD** (`git diff` on it
is empty), so recall is unchanged - as expected, since the patch only touches
directory naming. Star Asia: cells missed by EVERY engine = none, i.e. the
camelot+pdfplumber union holds 15/15; camelot-stream alone 13/15 (misses `bdi`,
`3,186`), pdfplumber alone 13/15 (misses `glory bridge`, `7.5`), text extractors
15/15.

### Finding 6 (NOT fixed - reported): 19% of "tables" are prose banners, not grids

12,921 of 67,149 tables carry a single column of prose or a title banner, e.g.
hellenic `2026-09-12_best-oasis-weekly-recycling-market-report...` gives a table
whose rows are `WEEKLY SHIP RECYCLING` / `REPORT` / `( 05 SEPTEMBER - 11 SEPTEMBER) 2026`,
and another whose rows are `INDIA` then `The Indian recycling market remains quite
buoyant. After a strong run, prices have...`. Another 5,907 tables contain no
digit at all. The numeric tables themselves are good - the same MMi page yields
`['IOPI58','58% Fe Fines','708','-2','-0.3%','676','732','567','907','94.81',...]`,
aligned correctly - so this is catalogue hygiene, not data corruption. I did NOT
add a filter: dropping tables changes what the already-extracted corpus means, and
that is the human's call. Downstream can filter today from
`cells.is_numeric`/`catalogue.n_cols`; the catalogue already carries
`n_rows`/`n_cols`/`text_verified`, so no schema change is required.

### Finding 7 (NOT fixed - no code change warranted): poten masthead is ASCII-substituted glyphs

123 of the 1,084 extracted poten documents contain the identical block
`'WAFWOFleet esv 
 
Bi or No De?'` (15/47 of 2015, 50/50 of 2016, 40/48 of 2017,
then 1-3 per year as the Midterms editions reuse the old cover). It is a broken
font mapping that stays inside ASCII, so `is_garbled_text()` cannot see it by
construction - it counts control codes and U+0100-U+036F, and this block is plain
letters - and every one of those pages reports `garbled_blocks: 0`. No digits are
involved, and the affected documents are already extracted, so a detector change
would fix nothing retroactively. Recorded so the knowledge-base phase can exclude
the string rather than ingest it as prose.

### Deliberately NOT changed

* No extractor table filtering (Finding 6) - changes the meaning of data already extracted.
* No `build_table_db.py` schema change - the prose-blob filter is derivable from `cells.is_numeric`.
* No detector change for Finding 7 - already-extracted class, no future benefit.
* No re-extraction beyond the single lost document; nothing moved or deleted under `data/extracted/corpus/`.
* `corpus_checkpoint.jsonl` was read only, never written.

### Still for the human (unchanged from the previous entry)

1. Mojibake decision for the 1,026 hellenic docs.
2. The 3 timeout textbooks - accept, or raise `--timeout` above 900 s.
3. Disk: 25.2 GB free, ETA ~7 h, output growth ~5 GB for the remaining docs.


### Update 03:10 IST (21:40 UTC) - INCIDENT (self-inflicted, recovered): 204 documents lost to a broken patch window

While patching `extract_all.py` for Finding 5 I wrote the file twice: the first
write carried a stray NUL byte (0x00) inside a regex character class, because a
backslash escape in my shell heredoc was decoded into a real control character
before Python ever saw it. `extract_all.py` was unimportable from that moment
until I repaired it, roughly 8-10 minutes later.

What that cost, measured: every `batch_worker` subprocess in that window died at
`import extract_all`, so `run_batch` recorded **204 documents as status CRASH**
(checkpoint rows 3728-3931, contiguous, all
`reports/shipbrokers/advanced_shipping/*`, 2022 W12 -> 2026 W27):

    SyntaxError: source code string cannot contain null bytes
      File ".../batch_worker.py", line 21, in main
        import extract_all as E

None of them left a directory: `dir absent: 204 | partial: 0 | complete: 0`.
`--resume` treats any recorded status as done, so they would have been skipped
permanently - the same trap as the earlier "missing dependency reads like a
finished run" case.

Recovery tool: `scripts/extract/recover_crashed.py` (sequential, one
`batch_worker` subprocess per document, 900 s ceiling, append-only progress in
`data/extracted/crash_recovery.jsonl`, checkpoint never written):

    python scripts/extract/recover_crashed.py

Measured while it ran: 16 documents recovered in the first ~6 minutes, every one
status `ok`, 19-36 s per document (the advanced_shipping weeklies are 9-10 pages
with ~50 tables each, so they are ~4x the corpus average of 5.9 s). Projected
finish ~04:05 IST (22:35 UTC) for all 204. Artefacts verified on two of them:

    advanced_shipping_2022_W12... : tables 47 | text blocks 397 | pages 9 | charts 11
    advanced_shipping_2022_W26... : tables 56 | text blocks 419 | pages 10 | charts 12
    sample row: ['T','BHSI','1.276','1.334','-4,35%']

### Also seen: a duplicate recovery sweep

Two copies of the recovery tool were launched within 5 seconds of each other
(pid 17156 at 02:51:44 and pid 11548 at 02:51:49 - the second was mine, launched
before I noticed the first). Evidence of the duplication was visible in the
progress file as the same path logged twice with different durations
(`...W12... ok 25.2s` and `...W12... ok 26.6s`). I stopped the newer copy
(pid 11548) and left one sweep running; three documents were extracted twice.
Nothing was corrupted - extraction is deterministic and idempotent - but on a
box already running the main batch this doubles CPU contention, and it is the
same class of mistake as the two-concurrent-batches incident in the runbook.

Two things follow for the human:

1. The hourly verifier will now report `CRASH: 204` as a NEW failure kind. That
   is this incident, already recovered in the tree; the checkpoint rows keep the
   stale status because that file must not be rewritten. If you prefer a clean
   checkpoint, `run_batch.py --all --retry-failed --resume` re-attempts anything
   whose status is not ok and appends fresh rows (idempotent: the recovery above
   already wrote the artefacts, and re-extraction overwrites them identically).
2. Lesson for whoever patches next: in this environment a `\x` or `\n` escape
   written inside a shell heredoc reaches the file as a raw control character.
   Build such strings with `chr(10)` / `ord()` checks instead, and run
   `python -m py_compile` on the target file IMMEDIATELY after writing it. The
   live batch turns any syntax error into a burst of CRASH rows within seconds.

### Closing state 03:20 IST (21:50 UTC)

`verify_extraction.py --json`: done 4,260 / 7,816 (ok 3,981, error 72, timeout 3,
CRASH 204), 5.8 s/doc, ETA 346 min, `empty_after_ok_status` 0,
`empty_not_in_checkpoint` 0, mean `text_verified` 0.982, 24.6 GB free. Processes:
one `run_batch` (pid 7376) with 2 workers, plus one recovery sweep (pid 17156).
The recovery had reached 24 of 204 documents, every one `ok`, and all 22 unique
documents logged so far carry full text/tables/pages/charts - ETA for the rest
~04:05 IST. It is safe to leave running: it is sequential, it appends progress,
and a restart skips what it already did.

One reading worth not panicking about later: an empty-output scan taken while the
recovery was mid-document listed
`shipbrokers/advanced_shipping_2022_W33_...` as an empty dir (charts only) because
the worker had harvested images but had not yet written text/tables/pages. It is
complete now. `verify_extraction.py` classifies such dirs as in-flight, so a
transient count of 4 `empty_after_failure` (3 timeout textbooks + 1 mid-write) is
a snapshot, not a defect. No silent-empty recurred: `empty_after_ok_status` is 0.


## 2026-09-22 06:55 IST (01:25 UTC) - deep review: hourly restarts were dying with the agent session; one measured recall finding

Verdict: **FIXED** (launch durability) with one NEW measured item flagged for human decision.

### What I measured

`verify_extraction.py --json` at 06:05 IST: 5,033 checkpoint rows, 5,033 unique (0
duplicates), ok 4,752, `empty_after_ok_status` 0, `empty_unexpected` 0, mean
`text_verified` 0.991, failures 74 (71 not-a-pdf bad header, 3 timeout = 1.5%),
disk 55.5 GB free, `actions[]` EMPTY. **The batch was dead on arrival**: last
checkpoint write 05:48:59.579, zero `run_batch`/`batch_worker` processes at 06:02.

### Finding 1 (FIXED): the hourly restart dies within ~20 s of the restarting run

Evidence, all from this box:

* the hourly run restarted the batch at 05:37:03 IST; its last checkpoint row was
  written 05:48:59.579; that run was recorded finished 05:49:00.462. The next row
  would have landed ~05:49:10, so death is bracketed to [05:48:59.6, ~05:49:20] -
  within ~20 s of the driving process exiting.
* it was **terminated, not crashed**: the Windows Application log has no
  `python.exe` event 1000 in that window, while other applications here do produce
  1000s (PhoneExperienceHost 05:40:44, Hermes.exe 21-09 12:04). A hard fault leaves
  a record; an external TerminateProcess leaves none.
* mechanism: Hermes attaches its own process to a Windows job object with
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`
  (hermes-agent/hermes_cli/process_identity.py layer 3, ~line 425). A child that
  does not request `CREATE_BREAKAWAY_FROM_JOB` stays in that job and dies when the
  agent process exits. hermes_cli/gateway_windows.py:44 documents the same hazard.
* honest limit: PID 7376 (the 20:32 - 04:51 batch) survived many hourly runs, so
  this is evidently not universal for background-session children. The correlation
  above is 1:1 but n=1. The previous death (04:51) had a different, unrelated
  cause: critical-battery shutdown (Kernel-Power 524 at 04:51:03, 109 at 04:51:14),
  machine back up 05:32:48.

Fix: `scripts/extract/launch_detached.py` spawns the prescribed `run_batch`
command with `CREATE_BREAKAWAY_FROM_JOB | DETACHED_PROCESS |
CREATE_NEW_PROCESS_GROUP` and sends stdout+stderr to
`data/extracted/batch_run.log`. The 05:48 death left **no driver output at all**,
which is why it needed a forensic pass; that log is the missing evidence channel.

Verified: launched 06:17:17, `mode=breakaway+detached pid=17700,
alive_after_3s=True` (breakaway accepted, no access-denied fallback), 2
`batch_worker` children observed, checkpoint 5,033 -> 5,116 by 06:55 with log rows
`[1/2783]` .. `[60/2783]` all status ok.

### Finding 2 (NEW, previously unsurfaced): whole sale sections sit in the text and in no grid

Reproduced by hand on `carriers_2026_W26_WK-26-26-CARRIERS_SP-MARKET-REPORT`
(3 pages, 38 tables, every table `text_verified` 1.0). Page 0 of the source PDF
holds two sale tables. The grids captured "Bulk Carriers Reported Sold" (9 rows:
CORNELIE OLDENDORFF 93,246 ... DARYA KRISHNA 34,874) and dropped **every row** of
"Tankers / LPG Vessels Reported Sold" -

    ECLAT          TANKER  299,031  2004  Universal Shbldg - Ariake   50.00  UNDISCLOSED
    HANSA OSLO     TANKER   51,215  2007  STX Shipbuilding - Jinhae    20.00  UNDISCLOSED
    XING TONG 799  TANKER   49,962  2011  Onomichi Dockyard Co Ltd     27.50  UNDISCLOSED

plus the single Container row (NJORD CV 9,543 2007 Sainty Shipbuilding 7.50). No
cell in any of the 38 tables contains ECLAT, while the value is in the page text
of the pipeline text.jsonl and of PyMuPDF. Re-running
`camelot.read_pdf(page=1, flavor=stream)` directly on the source PDF also returns
no cell containing ECLAT: an **engine coverage limit, not a routing bug and not a
corrupt file**.

Scale, measured with the new tool over the committed corpus:

| source | docs | record-grade orphan values | docs affected |
|---|---|---|---|
| carriers | 125 | 513 | 97 (78%) |
| allied | 204 | 111 | 57 (28%) |
| banchero_costa | 237 | 14 | 6 (3%) |
| advanced_shipping | 44 | 6 | 2 (5%) |
| agora | 211 | 0 | 0 |

Definition: values matching `^[0-9]{1,3},[0-9]{3}$` (tonnage-shaped) present in the
page text and in no table cell of that page, sitting in a text block with no prose
function-words (a record row, not a sentence). Worst carriers docs:
`carriers_2026_W06` 18 (e.g. "DHT BAUHINIA TANKER 301,019 2007 Daewoo Shipbuilding
& Marine 51.50 CHINESE"), `carriers_2025_W29` 13 (e.g. "ATLANTIC LOYALTY TANKER
307,284 2007 Dalian Shipbuilding Ind - No 2 44.00 UNDISCLOSED"), `carriers_2025_W38`
13. The 308 raw DWT-shaped orphans in advanced_shipping are 302 chart axis labels
("0 500 1,000 ... Tankers") and prose, so that row is an upper bound, not loss.

Why every existing gate missed it: the reconciliation runs **cells -> text** only.
A document whose grid is complete but which is *missing entire rows* reports
`text_verified` 1.0, and this carriers document does, on both engines.
`pages.jsonl` records `values_only_in_text` and nothing aggregates it.

Tooling added: `scripts/extract/recall_gap_report.py` (read-only) reproduces the
table above per source.

NOT changed: nothing was re-extracted and the corpus was not written to.
Reconstructing sale rows from the text layer for the ~5,000 already-extracted docs
changes how existing data should be interpreted, so it is a human decision.

### Deliberately not changed

* `run_batch.py`, `extract_all.py`, `batch_worker.py`, `verify_extraction.py`, the
  hourly job prompt, the checkpoint, the corpus dir, `index.html`, `data/etf/**`,
  other pipelines, git history. No push, no commit to main.
* The 441-page `fearnleys_2022_W50` document (230 s against an 11 s median, a 21x
  outlier) - a throughput outlier, not a defect, and not a reason to raise the
  900 s per-document ceiling.
* Worker count left at 2 as prescribed. Standing risk, not acted on: available RAM
  is 354-453 MB with **no** extraction running (committed 11.5 GB on a 7.9 GB
  physical box), the environment in which the earlier 0xC0000409 fail-fast burst
  occurred.
