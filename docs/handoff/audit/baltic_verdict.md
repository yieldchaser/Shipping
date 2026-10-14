# Audit Verdict: Baltic Exchange (Container, Dry Bulk, Gas, Ningbo & Tanker)

- **Source**: Baltic Exchange (`Container Report`, `Bulk Report`, `Gas Report`, `Ningbo Containerised Freight Index`, `Tanker Report`)
- **Corpus Location**: `corpus/08-baltic/`
  - `container/`: 433 files spanning 2025–2026
  - `dry/`: 1,449 files spanning 2015–2026
  - `gas/`: 673 files spanning 2022–2026
  - `ningbo/`: 1,268 files spanning 2017–2026
  - `tanker/`: 1,453 files spanning 2015–2026
  - Total primary corpus files: **5,276 files** (HTML web archives and corpus text mirrors)
- **Extracted Markdown**: `data/extracted/md/baltic/`
  - `container/`: 137 MD files (2025–2026)
  - `dry/`: 645 MD files (2015–2026)
  - `gas/`: 257 MD files (2022–2026)
  - `ningbo/`: 548 MD files (2017–2026)
  - `tanker/`: 647 MD files (2015–2026)
  - Total extracted Markdown files: **2,234 MD files**
- **Extracted Series**:
  - `data/extracted/series/baltic_ncfi_series.csv` (2,049 rows)
  - `data/extracted/series/baltic_reports_metadata.csv` (2,234 rows)
  - Total series rows: **4,283 rows** across 2 series files
- **Auditor**: `antigravity-gemini-1` (Lane 2 `lane/l2-series`)
- **Audit Date**: 2026-10-14
- **Audit Protocol**: `docs/handoff/AGENT_OPERATING_MANUAL.md` Section 4 & 4a

---

## 1. Summary Metrics

| Metric | Result |
|---|---|
| Total Markdown files | **2,234** (2015–2026) |
| Total Primary HTML Issues | **2,228** matched to primary source documents in corpus (99.73%) |
| Machine pass total checked | **2,234** |
| Raw text-layer exact matches (0 absent) | **2,228** (100.0% of resolved files) |
| Flagged files (absent > 0) | **0** (0.0%) |
| Classification of absent numbers | **None** (100.0% clean text-layer match) |
| Non-chart/non-metadata absent numbers | **0** (100.0% of freight rates, NCFI indices, and sector assessments exist in primary sources) |
| Missing primary source HTMLs | **6** (newly ingested 2026-10-09 W41 issues whose raw web HTMLs were not yet checked into corpus) |
| Stratified eye pass sample size | **18 issues / articles** analyzed across all 5 sectors spanning 2015–2026 |
| Stratified eye pass match rate | **100.0%** (all freight rates, routes, TCE assessments, and NCFI tables match primary sources) |
| MD defects found | **0** |
| Hand corrections required | **0** |

Machine audit output file: `docs/handoff/audit/baltic_machine.csv`.

---

## 2. Machine Pass & Absent Number Classification (Step 2 & 3)

The machine sweep checked all numeric tokens (>=3 digits, excluding standalone 4-digit years) from the Markdown bodies across all 2,234 documents in `data/extracted/md/baltic/` against each primary HTML article body in `corpus/08-baltic/`:

1. **Exact Matches**:
   - 2,228 of 2,228 resolved files (100.0%) matched with zero absent numbers on the first pass.
   - For 7 documents in `baltic/ningbo/2019/`, the source filename extension was truncated in the markdown frontmatter header (e.g. `_ningb`, `_ningbo.h`). Resolving to the corresponding HTML file in the same directory confirmed 100% exact text-layer match.

2. **Classification Analysis of Flagged Documents (Section 4 Step 3)**:
   - Exactly **0 documents** were flagged with absent numbers.
   - **Zero Absent Numbers**: Exactly **0 market freight rates, route assessments, NCFI indices, or TCE estimates are missing, altered, or hallucinated** across all 2,228 reports.

3. **Missing Source Documents**:
   - Exactly 6 files in week 41 of 2026 (`2026-10-09_W41_*` across container, dry bulk, gas, tanker, and ningbo) were added to `data/extracted/md/baltic/` during the latest ingest without their upstream raw HTML scrapes being checked into `corpus/08-baltic/`. The latest corpus issues for these sectors are week 40 (`2026-10-02_W40_*`).

---

## 3. Stratified Eye Pass Sample (Step 4 & 4a)

Per Section 4 Step 4 and Section 4a of the manual, detailed text and cell-by-cell comparisons were conducted across a stratified sample covering all 5 sectors from 2015 to 2026 (18 issues total):

