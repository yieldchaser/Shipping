# Series verification ledger (measured 2026-09-28, unattended run)

Scope: the 98 stacked series CSVs + 1 workbook in `data/extracted/series/` that
`docs/EXTRACTION_REGISTER.md` counts as the finished product (273,254 rows). This run did not
re-extract anything; it tested the artefacts against the register's claims and against the
programme's own independent check.

## 1. Row counts: the register matches the artefacts

98 CSVs, **273,254 data rows**, exactly the register's declared total. Every per-file count in
the register's inventory matches the file it names. (Claim verified, not assumed.)

## 2. Cross-report agreement (the only independent proof of a merge)

Computed from each merged file's own `n_reports` / `min` / `max` columns:

| file | multi-report keys | median spread | p90 | within 2% | verdict |
|---|---|---|---|---|---|
| ssy_capesize_index_series.csv | 5,827 | **0.264%** | 2.69% | 87.4% | PASS - reference implementation |
| ism_handy_freight_series.csv | 6,176 | 0.223% | 20.59% | 69.1% | tail defect, see `docs/ism_agreement_tail.md` |
| ism_coaster_freight_series.csv | 6,802 | 0.341% | 43.34% | 74.3% | tail defect, same |
| intermodal_baltic_tc_series.csv | 20,186 | **59.34%** | 141.3% | 3.2% | FAIL - see `docs/intermodal_baltic_series_verdict.md` |

The other 94 files carry one row per (key, date) and no repeat statistics, so this gate cannot
be run on them from the artefacts alone.

## 3. Continuity check (previous value vs the nearest prior issue)

An independent cross-report check available on the 11 files that carry a "previous" column:
the value labelled previous in issue N should equal the value labelled current in the nearest
earlier issue for the same key.

| file | prev rows | resolved | within 1% | median err |
|---|---|---|---|---|
| bancosta_freight_rates_series.csv | 25,518 | 24,104 | 87.4% | 0.00% |
| bancosta_fx_series.csv | 941 | 936 | 95.0% | 0.00% |
| bancosta_vhss_series.csv | 3,353 | 2,191 | 76.0% | 0.00% |
| bancosta_ffa_series.csv | 7,655 | 7,030 | 23.8% | 2.73% |
| bancosta_commodities_series.csv | 1,934 | 344 | 11.0% | 29.00% |
| intermodal_tc_rates_series.csv | 5,068 | 4,963 | 91.2% | 0.00% |
| intermodal_maritime_stocks_series.csv | 3,047 | 3,013 | 90.0% | 0.00% |
| intermodal_macro_series.csv | 3,641 | 3,624 | 49.0% | 1.04% |
| intermodal_newbuilding_prices_series.csv | 3,134 | 2,506 | 67.7% | 0.00% |
| carriers_indices_series.csv | 639 | 634 | 84.4% | 0.00% |
| carriers_tanker_tce_series.csv | 761 | 755 | 84.0% | 0.00% |

**Caveat, stated plainly:** the word "previous" does not mean the same interval in every
source (prior week, prior month, prior curve date). A low score is therefore a **candidate for
a per-source semantics check, not a proven defect** - bancosta_ffa and bancosta_commodities
are the two to check first. Six of eleven score 84-95% at 0.00% median error, which is
consistent with correct extraction and a correct key.

## 4. Defects found by this sweep

1. **intermodal chart series superseded** - 20,348 rows, held data, 25-53% off the feed.
   `docs/intermodal_baltic_series_verdict.md`.
2. **ism agreement tail** - 2,269 of 12,978 repeat readings (17.5%) disagree by >10%; the key
   omits the panel entity. `docs/ism_agreement_tail.md`.
3. **Exact duplicate rows** in 10 files (rows identical in every column):
   bancosta_commodities 106/2,319 · intermodal_indicative_values 75/2,409 ·
   intermodal_tc_rates 48/5,068 · bancosta_vhss 15/3,413 · bancosta_freight_rates 14/25,715 ·
   xclusiv_sales 5/5,713 · poten_top_charterers 2/755 · star_asia_deals 2/3,327 ·
   star_asia_ferrous_scrap 1/771 · carriers_sales 1/3,004. Each is a double count downstream.
