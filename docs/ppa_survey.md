# PPA (Pilbara Ports Authority) - source survey (measured 2026-09-28)

Source: `corpus/09-ppa` - **493 PDFs**, 167 in `_root_pdfs/` (named) and 326 in
`ppa_pdf/` (sha1-named downloads of the same publication set).
Publisher: Pilbara Ports Authority. Cadence: monthly. Ports: Port Hedland + Port of Dampier.
Manifest group `09-ppa`, description "Pilbara Ports Authority throughput", status UNKNOWN.

## Three document families (measured by first-page text over all 493 files)

| family | docs | pages/doc | layout |
|---|---|---|---|
| A `Cargo Stats by Origin / by Destination` (Port Hedland) | **255** | 2 | **RULED GRID** - real stroke rects (212-428 per page) |
| B `PORT OF DAMPIER <FY> FINANCIAL YEAR CARGO STATISTICS` | **83** | 1 | **BORDERLESS** - no ruling lines; FY = July-June |
| C `Cargo, GRT and DWT Statistics by Commodity Group` (Port Hedland) | **152** | 5-10 (median 8) | borderless per-vessel register, 1 drawing/page |
| junk | 3 | - | see "Junk routed" below |

### Family A - the main monthly series
Two pages per document. Page 0 = **DISCHARGE** (origin), page 1 = **LOAD** (destination).
Table = countries (rows) x commodities (columns) with a printed **Total row AND Total
column**, in tonnes. 13 distinct commodity labels appear across the years; the column set
varies per month (only commodities with traffic are printed), and the 2024-05 file drops
the Total column entirely.

### Family B - Dampier financial year
One page, months (JULY..JUNE) x commodities, plus a printed **TOTALS: row**.
**19 of the 83 files have `page.rotation == 90`** (text drawn sideways) - word coordinates
must be passed through `page.rotation_matrix` or every row reads as a vertical smear.

### Family C - per-vessel register (NOT built this run)
152 docs, 5-10 pages, 2015-2026. Columns: Vessel, Arrival Date, Departure Date, Import
Volume, Export Volume, GRT, DWT, Destination/Origin Country, Cargo Complete. Roughly
20-30k vessel-level rows. No ruling lines. This is a genuinely missing grain (vessel-level
port calls) and needs its own measured pipeline - it is the next target for this source.

## Number convention
**ISO** (comma = thousands, period = decimal): `44,224,980.00`, `2,659.32`.
Confirmed against the printed page for 2020, 2021, 2024, 2025 and 2026 files.
No European-convention file was found in this source.

## Two traps specific to this source

1. **The reporting date is printed in BOTH conventions in the same document.**
   `Cargo Complete Date: 01/07/2026 to 31/07/2026` is D/M/Y while
   `Departure Date: 07/01/2026 to 07/31/2026` is M/D/Y. A third date also appears on the
   page - `Printed: pilbaraports\Rachael.Fahey, 8/10/2026 1:26:47 PM` - which is the PRINT
   timestamp and must not enter the vote. Resolve the month by anchoring on the reporting
   period line and taking the interpretation under which both endpoints share one month.
2. **Numbers are split across two text spans with a real gap**: `1` + `520,746` is
   1,520,746 and `1,` + `44,068` is 144,068. Concatenating cell fragments with a separator
   silently produces 1,520 and 1,44,068. Join fragments on the SAME line with no separator;
   join stacked header words ("Chemical" / "Compound") with a space.

## Three-baseline test - what is already ours

| baseline | finding |
|---|---|
| live feeds | `data/commodities/australia_ppa_iron_ore.csv` - 423 rows, `date, port, total_throughput_mt, iron_ore_exports_mt, destinations_t` for Port Hedland (133) and Port of Dampier (290), 2002-07 -> 2026-08, extracted from **these same PDFs** by `scripts/scrapers/fetch_ppa_iron_ore.py` / `fetch_australia_ppa.py` |
| our own extraction | none before this run |
| the app | `index.html` renders `hedland_ore_monthly` / `dampier_iron_ore_monthly_raw` / `pilbara_iron_ore.hedland_envelope` |

**Verdict: PARTIALLY_COVERED.** The IRON ORE + TOTAL slice is already held and displayed.
**Genuinely missing = the full commodity x country matrix** (Salt, Spodumene Concentrate,
Manganese Ore, Copper Concentrates, Containers, General, Chemical Compound, Hydrocarbon,
Acid, Primary Produce for Hedland; Salt, Condensate, LNG, LPG, Ammonia/Ammonium, General
Out/In, Petroleum, Diesel In for Dampier), for both LOAD and DISCHARGE, per month. That is
what the new runner produces.

## Junk routed (explicitly, not extracted)
* `_root_pdfs/ppa_dampier_wayback_..._appendix_1_figures_ed2012_000575_pdf.pdf` - an
  engineering drawing appendix (wharf expansion figures), misfiled under a stats folder.
* `_root_pdfs/ppa_hedland_commodity_latest.pdf` - a **Wayback Machine bot-wall placeholder**
  ("Keep the news in the Wayback Machine... Please Don't Scroll Past This").
* `_root_pdfs/test_download.pdf` - an **ASX site access/terms page** (HTML served as PDF).

All three are skipped by content check, never parsed.
