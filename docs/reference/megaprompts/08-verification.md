# PROMPT 08 — ADVERSARIAL VERIFICATION & REGRESSION SWEEP

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-08-verification.md`
> Depends on: Prompts 01–07 complete.

---

## Your posture for this task

**You are not the builder now. You are the auditor, and you assume the builder lied.**

Not out of malice — because that is what happened before. A previous agent transcribed
numbers off a chart image, wrote a `calibrate_*` function that computed a cross-check,
logged it, discarded it, returned the hardcoded values, and described the whole thing in
its docstring as "UN Comtrade HS 260600 + Port of Kamsar AIS water flows".

Every claim in `docs/megaprompts/LEDGER-*.md` is a hypothesis. Test it. Do not take a
`STATUS: DONE` at face value — **re-run its `VERIFY COMMAND` yourself** and compare to the
recorded `ACTUAL RESULT`.

---

## PHASE 8.1 — Re-run every ledger claim

For each of `LEDGER-01` … `LEDGER-07`:

1. Execute every `VERIFY COMMAND` recorded.
2. Compare actual output to the recorded `ACTUAL RESULT`.
3. Produce `docs/megaprompts/VERIFICATION_REPORT.md`:

```markdown
| Ledger | Step | Claimed | Re-verified | Verdict |
|---|---|---|---|---|
| 03 | 3.4 | 1 definition at :18402 | 1 definition at :18402 | ✅ CONFIRMED |
| 05 | 5.3.b | operator join complete | 214 of 740 rows have operator | ❌ OVERSTATED |
```

Verdicts: **CONFIRMED · OVERSTATED · UNVERIFIABLE · CONTRADICTED**.

Any step with no `VERIFY COMMAND` is automatically **UNVERIFIABLE** — list these
prominently; they are where concealment hides.

---

## PHASE 8.2 — Independent fabrication sweep

Do not trust `check_no_fabrication.py` — you may have written it to pass. Sweep by hand:

1. **Every dict literal with ≥8 numeric values** anywhere in `scripts/`, `bunker_pipeline/`.
   For each, decide: legitimate static reference (port coordinates, DWT bands, tick sizes,
   great-circle distances) or observation data. Report both categories.
2. **Every `except` block** in a data path. Does it fail loudly, or substitute?
3. **Every docstring** naming a data source. Does the code below it actually call that
   source? Check line by line.
4. **Every `*_KT`, `*_MT`, `*_HISTORICAL`, `*_CONFIG` constant.**
5. **Comments referencing images** — grep `image [0-9]`, `from the chart`, `read off`,
   `per the screenshot`, `green line`, `blue line`, `navy`.
6. **`index.html` inline arrays** of ≥12 numbers. (Baseline before this project: 4 hits,
   all 12-element month-label arrays — legitimate. Any new hit is a regression.)
7. **Identical-slope test.** For every multi-entity curve (forward curves, term structures,
   port price sets), compute the ratio series per entity and check whether entities share a
   slope to >4 decimal places. That test is what exposed the bunker forward curve. Run it
   across everything.

Anything found goes in the report with file, line, and the evidence.

---

## PHASE 8.3 — Provenance completeness

- Every data file `index.html` fetches has a manifest entry. **List any that do not.**
- Every manifest entry's `row_count` and `date_span` match the actual file. Recompute all.
- Every `status: "LIVE"` series has a `last_fetched_utc` within its expected refresh window.
  A "LIVE" series last fetched six months ago is mislabelled — report it.
- Every `ESTIMATED` series has a non-empty `derivation` **and** a visible EST. badge in the
  UI. Verify the badge renders; do not trust the manifest alone.
- Every `is_derived: true` names its inputs, and those inputs exist.
- **Nothing under `data/_quarantine/` is reachable from the UI.** Grep `index.html` and
  every view manifest for those filenames.

---

## PHASE 8.4 — Regression sweep

Untouched tabs — **DASHBOARD, YEARLY, SEASONALITY, INDICES, ETFS, INTELLIGENCE, OFFSHORE** —
must be unchanged in content. Open each, confirm:
- it switches, renders, and its charts draw
- its series count and date spans match the pre-project baseline
- no new console errors

Baseline to compare against (captured 2026-09-10, pre-project):
```
transfer 80.1 MB · 129 requests · load 4503 ms · 96 canvases · 16,838 DOM nodes
known console error: [refreshVisibleCharts dashboard] TypeError: Cannot read
  properties of undefined (reading 'label')  — near index.html:37821
tab panels: tab-dashboard, tab-yearly-dash, tab-seasonality, tab-indices, tab-etfs,
  tab-signals, tab-fearnleys, tab-intelligence, tab-tracking, tab-bunkers, tab-offshore
```

Targets now: **≤2.5 MB transfer, ≤1200 ms load, ≤12 canvases at load, 0 console errors**
(including the pre-existing one, which Prompt 03 was told to fix).

---

## PHASE 8.5 — Design conformance

```js
// must be 0
[...document.querySelectorAll('*')].filter(e=>e.innerText&&!e.children.length&&parseFloat(getComputedStyle(e).fontSize)<11).length
// every pane: scrollHeight - visible content <= 48px
// zero Unicode block sparklines
document.body.innerText.match(/[▁▂▃▄▅▆▇█]{3,}/g)   // must be null
// no tooltip describing the UI
[...document.querySelectorAll('[data-tip],[title]')].filter(e=>/re-renders from cache|Interactive control for this section|switches this section/i.test(e.getAttribute('data-tip')||e.getAttribute('title')||'')).length  // must be 0
```

Tooltip sample audit: pick **20 tooltips at random across all tabs**. For each, score
against the Prompt 01 §1.5 standard — three beats, 60–160 chars, no UI description, no
data caveat, provenance present. Report the pass rate. Below 90% means the rewrite was
partial and must be finished.

---

## PHASE 8.6 — Final report

Write `docs/megaprompts/VERIFICATION_REPORT.md` with:
1. Ledger verification table (§8.1)
2. Fabrication sweep findings (§8.2) — **or an explicit statement that a hand sweep of all
   seven categories found nothing**
3. Provenance gaps (§8.3)
4. Regression results + the five metrics before/after (§8.4)
5. Design conformance + tooltip pass rate (§8.5)
6. **An explicit list of everything that was claimed done but is not**

Then print a plain-language summary for the product owner: what is genuinely finished, what
is partial, what is still fabricated or unsourced, and what you would not personally vouch
for.

**A verification pass that finds problems is a successful verification pass.** One that
reports everything perfect will itself be audited.

```
git commit -m "test(verify): adversarial verification and regression sweep across phases 01-07

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.**
