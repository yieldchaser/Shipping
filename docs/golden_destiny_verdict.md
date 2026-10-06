# GOLDEN_DESTINY (corpus/archive/golden_destiny) - extraction VERDICT

Measured 2026-10-06 source-by-source cron run (archive backfill source 2, after
allied). Branch `auto/extract-fixes-2026-10-06-deepreview`.
Runner `scripts/extract/publishers/run_golden_destiny.py` (per-source, self-contained).

## Headline
**252/252 documents extracted, 0 failures.** The `.md` tier is exact; the typed
prose-deal layer is best-effort with disclosed residuals.

| measured | value |
|---|---|
| documents | **252/252**, 0 failed (`_run_state.json`) |
| md files | 252 (`data/extracted/md/golden_destiny/<year>/`) |
| tables.json | 252 |
| md files < 1 KB | **0** |
| deal rows | **5,320** (`data/extracted/series/golden_destiny_sales_series.csv`) |
| distinct vessels | 4,911 |
| issue_date range | 2021-07-02 .. 2024-11-29, **170 distinct dates, 0 blank** |
| priced rows | 3,866 (`price_usd_m`), 724 "undisclosed price" |
| price_usd_m | min 0.47 / median 18.5 / max 213.0 |
| en-bloc group totals | 730 rows carry `group_total_mil` (max 1,050.0) |

## The .md is the primary deliverable - exact
`.md` = the full page text of each document. Fidelity = token recall of the PDF's
own text layer over a random 6-document sample spanning 2021-2024 and BOTH
classes (weekly report + special edition): **100.00% on all 6.** No vision tool in
this cron session - a same-document text-layer reconciliation, stated as such.

## Document classes
- `Weekly-SP-Market-Report` (~171 docs): prose deals.
- `Special-Edition-Weekly-SP-Market-Trends` (**81 docs**): 1-page aggregate stat
  cards -> captured in `.md`, **0 typed rows** (aggregate stats, not a deal
  series - same decision as allied's SnP-Statistics class).

## The typed deals layer - reconciled, conservative
Deals are PROSE: `NAME` / `<dwt> DWT BLT <yy> ...` / `SOLD ... US $<x> MIL TO
<buyer>` / a per-unit value. Verified against the printed page on the trial docs
(2021 W26, 2023 W20) and by construction rules:

- **EN-BLOC handled by the lion rule.** `$17.00 MIL EACH` -> that price per vessel
  (2023 W20 OLYMPIUS+VICTORIUS); a group total with several preceding vessels and
  no EACH -> `price_usd_m` left BLANK, the amount kept in `group_total_mil` (2023
  W20 SEA PROTEUS/PLUTO/VENUS = $70,5M). 730 rows are group totals.
- **0 blank vessel_name, 0 blank dwt / built, 0 blank price_raw, 0 blank date.**
- buyer blank on **30** rows: the source's SOLD line genuinely omits the buyer
  (e.g. `SOLD FOR ABT US $4.5 MIL` with the buyer on a following line). Left
  blank rather than guessed.

## Bugs the trial + verification caught and fixed (before trusting the output)
1. **Date** - cover line is `September 30th2022` (no space between ordinal and
   year); the separator was required. 160 rows were dateless -> fixed.
2. **Name** - `S SANTIAGO` (single letter + space) and `BASHUNDHARA LPG
   CHALLENG` fused to its spec line (`...CHALLENG53,677 DWT...`) -> name regex +
   same-line prefix extraction. 12 blank names -> 0.
3. **Buyer** - source writes `TOVIETNAMESE BYRS` / `TOUNDISCLOSED BYRS` (TO fused
   to the word); fixed the boundary.
4. **Section headers as deals** - `SECONDHAND TONNAGE SOLD FOR FURTHER TRADING`
   and `TONNAGE SOLD FOR DEMOLITION` matched the SOLD anchor and produced **58
   wrong rows** -> dropped (a section header now clears the pending buffer).
5. **Price phrasings** - `SOLD ENBLOC AT HIGH $ 60 MIL`, `ABT US 71.6 MIL`,
   `ABT 12,2 MIL` (no `US $`) were missed -> regex relaxed; blank `price_raw`
   21 -> 0.

Number convention is MIXED in the same document (comma-decimal `15,8`=15.8,
period-thousands `252.000`=252000, period-decimal prices `26.5`); parsed BY SHAPE.

## Known residuals (disclosed, not hidden)
- 30 rows with a genuinely buyer-less SOLD line (blank buyer).
- A few `RESP.`/`respectively` multi-price en-bloc lines (`$17.35 | $16.65 | ...`)
  cannot be mapped per vessel -> the safe group-total path is used (no wrong
  per-vessel price). One malformed `US $46 EACH MIL` line stays unpriced.
- 207 exact-duplicate rows collapsed (same doc+vessel+dwt+price; the parser can
  re-emit a name across a page break).

## Register
`sync_extraction_register.py` run -> CSV series count and rows updated;
`verify_registers.py` gate re-run.

## Liveness
Newest content 2024-11-29 (~675 d) -> **BACKFILL_ONLY**, never CONSTRUCT.
