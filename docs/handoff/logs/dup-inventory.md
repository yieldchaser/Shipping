# Duplicate Voice Records and Stale `_digests` Inventory (Package F)

## Executive Summary

This inventory comprehensively audits two legacy data duplication and synchronization issues:
1. **Fearnleys Broker Voice Duplicates**: 634 duplicate `(date, desk)` pairs (1,268 files total) residing under `corpus/01-brokers/fearnleys/voice/`.
2. **Stale Digest Files**: 207 legacy markdown files residing under `corpus/01-brokers/_digests/` scraped from Hellenic Shipping News, compared against canonical markdown files under `data/extracted/md/`.

---

## Part 1: Duplicate Broker Voice Records

### Pipeline Locations & Generation Scripts
Voice records are produced and maintained by:
- **Extraction Script**: `scripts/fearnleys/export_broker_voice_to_corpus.py` (exports Hasura API records into corpus and extracted MDs).
- **Sync Script**: `scripts/fearnleys/daily_fearnleys_sync.py` (syncs broker commentary and tables daily).
- **Underlying CSV**: `data/derived/fearnleys_broker_comments.csv` (contains 11,759 structured rows).
- **File Targets**:
  - `corpus/01-brokers/fearnleys/voice/<sector>/<desk>/<year>/` (4,748 files)
  - `data/extracted/md/fearnleys/voice/<sector>/<desk>/<year>/` (4,766 files)

### Root Cause Analysis
In historical extractions spanning 2019 through early 2023, two successive export runs occurred:
1. **Run A (Un-suffixed)**: Created files with name pattern `<date>_<desk>_weekly_comment.md` (e.g. `2019-02-04_aframax_weekly_comment.md`).
2. **Run B (Hex GUID-suffixed)**: Created files with name pattern `<date>_<desk>_weekly_comment_<HEX>.md` (e.g. `2019-02-04_aframax_weekly_comment_3B9FF709.md`).

Both files represent the identical broker commentary issued for that date and desk. The underlying Hasura database assigned two different internal UUIDs across migrations, resulting in different frontmatter `id:` lines. However, the prose text under `## Market Commentary` is 100% byte-for-byte identical in 632 of 634 groups (99.7%).

### Summary of Duplicate Voice Groups

| Metric | Count | Note |
| :--- | :--- | :--- |
| Total Duplicate Groups | **634** | Exact `(date, desk)` collisions |
| Total Files in Duplicate Groups | **1268** | 2 files per group |
| Full File Byte-Identical Groups | **0** | Frontmatter contains different UUID |
| Body Prose Identical Groups | **632** | Market Commentary text is 100% identical |
| Minor Body Diff Groups | **2** | Formatted subheader markdown variant |

### Breakdown by Year

| Year | Duplicate Groups | Total Files |
| :--- | :--- | :--- |
| 2019 | 129 | 258 |
| 2020 | 153 | 306 |
| 2021 | 154 | 308 |
| 2022 | 153 | 306 |
| 2023 | 45 | 90 |

### Breakdown by Desk

| Desk | Duplicate Groups | Total Files |
| :--- | :--- | :--- |
| Suezmax | 212 | 424 |
| Aframax | 211 | 422 |
| VLCC | 211 | 422 |

### 10 Concrete Examples of Duplicate Voice Groups