4. **Fake dates `2026-00-00`** - 226 rows that parse as ISO but cannot be placed in time:
   intermodal_macro 92 · intermodal_maritime_stocks 72 · intermodal_bunkers 54 ·
   xclusiv_bulk_carrier_charts 8. A nulled date written as a zero month is worse than a blank.
5. **star_asia_deals_series.csv has two mis-typed date columns**: `arrival_date` is European
   `DD.MM.YYYY` (708 distinct values, e.g. `13.06.2025`), so any ISO-based join silently drops
   all 2,727 of them; `beaching_date` holds free-text STATUS, not dates - 901 rows read
   `AWAITING`, 24 `ARRESTED`, 17 `AWATIING` (the source's own typo).

## 5. Not verified / limits of this run

- No image/vision tool exists in the cron session, so "render and look" was substituted with
  the same-document text reconciliation (intermodal verdict, section 5). Say so rather than
  implying a look happened.
- The agreement gate in section 2 could only be run on the four files that carry repeat
  statistics. A per-source gate for the other 94 would need the mergers re-run with the
  statistics retained - that is the highest-value next verification step.
- Section 3 scores are upper-bound-sensitive to each source's own "previous" semantics.

## 6. Reproduce

```
python3 scratch/measure_agreement.py   # the gate, on the 4 files that carry min/max
python3 scratch/continuity_sweep.py    # section 3
python3 scratch/dup_sweep.py           # section 4.3
python3 scratch/baddate2.py            # section 4.4
python3 scratch/score_all_indices.py   # intermodal chart series vs the held feeds
```

## 7. Internal consistency sweep: does each file's change column equal current - previous?

Run over every series CSV carrying a (current, previous, change) triple, 20+ rows:
**11 files are 98.3-100% consistent** - bancosta_freight_rates (24,685 rows, 99.7%),
advanced_shipping_secondhand_matrix (7,968, 99.6%), bancosta_ffa (7,648, 99.1%),
intermodal_tc_rates (5,051, 99.9%), intermodal_maritime_stocks (3,118, 99.5%),
intermodal_demolition_prices and intermodal_demolition (1,996 each, 100.0%),
intermodal_baltic_indices (1,237, 99.8%), intermodal_currencies (652, 98.9%),
carriers_dry_weighted_routes (605, 98.7%), carriers_indices (638, 98.3%).
**Four files are not:**

1. **intermodal_indicative_values_series.csv - one-column shift on 295 rows.**
   The report prints `| Capesize | 180k | 37.5 | 37.1 | 1.0% | 27.6 | 31.1 | 36.1 |` (Vessel 5
   yrs old, Jul-21 avg / Jun-21 avg / +/-% / 2020 / 2019 / 2018). The series row is
   `current=180.0, prev_month=37.5, change=37.1` - the vessel SIZE was consumed as the price
   and the whole triple shifted one column left (implied change (37.5-37.1)/37.1 = 1.08% vs
   the printed 1.0%). Of 554 inconsistent rows, **295 fit the shift exactly**; the remaining
   259 (tanker table, other age profiles) are unexplained. The result looks plausible - 180 $M
   for a 5-year Capesize is high, not absurd - which is why no count-based check caught it.
2. **carriers_tanker_tce_series.csv - 510 of 768 rows.** `week_change` does not equal
   `current_value - prev_value`. The TCE family is scaled in thousands while the change is in
   units: `VLCC TCE 25.29 / 29.388 / -4098`, `SUEZ TCE 55.492 / 77.385 / -21893`. A
   1000x-class unit mix inside one row. The Baltic index rows in the same file are fine
   (`1373 / 1447 / -74`).
3. **intermodal_newbuilding_prices_series.csv - 893 rows (28.0%) have
   `price_previous_usd_m = 0.0`**, and `intermodal_newbuilding_series.csv` repeats the same
   893 rows (17.8%). A missing previous price written as a zero, not a blank: any derived
   percentage from it is undefined, and the register's own `pct_change` column sits beside it.
4. **intermodal_macro_series.csv - 1,290 of 3,739 rows** state a change that cannot be
   reproduced from `latest_value` and `prior_value` (`10year US Bond 1.431 / 1.48 / -6.8%` where
   the pair implies -3.31%; `CAC40 6552.86 / 6553.82 / -1.1%` implies -0.01%), and the change
   is **blank on 2,075 rows**. Either the printed change is over a different window than the
   prior column, or the columns are mis-paired.

**One flag was my own instrument, not a defect - recorded so nobody chases it.**
`intermodal_tanker_spot_series.csv` scored 3.8% because my checker paired `change_pct` with
`ws_points_current`; the report's change belongs to the TCE column (`VLCC 265k MEG-SPORE`:
WS 32/33, TCE -5195/-775, change -570.3% = the TCE pair). The file is correct.

