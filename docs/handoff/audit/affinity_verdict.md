# Audit Verdict: Affinity Shipbrokers

- **Source**: Affinity Shipbrokers (`Affinity Tanker Weekly`)
- **Corpus Location**: `corpus/01-brokers/affinity/` (256 primary PDFs across 2021–2026)
- **Extracted Markdown**: `data/extracted/md/affinity/` (249 MDs partitioned by year `2021/` to `2026/`)
- **Extracted Series**: `data/extracted/series/affinity_tce_series.csv`, `affinity_bda_series.csv`, `affinity_indices_series.csv`
- **Auditor**: `antigravity-gemini-1` (Lane 2 `lane/l2-series`)
- **Audit Date**: 2026-10-14
- **Audit Protocol**: `docs/handoff/AGENT_OPERATING_MANUAL.md` Section 4 & 4a

---

## 1. Summary Metrics

| Metric | Result |
|---|---|
| Total Markdown files | **249** |
| Total Sidecars (`.tables.json`) | **249** |
| Total Chart metadata (`.charts.json`) | **249** |
| Machine pass total checked | **249** |
| Machine pass clean (0 absent numbers) | **249** (100.0%) |
| Machine pass flagged (absent > 0) | **0** |
| Missing source PDFs | **0** |
| Stratified eye pass sample size | **13 issues** (26 pages analyzed, cell-by-cell comparison) |
| Stratified eye pass match rate | **100.0%** (all cells, routes, quantities, units, trends match printed PDF) |
| MD defects found | **0** |
| Hand corrections required | **0** |

Machine audit output file: `docs/handoff/audit/affinity_machine.csv`.

---

## 2. Machine Pass Analysis (Step 2 & 3)

The machine sweep extracted all numeric tokens (>=3 digits, excluding standalone 4-digit years) from the Markdown bodies across all 249 documents in `data/extracted/md/affinity/` and verified them against each PDF's primary text layer (`pymupdf` word tokens, testing standard canonical formats including European and comma/period substitutions):

- **Clean documents (0 absent numbers)**: 249 / 249 (100%)
- **Flagged documents (>0 absent numbers)**: 0 / 249
- **Missing PDFs**: 0 / 249 (all resolved across local worktree and corpus root `C:/Users/Dell/Github/Shipping/corpus/01-brokers/affinity/`).

Because no documents had absent numbers, no classification of absent numbers (Step 3) was required.

---

## 3. Stratified Eye Pass Sample (Step 4 & 4a)

Per Section 4 Step 4 and Section 4a of the manual, visual comparisons were conducted across a stratified sample covering first and last issues of each year (2021–2026) plus the major layout transition issue in late 2022 (13 issues total). Each issue was rendered side-by-side using `scripts/verify/page_view.py side`:

### Sample 1: 2021-07-02 (`affinity_2021_Affinity-Tanker-Weekly-02.07.2021-HSN.md`)
- **Image**: `side_p001.png` (Page 0 data panel vs MD tables)
- **BDTI / BCTI card**: BDTI 592 (↓ Softer), BCTI 445 (↓ Softer). Exact match.
- **BDA card**: TKR/LRG 562.3 (+5.0), TKR/MED 563.8 (+4.6), TKR/SML 565.3 (+5.0). Exact match.
- **BALTIC TCE DIRTY card** (8 routes): TD1 (-$17,192), TD3C (-$4,674), TD6 (-$6,312), TD8 ($1,072), TD9 (-$2,816), TD14 ($1,765), TD17 ($3,037), TD20 (-$1,099). All routes, descriptions, quantities (MT), rates, and trends match printed PDF 100%.
- **BALTIC TCE CLEAN card** (7 routes): TC1 ($511), TC2 ($1,834), TC5 ($760), TC6 (WS 119.56), TC7 ($2,643), TC8 (WS 21), TC9 (WS 120). Exact match. Note: Publisher `$ / WS` header mixes explicit WS and $/day values; correctly transcribed.

### Sample 2: 2021-12-24 (`affinity_2021_Affinity-Tanker-Weekly-24.12.2021-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 788 (↓ Softer), BCTI 793 (↓ Softer). Exact match.
- **BDA card**: TKR/LRG 593.1 (-3.0), TKR/MED 594.6 (-4.1), TKR/SML 595.6 (-4.3). Exact match.
- **BALTIC TCE DIRTY card** (8 routes): TD1 (-$17,796), TD3C ($2,044), TD6 ($3,466), TD8 ($3,804), TD9 ($8,198), TD14 ($7,026), TD17 ($22,485), TD20 ($4,219). All cells match 100%.
- **BALTIC TCE CLEAN card** (7 routes): TC1 ($15,540), TC2 ($8,963), TC5 ($10,603), TC6 (WS 259.06), TC7 ($10,013), TC8 ($28), TC9 (WS 222.86). Exact match.