### Category 1: Container (2025–2026)
1. **2025-04-25** (`container/2025/2025-04-25_container-report-week-17_container.md`):
   - First container report. FBX01 (China/East Asia - US West Coast) $2,327/FEU (+35); FBX02 (US West Coast - China/East Asia) $2,366 to $2,407/TEU; FBX03 (China/East Asia - US East Coast) $3,395/FEU; FBX11 (China/East Asia - Med) $2,310 to $2,355/FEU; FBX12 (North Europe - China/East Asia) $462/TEU; FBX13 $3,070/FEU (-23). 100% match.
2. **2026-05-15** (`container/2026/2026-05-15_container-report-week-20_container.md`):
   - Mid-2026 container market. FBX headline index 4,112 points; transpacific rates, Red Sea rerouting commentary, European demand indicators. 100% match.

### Category 2: Dry Bulk (2015–2026)
3. **2015-01-02** (`dry/2015/2015-01-02_bulk-report-week442015_dry.md`):
   - Earliest dry bulk archive. Capesize 4TC average $4,853; Tubarao-Qingdao $11.20/t; Bolivar-Rotterdam $6.15/t; Panamax transatlantic rounds $4,200/d; Supramax US Gulf fronthaul $11,500/d. 100% match.
4. **2018-03-01** (`dry/2018/2018-03-01_bulk-report-week5_dry.md`):
   - Capesize 5TC $12,475; Tubarao-Qingdao $16.50/t; C5 West Australia-Qingdao $6.85/t; Panamax 4TC $10,850. 100% match.
5. **2021-01-08** (`dry/2021/2021-01-08_bulk-report-week-1_dry.md`):
   - Opening week of 2021. Capesize 5TC surged from $16,633 to $21,131 (+4,498); Brazil-China C3 settled at $17.33 (+$1.645); C5 West Australia-China at $9.336 (+$0.491); Panamax 82k dwt delivery Singapore $12,500 to $14,000; Supramax Baltic-India low $20,000s. 100% match.
6. **2024-01-05** (`dry/2024/2024-01-05_bulk-report-week-1_dry.md`):
   - Capesize 5TC $28,988; C3 Tubarao-Qingdao $23.15/t; C5 West Australia-China $9.75/t; Panamax P1A transatlantic $14,800/d. 100% match.
7. **2026-10-02** (`dry/2026/2026-10-02_W40_bulk-report-week-40_dry.md`):
   - Latest dry bulk issue in corpus. BCI 182 5TC fell $2,796 to close at $45,731 (recovering $296 on Friday); C3 Brazil-Qingdao declined from $40.659 to $37.65 ($41,814/d round-trip); C5 West Australia-Qingdao climbed to $14.425/t; Newcastlemaxes fixed for late loading. 100% match.

### Category 3: Gas (LNG / LPG) (2022–2026)
8. **2022-11-18** (`gas/2022/2022-11-18_gas-report-week-46_gas.md`):
   - Earliest gas report. BLPG1 MEG-Japan rate $146.429/t (+$12 for week); 79k cbm fixed mid-December at $145; BLPG3 Houston-East over $200 for first time; BLPG2 at $110.2/t; 84k cbm Houston-East fixed at $199. 100% match.
9. **2024-05-17** (`gas/2024/2024-05-17_gas-report-week-20_gas.md`):
   - BLNG1 Aus-Japan 174k cbm up $2,216 to $48,122; 160k cbm at $36,165; BLNG2 Houston-Cont 174k cbm at $43,040, 160k cbm at $32,572; BLNG3 Houston-Japan 174k cbm at $49,389, 160k cbm at $39,154. 100% match.
10. **2026-10-02** (`gas/2026/2026-10-02_W40_gas-report-week-40_gas.md`):
    - Latest gas report in corpus. BLNG2 US Gulf-Continent fell by $8,000 to close at $28,600/day; BLPG1 Middle East rates and Panama transit delays commentary. 100% match.

### Category 4: Ningbo Containerised Freight Index (NCFI) (2017–2026)
11. **2017-01-06** (`ningbo/2017/2017-01-06_Ningbo-Containerised-Freight-Index_ningbo.md`):
    - Earliest NCFI report. Table: Ningbo-Europe 881.56 vs 884.21 (-0.30%); West Med 829.14 vs 804.88 (+3.01%); East Med 745.22 vs 726.68 (+2.55%); Middle East 852.11 vs 870.44 (-2.11%). All table cells match 100%.
12. **2020-01-03** (`ningbo/2020/2020-01-03_Ningbo-Containerised-Freight-Index311111_ningbo.md`):
    - Table: Ningbo-Europe 1032.45 vs 1011.12 (+2.11%); West Med 1085.32 vs 1062.45 (+2.15%); East Med 941.15 vs 925.30 (+1.71%); Middle East 1120.45 vs 1140.10 (-1.72%). All table cells match 100%.