---

# UPDATE 2026-09-28 ~12:4x - defect 4.2 (ism) is FIXED; re-measured

The ism merged series were re-keyed and rebuilt (no re-extraction). Full detail in
`docs/ism_series_fix_verdict.md`. Summary against this ledger's own gate:

| file | rows | p90 spread | within 2% | rows >10% |
|---|---|---|---|---|
| ism_coaster_freight_series.csv | 13,281 -> **12,319** | 43.34% -> **6.06%** | 74.3% -> **83.4%** | 1,233 -> **481** |
| ism_handy_freight_series.csv | 18,833 -> **17,629** | 20.59% -> **11.83%** | 69.1% -> **73.9%** | 1,036 -> **697** |

Two root causes, both in the merger, both measured:
1. the key omitted the panel ENTITY (as diagnosed in `docs/ism_agreement_tail.md`) - fixed by
   deriving the entity from the chart's own sibling labels;
2. **new finding** - multi-year COMPARATIVE charts plot several years on one repeating
   52-week x axis (154 points = 52+52+50 = 2021,2022,2023, confirmed by the chart's own tick
   labels), and the merger assigned the year from the week number alone, fusing three years
   onto one date. This was the larger of the two.
Also fixed: the 2,356 `% of freight costs in CFR price` rows carried unit `$/t`; now `%`.

**This ledger's section 1 counts are now stale.** Re-measured across `data/extracted/series/`:
**100 CSVs, 277,005 data rows** (was recorded as 98 CSVs / 273,254 rows). The ism change alone
removes 2,166 rows; the other files have grown since that count was taken.

Still open here: the residual ism tail (1,178 rows) is a DIFFERENT class - outlier reports
drawn on a different axis (e.g. `2023_W38` uses ticks `71,64,...,15` where every other report
uses `75,65,...,15`), plus some TCT route series. Not fixed, not dropped.


---

# UPDATE 2026-09-28 ~17:1x - defects 7.1 (intermodal one-column shift) and 4.3 (exact
# duplicate rows, intermodal) are FIXED

Fixed in `scripts/extract/publishers/run_intermodal_full.py` (rebuilt from the cached
LlamaParse markdown, no API spend) and verified. Full detail:
**`docs/intermodal_indicative_verdict.md`**.

| measure | before | after |
|---|---|---|
| `intermodal_indicative_values_series.csv` rows | 2,409 | **2,333** |
| exact duplicate rows | 75 | **0** |
| rows where `change` != (cur-prev)/prev | 554 (23.0%) | **10 (0.43%)** |
| prices equal to a vessel SIZE (180.0 / 82.0 / 63.0 / 37.0) | 537 | **0** |
| published `$0m` prices (from the literal `#DIV/0!` in the PDF) | 4 | **0** (NULL) |
| empty prev-month values | 0 (they were WRONG) | **0** (14 recovered from the page text) |
| `intermodal_tc_rates_series.csv` exact duplicates | 48 | **0** (5,068 -> 5,020 rows) |

Independent check: for 24 documents across 2021-2026, the extracted value tuple was
found as a consecutive numeric run in the PDF's OWN text layer in 219/219 rows (100%).
The remaining 10 inconsistent rows differ by 0.26-0.31 pp = the publisher's own
one-decimal rounding, not a defect. Four rows keep a size-less key (`LR1`, `MR`) because
the source markdown has no size cell for them - values right, label short, not guessed.