### Sample 3: 2022-01-07 (`affinity_2022_Affinity-Tanker-Weekly-07.01.2022-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 711 (↓ Softer), BCTI 642 (↓ Softer). Exact match.
- **BDA card**: TKR/LRG 591.0 (-2.1), TKR/MED 593.3 (-1.3), TKR/SML 594.5 (-1.1). Exact match.
- **BALTIC TCE DIRTY card** (8 routes): TD1 (-$20,150), TD3C (-$760), TD6 (-$3,625), TD8 ($3,120), TD9 ($3,527), TD14 ($6,320), TD17 ($31,849), TD20 ($1,646). All cells match 100%.
- **BALTIC TCE CLEAN card** (7 routes): TC1 ($6,976), TC2 ($7,145), TC5 ($4,126), TC6 (WS 185.63), TC7 ($8,607), TC8 ($25), TC9 (WS 218.57). Exact match.

### Sample 4: 2022-11-25 (`affinity_2022_Affinity-Tanker-Weekly-25.11.2022-HSN.md` - Transition Issue)
- **Image**: `side_p001.png`
- **Context**: First issue where publisher transitioned the CLEAN card header from `$ / WS` to `$ / Day`.
- **BDTI / BCTI card**: BDTI 2494 (↑ Firmer), BCTI 1770 (↑ Firmer). Exact match.
- **BDA card**: TKR/LRG 527.5 (-14.4), TKR/MED 530.6 (-15.3), TKR/SML 532.5 (-15.8). Exact match.
- **BALTIC TCE DIRTY card** (8 routes): TD1 ($42,599), TD3C ($76,493), TD6 ($170,285), TD8 ($73,790), TD9 ($180,825), TD14 ($74,565), TD17 ($193,154), TD20 ($85,594). All ↑ Firmer, exact match.
- **BALTIC TCE CLEAN card** (7 routes): TC1 ($72,421), TC2 ($45,890), TC5 ($53,891), TC6 ($74,592), TC7 ($49,625), TC8 ($56,529), TC23 ($57,629). Note: Route TC23 introduced replacing TC9. Rates quoted in `$/Day`. All cells match 100%.

### Sample 5: 2022-12-23 (`affinity_2022_Affinity-Tanker-Weekly-23.12.2022-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 1887 (↓ Softer), BCTI 2143 (↑ Firmer). Exact match.
- **BDA card**: TKR/LRG 516.5 (+0.1), TKR/MED 520.1 (+0.6), TKR/SML 524.2 (+2.3). Exact match.
- **BALTIC TCE DIRTY card** (7 routes): TD1 ($22,636), TD3C ($39,356), TD6 ($122,896), TD8 ($75,586), TD9 ($46,888), TD14 ($82,765), TD20 ($48,253). Note: TD17 absent on printed page; MD accurately reflects 7 routes. All cells match 100%.
- **BALTIC TCE CLEAN card** (7 routes): TC1 ($82,128), TC2 ($34,179), TC5 ($69,916), TC6 ($85,115), TC7 ($49,317), TC8 ($75,884), TC23 ($56,576). All cells match 100%.

### Sample 6: 2023-01-06 (`affinity_2023_Affinity-Tanker-Weekly-06.01.2023-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 1391 (↓ Softer), BCTI 1068 (↓ Softer). Exact match.
- **BDA card**: TKR/LRG 529.0 (+6.3), TKR/MED 532.5 (+7.4), TKR/SML 535.3 (+5.3). Exact match.
- **BALTIC TCE DIRTY card** (7 routes): TD1 ($15,162), TD3C ($30,486), TD6 ($90,824), TD8 ($71,413), TD9 ($24,498), TD14 ($81,252), TD20 ($33,560). W-O-W column omitted by publisher on page; MD accurately records `-` for trends. All cells match 100%.
- **BALTIC TCE CLEAN card** (7 routes): TC1 ($67,014), TC2 ($23,698), TC5 ($62,555), TC6 ($34,165), TC7 ($38,780), TC8 ($66,473), TC23 ($26,266). All cells match 100%.

