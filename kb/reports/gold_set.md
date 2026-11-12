# Gold Q&A set -- design note (PLAN 12.1, AGENT_TASK row 8)

* Purpose: 250-question held-out evaluation set for P7 answer scoring, spread over the
  eight plan strata (a 50, b 25, c 35, d 25, e 35, f 25, g 15, h 40).
* Generation is code-only: every question is a template filled with values read from
  `kb/state/kb.duckdb`. No LLM invents facts, so no answer can be hallucinated here.
* Every candidate answer is re-read from the database before the item is kept
  (`verification.checks` names the re-read); a candidate that cannot be reproduced is
  dropped, so set size can shrink rather than carry an unverifiable answer.
* Sources are recorded per item (observation id + doc_id + corpus path, transaction id,
  section id + filing path, or the absence proof for the unanswerable stratum), which is
  what P7 needs to score citations as well as answers.
* SEC XBRL was skipped upstream (no `SEC_USER_AGENT`, see `kb/reports/upstream_defects.md`),
  so the SEC stratum (e) is prose/section lookup from 10-K/20-F/10-Q/8-K/6-K filings
  instead of XBRL facts -- deviation D6.
* (d) is a temporal association (event date -> next 30 days of a market series), not a
  causal claim; it is judge-graded and the judge is told the association is temporal.
* (f) and (d) are judge-graded (`judge_only: true`); (a), (b), (g) carry numeric
  tolerances; (c) and (e) have exact string-set answers; (h) requires a refusal.
* Determinism: `sample_seed = seed_for("GOLD_SET")`; the seed is stored in the set and
  every report sample is drawn from it, so re-running the builder reproduces the same set.
* Cost: $0 (no paid model calls; DB reads only).

## Result

| stratum | description | target | built | verified | judge-graded |
|---|---|---:|---:|---:|---:|
| a_single_number | one verified observation value (exact match) | 50 | 50 | 50 | 0 |
| b_window_aggregate | mean over a contiguous window of observations | 25 | 25 | 25 | 0 |
| c_multihop_entity | vessel entity -> transaction -> the documents that reported it | 35 | 35 | 35 | 0 |
| d_event_market | transaction event date -> market series move over the next month | 25 | 25 | 25 | 25 |
| e_sec_section | SEC filing -> section heading that discusses a given term | 35 | 35 | 35 | 0 |
| f_summary_trend | start/end values and percentage change of a series window | 25 | 25 | 25 | 25 |
| g_as_known_on_date | latest known value as of a past date (published_at <= date) | 15 | 15 | 15 | 0 |
| h_unanswerable | question the corpus cannot answer; must be refused with a gap statement | 40 | 40 | 40 | 0 |
| **total** |  | **250** | **250** | **250** | **50** |

- sample_seed: `2888775339`
- built_at: 2026-11-12T18:05:48
- wall_seconds: 30.6
- money_spent_usd: 0.0
- short strata: none
- verification failures: none
- model roles: answer/question generator = deterministic code (no LLM); judge = free NIM model, different family from the extractor, opened at P7; extraction family for the KB = local parser + free NIM embeddings

## Sampled records (10, deterministic)

### G-129 [c_multihop_entity]

- question: The vessel Ying Hao 03 was reported sold on 2024-05-27 at 17.20 usd_m. Which publications reported it, and in how many documents? List the publication names.
- gold answer: Ying Hao 03: 17.20 usd_m on 2024-05-27; publishers Banchero Costa across 2 documents
- source: kind=transaction, txn_id=t:d38c5ec978a28056, vessel_id=vessel:prov:f1a27d1591657bf7, path=data/extracted/md/banchero_costa/2024/banchero_costa_2024_W21_Bancosta-Weekly-2024-21.md
- verification: ['mention_doc_count_reread', 'publisher_count_reread'] passed=True

### G-016 [a_single_number]

- question: What was the 2022 year for Handysize/Supramax / Coal, 40,000t, Samarinda - Guangzhou (8000c/12000c), $/t on 2022-04-04? Give the exact number and its unit.
- gold answer: 22 $/t
- source: kind=observation, obs_id=983328109736364435, period_to=2022-04-04, raw_cell=22.0, series_id=s:9d0e028e65711569
- verification: ['obs_row_reread', 'value_matches_raw_cell'] passed=True

### G-150 [c_multihop_entity]

