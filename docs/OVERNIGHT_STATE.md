# OVERNIGHT STATE - read this FIRST, then resume

**Purpose:** if the machine sleeps, a session dies, or a new context starts with no
memory of this project, this file is the single source of truth. Read it, check the
live state it tells you to check, then continue. Do not restart finished work.

Last updated: 2026-09-24 ~02:30 IST (user asleep; wants autonomous work until ~06:30+)

---

## THE RULE (user's explicit instruction, do not violate)

**SOURCE BY SOURCE ONLY.** Each publisher gets its own measured pipeline with its
own treatment. A generic one-size runner across publishers was built and DELETED
on the user's order - a previous mass-extraction attempt "resulted in garbage or
complete fucking crap". Measurement scripts may be shared; the EXTRACTION
strategy must be per-source.

Method for every source, in order:
1. Count PDFs, year spread.
2. RENDER pages from several years and LOOK at them with vision.
3. Write `docs/<source>_survey.md` with the measured facts.
4. Build `scripts/extract/publishers/run_<source>.py` for THAT source.
5. TRIAL on 2+ documents from DIFFERENT years; compare against what you SEE.
   Do not bulk-run until the trial matches by eye.
6. Bulk-run as a BACKGROUND process with `notify=true` (never nohup).
7. Verify by CONTENT (doc counts, row counts, spot-check 2-3 values against a
   RENDERED page), then write `docs/<source>_verdict.md`.
8. Commit each step. Branch only, never main.

---

## STATUS

### DONE and verified - do NOT redo
| source | docs | output | notes |
|---|---|---|---|
| advanced_shipping | 249/249 | `data/extracted/md/advanced_shipping/` | VECTOR charts, EUROPEAN numbers (60.000=60000). `docs/prose_merge_verdict.md` records why a prose-fused table defect was ABANDONED (it duplicates Baltic data already held in `corpus/08-baltic` and already displayed). Do not reopen. |
| star_asia | 193/193 | `data/extracted/md/star_asia/` | 3,640 tables. Charts are RASTER and restate the text tables, so NO chart series are taken. ISO numbers. `docs/star_asia_survey.md`, `docs/star_asia_verdict.md`. |
| ssy | 519/519 | `data/extracted/md/ssy/` | 5,920 route rows. 1 page/doc. `docs/ssy_verdict.md`, `scripts/extract/publishers/run_ssy.py`. |

### xclusiv - COMPLETE (3 passes), verified
**266/266, 0 failures, 299s.** `data/extracted/md/xclusiv/`, pipeline
`scripts/extract/publishers/run_xclusiv.py`, verdict `docs/xclusiv_verdict.md`.

It took three passes, and the only reason the problems were found is that each
pass was verified against a RENDERED page:
  pass 1 - 85% labelled, but labels WRONG ('West Africa to Continent' labelled
           'Middle East Gulf' - a route named later in the same sentence).
  pass 2 - fixed to label the VALUE not the sentence -> 69% labelled, wrong
           pairs gone, but verification exposed two more defects.
  pass 3 - removed a duplicate value (153,488 as both LR2 and MR) and a stray
           value of 1 from an 'IN A NUTSHELL' sentence. Measured after: 0
           duplicates, 0 stray values.
Trustworthy: the .md corpus (full page text, all 266 docs) and every LABELLED
rate. Unlabelled values are real but their subject is deliberately not asserted.

### IN PROGRESS: source 5
Next source chosen: fearnleys (257 PDFs). Recon running.
Method as always: render pages from several years and LOOK; write
`docs/<source>_survey.md`; build `scripts/extract/publishers/run_<source>.py`;
TRIAL on 2+ docs from different years against what you SEE; only then bulk-run as
a BACKGROUND process with notify=true; verify by CONTENT and spot-check against a
rendered page; then write the verdict.
### NEXT (pick one, biggest first)
xclusiv 266 (in progress) · fearnleys 257 · intermodal 252 · affinity 250 ·
banchero_costa 243 · agora 213 · carriers 129 · ism 112 · lion 44
Non-broker: `corpus/04-poten` 1087 · `corpus/09-ppa` 493 · `corpus/06-drewry` 276 ·
`corpus/03-breakwave` 302
Count with: `find corpus/01-brokers/<name> -name '*.pdf' | wc -l`

