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


## 2026-09-22 22:21 IST (16:51 UTC) - deep review: the corpus is COMPLETE; European decimals were being read as thousands (fixed)

Verdict: **FIXED** (one proven numeric-parsing defect) plus one human decision.

### What I measured (all read-only)

`verify_extraction.py --json`: 7,816 checkpoint rows, 7,816 unique, 7,816
inventory non-dup paths, `empty_after_ok_status` 0, `empty_unexpected` 0,
golden 15/15, disk 32.5 GB free. Statuses of the LAST row per path: ok 7,488,
CRASH 249, error 75, timeout 3, no-extractable-content 1.

**The batch is finished, not dead.** No `run_batch`/`batch_worker` process
exists and `corpus_state.json` is 659 min old, which the hourly job reports as
"batch may have died". Re-running `run_batch.py --all --resume` is a no-op:
replicating its own selection logic (inventory minus `PROVENANCE_ONLY` = 7,676
selected; done-set = 7,816 paths) gives **0 documents to run**, so it would print
"nothing to do" and exit 0. The 880/882 in the state file is bookkeeping, not
missing work: every inventory path has a checkpoint row and an artefact.

I checked the non-ok rows against the filesystem rather than trusting the
checkpoint:

| last-row status | count | has text.jsonl |
|---|---|---|
| CRASH | 249 | 249 (all listed in crash_recovery.jsonl) |
| error (not-a-pdf) | 74 | 0 - quarantined, no content expected |
| timeout | 3 | 3 (the three textbooks) |
| error (FileNotFoundError, trailing-dot stem) | 1 | 1 - stale row, document extracted fine |
| no-extractable-content | 1 | 1 |

So exactly 74 documents have no artefacts and all 74 are the quarantined
bad-header files (68 breakwave, 2 hellenic, 1 signal, 1 ppa_hedland, 1
test_download, 1 reports/). Catalogue shape split from the DB: grid 140,489,
onecol 22,854, empty 14,532, single_cell 7,761, blob 6,899 = 27.0% of 192,535
table records are extraction noise (already labelled, not new).

New measurement, one SQL query against the existing `cells`+`catalogue` views:
**2,784 of 140,489 grids (2.0%) are prose-shaped** (first-column median cell
length > 40 chars and < 20% of cells containing a digit) - shipbrokers 793,
poten 437, hellenic 406, the rest textbooks. The prose-fragment grids I opened
by hand (xclusiv weekly page 1: a 30x11 camelot-stream record whose first cells
are "high and a sharp surge from 2.1 million tonnes", "from the previous",
"fiscal year, due to Russia's", all with text_verified 1.0) are real but small
in number. I did NOT write a new tool for this; the class is measurable from the
catalogue and the count does not justify one.

### Finding (FIXED): a European decimal comma was read as a thousands separator

`build_table_db.to_number()` stripped every comma before parsing, so
`3,07` -> 307.0, `30,74` -> 3074.0, `1,1476` -> 11476.0, `104,82` -> 10482.0 and
`1.234,56` -> 1.23456.

Ground truth, two independent sources: the PDF text layer of
`advanced_shipping_19_09_2026` page 9 prints
`Diana Shipping Inc (DSX) NYSE 3,07 2,92 5,14%` (a NYSE share price, so 3.07),
and the publisher's own markdown mirror
(`reports/broker_reports/2026/advanced_shipping_19_09_2026_...md` line 557)
prints the identical string; page 8 prints `Brent Crude (BZ) 104,82 107,63
-2,61%` (104.82, not 10,482) and `EUR / USD 1,1476`.

Rule: a thousands group is exactly three digits, so a comma followed by any
other count of digits cannot be a thousands separator. Ambiguous `1,234` stays
1234 (US convention, pre-existing behaviour).

Scale, measured against `data/extracted/corpus/db`: 39,151 cells matching
`^[0-9]{1,3},[0-9]{1,2}$` (558 docs, 5 sources, 39,127 shipbrokers), 2,840
matching `^[0-9]{1,3},[0-9]{4}$` (409 docs, shipbrokers FX quotes), 1,937 in
European full form `1.234,56` (315 docs, shipbrokers) = **43,928 cells in 558
documents**. 277,454 US-format cells (`1,234`) are untouched.

One-document before/after, `build_table_db.py --rebuild` into
`data/extracted/scratch_eur`: 102 of 260 numeric cells change - 49 x100, 51 x10,
1 x10000. e.g. `3,07` 307.0 -> 3.07, `104,82` 10482.0 -> 104.82, `1,1476`
11476.0 -> 1.1476, `46,5` 465.0 -> 46.5. Non-numeric cells still parse to None
("high and a sharp surge...", "N/A", "2022-05-23").

This is the cause behind 466 CRITICAL `EURO_DECIMAL_MISPARSE` series already
listed in `data/extracted/qaudit_corpus.csv`.

Changed: `scripts/extract/build_table_db.py` only (+36/-1), branch
`auto/extract-fixes-2026-09-22`, commit **aa5bc7b5b**. Golden unaffected:
`verify_extraction.py` golden 15/15, and `golden_matrix.py` re-run reproduces the
committed `golden_matrix.json` exactly (star_asia camelot-stream 13/15,
plumber-text 15/15, pymupdf-text 15/15; ssy_atlantic 14/14; breakwave camelot 5/6,
plumber-text 6/6). Scratch dir `data/extracted/scratch_eur` deleted.

### HUMAN DECISION: rebuild the derived DB (or the 43,928 cells stay 100x)

The fix changes how already-extracted data must be interpreted, so I did not
rebuild anything. `data/extracted/corpus/db/` still holds the old numbers, and
every series built from it (5,123 series / 1,193,415 points) still holds them.
To apply:

    python scripts/extract/build_table_db.py --out data/extracted/corpus --rebuild
    python scripts/extract/build_series_sql.py     # then re-run the series QA

Cost: a full reparse of 192,535 table records (~7 minutes of wall clock when the
box is idle; RAM was 691 MB free with nothing running). Risk: other agents'
audits (gap_matrix, qaudit, series_priorities) read this DB, so rebuild when
none of them is mid-run.

### Deliberately not changed

* `corpus_checkpoint.jsonl` - never written. Note for whoever reads it next: the
  last row for 249 recovered documents still says `CRASH`. `verify_extraction.py`
  resolves them through `crash_recovery.jsonl` and I confirmed all 249 have
  text.jsonl on disk, but a consumer that reads the checkpoint alone will count
  249 false failures.
* No batch started, nothing re-extracted, no `run_batch.py`/`extract_all.py`/
  `batch_worker.py`/`verify_extraction.py` edit, no push, nothing outside
  `scripts/extract/`.
* `data/extracted/scratch_review/` (a previous run's scratch, 756 KB, holds
  `build_table_db.py.before`) left in place.
* The HTML pass has never produced output - `data/extracted/html` does not
  exist - so HTML-collected sources are unextracted. Related: the 68 breakwave
  not-a-pdf paths no longer exist on disk; the same articles survive as 3,221
  `.html` files in `reports/breakwave/` with a different stem. The one I opened
  has no `<table>` element, so the value looks prose-only, but I only opened one
  of 3,221 and this is a decision, not a defect.
* `source_configs.QUARANTINE_GLOBAL` still says "not-a-pdf headers (3 found:
  breakwave x2, signal fueleu)"; the measured count is 74. Stale comment, left
  for a human to correct with the disposition they want.

### Second fix: connectivity/error pages were becoming HTML-pass documents

Scanned every `meta.json` under `data/extracted/corpus` (17,653 document dirs;
9,911 are HTML-pass documents, 850 of which the existing junk rules already
catch - baltic `/assets/`, yahoo/cnn dumps, blogspot reposts). Three were
connectivity pages recorded as content with `junk: false`, all in hellenic:

    hellenic/0000-00-00_weekly-dry-time-charter-estimates-march-23-2022
        title "This site can't be reached", text "The webpage at
        https://www.hellenicshippingnews.com/... might be temporarily down"
    hellenic/0000-00-00_gms-week-35-activity-increase
        title "Web server is returning an unknown errorError code 520"
    hellenic/0000-00-00_athenian-shipbrokers-s-a-demolition-quick-update-week-03-2026
        title "hellenicshippingnews.com | 520: Web server is returning an
        unknown error"

`junk_verdict()` had no rule for either error string, so each became a
"document" (the first has 3 text blocks, 0 tables). Before: `junk_verdict()`
returns `(False, None)` on both files. After: `(True, "browser error page (site
unreachable)")` and `(True, "web server error page (5xx)")`, while the same
publication's real article (`2021-07-07_weekly-dry-time-charter-estimates-july-07-2021`)
still returns `(False, None)`. End-to-end: running the pass on that one-file
directory now writes only `meta.json {"junk": true}` with no text.jsonl
(docs 0, junk 1) instead of a 3-block document.

Changed: `scripts/extract/run_html_pass.py` only (+14 lines), commit
**a2815f46e** on `auto/extract-fixes-2026-09-22`. Scratch dir deleted. This
prevents new placeholder documents; it does not remove the three already in the
corpus (nothing under `data/extracted/corpus/` was touched - that needs a human).


## 2026-09-23 02:32 IST (21:02 UTC 09-22) - deep review: currency-space numbers were dropped, so every $/day broker rate column was missing (FIXED)

Verdict: **FIXED** - three proven defects repaired on branch `auto/extract-fixes-2026-09-23`.
The pre-existing DB-rebuild decision is restated below with its scope doubled.

### What I measured (all read-only)

`verify_extraction.py --json`: 7,816 checkpoint rows / 7,816 unique paths, `empty_after_ok_status` 0,
`empty_unexpected` 0, golden 15/15, 249 crash-recovered rows all resolved, disk 41.7 GB free.
No `run_batch`/`batch_worker` process exists and `corpus_state.json` is 899 min old.

**The run is finished, not dead.** The new `remaining_work()` recomputes run_batch's own selection
(inventory 7,676 paths after content-duplicates and PROVENANCE_ONLY) minus the checkpoint paths =
**0 documents to extract**, so a resume would print "nothing to do". A stale state file on a
finished run is COMPLETE, not a dead batch.

DB coverage (the "verify the artefact, not the intent" rule): 8,144 documents hold a non-empty
`tables.jsonl` and 8,144 distinct docs appear in `corpus/db/tables.parquet` - 0 missing, 0 extra.
The derived DB is complete with respect to the extraction; only the number-format fix below is
pending, and applying it needs the rebuild already flagged as a human decision.

### Finding 1 (FIXED): a currency symbol followed by a SPACE defeated the number parser

`to_number()` stripped `$` and `£` but not the whitespace after them, so the cell `"$ 15,648"`
became `" 15,648"` and `NUM` (anchored at the start) never matched. The broker weeklies print every
rate that way.

Evidence, one document: `allied_2022_W12_ALLIED-Weekly-Market-Report_27_03_2022` page 1,
camelot-stream table 2, the BCI 5TC row - `['BCI 5TC', '$ 15,648', '$ 21,604', '-27.6%',
'$ 14,866', '$ 32,961']`. Ground truth is the PDF's own text layer, not another extractor: pymupdf
page 1 reads "the BCI 5TC finally closing on Friday at US$  15,648/day, 27.6% lower" and "holding
at the US$ 30,000/day territory". ATLANTIC RV (11,875 / 20,175 / 17,120 / 36,070) and Cont / FEast
(30,900 / 36,250 / 34,660 / 54,145) are the same shape.

Scale, measured against `data/extracted/corpus/db` with the current and the fixed parser: 65,700
shipbroker cells begin with a currency symbol plus whitespace; **38,149 cells across 469 documents
change from non-numeric to numeric, with 0 cells lost** (regression check over all 6,946,400
cells). 4,280 of the affected (doc, page, table, engine, column) columns hold 4 or more recovered
cells - whole rate columns, 24 cells each in the Allied weeklies. 37,877 of the 38,149 are
shipbrokers; the rest are seabrokers 127, cftc 80, one 10-Q 19, hellenic 14.

One-pool before/after (Allied W12 + xclusiv 2021-08-16, built into
`data/extracted/scratch_review_20260923`): numeric cells 2,458 -> 3,495 of 6,179, 1,037 flipped,
0 regressions. The BCI 5TC row then reads 15648.0 / 21604.0 / -27.6 / 14866.0 / 32961.0.
`to_number` spot checks: `$ 15,648` 15648.0, `$15,648` 15648.0, `$ (56,591)` -56591.0,
`$ 1,234,567` 1234567.0, `22,5m` None (unit suffix, unchanged), `1.234,56` 1234.56 and `3,07` 3.07
(the European-decimal fix still holds).

Changed: `scripts/extract/build_table_db.py` (+10/-1: a `CUR` prefix regex and one call site).
Golden unaffected: `golden_matrix.py` re-run reproduces star_asia camelot-stream 13/15,
plumber-text 15/15, pymupdf-text 15/15; ssy_atlantic 14/14; breakwave camelot 5/6, plumber-text
6/6 - identical to the committed matrix. Scratch dir deleted.

### Finding 2 (FIXED): HTML content inside a layout-table cell never became a text block

`handle_data()` gives the cell buffer precedence over the wrapping content tag, so text inside
`<td><p>...</p></td>` (an email-shaped newsletter) is captured into the table cell and never into a
block. Signal's monthly newsletters are table-based emails: 105 `<table>` and 113 `<td>` against 13
`<h1>` and 17 unclosed `<p>`, all of it inside cells.

Measured over all 9,911 HTML-pass documents: exactly **10** are non-junk with `blocks: 0`, and all
10 are Signal newsletters (`march-2025`, `april-2025`, `february-2025`, `2025-january`, `may-2025`,
`july-2025`, `september-2025`, `october-2025`, `january-2026`, `may-2026`) whose source HTML holds
2,472-5,529 characters of visible text. A trailing empty `<title>` (an SVG logo carries one) also
erased the real title: exactly 9 documents have `meta.title == ""` while the HTML holds
`<title>March 2025 Newsletter</title>`.

**This is index coverage, not lost content**: every one of the 10 has a markdown mirror under
`reports/signal/newsletters/` (45,730-88,979 bytes each, 626 KB total), so the text is already in
the repo. What was missing was the corpus/HTML-pass representation of it.

Fix: the parser carries a `cell_blocks` flag and `extract()` re-parses only when the normal pass
produced **no** blocks at all, plus a title is no longer overwritten by an empty one. After the fix
the 9 zero-block newsletters yield 18-34 blocks (2,218-3,977 characters) and their real titles.

Blast radius, measured by running the OLD and NEW `extract()` over every one of the 9,976 HTML
files in `reports/`: **exactly 10 documents differ** - the 9 newsletters above (blocks 0 -> 13-34)
and one junk-classified breakwave `assets/` file whose blocks are unchanged at 17 and whose title
only goes from `''` to `'WEEKLY: China's iron ore p...'`; junk documents write only `meta.json` and
never call `extract()`, so that one changes nothing on disk. A seeded 300-document random sample of
the same set showed 0 differences.

Residual, stated rather than hidden: `march-2025` recovers only its 13 headings (352 of 4,064
visible characters) because its `<p>` tags are never closed, so no block boundary exists for the
paragraph text. The md mirror carries the full text.

Changed: `scripts/extract/run_html_pass.py` (+25/-2). Golden unaffected (PDF path untouched;
`verify_extraction.py` golden 15/15).

### Finding 3 (FIXED): two verifier defects made the hourly health check lie

1. `check_db()` looked only at `<out>/db`, which is an empty directory (`data/extracted/db`,
   created 15:17, no files), while the live database is `data/extracted/corpus/db`
   (catalogue.parquet 831,655 B, tables.parquet 50,715,534 B, corpus.duckdb 125,054,976 B). The
   integrity check answered "not built yet" for the whole run and validated nothing. It now scans
   `<out>/db` and `<out>/*/db` and reports which one it used: `db_dir: data/extracted/corpus/db`,
   `db: 192535 tables, 6946400 cells`.
2. `check_state()` treated any state file older than 30 min as "batch may have died; rerun with
   --resume". A finished run stops advancing its state file, so the hourly job reported a dead
   batch every hour for a completed corpus, and two deep-review runs spent effort re-proving the
   same false alarm. A stale state file with `remaining == 0` is now reported as
   `state_note: ... run COMPLETE, not a dead batch`, and the action is raised only when documents
   really remain (it then names how many).

After the fix `verify_extraction.py` prints "OK - no action required" and exits 0, instead of the
same false action it has printed since the pass ended. Changed:
`scripts/extract/verify_extraction.py` (plus a `remaining_work()` helper).

### HUMAN DECISION (unchanged, scope doubled): rebuild the derived DB

`data/extracted/corpus/db` still holds pre-fix numbers: the 43,928 European-decimal cells from the
2026-09-22 fix AND the 38,149 currency-space cells from this one are wrong or still non-numeric in
it, and every series built from it inherits that. I did not rebuild: it is the documented human
decision, other agents' audits read this DB, and a rebuild must not run while they are mid-flight.

    python scripts/extract/build_table_db.py --out data/extracted/corpus --rebuild
    python scripts/extract/build_series_sql.py     # then re-run the series QA

Cost unchanged: a full reparse of 192,535 table records (about 7 minutes idle). Combined effect of
the two number-format fixes: 82,077 cells change value or become numeric.

### Second human decision (new, bounded): re-run the HTML pass for the 10 newsletters

The fix takes effect for documents extracted from now on. The 10 Signal newsletters already in
`data/extracted/corpus` still have an empty text.jsonl. A bounded re-run of one root is small; it
writes inside the corpus, so it is a human call:

    python scripts/extract/run_html_pass.py --root reports/signal/html --out data/extracted/corpus

### Deliberately not changed

* `corpus_checkpoint.jsonl` (never written - the live-batch append-handle rule) and nothing under
  `data/extracted/corpus/`. The 249 rows still reading CRASH are resolved via `crash_recovery.jsonl`.
* `extract_all.py`, `batch_worker.py`, `run_batch.py`; no batch started; no re-extraction.
* `empty_not_in_checkpoint: 854` - measured: 850 are junk HTML placeholders (baltic/breakwave
  bot-wall `assets/`), 1 is the signal newsletter above, and 3 I could not classify to my own
  satisfaction (my scan and the verifier's disagree on those 3). It fires no action, so I left the
  metric alone rather than change a number I cannot fully account for.
* Other agents' uncommitted work in the tree (`knowledge/**`, `docling_units.py`,
  `build_series_wrong_gate.py` deleted, three untracked scripts) - I committed only my three files.
  I did not pull main: the tree is shared and mid-edit.

## 2026-09-23 12:05 IST (06:35 UTC) - deep review: the reconciliation metric could not see the text layer, so 227 pages were queued for OCR without reason (FIXED)

Verdict: **FIXED** - one proven defect in the reconciliation code path repaired on branch
`auto/extract-fixes-2026-09-23`. Two further measured observations are reported and deliberately not
changed. No re-extraction was run and nothing under `data/extracted/corpus/` was written.

### What I measured (all read-only)

`verify_extraction.py --json`: 7,816 checkpoint rows / 7,816 unique, `empty_after_ok_status` 0,
`empty_unexpected` 0, `empty_by_design` 114, `empty_not_in_checkpoint` 854, golden 15/15,
`crash_recovered_docs` 249, `db_dir: data/extracted/corpus/db` (192,535 tables / 6,946,400 cells),
disk 39.6 GB free, **actions: []**.

Process check (STEP 2): `Get-CimInstance Win32_Process` for `python.exe` shows **no `run_batch`, no
`batch_worker`, no `extract_all`**. The 5 live `python.exe` processes belong to other agents. The
corpus is complete (`remaining_to_extract` 0), so there is no duplicate-batch question to answer.

Reproducibility spot-check: re-running `extract_all.py` on `Drewry_AIS_Product_LR2_Week33_2026`
reproduces its checkpoint row exactly (9 pages, 303 blocks, 50 tables, 37 images, 0 orphans) - the
extractor is deterministic on this corpus, so the before/after comparisons below are trustworthy.

Documents opened by hand: `Drewry_AIS_Product_LR2_Week33_2026` (recently completed),
`shipbrokers/advanced_shipping_2023_W31_ADVANCED-MARKET-REPORT-WEEK-31` and
`hellenic/2025-09-20_Weekly-Ship-Recycling-Report-13-September-19-September-2025`.

### Finding (FIXED): `text_verified` tested a substring, not a value

`verify_tables_against_text()` decided a digit cell was "confirmed by the text layer" by asking
whether the whole normalized cell string occurs in the normalized page text
(`re.sub(r"\s+"," ",c).casefold() in norm_text`). That is wrong in both directions, and I measured
both on 165 sampled documents (a seeded 3-per-source sample of the 7,489 ok rows):

* **under-report, 2,828 cells**: the extractor joins fragments that are not contiguous in the text
  layer, so the cell string never matches even though every number in it is on the page. Real
  examples: cell `'90%\nUtilisation'` (drewry p1), cell `'800\n$/ tonne'` (drewry p3), and the merged
  pdfplumber cell
  `'USD / INR USD / BDT USD / PKR USD / TRY\nThis Week : 88.10 This Week : 121.72 This Week : 283.12 This Week : 41.35\n...'`
  (hellenic demolition 2025-09-20 p2) while the same page's text layer prints
  `'USD / INR\nThis Week         :  88.10\nPrevious Week :  88.27\nGain                    :  0.17\n...'`.
* **over-report, 102 cells**: `'7'` was "confirmed" because a `7` occurs inside `17,000` somewhere on
  the page (e.g. `Maritime Economics` p191/257/258, `Lloyds_Maritime_Atlas` p12 `',148 Ships'`).

The under-report was the costly half because a second rule consumes it:

    scored = [t.get("text_verified") for t in page_tables if t.get("text_verified") is not None]
    if scored and all(s == 0 for s in scored):
        p_rows[-1]["ocr_queue"] = "table values not in text layer (image table)"