### Sample 7: 2023-12-22 (`affinity_2023_Affinity-Tanker-Weekly-22.12.2023-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 1200 (↑ Firmer), BCTI 960 (↑ Firmer). Exact match.
- **BDA card**: TKR/LRG 493.9 (-1.9), TKR/MED 503.8 (-1.3), TKR/SML 511.9 (-1.1). Exact match.
- **BALTIC TCE DIRTY card** (7 routes): TD1 ($7,699), TD3C ($31,790), TD6 ($58,959), TD8 ($48,432), TD9 ($25,987), TD14 ($40,135), TD20 ($42,579). All cells match 100%.
- **BALTIC TCE CLEAN card** (7 routes): TC1 ($51,159), TC2 ($20,593), TC5 ($38,009), TC6 ($44,834), TC7 ($24,148), TC8 ($55,206), TC23 ($26,887). All cells match 100%.

### Sample 8: 2024-01-05 (`affinity_2024_Affinity-Tanker-Weekly-05.01.2024-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 1384 (↑ Firmer), BCTI 799 (↓ Softer). Exact match.
- **BDA card**: TKR/LRG 492.8 (-1.1), TKR/MED 502.9 (-0.9), TKR/SML 510.1 (-1.8). Exact match.
- **BALTIC TCE DIRTY card** (8 routes): TD3C ($30,738), TD6 ($63,193), TD8 ($49,997), TD9 ($76,837), TD14 ($39,418), TD20 ($57,480), TD22 ($36,298), TD25 ($75,916). Note: New routes TD22 and TD25 added. All cells match 100%.
- **BALTIC TCE CLEAN card** (7 routes): TC1 ($35,058), TC2 ($5,600), TC5 ($28,600), TC6 ($25,811), TC7 ($24,623), TC8 ($46,486), TC23 ($29,331). All cells match 100%.

### Sample 9: 2024-12-20 (`affinity_2024_Affinity-Tanker-Weekly-20.12.2024-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 914 (↓ Softer), BCTI 627 (↓ Softer). Exact match.
- **BDA card**: TKR/LRG 466.0 (-3.1), TKR/MED 472.3 (-4.0), TKR/SML 475.7 (-3.5). Exact match.
- **BALTIC TCE DIRTY card** (8 routes): TD3C ($18,726), TD7 ($35,817), TD15 ($26,623), TD19 ($42,246), TD20 ($28,613), TD22 ($28,066), TD26 ($42,732), TD27 ($28,311). Routes reflect 2024 route expansion. All cells match 100%.
- **BALTIC TCE CLEAN card** (10 routes): TC1 ($18,988), TC2 ($11,571), TC5 ($11,790), TC6 ($17,475), TC7 ($14,244), TC8 ($15,000), TC14 ($27,828), TC17 ($20,162), TC20 ($20,733), TC21 ($47,379). Expansion to 10 routes correctly captured. All cells match 100%.

### Sample 10: 2025-01-03 (`affinity_2025_Affinity-Tanker-Weekly-03.01.2025-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 841 (↓ Softer), BCTI 591 (↓ Softer). Exact match.
- **BDA card**: TKR/LRG 466.8 (+0.3), TKR/MED 472.4 (-0.1), TKR/SML 476.9 (-0.4). Exact match.
- **BALTIC TCE DIRTY card** (9 routes): TD3C ($21,643), TD7 ($30,895), TD15 ($26,360), TD19 ($39,897), TD20 ($22,070), TD22 ($25,328), TD25 ($23,882), TD26 ($21,266), TD27 ($23,290). All 9 routes match 100%.
- **BALTIC TCE CLEAN card** (10 routes): TC1 ($22,205), TC2 ($7,378), TC5 ($14,004), TC6 ($18,017), TC7 ($14,241), TC8 ($18,154), TC14 ($13,787), TC17 ($17,634), TC20 ($25,527), TC21 ($13,161). All 10 routes match 100%.

### Sample 11: 2025-12-19 (`affinity_2025_Affinity-Tanker-Weekly-19.12.2025-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 1401 (↑ Firmer), BCTI 751 (↑ Firmer). Exact match.
- **BDA card**: TKR/LRG 409.1 (-0.5), TKR/MED 415.8 (-0.9), TKR/SML 419.5 (-1.4). Exact match.
- **BALTIC TCE DIRTY card** (9 routes): TD3C ($110,068), TD7 ($71,230), TD15 ($94,771), TD19 ($69,018), TD20 ($77,027), TD22 ($82,809), TD25 ($63,437), TD26 ($78,573), TD27 ($73,879). All cells match 100%.
- **BALTIC TCE CLEAN card** (10 routes): TC1 ($36,146), TC2 ($9,765), TC5 ($28,705), TC6 ($40,265), TC7 ($27,785), TC8 ($31,463), TC14 ($21,574), TC17 ($28,184), TC20 ($36,993), TC21 ($22,118). All cells match 100%.

