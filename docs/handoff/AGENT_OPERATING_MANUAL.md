# Agent operating manual — corpus perfection sprint (2026-10-14 → 2026-10-19)

Owner: Prateek. Reviewer: Claude (back Saturday 2026-10-17). Target: done by Monday 2026-10-19.

## 1. The end goal (read this twice)

Every document we ingest — broker PDFs (corpus/01-brokers/*), Hellenic, Breakwave, Poten, Seabrokers,
Drewry, Signal, Baltic HTML, PPA, company reports, books — becomes a Markdown file that says exactly
what the page says, and every recurring table becomes a series CSV:

1. **Text**: complete, in reading order, no junk captions, no staff phone numbers.
2. **Printed tables**: every cell transcribed exactly as printed (European decimals as printed in the
   MD; numeric columns in CSVs parsed). Nothing dropped, nothing shifted, nothing invented.
3. **Charts**: NEVER eyeballed. A chart becomes `> **Chart (not transcribed):** <title>` UNLESS its
   numbers are recoverable exactly: printed data labels, the vector geometry of a PDF chart read by a
   deliberate reader (Drewry AIS, ISM, Hellenic MMi), or the data embedded in an HTML page (Gibson).
   Recover only charts that recur every issue, carry data we do not already have, and are not
   Baltic/route rates we already hold (`data/indices/`, `data/reference/fearnpulse_rates*.csv`).
4. **Backfill + ongoing**: the historical archive is fixed AND the extractor for that source is fixed,
   so the next weekly report comes out right with no manual step.

Per-source parsing spec: `corpus/01-brokers/Shipbroking_Source_Parsing_Notes.docx` (14 broker
sources; the owner's own notes — read the section for your source before touching it).
Read with: `python -c "import zipfile,re;x=zipfile.ZipFile('corpus/01-brokers/Shipbroking_Source_Parsing_Notes.docx').read('word/document.xml').decode();print('\n'.join(re.sub('<[^>]+>','',p) for p in re.findall(r'<w:p[ >].*?</w:p>',x,re.S)))"`

## 2. Source status ledger (2026-10-13)

| Source | Status | What is left |
|---|---|---|
| Lion | DONE (verified vs PDFs) | — |
| Hellenic Alibra TC | DONE (every image checked) | — |
| Star Asia | DONE (526 pages rebuilt with Nace) | — |
| SSY, Affinity, Poten, Baltic, Breakwave, Signal, Drewry opinions, Hellenic demolition | AUDITED OK (triage) | Breakwave/Signal: junk figure captions with asset hashes (cosmetic) |
| Drewry AIS | DONE (vector reader rebuilt) | — |
| Carriers | FIXED (TCE x1000) | full-sample audit not yet done |
| Xclusiv | FIXED (year labels) | full-sample audit not yet done |
| Agora | FIXED (contact sheet removed) | full-sample audit not yet done |
| Gibson | FIXED (live charts trimmed) | full-sample audit not yet done |
| Advanced Shipping | 2023 W31/W34-37 REBUILT | series CSVs stale for 2025 W46, 2026 W38/W40/W41 (Package A) |
| Intermodal | chart tables -> notes (verified) | raster S&P/currency tables 2026 W08/W09; BDI dup rows (Package B) |
| Banchero Costa | charts noted, 119 bar tables rebuilt | raster S&P image tables unverified (sample 20) |
| ISM | values OK | series labels that are text fragments (Package C) |
| Seabrokers | mostly OK | 2019-05 image vessel table |
| Fearnleys | UNAUDITED | ~4,766 MDs with no resolvable source; 2018 W29 (2 MDs) |
| Fearnleys-md | UNAUDITED | 184 MDs no source; raster charts: extraction APPROVED by owner but must be exact |
| Clarksons | UNAUDITED | full audit |
| Hellenic (other folders: VV, MMi, …) | partly | MMi desk commentary has scrambled font encoding |
| PPA, companies, other, books | UNAUDITED | inventory first (books are copyrighted: never commit them) |

## 3. Lanes — run up to three harnesses in parallel

Lanes own disjoint files, so their branches never conflict. Each lane pushes ONLY its own branch.

| Lane | Branch | Owns (may edit) | Work, in this order |
|---|---|---|---|
| L1 audit-brokers | `lane/l1-audit-brokers` | `data/extracted/md/{clarksons,fearnleys-md,carriers,xclusiv,agora}/**`, their sidecars and series CSVs, their extractor scripts | Clarksons → Carriers → Xclusiv → Agora → Fearnleys-md (audit; raster-chart extraction only after audit) |
| L2 series-scripts | `lane/l2-series` | `data/extracted/series/{advanced_shipping_*,intermodal_baltic_tc_series,ism_*}.csv`, the producers of those, `scripts/verify/md_quality_gate.py`, `tests/` | WORK_PACKAGES A → B → C → G |
| L3 render-checks | `lane/l3-render` | `data/extracted/md/{seabrokers,intermodal,banchero_costa,fearnleys,gibson}/**` and sidecars | WORK_PACKAGES D → Gibson full-sample audit → Fearnleys orphans inventory (E) → F |

If you only have one harness: L3 first (safest, most value per hour), then L1, then L2.
File ownership is machine-enforced: `docs/handoff/lanes.json` + check E7.

### 3a. Claiming a lane (do this FIRST — several agents may get the same prompt)

Each harness has a name the owner gives you in the prompt (HARNESS = e.g. `antigravity-1`, `kilo-1`).

1. `git fetch origin --prune` and list `git branch -r --list "origin/lane/*"`.
2. For each lane in order L3, L1, L2: if `origin/lane/<lane>` exists, read
   `git show origin/lane/<lane>:docs/handoff/claims/<lane>.json`.
   - claim `harness` == your HARNESS -> it is YOUR lane from an earlier session: `git switch <branch>`
     (or `git switch -c <branch> origin/<branch>`), read the progress file, RESUME.
   - another harness -> NOT yours. Never commit to, rebase, or push that branch. Go to the next lane.
3. No branch exists for the lane -> claim it:
   `git switch -c lane/<lane> origin/main`, write `docs/handoff/claims/<lane>.json` =
   `{"lane": "<lane>", "harness": "<HARNESS>", "claimed_utc": "<now>"}`, commit, and
   `git push origin lane/<lane>` (NO --force). If the push is rejected, another agent claimed it a
   moment earlier: delete your local branch and try the next lane.
4. All three lanes taken by others -> stop and tell the owner. Do not invent a fourth lane.

### 3b. What the checker cannot see — and how the review will catch it

We assume an agent may try to look productive instead of being correct. Known shortcuts and their
consequence (all are checked on Saturday; any one found rejects the branch):
- Evidence copied from a different page/row than the cell it supports -> `row` must be on the same
  line as the value (E3) and the PDF page must print the number (E1). Reviewer re-renders 10%.
- Deleting or "noting" hard tables to avoid proving them -> every removed numeric line needs a
  removal entry with page + reason (E5); reviewer looks at every removal page.
- Writing "audited 120 MDs, all good" without looking -> audit verdicts must list, per sampled table,
  the crop file and the number of cells compared; the machine-pass CSV must be reproducible by the
  committed script (reviewer reruns it and diffs).
- Claiming the validator or checker passed -> reviewer reruns both; a false claim rejects the branch.
- Editing the checker/validator/manual, or files of another lane -> E6/E7 hard fail.
- Copying values from another broker's report for the same week -> E1 checks the cited PDF only.
- Large regenerated outputs (rerunning an extractor over a whole source) -> forbidden; E4 will
  demand evidence for every changed number anyway.
Honest "could not verify / skipped" entries in the log are always accepted and cost nothing.

## 4. The audit protocol (how to attack a source)

For source S:
1. Read S's section in the parsing-notes docx. Read S's extractor (`git grep -l "<S>" scripts/extract`).
2. **Machine pass over every MD of S**: for each MD with a source PDF, collect numbers (>=3 digits)
   from the MD body and check them against the PDF text layer (pymupdf words; also accept European
   variants 3.285 = 3285, 0,92 = 0.92). Tool already on this machine:
   `C:/Users/Dell/shipping_session_tools_2026-10-13/src_sweep2.py` (read its docstring) — or write the
   equivalent. Output `docs/handoff/audit/<S>_machine.csv`: md, numbers, absent, absent examples.
3. **Classify every MD with absent numbers** by looking at the page (render 150 dpi). Classes:
   OK-COMPUTED (e.g. a change column the MD computed), OK-IMAGE (value is printed in an image; verify
   by eye), CHART-READING (must become a note), WRONG-VALUE, SHIFTED/DROPPED CELLS, MISSING ROWS.
4. **Eye pass on a stratified sample** even when the machine pass is clean: 2 issues per year
   (first and last of the year) + every issue whose layout changed. Compare every table cell by cell.
5. **Fix**: targeted edits only to MDs with a confirmed defect, each changed number logged in the
   evidence file (section 5). If one defect class hits >2 MDs, fix the extractor too and say so.
   Never rerun an extractor over MDs that were hand-corrected (Advanced 2023 W31/W34-37,
   Star Asia, Alibra, Banchero) — check `git log --oneline -- <file>` first.
6. Write `docs/handoff/audit/<S>_verdict.md`: MDs total, machine-clean, sampled by eye, fixed (list),
   open questions, extractor changes. Update the ledger row in this file in your branch.

### 4a. Look at the page (use your vision — this is required, not optional)

You are a vision model. Text-layer checks only prove a number exists somewhere on the page; only your
eyes prove it sits in the right row and column, and only your eyes see outlined/raster tables.
`scripts/verify/page_view.py` (read its docstring) makes the images:

    python scripts/verify/page_view.py absent <md>                 # absent numbers + renders their pages
    python scripts/verify/page_view.py side <md> <pdf> <page>      # page left, our MD table right, ONE png
    python scripts/verify/page_view.py page <pdf> <page> --find "SPRINGBANK"   # red boxes on matches
    python scripts/verify/page_view.py crop <pdf> <page> --find "SPRINGBANK" --save docs/handoff/evidence/<lane>/<id>.png

When to look (not uselessly — every look costs time):
- every MD that `absent` flags: open each rendered page and classify (section 4 step 3);
- the stratified eye sample (section 4 step 4): run `side` and compare every cell of every table;
- every edit you make: run `side` on the page AFTER the edit and look again;
- every kind=image evidence line: make the crop with `crop` and look at it before writing the line.
Write in the log what you saw ("p2 side: 14 rows, all cells match" / "p3: DD column shifted one row
from VIALLI down"). A log that never describes a page is treated as "never looked" at review.
Do not look at charts to read values from them — a chart is a note, never numbers.

## 5. Proof of work (non-negotiable — this is what your work is judged on)

Every number you add or change in `data/extracted/**` needs one line in
`docs/handoff/evidence/<lane>.jsonl` (format in `scripts/verify/check_evidence.py`). For image/
outlined pages, save the crop PNG under `docs/handoff/evidence/<lane>/`. Before each push run:

    python scripts/verify/check_evidence.py --lane <lane> --base origin/main --corpus-root C:/Users/Dell/Github/Shipping
    python scripts/validate_knowledge.py        # alone; must PASS

`check_evidence.py` re-reads the PDF page for every claim and fails any added number without
evidence. Saturday review: Claude re-checks a random 10% of evidence lines and every OCR-UNCONFIRMED
crop by eye. ONE fabricated evidence line rejects the whole branch; an honest "could not verify" in
the log costs nothing. Do not edit `scripts/verify/check_evidence.py` or `scripts/validate_knowledge.py`
(a branch that touches them is rejected).

## 6. Tools and money

- **PyMuPDF** text layer first, always (free, exact).
- **rapidocr** (`rapidocr_onnxruntime`, installed) for raster/outlined cells. Pattern that worked for
  Advanced 2023: column bounds from header words, row bands from alternating row backgrounds, OCR each
  cell crop at 300 dpi, then eye-check every table against the render. Tools: 
  `C:/Users/Dell/shipping_session_tools_2026-10-13/adv_cells.py, adv_build.py, adv_apply.py`.
- **Nace.AI** (docs: https://console.nace.ai/llms-full.txt; SDK `nace-sdk`). Keys: `~/.nace/keys.env`
  (NACE_API_KEY, NACE_API_KEY_2..6; loader `keys()` in `scripts/qa/nace_crosscheck.py`). Never print or
  commit a key. Use **NDI Parse** (`documents.parse`, `parse_mode="high"`, 2 credits/page, table_format
  html, figures omit) for image tables when rapidocr is unsure — it read Star Asia image tables exactly
  and does NOT invent chart tables. Do NOT use Extract for charts (it guesses gridline values).
  Budget: at most 3,000 credits per lane (~$12); log credits used. Retry 503 "not confirmed yet".
  Give `jobs.wait` a timeout.
- **LlamaParse**: all keys exhausted — do not use.
- Validator: `python scripts/validate_knowledge.py` (run alone, ~15-20 min).

## 7. Logs, resume, push

- Log `docs/handoff/logs/<lane>.md`, updated as you go: commands that changed files, decisions,
  problems met and how you handled them, open questions. Top: 10-line summary.
- Progress `docs/handoff/logs/<lane>.progress.jsonl`: one line per finished unit (MD or table).
  On start, read it and skip finished units. Commit every ~20 units.
- Push: `git push origin HEAD:lane/<lane-branch>` — never main. If the push is rejected, fetch and
  rebase your own branch; never force-push someone else's branch.

## 8. Paste-ready prompts

### Prompt for any lane (fill LANE)

```
You are harness HARNESS. Read docs/handoff/AGENT_OPERATING_MANUAL.md completely, then
docs/handoff/WORK_PACKAGES_2026-10-14.md (ground rules section). Claim or resume a lane exactly as
section 3a says — never touch a lane claimed by another harness. Then work your lane's list
(section 3) in order.
Follow the audit protocol (section 4) source by source. Every number you change needs an evidence line
(section 5); run check_evidence.py and the validator before every push; push only your branch.
You can see images: use scripts/verify/page_view.py and look at the page as section 4a says;
describe in your log what you saw on each page you checked.
If something is ambiguous, write it under "Open questions" in your log and move on. Never estimate a
number. Never read a chart by eye. When your lane's list is finished, start the next unaudited source
in the ledger that no other lane owns, and say so in the log.
```

Replace HARNESS with a unique name per harness (e.g. antigravity-1, kilo-1, roo-1). The same prompt can be given to every harness; the claim protocol assigns lanes.

The vision line is already in the prompt above (section 4a: use scripts/verify/page_view.py
and describe what was seen in the log).

### Resume prompt (same harness, new chat/session)

```
You are harness HARNESS, resuming. Read docs/handoff/AGENT_OPERATING_MANUAL.md, then
docs/handoff/claims/ and your log docs/handoff/logs/<your lane>.md and .progress.jsonl on your lane
branch. Check out your lane branch, skip finished units, continue. Same rules as before.
```

### Owner checklist (who gets what)

| harness | message | when |
|---|---|---|
| Antigravity (Gemini) | lane prompt with HARNESS=antigravity-1 | now |
| Kilo | lane prompt with HARNESS=kilo-1 | now |
| third harness, if any | lane prompt with HARNESS=<name>-1 | now |
| any harness after a crash/new chat | resume prompt with its OLD harness name | as needed |
| Claude, Saturday after quota reset | "Saturday review: fetch lane/* branches, run check_evidence per lane, re-check 10% of evidence lines + every OCR-UNCONFIRMED crop by eye with page_view side, merge what passes, then continue WORK_PACKAGES" | Sat 10-17 after 18:30 IST |
