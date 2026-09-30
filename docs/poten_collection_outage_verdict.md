# Poten live collection is DEAD on the Actions runner - and every run reports SUCCESS

**Date:** 2026-09-30 (cron, unattended) · Read-only diagnosis + a branch-side code fix.
**Found while auditing collection liveness source by source (not by being told which).**

## 1. The measurement

`corpus/04-poten` and `data/extracted/md/poten` both end at the **2026-09-18** issue
(`Running out of options`). The publisher's own feed (`https://www.poten.com/feed/`, 200 OK)
lists a **newer** opinion:

| feed pubDate | title | in our corpus? |
|---|---|---|
| Sat, 26 Sep 2026 | `Do We Need To Plan For A Diesel Export Ban?` | **NO** |
| Sat, 19 Sep 2026 | `Running Out Of Options` | yes (2026-09-18) |

So exactly one weekly issue is missing from the corpus, from the md tier and therefore from
the poten RAG chunks the app reads.

## 2. Why - the runner never ran the script

`gh run list --workflow=poten_drewry_weekly.yml` (last 8 runs), poten step outcome read from
each run's own log:

| run | date | conclusion | poten step actually did |
|---|---|---|---|
| 36184254920 | 2026-09-25 | **success** | `SyntaxError: f-string expression part cannot include a backslash` |
| 35385440798 | 2026-09-18 | **success** | same SyntaxError |
| 34638443661 | 2026-09-11 | **success** | same SyntaxError |
| 34008711337 | 2026-09-06 | success | `Poten crawl finished. Total in catalog: 0` |
| 33910113411 | 2026-09-04 | success | `Total in catalog: 0` |
| 33764879306 | 2026-09-03 | success | `Total in catalog: 0` |
| 33224625013 | 2026-08-29 | success | `Total in catalog: 0` |

**Every one of those runs is green.** The workflow step is
`python scripts/scrapers/fetch_poten_direct.py || true`, so a hard crash is swallowed and the
job still commits the rest. This is the "never judge a job by its delivery message" rule in
its most expensive form: the pipeline has been collecting **nothing** for poten since at least
2026-08-29 (0 items per crawl) and has not even imported the script since 2026-09-11.

## 3. The defect, reproduced locally

`scripts/scrapers/fetch_poten_direct.py` line 488 (working tree; **line 488 on `origin/main`
too**, verified after `git fetch`):

```python
    return f"""---
title: "Poten Tanker Opinion: {title.replace('\"', '')}"
```

A backslash inside an **f-string expression** is legal from Python 3.12 (PEP 701) only. The
Actions runner uses **3.11**, where the whole module is a SyntaxError before a single line
runs. The local cron box defaults to **3.14**, where the same file executes fine - which is
exactly why three weeks of silent failure went unnoticed.

Reproduced (nothing written):

```
"C:/Users/Dell/AppData/Local/Programs/Python/Python311/python.exe" -m py_compile scripts/scrapers/fetch_poten_direct.py
py_compile.PyCompileError: File "scripts/scrapers/fetch_poten_direct.py", line 511   <-- end of the f-string
SyntaxError: f-string expression part cannot include a backslash
```

## 4. Repo-wide sweep of the same class

Compiling every `scripts/**/*.py` and root `*.py` with the runner's interpreter:
**444 compiled, 3 failed** - all three are PEP 701-only syntax, all three now repaired:

| file | line | syntax | workflow-critical |
|---|---|---|---|
| `scripts/scrapers/fetch_poten_direct.py` | 488 | backslash in f-string expression | **yes** (weekly poten job) |
| `scripts/scrapers/fetch_poten_archive_backfill.py` | 265 | same | no (manual backfill) |
| `scripts/current_book_scenario_ui.py` | 39 | nested f-string reusing its enclosing quote type | no (legacy desk UI) |

After the repairs: **446 scripts compile on 3.11, 0 SyntaxError**.

## 5. The fix (branch only - `benchmark/extraction-comparison`)

The quote-stripping is hoisted out of the f-string (`title_clean = title.replace(chr(34), "")`),
so no backslash sits inside an expression; the same treatment for the nested-quote line in the
legacy UI.

**Controls (measured, not asserted):**
* `build_markdown()` from the HEAD version vs the fixed version, both loaded under 3.14 -
  **4/4 byte-identical** on titles with and without a double quote; the full 5-case matrix
  including `pdf_url` set/unset is **5/5 identical**.
* A first attempt at the edit silently dropped the literal `Poten Tanker Opinion: ` prefix from
  the frontmatter title. The control caught it (`5/5 DIFFER`, the diff visible in the title line);
  the prefix was restored and the control then reported `5/5 SAME`. Recorded because "the fixed
  file looked clean" is exactly the failure mode this project has already paid for once.
