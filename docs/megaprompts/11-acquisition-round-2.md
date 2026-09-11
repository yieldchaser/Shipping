> # ⛔ SUPERSEDED — DO NOT EXECUTE THIS PROMPT
>
> **Replaced by `13-scraper-targets.md`, which was written after executing the endpoints
> rather than reasoning about them.** Every job here is covered there with verified URLs and
> real response data.
>
> This file is kept only for its audit trail. **It contains claims now known to be false:**
> - "The file's other columns (VLCC, Suezmax, Aframax, 1-yr TCs, bunkers) run the full
>   2018-05 → 2026-09" — **false.** Nine tanker series are dead since **2023-05-22**.
> - "Backfill C3/C5/Newcastle to 2018" — **understated.** C3 reaches **1998-05-06** (7,085
>   rows), C5 **1999-03-01** (6,877 rows).
> - `last=2600` — **not the ceiling.** Omitting `last` entirely returns the full series.
> - It does not mention that six series in that file are **mislabelled by vessel class**,
>   which is a live UI bug (see Prompt 13 Target 1A).
>
> Job mapping into Prompt 13: A→T2 · B→T11 · C→T3 · D→T4 · E→T1 · F→T10.

---

# PROMPT 11 — ACQUISITION ROUND 2 (SUPERSEDED)

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-11-acquisition.md`
> Depends on: Prompt 10 (staleness fields must exist before you can prove improvement).

Prompt 02 attempted acquisition. Some of it worked; several jobs were reported complete
while delivering thin or stale files. This phase finishes them, measured against
`data_through` rather than "the script ran".

**Definition of done for every job: `data_through` within SLA, and depth sufficient for a
5-year seasonal envelope (i.e. ≥ 60 monthly points or ≥ 260 weekly points).**

---

## JOB A — Guinea bauxite ★ still effectively unsolved

Current state on disk: `data/commodities/guinea_bauxite_exports.csv` = **24 rows,
2023-01 → 2024-12, 648 days stale**. `un_comtrade_guinea_bauxite.csv` is the same 24 rows.
That is not enough for a seasonal envelope and it is nearly two years old.

The UI currently renders a "MIRROR TRADE FLOW" series with an honest
`⚠ Official Direct Conakry Customs Series: UNAVAILABLE` card. **The honesty is correct and
must be preserved** — the goal is to make the mirror series deep and current, not to fake
the direct one.

Work the mirror properly:
1. **UN Comtrade, China as reporter** — `https://comtradeapi.un.org/data/v1/get/C/M/HS`,
   reporterCode `156`, flowCode `M`, partnerCode `324`, cmdCode `260600`, freq `M`.
   Pull **2017-01 → latest available**, not 2023-2024. Comtrade monthly typically lags
   2–3 months; that is expected and fine — record it as the SLA.
2. If the free tier truncates, page year by year and concatenate. Record every call.
3. **Cross-check against a second reporter**: India (`699`) and UAE (`784`) also import
   Guinean bauxite. A three-reporter mirror is materially more credible than one.
4. **Guinea EITI** — `https://opendataitie-guinee.org/` — for annual totals to sanity-check
   the mirror's level. Annual-only is fine as a validation series; register it separately,
   never blend it into the monthly line.

Deliverable: ≥ 96 monthly points, `data_through` within 100 days, per-row `source` and
`reporter` columns.

---

## JOB B — Brazil ComexStat ★ incomplete, reported complete

Current: **124 rows, 2024-01 → 2026-07, 71 days stale.** Prompt 02 asked for
**full monthly history 2017-01 → present**. That did not happen.

1. The endpoint works — the file exists and is real. Re-run it with the full period range
   `201701` → current month. If the API caps the window, loop year by year.
2. Pull **all four NCM groups in the same run**: iron ore `2601`, soybeans `1201`,
   corn `1005`, and sugar `1701` (Brazil is the top sugar exporter and it is a real
   Supramax/Handy driver we currently ignore entirely).
3. Record both `metricKG` and `fobValue` so the tab can show volume *and* value.

Deliverable: ≥ 110 monthly points per commodity, `data_through` within 45 days.

---

## JOB C — Australia Port Hedland ★ 132 days stale

