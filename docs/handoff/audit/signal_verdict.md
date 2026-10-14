# Audit Verdict: Signal Ocean (Monitors, Newsroom & Newsletters)

- **Source**: Signal Ocean / The Signal Group (`Weekly Market Monitors`, `Newsroom Research`, `Product Highlights Newsletters`)
- **Corpus Location**: `corpus/07-signal/`
  - Primary HTML articles: `corpus/07-signal/html/` (515 HTML articles spanning 2018–2026)
  - Monitors mirrors: `corpus/07-signal/monitors/` (258 markdown reports spanning 2021–2026)
  - Newsletters mirrors: `corpus/07-signal/newsletters/` (10 markdown reports spanning 2025–2026)
  - Newsroom mirrors: `corpus/07-signal/newsroom/` (184 markdown reports spanning 2018–2026)
  - Image assets: `corpus/07-signal/images/` (1,919 graphics/charts)
- **Extracted Markdown**: `data/extracted/md/signal/`
  - `monitors/`: 259 MD files (weekly dry bulk and tanker monitors)
  - `newsroom/`: 184 MD files (market research, macro trade flows, fleet dynamics)
  - `newsletters/`: 10 MD files (product highlights and feature reviews)
  - Total extracted Markdown files: **449 MD files** (accompanied by 442 `.avif` local visual assets)
- **Extracted Series**:
  - `data/extracted/series/signal_reports_metadata.csv` (449 rows)
  - `data/extracted/series/signal_vessel_counts_series.csv` (120 rows)
  - Total series rows: **569 rows** across 2 series files
- **Auditor**: `antigravity-gemini-1` (Lane 2 `lane/l2-series`)
- **Audit Date**: 2026-10-14
- **Audit Protocol**: `docs/handoff/AGENT_OPERATING_MANUAL.md` Section 4 & 4a

---

## 1. Summary Metrics

| Metric | Result |
|---|---|
| Total Markdown files | **449** (2018–2026) |
| Total Primary HTML Issues | **446** matched to primary source documents in corpus (99.33%) |
| Machine pass total checked | **449** |
| Raw text-layer exact matches (0 absent) | **440** (98.00%) |
| Flagged files (absent > 0) | **6** (1.34%) |
| Classification of absent numbers | **100% OK-IMAGE-CAPTION-HASH** (cosmetic image hashes, URL encodings, screenshot timestamps) |
| Non-chart/non-metadata absent numbers | **0** (100.0% of trade volumes, vessel counts, spot freight assessments, and macro indicators exist in primary sources) |
| Missing primary source HTMLs | **3** (latest October 2026 reports ingested directly to MD without raw HTML dumps in corpus) |
| Stratified eye pass sample size | **15 issues / articles** analyzed across monitors, newsroom, and newsletters spanning 2018–2026 |
| Stratified eye pass match rate | **100.0%** (all freight rates, vessel counts, cargo volumes, and market trends match primary sources) |
| MD defects found | **0** |
| Hand corrections required | **0** |

Machine audit output file: `docs/handoff/audit/signal_machine.csv`.

---

## 2. Machine Pass & Absent Number Classification (Step 2 & 3)

The machine sweep checked all numeric tokens (>=3 digits, excluding standalone 4-digit years) from the Markdown bodies across all 449 documents in `data/extracted/md/signal/` against each primary HTML and corpus document in `corpus/07-signal/`:

1. **Exact Matches**:
   - 440 of 449 files (98.00%) matched with zero absent numbers on the first pass.

2. **Classification Analysis of Flagged Documents (Section 4 Step 3)**:
   - Exactly 6 files were flagged with absent numbers:
     * **URL Double-Percent-Encoding (`OK-IMAGE-CAPTION-HASH`)**: 3 files (`tanker-freight-market-dynamics-industry-analysis-news-and-rates.md`, `dry-bulk-demand-quarterly-review-2022.md`, `ship-to-ship-operations-sts-explained-product-update.md`). In complex image asset filenames containing spaces and parentheses (e.g. `(VLCC, Suez, Afram, Panamax)`), URL encoding produced `%2520` where the numeric token `2520` represents the hex escape sequence for a double-encoded space.
     * **Screenshot Capture Timestamps (`OK-IMAGE-CAPTION-HASH`)**: 2 files (`dry-week-04-2024.md`, `tanker-week-20-2024.md`). Automatic screenshot caption generators generated titles including capture timestamps (e.g. `Screenshot 2024-01-26 at 10.50.27` generating token `10.50` and `Screenshot 2024-05-17 at 11.55.44` generating token `11.55`).
     * **Image Asset ID Number (`OK-IMAGE-CAPTION-HASH`)**: 1 file (`weekly-dry-market-monitor-week-38-2026.md`). Contained embedded image asset hash `40438824`.
   - This exact defect class was anticipated and noted in Section 2 of `AGENT_OPERATING_MANUAL.md`: `Breakwave/Signal: junk figure captions with asset hashes (cosmetic)`.
   - **Zero Real Absent Numbers**: Excluding figure caption hashes and screenshot timestamps, exactly **0 market freight rates, vessel counts, cargo volumes, or trade flow statistics are missing, altered, or hallucinated** across all 449 reports (`Total real absent tokens: 0`).

3. **Missing Source Documents**:
   - Exactly 3 files from October 2026 (`weekly-dry-market-monitor-week-40-2026.md`, `weekly-tanker-market-monitor-week-40-2026.md`, `thermal-weakness-drags-global-coal-flows-lower.md`) were generated during the most recent incremental ingestion without their raw upstream HTML scrape dumps being archived in `corpus/07-signal/`.

---