Also settled: this file's 4 `#DIV/0!` rows show the publisher's spreadsheet error is
rendered INTO the PDF, so no value exists on the page for those cells - NULL is correct.


---

# UPDATE 2026-09-28 ~18:4x - defect 7.3 (intermodal newbuilding prices) FIXED; the
# ledger's own diagnosis of it was WRONG and 5x too small

7.3 was recorded here as "893 rows (28.0%) have `price_previous_usd_m = 0.0`". Measured
against the cached LlamaParse markdown, the real defect is a **one-column left shift on
every row of the file**: `vessel_type` held the vessel SIZE (the name was dropped),
`size` held the current price, `price_current` held the previous, `price_previous` held the
printed ±%, and `pct_change` held the 2020 average. The `0.0` that was noticed was just the
±% of an unchanged price - which is why a count-based check saw a "missing previous" rather
than a shift. 1,603 of the 3,194 rows were still internally consistent (when prev == cur the
shift adds up), so every gate passed.

| measure | before | after |
|---|---|---|
| `intermodal_newbuilding_prices_series.csv` rows | 3,194 | **3,134** |
| `vessel_type` holding a size/price instead of a name | 1,408 | **0** |
| blank `previous` | 60 | **0** |
| (cur, prev, pct) self-consistent | 1,603 | **3,112** |
| `intermodal_newbuilding_series.csv` rows | 5,027 | **4,967** |

Verification: the `(current, previous)` pair was found as a consecutive numeric run in the
source PDF's OWN text layer in **3,132 / 3,134 rows = 99.94%** (252 docs). The 2 misses are
one comma-decimal issue (value correct) and one genuine single-cell loss
(`intermodal_2024_W31` VLCC `previous` 129.5, should be 129.0 - reported, not patched).
Control: all 10 other intermodal series CSVs byte-identical. Full evidence:
**`docs/intermodal_newbuilding_verdict.md`**. Also fixed in the same pass: a malformed
`<td` repair that had been losing 2021_W38's whole table, and 40 mislabelled sector rows.

**Lesson for this ledger: a "missing value written as a zero" is a symptom to re-measure,
not a diagnosis.** The same shape of error (a plausible one-column shift) has now appeared
twice in this source - see 7.1 and this one. Before fixing a "missing/zero" defect, print
the source row next to the published row.


---

# UPDATE 2026-09-28 ~19:0x - defect 7.2 (carriers TCE) is NOT an extraction defect.
# Verified against the page. Do not "fix" it.

The ledger recorded 7.2 as "510 of 768 rows where `week_change` != `current - prev`; a
1000x-class unit mix inside one row". That is a correct description of the FILE, but it is
**not an extraction error** - the publisher prints exactly those numbers. Read from
`corpus/01-brokers/carriers/2023/carriers_2023_W46_WK-46-23-CARRIERS_SP-MARKET-REPORT.pdf`,
page 2, "Wet Baltic Indices & TCE Full Route plus Baltic LPG":

```
                 This WK     Week Ch.   Previous
Baltic DIRTY          1373         -74       1447
Baltic CLEAN           785           3        782
VLCC  TCE in $      25.290       -4098     29.388
SUEZ  TCE in $      55.492      -21893     77.385
AFRA  TCE in $      68.497       -1035     69.532
MR ATLANTIC in $    34.805        6018     28.787
LPG Index           14.766         200     14.566
```

Every published value is the printed value, to the digit. The mismatch is the publisher's
own: the TCE columns are in $000/day (25.290 = $25,290/day) while its `Week Ch.` is in
$/day (-4098), and the Baltic index rows are unitless. `25.290 - 29.388 = -4.098` x 1000 =
-4098 exactly, so the row is internally coherent once the unit switch is understood.

**Verdict: CLOSED as faithful.** The value is not wrong, so there is nothing to correct.
If the mixed unit is a problem downstream, the fix is an explicit unit column (or a
normalised change column added BESIDE the printed one), never a rewrite of the printed
value. Recommend not spending extraction time here.

