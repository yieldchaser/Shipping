# PROMPT 06 — BUNKERS: REAL HISTORY, HONEST CURVES, CHARTS NOT TABLES

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-06-bunkers.md`
> Depends on: Prompts 01, 02, 03 complete. **Job C of Prompt 02 must have reported back.**

---

## Context: what is wrong today

1. **The 12M Forward Curve is rendered as a table of 12 rows × 4 numeric columns.**
   A forward curve's entire meaning is its *shape* — contango, backwardation, the kink at a
   regulatory deadline. A table destroys that. Nobody reads a curve as numbers.
2. **All six hubs share an identical curve slope to five decimals** (m2/m1 = 0.95594–0.95595,
   m12/m11 = 0.99180–0.99182). Six independent fuel markets cannot do that. It is one
   modelled slope scaled per port. Prompt 02 Job C is resolving the provenance.
3. **It is a single snapshot from 2026-09-05** presented as live.
4. **The tab renders an 18 KB daily file** (`bunker_prices_daily.csv`) while
   `bunker_master_historical.csv` — **482,024 rows, 221 ports, 2018-02-12 → 2026-09-04** —
   sits unused.
5. **Layout strands whitespace:**
   ```
   bunkers-workstation 1360 × 807
   ├ left-pane   500 × 807  → table-wrap 498 × 660 (content 2764)  ← clipped
   └ right-pane  844 × 807  → chart-drawer 844 × 411  ← 396px dead space
   ```
6. **Averages are sold as places.** `APAC Average`, `Americas Average`, `EMEA Average`, and
   literally `Brent` and `EUA` are rows inside the "221 ports" table. The port count is
   inflated by non-ports.
7. **Unguarded outliers render raw** — Civitavecchia VLSFO `$275.00`, Djibouti MGO `$2175.00`.
8. **Sparklines are Unicode block glyphs** (`▁▁▁▁▁███▆▆▇▇`) in a text column.
9. Duplicate `bunker_forward_curves_12m.csv`, `bunker_physical_sales_volumes.csv` and
   `bunker_bix_macro_benchmarks.csv` are written to **both** the repo root and
   `data/bunkers/`. The root copies are strays — remove them and fix the writer in
   `bunker_pipeline/run_pipeline.py`.

---

## Design reference

`Inspiration/` screenshots 9234, 9236, 9239, 9241, 9243 show Ship & Bunker and BunkerIndex.
Take from them:
- **Grade tabs driving one chart and one table together**: `VLSFO | MGO | LSMGO | Biofuel |
  IFO380 | Scrubber Spread | MEOH | MEoH VLSFOe | MEoH MGOe`, with period tabs
  `1M | 3M | 6M | 1Y | 2Y | ALL`.
- **Regional averages kept structurally separate** from ports: Global 20 Ports Average,
  Global 4 Ports, Americas/APAC/EMEA — their own block, above the port table, never inside it.
- **`SPREAD` as a first-class column** alongside price/change/high/low.
- A **Top Ports** side rail showing VLSFO + MGO with deltas.
- A per-port page with its own price history chart.

---

## PHASE 6.1 — Layout and data foundation

- Replace fixed-height twin panes with CSS Grid, independent scroll, ≤48px trailing space.
- Rebuild the spot table on `bunker_master_historical.csv` (482,024 rows) via a Prompt 01
  view manifest. Keep the raw file for drill-down.
- **Separate averages from ports.** Regional and global composites move to their own block.
  `Brent` and `EUA` are not bunkering ports — move them to the Alt Fuels / carbon block.
  Recount and state the true port number; if it is not 221, say the real figure.
- **Outlier guard:** flag any price more than 3σ from that grade's 30-day cross-port
  distribution. Show the flag in the row, keep the value visible, never silently drop it.
- Replace Unicode sparklines with inline SVG.
- Remove the duplicate root-level CSV writes.

---

## PHASE 6.2 — The forward curve, resolved

Act on what Prompt 02 Job C found:

- **If SGX Marine Fuel 0.5% FOB Singapore futures were successfully ingested** — build the
  forward curve on that. Real exchange data with settle, open interest and volume, exactly
  as we already do for iron ore `FEF` / `M65F` / `LPF`. **Delete the modelled curve.**
- **If BunkerIndex genuinely publishes the single-slope model** — keep it, render it as a
  **line chart**, and label it precisely: *"BunkerIndex modelled curve — one slope applied
  per hub"* plus a prominent as-of date. Add a `MODELLED` badge in the Series Museum format.
- **If the stored file turns out to be an artefact of our own removed projection engine** —
  delete the subview entirely and show *"No forward curve source available"*. This is an
  acceptable outcome. An empty state beats a fake curve.

In every branch: **the curve is a chart, never a table.** Show the shape, mark contango vs
backwardation, and plot spot as the anchor point at M0.

---

## PHASE 6.3 — Subviews

Keep: **Spot Prices · 12M Forward Curves · Physical Volumes · Scrubber & EU ETS · Alt Fuels**

**Receive from SIGNALS:** *EU ETS Maritime Carbon (€/t CO₂) & Scrubber Hi-5 Fuel Economics*
→ merge into the existing **Scrubber & EU ETS** subview. Do not create a second panel; pick
the better implementation and record which won.

**Add a port detail view.** Click any port → its own price history across all grades, its
spread vs Singapore, its 7-day and 30-day change, its data span and source. This is the
Ship & Bunker per-port page pattern and it is the main thing the tab is missing.

**Scrubber spread as a first-class series.** VLSFO − HSFO is the single most important
derived number in marine fuel — it decides scrubber payback. Compute it per port, plot it,
and rank ports by it. Mark it `is_derived: true` in the provenance manifest with its inputs
named.

**Physical volumes** — `bunker_physical_sales_volumes.csv` plus the BunkerIndex Singapore
monthly sales indicator. Singapore is the global demand bellwether; give it a proper chart
with a seasonal envelope rather than a number.

---

## PHASE 6.4 — Tooltips and provenance

120 rich tooltips today, averaging 58 characters. Rewrite all to the Prompt 01 §1.5
standard. Specifically:
- Delete the boilerplate `"<div class='rt-title'>Control: Show All Ports</div>…Interactive
  control for this section…re-renders from cache"` template output.
- Every grade needs a real explanation: what VLSFO/HSFO/LSMGO/B24/MEOH *are*, why the
  0.5% sulphur cap matters, what the Hi-5 spread decides.
- Every price carries source + as-of.

---

## PHASE 6.5 — Verify and stop

```js
const b=document.getElementById('tab-bunkers');
({tiny:[...b.querySelectorAll('*')].filter(e=>e.innerText&&!e.children.length&&parseFloat(getComputedStyle(e).fontSize)<11).length,
  panes:[...b.querySelectorAll('[class*=pane]')].map(p=>({h:p.getBoundingClientRect().height,content:p.scrollHeight}))})
```
Plus: confirm no `Brent` / `EUA` / `*Average` row remains inside the port table.

```
git commit -m "feat(bunkers): 482k-row history, honest forward curve, port detail pages

- spot table rebuilt on bunker_master_historical (482,024 rows, 221 ports, 2018-2026)
- forward curve resolved per prompt-02 job C; rendered as a chart with explicit labelling
- regional/global averages separated from ports; Brent and EUA moved out of the port table
- scrubber spread (VLSFO-HSFO) promoted to a first-class per-port series
- per-port detail view with full grade history
- EU ETS + scrubber economics absorbed from signals
- outlier guard, SVG sparklines, grid panes, tooltips rewritten
- remove duplicate root-level bunker CSV writes

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print: the forward-curve branch taken and why, true port count, rows now wired.