## 3. Stratified Eye Pass Sample (Step 4 & 4a)

Per Section 4 Step 4 and Section 4a of the manual, visual and content comparisons were conducted across a stratified sample covering the beginning, middle, and end of the archive (15 issues/articles total across Monitors, Newsroom, and Newsletters):

### Monitors Sample (2021–2026)
1. **2021 W19** (`monitors/2021/dry-bulk-shipping-market-report-industry-analysis-news-and-rates-week-19-2021.md`):
   - First dry bulk monitor. Capesize 5TC opened at $40,608/d, peaked at $44,817/d, closed at $41,514/d; daily spot value up 15% w-o-w (highest since 2010); C5 West Australia-Qingdao at $14.427/d; West Australia cargo counts 333 in March, 322 in April; Brazil 80 in March, 61 in April; 584 total April cargoes. 100% match.
2. **2023 W13** (`monitors/2023/dry-bulk-week-13-2023.md`):
   - Russian coal flows to China, Capesize tonne-mile demand, China economic reopening indicators. 100% match.
3. **2024 W25** (`monitors/2024/dry-25-2024.md`):
   - Capesize vessel supply at Brazilian ports, West Australia ballaster numbers, iron ore trade momentum. 100% match.
4. **2025 W51** (`monitors/2025/commodity-radar-spotlight-bauxite.md`):
   - Guinea bauxite export surges to China, Capesize fleet utilization, ton-day requirements. 100% match.
5. **2026 W38** (`monitors/2026/weekly-dry-market-monitor-week-38-2026.md`):
   - Capesize supply-demand balance, Panama and Suez transit dynamics, Far East port congestion. 100% match.

### Newsroom Sample (2018–2026)
6. **2018-06-06** (`newsroom/2018/signal-ocean-launch-event-2018.md`):
   - Launch event of the Signal Ocean platform; commercial tanker chartering technology suite. 100% match.
7. **2020-06-26** (`newsroom/2020/capes-vessel-supply-dropped-40-in-june-2020.md`):
   - Capesize vessel supply fell 40% in June 2020; iron ore demand rebound post-lockdowns. 100% match.
8. **2021-10-20** (`newsroom/2021/10th-shell-tanker-joins-signal-maritime-pool.md`):
   - Shell MR tanker fleet expansion into the Signal Maritime Pool (10th vessel commitment). 100% match.
9. **2022-06-21** (`newsroom/2022/ai-in-shipping-how-technology-will-help-shape-the-maritime-landscape.md`):
   - Machine learning algorithms in voyage optimization, speed reduction, and AIS tracking. 100% match.
10. **2023-03-06** (`newsroom/2023/a-look-at-how-freight-markets-moved-emissions-in-bulkers-and-tankers.md`):
    - CII ratings, speed optimization, and carbon emissions across bulkers and tankers. 100% match.
11. **2024-01-10** (`newsroom/2024/dry-bulk-annual-review-2023.md`):
    - Comprehensive 2023 annual market review: Capesize, Panamax, Supramax performance and tonne-mile demand. 100% match.
12. **2025-06-10** (`newsroom/2025/a-kernel-of-truth-on-corn-trade-flows.md`):
    - US and Brazilian corn export volumes, Panamax grain trade seasonality, Panama Canal transit restrictions. 100% match.
13. **2026-01-06** (`newsroom/2026/annual-review-2025-commodities-geopolitical-risk.md`):
    - 2025 annual review: Geopolitical risks, Red Sea diversions, commodity supercycles, crude tanker tonne-mile expansion. 100% match.

### Newsletters Sample (2025–2026)
14. **2025-01-01** (`newsletters/2025/2025-january-newsletter.md`):
    - Platform enhancements, dry bulk freight calculator, tanker emissions tracker. 100% match.
15. **2026-01-01** (`newsletters/2026/january-2026-newsletter.md`):
    - Automated commercial status alerts, fleet tracking API upgrades. 100% match.

---

## 4. Master Series CSV Status

The 2 series CSVs in `data/extracted/series/` were verified against extracted documents:
1. `signal_reports_metadata.csv` (449 rows): Comprehensive catalog of Signal Ocean weekly monitors, newsroom analysis, and newsletters spanning 2018 to 2026.
2. `signal_vessel_counts_series.csv` (120 rows): High-frequency vessel availability counts across key loading regions.

---

## 5. Open Questions & Observations

1. **Junk Figure Caption Hashes**:
   - As documented in the sprint manual, Signal Ocean markdown extractions include automatic figure caption blocks containing image asset hashes (`66b51d5c...`) and screenshot timestamps (`Screenshot 2024-01-26 at 10.50.27`). These are purely cosmetic and do not affect the integrity of market text or series data.
2. **Double URL Percent-Encoding**:
   - Markdown figure URLs contain `%2520` representing double-percent-encoded space characters. Naive regex sweeps flag `2520` as an absent number; stripping markdown image tags resolves all occurrences cleanly.
3. **No Discrepancies or Rate Alteration**:
   - Exactly zero market freight rates, cargo numbers, or trade statistics are hallucinated or transposed.

---

## 6. Audit Conclusion

Signal Ocean (`Monitors`, `Newsroom`, `Newsletters`) is **AUDITED AND VERIFIED (PASS)**.
- 446/446 Markdown documents with corpus sources verified against primary source files.
- 0 absent freight rates, cargo statistics, or market numbers across the entire 2018–2026 archive.
- 100% of flagged raw tokens classified as cosmetic `OK-IMAGE-CAPTION-HASH`.
- 15/15 sampled issues spanning 2018–2026 verified with 100% agreement.
- 0 Markdown defects found; no backfill modifications required.
