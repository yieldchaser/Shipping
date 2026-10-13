# Work packages for other agents — 2026-10-14 → 2026-10-17

Written 2026-10-13 by Claude for Prateek, to keep the corpus clean-up moving while Claude is out of
weekly quota until Saturday 2026-10-17. Claude reviews every branch on Saturday before anything reaches
`main`.

How to use: open a fresh session of the other model **in a clean clone/worktree of this repo on an up-to-date
`main`**, paste the "Ground rules" section, then paste ONE package prompt. One package per session.

---

## Ground rules (paste these first, every session)

```
You are working on the Shipping repo (maritime market-report corpus: PDFs -> Markdown + CSV series).
These rules are absolute. Breaking one makes the whole session's output unusable.

1. NEVER push to main. Create the branch named in the package from an up-to-date origin/main
   (`git fetch origin && git switch -c <branch> origin/main`) and push only that branch.
2. NEVER invent, estimate, interpolate or "fix up" a number. Every value you write must be read
   from the source PDF text layer (pymupdf `page.get_text("words")`) or from a rendered page image
   you have actually looked at. If you cannot verify a value, leave the file unchanged and list it
   under "Open questions" in your log.
3. Reading a chart by eye is NOT allowed. Only numbers PRINTED on the page count.
4. Change only the files your package names. No bulk scripts over other Markdown files.
   Frontmatter-only changes keep the body byte-identical, and vice versa.
5. Never print, copy or commit secrets: ~/.nace/keys.env, anything starting llx-, sk-, ghp_, AKIA,
   "Bearer". Never commit personal phone numbers.
6. Before every commit run, ALONE (no other heavy job running):
       python scripts/validate_knowledge.py
   It must end with "Validation status: PASS". If it fails, fix or revert; do not commit.
   If you edited files under reports/broker_reports/, their source_hash in
   knowledge/manifests/documents.jsonl must be refreshed (see scripts/knowledge_hash.py).
7. Before every commit: `git diff --cached --stat` and read it. Only your package's files may appear.
8. Windows gotchas: write Python files with a file-writing tool, not bash heredocs (they mangle
   backslashes). Use PYTHONIOENCODING=utf-8. Long paths under knowledge/ need the "\\?\" prefix.
   Keep the line endings a file already has (check for \r\n before writing).
9. Keep a log at docs/handoff/logs/<package-id>.md, updated AS YOU GO (not at the end):
     - every command you ran that changed something,
     - every file changed, and for every changed value: file, old value, new value,
       evidence (PDF path + page number + the printed text you matched),
     - everything you skipped and why,
     - "Open questions" for the owner/Claude.
   Writing "verified" without the evidence line counts as fabrication.
10. Resume: keep docs/handoff/logs/<package-id>.progress.jsonl, one JSON line per finished unit
   ({"unit": ..., "status": "done"|"skipped", "note": ...}). On start, read it and skip done units.
   Commit work in small steps (every ~20 units) so a crash or shutdown loses little.
11. When unsure: stop changing things, write the question in the log, move to the next unit.
12. Finish by pushing the branch and writing a 10-line summary at the top of the log.
```

---

## Package A — Advanced Shipping series CSVs out of date (branch `handoff/advanced-series-drift`)

```
Context: data/extracted/series/advanced_shipping_*.csv are built from the per-issue sidecars
data/extracted/md/advanced_shipping/<year>/<stem>.tables.json. Running
  python scripts/extract/publishers/run_advanced_shipping_tables.py --stack-only
rebuilds all 5 CSVs from the sidecars. Today that rebuild DIFFERS from the committed CSVs for the
issues 2025 W46 ("...WEEK-46-1.pdf"), 2026 W38, W40, W41: the CSVs were not refreshed after those
issues were (re)ingested.

DANGER: do NOT run the script with --file or --all: --file overwrites every series CSV with one
issue's rows, and --all regenerates Markdown that later passes have hand-corrected
(2023 W31/W34-W37 were rebuilt from page renders on 2026-10-13 and must not be touched).

Task:
1. Run --stack-only in your branch, then `git diff --stat data/extracted/series/`. Restore any CSV
   change that is not one of those 4 issues (git checkout -- <file> and re-apply only their rows if
   needed). Report exactly which rows were added/removed/changed per issue.
2. Make sure 2025 W46 is not double-counted: check whether "...WEEK-46.pdf" and "...WEEK-46-1.pdf"
   are the same report (compare page-1 text). If they are duplicates, list it as an open question;
   do not delete anything.
3. Verify 15 random new/changed rows against the PDF text layer (log the evidence lines).
4. Validator, commit, push the branch.
```

## Package B — BDI rows duplicated in intermodal_baltic_tc_series.csv (branch `handoff/intermodal-bdi-dup`)

```
Context: data/extracted/series/intermodal_baltic_tc_series.csv holds daily values read from the
Baltic-index line charts in Intermodal PDFs (series BDI, BCI, BPI, BSI, BHSI, 5TC averages).
The official daily BDI is already in data/indices/bdiy_historical.csv (1985 -> today). Owner rule:
Baltic data that already exists in the repo must not be duplicated from chart readings.
Producers: scripts/extract/publishers/run_intermodal_charts.py, merge_intermodal_charts.py,
and the SIGNATURE_CATALOG entry in scripts/extract/orchestrate_incremental_ingest.py.

Task:
1. ACCURACY AUDIT FIRST (read-only): join the chart-read BDI rows to bdiy_historical.csv by date.
   Report count, mean absolute error, max error, and the 10 worst dates. Write the numbers in the log.
   This tells the owner how good the remaining chart-read series (BCI/BPI/BSI/BHSI) are.
2. Remove the BDI rows from intermodal_baltic_tc_series.csv AND change the producer(s) so a rerun
   does not bring them back. Do not touch other series.
3. Prove it: rerun the producer in merge-only mode if one exists (read its argparse first) or show
   by code reading that BDI is filtered. Do not regenerate other outputs.
4. Validator, commit, push the branch.
```