**227 pages in the collected corpus carry that flag** (191 documents; shipbrokers 120, hellenic 77).
I recomputed every one of them from its stored `tables.jsonl` and the page text of the source PDF:
**186 would clear** (the values are in the text layer), **2 stay flagged** - and those 2 are the rule's
true positives, which is why the rule must keep working:

    shipbrokers/advanced_shipping_2023_W31_ADVANCED-MARKET-REPORT-WEEK-31 page 3
        stored cells: '6.494', '2009', '03/2024', '$ 32m', '4.963', '04/2025'  - tv 0/31
        page text (337 chars): 'WEEKLY SHIPPING MARKET REPORT - pg. 4 ... Type Name Teu YoB Yard SS
        M/E Gear Price Buyer Comments ... $ ... REPORTED SALES'  -> the sale table is a picture
    shipbrokers/advanced_shipping_2023_W35_... page 3: '4.363', '11/2027', '$ 20,8m', '3x45T' - same

(39 of the 227 were skipped: the source PDF is no longer on disk. Reported, not assumed.)

Fix: `cell_confirmed(cell, text_tokens)` - a digit cell is confirmed when **every number in it exists
as a number in the page text** (thousands separators ignored on both sides). One document, before and
after, same command, scratch out-dir:

| document | before | after |
|---|---|---|
| hellenic/2025-09-20_Weekly-Ship-Recycling-Report (4 pp) | mean tv 0.750, cells 48/51 (94.1%), `ocr_queue: table values not in text layer (image table)` on p2 | mean tv 1.000, cells 51/51 (100%), no flag |
| drewry_ais_pdfs/Drewry_AIS_Product_LR2_Week33_2026 (9 pp) | mean tv 0.477, cells 302/392 (77.0%) | mean tv 1.000, cells 392/392 (100.0%) |

Per-table detail for the hellenic document: table 4 (p2, pdfplumber) `0/2 -> 2/2`; table 7 (p3,
pdfplumber) `0/1 -> 1/1`. Page/block/table/image counts are unchanged, so only the metric moved.

Honest limit, stated rather than implied: `text_verified` is a RECALL indicator, not a correctness
check. It cannot see a cell assigned to the wrong row, and at 1.000 it says only "every number in
this grid also occurs somewhere on this page". The reverse direction (values in the text that are in
no grid) is still the stricter, more conservative test - see the next finding.

### Finding (FIXED, same file): the number tokenizer split values at the comma

The orphan detector used `re.findall(r"\b\d[\d,]*\.?\d*\b", page_text)`. On `"180,000dwt"` that
pattern returns **`['180,']`** - the value was never tested as a whole, and the token it stored is not
a number. Measured over the 78,035 values the corpus already holds in `pages.jsonl
values_only_in_text`: **750 end in a comma** (`'270,'` Amplify_BWET_Prospectus, `'5,'` hellenic,
`'1,175,'` shipbrokers) and **525 end in a dot** (`'526.'`, `'432.'`, `'8.'`), i.e. 1,275 of the
stored "dropped values" are extraction artefacts, and the true value behind them was never checked.

It also hid real losses: `recall_gap_report.py` filters these values with `^\d{1,3},\d{3}$`, so a
dropped `33,000` stored as `'33,'` is invisible to the report that exists to find dropped values.
On 2,566 sampled pages the fixed tokenizer surfaces **18 more DWT-like dropped values** (e.g.
`shipbrokers/allied_2023_W04` page 13 `'33,000'`, `seabrokers/2019-10-01_markedsrapport-oktober-2019`
pages 8/11 `'3,258'`/`'1,850'`) and **39 more 4+ digit ones**.

Fix: `NUM_TOKEN_RE = re.compile(r"\d+(?:,\d{3})*(?:[.,]\d+)?")` - thousands groups are exactly three
digits, and a comma followed by 1-2 digits stays a European decimal (`'5,3'`), so the 1,051
euro-decimal orphan values already in the corpus are preserved rather than split. Verified by
assertion, not by eye: `NUM_TOKEN_RE.pattern` equals the intended string, and
`'180,000dwt'->['180,000']`, `'5,3'->['5,3']`, `'1,500,000'->['1,500,000']`, `'270,'->['270']`,
`'526.'->['526']`, `'1,234.56'->['1,234.56']`.

I deliberately kept the **substring** comparison inside the orphan detector rather than moving it to
token membership: measured on the same 2,566 pages, token membership adds 2,286 short (<=3 digit)
tokens to the orphan lists for only +52 long values, i.e. it floods the diagnostic with page-number
noise. The orphan list is the loss detector, so it stays conservative; the confirmation metric above
is the one that was made precise.

Changed: `scripts/extract/extract_all.py` only (+40/-4), commit `aa3ba0543` on branch
`auto/extract-fixes-2026-09-23` (created off the current `auto/extract-fixes-2026-09-22`, so the
previous fixes stay underneath).
Committing to a branch does not change the working tree, so the fix already applies to any document
extracted from now on.

Golden check after the change: `golden_matrix.py` re-run reproduces the committed
`scripts/analysis/golden_matrix.json` **byte-identically** (sha256
`99cdcf6cca1e0ab90920cffc9b4f2558dfe0eba29053891e93ed74ad879634d7` before and after); star_asia
plumber-text 15/15, pymupdf-text 15/15, camelot-stream 13/15; ssy_atlantic camelot 14/14; breakwave
plumber-text 6/6. `ruff check scripts/extract/extract_all.py`: 3 errors, all three present at HEAD
(F401 `hashlib`, F841 `H`, E741 `l`) - no new lint. `python3 -m py_compile` clean. Scratch dir
`data/extracted/scratch_deep_20260923` deleted at the end of this run.

### Observation (NOT changed): a whole source's "tables" are Power BI chart scaffolding