---

## HOW TO CHECK LIVE STATE (do this before assuming anything)

```bash
cd C:/Users/Dell/Github/Shipping
export PATH="/c/Users/Dell/AppData/Local/Programs/Python/Python314:$PATH"

# what is running right now
tasklist | grep -i python | head

# progress of the current source (resumable state file)
python3 -c "
import json,sys
st=json.load(open('data/extracted/md/xclusiv/_run_state.json'))
print('done',len(st['done']),'failed',len(st['failed']))
[print('  FAIL',k,v[:90]) for k,v in list(st['failed'].items())[:8]]
"

# file counts per source
for s in advanced_shipping star_asia ssy xclusiv; do
  echo "$s: $(ls data/extracted/md/$s/*.md 2>/dev/null | wc -l) docs"
done
```

If the xclusiv process is GONE and `done` < 266, just re-run it - it resumes from
where it stopped, it does not restart:
```bash
python3 -u scripts/extract/publishers/run_xclusiv.py
```

---

## HARD-WON LESSONS (each cost hours - do not relearn)

- **RENDER A PAGE AND LOOK AT IT.** Four separate detectors of ours were
  confidently WRONG. Every real bug in this project was found by eye, not by a
  metric. Never report a defect count without hand-checking examples.
- **The control must point at the SAME document you rendered.** A run once showed
  all-MISS purely because the script picked the newest file while the eye-values
  came from an older one.
- **VERIFY WITH A CONTROL, before and after.** A "successful" fix once looked good
  only because a DIFFERENT earlier fix had already cleaned the file - it cost a
  wasted 4.2-hour run.
- **Never assign labels by row order or position.** Match by VALUE, bbox, or exact
  vocabulary; otherwise leave unlabelled. A wrong label is worse than a missing one.
- **Do not assume geometry is stable across years.** On SSY the label column moved
  from x~208 (2021) to x~12 (2026) and the table font changed 9.0 -> 8.7pt; a fixed
  x-cut silently deleted every route name and a fixed size threshold dropped the
  whole table. Derive thresholds FROM THE PAGE (e.g. the table's font size = the
  modal size among that page's numeric cells).
- **Evenly spaced rule chains appear in BOTH tables and charts** - anchor on
  CONTENT (numeric cells per row), not on geometry.
- **liteparse `ocr_enabled` defaults to ON** and costs ~43 of every 45 seconds
  (0 of 312 sampled pages needed OCR). Always pass `ocr_enabled=False`.
- **Numbers are PER SOURCE.** advanced_shipping European (60.000=60000);
  star_asia/ssy/xclusiv ISO (29,580=29580). Never carry a parser across publishers.
- **Verify completeness by CONTENT, not file count.** 193 files existing is not
  193 files being correct.
- **Check the data is not already held** before treating a defect as worth fixing:
  look in `data/**/*.csv`, the corpus, and `index.html`. One whole defect was
  abandoned after this check - it was worth zero.
- **Report MEASURED numbers, never estimates.** Estimates were wrong three times in
  one night in the safe direction.

---

## ENVIRONMENT

- Repo `C:/Users/Dell/Github/Shipping`. Commit on **`benchmark/extraction-comparison`**.
  **NEVER touch `main`.** `scratch/` is gitignored.
- Shell is **MSYS/git-bash**, not PowerShell. Native tools need `C:/...` paths.
- CPU-only, ~8 GB RAM: **no two heavy jobs at once.**
- Power: AC + DC standby/hibernate/disk timeouts are 0 (never) - verified.
- Python: `export PATH="/c/Users/Dell/AppData/Local/Programs/Python/Python314:$PATH"`
- Installed extractors: `liteparse 2.14.7`, `pdf_inspector`, `pymupdf4llm`, `pymupdf`.
  `opendataloader_pdf` is installed but performs badly here (0/35 numbers) and once
  polluted `corpus/` with stray `.json`/`_images/` - do not use it.
- LLaMA Parse (paid) is NOT installed and has no API key. Do not try to use it.
- User has **1,155 uncommitted files** in the working tree - **do not disturb them**
  and do not `git checkout`/`git stash` broadly.