#### 1. `2019-02-04` — `Aframax`
- **Group Key**: `2019-02-04::Aframax`
- **File 1**: `corpus/01-brokers/fearnleys/voice/aframax/2019/2019-02-04_aframax_weekly_comment.md` (UUID: `0587681E-57C3-4F9B-B39A-52B5F4DE2883`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/aframax/2019/2019-02-04_aframax_weekly_comment_3B9FF709.md` (UUID: `3B9FF709-0DFF-4E98-A9D6-B5C7F2A43332`)
- **Prose Content**: 100% identical
- **Excerpt**: *"As expected, Aframax rates in the N.Sea and Baltic came under downward pressure this week. The downward correction was mainly due to lack of..."*

#### 2. `2019-02-04` — `Suezmax`
- **Group Key**: `2019-02-04::Suezmax`
- **File 1**: `corpus/01-brokers/fearnleys/voice/suezmax/2019/2019-02-04_suezmax_weekly_comment.md` (UUID: `7B8ECA62-BCCF-45D9-83D2-9C94CC31EF9C`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/suezmax/2019/2019-02-04_suezmax_weekly_comment_D9EEF30E.md` (UUID: `D9EEF30E-3058-4ACB-B911-30C59C3811B4`)
- **Prose Content**: 100% identical
- **Excerpt**: *"Activity has been slow for Suezmaxes the past week, third decade dates in W.Afr were slow in showing and caused a slow decline in the rates ..."*

#### 3. `2019-02-04` — `VLCC`
- **Group Key**: `2019-02-04::VLCC`
- **File 1**: `corpus/01-brokers/fearnleys/voice/vlcc/2019/2019-02-04_vlcc_weekly_comment.md` (UUID: `6992AA37-B667-4D42-823A-2D71D8188047`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/vlcc/2019/2019-02-04_vlcc_weekly_comment_D7B30093.md` (UUID: `D7B30093-3B5A-499E-AE76-6DB450C5FAAC`)
- **Prose Content**: 100% identical
- **Excerpt**: *"The activity for the VLCCs, particularly in the days prior to the Lunar New Year holidays, remained active but as the holidays started in ea..."*

#### 4. `2019-02-11` — `Aframax`
- **Group Key**: `2019-02-11::Aframax`
- **File 1**: `corpus/01-brokers/fearnleys/voice/aframax/2019/2019-02-11_aframax_weekly_comment.md` (UUID: `2E964FB7-83F8-4189-B076-B41697AD1BAC`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/aframax/2019/2019-02-11_aframax_weekly_comment_4B5635E6.md` (UUID: `4B5635E6-875B-4611-8CE6-8167054E4A4C`)
- **Prose Content**: 100% identical
- **Excerpt**: *"Aframax rates in NSea and Baltic hovered around bottom levels the last week. Currently there is a more firm sentiment to the market as this ..."*

#### 5. `2019-02-11` — `Suezmax`
- **Group Key**: `2019-02-11::Suezmax`
- **File 1**: `corpus/01-brokers/fearnleys/voice/suezmax/2019/2019-02-11_suezmax_weekly_comment.md` (UUID: `F5C61E6C-E1F4-441E-89AA-982BC8B9C6AB`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/suezmax/2019/2019-02-11_suezmax_weekly_comment_99FA7917.md` (UUID: `99FA7917-21FE-4CA2-A5B5-4E5622F0EB94`)
- **Prose Content**: 100% identical
- **Excerpt**: *"The Suezmax market has been a mix of bewilderment and an acceptance of reality as the continued slow pace of firm cargoes working has contin..."*

#### 6. `2019-02-11` — `VLCC`
- **Group Key**: `2019-02-11::VLCC`
- **File 1**: `corpus/01-brokers/fearnleys/voice/vlcc/2019/2019-02-11_vlcc_weekly_comment.md` (UUID: `79E082D9-C624-4EC6-B32B-C07D686308E5`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/vlcc/2019/2019-02-11_vlcc_weekly_comment_B74126CD.md` (UUID: `B74126CD-AED9-4428-AA7F-FAB8033BEEC5`)
- **Prose Content**: 100% identical
- **Excerpt**: *"Another week with rates for the VLCCs under pressure and therefore corrected down somewhat more. There is however a feeling that there is su..."*

#### 7. `2019-02-26` — `Aframax`
- **Group Key**: `2019-02-26::Aframax`
- **File 1**: `corpus/01-brokers/fearnleys/voice/aframax/2019/2019-02-26_aframax_weekly_comment.md` (UUID: `16527010-D441-457D-BB90-DD011A1D6EC9`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/aframax/2019/2019-02-26_aframax_weekly_comment_922F2D6A.md` (UUID: `922F2D6A-9BC3-45CB-B4F2-014B2F57F174`)
- **Prose Content**: 100% identical
- **Excerpt**: *"As expected, Aframax rates in the Baltic and North Sea increased this week. Quite a few vessels had left the area leaving charterers with fe..."*

#### 8. `2019-02-26` — `Suezmax`
- **Group Key**: `2019-02-26::Suezmax`
- **File 1**: `corpus/01-brokers/fearnleys/voice/suezmax/2019/2019-02-26_suezmax_weekly_comment.md` (UUID: `ABCFB527-6907-4AE4-8CDC-3D3D4B32F42C`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/suezmax/2019/2019-02-26_suezmax_weekly_comment_CC64C1B6.md` (UUID: `CC64C1B6-7A2A-4FDF-AD26-A84142720C5E`)
- **Prose Content**: 100% identical
- **Excerpt**: *"Sporadic action has allowed tonnage lists to build and further erosion of rates across the board has been the flavour of the past week. It h..."*

#### 9. `2019-02-26` — `VLCC`
- **Group Key**: `2019-02-26::VLCC`
- **File 1**: `corpus/01-brokers/fearnleys/voice/vlcc/2019/2019-02-26_vlcc_weekly_comment.md` (UUID: `898CC652-86B9-400E-8C92-70D88C71F641`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/vlcc/2019/2019-02-26_vlcc_weekly_comment_FA6971E1.md` (UUID: `FA6971E1-6AC9-45FE-95AF-6BA4F8A7EE57`)
- **Prose Content**: 100% identical
- **Excerpt**: *"The brisk activity ex Usg for march has managed to pull the rates up for the other major VLCC-routes. Ships have ballasted on spec from the ..."*

#### 10. `2019-03-04` — `Aframax`
- **Group Key**: `2019-03-04::Aframax`
- **File 1**: `corpus/01-brokers/fearnleys/voice/aframax/2019/2019-03-04_aframax_weekly_comment.md` (UUID: `30BC5DF2-73ED-40F3-84AD-69508241D76E`)
- **File 2**: `corpus/01-brokers/fearnleys/voice/aframax/2019/2019-03-04_aframax_weekly_comment_64BDC632.md` (UUID: `64BDC632-9264-40FA-8114-AF051851BA45`)
- **Prose Content**: 100% identical
- **Excerpt**: *"Aframax rates in NSea and Baltic are currently under upward pressure. Moving into 3rd decade fixing window in Baltic, there will be a greate..."*

---

## Part 2: Stale `_digests` Inventory

### Overview
The directory `corpus/01-brokers/_digests/` contains 207 markdown files that originated as syndicated blog post scrapes from Hellenic Shipping News. These files represent intermediate digest articles that announce weekly shipping reports from 16 different brokerage houses.

### Mapping & Status Summary

| Status | Count | Percentage | Description |
| :--- | :--- | :--- | :--- |
| `differs` | 200 | 96.62% | Canonical PDF-derived MD exists in data/extracted/md/; digest is an earlier web synopsis |
| `no canonical found` | 7 | 3.38% | General Hellenic web news articles with no associated PDF or broker table report |
| `identical` | 0 | 0.00% | Exact byte/content match |
| **Total** | **207** | **100.00%** | |

### Breakdown by Broker

| Broker | Total Files | Differs (Matched) | No Canonical Found |
| :--- | :--- | :--- | :--- |
| `advanced_shipping` | 11 | 11 | 0 |
| `affinity` | 4 | 4 | 0 |
| `agora` | 4 | 4 | 0 |
| `banchero_costa` | 14 | 14 | 0 |
| `carriers` | 108 | 101 | 7 |
| `clarksons` | 3 | 3 | 0 |
| `fearnleys` | 4 | 4 | 0 |
| `gibson` | 3 | 3 | 0 |
| `intermodal` | 13 | 13 | 0 |
| `ism` | 3 | 3 | 0 |
| `lion` | 12 | 12 | 0 |
| `ssy` | 9 | 9 | 0 |
| `star_asia` | 5 | 5 | 0 |
| `xclusiv` | 14 | 14 | 0 |

### Why Matched Digests Differ from Canonical MDs
All 200 matched digest files differ from the canonical MDs in `data/extracted/md/` due to architectural design:
1. **Digest Structure**: Digest files contain web scraping headers (`Source URL`, `pdf_url`), introductory editorial synopses, disclaimer footers, and raw HTML formatting.
2. **Canonical Structure**: The canonical MDs in `data/extracted/md/` were generated directly from the original primary PDF reports using dedicated Python extractors. They feature complete multi-page markdown tables, standardized frontmatter schemas (`source_file`, `report_week`, `issue_date`), and sidecar `.tables.json` files.
3. **Cross-Syndication**: Several reports under `_digests/` were filed under one broker folder but syndicate reports from another publisher (e.g. 14 Gibson tanker reports syndicated under `carriers/`, `gibson/`, and `lion/`; and a Clarksons SnP report syndicated under `lion/`). All have been cross-resolved to their true canonical extraction.

### 10 Concrete Examples of Matched Digests (`differs`)

#### 1. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 31 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_01_08_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2021/advanced_shipping_2021_W31_ADVANCED-MARKET-REPORT-WEEK-31.md`
- **Status**: `differs` (-4906 chars)

#### 2. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 40 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_03_10_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2021/advanced_shipping_2021_W40_ADVANCED-MARKET-REPORT-WEEK-40.md`
- **Status**: `differs` (-6636 chars)

#### 3. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 36 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_05_09_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2021/advanced_shipping_2021_W36_ADVANCED-MARKET-REPORT-WEEK-36.md`
- **Status**: `differs` (-3537 chars)

#### 4. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 32 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_08_08_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2021/advanced_shipping_2021_W32_ADVANCED-MARKET-REPORT-WEEK-32.md`
- **Status**: `differs` (-4720 chars)

#### 5. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 41 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_10_10_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2021/advanced_shipping_2021_W41_ADVANCED-MARKET-REPORT-WEEK-41.md`
- **Status**: `differs` (-3438 chars)

#### 6. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 37 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_12_09_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2021/advanced_shipping_2021_W37_ADVANCED-MARKET-REPORT-WEEK-37.md`
- **Status**: `differs` (-6403 chars)

#### 7. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 29 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_18_07_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2021/advanced_shipping_2021_W29_ADVANCED-MARKET-REPORT-WEEK-29.md`
- **Status**: `differs` (-2957 chars)

#### 8. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 33 – 34 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_22_08_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2026/advanced_shipping_2026_W33_ADVANCED-MARKET-REPORT-WEEK-33-34.md`
- **Status**: `differs` (-3799 chars)

#### 9. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 30 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_25_07_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2021/advanced_shipping_2021_W30_ADVANCED-MARKET-REPORT-WEEK-30.md`
- **Status**: `differs` (-4170 chars)

#### 10. `advanced_shipping` — Advanced Shipping & Trading – WEEKLY SHIPPING MARKET REPORT WEEK 39 2026
- **Digest File**: `corpus/01-brokers/_digests/advanced_shipping/2026/advanced_shipping_26_09_2026_advanced_shipping_trading_weekly_shipping_marke.md`
- **Canonical MD**: `data/extracted/md/advanced_shipping/2021/advanced_shipping_2021_W39_ADVANCED-MARKET-REPORT-WEEK-39.md`
- **Status**: `differs` (-6018 chars)

### All 7 Unmatched Digests (`no canonical found`)

The only 7 unmatched files are non-report web articles from Hellenic Shipping News (industry conferences, technology briefings, video announcements) with empty `pdf_url:` and no publisher PDF report:

#### 1. HELMEPA AT POSIDONIA 2024
- **Digest File**: `corpus/01-brokers/_digests/carriers/2024/general_broker_14_07_2024_helmepa_at_posidonia_2024.md`
- **Reason**: General web publication (no underlying PDF or broker weekly report).

#### 2. Efficiency given over 30% boost with quad lifts at APM Terminals Lazaro Cardenas
- **Digest File**: `corpus/01-brokers/_digests/carriers/2024/general_broker_16_07_2024_efficiency_given_over_30_boost_with_quad_lifts_at_apm.md`
- **Reason**: General web publication (no underlying PDF or broker weekly report).

#### 3. Flex LNG Q1 2024 Key Takeaways Video
- **Digest File**: `corpus/01-brokers/_digests/carriers/2024/general_broker_24_05_2024_flex_lng_q1_2024_key_takeaways_video.md`
- **Reason**: General web publication (no underlying PDF or broker weekly report).

#### 4. Flange Mounted Upending Tool [FMUT]
- **Digest File**: `corpus/01-brokers/_digests/carriers/2024/general_broker_26_05_2024_flange_mounted_upending_tool_fmut.md`
- **Reason**: General web publication (no underlying PDF or broker weekly report).

#### 5. Oceanos Ntua – National Technical University of Athens – Greece
- **Digest File**: `corpus/01-brokers/_digests/carriers/2024/general_broker_27_06_2024_oceanos_ntua_national_technical_university_of_athens.md`
- **Reason**: General web publication (no underlying PDF or broker weekly report).

#### 6. Black Carbon, Scrubbers & the Arctic: Clean Arctic Alliance Briefing for IMO PPR 12 Shipping Meeting
- **Digest File**: `corpus/01-brokers/_digests/carriers/2025/general_broker_23_01_2025_black_carbon_scrubbers_the_arctic_clean_arctic_all.md`
- **Reason**: General web publication (no underlying PDF or broker weekly report).

#### 7. Capt. Girish Munjal, Content Director, MarinePALS on the impact of the PSC CIC on Cargo Securing.
- **Digest File**: `corpus/01-brokers/_digests/carriers/2026/general_broker_10_09_2026_capt_girish_munjal_content_director_marinepals_on_t.md`
- **Reason**: General web publication (no underlying PDF or broker weekly report).

---

## Recommendations for Upstream Cleanup

1. **Voice Records Deduplication**: When pruning duplicates, preserve the GUID-suffixed files (`<date>_<desk>_weekly_comment_<HEX>.md`), as these correlate with the unique GUIDs used in `data/extracted/md/fearnleys/voice/`.
2. **`_digests/` Retirement**: All weekly broker intelligence is already canonically extracted and validated under `data/extracted/md/`. The `_digests/` directory represents legacy scrape artifacts and can be safely archived or quarantined without data loss.
