# Agora: W40 (2026-10-02) was extracted but NEVER STACKED - fixed, and a per-source stacker committed

**Date:** 2026-10-08 · **Branch:** `auto/extract-fixes-2026-10-08` · source: `corpus/01-brokers/agora` (SNAPSHOT OF COMMERCIAL INDICATORS)

## The defect (measured, not inferred)

`agora_indicators_series.csv` stopped at **2026-09-25 / week 39** while the corpus and the `.md`
tier already held the **Week 40** issue (collected 2026-10-04, extracted to `.md` 2026-10-06):

| artefact | state before |
|---|---|
| `corpus/01-brokers/agora/2026/agora_2026_W40_...pdf` | present (md5 `a2b3930fcc`) |
| `agora_2026_W40_....md` + `.tables.json` | present (24,349 B sidecar, real tables) |
| `_run_state.json` | `agora_02_10_2026_...` (byte-identical keeper) listed **done**, 214 docs / 0 failed |
| `agora_indicators_series.csv` | **max issue_date 2026-09-25** - the 47 W40 rows were absent |

Cause: `run_agora.py` writes only md/tables sidecars. The series was previously extended by a
throwaway scratch script with **hardcoded weeks** (`scratch/agora_fix/append.py`), so a newly
collected issue is extracted but silently never stacked. This is exactly the "extraction gap"
class the register gate cannot see, because the gate compares the CSV against itself.

W40 is a byte-identical **pair** (`agora_2026_W40` = `agora_02_10_2026`, both md5 `a2b3930fcc`);
the ensemble kept the second copy as the keeper - consistent with the runner's rule.

## The date convention (measured, because getting it wrong is a silent one-day error)

The first append used the cover's *reference point* date (**2026-10-01**, a Thursday). That was
**wrong**. Measured over the shipped series:

* **212 / 213** distinct issue dates were a **Friday**;
* `report_week` == the **ISO week** of that date on **213 / 213** rows.

So the convention is: `issue_date` = the **Friday of the report's own ISO week**, not the printed
reference date (which is the Thursday before). Correct W40 date = **2026-10-02** (Friday, ISO week 40).
After the fix: **213/213 dates are Fridays, `report_week` == ISO week on 213/213, max date 2026-10-02**.

## Verification (control points at the same document that was built)

1. **Builder control** - `run_agora.build()` re-derives four *existing* weeks byte-exact before it
   is trusted: W35 (2026-08-28), W36 (2026-09-04), W37 (2026-09-11), W39 (2026-09-25) all
   `EXACT MATCH = True`.
2. **Content control (this session has no vision tool - same-document text reconciliation, stated)**
   - every built W40 value must exist as a numeric token in the PDF's own text layer, parsed with the
   document's EU convention: **141/141 (100.0%)**.
3. **Append control** - existing rows asserted byte-identical afterwards: `CONTROL ok`. 10,002 -> **10,049** rows (exactly +47), no removals.

## Named, NOT auto-applied (a wrong value is worse than a missing one)

The committed stacker reads the date from the document's own cover (`Week N / YYYY`) and skips -
naming - anything it cannot place. Three documents are named, none changed:

* `agora_2022_W52_...Week-52.-2021...pdf` - stacked as **2022-12-30**, but the document's own cover
  says **Week 52 / 2021**. Likely a pre-existing year error on 85 rows; NOT touched (needs its own
  measured fix, same class as the intermodal issue_date bug).
* `agora_2025_W38_...Week-42-2025...pdf` - filename says W38, cover says **Week 42**; the series
  carries it as 2025-09-19. Not re-added (double-count guard). The 39-42 window is otherwise absent.
* `agora_2026_W33_...Week-33...pdf` - cover says W33 but its printed reference point (20 Aug) is
  ISO week 34; the series already holds a week-33 row (2026-08-14). Internally inconsistent -> skipped.

## Committed tooling

`scripts/extract/publishers/stack_agora_weeks.py` - idempotent, content-driven, per-source stacker:

* date/week from the document cover, never a filename guess and never a hardcoded list;
* byte-duplicate dedup by md5 (lexicographically-first keeper, the runner's rule);
* "already in the series under another date" guard (no double-count);
* append-only with a byte-identical control.

`--dry-run` on the pre-fix corpus proposed **exactly** the W40 week (47 rows) plus the three named
skips - no collateral.

## Gate

`scripts/extract/verify_registers.py` = **ALL PASSED**, 180 CSVs / **640,917** logical rows == JSON == MD,
0 mismatches, 0 control chars/emoji (was 640,870; delta exactly +47).