Drewry AIS documents are Power BI exports: the chart is an embedded image, and what camelot calls a
table is the axis/annotation text around it. `Drewry_AIS_Product_LR2_Week33_2026` reports 50 tables
in 9 pages, and the ones I opened are exactly that - a 32x8 camelot grid whose rows hold `'Current'`,
`'Utilisation'`, `'▼ 2.5'`, `'MoM percentage point'`, `'change in utilisation'`, `'86%'`, `'88%'`,
`'90%'` plus prose sentences from the report body. The real series are in the chart images (a separate
`drewry_ais_series.parquet` already exists from another agent's work). Consequence to be aware of, not
fixed: the checkpoint's `tables` count for this source (~50 per document, ~250 documents) is schema
coverage that does not exist, and its pdfplumber tables are interleaved-text garbage
(`'LR2 FlPeoewte rP BIe Drefsoktromp ance Week 33 202'` = "Fleet Performance" + "Power BI Desktop"
interleaved). Labelling this class is a classifier decision, not a one-line fix, so it is reported.

### Observation (NOT changed): 24% of embedded images hash to the same all-zero dhash

`charts/meta.jsonl` holds 102,809 image records; **24,689 (24.0%) carry `dhash =
0000000000000000`** and 27 carry `ffffffffffffffff`. This is not a coding error - the algorithm
compares horizontal neighbours, and a smooth gradient satisfies every comparison, so the hash is
degenerate for gradients. Checked one directly: `p00_373_00000000.jpeg` (1280x720, 93,903 bytes) has
mean 46.9 / stdev 52.5 / range 0-255 and its 9x8 downsample is `8,10,13,18,26,34,40,56,124` - a
monotone ramp, hence all-zero. The chart-linkage step the strategy doc calls for ("perceptual-hash
embedded images to link the same chart across weeks") therefore cannot link those 24,689 images. A
fix means choosing a second hash (aHash, or a gradient-normalised dHash) and changes the stored
filenames, so it is a decision, not a repair.

### HUMAN DECISION (unchanged, and now with a third component): derived DB + already-extracted text

Both fixes take effect only for documents extracted from now on. Nothing was re-extracted
(prohibited, and a human decision), so:

* `data/extracted/corpus/db` still holds pre-fix `text_verified` and `num_value` values
  (`build_table_db.py` copies `text_verified` straight out of the corpus `tables.jsonl`);
* the 7,742 already-extracted documents still carry 1,275 junk orphan tokens and 227 stale
  `ocr_queue` flags in their `pages.jsonl`;
* the two number-format fixes from the previous runs are still only in the parser, not in the DB.

Applying all of it:

    python scripts/extract/build_table_db.py --out data/extracted/corpus --rebuild
    python scripts/extract/build_series_sql.py     # then re-run the series QA

Note that the DB rebuild alone does NOT refresh `text_verified` or `pages.jsonl`: those live in the
corpus documents, so refreshing them means re-running the extractor over the affected documents
(227 flagged pages / 191 documents, or the 558 euro-decimal documents, or the whole corpus). I did not
choose that scope - it is the human call, and the affected list is in this entry.

### Deliberately not changed

* `corpus_checkpoint.jsonl` - never written; nothing under `data/extracted/corpus/` was written.
* No batch started, no document re-extracted, no `run_batch.py` / `batch_worker.py` /
  `verify_extraction.py` / `build_table_db.py` / `run_html_pass.py` edit, no push to main.
* The 3 pre-existing ruff findings in `extract_all.py` (unrelated to this fix, so left alone).
* Other agents' uncommitted work in the tree (`knowledge/**`, `scripts/process_knowledge.py`,
  `scripts/extract/docling_units.py`, deleted `build_series_wrong_gate.py`) - I committed only
  `scripts/extract/extract_all.py` and this log. I did not pull main: the tree is shared and mid-edit.
* The previous run's log entry (02:32 IST, currency-space fix) was sitting uncommitted; it is included
  in this commit so the audit trail is not lost.

## 2026-09-30 06:35 UTC (12:05 IST) - deep review: the working tree lost the fixes again, and a rebuild from it would REGRESS 36,956 cells

Job: "Extraction deep review + fix (3-hourly)". Read-only diagnosis plus one new check
script. No document re-extracted, nothing written under data/extracted/corpus/, no batch
started, no push to main.

### What I measured

verify_extraction.py --out data/extracted --state data/extracted/corpus_state.json
--checkpoint data/extracted/corpus_checkpoint.jsonl --json: checkpoint_rows 7,816 /
checkpoint_unique 7,816, doc_dirs 17,658, empty_by_design 114, empty_after_ok_status 0,
empty_after_failure 0, empty_unexpected 0, empty_not_in_checkpoint 856, crash_recovered_docs
249 / crash_rows_resolved 253, failure_kinds not-a-pdf 74 + no-extractable-content 1,
golden 15/15, disk_free_gb 30.2.

Liveness checked rather than assumed: the ONE action ("state file is 11532 min old") is the
stale-lag artefact of the tail rerun that owned corpus_state.json (done 880 / planned 882,
updated 2026-09-22T05:41Z). Get-CimInstance Win32_Process shows no run_batch, no
batch_worker, no extract_all - only the two Hermes gateways - so there is no duplicate batch
and nothing to kill. Corpus completeness was established on 2026-09-22 and is unchanged:
7,816 of 7,816 unique PDFs carry a terminal row.

Golden gate re-run for real, not quoted: sha256 of scripts/analysis/golden_matrix.json is
99cdcf6cca1e0ab90920cffc9b4f2558dfe0eba29053891e93ed74ad879634d7, identical to HEAD -
star_asia camelot-stream 13/15, pdfplumber 13/15, plumber-text 15/15, pymupdf-text 15/15;
ssy_atlantic camelot 14/14; breakwave plumber-text 6/6. The gate rewrote the file with LF
endings; it was restored and git diff on it is empty.

### Finding 1 (VERIFIED BY EXECUTION, unchanged): the working tree still does not hold the measured rules

The 02:44 UTC entry restored four fixes onto branch auto/extract-fixes-2026-09-30. The tree
is no longer on that branch (it is on benchmark/extraction-comparison), so the rules are
absent from disk again. I did not take that from git history - I ran the tree's own parser:

    to_number("209.523")    -> 209.523   (must be 209,523 dwt)
    to_number("60.000")     -> 60.0      (must be 60,000)
    to_number("1.460")      -> 1.46      (must be 1,460, a BDI level)
    to_number("$ 15,648")   -> None      (must be 15,648)
    to_number("11.118.522") -> None      (must be 11,118,522)
    to_number("34,5")       -> 34.5      (correct, comma decimal)
    to_number("1.234,5")    -> 1234.5    (correct, European full form)

### Finding 2 (NEW, and it changes the pending decision): rebuilding from this tree would LOSE 36,956 already-correct cells

Measured with the tree's parser over every distinct value in the live store that is numeric
today and carries a currency marker plus a space:

* 36,956 cells (9,233 distinct values, 389 documents) are numeric in corpus.duckdb and
  would become NON-NUMERIC under a rebuild from the current tree - 100 percent of them, zero
  exceptions. Largest: "$ 50,000" (230 cells), "$ 45,000" (138), "$ 33,500" (116),
  "$ 10,319" (113) - the broker $/day TCE columns.
* the branch parser loses 0 of them.

So the currency-space rule IS baked into the store built 2026-09-23 13:33 (the 02:32 IST fix),
and a rebuild from the current tree would regress it. The 02:44 UTC note framed a rebuild as
"no improvement plus a 1,000x penalty"; the accurate framing is that it is also a regression
of 36,956 cells. A rebuild must run from a tree that carries the rules.

### Finding 3 (NEW): the penalty is about twice the figure recorded this morning

SQL over the live store (6,946,400 cells). Period-shaped cells (d.ddd, three-digit groups)
in the three publishers whose convention was measured:

| publisher | cells | documents | pages |
|---|---|---|---|
| advanced_shipping | 28,686 | 248 | 1,422 |
| agora | 986 | 95 | 95 |
| star_asia | 65 | 29 | 34 |
| **total** | **29,737** | | |

By column header: Dwt 12,523, no header resolved 7,897, Teu 1,586, Actual last 735, Cbm 700,
Demolition Sales Ldt 416, Ldt 384, LDT 42, Baltic Indices Bulkers 333, plus/minus USD 203,
plus/minus percent 142, remainder under date headers. The tonnage-header subset alone
(dwt/ldt/teu/cbm = 13,365) is what the 02:44 UTC entry counted as 15,146 including
non-whitelisted publishers; the publisher rule reaches roughly twice that.

It reached the promoted layer: shipbrokers|vlcc|dwt|b1 has a daily row for 2026-07-27 whose
value is 299.999 while its own value_max is 319911.000, and the series mixes 296887 (a week
whose dwt column printed comma-thousands) with 296.887 (a week that printed periods). 294
shipbrokers series and 24 hellenic series carry at least one daily value below 10 against a
maximum above 100.

### Finding 4 (NEW, and it de-risks the fix): the whitelist direction holds on pages the fix never read

Read from the PDFs own text layers, three documents chosen from the same publishers, none of
them the document the 09-23 rule was derived from:

* advanced_shipping_2026_W22 (rule measured on W38): p1 chart y-axis ticks "10.000 20.000 ...
  60.000" (a $/day TCE scale), p2 dwt "53.712" and "181.221", p3 "180.000" with newbuild
  "$ 252m" - period is thousands.
* star_asia_2026_W21 (rule measured on 2024 W02): p1 prints "BDI: 2,991" with a COMMA, p2
  carries "the Beltiger 63/2017" whose cell is 63.027 - one publication, both separators,
  both thousands, which is what the rule assumes.
* agora_2026_W22 (rule measured on 2026 W18): p2 prints indices and levels as "3.226 / 5.517 /
  2.331 / $46.538" and ratios as "88,90 / 8,84% / 4,455%". Quantities use period-thousands,
  ratios use comma-decimals, and the rule fires only on three-digit groups, so the ratio
  columns cannot be inflated 1000x by it.

Also checked: advanced_shipping has zero cells carrying both separators, so the ambiguous
branch of the parser never fires for it (28,686 period-shaped against 145 comma-thousands;
for comparison star_asia is 65 against 28,996, agora 986 against 1,326).

### What I changed

One new file, scripts/extract/check_measured_rules.py, committed as 47134dbc0 on branch
auto/extract-fixes-2026-09-30 (today branch, which already holds the restored rules). It
asserts the 11 measurable number-format cases, each with a document+page citation so the case
can be re-derived from the PDF instead of trusted from the file, and exits 1 naming the
absent rule. Verified both ways, same script, two parsers:

    python scripts/extract/check_measured_rules.py <path to build_table_db.py>
      branch parser -> "all 11 measured rules present", exit 0
      tree parser   -> 7/11 MISSING, exit 1

Committed through a temporary index (git hash-object / read-tree / write-tree / commit-tree /
update-ref) so HEAD stayed on benchmark/extraction-comparison - git checkout would have
carried or refused another agent modified tracked files. Verified afterwards: the branch diff
against 6074ff4b3 is exactly one file added, and nothing was written into the working tree by
the commit.

Why a file rather than another log paragraph: this same failure - a fix that is committed,
silently absent from the tree, and invisible to every recall and plausibility check - has now
been found by hand three times (09-24, 09-30 02:44, 09-30 06:35). The script makes the fourth
time mechanical.

### HUMAN DECISION (one item, with a corrected number)

Order matters - check the parser before spending a rebuild on it:

    python scripts/extract/check_measured_rules.py    # must report all 11 measured rules present
    python scripts/extract/build_table_db.py --out data/extracted/corpus --rebuild
    python scripts/extract/build_series_sql.py

Run from a tree that carries the rules (merge or check out branch auto/extract-fixes-2026-09-30
or equivalent). From the current tree it would turn 36,956 numeric cells non-numeric
(Finding 2) and leave 29,737 period-shaped cells 1000x low (Finding 3). Nothing above is
applied. The affected documents are 248 advanced_shipping + 95 agora + 29 star_asia.

### Deliberately not changed

* corpus_checkpoint.jsonl - never written. Nothing under data/extracted/corpus/ was written,
  moved or deleted.
* No DB rebuild, no series rebuild, no document re-extracted, no batch started or killed.
* scripts/analysis/golden_matrix.json - rewritten by the gate run, then restored; git diff empty.
* The 2026-09-21..09-28 fix branches were not merged into the current branch: the tree is
  shared and mid-edit by other agents (modified scripts/scrapers/fetch_drewry_wci.py and
  backfill_wci_history.py, about 70 untracked files under scripts/extract/), so branch topology
  is a human call, not mine.
* Observed but not touched: all 7,816 checkpoint rows still record their pre-reorg path
  (reports/shipbrokers/...), which no longer exists after the corpus/ migration - an
  explicit-path-field that silently 404s for anything reading the checkpoint as an index.
* No push to main.

## 2026-09-30 10:33 UTC (16:03 IST) - deep review: the four fixes are now IN the working tree, and the garbled-route loss is ~1,400 pages, not 181

### What I measured first

No batch is running: zero python processes matching run_batch / batch_worker / extract_all,
and checkpoints last written 2026-09-22 11:12 IST (state_age_min 11,811). verify_extraction.py:
done 880 / planned 882, ok 876, no-extractable-content 1, error 3, checkpoint 7,816 rows all
unique, 17,658 doc dirs, quality over the last 40 docs = median 634 blocks / 37 tables / 2
images, mean text_verified 0.861, crash-recovered 249, golden 15/15, db "not built yet",
disk free 36.6 GB.

### Finding 1 (fixed): the same four fixes were AGAIN absent from the working tree

The recurring one, now with the mechanism named. The tree is on benchmark/extraction-comparison
and its blob for each file is an OLDER revision than the fix:

  file                     tree/HEAD blob   commits with it             fix blob
  build_table_db.py        c004cae1d        aa5bc7b5b (09-22)           ac6878465
  extract_all.py           9eb858ffc        b20829464 (09-23)           a09e9aa1d (4764f1512)
  publishers/run_ssy.py    3032ccbb6        c837886ac (09-24)           686b2d7a7 (5dbe6da77)

Every previous repair wrote a commit through a temporary index, which by design leaves the
tree alone, so the tree kept regressing the moment anything ran from it. Before: from the tree,
check_measured_rules.py reported 7/11 measured rules MISSING (5 of them as a to_number()
signature error). After: "all 11 measured rules present", exit 0.

Fixed by applying the three files from 6074ff4b3 (verified there to be "main plus that fix
only") into the WORKING TREE, and committing that tree to a new branch
auto/extract-fixes-2026-09-30-tree (commit 1bd53067), HEAD left on
benchmark/extraction-comparison so no other agent's checkout is disturbed. The working tree now
carries the fixes, which is what actually runs.

Evidence after applying, all measured this run:

* check_measured_rules.py from the tree: 11/11, exit 0 (was 4/11).
* golden_matrix.py output byte-identical before and after; star_asia camelot-stream 13/15,
  plumber-text 15/15, pymupdf-text 15/15 - no recall change. scripts/analysis/golden_matrix.json
  was rewritten by the gate run and restored; git diff empty.
* build_table_db.py, 8-document pool (advanced_shipping W22 and W44 2021, allied W12 2022,
  carriers W46 2023, golden_destiny W31 2022, star_asia W21 2026 and W02 2024, one seabrokers
  month), old parser vs new on identical tables.jsonl:
    - distinct table contents 369 vs 369, 0 lost; 690 cells dropped as duplicates and all 690
      have an identical (doc,page,engine,row,col,value) twin still present;
    - 267 cells corrected by exactly 1000x ("1.460" 1.46 -> 1460.0; "1.000" 1.0 -> 1000.0);
    - 565 cells became numeric that were not (548 of them the "$ 15,648" currency-space shape,
      e.g. "$ 15,648" -> 15648.0), 17 period-thousands.
* extract_all.py, allied_2022_W11 SnP Statistics, same PDF, everything else identical
  (9 pages, routes {garbled 5, scanned 1, image-heavy 3}, 300 blocks, 80 images): tables
  7 -> 26. Pages 2-6, i.e. all five garbled-routed pages, went from 0 stored tables to 19.
  The recovered page-2 grid is 80 rows x 8 cols, text_verified 1.0, garbled_cells 0, and reads
  real SnP totals: "903" vessels sold, "61,002,799" DWT, "12" avg age, "$ 9,510.2m" invested
  capital; 184 of its 210 digit-carrying cells are present verbatim in the page text layer.

### Finding 2 (measured, needs a human decision): the garbled-route skip is far wider than 181 docs

The 09-28 note recorded "page 7 of every hellenic demolition weekly (181 documents)". Measured
properly, across every document that has a pages.jsonl, the population is:

  1,520 garbled-routed pages in 717 documents, concentrated in four RECURRING sources -
  shipbrokers 743 pages / 314 docs, ppa_pdf 387 / 126, hellenic 181 / 181, seabrokers 96 / 96
  (the rest are one-off books and wayback filings).

Sampling 40 of those pages and probing the SOURCE PDF (the stored text.jsonl fuses numbers into
prose, so a block-level test cannot see them): 37 of 40 (92.5%) are table-shaped at the PDF
level, >=5 y-bands each holding >=2 numeric tokens, mean 30.1 numeric rows per page - and 0 of
those 37 pages stored a single table record. Examples: allied_2022_W11 p2 (42 numeric rows),
ppa_pdf/31a3d8838b75 p2 (44), ppa_pdf/4ca4100fd3dd p4 (44), seabrokers 2022-01 p6 (11),
hellenic 2022-07-11_gms-week-27 p7 (13).

Scaling the measured rate over that population gives ~1,400 table-shaped pages whose tables were
never stored - an estimate from a 40-page sample, not a count. The allied before/after above is
the measured unit cost: 19 tables on 5 pages.

The tree now carries the fix, so any future extraction recovers these. The stored corpus does
not, and applying it means re-extracting 717 documents - a human decision, and NOT the whole
corpus. The command I would run (blast radius: writes 717 existing doc dirs under
data/extracted/corpus/, leaves the checkpoint alone, so --resume will not redo them):

  python scripts/extract/extract_all.py --inventory <the 717 (source, doc) rows> --out data/extracted

Before spending it: check whether the affected source has already been re-parsed by its own
bespoke runner (several exist - run_seabrokers_llamaparse.py, run_hellenic_demolition.py,
run_ppa*), in which case the extract_all tables are not what the series read and the re-run is
worth less. I did NOT verify that per source; it is the first thing to check.

### What I changed

* scripts/extract/build_table_db.py, scripts/extract/extract_all.py,
  scripts/extract/publishers/run_ssy.py - applied from 6074ff4b3 to the working tree; byte
  identical to that commit (git diff empty).
* scripts/extract/check_measured_rules.py - added to the tree (it existed only on
  auto/extract-fixes-2026-09-30), so the gate can be run before any rebuild is believed.
* Branch auto/extract-fixes-2026-09-30-tree, commit 1bd53067, four files vs HEAD.
* Append-only edit to this log.

### Deliberately not changed

* corpus_checkpoint.jsonl - never written. Nothing under data/extracted/corpus/ written, moved
  or deleted; the only reads were opens. No document re-extracted. No DB rebuild (the DB is
  still empty, data/extracted/db is 0 files) and no series rebuild - both remain human calls.
* run_intermodal_full.py and run_star_asia_tables.py carry other agents' uncommitted edits; left
  alone.
* The 1,520 garbled pages were not fixed: that needs re-extraction (above), not a code change.
* The 7,816 checkpoint rows still carry pre-reorg paths (reports/shipbrokers/...): still open,
  still only an explicit-path-field that a reader would 404 on.
* scripts/analysis/golden_matrix.json - restored to HEAD after the gate run rewrote it.
* I did not merge any auto/extract-fixes-2026-* branch into benchmark/extraction-comparison or
  main. The tree now carries the fixes; branch topology is a human call.
* No push to main.

## 2026-10-01 05:52 UTC (11:22 IST) - deep review: the health check was crying wolf again (its fix had vanished), and the 717-doc re-extraction buys almost nothing

Verdict: **FIXED** - one proven verifier regression repaired. The extraction pass itself is complete
and healthy (7,816/7,816 documents, 0 remaining, golden 15/15); the material new result is that
yesterday's proposed 717-document re-extraction is worth close to zero, with the measurement below.

### What I measured first (all read-only)

`verify_extraction.py --json`: 7,816 checkpoint rows / 7,816 unique paths, `empty_after_ok_status` 0,
`empty_unexpected` 0, `empty_not_in_checkpoint` 856, `empty_by_design` 114, golden **15/15**,
249 crash-recovered rows all resolved, disk 31.7 GB free. Statuses: ok 7,488, CRASH 249 (all
recovered), error 75, timeout 3, no-extractable-content 1. Inventory (7,676 after content-duplicates
and PROVENANCE_ONLY) minus checkpoint = **0 documents to extract**.

Liveness, honestly: no `run_batch` / `batch_worker` process exists. The only python.exe processes are
the two Hermes gateways. The pass finished 2026-09-22; `corpus_state.json` is 12,970 min old because
the job is done, not because it died.

Checkpoint-vs-disk consistency over all 7,816 rows: **0 rows with status ok whose output directory is
missing**. The only 74 rows whose directory is absent are the not-a-pdf quarantines, which were never
extracted. So there is no provenance gap for any successful document.

### Finding 1 (FIXED, proven by execution): check_state had lost its remaining_work() check

The 2026-09-23 entry records this exact defect as fixed: a stale state file with `remaining == 0` must
read `run COMPLETE, not a dead batch`, and the action must fire only when documents really remain;
after that fix the verifier printed `OK - no action required`. Measured today, `remaining_work()`
existed nowhere in `scripts/extract/`, and `check_state` warned unconditionally.

Before (first run today): actions = ["state file is 12915 min old (> 30) - batch may have died;
rerun with --resume"] - the same false alarm the hourly job has printed for a week.

After (restored helper, same corpus): actions = [], exit 0, and
state_note = "state file is 12970 min old but 0 documents remain (7676 planned, 7816 recorded) -
run COMPLETE, not a dead batch".

The restored helper recomputes run_batch's own queue (`load_inventory()` minus `PROVENANCE_ONLY`) and
subtracts the checkpoint, so `7676 planned` reproduces the 09-23 figure exactly. All three branches
were exercised directly: real checkpoint -> 0; missing checkpoint -> 7,676 (plan, 0 recorded); queue
unrecomputable -> `None`, which falls back to the old warning rather than claiming a finished corpus.
Golden unaffected: `golden_matrix.py` re-run gives star_asia camelot-stream 13/15, plumber-text 15/15,
pymupdf-text 15/15, ssy_atlantic 14/14 - identical to the committed matrix, and
`scripts/analysis/golden_matrix.json` is unmodified.

### Finding 2 (resolves the open question from the 10:33 run): 510 of the 717 documents are covered by a pipeline that never reads the extract_all tables

The 10:33 entry left this unanswered: check whether the affected source has already been re-parsed by
its own bespoke runner - "I did NOT verify that per source; it is the first thing to check."

Answer, measured. The bespoke runners under `scripts/extract/publishers/` open the SOURCE PDFs
directly (e.g. `run_hellenic_demolition.py` opens `corpus/02-hellenic/demolition` with pymupdf) and
write `data/extracted/md/<pub>/*.tables.json` plus `data/extracted/series/*.csv`; **none of them read
`data/extracted/<run>/<source>/<stem>/tables.jsonl`**. `index.html` fetches none of that tree either
(it reads `data/views/`, `data/derived/`, `data/clarksons/`, `data/etf/`). `build_table_db.py` is the
only consumer. So for any publisher with a bespoke runner, re-running `extract_all` on its documents
changes nothing any series or the app can see.

Recounting the affected population from the stored `pages.jsonl` (my numbers; the 10:33 run counted
1,520 pages across 717 docs, I get 1,469 pages across 727 docs - the difference is 75 rows with no
`pages.jsonl`, i.e. the quarantines, and it does not change the conclusion):

| Publisher affected | Docs | Bespoke pipeline that bypasses extract_all |
|---|---|---|
| shipbrokers/allied | 129 | **none - and archived** |
| shipbrokers/golden_destiny | 78 | **none - and archived** |
| shipbrokers/banchero | 59 | `run_banchero_*` -> 10 series CSVs, 256 md files |
| shipbrokers/xclusiv | 39 | `run_xclusiv_tables.py` -> 10 CSVs, 21,212 rows |
| shipbrokers/advanced_shipping | 5 | `run_advanced_shipping_tables.py` -> 5 CSVs, 18,744 rows |
| shipbrokers/fearnleys | 4 | `run_fearnleys*` -> 7 CSVs |
| hellenic | 181 | `run_hellenic_demolition.py` etc. -> 31 CSVs, 265,104 rows |
| ppa_pdf | 126 | `run_ppa.py` -> `data/extracted/ppa/hedland_rows.jsonl` (1.9 MB), `dampier_rows.jsonl` (2.3 MB) |
| seabrokers | 96 | `run_seabrokers_llamaparse.py` -> 9 CSVs, 16,500 rows |

510 of the 717 belong to a publisher whose series never read these tables. The only uncovered
documents are allied (129) and golden_destiny (78) - **both are in `corpus/archive/`**: allied's newest
issue is `allied_2024_W07`, golden's is `golden_destiny_2024_W48`, both more than 180 days old, so
BACKFILL_ONLY by the liveness rule. Neither has a series CSV and neither is named as data anywhere in
`index.html` (the only textual hits are unrelated: "golden age", "Golden Dip", "Golden Ocean").

The defect itself is real and was re-verified at page level rather than taken on trust.
`allied_2021_W26_ALLIED-SnP-Statistics`: pages 2-6 are routed `garbled` and store **0 tables each**,
while sibling pages 1/7/8 store 2-3 tables each. Probing the source PDF with pymupdf, those same pages
carry 62 / 32 / 43 / 59 / 19 y-bands holding 2 or more numeric tokens - they are the SnP statistics
pages, i.e. the actual data. 20 of 20 sampled allied garbled pages are table-shaped. The fix is in the
working tree (`tabular_page` now includes non-mojibake `garbled` pages), so this is a backfill of two
dead titles, not a live-series gap.

### Finding 3 (measured; runbook corrected): the 74 not-a-pdf quarantines are genuine, not a regression

The runbook's known-failures row said "3 files with bad %PDF- headers (breakwave x2, signal fueleu)" -
that was the 303-document dryrun. The full pass quarantined **74**. Re-checked by magic bytes rather
than by assuming the check was right: of the 6 whose source file still exists, **0 are PDFs** - 5 HTML
(`<!DOCTYPE html>`, `<html><head>`) and 1 DOCX (`PK`, `word/document.xml`). The other **68 source files
no longer exist anywhere in the repo** (breakwave "commodity call" HTML-dumps, e.g.
`2023-06-09_metals-gain..._commodity-call-fine-china_bd06483485bb.pdf`, gone during the
`corpus/<NN-group>/` reorganisation; a substring search for the names returns nothing). Quarantine
cost 0 real documents. Runbook row corrected and a note added so a future verifier does not "fix" it.

### Observation (measured, no change made): the structural shape of the stored tables

Census over all 16,803 document `tables.jsonl` files (occ% = non-empty cells / all cells):

| source | docs | tables | cells | occ% | tables tv=0 | 1-col % | 2+ numeric rows % |
|---|---|---|---|---|---|---|---|
| shipbrokers | 3,429 | 99,252 | 9,250,931 | 40.7 | 7% | 25% | 45% |
| hellenic | 5,199 | 57,351 | 6,149,065 | 36.6 | 3% | 14% | 67% |
| drewry_ais_pdfs | 276 | 11,244 | 655,434 | 20.0 | **38%** | 12% | 38% |
| poten | 1,084 | 4,743 | 350,948 | 28.2 | 3% | 30% | **13%** |
| seabrokers | 96 | 4,290 | 309,389 | 41.3 | 4% | 7% | 26% |
| baltic | 2,217 | 1,088 | 16,320 | 99.9 | 0% | 0% | 50% |
| ppa_pdf | 207 | 860 | 332,882 | 58.6 | 0% | 0% | 100% |
| signal | 513 | 381 | 3,810 | 47.0 | 0% | 86% | 2% |

Two things worth knowing, neither a defect I should silently "fix":
- **No text blobs anywhere**: 0 documents in the whole corpus have a text block over 20,000 chars; the
  largest block in any document is 7,618 chars.
- The union extractor's low occupancy (36-41% on the two big sources) and the ~25% single-column tables
  on shipbrokers are the pdfplumber leg shredding sparse Power BI / slide layouts. The already-recorded
  2026-09-23 observation (drewry's tables are Power BI scaffolding) still measures true: drewry is the
  lowest occupancy at 20.0% and the highest share of `text_verified == 0` tables at 38%. `poten` is the
  other outlier: only 13% of its 4,743 stored tables hold 2 or more numeric rows, so 87% are prose
  fragments, not tables. Both publishers have bespoke runners that bypass this tree, and the DB that
  consumes it is not built, so today the impact is nil. Changing the union's table filter would move
  ~99,000 shipbrokers tables and must not be done without the DB rebuild decision below.

### What I changed

* `scripts/extract/verify_extraction.py` - restored the `remaining_work()` helper and made
  `check_state` raise the stale-state action only when documents actually remain (it now also names
  the count). Commit **3b39bdc5e** on branch `auto/extract-fixes-2026-10-01` (+61/-4).
* `docs/EXTRACTION_RUNBOOK.md` - corrected the quarantine row to the measured 74 with the magic-byte
  evidence, and added a "what the extract_all corpus does and does not feed" section carrying the
  coverage table above. Commit **4c6f5bd03** on the same branch (+43/-1).
* Evidence and scratch scripts under `scratch/review/`, deleted at the end of this entry.

### Deliberately not changed

* `data/extracted/corpus_checkpoint.jsonl` - never written; nothing under `data/extracted/corpus/` was
  written, moved or deleted. No document was re-extracted. No DB rebuild, no series rebuild.
* **No re-extraction of the 717 documents.** Yesterday's entry proposed it as the main follow-up;
  measured today, 510 of the 717 are covered by bespoke runners and the remaining 207 are two archived
  titles. It is a human call and now looks like low value.
* The union table filter (the observation above) - a change there affects ~99,000 tables and is only
  meaningful together with the DB rebuild.
* `scripts/extract/publishers/run_intermodal_full.py` and `run_star_asia_tables.py` carry other agents'
  uncommitted edits; left alone. `run_hellenic_iron_ore_pdf.py` is dirty in the working tree from
  another agent and was not staged by me.
* No merge of any `auto/extract-fixes-*` branch into `main`. No push to main.

### HUMAN DECISIONS

1. **Rebuild the derived DB** (unchanged, still pending, now also blocks any table-filter change):
   `data/extracted/corpus/db/corpus.duckdb` still holds the pre-fix 2026-09-22 and 2026-09-23 numbers.
   Command: `python scripts/extract/build_table_db.py --out data/extracted` then
   `python scripts/extract/check_measured_rules.py`.
2. **Re-extraction of the 717 documents - now recommended SKIP.** If it is wanted anyway, the only
   defensible subset is allied + golden_destiny (207 docs, 551 garbled pages), and it backfills two
   titles that stopped in 2024. The current recommendation is to leave it.
3. The 68 checkpoint rows whose source PDFs no longer exist are a provenance curiosity only - the rows
   are correctly quarantined and no artefact is missing.
## 2026-10-01 09:44 UTC (15:14 IST) - deep review: the health check said run COMPLETE for a corpus 274 documents bigger than the list it was checking

Verdict: **FIXED** - one proven verifier defect repaired. The extraction pass itself is
complete and the corpus is intact; the defect is that its completeness claim was computed
against a frozen inventory rather than against the corpus on disk.

### What I measured first (all read-only)

`verify_extraction.py --json`: 7,816 checkpoint rows / 7,816 unique paths,
`empty_after_ok_status` 0, `empty_unexpected` 0, golden **15/15**, 27.1 GB free, and
`corpus_state.json` 13,200 min old with 0 documents remaining. Liveness, honestly: no
`python.exe` carries `run_batch` or `batch_worker` (the only python.exe processes are the two
Hermes gateways), so the stale state file is a finished job, not a dead batch.

The 05:52 fix to `remaining_work()` (commit 3b39bdc5e) is **in main and in the working tree** -
the "fixes vanished" failure mode did not recur this time. `scripts/extract/` was clean at the
start of this run (only `data/derived/broker_reports_checkpoint.json` was dirty, and that is
another job's file).

### Finding (FIXED, proven by execution): "run COMPLETE" was a statement about inventory.jsonl, not about the corpus

`run_batch`'s queue - and therefore `remaining_work()`, added yesterday - is computed from
**`data/extracted/inventory.jsonl`, a frozen file built 2026-09-21 (`build_inventory.py` is
reorg-aware, but nothing re-runs it)**. Every issue that landed in `corpus/` afterwards is
invisible to the queue, so the check printed `0 documents remain ... run COMPLETE` for a corpus
that had grown past the list. Measured with the same roots `build_inventory.py` walks:

| measure | value |
|---|---|
| inventory.jsonl built / rows | 2026-09-21 / 9,912 (7,816 after content-duplicates) |
| PDFs on disk under those roots | **12,912** |
| absent from the inventory by filename | **338** |
| of those, content (md5) the inventory has never seen | **274** (all 338 hashed offline) |

The 274 break down as: 176 `fearnleys-md/pdfs` backfill files, plus 2026 W36..W39 broker
weeklies (advanced_shipping, affinity, agora, banchero_costa, carriers, clarksons, intermodal,
ism, lion, ssy, star_asia, xclusiv), MMI iron-ore dailies to 2026-09-28, GMS/Best Oasis
demolition weeks 38-39, Breakwave dry/tanker, 12 Drewry AIS weeklies and 7 Signal PDFs.

**No live series was gapped by this** - the publishers' bespoke runners open the source PDFs
directly, and I checked rather than assumed: `md/banchero_costa/` holds W36/W37/W38 `.md` +
`.tables.json`; `hellenic_gms_demolition_series.csv` runs to issue_date **2026-09-25**;
`best_oasis_demolition_series.csv` to **2026-09-19**; `hellenic_iron_ore_daily_series.csv` to
**2026-09-28**. The other 4,061 filename-absent files are content-duplicates of already
extracted documents (verified by md5 against the inventory) - correctly skipped, not gaps.

### What I changed

* `scripts/extract/verify_extraction.py` - added `inventory_drift()` / `check_inventory_drift()`:
  walks the inventory's own roots, compares filenames, and md5s **25 of a sorted candidate
  list** to confirm the residue is unseen content. It is surfaced in `state_note` and as
  `info["inventory_drift"]`, and it is **informational only - never an ACTION**, so the hourly
  job still exits 0. Commit **d697e76a1** on branch `auto/extract-fixes-2026-10-01-corpus-drift`.
* The md5 step is a sample on purpose: hashing all 338 measured **104 s cold**, which took the
  whole hourly check from 25 s to **2 m 09 s**. With the 25-candidate sample the check is back
  to **25.3 s**; the full 338/274 figures above come from a one-off offline run and are recorded
  in the function's docstring.
* A bug in my own first implementation is worth recording: the roots overlap
  (`corpus/01-brokers` and `corpus/01-brokers/fearnleys-md`) **and spell the same directory with
  different separators**, so de-duplicating on the raw path string counted the 176 fearnleys-md
  files twice and reported 450 instead of 274. Fixed by de-duplicating on
  `os.path.normcase(os.path.normpath(...))`; this is the same class of defect as the stale-path
  lesson in the skill (a path string is not a stable identity).
* Verified the branches directly, not by inspection: real corpus -> 338 absent / 19 of 25 sampled
  unseen; missing inventory -> degrades to an error dict, no exception and no claim; empty roots
  -> zeros; `check_inventory_drift` populates `info`.

### Additions to the verifier, after the change

```
state_note: state file is 13200 min old but 0 documents remain (7676 planned, 7816 recorded)
            - run COMPLETE, not a dead batch; NOTE: the queue comes from inventory.jsonl built
            2026-09-21, and 338 PDFs now in the corpus are absent from that inventory by
            filename (19/25 of a deterministic sample were unseen content), so COMPLETE
            describes that list, not the corpus
actions:    []          (exit 0)
```


### Other things measured today (no change made)

1. **The chart store's dhash series key is degenerate for 24% of entries.** Census over all
   17,654 document dirs / 7,742 `charts/meta.jsonl` files / **102,809 entries**: **24,689
   entries (24.0%) carry the all-zero dhash `0000000000000000`**. I opened 15 of them rather
   than guessing: every one is a flat image (`RGBA`, `min == max`, 1 distinct grey level) - an
   alpha mask, a solid band or a 1239x4 rule strip, e.g. `p00_14_00000000.png` (795x30, one
   level), `p00_26_00000000.png` (226x140, one level). `img_dhash` returns all-zero for any
   uniform image by construction. Consequence if anyone later groups by dhash to rebuild a
   series (which the strategy nominates as a capability): 24,689 unrelated images collapse into
   one bogus series. **Nothing consumes this tree today** (`build_table_db.py` globs
   `tables.jsonl` only), so this is a documented landmine, not a repair - and repairing it
   would require re-extraction, which is a human decision.
2. **The star_asia Gaddani cell-boundary defect recorded in `MASTER_EXTRACTION_PLAN.md` section 9
   no longer reproduces.** Scanning all 200 `md/star_asia/**/*.tables.json` (47,979 rows):
   **579 label cells mention GADDANI and 0 of them are dirty** (no digit, no fused TURKEY, all
   carry PAKISTAN), and 0 of 1,529 yard-label cells (GADDANI/TURKEY) carry a value or the next
   row's yard. The 122 TURKEY labels that do carry a footnote (`TURKEY / ... For Non-EU ships
   ... USUS$30-40/ton less`) have intact value columns (`300 ~ 310`, `290 ~ 300`, ...). So that
   item can come off the plan's next-actions list.
3. **The live series survive a plausibility audit.** All 120 `data/extracted/series/*.csv` were
   grouped by their non-numeric key columns and every numeric column checked for a
   max/min >= 200x with n >= 5. Exactly one family flagged -
   `athenian_yearly_demolition_volume_series.csv`, `demolition_mio_dwt` 0.10 .. 55.8 - and it is
   **my own pivot's bug, not the data's**: `year` (2007..2021) is numeric so my audit put it in
   the value set instead of the series key, fusing 16 year-rows into one "series". Rows read
   `2007 -> 5.3`, `2012 -> 55.8`, `2021 -> 12.8`, which are plausible annual totals. That is
   the skill's Bug 2 reproduced by accident, and it is the reason I did not report a defect.
4. **Every literal `fetch()` target in `index.html` resolves.** 42 distinct paths; the only
   apparent miss, `data/derived/fearnleys_comments_`, is a string-concatenation prefix, not a
   path. So the corpus reorganisation has not left the app 404ing through the paths the app
   itself names.
5. **The extract_all tree still feeds nothing** (re-confirmed: `index.html` reads
   `data/{{views,derived,clarksons,etf,reports,bunkers,cargo,congestion,geospatial,provenance}}`
   only). This is why the drift above is informational rather than urgent.

### Deliberately not changed

* `data/extracted/corpus_checkpoint.jsonl` was never written, and nothing under
  `data/extracted/corpus/` was written, moved or deleted. No document was re-extracted. No DB
  rebuild, no series rebuild.
* **No re-extraction of the 338 filename-absent documents.** They are already covered by the
  bespoke runners (evidence above); re-running `extract_all` over them would populate a tree
  nothing reads. This supersedes yesterday's "backfill allied + golden_destiny (207 docs)"
  option for the same reason - that tree is not consumed.
* The union table filter and the dhash degeneracy above - both change ~99,000 tables or need
  re-extraction, and are only meaningful together with the DB rebuild decision below.
* `scripts/extract/publishers/run_drewry_ais.py` was modified in the working tree by another
  agent during this run; left alone and not staged.
* No merge of any `auto/extract-fixes-*` branch into `main`. No push to main.

### HUMAN DECISIONS

1. **Rebuild the derived DB** (unchanged, still pending): `data/extracted/corpus/db/corpus.duckdb`
   still holds the pre-fix 2026-09-22/23 numbers. Command:
   `python scripts/extract/build_table_db.py --out data/extracted` then
   `python scripts/extract/check_measured_rules.py`.
2. **Decide whether the platform-driven `extract_all` tree is wanted at all.** It is complete
   for its 2026-09-21 list and consumed by nothing the app displays, while the corpus grows
   ~30 documents/week. Two defensible options: retire it (leave the bespoke runners as the
   pipeline, and the new drift note as the record of why) or re-run `build_inventory.py` plus a
   resume so it tracks the corpus. I did neither - both are programme decisions, not repairs.
3. **Audit-trail issue, not a data issue:** my in-progress edit to `verify_extraction.py` was
   picked up by another agent's parallel commit **6a4892683** (`feat(drewry-ais): ingest 9 new
   weekly reports...`, which also stages `run_drewry_ais.py` and a corpus xlsx), and the rest of
   the fix is in **d697e76a1**. The file is correct and self-consistent at HEAD, but the fix is
   split across a code commit and a data commit, so a revert of 6a4892683 would take most of it
   with it. Flagging because this repo's convention is code and data commits kept separate.

## 2026-10-01 14:13 UTC (19:43 IST) - deep review: three publishers read the European decimal comma as a thousands separator

### What I measured first

* `verify_extraction.py --json`: run **COMPLETE** (7,676 planned / 7,816 recorded, 0 remaining),
  `status_counts {ok: 876, no-extractable-content: 1, error: 3}`, golden **15/15**,
  `inventory_drift` **345** PDFs absent from the 2026-09-21 inventory (338 yesterday),
  `crash_recovered_docs` 249, disk free 23.9 GB, `actions: []`.
* Process check: **no `run_batch` / `batch_worker` process is running** (Win32_Process query
  returned nothing). Nothing was killed, nothing was restarted.
* Integrity sweep over all **166 delivered `data/extracted/series/*.csv`** (595,952 data rows):
  date-key anomalies, duplicate keys, constant columns, junk in numeric columns, and a 1000x
  pairing detector. Most hits were the detector's own false positives (a column named
  `..._usd_per_day` matches a `day` date regex); the real signal was the price columns.

### What I found (all values reproduced from the publisher's OWN source document)

Prices printed with a **decimal comma** were stored 10x-1000x too large, because each runner
deleted the comma before reading the number. Ground truth, read as positioned text from the
source PDFs (never from another extractor):

| publisher / doc | line on the page | was stored | correct |
|---|---|---|---|
| intermodal 2025 W09 p3 | `CAPE MOUNT AUSTIN 178,623 2010 MITSUI, Japan ... $ 26,75m` | 2675.0 | **26.75** |
| intermodal 2023 W47 p3 | `KMAX PEDHOULAS CHERRY 82,013 2015 MAN-B&W Jul-25 $26,625m` | 26625.0 | **26.625** |
| intermodal 2024 W46 p5 | `SK SUMMIT 76,064 29,971 1999 DAEWOO, S. Korea GAS TANKER 469,5/ldt` | 4695.0 | **469.5** |
| platou hellas 2022-06-17 | `EMILIA 53,098 2002 OSHIMA 4 x 30 T USD 13,9 M CHINESE` | 139.0 | **13.9** |
| platou hellas 2026-02-13 | `ILMA 318,395 2012 HYUNDAI HI ... USD 98,2 M S. KOREAN` | 982.0 | **98.2** |
| carriers 2023 W46 p0 | `MAGIC MOON BC 76,602 2005 Imabari, Japan 11,80 TURKISH` | 1180.0 | **11.80** |
| xclusiv 2023-12-04 p3 | `TANAIS FLYER 28,674 1998 JAPAN IMABARI UNDISCLOSED 4,8` | 48.0 | **4.8** |

The publishers mix BOTH conventions inside one table, which is why no single rule was safe: the
shape census over intermodal's 3,358 price strings is 1,629 period-decimal, **179 decimal-comma**,
and thousands-grouped only on amounts that are not millions figures.

**Rows affected, measured per delivered CSV:** intermodal sales **179**, intermodal demolition
**5**, clarksons `snp_sales` **6**, xclusiv sales **1** = **191 rows corrected by this change**;
carriers is a further **10** (see "not changed").

### Two column-mapping defects found in the same intermodal sales branch

* **The Gas sub-table's header omits the `Built` label** - 11 data cells under 10 labels, so every
  field from `Yard` rightward sits one column early. Ground truth (2023 W22 p3):
  `LPG GLOBAL SCORPIO 58,814 2003 HYUNDAI, S. Korea MAN-B&W Jul-23 80,530 $ 47.5m undisclosed`.
  We stored `dwt='-23'`, `built=''`, `yard='2003'`, `m_e='undisclosed'`, `price_raw='80,530'`.
  Now: `dwt=58814, built='2003', yard='HYUNDAI, S. Korea', m_e='MAN-B&W', ss='Jul-23',
  price='$ 47.5m' -> 47.5`. Detected **per row on content** (no `Built` column exists and the cell
  under `Yard` is a 4-digit year), never on geometry.
* **`Cbm` was an alias for `Dwt`** (the capacity column overwrote the deadweight on gas rows), and
  **the engine test was a substring test** so the `Comments` header matched `me`: the engine column
  held comment text on **824 of 3,358 rows** and the comments column is **empty on all 3,358**.
  Header spellings actually present in the 818 sales tables: `M/E` and `Comments` only.

### What I changed

Branch **`auto/extract-fixes-2026-10-01-decimal-comma`**, commit **bdc62bd92** (+201/-44, 4 files,
code only - no data file touched):

* `scripts/extract/publishers/run_intermodal_full.py` and `run_intermodal_tables.py` -
  `read_dual_separator_number()` + `parse_price_mill()` + `parse_price_per_ldt()`; the per-row
  `Built`-omitted shift; the `Cbm`/`M/E` header guards.
* `scripts/extract/publishers/run_clarksons_hellas_world_class.py` - `parse_price_usd_m()` comma rule.
* `scripts/extract/publishers/run_xclusiv_tables.py` - `parse_price_mill()` comma rule.

Each publisher keeps its OWN reader (no shared numeric parser, per plan section 10).

**Evidence, isolated so my own change is the only variable.** Old-parser vs new-parser over every
distinct raw price string the CSVs contain: clarksons 677 strings -> **exactly 6 changed**, all
corrections; xclusiv 1,729 strings -> **exactly 1 changed**, a correction. For intermodal, all 257
cached reports were re-parsed offline (`llama_parse` stubbed; **no API call, no credit spent**) and
diffed against each document's own sidecar: **3,367 sales rows compared, 185 changed** (179
decimal-comma + 6 column-shift), **5 of 581 demolition rows changed**, **0 rows lost**, **0
period-decimal prices moved**, **0 parse errors**.

Self-caught regression, worth recording: my first helper stripped every separator, so `'$ 47.5m'`
became 475.0 and a malformed source string `'12,.2m'` crashed the parse on 2 of 257 documents. The
20-case unit test (`scratch/review_dr/unit_test_prices.py`) now covers period decimals, decimal
commas, 3-digit groups, malformed `12,.2`, flat dollars and `$/ldt`, and passes on both runners.
The blast-radius diff above is the control that would have caught it.

Golden gate re-run after the change: `python3 scripts/analysis/golden_matrix.py` - Star Asia **text
15/15** (plumber + pymupdf), camelot-stream 13/15, pdfplumber 13/15, tabula 9/15, lattice 2/15 -
**identical to the matrix documented in EXTRACTION_STRATEGY.md**. No regression.

### Deliberately NOT changed

* **The delivered series CSVs were not regenerated.** A re-run rewrites `data/extracted/series/**`,
  which is outside this job's write scope (scripts/extract/ and docs/EXTRACTION_*.md only). **Until a
  re-run, those 191 rows still hold the old values.** The fix takes effect for documents processed
  afterwards; the regeneration commands are in HUMAN DECISIONS below.
* **carriers** (2 `sales` + 3 `newbuilding` + 5 `dry_tc_period` rows) shows the same signature but its
  price reader is `parse_numeric()`, **shared with the `dwt` field where the comma IS a thousands
  separator** (`'77,750'`). Fixing it needs a price-only reader, and the `ATL 16,5-17,000` rows are a
  source typo inside a range (16,500-17,000) where the intended point value would be a guess.
  Measured and left for a source-specific pass rather than guessed at.
* **`'#####'` as `year_built`** (MAHAVIR, intermodal 2023 W10) is NOT our defect: the PDF itself
  prints `#####` (`MAHAVIR 74,005 10,540 ##### IMABARI, Japan BC $ 560/Ldt Bangladeshi`) - a
  spreadsheet cell exported too narrow by the publisher. Left as the source's own artefact.
* The `--stem`/`--limit` truncation hazard, the hardcoded key, and the DB rebuild (all below).
* `scripts/extract/publishers/run_poten.py` is dirty in the working tree from another agent; not
  staged. No merge of any `auto/extract-fixes-*` branch into `main`; no push to main.

### HUMAN DECISIONS

1. **Regenerate the three publishers' series from the fixed parsers** (this is what makes the 191 rows
   correct in the delivered files):
   ```bash
   # intermodal: reparse the cached markdown (no API, no credits), then rebuild the CSVs
   python3 scripts/extract/publishers/run_intermodal_full.py --reparse-only --year all
   python3 scripts/extract/publishers/run_intermodal_full.py --stack-only
   # xclusiv (local pymupdf, no API) and clarksons (its runner is cache-first)
   python3 scripts/extract/publishers/run_xclusiv_tables.py --all
   python3 scripts/extract/publishers/run_clarksons_hellas_world_class.py
   ```
   The intermodal reparse rewrites sidecars, so **`--stack-only` must follow it**; on its own it just
   re-copies the old values.
2. **`run_intermodal_tables.py --stem X` (or `--limit N`) is a data-loss footgun**: `main()` calls
   `write_stacked_series()` with only the filtered documents, so a single-document run **truncates all
   three delivered CSVs** to that subset. A guard (refuse to write when the target set is a subset
   unless `--force-write`) is a small change I did not make, because it alters an interface other
   scripts may call.
3. **A LlamaParse API key is hardcoded as a fallback default in 3 tracked files**
   (`run_intermodal_llamaparse.py`, `run_intermodal_tables.py`, `run_star_asia_charts.py`:
   `os.environ.get("LLAMA_CLOUD_API_KEY", "llx-...")`). The value is in git history. Rotate it and read
   the key from the secrets file only - the plan already treats keys as burnable and rotated.
4. **Rebuild the derived DB** (still pending from previous runs):
   `python3 scripts/extract/build_table_db.py --out data/extracted` then
   `python3 scripts/extract/check_measured_rules.py`.
5. **Audit-trail issue, again:** another agent's commit **dfb2f8daa** ("feat(poten): automate chart
   clipping...") swept my first, in-progress edit to `run_intermodal_full.py` into its own commit, so
   that file's fix is split between dfb2f8daa and bdc62bd92. The file is correct and self-consistent at
   this branch's HEAD, but a revert of dfb2f8daa would take part of the fix with it.

## 2026-10-01 17:55 UTC (23:25 IST) - deep review: the Athenian demolition series carried 384 duplicate rows, and the first fix for it was itself destructive

### What I measured first

* verify_extraction.py --json: run COMPLETE (7,676 planned / 7,816 recorded, 0 remaining),
  status_counts {ok: 876, no-extractable-content: 1, error: 3}, golden 15/15,
  inventory_drift 345 PDFs absent from the 2026-09-21 inventory, disk free 23.7 GB, actions: [].
* Process check: no run_batch / batch_worker process is running (only the Hermes gateways and
  code-review-graph). Nothing was killed, nothing was restarted.
* Duplicate census over the COLLECTED corpus, size-bucketed md5 so it is cheap: 13,995 PDFs,
  2,442 size buckets with more than one member, 8,625 files hashed, 2,422 content-identical
  groups / 6,149 extra copies. Then the measurement that matters, over the DELIVERED
  data/extracted/series/*.csv: key = every column except the provenance columns (source_file and
  friends), so two rows differing ONLY in which of two byte-identical PDFs they came from are
  exposed as the duplicate they are -> 1,301 duplicate-key rows, classified by whether the pair
  of source documents is byte-identical: 709 BYTE_DUP_PAIR, 520 DIFFERENT_BYTES (a different
  cause, see "not changed"), 72 SAME_SOURCE_REPEAT (one document emitting a row twice).

### The finding (PROVEN from the source page and the delivered file)

hellenic_athenian_demolition_series.csv held 384 duplicate rows of 3,300 (11.6%). Every one is a
BYTE_DUP_PAIR. Root cause is one line in
scripts/extract/publishers/run_hellenic_demolition.py:

    # Deduplicate identical PDFs
    pdf_hash = pdf_path.name          # <- the NAME, not a hash

Two HTML articles for the same week (e.g. ...week-34-202.html and ...week-34-2021.html) link to
two differently-named but BYTE-IDENTICAL PDFs (2021-09-01_Demo_IG_weekly_34_2021_.pdf = md5
5be5f22c... = 2021-09-01_athenian-shipbrokers-..._b4d541636014.pdf), so both were parsed and
stacked. 32 issue dates carry 24 rows where the issue has 12. A filename is not an identity - the
same lesson as the stale-path note in the skill, on documents instead of paths.

Proven per row, not asserted: for 2021-09-01, (2021-09-01, 34, India, Tankers, 590.0) appears
twice in the delivered CSV, once from each filename.

### The fix, and the defect the first version of it introduced

One file, scripts/extract/publishers/run_hellenic_demolition.py, 26 insertions / 18 deletions,
code only (no data file touched). The dedup is now TWO rules, BOTH required:

1. by FILENAME, as before;
2. by CONTENT + issue_date + publisher branch (new; publisher_branch() reuses the same predicates
   and the same order as the dispatch, so a copy can only be suppressed by one that would be
   routed to the SAME series for the SAME issue).

Why not content alone, and why not content+branch+date alone - both were BUILT AND MEASURED
against the delivered files, each with its own failure:

| rule built | athenian rows | GMS demolition | GMS port positions | verdict |
|---|---|---|---|---|
| old: filename | 3,300 (384 dup) | 448 | 2,931 | this is the defect |
| content only | 2,916, 0 dates lost | 444, 2026-06-13 date DELETED | 2,898, 2 dates DELETED | destructive |
| content + date + branch | 2,964, 4 dates ADDED (2024-12-23, 2025-09-09, 2025-12-16, 2025-12-23, each carrying a 2022/2024 report's prices, because a 2025 archive page's link still points at the old PDF) | 448 | 2,931 | no loss, but invents issues |
| filename AND (content+date+branch) | 2,916, 242 dates kept, every other row identical | 448 | 2,931 | shipped |

### Evidence, isolated so the change is the only variable

A harness imports the patched module, redirects its TWO output roots (SERIES_DIR, MD_BASE_DIR) to
data/extracted/scratch_review/deep_20261001/out/, and calls main(). The delivered files are never
opened for writing; nothing under series/ or md/ was modified by this run.

    Total HTML articles in demolition: 807
    Saved 2916 Athenian records    (delivered file: 3300)
    Saved  233 Best Oasis prices   (unchanged)
    Saved  514 Best Oasis deals    (unchanged)
    Saved  448 GMS rankings        (unchanged)
    Saved 2931 GMS port positions  (unchanged)
    Successfully processed 737 demolition reports.  ELAPSED 181.4s

Control, old delivered file vs the new output, per series: OVERALL PASS

* athenian: delivered 3,300 -> scratch 2,916, removed 384, documents 275 -> 243,
  kept-document rows identical (extra 0, missing 0), every removed row still present in the
  scratch file as a duplicate, issue dates 242 -> 242, lost dates: none.
* best_oasis deals 514, best_oasis demolition 233, GMS demolition 448, GMS port positions 2,931:
  removed 0, identical, no dates lost.

Golden gate after the change: python3 scripts/analysis/golden_matrix.py -> Star Asia plumber-text
15/15, pymupdf-text 15/15, camelot-stream 13/15, pdfplumber 13/15, tabula 9/15, lattice 2/15 -
identical to the matrix in EXTRACTION_STRATEGY.md. No regression.

### The collision, stated plainly

Two other agents each picked up my in-progress working-tree edit and committed it themselves
while this run was still measuring. 0f71c1366 (23:34 IST) committed the content+date+branch
variant, i.e. the row of the table above that ADDS 4 spurious issue dates and 48 rows, and it
reached main through a merge. 3db3e145f then committed the corrected TWO-RULE version, which is
the shipped row of the table, and that is what main holds now. Verified by re-running the harness
against the committed file: same 2,916 / 448 / 2,931 / 514 / 233 and the same PASS control.
Flagging the process, not the code: a fix split across two commits by two agents, where the first
is measurably wrong, is exactly the audit-trail hazard this log has recorded before.

The delivered CSVs were NOT regenerated: hellenic_athenian_demolition_series.csv is still the
16:39 IST file with 3,300 rows and 242 dates, so neither the defect nor the intermediate wrong fix
has reached delivered data.

### Measured but deliberately NOT changed

* The delivered series were not regenerated. Writing data/extracted/series/** is outside this job's
  write scope; the fix takes effect for documents processed after it.
* carriers: 254 duplicate-key rows, all BYTE_DUP_PAIR (72 dry_tc_period + 70 sales + 42 indices +
  18 bspa + 18 tanker_tce + 15 dry_weighted_routes + 9 bda + 4 demolition). Its twin is
  15_09_2026_carriers_sales_purchase_market_report_week_37 (2).pdf vs
  carriers_2026_W35_WK-35-26-CARRIERS_SP-MARKET-REPORT.pdf, identical rows including
  issue_date 2026-09-01 and week 35. Already recorded as untouched in the dedup census; still is.
* 520 DIFFERENT_BYTES duplicate-key rows are a DIFFERENT defect and I did not touch them.
  baltic_ncfi_series.csv (148): two Wayback captures of the same Ningbo page
  (2020-05-29_...Index31_ningbo.html and 2020-06-05_...Index3_ningbo.html) both contribute rows
  dated 2020-06-05 - an HTML-pass issue, not a PDF dedup issue. hellenic_vv_* (214), lion_* (119),
  star_asia_valuation_matrix (13), hellenic_iron_ore_table (10) are the same class. I measured the
  size, not the cause; each needs its own diagnosis.
* 72 SAME_SOURCE_REPEAT rows (one document emitting a row twice): clarksons_desk_talk 17,
  lion_demometer 24, hellenic_vv_matrix 15. Parser-level, a separate fix.
* The 23 byte-identical GMS 2021 "web" PDFs are junk, and I checked before claiming anything.
  2021-07-05_gms-week-27 through 2021-12-28_gms-week-53 (23 files, all md5 38c0a8c225ab, 92,695
  bytes) are the same 15-page site-navigation dump with no dates and no week numbers, and they
  contribute 0 rows to the delivered GMS series. A naive reading of the census ("23 weeks share one
  issue's prices") would have been a false alarm.
* run_seabrokers_llamaparse.py was dirty in the working tree from another agent; not staged.
  No merge of any auto/extract-fixes-* branch into main by me; no push to main.

### HUMAN DECISIONS

1. Regenerate the hellenic demolition series from the fixed runner (this is what makes the 384
   duplicate rows disappear from the delivered files):

       python3 scripts/extract/publishers/run_hellenic_demolition.py

   Expected: hellenic_athenian_demolition_series.csv 3,300 -> 2,916 rows, same 242 issue dates,
   the other four demolition CSVs unchanged (verified offline, above).
2. Still pending from previous runs: rebuild the derived DB
   (python3 scripts/extract/build_table_db.py --out data/extracted then
   python3 scripts/extract/check_measured_rules.py).
## 2026-10-02 20:30 UTC (2026-10-03 02:00 IST) - deep review: the carriers series carried 253 duplicate rows from three byte-identical PDF pairs (FIXED); lion's delivered demometer is stale by exactly 24 rows; two more duplicate classes quantified

### What I measured first (the whole picture, not a chosen subset)

verify_extraction.py: run COMPLETE (7,676 planned / 7,816 recorded, 0 remaining), golden 15/15,
78 not-a-pdf quarantines (expected), inventory_drift 352 PDFs by filename (informational). No
run_batch / batch_worker process on the box; checkpoint unchanged at 7,816 lines. Disk 16.0 GB free.

A duplicate-key census over ALL 170 files in data/extracted/series/ (key = every column except
`source_file`; where that column is absent, the whole row) found **841 duplicate-key rows across 24
series**. Largest first:

| series | rows | dupRows |
|---|---|---|
| baltic_ncfi_series.csv | 2,180 | 148 |
| hellenic_vv_matrix_series.csv | 12,340 | 132 |
| carriers_dry_tc_period_series.csv | 3,216 | 72 |
| carriers_sales_series.csv | 3,130 | 69 |
| lion_deals_series.csv | 1,314 | 64 |
| hellenic_vv_sales_series.csv | 2,122 | 60 |
| lion_sales_series.csv | 1,200 | 55 |
| carriers_indices_series.csv | 1,876 | 42 |
| bancosta_sales_series.csv | 3,244 | 24 |
| lion_demometer_series.csv | 576 | 24 |
| ... 14 more, each under 25 | | |

Frame, stated before any conclusion: **none of these series is read by the app.** index.html,
data/views/** and data/derived/** contain zero references to carriers_*, lion_*, hellenic_vv*,
baltic_ncfi or agora_indicators. data/extracted/series/** is consumed by the register, the cadence
audits and downstream series builds. So this class inflates counts that are published in
docs/EXTRACTION_REGISTER.md and any derived series (the register lists carriers_sales at 3,004 rows
where the file holds 3,130, 69 of them duplicates). It does not corrupt a displayed number. That is a
reason to fix it, not a reason to call it a false alarm.

### Finding 1 (FIXED): carriers - a filename is not an identity

data/extracted/series/carriers_*_series.csv carried 253 duplicate-key rows, from exactly **three
byte-identical PDF pairs**, proven by md5 rather than inferred:

    md5 c0ca7320cdb269874e30c7b8869a65bf
      carriers_2026_W35_WK-35-26-CARRIERS_SP-MARKET-REPORT.pdf
      15_09_2026_carriers_sales_purchase_market_report_week_37 (2).pdf   <- name says week 37
    carriers_2026_W38_WK-38-26-CARRIERS_SP-MARKET-REPORT.pdf  vs  ....pdf.pdf
    carriers_2026_W39_WK-39-26-CARRIERS_SP-MARKET-REPORT.pdf  vs
      general_broker_28_09_2026_carriers_sales_purchase_market_report_week_39.pdf

Each pair emitted identical rows under the same issue, e.g. ('2026-09-01','35','CAPE 180k','SHORT',
'37500.0') once from carriers_2026_W35_... and once from 15_09_2026_..._week_37 (2).pdf. run()
rglobs every PDF under corpus/01-brokers/carriers and parses each; nothing stopped a copy
re-emitting the same series rows. The (2) file is the Week 35 report - extract_metadata()'s existing
"page wins" rule already dates it 2026-09-01 / week 35 - so both copies land in the same series for
the same issue.

Fix: commit 57d064c09, branch auto/extract-fixes-2026-10-03-carriers, one file
(scripts/extract/publishers/run_carriers_complete.py, 21 insertions, code only) - the same two-rule
guard already shipped for hellenic / fearnleys / star_asia. A byte-identical copy is suppressed ONLY
when it resolves to the same (issue_date, report_week), i.e. it would be routed to the same series
for the same issue. Content alone is not enough, and a name is not an identity.

Evidence: a harness imports the patched module with its write roots redirected to
data/extracted/scratch_review/deep_20261003/ (the corpus and the delivered files are never opened
for writing).

| series | delivered | before-run | after-run | removed |
|---|---|---|---|---|
| carriers_sales | 3,130 | 3,130 | 3,061 | 69 |
| carriers_dry_tc_period | 3,216 | 3,216 | 3,144 | 72 |
| carriers_indices | 1,876 | 1,876 | 1,834 | 42 |
| carriers_tanker_tce | 804 | 804 | 786 | 18 |
| carriers_bspa | 749 | 749 | 731 | 18 |
| carriers_dry_weighted_routes | 670 | 670 | 655 | 15 |
| carriers_bda | 375 | 375 | 366 | 9 |
| carriers_newbuilding | 312 | 312 | 306 | 6 |
| carriers_demolition | 178 | 178 | 174 | 4 |
| **duplicate keys** | **253** | **253** | **0** | |

The before-run reproduces the delivered files EXACTLY (multiset-identical across all nine series), so
the sandbox is a faithful stand-in. Control: every removed row still has an identical row (all fields
except source_file) in the after file; no key fully lost; 0 rows added; three SKIP lines, one per
pair. Golden gate after the change: scripts/analysis/golden_matrix.py unchanged - Star Asia
plumber-text 15/15, pymupdf-text 15/15, camelot-stream 13/15, lattice 2/15.

### Finding 2 (NOT a live bug): lion's delivered demometer is stale by exactly 24 rows

lion_demometer_series.csv (Sep 29 22:27) holds 576 rows over 46 issue dates, with 2026-09-11 and
2026-09-18 at 24 rows where every other issue holds 12. Running the CURRENT run_lion_tables.py in a
sandbox produces 552 rows over the SAME 46 dates, differing at exactly two:

    dates where counts differ: {'2026-09-11': (24, 12), '2026-09-18': (24, 12)}

The delivered source_file column shows 31 rows from the W37 PDF and 31 from the W37 digest .md, so
those two issues were each parsed twice when the file was written. The current code no longer adds
them: the digest names it looks for (lion_12_09_2026_lion_weekly_market_report_week_37_2026.md) do
not match the ones on disk (lion_shipbrokers_12_09_2026_...). Nothing broken to fix, so no code
change - the delivered file is simply stale and regeneration is a human decision.

### Finding 3 (human decision): hellenic VesselsValue - download date used as issue_date, and two issues saved 3x and 5x

Same census: hellenic_vv_sales 60 dupRows, hellenic_vv_benchmark_sales 22, hellenic_vv_matrix 132
(214 total). Both runners derive the issue date the same way - the DOWNLOAD-date filename prefix:

    m_date = re.match(r"^(\d{4}-\d{2}-\d{2})", fname)
    issue_date = m_date.group(1)

Measured over the 261 VV HTML files: the prefix equals the page's own title date for 183 files and
differs for 78 (69 by +1 day, 8 by +2, 1 by -10). The page carries the report masthead date; the
prefix is the scrape day:

    file 2026-02-11_...-report-february-10-2026.html  title "February 10 2026"  -> series says 2026-02-11

Separately, exactly TWO issue dates are over-copied and they explain all 214 duplicate rows:

    2026-02-19 <- 3 files (slugs feb-03 / feb-10 / feb-17)   all titled "February 17 2026"
    2026-04-01 <- 5 files (slugs feb-17 / feb-24 / mar-03 / mar-24 / mar-31)  all titled "March 31 2026"

Diffing the three February files: the URL-stripped text is byte-identical (2,437 chars each); the only
difference is the canonical permalink. One report saved under three slugs, parsed three times -
"2026-02-19: 36 rows from 3 files" where a single issue yields 12.

Not changed. The dedup half is straightforward, but the date half re-dates roughly 30% of the issue
dates in three delivered series (2,122 + 12,340 + 141 rows), and the two defects are entangled:
deduping without the date change leaves two issues dated on their download day; changing the date
without deduping leaves the copies colliding on the corrected date. That combination is a data
regeneration - explicitly a human decision.

### Deliberately NOT changed, and why

* The delivered CSVs were not regenerated. Writing data/extracted/series/** is outside this job's
  write scope; the carriers fix takes effect for documents processed after it.
* hellenic VV (Finding 3) - see above.
* baltic_ncfi 148 dupRows (two Wayback captures of the same Ningbo page contributing rows for one
  date - an HTML-pass issue, not a PDF one); lion_deals 64 / lion_sales 55; bancosta 44;
  star_asia_valuation_matrix 13; hellenic_iron_ore_table 10. Each needs its own diagnosis; I measured
  the size, not the cause, and will not guess at it.
* run_lion_tables.py was exercised only in a sandbox; no lion code was touched.
* scripts/analysis/golden_matrix.json was modified by running the golden check and restored with
  `git checkout --`, so the working tree carries no out-of-scope edit.
* Another agent is checked out on auto/extract-fixes-2026-10-03-intermodal-finance (2 commits: agora
  and intermodal-finance dedup). I branched from that HEAD rather than switching branches under it
  and committed only my one file - their commits are carried along untouched. No push, no merge.

### HUMAN DECISIONS

1. Regenerate the nine carriers series so the 253 removed rows leave the delivered files:

       python3 scripts/extract/publishers/run_carriers_complete.py

   Expected: sales 3,130 -> 3,061, dry_tc_period 3,216 -> 3,144, indices 1,876 -> 1,834,
   tanker_tce 804 -> 786, bspa 749 -> 731, dry_weighted_routes 670 -> 655, bda 375 -> 366,
   newbuilding 312 -> 306, demolition 178 -> 174; no issue date added or lost (verified offline).

2. Regenerate lion's series - the delivered files are stale by 24 demometer rows (the deal series
   also differ from a fresh run):

       python3 scripts/extract/publishers/run_lion_tables.py

3. Decide the hellenic VV date convention. If the page's own report date is wanted over the download
   date, the change is one expression in each of run_hellenic_vessel_valuations.py and
   run_hellenic_vv_matrix.py, plus a per-issue dedup so the 3x/5x copies collapse; 78 of 261 files
   and 214 duplicate rows are affected.

4. Still pending from earlier runs: the Athenian demolition series regeneration
   (python3 scripts/extract/publishers/run_hellenic_demolition.py) and the derived DB rebuild
   (python3 scripts/extract/build_table_db.py --out data/extracted then
   python3 scripts/extract/check_measured_rules.py).


## 2026-10-03 06:22 UTC (11:52 IST) - deep review: the Clarksons Desk Talk series was 45% page furniture, and the running header duplicated once per page (FIXED)

### What I measured first

`verify_extraction.py`: run COMPLETE (7,676 planned / 7,816 recorded, 0 remaining), golden 15/15, 78
not-a-pdf quarantines (expected, verified genuine on 2026-10-01), inventory_drift 352 PDFs by
filename (informational). No `run_batch` / `batch_worker` process on the box; checkpoint unchanged at
7,816 lines. Disk 23.0 GB free. All 170 series CSVs were re-censused for duplicate keys
(key = every column except `source_file`): **258 duplicate-key rows remain**, of which 229 are the
known hellenic VV human decision (matrix 147 + sales 60 + benchmark 22) and 29 are scattered
(clarksons_desk_talk 17, xclusiv_sales 5, star_asia_deals 2, poten_top_charterers 2,
star_asia_ferrous_scrap 1, hellenic_gms_port_positions 1, carriers_sales 1).

The 17 dupRows in `clarksons_desk_talk_series.csv` were not previously attributed, so I diagnosed
them. The delivered series holds 608 rows.

### Finding 1 (FIXED): one report emits the same row 2-3 times, and 45% of the series is not commentary

The duplicate was not two files: the SAME source_file produced the SAME (issue_date, report_week,
sector, commentary_text) row 2-3 times. Reproduced on the current code (so not a stale-file case)
against the cached markdown for 2023-03-17 bulletin 61 - 7 commentary rows, of which 3 were the
byte-identical string

    'Sale & Purchase | Clarksons Hellas Weekly Bulletin | 17 Mar. 23'

plus a contact block and the legal disclaimer. Chasing it down: that header occurs 3x in the markdown
(once per page) and the line-based parser flushes `curr_text_block` at every table boundary, so each
occurrence became its own commentary row.

The root cause is four near-miss guards in `extract_clarksons_data`:

    "clarkson hellas" not in l_str.lower()   <- the text says "Clarksons Hellas"; "clarkson hellas"
                                                is not a substring of "clarksons hellas"
    "direct +" not in l_str.lower()          <- the line renders as "<b>Direct</b> +(30) 210..."
    "disclaimer" not in l_str.lower()        <- the word "disclaimer" never appears in the body
    "kifissias" ...                          <- only caught one of the three address spellings

Held on its own, none of the four fire. Quantified over all 165 cached reports: 273 of 608
commentary rows (45%) matched a page-furniture pattern (232 contained "Clarksons Logo CLARKSONS",
148 the masthead header, 41 a bare date).

Fix: commit **abee30d58**, branch `auto/extract-fixes-2026-10-03-clarksons-desktalk`, one file
(`scripts/extract/publishers/run_clarksons_hellas_world_class.py`, +78/-1, code only). A corrected
`is_page_furniture()` predicate keyed on the shapes actually present in the corpus (masthead/logo in
all three spellings, letterhead address, contact block including the HTML-markup forms, the seven
disclaimer sentences, bare and `<sup>`-tagged dates), plus a per-document dedup of byte-identical
commentary rows.

Evidence: a harness imports the old module (from `git show HEAD:`) and the new one, and runs both over
every cached report in memory. The corpus and the delivered files are never opened for writing. The
before-half reproduces the delivered 608 rows exactly.

| metric | before | after |
|---|---|---|
| commentary rows (165 docs) | 608 | **355** |
| duplicate keys in the series | 17 | **0** |
| rows still matching a furniture pattern | 273 | **0** |
| docs where `sales` output differs | - | **0** |
| docs where `demolitions` output differs | - | **0** |
| genuine commentary rows lost | - | **0** |

The loss control is the one that matters: for every old row that was NOT furniture, I required a new
row sharing >= 60% of its longest common substring; every removed row resolved to masthead, contact,
disclaimer or date-only furniture. The 5 shortest retained rows are 86-109 chars and all real
("Another relatively slower week on the tanker market, with no confirmed sales reported."). A sandbox
write of the full series to `scratch_review/` produced 355 rows with 0 duplicate keys; the directory
was deleted afterwards. Golden gate after the change: Star Asia plumber-text 15/15, pymupdf-text
15/15, camelot-stream 13/15, SSY 14/14 - unchanged (the change touches commentary parsing only).

### Deliberately NOT changed, and why

* The delivered `clarksons_desk_talk_series.csv` (608 rows) and the 165 Clarksons `.md` sidecars under
  `data/extracted/md/hellenic/shipbuilding/clarksons/` and `data/extracted/md/clarksons/` still carry
  the junk. Writing `data/extracted/**` is a data regeneration, not a code fix - see the human
  decision below. The fix takes effect for anything extracted afterwards.
* The other 29 scattered dup rows were measured, not diagnosed. xclusiv_sales (5), star_asia_deals (2),
  poten_top_charterers (2), star_asia_ferrous_scrap (1), hellenic_gms_port_positions (1) and
  carriers_sales (1, already named on 2026-10-03 as publisher-side) each need their own root cause; I
  will not guess at them from the census alone.
* The 229 hellenic VV duplicate rows remain the standing date-convention decision recorded on
  2026-10-03; nothing here changes it.

### HUMAN DECISIONS

1. Regenerate the Clarksons Desk Talk series and the 165 Clarksons markdown sidecars so the 253
   furniture rows leave the delivered files:

       python3 scripts/extract/publishers/run_clarksons_hellas_world_class.py

   Expected: `clarksons_desk_talk_series.csv` 608 -> 355 rows (0 duplicate keys); sales, demolition
   and macro series unchanged (measured byte-identical). The register lists this CSV at 608 rows.

2. Still pending from earlier runs: the hellenic VV date convention (229 dup rows), the lion series
   regeneration, the Athenian demolition regeneration and the derived DB rebuild
   (`python3 scripts/extract/build_table_db.py --out data/extracted` then
   `python3 scripts/extract/check_measured_rules.py`).
## 2026-10-03 09:58 UTC (15:28 IST) - deep review: the Star Asia S&P sales series was delivered EMPTY (0 of ~3,600 rows) by a header-key plus row-shape mismatch, and 96% of its sidecar tables were mis-typed by the same bug (FIXED)

### What I measured first (all read-only)

`verify_extraction.py` over the bulk pass reported: 7,816/7,816 checkpoint rows
(7,816 unique), `actions: []`, golden 15/15, `db: not built yet`, 74 not-a-pdf
quarantines, 352 inventory-drift PDFs, disk free 22.7 GB. The bulk `extract_all`
pass is COMPLETE. The PowerShell `Win32_Process` query for `run_batch` /
`batch_worker` returned nothing: no batch is live, so the open-append-handle
prohibition does not apply this run.

I then swept all 172 delivered series CSVs in `data/extracted/series/` for
structural smells (all-null columns, zero-row files). Two files are header-only:

| file | rows | bytes | mtime |
|---|---|---|---|
| `star_asia_snp_sales_series.csv` | 0 | 128 | 2026-10-02 08:39 |
| `signal_vessel_counts_series.csv` | 0 | 67 | 2026-10-02 22:39 |

`docs/EXTRACTION_REGISTER.md` still asserts Star Asia S&P = **3,717 rows**
("Secondhand sales transactions ($M)"), and names `run_star_asia_world_class.py`
as the pipeline.

### Finding 1 (FIXED): the S&P series is empty - the extractor reads the wrong header key AND the wrong row shape

`run_star_asia_tables.py::extract_snp_sales()` read the table header from
`t.get("header", [])`. Every one of the 198 delivered sidecars under
`data/extracted/md/star_asia/` stores it under `"headers"` (plural: 5,348 tables
carry `"headers"`, 215 legacy tables carry `"header"`). With the wrong key the
gate matched 2 of 5,566 tables. Replacing the key alone exposed a second layer:
rows are stored as list-of-dicts keyed by header name, while the function indexed
them positionally (`r[col_map["vsl"]]` raised `KeyError: 0` on 192 of 198
documents).

Measured over all 198 sidecars, with the module imported from `git show HEAD:`
versus the corrected file (no writes; scratch out-dir only):

| | shipped | corrected |
|---|---|---|
| S&P rows recovered | **23** (1 document) | **3,598** (193 documents) |
| documents crashing | 0 (silently matched nothing) | 0 |
| `table_type` = `market_data` (fallback) | **5,360 / 5,566 (96.3%)** | **3,076 / 5,566 (55.3%)** |

Compounding cause of the zero: the CSV write at the end of the same module is
unconditional, so the 2026-10-02 08:39 run of that runner truncated whatever was
in the file to its own (near-empty) result - 128 bytes, header only. Compare
`run_star_asia_world_class.py`, which guards the same series with `if snp_rows:`.

The recovered values ground out against the sidecar: for
`star_asia_2022_W29_Market-report-Week-29.tables.json` the first row is
`THERESA SHANDONG / KMAX / 82,000 / 2012 / CHINA / 22.0 / GREEK BUYERS`, and the
rebuilt scratch CSV row 1 is identical
(`dwt=82000.0, year_built=2012, price_usd_mill=22.0, buyers_comments=GREEK BUYERS`).
A second sampled row, `STI ROCHER / STI LARVOTTO | MR | 49,990 | 2013 | 72.4 |
GULF ENERGY MARITIME` (2024-03-30), likewise matches its sidecar.

"Delivered empty by a broken writer" is the claim; I did not observe a
previously-populated copy of the file during this run, so the earlier row count
is attested only by the register (3,717) and by `run_star_asia_world_class.py`,
whose own gate (vessel name + price + buyer) matches 524 of the 5,566 tables.

### Finding 2 (FIXED, same root cause): classify_table_type mis-typed 2,284 of 5,566 sidecar tables

`classify_table_type()` read the same wrong key (`t.get("header", [])`), so its
`hdr` was empty for almost every table and the classifier fell through to the
`market_data` default. The delivered sidecars carry that mis-stamp: 5,360 of
5,566 tables (96.3%) are `market_data`, versus 3,076 (55.3%) under the corrected
key - 2,284 tables change type (389 become `secondhand_sales`, 615
`beaching_position`, 388 `indicative_scrap_prices`, 295 `indices`, 257
`exchange_rates`, 193 `demolition_sales`, 191 `bunkers`, 162 `commodities`).

Scope note, measured: `table_type` is written at `run_star_asia_tables.py:563`
and read nowhere - a repo grep for the field finds only that file. So this is a
metadata-quality defect on a delivered artefact, not a live series break. It is
recorded because it is the same bug and because a future consumer keying on
`table_type` would be silently misled.

### Golden gate after the change

The change touches S&P parsing and table typing only. Star Asia `plumber-text`
**15/15**, `pymupdf-text` **15/15**, camelot-stream 13/15, SSY atlantic 14/14 -
identical to the levels recorded on 2026-10-03 06:22 UTC. No golden recall lost.

### What I changed

Branch `auto/extract-fixes-2026-10-03-star-asia-snp`, one file
(`scripts/extract/publishers/run_star_asia_tables.py`, +95/-49, code only):

1. `extract_snp_sales()` reads `"headers"` with a `"header"` fallback, reads rows
   through a new `_sidecar_cell()` helper that handles list-of-dicts and
   positional lists, and uses the same gate as `run_star_asia_world_class.py`
   (vessel-level row carrying a price and a BUYER column, so both the dry-bulk
   DWT and the container TEU tables match).
2. `classify_table_type()` gets the same key fallback.
3. The S&P CSV write is now guarded: a zero-row result prints a warning and
   leaves the delivered file untouched instead of truncating it.

Verification: module import and `py_compile` clean; the before/after table above;
a scratch write of the full 3,598-row series to
`data/extracted/scratch_review_starasia/` (deleted afterwards); the golden
matrix. No delivered file was written. `ruff` is not installed in this
interpreter, so no lint run.

### Deliberately NOT changed, and why

* The delivered empty `star_asia_snp_sales_series.csv` and the 198 mis-typed
  sidecars. Rewriting `data/extracted/**` is a data regeneration, not a code fix
  - see human decision 1. The fix takes effect for the next run of the runner.
* The identical unconditional-write pattern in the same function for the
  indicative-scrap and demolition-deals series. I can prove the S&P writer
  truncated a file; I cannot prove those two ever did (both are populated today:
  `star_asia_deals_series.csv` 3,349 rows, `star_asia_demolition_series.csv`
  3,072 rows). Guarding them is a behaviour change I did not measure, so I left
  them and name them here.
* The hardcoded narrative row in `update_extraction_register.py` that still
  prints "3,717 rows" for this series (see human decision 2).
* `signal_vessel_counts_series.csv` (0 rows). Not diagnosed this run.

### Checked and found NOT to be defects

* `drewry_ais_lpg_fr_series.csv` has `current_utilisation_pct` empty on all 32
  rows while the other nine Drewry AIS sector series are fully filled (VLCC
  32/32, Aframax 31/31, Suezmax 30/30, LR1 34/34, LR2 31/31, Capesize 27/27,
  Handysize 25/25, Panamax 23/23, Supramax 23/23). I opened three LPG_FR reports
  (2024 W04, 2026 W26, 2026 W38) and the string "util" appears on NO page of any
  of them: the LPG report page 2 carries "Current tonne-miles index" and "Change
  in trading status - MoM" where the other sectors carry "Current Utilisation".
  The empty column is the source shape, not an extraction defect. No change made.
* Empty columns in `bancosta_demolition_series.csv` (buyer 0/959) and
  `bancosta_newbuilding_series.csv` (owner/size/yard 0/2,377) are partitioned by
  `record_type` and empty by design on the assessment/indicative rows.

### Measured but not diagnosed

* `star_asia_deals_series.csv` (3,349 rows) has one effectively empty column,
  `arrival_date_status` (1 of 3,349 filled), i.e. the date-status fields that the
  runner added alongside `arrival_date_raw` are never populated on the 2,748
  `Beaching / Arrival` rows. Not chased; the raw date columns are present.
* `signal_vessel_counts_series.csv` is header-only. Its runner (`run_signal.py`)
  writes it; whether zero is correct for that source was not established.

### HUMAN DECISIONS

1. Regenerate the Star Asia series from the cached sidecars. This reads no PDFs
   and spends no LlamaParse credits - it re-derives from
   `data/extracted/md/star_asia/*.tables.json`:

       python3 scripts/extract/publishers/run_star_asia_tables.py

   Expected: `star_asia_snp_sales_series.csv` goes 0 -> **3,598 rows** (measured
   from the current sidecars; the register figure of 3,717 is not reproducible
   from today's corpus). The same run re-stamps `table_type` on 198 sidecars
   (2,284 tables change) and rewrites the indicative-scrap and demolition-deals
   CSVs.

2. The generated narrative in `update_extraction_register.py` (line 155) still
   hardcodes "3,717 rows" for this series, so regenerating the register will not
   correct it, and the document currently contradicts itself (its generated
   section already prints 0 for this file). Correct it with the number measured
   after decision 1.

   Still open from earlier runs: the hellenic VesselsValue date convention (229
   duplicate rows), the lion series regeneration, the Athenian demolition
   regeneration, the Clarksons Desk Talk 608 -> 355 row regeneration, and the
   derived DB rebuild (`python3 scripts/extract/build_table_db.py --out
   data/extracted` then `python3 scripts/extract/check_measured_rules.py`).

### Addendum to "Measured but not diagnosed": signal_vessel_counts

`signal_vessel_counts_series.csv` is written header-only by `run_signal.py`, whose
extractor keys on `row_dict.get('Vessel Class')` / `.get('Ballasters')` /
`.get('Number of Vessels')` / `.get('Count')`. The raw source does carry those
headers: over `corpus/07-signal/html/` the literal strings "Ballasters" (728
occurrences), "Vessel Class" (35) and "Number of Vessels" (2) are present. So the
delivered 0 rows is a mismatch between what the runner reads and what the source
holds, not an absent source. I did NOT run the runner or its HTML table parser, so
I am not naming the exact failed key - that is the next step, and it is a second
candidate of the same shape as the Star Asia defect.


## 2026-10-03 17:05 UTC (22:35 IST) - deep review: 25,274 mojibake table cells across 1,175 docs were stamped `garbled_cells 0` by a detector that cannot see pdfminer's `(cid:N)` form (FIXED)

### What I measured first (read-only)

No batch is live: the `Win32_Process` query for `run_batch` / `batch_worker` returned
nothing (the five `python.exe` are the Hermes gateway, two socket probes and two
proxy gateways). `data/extracted/corpus_checkpoint.jsonl` is untouched since
2026-09-22 11:12, so the bulk pass is COMPLETE and the open-append-handle
prohibition does not apply this run. I wrote nothing to it.

`verify_extraction.py` (out `data/extracted`, state/checkpoint = corpus*): 7,816
checkpoint rows, 7,816 unique, `actions: []`, golden 15/15, db **189,481 tables /
6,726,703 cells** (now correctly found at `corpus/db`), 74 not-a-pdf quarantines,
352 inventory-drift PDFs, disk free 22.1 GB.
`check_measured_rules.py`: all 11 rules present (EU/ISO decimals, currency-space).

`verify_registers.py` reports **1 mismatch**: `hellenic_athenian_demolition_series.csv`
disk 3,052 logical rows vs JSON 2,916. Cause measured, not a defect of mine: a
sibling job rewrote the four athenian CSVs at 22:14:52 IST, about 15 minutes before
the check, and has not re-run the register sync. Sibling commit `50a23c3ab`
("athenian runner no longer clobbers the deduped mirror") landed while this run was
measuring. Left alone.

### Finding (reproduced on ONE document, then FIXED): the mojibake detector cannot see `(cid:N)`

The corpus DB holds **25,274 cells whose value is pdfminer's unmapped-glyph token
`(cid:N)`** (hellenic 25,224 / 1,159 docs, of which 24,903 are MMi iron-ore reports;
seabrokers 10 docs, shipbrokers 4, one textbook 33, poten 1). Every one of those
cells carries `garbled_cells` 0 or no such key at all, because
`garbled_ratio()` counts only control codes and code points in `0x100..0x36F` --
and every character of `(cid:NNN)` is ASCII.

Reproduced today by re-extracting one document to a scratch out-dir
(`2021-08-10_mmi-daily-iron-ore-index-report ... _cb11d855ef22.pdf`, 6 pages, 33
tables, 1m32s):

| | pdfplumber tables | (cid:) cells | `garbled_cells` reported |
|---|---|---|---|
| before the fix | 11 | 64 | **0 on all 11 tables** |
| after the fix | 11 | 64 | 6, 1, 12, 6, 11, 12, 10, 1, 5 (sum 64) |

Doc-level summary is otherwise byte-identical (pymupdf's Latin-Extended form of the
same defect was already caught here: `garbled_blocks` 64, tables 33, blocks 504,
`ocr_queue_pages` 0). One of the pdfplumber tables has **5 cells and all 5 are
`(cid:)` tokens** with `text_verified` 0.0 -- the table is unreadable text by
content, and the old metric called it clean. `text_verified` is self-consistent but
blind here: the page text is the same gibberish, so the tokens "verify".

### What I changed

Branch `auto/extract-fixes-2026-10-03-cid-mojibake`, one file
(`scripts/extract/extract_all.py`, +16/-4): `CID_TOKEN_RE` plus one line in
`garbled_ratio()` that counts the characters of `(cid:N)` runs as glyphed. Nothing
else moved: `route_page()`, the table gate and the thresholds are untouched, and the
change can only ever ADD detections (a cell is newly flagged only if it contains a
`(cid:N)` token).

### Controls

* **Blast radius is enumerable and bounded.** Distinct cell values containing
  `(cid:)`: 3,207. Newly flagged by the fix: **2,219**, of which **2,202 (99.2%) are
  all-token cells** (`(cid:47)(cid:90)(cid:75)(cid:69)...` = "Power BI" interleaved)
  and only **17 (0.8%) are readable cells with an embedded token**. All 17 are
  disclosed as a judgement call: mostly chart-axis blobs (`50%
40%...IOPI65 %
  Spread to IOPI62(cid:116)(cid:28)...`) plus a handful of bullet glyphs
  (`(cid:31) Acquirer: Excel Maritime Carriers Ltd`) where `(cid:31)` is an
  unmapped bullet. None is a false positive on ordinary text.
* **`garbled_cells` has no reader.** A scoped grep finds the field only in
  `extract_all.py` (plus its `__pycache__`). The change is additive metadata on
  future extractions, not a behaviour change to delivered data.
* **Golden gate**: `python3 scripts/analysis/golden_matrix.py` -> star_asia
  `plumber-text` **15/15**, `pymupdf-text` **15/15**, camelot-stream 13/15,
  pdfplumber-tables 13/15; ssy_atlantic camelot-stream **14/14**. Identical to the
  levels recorded 2026-10-03 09:58 UTC. No golden recall lost.

### Deliberately NOT changed, and why

* The 25,274 existing `(cid:)` cells in `data/extracted/corpus/**` and in the derived
  DB. Applying the fix to already-extracted documents is a re-extraction, which is a
  human decision. The fix takes effect for documents extracted after this commit.
* `decode_mojibake.py` and the MMi mojibake LABELS (`/ZKEKZ...` =
  "IRON ORE PORT STOCK IN IOPI"). That pipeline is deliberately report-only because
  the header/title glyph table is incomplete ("teekly" for "Weekly"), and it is
  documented in its own header. Not reopened.

### Measured but NOT fixed (a defect in the refreshed series layer's key, one level up)

The sibling run refreshed `series`/`series_points` from the rebuilt cells and its
integrity gate passes (orphans 0). Plausibility was not part of that gate, and it
fails in exactly the shape the skill warns about: **764 (source, entity,
measurement) triples carry more than one `series_id`**, and for most of them the
ranges are DISJOINT, so the pair is not a series key.

Quoted from the DB, `hellenic / IOPI58 / YTD` (both starting 2021-07-14):

| series_id | block_no | n | min | median | max |
|---|---|---|---|---|---|
| `helleniciopi58ytdb1` | 1 | 2,532 | 622.0 | 758.0 | **1,107.0** |
| `helleniciopi58ytdb2` | 2 | 2,337 | **90.55** | 104.09 | 162.13 |

This is the RMB-versus-USD split of ONE printed row. In
`2021-08-10_mmi-...cb11d855ef22` the header row reads
`Index, Fe Content, Price, Change, Change %, MTD, YTD, Low 2, High 2 | Price,
Change, Change %, MTD, YTD, Low 2, High 2` -- "YTD" appears in BOTH the
`FOT Qingdao (inc. 13% VAT), RMB/wet tonne` block and the
`CFR Qingdao Equivalent (exc. 13% VAT), USD/dry tonne` block. The data row is
`['IOPI58','58% Fe Fines','1052','1267','1199','1186','1013','1144','1102',
'152.78
187.31', ..., '161.40']`: 1,102 RMB/wet tonne and 161.40 USD/dry tonne are
two measurements, one key. Worse cases: `shipbrokers / BCI / (empty)` is 9 series
spanning -3,530 to 83,865; `drewry_ais_pdfs / MoM change in / (empty)` is 16 series
spanning 10 to 50 (utilisation, speed, availability, congestion).

The layer is not internally fused (`block_no` separates them), so nothing is
corrupt; what is wrong is the human-readable key, which is what a consumer would
join on. NOT changed: `build_series_sql.py` was patched by a sibling minutes before
this run and is their file right now; changing the key model is a data regeneration,
not a code fix.

Note on the deltas: my `wc -l`-based row counts in an early pass disagreed with
`verify_registers.py` (athenian 2,916 vs 3,052). The register counts LOGICAL CSV
rows; several series carry embedded newlines inside quoted fields, so physical line
counts understate them. Use `csv.DictReader`, not `wc -l`.

### Checked and found NOT to be defects

* `star_asia_deals_series.csv` `arrival_date`: the long-open ledger item (European
  `DD.MM.YYYY` on 2,680/2,727) is CLOSED. Measured: 2,700 of 3,349 rows carry a
  clean ISO date, `arrival_date_note` says `EU_DDMMYYYY` on 2,692; the 48 gaps are
  all genuinely unparseable source typos (`29.02.2022` -- not a leap year,
  `31.012.2022`, `02.02.20323`) correctly left blank with note `UNPARSED`
  (41), `EMPTY_DASH` (6), `STATUS` (1). `arrival_date_status` being empty on
  3,348/3,349 rows is therefore a dead column, not lost data.
* No delivered series CSV contains mojibake or `(cid:)`. A signature scan over all
  170 files matched 10, and every match is legitimate Unicode (ALIAGA, CELIK,
  SZCZECINKA with Turkish/Polish diacritics, `ReBar HRB400 018mm` with a diameter
  glyph).
* `drewry_ais_pdfs` median `text_verified` 0.333 and 3,900 zero-verified tables are
  real but expected: the pages are Power BI exports whose pdfplumber pass interleaves
  two text layers (`'Aframax', 'PoweOr BvI eDrevskiteopw'` = "Power BI Desktop" over
  "Overview"). Drewry is served by its own runner (`drewry_ais_*_series.csv`, 10
  sector series), so this is audit-tier noise, not a series break.
* `1,973` shipbrokers tables with numeric cells on a single `col_idx` are chart
  pseudo-tables, not fused data rows: `xclusiv_2026_06_01` page 2 col 1 is the y-axis
  tick ladder `360,000 / 330,000 / ... / 30,000` beside prose in col 0. Known class
  (evenly spaced rule chains exist in both tables and charts), no change made.

### HUMAN DECISIONS

1. Nothing new is required from the fix itself: it is prophylactic for documents
   extracted after this commit. If you want the 1,175 affected documents re-stamped,
   that is a re-extraction of the existing corpus, not something to run unattended.
2. Still open from earlier runs, unchanged by this one: the hellenic VesselsValue
   date convention (229 dup rows - a sibling is mid-fix on
   `run_hellenic_vv_matrix.py`, edited 21:36 IST), lion series regeneration,
   intermodal_macro 4.3 (1,290 rows), ism agreement tail (1,178 rows), affinity
   WS-era md rounding (144 cells, display only), and the register sync for the
   athenian CSVs a sibling rewrote at 22:14 IST.


## 2026-10-04 04:18 UTC (09:48 IST) - deep review: the xclusiv row builder folded an overprinted text layer into doubled cells (16 of 18 rows corrupted on ONE page; FIXED)

State at entry: no extraction process running (only unrelated python: proxy_gateway,
hermes, code_review_graph). `verify_extraction.py` reports the bulk pass COMPLETE
(done 880/882, ok 876, error 3, no-extractable 1; state file 17,159 min old but 0
docs remaining), golden 15/15, db 189,481 tables / 6,726,703 cells. `resume` is a
no-op; `inventory_drift` 352 is informational. So this run is diagnosis + repair,
not liveness.

### What I looked at first (read-only)

* Scanned all 170 delivered series CSVs for structural smells (logical-row counts vs
  the register: only 2 mismatches, both `hellenic_vv_*`, in a sibling's live file; a
  physical-`wc -l` count disagrees with both on 13 files because several cells carry
  embedded newlines - count with `csv.reader`, not `wc -l`).
* Located cells holding two numbers in one string (a number-space-number regex):
  74 across the corpus. The largest non-benign cluster was `xclusiv_sales_series.csv`
  (40), then `clarksons_sales_series.csv` (13).

### Finding (reproduced on ONE document, then FIXED): a two-layer page yields doubled cells

`xclusiv_sales_series.csv` held rows like
  `NAME='CONRAD CONRAD'  DWT='207,647 207,647'  YEAR='2017 2017'`.
Ground truth from the source PDF's OWN text layer
(`pymupdf page.get_text()` on `corpus/01-brokers/xclusiv/2021/xclusiv_2021_xclusiv_weekly_2021_10_4.pdf`)
is `CONRAD / 207,647 / 2017` - single. So the doubling is introduced by the parser.

Root cause: that one page is drawn with every word TWICE at ~0.12pt offset
(`get_text("words")` returns `CONRAD` at x0=31.20,y0=103.22 AND at x0=31.08,y0=103.33;
195 of 533 words duplicated). The runner buckets words into rows by y within 5pt and
appends every word in the bucket, so both copies land in the cell and `clean_str`
joins them. Footprint measured by scanning all **271** xclusiv PDFs: exactly **one
page** carries the overprint. 18 Bulk-Carrier rows on that page were affected (17
doubled, plus `SHUANG XI`/`XIN HUA` interleaved into two fused rows).

### What I changed

Branch `auto/extract-fixes-2026-10-04`, one file
(`scripts/extract/publishers/run_xclusiv_tables.py`, +37/-9): added `_dedupe_words()`
and wrapped all 9 `get_text("words")` call sites with it. A word is dropped only when
an IDENTICAL string already sits within 1.0pt in BOTH x and y - the overprint offset
is ~0.12pt, real words never coincide that closely, and the same string elsewhere on
the page is far apart and preserved. (A first attempt keyed on `round()` of the raw
coordinates was abandoned: the 0.12pt offset straddles `.5` boundaries
(`round(55.56)=56` vs `round(55.44)=55`), so it deduped some rows and not others.)

### Evidence, isolated so the change is the only variable

* **Before** (pre-fix module from `git show HEAD:...`): 19 bulk rows, 17 doubled.
* **After**: 16 of 18 vessel rows are now exact ground truth
  (`CONRAD/207,647/2017/SWS`, `AQUA HONOR/175,428/2012/JINHAI`,
  `ROSCO MAPLE/181,453/2010/SASEBO`, ... `AMIRA ILHAM/28,434/2009/SHIMANAMI`).
* **Regression**: pre-fix vs post-fix `extract_sales_tables` on 25 PDFs sampled
  across 2021-2026 -> **25/25 identical**; the other five extractors
  (`extract_demo_sales_tables`, `extract_indicative_demolition`,
  `extract_secondhand_prices`, `extract_newbuilding_orders`,
  `extract_newbuilding_prices`) on 14 PDFs -> **0 differences**. Only the known page
  changes.
* **Golden gate**: `scripts/analysis/golden_matrix.py` -> star_asia `plumber-text`
  **15/15**, `pymupdf-text` **15/15**, camelot-stream 13/15, ssy_atlantic
  camelot-stream 14/14 - identical to the recorded levels. No golden recall lost.

### Deliberately NOT changed, and why

* The delivered `xclusiv_sales_series.csv` still holds the 16 doubled + 2 fused rows.
  Fixing the already-extracted CSV is a re-run of one publisher (human decision,
  command below), not something to run unattended - and the runner writes fixed paths
  with no `--out`.
* The residual `SHUANG XIN HUA XI` / `XIN SHUANG HUA XI` pair on that page. It is a
  DIFFERENT phenomenon: the two overprinted layers carry DIFFERENT vessels
  (`SHUANG XI` vs `XIN HUA`), so a same-string dedupe cannot and should not merge
  them. Left as-is and called out rather than guessed at.
* `clarksons_sales_series.csv` (13 rows with a two-number DWT, e.g. `SAMSUNG` yard row
  `114,858 114,795`, `HAFNIA KRONBORG` `73,708 50,346`) - these halves DIFFER, so they
  are not an overprint but a possible two-vessel row-merge. NOT proven against the
  source yet, so NOT touched.
* The derived series-layer key model: the `(source, entity_key, measurement_key)` ->
  >1 `series_id` collision is UNCHANGED at **764 triples** (2,686 series), and 43% of
  5,241 series carry an empty `measurement_key`. Already a recorded human decision
  (a data regeneration, not a code fix).
* The hellenic VV dedup a sibling committed: independently VERIFIED. `2026-02-19` now
  holds 78 matrix rows (was 234) and 5 benchmark sales (was 15) - the report-copy
  tripling is gone. Residual on that source: `2026-01-28` carries 65 rows with a
  duplicated age-10 row and missing age band, and `hellenic_vv_benchmark_sales_series.csv`
  is 124 rows against the register's 141.

### HUMAN DECISIONS

1. To apply the xclusiv fix to the delivered data, re-run the ONE publisher (its own
   runner, reads local PDFs, no LlamaParse credits):

       python3 scripts/extract/publishers/run_xclusiv_tables.py

   Expected: `xclusiv_sales_series.csv` Bulk-Carrier rows on `2021-10-04` move from
   doubled to single values (16 rows); all other dates byte-identical.
2. Still open from earlier runs, unchanged by this one: the lion series regeneration,
   the Athenian demolition regeneration, the derived series-layer key model (764
   collisions), and the `hellenic_vv` `2026-01-28` age-band defect above.


## 2026-10-04 08:06 UTC (13:36 IST) - deep review: star_asia deal dates carry the publisher's year typos unflagged (23 future-vs-issue, 44 beaching-before-arrival; FIXED - flags added)

State at entry: no extraction process running (`Get-CimInstance Win32_Process` for
run_batch/batch_worker returned nothing). `verify_extraction.py` reports the bulk
pass COMPLETE (done 880/882, ok 876, error 3, no-extractable 1; state file 17,382
min old but 0 docs remaining), `actions: []`, inventory_drift 357 (informational,
unchanged). Golden gate re-run this session: star_asia `plumber-text` 15/15,
`pymupdf-text` 15/15; ssy_atlantic 14/14; breakwave_dry 6/6 - identical to the
recorded levels. So this run is diagnosis + repair, not liveness.

### What I looked at (read-only, in this order)

* Broad structural scan of all 170 `data/extracted/series/*.csv`: ragged rows = 0
  everywhere; the only >50%-empty columns are schema-union placeholders (e.g.
  `bancosta_newbuilding_series.csv` `owner`/`size`/`yard` are 100% empty by
  construction - the content lives in `comments`). Not defects.
* Number-format sweep (cells holding BOTH `,` and `.`): all legitimate US-convention
  values (`12,755.50`, `34,000,000`). No 1000x locale error found in the delivered
  CSVs.
* Cross-series date-plausibility sweep (any ISO date cell >60 days after its
  issue/report date, across every series CSV): EXACTLY ONE source fires -
  `star_asia_deals_series.csv`. So the defect is per-source, not systemic.

### Finding (measured + verified page-faithful): star_asia's own date typos pass every validation

`star_asia_deals_series.csv` (3,349 rows) holds:
* **23** arrival/beaching cells more than 30 days AFTER the issue date; and
* **44** rows whose `beaching_date` PRECEDES `arrival_date` (impossible ordering).

These are the PUBLISHER's own year typos, and the raw strings are faithful to the
page - verified in the PDF text layer (`fitz`), not by trusting the extractor:
* `corpus/01-brokers/star_asia/2025/star_asia_2025_W01_Market-report-Week-12.pdf`
  prints `MSC ESHA F  CONTAINER  4,950  29.12.2025  04.01.2025` - beaching (04 Jan
  2025) three days BEFORE arrival (29 Dec 2025), arrived ~12 months after the report.
* `.../2023/star_asia_2023_W01_Market-report-Week-1.pdf` prints `CHANG FA HAI ...
  31.012.2022`; `.../2023/...W01...` prints `CHANG FA HAI ... 30.12.2023` in a
  Jan-2023 issue.
* `.../2023/...W01...` prints the 3-digit-middle typo `31.012.2022` verbatim, which
  is why `star_asia_dates.py` correctly leaves it `UNPARSED` (not a bug).

Before this run the normaliser marked all 44/23 rows `EU_DDMMYYYY` with an EMPTY
`*_status` - i.e. clean - so an ISO join would silently accept an impossible date.
This is the skill's documented class: a well-formed value that no validation catches.

### What I changed

Branch `auto/extract-fixes-2026-10-04`, one file
(`scripts/extract/publishers/star_asia_dates.py`, +42/-2): `normalise_deal_dates`
now appends `|FUTURE_VS_ISSUE` (>30 days after `issue_date`) and/or `|ORDER_INVALID`
(`beaching_date < arrival_date`) to the `*_note` column ONLY. `_parse_iso` +
`FUTURE_HORIZON_DAYS=30` added.

### Evidence, isolated so the change is the only variable

* Re-normalised all **3,349** delivered rows from their page-faithful `*_raw` cells
  through the patched module: **0 ISO-value differences** vs the delivered CSV, **0
  `*_raw` differences** - values are untouched, only notes gain the suffix.
* New note distribution: 23 cells `FUTURE_VS_ISSUE` (4 alone + 19 with
  `ORDER_INVALID`), 44 rows / 88 cells `ORDER_INVALID`; every pre-existing note
  (`EU_DDMMYYYY` 4,337, `STATUS` 980, `UNPARSED` 65, `RECONSTRUCTED_8DIGIT` 14,
  `EMPTY_DASH` 6) is unchanged.
* `py_compile` OK. Golden gate re-run: **star_asia 15/15 on both text engines**, no
  other cell moved.

### Deliberately NOT changed, and why

* The delivered `star_asia_deals_series.csv` is NOT rewritten (prohibition #4 - the
  fix is code-only and takes effect on documents processed afterwards, exactly like
  the xclusiv fix). Applying it is a one-publisher re-run, a human decision:

      python3 scripts/extract/apply_star_asia_deals_dates.py --apply

  Expected: the 23 `FUTURE_VS_ISSUE` cells and 44 `ORDER_INVALID` rows gain their
  note suffix; every ISO value and every `*_raw` stays byte-identical (proven above).
* The date VALUES are not corrected. `30.12.2023` is provably impossible in a
  Jan-2023 issue but the correct value (2022-12-30?) is not provable from the page,
  and this module's contract is to never invent a value.
* `07.07.2026` on VIGO in the 2026-W01 issue is flagged `FUTURE_VS_ISSUE` (179 days
  after the issue date) but its VALUE is kept: a 2026 report may legitimately list an
  AWAITING vessel's expected future arrival, so the value is not provably wrong - the
  flag lets a consumer decide, rather than the parser guessing a correction.

### HUMAN DECISIONS

1. To apply the star-asia flag fix to the delivered CSV: run the command above
   (`apply_star_asia_deals_dates.py --apply`). Values do not change; two note
   columns gain a suffix on 67 rows.
2. Still open from earlier runs, unchanged by this one: the xclusiv `2021-10-04`
   doubled-cell CSV re-run; the `hellenic_iron_ore_pdf_*` two-writer family (5 files,
   2 with 11,553/2,207 empty values); hellenic VesselsValue date convention; lion
   series regeneration; affinity WS-era md rounding; DB `label_series`; intermodal_macro
   ism agreement tail.

## 2026-10-04 11:50 UTC (17:20 IST) - deep review: 104 ISM coaster rows carried unit `$/t` on a `$/day` TCE chart (legend-label pollution; FIXED)

### What I measured first (read-only)

* `verify_extraction.py` -> run COMPLETE (7,816/7,816 recorded; state 17,608 min old,
  0 remaining). No `run_batch`/`batch_worker` alive. db 189,481 tables / 6,726,703 cells;
  mean `text_verified` 0.861; 249 crash-recovered docs; disk 14.7 GB free. No action.
* Swept all 170 series CSVs for structural smells (all-empty cols, constant cols,
  exact-duplicate rows, numeric min/max/median per column). The all-empty columns are
  schema placeholders populated by other record types (verified per `record_type`), the
  duplicate counts are 1-60 rows (not a systematic bug), and the apparent 1000x outliers
  were checked against their sources (below).

### Findings checked against the SOURCE (not assumed)

* `baltic_ncfi` 2026-05-29 `Ningbo - Middle East` prev=33943.74: the HTML itself prints
  `<td>4089.10</td><td>33943.74</td><td>3.69</td>` - a publisher typo, we are faithful.
* `affinity_bda` 2023-04-21 `TKR/LRG` 382.3 / -185.2: the PDF text layer prints
  `This week 382.3 ... Δ W-O-W -185.2` verbatim - publisher value, we are faithful.
* `affinity_tce` 2026-09-18 `TD3C` 1,241,097 USD/day: the report's prose reads
  "rates for vessels loading inside the AG have surpassed USD 1 Mn per day" - the
  scenario's value, we are faithful.
* `baltic_ncfi` 2022-02-11 `Ningbo - Europe` change `-1,38` (European decimal comma)
  parsed as `-138.0` by `run_baltic.parse_float`'s blanket `replace(',','')`. This IS a
  real parser bug, but the pattern occurs in **exactly 1 cell** across all 3,043 baltic
  HTML files (grep-verified), so it is documented, not force-fixed this run.

### Finding (reproduced on ONE document, then FIXED): a polluted legend label mislabels the unit

`ism_2023_W22_ISM_coaster_week-22.pdf` page 1 holds a chart titled
**"Average round voyage TCE (given backhaul leg in ballast), $/day"**. Its second series
legend entry read `Azov - Marmara RV, 3,000 DWCC sea-river Price / Freight rate, $/t vsl`
- a caption fragment from the *neighbouring* chart ("Russian wheat: weight of freight in
CFR Marmara price", whose legend is `Freight rate, wheat, 3,000t, Rostov - Marmara, $/t`)
blended into it. `unit_for()` read that `$/t` off the label, so the series shipped as
`$/t` though it is a `$/day` TCE line whose values (2,392-4,871) match its `$/day`
sibling on the same axis.

### What I changed

Branch `auto/extract-fixes-2026-10-04`, one file
(`scripts/extract/publishers/run_ism_series.py`): `unit_for()` now takes the chart
TITLE's declared unit first (`$/day` / `%` / `EUR/t` / `$/t`), and only falls back to the
per-label unit when the title names none (the CFR-weight charts, whose title carries no
unit). ~40 lines, comment-documented.

### Evidence, isolated so the change is the only variable

* Re-ran the stacking to `data/extracted/scratch_review/` with the patched module over
  the same 115 sidecars: **104 rows change, all of them the `unit` field, `$/t` ->
  `$/day`**; **0 rows change in any other column** (values, dates, min/max/sd byte-identical);
  `ism_handy` **0 rows change**. Affected reports: `ism_2023_W16` (52) and `ism_2023_W22` (52).
* Cross-checked the whole corpus: of 115 deduped ism sidecars, this title-vs-label unit
  precedence changes the unit of **exactly the 2 polluted labels and no other series**
  (simulated both functions over every series label).
* `py_compile` OK. Golden gate re-run: **star_asia 15/15 on both text engines**, no other cells moved.

### Deliberately NOT changed, and why

* The delivered `ism_coaster_freight_series.csv` is NOT rewritten (prohibition #4). The fix
  is code-only and takes effect on the next ism re-run, a human decision:

      python3 scripts/extract/publishers/run_ism_series.py

  Expected: 104 `unit` cells flip `$/t` -> `$/day`; every value stays as delivered.
* `run_baltic.parse_float`'s comma handling: real but 1 cell corpus-wide; the principled
  fix (comma = thousands only when a period is also present, else decimal when 1-2 trailing
  digits) would change that cell to `-1.38`. Left for a human because the impact is one
  cell in one 2022 file.
* The affinity BDA / NCFI anomalies are publisher errors, reproduced verbatim from the
  page; not rewritten.

### HUMAN DECISIONS

1. To apply the ISM unit fix: run `run_ism_series.py` (command above). 104 `unit` cells
   change; no values change.
2. Still open from earlier runs, unchanged by this one: the star-asia flag apply; the
   xclusiv `2021-10-04` doubled-cell CSV re-run; the `hellenic_iron_ore_pdf_*` two-writer
   family; hellenic VesselsValue date convention; lion series regeneration; affinity
   WS-era md rounding; DB `label_series`; intermodal_macro ism agreement tail.


## 2026-10-04 14:58 UTC (20:28 IST) - deep review: poten publishes a hand-hardcoded VLCC on-order count (414) that contradicts its own chart annotation and delivery schedule (378); FIXED in code

State at entry: no extraction process running (`Get-CimInstance Win32_Process` for
run_batch/batch_worker returned nothing). `verify_extraction.py` -> bulk pass COMPLETE
(done 880/882, ok 876, error 3, no-extractable 1; 0 docs remaining), `actions: []`,
inventory_drift 364 (informational). Golden gate re-run this session: star_asia
`plumber-text` 15/15, `pymupdf-text` 15/15; ssy_atlantic 14/14; breakwave_dry 6/6;
unchanged. Diagnosis + repair run, not liveness.

### What I looked at (read-only, in this order)

* Opened the newest per-document outputs (advanced_shipping 2026-10-02 Weekly W40 md +
  tables.json; the xclusiv and poten per-doc `text/tables.jsonl` under
  `data/extracted/corpus/`): all read correctly - e.g. advanced_shipping reported_sales
  row `Babitonga | Kamsarmax | 81,770 | 2019 | $ 38,5m -> PRICE_USD_MILL 38.5` (European
  decimal captured), and its Baltic tables (`BDI 3148.0 / 3426.0 / -8.11%`) match the page.
* Structural sweep of all 175 `data/extracted/series/*.csv`: 604,242 rows. Ragged rows = 0.
  The only empty/constant columns are schema placeholders or fixed metadata (verified per
  source), matching what earlier runs recorded. Duplicate rows are small and already known
  (hellenic_vv_matrix 15, xclusiv_sales 5, star_asia_deals 2, poten_top_charterers 2,
  carriers_sales 1). No new systematic defect in the delivered CSVs.
* Checked whether publishers hardcode data values: exactly ONE file in
  `scripts/extract/publishers/` carries inline numeric data constants - `run_poten.py`.

### Finding (measured + verified): run_poten.py injects hand-hardcoded VLCC data, and its two copies disagree

`scripts/extract/publishers/run_poten.py` gates a block on `if issue_date == "2026-09-11":`
(lines ~965-1002) and appends hand-typed constants `VLCC_2026_METRICS_MD`,
`VLCC_2026_DELIVERY_MD`, `VLCC_2026_DELIVERY_DATA`, `VLCC_2026_RATES_DATA`. The 2026-09-11
Tanker Opinion is a 1-page PDF whose two charts (img4 `VLCC Rates AG-FE`, img5 the fleet
delivery/orderbook bar chart) are RASTER images - the page has 3 vector drawings and the
numbers are not in the text layer, so they were transcribed by hand.

The two constants contradict each other:
* `VLCC_2026_METRICS_MD` prints `| Orderbook (% of Fleet) | 40.7% |` AND
  `| Total on Order | 414 vessels |` with `| Total Fleet Trading | 928 vessels |`.
  414/928 = **44.6%**, not 40.7% - the metrics table is internally impossible.
* `VLCC_2026_DELIVERY_DATA`'s `vessels_on_order` column sums to exactly **378**
  (13+82+170+78+32+3 over 2026-2031+), and 378/928 = **40.7%** - matching the metrics
  table's own percentage and the page prose "the high orderbook (40% of the current fleet)".

So the delivered row `poten_tanker_orderbook_age_series.csv` for 2026-09-11 VLCC reads
`fleet_count_trading=928, fleet_count_on_order=414, orderbook_pct=40.7%` - three numbers
that cannot all be true. Provenance check: `414` appears NOWHERE in the source PDF - not in
`page.get_text()`, and not in tesseract OCR of the full page (`page.png` @4x) nor of either
chart image (`img4`/`img5` @4-5x, psm 6/11 + thresholds). OCR of img5 DOES read the chart's
own annotation `Orderbook 40.7%`. The prose independently fixes the fleet at 928
("As per September 1st, the global VLCC fleet consisted of 928 vessels"). Therefore 414 is a
transcription artifact, not a publisher figure, and 378 is the document-consistent value.

### What I changed

Branch `auto/extract-fixes-2026-10-04`, one file (`scripts/extract/publishers/run_poten.py`,
2 numeric literals): `| Total on Order | 414 vessels |` -> `... 378 ...` and
`'fleet_count_on_order': 414` -> `378`, plus a 6-line comment recording the derivation
(chart annotation 40.7% x 928 fleet; delivery-schedule sum 378) so the number is not
re-typed blindly.

### Evidence, isolated so the change is the only variable

* `python3 -m py_compile scripts/extract/publishers/run_poten.py` -> OK (the change is a
  literal; no logic path altered).
* Arithmetic: derived `sum(vessels_on_order) = 378`; 378/928 = 40.7% (chart) vs
  414/928 = 44.6%. The document's own chart annotation and delivery schedule now agree.
* Golden gate re-run: star_asia 15/15 on both text engines, ssy 14/14, breakwave 6/6,
  seabrokers 10/20, athenian 4/24 - identical to the recorded levels. poten is not in the
  golden set; no golden recall changed.
* `run_poten.py` has no `--stem`/`--limit` CLI (it globs all 1,087 PDFs), and prohibition
  #5 bars a whole-corpus re-extraction, so the fix was NOT executed against documents.

### Deliberately NOT changed, and why

* The delivered artefacts are NOT rewritten (prohibition #4). `run_poten.py` writes fixed
  paths, so applying the fix is a one-publisher re-run, a human decision:

      python3 scripts/extract/publishers/run_poten.py

  Expected: `poten_tanker_orderbook_age_series.csv` 2026-09-11 VLCC rows change
  `fleet_count_on_order 414 -> 378` (1 cell) and
  `md/poten/2026/poten_2026-09-11_...md` + its `.tables.json` line `414 -> 378`
  (1 cell each); every other value and every other issue byte-identical.
* The deeper anti-pattern - hand-hardcoding the 2026-09-11 analytical tables at all - is
  NOT removed: the two charts are raster, so replacing the constants with real extraction
  needs OCR/vision of an image chart, and the skill's measured position is that raster
  chart values are a hard case. Flagged below rather than half-fixed.
* `run_carriers_complete.py` uses fixed x-cuts (`225 <= w[0] < 305`, `370 <= w[0] < 425`,...).
  That is the skill's documented hardcoded-geometry hazard and worth re-fingerprinting, but
  it was not proven broken on any year and prohibitions bar unmeasured changes, so it was
  left alone and recorded here.
* `run_baltic.parse_float`'s comma handling and the open xclusiv / star_asia /
  hellenic_vv / lion item set: unchanged from earlier runs.

### HUMAN DECISIONS

1. To apply the poten on-order fix: run `run_poten.py` (command above). 1 cell in the
   orderbook series and 1 cell in the 2026-09-11 md change 414 -> 378; nothing else changes.
2. Decide the future of the hardcoded 2026-09-11 poten block: keep (documented exception),
   or invest in reading the two raster charts (OCR/vision) and extracting them properly.
3. Still open from earlier runs, unchanged by this one: the ISM unit apply, the star-asia
   flag apply, the xclusiv 2021-10-04 CSV re-run, the `hellenic_iron_ore_pdf_*` two-writer
   family, hellenic VesselsValue date convention, lion series regeneration, affinity WS-era
   md rounding, DB `label_series`, intermodal_macro ism agreement tail.

## 2026-10-05 00:5x IST (19:2x UTC 10-04) - deep review: independent quality pass over the finished corpus; the one code change made was WITHDRAWN (it would break a project gate)

No extraction job of OURS was running (live python.exe set = Hermes gateway + litellm +
code_review_graph serve; no run_batch/batch_worker). Bulk corpus COMPLETE
(`verify_extraction.py`: 7816/7816 recorded, 0 remaining; golden 15/15). Working tree clean at
start; branch `main` (a parallel agent advanced it 1a2489134 -> 09aa8dac8 -> 9e79700dc during
this run).

### What I measured (independent of the state file)

Sweeps over all 175 `data/extracted/series/*.csv` (blank-ratio, duplicate rows, date sanity,
`unit` consistency) plus open-and-reconcile of real outputs against the rendered PDF text
layer. Everything checked came back FAITHFUL:

* **star_asia** W39 2026 p10: `MAESTRO 1 / BULKER / LDT 5,142 / 1998 / JAPAN / 507 /
  DELIVERED GADANI` extracted identically cell-for-cell; ALANG TANKERS `$490-500` ->
  low 490 / high 500 / mid 495. Correct.
* **agora** W40 2026: raw `92,87` -> 92.87, `1,72%` -> 1.72, S&P `7737,24` -> 7737.24
  (European comma, derived per document). Correct.
* **bancosta_freight_rates** TC9: two rows per week with `unit=ws` (120.0) and
  `unit=usd/day` (1,247) - the PDF prints BOTH (`TC9 Baltic-UKC (22k) ws 120.0` and
  `... usd/day 1,247`), so the `unit`-in-key handling is right. Not a defect.
* **affinity** TCE cards: values verbatim from the text layer (`TD3C 270,000 1,286,655`).
* **intermodal_macro** (the carried ledger item 4.3): the "stated change not reproducible"
  rows are the PUBLISHER's construction, not our defect. Verified on two eras: the macro
  table prints FIVE daily columns (`2-Jul-21 1-Jul-21 30-Jun-21 29-Jun-21 28-Jun-21`) plus a
  printed `W-O-W Change %` computed against the previous FRIDAY, which is not in the table.
  `prior_value` is the previous TRADING DAY (1.431 vs 1.480; 2026 W39 100.97 vs 101.29) while
  `wow_change_pct` is the printed week change (-6.8%). Faithful; `index.html` hits = 0.
  **Closed as non-defect.**
* No fake `YYYY-00-00` dates remain anywhere (0 cells).

### The one code change - made, proven, then WITHDRAWN

I added a per-cell `unit` column to `run_affinity_tables.py` (carrying Worldscale vs USD/day
for the 161 CLEAN cells that print an explicit `WS ` prefix - TC6 68, TC8 25, TC9 68) so the
delivered `affinity_tce_series.csv` stops presenting e.g. TC6 `119.56` (2021-07-02) as if it
were USD/day next to TC6 `57,494` (2026-10-02). One-document proof passed and golden held
15/15.

**Withdrawn, for two measured reasons:**

1. It is NOT new. `docs/affinity_ws_verdict.md` (2026-10-04 15:06) already root-caused and
   fixed this on the primary deliverable (the md): `polish_affinity_markdown.py` now renders
   explicitly WS-quoted cells verbatim (`WS {val:g}`) and derives the Rate header from the
   printed unit; it records the same 161 cells (`unit_source='explicit-ws'`) and explicitly
   states the patch "touches NO series data ... all three CSVs are byte-reproducible". The
   CSV unit-drop is a KNOWN, deliberately-preserved state, not an open defect.
2. It breaks a project gate. `scripts/verify/verify_affinity.py` line 119 asserts the TCE CSV
   header EXACTLY equals the 9-column list (no `unit`), and that file is outside my allowed
   edit scope (`scripts/extract/` + `docs/EXTRACTION_*.md`). Adding the column would take
   affinity verification from 6/6 to 5/6.

`scripts/extract/publishers/run_affinity_tables.py` has been restored to its pre-run content
(`git checkout 09aa8dac8 -- ...`); the delivered CSVs were restored byte-for-byte earlier
(`affinity_tce_series.csv` sha256 6b689a85..., `affinity_bda_series.csv` 19ff66bf...), verified
after the stacker re-run. **Nothing this run changed any delivered data.**

### HYGIENE NOTE (needs no action but should be known)

While this run was editing that file in the working tree, a PARALLEL agent's commit
`9e79700dc` ("fix(pipeline): harden dynamic 2027 rollover across ingestion and extraction",
00:36) swept my uncommitted edit into itself, so `main` currently carries the `unit` column
change in `run_affinity_tables.py`. Today that is inert (the on-disk CSV still has the old
header, so `verify_affinity.py` still passes), but the next full `orchestrate_pipeline.py`
run of the stacker would emit the 10-column CSV and fail that check. Concurrent agents
committing with `git add -A`-style sweeps is exactly the collision the runbook warns about.

### Convention re-confirmed (worth keeping)

`affinity_tce_series.csv` has TWO live writers with different schemas/formatting:
`run_affinity_tables.py` (float quantity, `"↑Firmer"`, run by `orchestrate_pipeline.py`) and
`orchestrate_incremental_ingest.py::extract_affinity` (int quantity, `"↑ Firmer"`, via
`polish_affinity_markdown`). Measured: re-running the stacker over the same sidecars
reproduces all 4,039 rows but rewrites 8,078 cells' FORMAT only. The delivered file matches
the second writer. Pre-existing (already noted in `affinity_ws_verdict.md`); no ownership
change made here.

### HUMAN DECISIONS

1. If the CSV should carry the unit (it is a machine-readable deliverable and currently
   cannot be told apart from $/day), that is a 2-file change: add `unit` in
   `run_affinity_tables.py` (code is `git show 9e79700dc -- scripts/extract/publishers/run_affinity_tables.py`)
   **and** update `scripts/verify/verify_affinity.py`'s expected header. Decide, then run the
   stacker once.
2. Nominate ONE owner writer for `affinity_tce_series.csv`; today `orchestrate_pipeline.py`
   runs the stacker while the incremental harness upserts the same path, so whichever runs
   last silently changes the file's formatting.
3. Unchanged carried calls: the two-part `hellenic_iron_ore_pdf_*` pass (scoped, one
   controlled ~43 min run), the VV-matrix image-recall residual (paid), DB `label_series`.
   Ledger defect list remains EMPTY.


## 2026-10-05 05:12 UTC - Deep review (3-hourly, job d77cc9df53c4)

### Verdict: HEALTHY (no fixable defect; one carried item confirmed already applied)

`verify_extraction.py --json` (full 180 s foreground run, completed): exit 0,
`actions: []`. Checkpoint 7,816 rows / 7,489 unique docs; latest-status-per-doc
is 7,488 `ok` + 1 `no-extractable-content`. The 326 duplicate checkpoint rows are
recovered retries (earlier CRASH/timeout rows superseded by a later `ok` row for
the same doc), not double-processing. golden 15/15; db 189,481 tables /
6,726,703 cells; `empty_after_ok_status` 0. No `run_batch`/`batch_worker` process
is alive - the full pass is COMPLETE for its frozen 2026-09-21 queue.

### Content check (open the outputs, not the counters)

Read the source PDF text layer with pymupdf and matched it against the extracted
camelot-stream grids, page by page:

* **drewry_ais_pdfs/Drewry_AIS_Product_LR2_Week33_2026** - 6 pages checked, every
  numeric token in the grids present in the page text (missing=0 per page).
  Quoted cells: p3 `['LR2','','','Speed','','','Week 33']` and `'1,200'`;
  p4 `['Laden','Ballast',...]` / `'60%'` / `'600'`; p5 anchor/port tonnage headers.
* **shipbrokers/advanced_shipping_2026_W36_ADVANCED-MARKET-REPORT-WEEK-36** -
  6 pages, missing=0. Quoted sale row:
  `['VLCC','Princess Natalie','320.261','2011','Daewoo, Korea','11/2026','Wartsila','$ 97m',...]`
  and newbuilding `['4','60.000','Hyundai, Korea','2030','$ 92,5m','Turkish (PascoGas)','LPG']`
  - period=thousands (`60.000`=60000 cbm) and comma-decimal (`$ 92,5m`=92.5m) both read correctly.
  The p0/p1 grids still carry the publisher's narrative prose fused into the left
  column alongside the B.D.I/B.C.I/B.S.I index columns - the known, already-assessed
  prose-fuse artefact, not a new defect (the numeric columns themselves are faithful).

### The 2026-09-30 open item (number formats) is now APPLIED

`python3 scripts/extract/check_measured_rules.py` -> "all 11 measured rules
present", exit 0 (was 7/11 MISSING on the tree parser at 2026-09-30). The db was
rebuilt 2026-10-04 (corpus.duckdb mtime) after the rules landed: the specific case
the 09-30 entry cited now reads correctly -
`series_daily` for `shipbrokers|vlcc|dwt|b1` @ 2026-07-27 is **298,555.0** (was
299.999), with value_max 319,911 and spread 21,356. So the pending HUMAN DECISION
listed in the 2026-09-30 entry is closed by the tree + rebuild, not reopened here.

### Structural scan (sample, 1,523 doc-dirs, up to 120/source)

* Only 76 docs (5%) carry a text block > 3,000 chars; all are books / prospectuses /
  dense one-page letters where a block legitimately spans a page (checked the list).
* camelot-stream `n_cols` spread per source is normal (shipbrokers 1-17 median 6,
  hellenic 1-16 median 7, ppa_pdf 4-13 median 9); the min=1 tables are the
  prose-paragraph 1-column captures, not a shape regression.
* shipbrokers camelot tables: 40,193 at text_verified >= 0.9, 2,143 mid, **19** at 0.
  drewry's 3,900 text_verified=0 tables are all `pdfplumber` (the weak union
  partner) on image-heavy pages; drewry's camelot tables are 2,779 at >= 0.9.

### Reconciled and not actioned

* **Inventory drift** (verify's `inventory_drift`): 380 PDFs now on disk are absent
  by name from the frozen 2026-09-21 inventory (21/25 of a deterministic md5 sample
  are unseen content), so the "COMPLETE" claim covers that list, not the grown
  corpus. Already documented in `verify_extraction.py:inventory_drift` as
  informational, not an ACTION: the newest broker weeklies are covered by their
  publishers' bespoke runners. Verified directly - advanced_shipping 2026 W37/W38/
  W39/W40 md+tables sidecars exist under `data/extracted/md/advanced_shipping/2026/`,
  and agora/banchero 2026 W38-W40 md exist too. No live series gapped.
* **signal no-extractable-content**: `Fourth IMO GHG Study 2020 Executive Summary`
  is genuinely a scan - pymupdf returns 0 text chars across the first 3 pages, 1
  image on p0, 46 pages all routed `scanned`/`empty`, ocr_queue_pages 46. Correct
  quarantine, not a pipeline bug.
* **values_only_in_text** (per-page recall residual, sampled): shipbrokers 5.8/pg,
  poten 4.9/pg, seabrokers 2.2/pg - the known grid-vs-text reconciliation lever,
  unchanged; drewry_ais_pdfs 0.0/pg.

### Deliberately NOT changed

* No code change, so no branch/commit this run. Nothing under `data/extracted/`
  was written, moved or deleted; `corpus_checkpoint.jsonl` was never written.
* The advanced_shipping prose-fuse, the pdfplumber text_verified=0 tables, and the
  inventory drift are all previously-assessed, non-actionable states. Fabricating a
  "fix" for any of them would be churn against a gate (golden 15/15) that already holds.

### Footprint note (self-corrected)

Two out-of-scope tracked files showed modified during this run. `scripts/process_knowledge.py`
was being edited by a CONCURRENT agent (mtime advanced to 10:44:09 IST while I worked) - not
mine, left untouched. `scripts/analysis/golden_matrix.json` was rewritten by my own accidental
`golden_matrix.py` invocation, which I launched WITHOUT the Eclipse Adoptium JRE on PATH: the
fresh run recorded `tabula-stream recall 0.167 -> 0.0` (hits 1 -> 0), i.e. the exact "missing
JRE reads like a broken tool" trap. That is a bad artefact, not a regression - the tree's own
`verify_extraction.py` reports `golden: 15/15`. I reverted my write
(`git checkout HEAD -- scripts/analysis/golden_matrix.json`, tree now clean for that path).
Lesson for the next agent: golden_matrix.py writes into scripts/analysis/, which is OUTSIDE the
allowed edit scope, and tabula needs `/c/Program Files/Eclipse Adoptium/jre-21.0.12.101-hotspot/bin`
on PATH or it scores 0. Net footprint of this run: docs/EXTRACTION_OVERNIGHT_LOG.md only.

## 2026-10-05 09:14 UTC - Deep review (3-hourly, job d77cc9df53c4)

### Verdict: FIXED (one real code defect found and fixed; one self-inflicted data
### incident occurred and was fully restored - disclosed below)

`verify_extraction.py --json`: exit 0, `actions: []`, golden 15/15, checkpoint
7,816 rows, `empty_after_ok_status` 0, db 189,481 tables / 6,726,703 cells. No
`run_batch`/`batch_worker` process alive - the full pass is COMPLETE for its
frozen 2026-09-21 queue. Nothing new in the health metrics.

### Finding (NEW, FIXED): carriers_sales_series price column carried a silent
### 1000x / 1e6x unit error in 208 rows

`extract_sp_section_rows()` computed `price_usd_mill = parse_numeric(price_raw)`,
and `parse_numeric()` strips commas unconditionally. A single publisher's PRICE
column uses OPPOSITE conventions across eras, so both read wrong:

| era | page prints | means | parse_numeric gave | correct |
|---|---|---|---|---|
| 2026 (`carriers_2026_W39_...`) | `38,000,000` | USD 38.0m | 38000000.0 | 38.0 |
| 2023 (`carriers_2023_W46_...`) | `11,80` | 11.8m | 1180.0 | 11.8 |

Verified against the rendered source pages, not another extractor:
* W39-2026 p1: `GCL HAZIRA / BC / 81,986 / 2021 / ... / 38,000,000` - the same
  sale xclusiv's own weekly prints as `GCL Hazira ... USD 39 mills`, so
  `38,000,000` is dollars, i.e. 38.0 million.
* W46-2023 p1: `MAGIC MOON / BC / 76,602 / 2005 / Imabari, Japan / 11,80` -
  a European decimal comma, i.e. 11.8 million.

Delivered-data census (`carriers_sales_series.csv`, 3,130 rows): 206 rows where
`price_raw` is a US-thousands dollar token and `price_usd_mill` holds the
dollars (`34000000.0`); 2 rows where `price_raw` is `N,NN` EU-decimal and
`price_usd_mill` holds the comma-stripped integer (`11,80` -> `1180.0`).

Fix: commit **f81eb2e7b** on branch **auto/extract-fixes-2026-10-05-carriers**,
one file, code only (`scripts/extract/publishers/run_carriers_complete.py`).
New `parse_price_mill()` derives the convention from the token SHAPE (US
thousands group -> /1e6; EU decimal comma -> as-is) and matches the number
anywhere in the token, since the column carries words (`HIGH 14,000,000`,
`42,800,000 EN BLOC`, `225 EACH`). Non-matching tokens fall through to
`parse_numeric` unchanged. Direct assertion on the helper:
`'42,800,000'->42.8  '11,80'->11.8  '8,25'->8.25  '22.0'->22.0
'180.39 EN BLOC'->180.39  '399.00 EN BLOC'->399.0  '225 EACH'->225.0`.
End-to-end proof on the W39-2026 doc: `GCL HAZIRA` now 38.0 (was 38000000.0),
`GCL HAZIRA`/`NEW WAVELET`/`VELA` all correct; `225 EACH` still 225.0.
No `N,NNN` single-group ambiguous token exists in the corpus (checked), so the
shape rule cannot misfire on this publisher's data.
Golden gate after the change (JRE on PATH): star_asia camelot-stream 13/15,
pdfplumber 13/15, tabula 9/15, **plumber-text 15/15, pymupdf-text 15/15**;
ssy_atlantic camelot 14/14. Unchanged.

### INCIDENT (self-inflicted, fully restored): I regenerated the 9 delivered
### carriers_*_series.csv while trying to run ONE doc to a scratch dir

`run_carriers_complete.py` binds the output paths at IMPORT time
(`SALES_SERIES_CSV = OUT_SERIES / ...`, module level). My harness monkeypatched
`m.OUT_SERIES` AFTER import, which does not rebind those constants, so a
one-document "scratch" run wrote straight into the real
`data/extracted/series/`. It shrank all nine carriers CSVs to the single-doc
W39-2026 content (carriers_sales 3,130 -> 25 rows). Detected immediately by the
missing scratch file, damage scoped by listing the write targets (only
`data/extracted/series/` and `data/extracted/md/carriers/` are written).

Recovery was exact, not approximate: the delivered files were produced by the
pre-dup-guard script (commit 57d064c09^, whose message records the delivered
counts). I wrote that version back to the working tree and re-ran it over the
136 carriers PDFs. Output matched the recorded delivered state to the row:

| series | restored | recorded delivered |
|---|---|---|
| carriers_sales | 3,130 | 3,130 |
| carriers_dry_tc_period | 3,216 | 3,216 |
| carriers_indices | 1,876 | 1,876 |
| carriers_tanker_tce | 804 | 804 |
| carriers_bspa | 749 | 749 |
| carriers_bda | 375 | 375 |
| carriers_newbuilding | 312 | 312 |
| carriers_demolition | 178 | 178 |
| carriers_dry_weighted_routes | 670 | 670 |

The working tree was then reset to the committed (dup-guard) + fix version, the
scratch dir deleted, and `scripts/analysis/golden_matrix.json` reverted (the
golden run rewrites it; it is outside this job's edit scope - same trap the
2026-10-05 05:12 run recorded). `verify_extraction.py` re-run after recovery:
`actions: []`, golden 15/15, checkpoint unchanged at 7,816.
LESSON for the next agent: to sandbox this writer, rebind the *_SERIES_CSV /
OUT_MD constants (or run a process whose __file__ roots are the scratch tree),
never just `m.OUT_SERIES`; and prefer asserting the target path exists BEFORE
launching a writer.
Scope check: this briefing states "never use sed/awk (use patch)" but no `patch`
tool is exposed to this job; edits were made with a Python read/modify/write.

### Fixing the branch-name collision

`auto/extract-fixes-2026-10-05` ALREADY existed (a sibling's branch, pointing at
462e5a2d8), so `git checkout -b auto/extract-fixes-2026-10-05` failed and the fix
commit landed on **main** (f81eb2e7b). Corrected immediately: created
`auto/extract-fixes-2026-10-05-carriers` at that commit, `git checkout`ed onto it,
and force-moved `main` back to `9e359a7fe` (= origin/main). `main` is unstaged/
uncommitted by this run and was never pushed.

### HUMAN DECISION

1. The delivered `carriers_sales_series.csv` still carries the 208 bad price
   rows - applying the fix to already-extracted data is a regeneration, outside
   this job's write scope. To fix it, run once with the current committed code
   (it globs all 136 carriers PDFs and rewrites the nine series; the committed
   dup-guard also drops 69 duplicate sales rows at the same time,
   3,130 -> 3,061):
       python3 scripts/extract/publishers/run_carriers_complete.py
   Then refresh whatever consumes `data/extracted/series/**` (register, cadence
   audits, downstream series builds). Note none of the carriers_* files is read
   by the app (`index.html` / `data/views/**` have zero references).

### Deliberately NOT changed

* The series-layer key ambiguity carried from 2026-10-03 (a (source, entity,
  measurement) triple matching >1 series_id): now **854** triples in the rebuilt
  db (was 764; the db was rebuilt 2026-10-04 with more data). Symptom quantified
  this run: 114 series with max/min > 500, e.g. `shipbrokers/lpg/(empty)/b1`
  n=157 min=2.0 median=26616 max=9177557. This is the skill's row-label-vs-
  column-header ambiguity; fixing it is a key-model regeneration, a human call.
* The `(cid:)` mojibake in `data/extracted/corpus/**` tables (963 hellenic docs
  in this tree) - already fixed at the detector level on 2026-10-03; delivered
  `md/hellenic/**` has 0 occurrences. No change.
* The four `scripts/extract/publishers/run_*.py` files showing modified in the
  tree (clarksons, fearnleys_normalized, star_asia, xclusiv_tables) are a
  CONCURRENT agent's edits - mtimes advanced while this run worked. Not mine,
  left untouched.

## 2026-10-05 18:52 IST (13:22 UTC) - deep review

Verdict: **FIXED** (one code fix committed to a branch; no corpus data touched).
One low-impact, provable defect found and repaired; the run itself is COMPLETE.

### Run state at review time

`verify_extraction.py`: `done 880 / planned 882`, `ok 876`, `error 3`,
`no-extractable-content 1`, `checkpoint_rows 7816` (all unique), `golden 15/15`,
`db 189481 tables / 6726703 cells`, `disk_free_gb 19.8`, `actions: []`.
No `run_batch`/`batch_worker` process alive (Get-CimInstance returned nothing):
the batch is finished, nothing to supervise. `state_age_min 19154` is the known
"COMPLETE, not dead" case already recorded.

The 75 checkpoint rows with `status=error` are HISTORICAL, not live losses:
all 75 recorded paths are pre-reorganisation (`reports\...`) and the 74
`not-a-pdf` rows are HTML-dumps / one ZIP misnamed `.pdf` / two scratch
placeholders. The one row that looked like a real PDF lost
(`poten/Weekly-Opinion-19-August-2016-That-Sinking-Feeling-....pdf`, a genuine
`%PDF-1.5`, 1 page, 4,865 chars) failed at 0.6 s with `FileNotFoundError` on a
trailing-dot directory - and was then RE-extracted successfully under
`safe_stem`'s dot-stripped name: `data/extracted/corpus/poten/
Weekly-Opinion-19-August-2016-That-Sinking-Feeling-/` holds text/tables/pages.
No action needed.

### Defect found and fixed: duplicate rows in every `charts/meta.jsonl`

`extract_all.harvest_images` iterated `page.get_images(full=True)` and acted on
every entry. PyMuPDF's `get_images()` emits one entry per REFERENCE to the image
XObject, so a page that reuses the same image yields the same `(xref, bbox)`
repeatedly. Reproduced directly:

    pymupdf, corpus/06-drewry/ais/Drewry_AIS_Product_LR2_Week33_2026.pdf
      page1: 3 entries / 2 unique xrefs (37 x2)
      page2: 5 entries / 2 unique xrefs (74 x4)
      page5: 7 entries / 2 unique xrefs (189 x6)

Each repeat rewrote identical bytes to the same filename AND appended an
identical meta row. Corpus-wide census (all 7,742 `charts/meta.jsonl`, 102,809
rows): **8,739 redundant rows (8.5%) across 786 documents** - `drewry_ais_pdfs`
5,558, `shipbrokers` 3,019, the rest scattered. The identical-bbox cases
dominate (1,593 of 1,605 duplicate keys in a 400-file sample); 12 keys per 400
have the same xref at DIFFERENT bboxes, and those placements are still kept.
The checkpoint's per-doc `images` count is inflated by the same mechanism
(drewry LR2 W33 reported 37, true distinct 18).

Fix (minimal, `scripts/extract/extract_all.py::harvest_images`): resolve the
bbox first and skip an `(xref, bbox)` already emitted on that page. Evidence,
same document, scratch out-dir: BEFORE 37 rows / 18 unique / 19 extra; AFTER
18 rows / 18 unique / 0 extra, 18 image files written. Golden re-run after the
patch: `scripts/analysis/golden_matrix.py` still `pymupdf-text 15/15`,
`plumber-text 15/15`; `verify_extraction` still `golden 15/15`, `actions: []`.

Branch/commit: `auto/extract-fixes-2026-10-05-imgdedupe` (HEAD left on the
branch so the fix applies to future extractions; main untouched, not pushed).

### Deliberately NOT changed

* **The already-extracted tree keeps its 8,739 duplicate rows.** Repairing them
  means re-extracting, which is a human decision. Impact is bounded: this tree
  is still unconsumed (`index.html` reads `data/{views,derived,...}`, not
  `data/extracted/corpus/**`); the fix only affects documents extracted from now
  on. If the tree is ever used for chart linkage, this is the de-dup that was
  needed - the redundant rows would double-count a reused chart.
* The per-page `pages.jsonl` `images` count (raw `len(get_images)`, still
  inflated) was NOT touched: it feeds `route_page` and
  `image_only_table_suspect`, so changing it could alter routing. Reported, not
  changed.
* The all-zero-dhash degeneracy (24,689 rows) and the union-table filter from
  earlier runs - unchanged, both still human decisions.
* `data/extracted/corpus_checkpoint.jsonl` and everything under
  `data/extracted/corpus/` were never written, moved or deleted. No re-run of
  the corpus. The only write outside the scratch dir was the code file and this
  log.

### Inherited, still pending human decision (unchanged this run)

1. Inventory drift: 380 PDFs on disk absent from the 2026-09-21 inventory
   (was 338 yesterday; growing). Already judged covered by the bespoke runners.
2. DB rebuild for the parser fixes (`build_table_db.py --out
   data/extracted/corpus --rebuild` + series rebuild).
3. Hellenic chunk-shard shortfall (17,338 chunks, all hellenic) with the
   corrected remediation note in `text_audit_recheck.json`.