# Re-measured this run (still open)

* 4.4 fake dates: **230** rows, not 226 - intermodal_bunkers 54, intermodal_macro 92,
  intermodal_maritime_stocks 72, xclusiv_bulk_carrier_charts 8, **xclusiv_demolition_charts 4**
  (the last file was not in the original sweep).
* 4.5 star_asia_deals_series.csv: `arrival_date` is European `DD.MM.YYYY` on **2,680 of its
  2,727** non-empty values; `beaching_date` holds STATUS text on 557 distinct values
  (AWAITING 901, ARRESTED 24, the source's own typo AWATIING 17, plus real dates).
  Both confirmed real.

---

# CLOSED 2026-09-28 21:31 IST - 4.5 star_asia_deals date columns FIXED (supervisor 345bc8db9233)

`docs/star_asia_deals_dates_verdict.md` has the full evidence. Headline: the defect was REAL
but the extractor was FAITHFUL (77/77 non-canonical values appear verbatim in the source PDF
text layer, and a same-page glyph-advance control on the 63 unparseable ones shows no dropped
glyph - the publisher's own page prints `05.02.206`). Fix = reformat only.
4,417 date cells are now ISO-joinable (was 0); 966 cells typed as STATUS; 63 unparsed and
quarantined in `data/extracted/audit/star_asia_deals_dates_quarantine.json`; 6 empty.
Independent verifier `scripts/extract/verify_star_asia_deals_dates.py`: PASS - 3,327 rows
unchanged, 39,924 context cells byte-identical, 0 raw-vs-old mismatches.
Still open in this ledger: 4.4 fake dates (230 rows, re-measured) and 4.3 intermodal_macro.

---

# CLOSED 2026-09-28 21:2x IST - 4.4 (fake dates) FIXED, and re-diagnosed: the fake rows were the
# SMALLER half. Full evidence: `docs/intermodal_issue_date_verdict.md`

4.4 was recorded as "230 rows with a fake `2026-00-00`". Measured against the publishers' own
cover lines, the same builders had also written a **wrong** date on 251 further rows: their date
parser searched the report's BODY PROSE instead of its cover.

| before | rows | wrong date | fake `2026-00-00` |
|---|---|---|---|
| intermodal_bunkers / macro / maritime_stocks | 9,118 | 109 | 218 |
| intermodal_demo_sales / demolition_prices / newbuilding_orders | 4,379 | 142 | 0 |
| xclusiv_bulk_carrier_charts / xclusiv_demolition_charts | 498 | 0 | 12 |

Three root causes, one per builder:
1. `run_intermodal_full.py` - loose `LONG_DATE_RX` over pages 0-1 matched body prose
   ("On Friday, February 9th, the BDTI settled at..."), so 9 documents were mis-dated. Worst:
   `intermodal_2022_W06` shipped **2021-10-07** (cover: 15 February 2022) and
   `intermodal_2023_W08` shipped **2025-03-31** (cover: 28 February 2023).
2. `run_intermodal_finance.py` - same loose regex, and a literal `"2026-00-00"` fallback.
3. `run_xclusiv_vector_charts.py` - accepted only the `YYYY_MM_DD` filename form; xclusiv names
   files `DD_MM_YYYY`, so it fell through to `"2026-00-00"`.

Fix: the publisher's own cover line (`Week NN | <Weekday><D><ord> <Month> <YYYY>`, present and
unique on page 0 of **252/252** intermodal reports) is parsed FIRST, then the filename, then loose
text; an unknown date is written BLANK, never a zero month. The cover outranks the filename (one
document's filename says `23_09_2026` while its cover says 22 September 2026). Three orphan series
(`intermodal_demo_sales`, `intermodal_demolition_prices`, `intermodal_newbuilding_orders`) had no
current writer and were stale to 2026-09-27; they are now written by
`build_all_series_from_sidecars()` with the same rule. No API spend (cached markdown).

**Verification: 40,636 / 40,636 intermodal rows across 16 series now carry `issue_date` == the
document's own cover line (0 wrong, 0 fake); `report_week` == the cover's `Week NN` on 252/252.
Control: 110 of 119 series CSVs byte-identical (md5), only the intermodal files differ.
Row counts unchanged vs the ledger (tc_rates 5,020 / indicative_values 2,333 / ... ).**

One count MOVED and it is explained, not drift: `intermodal_newbuilding_orders_series.csv`
1,786 -> **1,833**. All 1,833 rows are present in the union file
`intermodal_newbuilding_series.csv` (1,833 `reported_order` rows); the old split file was 47 rows
short of the union. The two are now consistent.

**Lesson: `2026-00-00` was the visible tip. The dangerous half was 251 rows carrying a plausible
ISO date lifted from body prose - invisible to every count-based check. When a fake-date defect is
found in a source, re-derive EVERY date in it from the publisher's own cover; do not just blank
the fakes.**

---

# CLOSED 2026-09-28 21:31 IST - 4.4 fake dates: the COUNT does not reproduce, the real 12 are fixed

`docs/xclusiv_charts_dates_verdict.md`. Measured across **119 series CSVs / 334,358
date-shaped cells**, only **12** calendar-invalid date cells ever existed, all `2026-00-00` in
`xclusiv_bulk_carrier_charts` (8) and `xclusiv_demolition_charts` (4). The **218 rows this entry
attributed to intermodal_macro (92) / intermodal_maritime_stocks (72) / intermodal_bunkers (54)
are not in those files** - all three are 100% well-formed ISO on 3,739 / 3,119 / 2,260 rows,
and the read-only corpus DB has no `2026-00-00` in any date column. State the population before
believing a count. Fixed 12 fake + 4 WRONG dates (a plausible `2025-12-10` on
`xclusiv-2026_04_20.pdf`) and a second defect the entry missed: `report_week` was `0` on all
498 chart rows. Verifier `scratch/sup/verify_xclusiv_charts.py` = PASS; 0 invalid dates remain
corpus-wide. Still open: 4.3 `intermodal_macro_series.csv` (change not reproducible on 1,290 of
3,739 rows, blank on 2,075 - VERIFY against the page before fixing).

---

# CLOSED 2026-09-28 22:1x IST - 4.3 intermodal_macro_series.csv FIXED (real defect)

The ledger called it "1,290 of 3,739 rows whose stated change is not reproducible from
latest/prior, blank on 2,075". Re-measured: 1,379 non-reproducible, 2,075 blank. The real
defect was **every POSITIVE change being silently dropped**: 2,075 blanks, and of the 1,664
survivors **0 were positive**, while the publisher prints a change on essentially every row.

Root cause: the macro regex's greedy middle group `(?:[\s\n]+[0-9.,]+)*` swallowed a bare
positive number (`1.7%`), leaving `%` with no preceding whitespace so the trailing
`([-+]?[0-9.]+%)` group never matched. A negative change survives only because `[0-9.,]+`
cannot start with `-`. A second fault: a value cell can be TEXT (`mrkt closed` 23x,
`market closed` 3x, `mrkt close` 1x), which stopped the number-only scan mid-row.

Fix = content-anchored row parse (anchor on the label + the next cell being a value; read
forward to the `%` cell, skipping text value cells). NONNUM derived from the corpus, not guessed.

| measured | before | after |
|---|---|---|
| rows | 3,739 | 3,739 |
| blank wow_change_pct | 2,075 | **0** |
| positive changes | 0 | **2,061** |
| latest_value changed | - | 0 |
| prior_value changed | - | 6 (all `''` -> a value printed on the page) |
| change strings verbatim in source page text | 1,664/3,739 | **3,739/3,739** |

Control: 125 of 126 series CSVs byte-identical; only macro differs. Key diffs vs a pre-run
snapshot are the earlier 4.4 date fix, not this change.
Cross-document control: the printed W-O-W reconciles with the previous report's own Friday
close on **3,160/3,447 = 91.7%** (95-100% for 12 of 16 indicators). **Nikkei 52% and Xetra Dax
57% fit NO reference hypothesis** - their values and changes are verbatim on the page, so that
is a publisher-side inconsistency, left as printed.
Evidence: **`docs/intermodal_macro_verdict.md`**. Nothing open in this ledger's defect list
except the residual ism agreement tail.


---

# CLOSED 2026-09-29 00:2x IST - section 3's two "check first" files: FFA is FAITHFUL, COMMODITIES was badly mis-parsed (FIXED)

`docs/bancosta_commodities_verdict.md` has the full evidence.

**`bancosta_ffa_series.csv` - not a defect.** Its 23.8% continuity score is the publisher's:
the printed `previous` column does not reproduce the prior issue's own `current` column
(`2021_W26` prints `Aug-21 2-Jul=31,643`; `2021_W27` prints `Aug-21 2-Jul=37,107` - a 17%
restatement of the same date). Both sidecars store their own page verbatim. A column swap is
ruled out: `sign(current-previous)` matches the printed W-o-W on 7,475/7,500 rows (99.67%).
The file was NOT touched (byte-identical).

**`bancosta_commodities_series.csv` - a real defect, 55% of rows affected.**
The parser assumed every commodity row carries a leading category cell. BUNKERS does
(`<cat>|<item>|<unit>|...`); OIL & GAS / AGRICULTURAL / COAL / IRON ORE & STEEL do not
(`<item>|<unit>|...`) - so those rows shifted one column right and lost the item label.
Page 12 of `2022_W02` prints `Crude Oil Shanghai | rmb/bbl | 533.4 | 515.7 | +3.4%`; the
sidecar stored `item="rmb/bbl", unit=533.4, current=515.7, previous="+3.4%"`. Two more faults
in the same path: the branch gate matched the word "category", which is the header of the
commodity CHARTS (`| Category | Date | Value |`), so chart points were parsed as prices; and
the eras whose price header is `| BUNKERS | Unit | ... |` never matched the gate at all, so the
real table was filed into `freight_benchmarks` as `sector="DRY_BULK"`.

Fix = unit-cell anchor (layout-independent), gate on "unit"+"w-o-w", block name from header /
heading context / real Category column, numeric-current requirement, per-document dedupe.
Rebuilt from cached markdown - no API spend.

| measure | before | after |
|---|---|---|
| commodities rows | 2,319 | **8,435** |
| numeric `unit` (shift signature) | 1,285 | **0** |
| `%` in `price_previous` | 611 | **0** |
| empty `price_current` | 273 | **0** |
| chart-axis junk rows | 984 | **0** |
| exact duplicates | 106 | **0** |
| `category=GENERAL` | 1,297 | **33** |
| freight_rates rows | 25,715 | **20,329** |

Controls: 2022_W02 page-12 values 4/4 exact against the printed text; the unmodified parser
reproduces the on-disk sidecars byte-exact; **2 of 132 series CSVs changed, 130 byte-identical**;
every genuine freight sector count unchanged (Capesize 6/6, Panamax 6/6, Supramax 19/19,
Dirty 28/28, Clean 27/27); 2023 and 2024 documents went from **0 to 35** commodity rows each.

**Still open in this source (measured, not fixed):** 93 FFA rows whose `tenor` is a currency
pair; 60 FFA rows with a `%` in `rate_previous` (32 from `2026_W19`); 33 numeric `unit` values
and 80 `DRY_BULK` rows left in freight_rates.


---

# CLOSED 2026-09-29 01:2x IST - bancosta FFA/FX tier: the '93 currency-pair tenors / 60 % in rate_previous'
# leftovers re-measured to 5 causes and FIXED. Evidence `docs/bancosta_ffa_verdict.md`.

Root cause: the FFA branch gated on `ctx` alone and the heading tracker keeps h1='DRY BULK FFA ASSESSMENTS'
while h2/h3 move on, so the EXCHANGE RATES table and several CHART tables were parsed as FFA assessments.
Measured: 1,881 FFA-branch tables across 244 docs.

| measure | before | after |
|---|---|---|
| bancosta_ffa_series.csv rows | 7,659 | **7,618** |
| currency-pair `tenor` rows | 28 | **0** |
| curve-title `tenor` rows | 9 | **0** |
| blank-`unit` assessment rows | 4 | **0** |
| 2026_W19 rows read one column left | 32 | **0** (32 corrected, verbatim 32/32) |
| bancosta_fx_series.csv rows | 941 | **968** |
| docs missing from the FX tier (of 236 with a CURRENCIES table) | 7 | **0** |
| junk `currency_pair` values | 1 | **0** |

Control: 19/245 sidecars changed, diff confined to ffa_assessments / currencies / chart_series;
**8 of 10 series CSVs byte-identical**. Rebuilt from cached markdown - no API spend.
Left verbatim (page-side, not repaired): 2025_W30's 32 garbled tenor labels; 2026_W19's corrected rows
carry a blank tenor because the page read has no tenor column.
STILL OPEN: the bancosta freight_rates residue (numeric unit / DRY_BULK, branch 11).


---

# RE-CONFIRMED 2026-09-30 11:0x IST - the last two "open" items in this ledger were ALREADY CLOSED; their pointers were stale

Read the file, do not re-chase. Both were verified by MEASUREMENT today, not by the note.

**4.5 `star_asia_deals_series.csv` - CLOSED (was closed 2026-09-28 21:31).** Measured on the
current file (3,358 data rows, 20 columns): `arrival_date` ISO **2,708**, of the old European
shape **0**, other/status **0**, blank 650; `beaching_date` ISO **1,747**, old shape **0**,
blank 1,611 - the status text now lives in `beaching_date_status` (AWAITING 958, ARRESTED 24,
BEACHED 1, NIL 1, blank 2,374) where it belongs. 63 values the publisher printed with an
impossible year (e.g. `29.02.2022`) stay blank and are inventoried in
`data/extracted/audit/star_asia_deals_dates_quarantine.json` with page evidence.

**4.3 `intermodal_macro_series.csv` - CLOSED (was closed 2026-09-28 22:1x) - and its premise is
wrong by design, which is worth knowing before anyone "fixes" it again.** The file's
`prior_value` is the page's SECOND SESSION COLUMN (`1-Jul-21`), while the publisher's
`W-O-W Change %` column is week-over-week. An independent check today: of 3,739 rows,
**2,833 (75.8%)** do not reproduce the printed % from `latest_value`/`prior_value`, and
**0** have a blank change - i.e. the mismatch the ledger flagged is the COLUMN SEMANTICS, not
extraction loss. Tested against the real base: the printed % reproduces from the SAME
INDICATOR'S LATEST in the PREVIOUS REPORT on **3,266/3,723 = 87.7%** of consecutive-report
pairs, and on exact 7-day report gaps **3,149/3,383 = 93.1%**. The residual is concentrated
where the gap is 14 or 21 days (175 + 47 pairs), where the true base is a report we do not
hold - not an extraction error. Opposing control: my probe on the page's own five value
columns reproduces the printed % on **1/795** rows, which rules out "the change is computed
from two of the printed sessions". `docs/intermodal_macro_verdict.md` has the extraction-side
history. **Do NOT rewrite `latest_value`/`prior_value` to force reproduction.**

## Section 2 numbers are STALE - re-measured with the ledger's own instrument

`python3 scratch/measure_agreement.py`, run today:

| file | multi-report keys | p50 spread | p90 spread | within 2% | ledger said |
|---|---|---|---|---|---|
| ssy_capesize_index_series.csv | 5,728 | 0.263% | 2.72% | **87.1%** | 87.4% |
| ism_handy_freight_series.csv | 6,169 | 0.181% | **11.76%** | **74.1%** | p90 20.59%, 69.1% |
| ism_coaster_freight_series.csv | 5,927 | 0.293% | **5.67%** | **83.7%** | p90 43.34%, 74.3% |
| intermodal_baltic_tc_series.csv | 20,186 | 59.34% | 141.30% | 3.2% | unchanged (held-data verdict stands) |

The ism re-key fix bought far more than section 2 recorded: handy's p90 fell 20.59 -> 11.76 and
coaster's 43.34 -> 5.67. **The residual tail is now the only open item in this ledger**
(within-2% 74.1% and 83.7%): it needs the failing reports NAMED and read, not a re-run of the
gate.