### Sample 12: 2026-01-09 (`affinity_2026_Affinity-Tanker-Weekly-09.01.2026-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 1259 (↑ Firmer), BCTI 713 (↓ Softer). Exact match.
- **BDA card**: TKR/LRG 408.3 (-0.9), TKR/MED 414.7 (-1.1), TKR/SML 418.7 (-0.8). Exact match.
- **BALTIC TCE DIRTY card** (9 routes): TD3C ($59,536), TD7 ($56,863), TD15 ($59,260), TD19 ($49,092), TD20 ($57,352), TD22 ($63,480), TD25 ($61,327), TD26 ($72,485), TD27 ($58,574). All cells match 100%.
- **BALTIC TCE CLEAN card** (10 routes): TC1 ($43,598), TC2 ($6,361), TC5 ($31,766), TC6 ($12,167), TC7 ($26,726), TC8 ($28,033), TC14 ($21,883), TC17 ($24,341), TC20 ($39,030), TC21 ($30,276). All cells match 100%.

### Sample 13: 2026-10-09 (`affinity_2026_Affinity-Tanker-Weekly-09.10.2026-HSN.md`)
- **Image**: `side_p001.png`
- **BDTI / BCTI card**: BDTI 7964 (↑ Firmer), BCTI 2403 (↓ Softer). Exact match.
- **BDA card**: TKR/LRG 505.6 (-0.5), TKR/MED 513.8 (-1.2), TKR/SML 516.5 (-1.6). Exact match.
- **BALTIC TCE DIRTY card** (9 routes): TD3C ($1,412,243), TD7 ($525,034), TD15 ($762,720), TD19 ($368,066), TD20 ($570,375), TD22 ($634,974), TD25 ($308,695), TD26 ($399,604), TD27 ($571,207). All cells match 100%.
- **BALTIC TCE CLEAN card** (10 routes): TC1 ($270,681), TC2 ($12,700), TC5 ($193,738), TC6 ($61,356), TC7 ($68,233), TC8 ($184,976), TC14 ($31,560), TC17 ($113,399), TC20 ($283,128), TC21 ($27,619). All cells match 100%.

---

## 4. Master Series CSV Status

The three series CSVs were audited against the sidecars and MD tables:

1. **`data/extracted/series/affinity_tce_series.csv`**:
   - Total rows: **4,058**
   - Date range: **2021-07-02 to 2026-10-09**
   - Status: Complete, verified against sidecars and primary reports.
2. **`data/extracted/series/affinity_bda_series.csv`**:
   - Total rows: **747**
   - Date range: **2021-07-02 to 2026-10-09**
   - Status: Complete, verified against sidecars and primary reports.
3. **`data/extracted/series/affinity_indices_series.csv`**:
   - Total rows: **496**
   - Date range: **2021-07-02 to 2026-10-02**
   - Status: Clean historical series up to 2026-10-02.

---

## 5. Open Questions & Observations

1. **Missing 2026-10-09 in `affinity_indices_series.csv`**:
   - `affinity_tce_series.csv` and `affinity_bda_series.csv` both include the final issue (`2026-10-09`), but `affinity_indices_series.csv` stops at `2026-10-02` (496 rows instead of 498).
   - The sidecar `data/extracted/md/affinity/2026/affinity_2026_Affinity-Tanker-Weekly-09.10.2026-HSN.tables.json` has the indices fully parsed (`bdti: 7964.0`, `bcti: 2403.0`).
   - Per `docs/handoff/lanes.json`, `affinity_indices_series.csv` is not owned by Lane 2 (`l2-series` owns only `advanced_shipping_*`, `intermodal_baltic_tc_series`, and `ism_*`), so modifying it in this lane would fail governance rule E7. The 2-row append can be performed by the owning lane or during the weekend merge.
2. **2021–2022 `$ / WS` Publisher Unit Formatting**:
   - As documented in `docs/affinity_ws_verdict.md`, 68 issues in 2021 and early 2022 print `$ / WS` as the header for the CLEAN card while mixing explicit Worldscale rates (e.g. TC6 `WS 119.56`) with $/day rates (e.g. TC1 `$511`).
   - The extractor handles this properly using `unit_source` and preserves the raw printed values. Downstream consumers should continue to respect `unit_source`.

---

## 6. Audit Conclusion

Affinity Shipbrokers is **AUDITED AND VERIFIED (PASS)**.
- 249/249 Markdown documents match primary PDF text layers with zero absent numbers.
- 13/13 sampled issues verified cell-by-cell against rendered PDF card panels with 100% agreement.
- 0 Markdown defects found; no backfill modifications required.