- question: The vessel Lady Cedros was reported sent for demolition on 2024-12-06 at 467 usd_per_ldt. Which publications reported it, and in how many documents? List the publication names.
- gold answer: Lady Cedros: 467 usd_per_ldt on 2024-12-06; publishers Advanced Shipping & Trading across 2 documents
- source: kind=transaction, txn_id=t:289906ed68ef15c1, vessel_id=vessel:prov:7e6691e4018b8b93, path=data/extracted/md/advanced_shipping/2024/advanced_shipping_2024_W49_ADVANCED-MARKET-REPORT-WEEK-49.md
- verification: ['mention_doc_count_reread', 'publisher_count_reread'] passed=True

### G-069 [b_window_aggregate]

- question: What was the average Monthly avg spot dayrate for 2022-01 / PSVs < 900m2 over the 3 periods from 2022-11-01 to 2023-01-01? Give the exact number and its unit.
- gold answer: 6,684 GBP/day
- source: kind=observation, obs_id=68590279063514813, period_to=2022-11-01, raw_cell=6684.0, value=6684.0
- source: kind=observation, obs_id=893602028809401141, period_to=2022-12-01, raw_cell=6684.0, value=6684.0
- source: kind=observation, obs_id=977419255159315494, period_to=2023-01-01, raw_cell=6684.0, value=6684.0
- verification: ['avg_reread_from_db', 'periods_contiguous'] passed=True

### G-162 [d_event_market]

- question: After the 2024-11-18 report of the vessel sale (reported by Xclusiv Shipbrokers Inc.), how did the Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD move over the following month? Give the value on 2024-11-12 and on 2024-12-17 and the percentage change.
- gold answer: Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD: -3 -> -1.50 % (+50.00%)
- source: kind=transaction
- source: kind=observation, obs_id=857008797314877656, path=data/extracted/md/intermodal/2024/intermodal_2024_W45_Intermodal-Report-Week-45-2024.md, period_to=2024-11-12
- source: kind=observation, obs_id=91829352168968323, path=data/extracted/md/intermodal/2024/intermodal_2024_W50_Intermodal-Report-Week-50-2024.md, period_to=2024-12-17
- verification: ['window_observations_reread'] passed=True

### G-113 [g_as_known_on_date]

- question: As known on 2022-11-07, what was the latest Gulf of Finland (St- Pb) - ARA RV, 3,000 DWCC for Coaster / Average round voyage TCE (given backhaul leg in ballast), $/day and for which period? Give the exact number and its unit.
- gold answer: 9,774.20 $/day (period ending 2022-11-07)
- source: kind=observation, obs_id=1131816526918945378, period_to=2022-11-07, published_at=2022-11-07, raw_cell=9774.2
- verification: ['as_of_published_at_filter', 'recomputed_from_db'] passed=True

### G-109 [g_as_known_on_date]

- question: As known on 2023-04-10, what was the latest 2023 year for Handysize/Supramax / Wheat / corn, 5-6,000t, Constanta - Alexandria (2500x/1750x), $/t and for which period? Give the exact number and its unit.
- gold answer: 31.50 $/t (period ending 2023-04-10)
- source: kind=observation, obs_id=620008094014698323, period_to=2023-04-10, published_at=2023-04-10, raw_cell=31.5
- verification: ['as_of_published_at_filter', 'recomputed_from_db'] passed=True

### G-082 [f_summary_trend]

- question: How did the 2021 year for Handysize/Supramax / Wheat / corn, 5-6,000t, Reni / Izmail - Bari - Ortona (1250x/1250x), $/t change between 2021-01-11 and 2021-03-29? State the start value, the end value and the percentage change.
- gold answer: 23.60 -> 29.20 $/t (+23.73%)
- source: kind=observation, obs_id=34326258439407376, period_to=2021-01-11, raw_cell=23.6
- source: kind=observation, obs_id=1001691648201702198, period_to=2021-03-29, raw_cell=29.2
- verification: ['pct_recomputed_from_db'] passed=True

### G-073 [b_window_aggregate]

