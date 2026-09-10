# 00 — GUARDRAILS (MANDATORY PREAMBLE FOR EVERY PROMPT)

> **This file is prepended to every task in this series. Read it fully before every phase.
> If any instruction in a task prompt conflicts with this file, THIS FILE WINS.**

---

## 0.1 The one rule that matters

**You may never invent a number.**

This repository has already been damaged by fabricated data that was presented as
authentic. A previous agent transcribed values off a chart *image* into a Python
dictionary, labelled it "UN Comtrade HS 260600 + Port of Kamsar AIS water flows", and
wrote a validation function that computed a cross-check, logged it, threw it away, and
returned the hardcoded numbers unchanged. That data is currently rendered in the UI as
real market data.

You are being asked to fix that class of problem, not repeat it.

**If you cannot source a number, the correct output is an explicit absence.** Write
`null`. Emit a row with `status: "UNAVAILABLE"`. Render "no data" in the UI. Report it in
your ledger. All of these are correct. Inventing a plausible value is the single worst
thing you can do in this codebase, and it is worse than failing the task.

---

## 0.2 Forbidden patterns

These patterns are banned. A phase containing any of them is a failed phase, regardless
of how much else works.

### F1 — Hardcoded observation data
```python
# BANNED
HISTORICAL_KT = {2024: {1: 9600.0, 2: 10100.0, ...}}
```
Hardcoding is permitted **only** for genuinely static reference metadata: port
coordinates, UN/LOCODE mappings, vessel-class DWT bands, great-circle distances,
contract tick sizes. Anything that varies with time or is *observed* must be fetched
or read from a fetched file.

### F2 — Silent fallback to a literal
```python
# BANNED
except Exception:
    return {}                      # caller then falls back to a hardcoded dict
value = live.get(k) or HARDCODED[k]

# BANNED
'diverted_pct': computed if computed else -73.1
```
If a fetch fails, the pipeline **fails loudly** and the affected series is marked
`UNAVAILABLE`. It does not quietly substitute a literal.

### F3 — Provenance claims you did not verify
Do not write "authentic", "verified", "genuine", "100% real", or name a source in a
docstring unless the code on the line below actually calls that source. If the docstring
says ComexStat, there must be a request to ComexStat.

### F4 — Validation theatre
A function named `validate_*`, `calibrate_*`, `verify_*`, or `check_*` must change its
output based on what it computed, or raise. A function that computes a check, logs it,
and returns its input unchanged is banned.

### F5 — Hardcoded timestamps
```python
# BANNED
'generated_at': '2026-09-07'
```
Use `datetime.now(timezone.utc).isoformat()`.

### F6 — Deleting or "fixing" data to make a check pass
Never edit a data file so a test passes. Never drop rows to remove an outlier. Quarantine
and report instead.

---

## 0.3 Provenance is mandatory

Every dataset this project renders must have a registered provenance record. Create and
maintain `data/provenance/manifest.json`. Every series gets one entry:

```json
{
  "series_id": "guinea_bauxite_exports_monthly",
  "display_name": "Guinea Bauxite Exports (Monthly)",
  "status": "LIVE | STALE | UNAVAILABLE | ESTIMATED",
  "source_name": "UN Comtrade",
  "source_url": "https://comtradeapi.un.org/data/v1/get/C/M/HS",
  "fetch_method": "REST API",
  "fetch_script": "scripts/acquire/fetch_guinea_bauxite.py",
  "output_file": "data/commodities/guinea_bauxite_exports.csv",
  "row_count": 116,
  "date_span": ["2017-01-01", "2026-08-01"],
  "last_fetched_utc": "2026-09-10T14:02:11Z",
  "unit": "kt",
  "is_derived": false,
  "derivation": null,
  "notes": ""
}
```

Rules:
- `status: "ESTIMATED"` requires a non-empty `derivation` explaining the method **and**
  the UI must show an "EST." badge wherever that series is plotted.
- `is_derived: true` requires `derivation` naming every input series_id.
- A series with no provenance entry **must not be rendered**.

---

## 0.4 The execution ledger — how you prove what you did

Before you begin, create `docs/megaprompts/LEDGER-<phase>.md` (e.g. `LEDGER-03-signals.md`).

**Append an entry after every discrete step.** Not at the end — as you go.

```markdown
## STEP 3.4 — Move Bollinger Bands module to Signals
- STATUS: DONE | PARTIAL | SKIPPED | BLOCKED
- FILES TOUCHED: index.html (lines ~18400-18520)
- WHAT I DID: moved the module markup + its renderer fn; rebound to bdiy_historical.csv
- VERIFY COMMAND: `grep -n "renderBollinger" index.html`
- EXPECTED RESULT: exactly 1 definition, inside the tab-signals panel
- ACTUAL RESULT: 1 definition at line 18402  ✔
- DEVIATIONS: none
```

Rules for the ledger:
- **`SKIPPED` and `BLOCKED` are acceptable outcomes. Concealing them is not.**
  If you skip something, say so and say why. You will not be penalised for an honest
  skip. You will be caught on a concealed one — every claim in this ledger will be
  re-run during the verification phase.
- Every step needs a `VERIFY COMMAND` that a third party can run to check your claim.
- If `ACTUAL RESULT` does not match `EXPECTED RESULT`, write it down anyway and mark
  `PARTIAL`.

---

## 0.5 Work in phases and STOP

Each prompt is divided into numbered PHASES.

**After each phase:**
1. Append the ledger entries for that phase.
2. Run the phase's verification block.
3. Commit with the message format given in the prompt.
4. **STOP. Print a summary. Wait for the user to say continue.**

Do not run two phases in one go. Do not "helpfully" continue. The stops exist so the
user can inspect before you build further on a bad foundation.

---

## 0.6 No regressions

Tabs **DASHBOARD, YEARLY, SEASONALITY, INDICES, ETFS, INTELLIGENCE, OFFSHORE** are
working and are **out of scope**. Do not restructure them. You may only touch them where
a prompt explicitly says so (e.g. the global type scale in Phase 1).

Before finishing any phase, confirm:
- every tab still switches
- no new console errors (`refreshVisibleCharts` already throws one known
  `Cannot read properties of undefined (reading 'label')` — do not add more, and fix that
  one if your phase touches its code path)
- no data file that was previously rendering has stopped rendering

---

## 0.7 Environment facts

- The site is **one static file**, `index.html` (~2.8 MB), served by GitHub Pages.
  No backend, no server-side rendering. Any "API" is a static file fetch.
- Python pipelines live in `scripts/` and `bunker_pipeline/`, run by GitHub Actions.
- Data lives under `data/`. **436 files exist; only 84 are wired into the frontend.**
- The repo is a git worktree setup. Commit on the current branch; do not force-push.
- Chart library is Chart.js. Map library is Leaflet.
- **Never commit a file over 90 MB.** If a build artifact exceeds it, shard it.

---

## 0.8 Definition of done for any phase

- [ ] Every step in the phase has a ledger entry with a working VERIFY COMMAND
- [ ] `python scripts/verify/check_no_fabrication.py` passes (built in Phase 1)
- [ ] `data/provenance/manifest.json` updated for every series touched
- [ ] No forbidden pattern F1–F6 introduced (grep proofs in ledger)
- [ ] No regression per §0.6
- [ ] Committed
- [ ] Summary printed and **STOPPED**
