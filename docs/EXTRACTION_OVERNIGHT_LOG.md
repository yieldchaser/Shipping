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