- question: What was the average 2021 year for Handysize/Supramax / Wheat (sf 46-47`), 25-30,000t, Odesa - SpanMed (8000x/8000x), $/t over the 4 periods from 2021-07-05 to 2021-07-26? Give the exact number and its unit.
- gold answer: 30.98 $/t
- source: kind=observation, obs_id=950636579621845599, period_to=2021-07-05, raw_cell=28.6, value=28.6
- source: kind=observation, obs_id=838144809019121683, period_to=2021-07-12, raw_cell=28.6, value=28.6
- source: kind=observation, obs_id=89176696980564188, period_to=2021-07-19, raw_cell=33.1, value=33.1
- source: kind=observation, obs_id=550349839764068253, period_to=2021-07-26, raw_cell=33.6, value=33.6
- verification: ['avg_reread_from_db', 'periods_contiguous'] passed=True

### G-015 [a_single_number]

- question: What was the Value for Aframax / Crude Tankers / Laden tonnage at anchor in Pacific / seasonal on 2023-01-01? Give the exact number and its unit.
- gold answer: 1.51 mdwt
- source: kind=observation, obs_id=326704022473948263, doc_id=4d8ecf39e5cbf116, path=data/extracted/md/drewry/ais/Crude_Aframax/Drewry_AIS_PDF_Crude_Aframax_Week50_20241.md, period_to=2023-01-01, raw_cell=1.508, publisher=Drewry Maritime Research, series_id=s:cefe8f9b7301219d
- verification: ['obs_row_reread', 'value_matches_raw_cell'] passed=True

## C1 sample packet (25 questions)

For the C1 checkpoint review: these are the questions proposed for the held-out set. Approve or flag; the rest of the set stays unapproved until C2.

G-001	a_single_number	What was the % of freight costs in CFR price for Handysize/Supramax / Ukrainian corn, CFR Egypt, Handy lot on 2026-04-06? Give the exact number and its unit.	=> 12.30 %
G-051	b_window_aggregate	What was the average 2023 year for Handysize/Supramax / Wheat / corn, 5-6,000t, Izmail / Odesa - Bari / Ortona (1500x/1500x), $/t over the 4 periods from 2023-02-20 to 2023-03-13? Give the exact number and its unit.	=> 53.50 $/t
G-116	c_multihop_entity	The vessel ROSCO POPLAR was reported sold on 2024-08-26 at 17.60 usd_m. Which publications reported it, and in how many documents? List the publication names.	=> ROSCO POPLAR: 17.60 usd_m on 2024-08-26; publishers Banchero Costa across 2 documents
G-151	d_event_market	After the 2026-03-07 report of the vessel sale (reported by Seasure Shipbroking (Blue Report, valuations by VesselsValue)), how did the Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD move over the following month? Give the value on 2026-03-03 and on 2026-03-31 and the percentage change.	=> Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD: 13.30 -> 6.90 % (-48.12%)
G-176	e_sec_section	In Ardmore Shipping Corp's SEC 20F filed 2016-04-06, which section (Item 9) discusses Dilution? Give the section heading.	=> 'The Offer and Listing'
G-076	f_summary_trend	How did the Value for Aframax / Crude Tankers / Tonne-miles index (base: week 1, 2024 =100) / seasonal change between 2025-03-16 and 2025-06-01? State the start value, the end value and the percentage change.	=> 95.07 -> 91.33 index (-3.93%)
G-101	g_as_known_on_date	As known on 2022-06-13, what was the latest 2022 year for Coaster / Fertilizers, 4,000t, Klaipeda - ARA (2000c/2000x), €/t and for which period? Give the exact number and its unit.	=> 28 EUR/t (period ending 2022-06-13)
G-211	h_unanswerable	What was the TD27X spot TCE on 2025-05-14? Give the exact number.	=> The corpus has a gap here: no series or document in the corpus mentions route code TD27X
G-002	a_single_number	What was the 2021 year for Handysize/Supramax / Scrap (sf 55-58`), 25-30,000t, Damietta - Santos (8000x/7000c), $/t on 2021-08-30? Give the exact number and its unit.	=> 35 $/t
G-052	b_window_aggregate	What was the average 2023 year for Handysize/Supramax / Wheat/corn (sf 47-49`), 25-30,000t, Odesa - EgyptMed (8000x/5000x), $/t over the 4 periods from 2023-03-13 to 2023-04-03? Give the exact number and its unit.	=> 35.05 $/t
G-117	c_multihop_entity	The vessel Western Fedora was reported sold on 2025-02-24 at 14 usd_m. Which publications reported it, and in how many documents? List the publication names.	=> Western Fedora: 14 usd_m on 2025-02-24; publishers Seasure Shipbroking (Blue Report, valuations by VesselsValue) across 2 documents
G-152	d_event_market	After the 2025-12-15 report of the vessel sale (reported by Seasure Shipbroking (Blue Report, valuations by VesselsValue)), how did the Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD move over the following month? Give the value on 2025-12-09 and on 2026-01-13 and the percentage change.	=> Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD: 1 -> 14.90 % (+1390.00%)
G-177	e_sec_section	In SFL Corporation Ltd's SEC 20F filed 2016-04-01, which section (Item 10) discusses Publicly-Traded? Give the section heading.	=> 'ADDITIONAL INFORMATION'
G-077	f_summary_trend	How did the Laden for LR2 / Product Tankers / Days at anchor, global- 4 week moving average / weekly change between 2026-04-26 and 2026-07-12? State the start value, the end value and the percentage change.	=> 0.26 -> 0.31 days (+17.62%)
G-102	g_as_known_on_date	As known on 2026-09-30, what was the latest Change pct for Mac Fines 60.8% / port_stock_cny / Fines / yuan/wmt and for which period? Give the exact number and its unit.	=> 0.30 % (period ending 2026-09-30)
G-212	h_unanswerable	What was the TC5L spot TCE on 2025-05-14? Give the exact number.	=> The corpus has a gap here: no series or document in the corpus mentions route code TC5L
G-003	a_single_number	What was the Tce usd per day for TC2 / Cont / USAC / ↑ Firmer on 2022-11-25? Give the exact number and its unit.	=> 45,890 USD/day
G-053	b_window_aggregate	What was the average Ukrainian corn, CFR Egypt, Handy lot for Handysize/Supramax / Ukrainian corn, CFR Egypt, Handy lot over the 4 periods from 2026-04-20 to 2026-05-11? Give the exact number and its unit.	=> 266.12 $/t
G-118	c_multihop_entity	The vessel Miao Xiang was reported sold on 2025-12-15 at 16 usd_m. Which publications reported it, and in how many documents? List the publication names.	=> Miao Xiang: 16 usd_m on 2025-12-15; publishers Seasure Shipbroking (Blue Report, valuations by VesselsValue) across 2 documents
G-153	d_event_market	After the 2025-07-28 report of the vessel sale (reported by Banchero Costa), how did the Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD move over the following month? Give the value on 2025-07-22 and on 2025-08-26 and the percentage change.	=> Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD: -8.20 -> 4.70 % (+157.32%)
G-178	e_sec_section	In DHT Holdings, Inc.'s SEC 20F filed 2015-03-19, which section (Item 15) discusses Sponsoring? Give the section heading.	=> 'CONTROLS AND PROCEDURES'
G-078	f_summary_trend	How did the Value for Handysize / Dry Bulk / Ballast tonnage at anchor in Oceania / seasonal change between 2022-04-03 and 2022-06-19? State the start value, the end value and the percentage change.	=> 1.06 -> 1.07 mdwt (+1.13%)
G-103	g_as_known_on_date	As known on 2021-10-15, what was the latest Change pct for VLCC / 310k / 5 years and for which period? Give the exact number and its unit.	=> 0 % (period ending 2021-10-15)
G-213	h_unanswerable	What was the MR14J spot TCE on 2025-05-14? Give the exact number.	=> The corpus has a gap here: no series or document in the corpus mentions route code MR14J
G-004	a_single_number	What was the 2024 year for Coaster / Urea, 5-6,000t, Damietta - Sevilla (2500x/2500x), $/t on 2024-10-14? Give the exact number and its unit.	=> 30.50 $/t

## Known risks / deviations

- D6: SEC stratum is prose/section lookup, not XBRL facts (XBRL skipped, no `SEC_USER_AGENT`; see upstream_defects.md). If the owner exports `SEC_USER_AGENT` later, XBRL can be ingested and this stratum can gain numeric SEC questions in a v2 set.
- Numeric question wording is template-generated and can read stiffly ("What was the <measurement> for <signature> on <date>?"). Wording was not tuned after seeing retrieval scores; it is fixed before the P4a measurement run.
- (d) pairs an event date with a market series over the following month; the answer is a computed market move, not proof of causation.
- Series units are sometimes NULL in the DB; where the measurement name encodes the unit an explicit measurement->unit map is used, and the unit shown in the question is that resolved unit.
- (h) refusal questions are verified by absence (entity/series/FTS zero rows); a model that answers them must also state the corpus gap to score.