## Package C — ISM series names that are text fragments (branch `handoff/ism-series-labels`)

```
Context: data/extracted/series/ism_coaster_freight_series.csv and ism_handy_freight_series.csv come
from vector chart readings of ISM reports (per-report *.charts.json; find the producer with
`git grep -l ism_coaster_freight_series scripts`). Some series_name values are clearly not series
names: "increase in activity and rates until early October, when", "shifting their fleet from the
Continent to the western", "fertilizer offers for shipments ex Baltic ports in 2H May is",
"week CVB - Marmara/Med ...", "week Handysize, BlSea - EMed ...", and "YYYY year" values.

Task:
1. For each odd series_name, find 2 source reports (value_report column), render the page with the
   chart (pymupdf, 150 dpi), LOOK at it, and write in the log what the chart legend actually says.
   "2023 year" style names may be legitimate (one line per year in seasonal charts) — decide from
   the page, not from guessing.
2. Fix the label extraction in the producer so legends are read correctly; regenerate ONLY these two
   CSVs; show `git diff --stat` and that values (value column) are unchanged — labels only.
   If values change, stop and write an open question.
3. Validator, commit, push the branch.
```

## Package D — Render checks, verdict only (branch `handoff/render-checks`)

```
Context: these Markdown tables were produced by OCR of images and are not yet verified.
No text layer exists for them, so you must render and look.
  1. Seabrokers 2019-05 vessel table (data/extracted/md/seabrokers/2019/, the May issue): image table.
  2. Intermodal 2026 W08 and W09: raster S&P and currency tables.
  3. Fearnleys 2018 W29 (2 MDs under data/extracted/md/fearnleys/2018/).
  4. Banchero Costa raster S&P image tables: 20 random MDs that contain an S&P table with IMO
     numbers (data/extracted/md/banchero_costa/).
For each: render the page (pymupdf get_pixmap(dpi=150), crop to the table), compare EVERY cell with
the Markdown, and record per table: rows checked, cells checked, mismatches (MD value vs printed
value, row/column). Fix a cell ONLY when the printed value is unambiguous on the image; otherwise
log it. A table where more than 20% of cells are wrong: do not patch cell by cell — log it as
"rebuild needed" with the page number.
Output: docs/handoff/logs/render-checks.md with a verdict table. Validator, commit, push.
```

## Package E — Fearnleys MDs with no source file (branch `handoff/fearnleys-orphans`), READ-ONLY

```
Context: about 4,766 MDs under data/extracted/md/fearnleys/ and 184 under fearnleys-md/ have no
resolvable source document (frontmatter source_file missing or pointing to a file not in corpus/).
Task (read-only, no MD edits):
1. Produce docs/handoff/logs/fearnleys-orphans.csv: md_path, frontmatter source_file, issue date,
   title, candidate source(s) found under corpus/ (match by date + title words), match confidence
   (exact name / same date+title / none).
2. Summarise counts per year and per match class in the log. List 10 examples of each class.
Commit the CSV + log, push the branch. Do not delete or edit any MD.
```

## Package F — Duplicate voice records and stale _digests, inventory only (branch `handoff/dup-inventory`)

```
Context: the owner noted ~643 duplicate "voice" records and stale files under
corpus/01-brokers/_digests/ (generated copies that may lag the canonical MDs in data/extracted/md/).
Task (read-only):
1. Find where voice records live (`git grep -il "voice" -- scripts | head`, then the data they write)
   and list duplicate groups: key, count, files, and whether the duplicates are byte-identical.
2. For every file in corpus/01-brokers/_digests/, find its canonical MD in data/extracted/md/ and
   report: identical / differs (diff size) / no canonical found.
Write docs/handoff/logs/dup-inventory.md + CSVs. Commit, push the branch. No deletions.
```

## Package G — Quality gate script (branch `handoff/quality-gate`)

```
Goal: scripts/verify/md_quality_gate.py that fails (exit 1) on new/changed MDs with known defect
classes found in the 2026-10-13 sweep. It must take a list of files (default: files changed vs
origin/main) and print one line per finding: path:line: rule: detail.
Rules:
  R1 bare price cell: a table cell that is exactly "$", "Region $", "High $", "Low $".
  R2 fake zero change: a row with two different prices and a change cell "0.0%"/"0.00%".
  R3 personal phone: +<country code> followed by 8+ digits (allow-list the publishers' switchboard
     numbers already present on main — collect them, do not guess).
  R4 chart readings: a table whose first column is >=80% month dates (e.g. 9/Jul/20, Jan-22)
     in data/extracted/md/intermodal|banchero_costa (these must be chart notes).
  R5 frontmatter source_file missing or not existing under corpus/ (main checkout path).
Write tests in tests/ with small fixture strings for every rule (pass + fail case each).
Run it over ALL MDs on main and put the counts per rule in the log — do not fix them.
Do not wire it into CI yet (Claude will do that). Validator, commit, push.
```

---

## Saturday checklist for Claude

- Read every docs/handoff/logs/*.md; spot-check 10% of the evidence lines against PDFs.
- Review each branch diff; merge only what is verified.
- Owner decisions recorded 2026-10-13: ISM series stay (not Baltic data, not elsewhere in the repo);
  intermodal_baltic_tc_series keeps BCI/BPI/BSI/BHSI/5TC (no daily copy elsewhere), drops BDI
  (Package B); Agora staff numbers in git history: owner fine either way — a history rewrite of a
  public repo force-pushes main and breaks every clone and open branch, so it is NOT done unless the
  owner asks for it explicitly once more.