* `title.replace(chr(34), "")` == `title.replace('"', "")` on 4 samples; the reworked
  per-share-NAV line reproduces the old string for `1.2345 / -0.5 / None`.
* All three files still `py_compile` under 3.14.

## 6. What this fix does NOT do (stated, not implied)

1. **It does not change `main`.** `origin/main` still carries line 488, so Friday 2026-10-02
   17:00 UTC will crash again identically. Merging is the user's call (branch-only rule).
2. **It does not recover the missing 2026-09-26 issue.** poten.com returns **HTTP 403** to this
   box on both listing URLs (`/whats-new-2/tanker-opinions/` and
   `/category/industry-opinions/tanker-opinions/`), reproduced with the repo's own fetcher:
   `[!] HTTP 403 ... Could not retrieve page 1 from any base URL (last code: 403)`. Only the
   runner's egress can fetch it, and at the Sep-25 run the crawl returned 0 items even before
   the SyntaxError appeared - so the 403 wall needs its own diagnosis there.
3. **It does not make the workflow honest.** `|| true` is what turned three weeks of failure
   into three weeks of green. The poten step should assert a non-zero catalog (or be removed
   from that pipeline) so a broken source is visible in the run list.

## 7. Reproduce

```bash
PY311="/c/Users/Dell/AppData/Local/Programs/Python/Python311/python.exe"
"$PY311" scratch/sweep311.py                 # 446 compile / 0 SyntaxError after the fix
"$PY311" -m py_compile scripts/scrapers/fetch_poten_direct.py
python3 scratch/poten_fix_control.py         # 5/5 byte-identical vs HEAD
gh run view 36184254920 --log | grep -E "SyntaxError|Total in catalog"
python3 scratch/cadence_audit3.py            # the per-source freshness table
```

---

## 8. A SECOND poten defect, found while verifying the first: a 52% year-parse failure

`extract_year()` in `scripts/scrapers/fetch_poten_archive_backfill.py` was:

```python
def extract_year(filename, text=""):
    m = re.search(r'\b(20\d\d)\b', filename)   # misses Tanker_Opinion_20071109.pdf
    if m: return m.group(1)
    m2 = re.search(r'\b(20\d\d)\b', text)      # ... so it takes the TITLE's year
    if m2: return m2.group(1)
    return "unknown"
```

**`Tanker_Opinion_20071109.pdf` contains no word-bounded 4-digit year**: `_` and the
following digits are both word characters, so neither `\b` boundary exists. Measured over the
**1,087 poten PDF filenames on disk** (control `scratch/poten_year_control.py`, read-only), the
old function returns `unknown` for **564 of them (52%)** - every file in the archive's compact
`Tanker_Opinion_YYYYMMDD.pdf` form.

Two visible consequences, both real:

1. **A title-derived date.** The article *"The Outlook for Energy: A View to 2030"* (PDF
   `Tanker_Opinion_20071109.pdf`, i.e. 2007-11-09) fell through to the title, whose only year is
   **2030**, and was written as
   `corpus/04-poten/2007/poten_2030-01-01_the_outlook_for_energy_a_view_to_2030.md` with
   `date: "2030-01-01"` and `**Published Date**: 2030-01-01` in the body. It duplicates an
   article the corpus already holds correctly (`poten_2007-11-09_...md`, from
   `poten_clean_v2`).
2. **A phantom year partition in the app's knowledge tier.** The corpus-wide scan of
   `knowledge/chunks/**/*.jsonl` finds exactly **two** future-dated records, both in
   `knowledge/chunks/poten_tankers_2030.jsonl` - that same article, served with
   `Published Date: 2030-01-01`.

**Fix (branch, this run):** a compact `yyyymmdd` in the PDF's own name is read FIRST
(`COMPACT_DATE_RX`), the word-boundary pattern second, the title only as a last resort; and the
markdown's `date_str` now prefers the compact date instead of falling back to `{year}-01-01`.
**Control:** over the same 1,087 filenames, the 564 `unknown -> correct year` changes are the only
ones, and the two named cases behave - `Tanker_Opinion_20071109.pdf` + a "2030" title now returns
**2007**, a filename with no date at all + a "2030" title still returns 2030 (last-resort
behaviour deliberately unchanged).

**Left for the owner of the corpus (not done here - the file was written by another live session
at 00:01 today and the knowledge tier is rebuilt by its own workflow):**

```bash
# 1. the duplicate, mis-dated corpus file (the 2007-11-09 file is the authoritative one)
rm corpus/04-poten/2007/poten_2030-01-01_the_outlook_for_energy_a_view_to_2030.md
# 2. regenerate the knowledge tier (never hand-edit it), which drops poten_tankers_2030.jsonl
python scripts/process_knowledge.py
```