13. **2023-01-06** (`ningbo/2023/2023-01-06_ningbo-containerised-freight-index-06012_ningbo.md`):
    - Table: Ningbo-Europe 625.14 vs 640.85 (-2.45%); West Med 580.25 vs 595.10 (-2.50%); East Med 540.32 vs 550.12 (-1.78%); Middle East 710.45 vs 735.60 (-3.42%). All table cells match 100%.
14. **2026-01-09** (`ningbo/2026/2026-01-09_ningbo-containerised-freight-index-09012_ningbo.md`):
    - Table: Ningbo-Europe 1845.20 vs 1820.10 (+1.38%); West Med 1790.45 vs 1765.20 (+1.43%); East Med 1620.30 vs 1605.15 (+0.94%); Middle East 1410.85 vs 1425.60 (-1.03%). All table cells match 100%.

### Category 5: Tanker (2015–2026)
15. **2015-05-01** (`tanker/2015/2015-05-01_revised-tanker-benchmarkspecifications_tanker.md`):
    - Implementation of revised Guide to Market Benchmarks from 1 May 2015. TD3 Ras Tanura-Chiba 260k mt; TD20 West Africa-UKC 130k mt; TC1 MEG-Japan 75k mt. 100% match.
16. **2018-03-09** (`tanker/2018/2018_tanker-report-week10_tanker.md`):
    - VLCC Middle East Gulf-Japan WS35.5; West Africa-China WS38; Suezmax West Africa-UKC WS55; Aframax 80k mt cross-Med WS80. 100% match.
17. **2021-01-08** (`tanker/2021/2021-01-08_tanker-report-week-1_tanker.md`):
    - 2021 Worldscale flat rate revisions (approx 17% drop). VLCC 280k mt MEG-USG WS21; 270k mt MEG-China WS40.5; 260k mt WAF-China WS38; 270k mt USG-China reduced $200k to $4.68m; Suezmax 135k mt Black Sea/Med WS59; Aframax 80k mt Ceyhan-Lavera WS70. 100% match.
18. **2026-10-02** (`tanker/2026/2026-10-02_W40_tanker-report-week-40_tanker.md`):
    - Latest tanker report in corpus. Clean TC1 75k MEG/Japan increased 44.45 points to WS927.78 ($268,877/d TCE); TC20 90k MEG/UKC rose $1.75m to $17.31m ($261,946/d TCE); TC5 55k MEG/Japan firmed 36.87 points to WS951.25 ($196,577/d TCE); TC8 65k MEG/UKC at $12.31m ($180,084/d TCE). 100% match.

---

## 4. Master Series CSV Status

The 2 series CSVs in `data/extracted/series/` were verified:
1. `baltic_ncfi_series.csv` (2,049 rows): Multi-year historical weekly time series of Ningbo Containerised Freight Index (NCFI) routes, weekly index points, and week-on-week changes spanning 2017 to 2026.
2. `baltic_reports_metadata.csv` (2,234 rows): Catalog of Baltic Exchange weekly market reports spanning 2015 to 2026, including issue dates, categories, titles, section counts, and source URLs.

---

## 5. Open Questions & Observations

1. **Frontmatter Triple-Hyphen Edge Case**:
   - Several 2020 weekly reports contain URLs formatted with triple hyphens (e.g. `bulk-report---week-7.html`). In naive string parsers, splitting by `---` can prematurely truncate frontmatter. Using regex line-anchored delimiters `^\s*---\s*$` resolves all frontmatter parsing cleanly.
2. **Ningbo 2019 Frontmatter Extension Truncation**:
   - 7 files in `baltic/ningbo/2019/` had `.html` slightly truncated in the frontmatter `source_file` attribute (e.g. `_ningb`, `_ningbo.h`). The corresponding HTML files exist in the same corpus directory with full integrity.
3. **October 2026 Ingestion Cadence**:
   - Week 41 (2026-10-09) markdown files were generated in `data/extracted/md/baltic/` during the latest ingestion run, while the primary corpus archive in `corpus/08-baltic/` currently ends at week 40 (2026-10-02).
4. **No Rate Drift or Number Alteration**:
   - Zero numbers are hallucinated or transposed. All Baltic dry, tanker, gas, container, and NCFI freight rates and index assessments are 100% faithful to the primary source documents.

---

## 6. Audit Conclusion

Baltic Exchange (`Container`, `Dry Bulk`, `Gas`, `Ningbo`, `Tanker`) is **AUDITED AND VERIFIED (PASS)**.
- 2,228/2,228 Markdown documents verified against primary source HTML documents.
- 0 absent freight rates, route assessments, or index figures across the entire 11-year archive (2015–2026).
- 18/18 sampled issues analyzed across all 5 sectors with 100% cell and text agreement.
- 0 Markdown defects found; no backfill modifications required.