`australia_ppa_iron_ore.csv` ends **2026-05-01**. Port Hedland is ~43% of global seaborne
iron ore; a four-month hole here is the single most damaging staleness in the repo.

PPA publishes monthly throughput as a press release (no API) — the pattern is documented in
`docs/Newest Data/Maritime_Data_Discovery_Report.md` §1.1. Re-run the scraper for
2026-06, 2026-07, 2026-08 and fix whatever broke it. If the page structure changed, say so
and fix the parser rather than backfilling by hand.

**Also add Dampier** (Rio Tinto) — currently only Hedland is captured, and Dampier is the
second Pilbara gateway.

---

## JOB D — USDA grain queues ★ six years stale

`usda_grain_vessel_loading_queues.csv` ends **12/31/2020**. Meanwhile
`usda_grain_vessel_loading.csv` is current to 2026-08-13. Two files, same subject, one
abandoned.

Decide and record: either the queues file is superseded by the loading file (then mark it
`NOT_RENDERED — superseded`, and fix the Cargo tab title that claims 1995–2026), or its
source still publishes and the scraper broke (then fix it). **Do not leave a dead file
rendering behind a LIVE badge.**

Same decision for `usda_us_vs_brazil_landed_costs.csv` (ends 12/31/2025).

---

## JOB E — Baltic route rates depth ★ new finding

`data/clarksons/fearnleys_benchmark_rates_continuous.csv` genuinely contains the Capesize
route benchmarks — **this was verified and is current**:

| Route | tsId | Latest value (2026-09-09) |
|---|---|---|
| Tubarão/Qingdao Capesize Iron Ore **C3** | 10001 | **$41.92 /t** |
| Australia/China Capesize Iron Ore **C5** | 10002 | **$18.735 /t** |
| Newcastle/Qingdao Capesize Coal | 10003 | **$24.031 /t** |

**But depth is only 260 of 1,158 rows — actual span 2025-08-27 → 2026-09-09, about one
year.** The file's other columns (VLCC, Suezmax, Aframax, 1-yr TCs, bunkers) run the full
2018-05 → 2026-09. The dry-bulk route columns were added later and were never backfilled.

Backfill C3/C5/Newcastle to 2018 via the Fearnpulse time-series endpoint already documented
in `docs/MARITIME_INTELLIGENCE_MASTER_DISCOVERY.md` §10:
`https://fearnpulse.com/api/marketapi/TS?last=2600&id={tsId}` with
`Referer: https://fearnpulse.com/fearnleys-weekly-report`.

This matters because Prompt 07's flagship Origin→Freight module pairs cargo volume against
these routes. With one year of rate history the seasonal envelope on the rate side is
impossible.

**Correction to record:** earlier specs implied these columns already spanned 2018–2026.
They do not. Fix the claim wherever it appears.

---

## JOB F — Sugar, fertiliser, bauxite alumina: the missing minor bulks

The Signal taxonomy covers 154 dry-bulk nodes; we hold volume series for roughly eight.
Prompt 07 Phase 7.5 built the fixture-derived matrix to cover the rest, which is the right
primary answer. Add national series only where tonnage is large and fixtures are thin:

| Commodity | Source to test | Why |
|---|---|---|
| **Sugar** | Brazil ComexStat NCM 1701 (Job B) | top global exporter, Supramax/Handy driver |
| **Fertiliser / urea** | Comtrade HS 3102/3104, reporter India + Brazil (importers) | large Handy/Supra trade, currently zero coverage |
| **Alumina** | Comtrade HS 2818, reporter China | pairs with the bauxite mirror |
| **Steel** | World Steel Association monthly production (free) | Cape/Supra demand proxy |

Test each, report status, acquire only what returns real monthly data.

---

## Verify and stop

For every job, the ledger records: URLs called, HTTP status, rows retrieved, `data_through`,
`staleness_state`, and whether the ≥60-monthly-point depth bar was met.

**A job that fails and says so is a pass. A job that reports success with 24 rows is not.**

```
git commit -m "feat(data): acquisition round 2 - deepen guinea mirror, full brazil history, hedland backfill, C3/C5 depth

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print a before/after table: series → rows before → rows after → data_through before → after.
