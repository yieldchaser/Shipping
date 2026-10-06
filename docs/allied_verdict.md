# ALLIED (corpus/archive/allied) - extraction VERDICT

Measured 2026-10-06 source-by-source cron run. Branch auto/extract-fixes-2026-10-06-deepreview.
Runner `scripts/extract/publishers/run_allied.py` (per-source, self-contained).

## Headline
**203/203 documents extracted, 0 failures.** md tier exact; typed deals layer
best-effort with disclosed residuals.

| measured | value |
|---|---|
| documents | **203/203**, 0 failed (`_run_state.json`) |
| md files | 203 (`data/extracted/md/allied/<year>/`) |
| tables.json | 203 |
| md files < 1 KB | **0** (min 25,155 / median 36,969 / max 54,611 bytes) |
| deal rows | **3,218** (`data/extracted/series/allied_sales_series.csv`) |
| distinct vessels | 3,020 |
| issue_date range | 2021-07-04 .. 2024-02-16, 130 distinct dates, **0 blank** |

## The .md is the primary deliverable - exact
The `.md` is the full page text of each document. Fidelity checked by token
recall of the PDF's own text layer over a random 6-document sample spanning
2021-2023 and BOTH classes (SnP-Statistics + Weekly-Market-Review):
**100.00% recall on all 6** (1,865-5,646 tokens each). No vision tool in this
cron session - this is a text-layer reconciliation, stated as such (the skill's
substitute when no image tool exists).

## The typed deals layer - best-effort, reconciled
Every deal row's vessel NAME and PRICE token was checked to appear VERBATIM in
its own document's text (same-document reconciliation):

| field | verbatim | rate |
|---|---|---|
| vessel name (all tokens) | 3,214 / 3,218 | **99.88%** |
| price token | 2,426 / 2,427 | **99.96%** |

The 4 name misses are spaced-letter artifacts (`2`, `1`, `I`, `G R A`).

## Known residuals (disclosed, not hidden)
- **Container sub-tables** (`SUB`/`FEEDER` rows): the publisher prints TEU and
  Built as ONE token (`26642009`) -> `dwt` blank, `built` fused. These rows also
  carry no price (page prints N/A).
- **En-bloc rows**: the group price sits on the lead row; member rows show
  `each` with a blank price (same class as the lion verdict).
- 1 price row (`152,655 m`) where a capacity value bled into the price field.
- The SnP-Statistics class (dense aggregate tables) is captured in the `.md` but
  its nested sector tables are NOT parsed to typed rows (not needed: aggregate
  S&P statistics, not a deal series).

## Register
`sync_extraction_register.py` run -> **175 -> 176 CSV series**, rows
**630,393 -> 633,611**. `verify_registers.py` = ALL CHECKS PASSED (100.0%).

## Liveness
Newest content 2024-02-16 (~865 d) -> BACKFILL_ONLY, never CONSTRUCT.
