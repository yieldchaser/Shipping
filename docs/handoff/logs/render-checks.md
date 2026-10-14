# Render Checks Audit Verdict (Package D)

## Executive Summary
This document records the visual audit of unverified image/raster Markdown tables produced by OCR across four source publishers as specified in Package D:
1. **Seabrokers 2019-05** Seabay Spotlist table (Page 8)
2. **Intermodal 2026 W08 and W09** raster Secondhand Sales (S&P), Demolition, and Currencies tables (Pages 4 and 6)
3. **Fearnleys 2018 W29** raster Newbuilding and S&P tables (Page 3)
4. **Banchero Costa** 20 random MDs containing S&P tables with IMO numbers

Every table was inspected by rendering the source PDF page at 150–300 DPI and comparing cell-by-cell against the Markdown. High-resolution crop renders have been saved to `docs/handoff/evidence/l3-render/`.

---

## Verdict Table

| # | Source | Issue / File | Page | Table Name | Rows Checked | Cells Checked | Mismatches | Verdict | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Seabrokers | 2019-05-01_markedsrapport-mai-2019.md | 8 | Seabay Feature Spotlist | 14 | 140 | 0 | **PASS** | 100% match against web app UI graphic; evidence saved |
| 2 | Intermodal | intermodal_2026_W08 | 4 | Secondhand Sales - Tankers | 7 | 77 | 0 | **PASS** | 100% match against PDF render |
| 3 | Intermodal | intermodal_2026_W08 | 4 | Secondhand Sales - Bulk Carriers | 4 | 44 | 0 | **PASS** | 100% match against PDF render |
| 4 | Intermodal | intermodal_2026_W08 | 6 | Indicative Demolition Prices | 8 | 72 | 0 | **PASS** | 100% match against PDF render |
| 5 | Intermodal | intermodal_2026_W08 | 6 | Currencies | 4 | 20 | 0 | **PASS** | 100% match against PDF render |
| 6 | Intermodal | intermodal_2026_W09 | 4 | Secondhand Sales - Tankers | 4 | 44 | 0 | **PASS** | 100% match against PDF render |
| 7 | Intermodal | intermodal_2026_W09 | 4 | Secondhand Sales - Bulk Carriers | 5 | 55 | 0 | **PASS** | 100% match against PDF render |
| 8 | Intermodal | intermodal_2026_W09 | 6 | Indicative Demolition Prices | 8 | 72 | 0 | **PASS** | 100% match against PDF render |
| 9 | Intermodal | intermodal_2026_W09 | 6 | Currencies | 4 | 20 | 0 | **PASS** | 100% match against PDF render |
| 10 | Fearnleys | fearnleys_2018_W29_fw_week_29_2018b.md | 3 | Newbuilding Contracts | 8 | 64 | 0 | **PASS** | 100% match against scanned PDF render |
| 11 | Fearnleys | fearnleys_2018_W29_fw_week_29_2018b.md | 3 | Sale and Purchase Transactions | 20 | 140 | 0 | **PASS** | 100% match against scanned PDF render |
| 12 | Banchero Costa | 2023_W44_Bancosta-Weekly-2023-44.md | 11 | Reported Sales | 20 | 160 | >20% | **REBUILD NEEDED** | Column shift: original PDF lacked IMO column; header inserted IMO No. shifting all data columns |
| 13 | Banchero Costa | 2024_W08_Bancosta-Weekly-2024-08.md | 11 | Reported Sales | 25 | 225 | >20% | **REBUILD NEEDED** | Column shift: original PDF lacked IMO column; header inserted IMO No. shifting all data columns |
| 14 | Banchero Costa | 2024_W44_Bancosta-Weekly-2024-44.md | 11 | Reported Sales | 21 | 189 | >20% | **REBUILD NEEDED** | Column shift: original PDF lacked IMO column; header inserted IMO No. shifting all data columns |
| 15 | Banchero Costa | 2025_W03_Bancosta-Weekly-2025-03.md | 11 | Reported Sales | 21 | 189 | 0 | **PASS** | IMO '92291781' for Prabhu Yuvika is verbatim as printed in PDF |
| 16 | Banchero Costa | 2025_W04_Bancosta-Weekly-2025-04.md | 16 | Reported Sales | 12 | 108 | 0 | **PASS** | 100% match against PDF render |
| 17 | Banchero Costa | 2025_W07_Bancosta-Weekly-2025-07.md | 16 | Reported Sales | 18 | 162 | 0 | **PASS** | 100% match against PDF render |
| 18 | Banchero Costa | 2025_W17_Bancosta-Weekly-2025-17.md | 16 | Reported Sales | 24 | 216 | 0 | **PASS** | 100% match against PDF render |
| 19 | Banchero Costa | 2025_W19_Bancosta-Weekly-2025-19.md | 16 | Reported Sales | 27 | 243 | 0 | **PASS** | 100% match against PDF render |
| 20 | Banchero Costa | 2025_W20_Bancosta-Weekly-2025-20.md | 16 | Reported Sales | 21 | 189 | 0 | **PASS** | 100% match against PDF render |
| 21 | Banchero Costa | 2025_W21_Bancosta-Weekly-2025-21.md | 11 | Reported Sales | 22 | 198 | 0 | **PASS** | 100% match against PDF render |
| 22 | Banchero Costa | 2025_W23_Bancosta-Weekly-2025-23.md | 16 | Reported Sales | 11 | 99 | 0 | **PASS** | 100% match against PDF render |
| 23 | Banchero Costa | 2025_W27_Bancosta-Weekly-2025-27.md | 16 | Reported Sales | 14 | 126 | 0 | **PASS** | 100% match against PDF render |
| 24 | Banchero Costa | 2025_W48_Bancosta-Weekly-2025-48_compressed.md | 16 | Reported Sales | 19 | 190 | 0 | **PASS** | 100% match against PDF render |
| 25 | Banchero Costa | 2026_W10_Bancosta-Weekly-2026-10.md | 13 | Reported Sales | 23 | 230 | 0 | **PASS** | 100% match; overprinted digits in graphic noted |
| 26 | Banchero Costa | 2026_W16_Bancosta-Weekly-2026-16.md | 16 | Reported Sales | 22 | 220 | 0 | **PASS** | 100% match against PDF render |
| 27 | Banchero Costa | 2026_W18_Bancosta-Weekly-2026-18_compressed.md | 16 | Reported Sales | 22 | 220 | 0 | **PASS** | 100% match against PDF render |
| 28 | Banchero Costa | 2026_W22_Bancosta-Weekly-2026-22_compressed.md | 18 | Reported Sales | 24 | 240 | 0 | **PASS** | 100% match against PDF render |
| 29 | Banchero Costa | 2026_W24_Bancosta-Weekly-2026-24.md | 16 | Reported Sales | 19 | 190 | 0 | **PASS** | 100% match against PDF render |
| 30 | Banchero Costa | 2026_W28_Bancosta-Weekly-2026-28.md | 13 | Reported Sales | 10 | 100 | 0 | **PASS** | 100% match against PDF render |
| 31 | Banchero Costa | 2026_W33_Bancosta-Weekly-2026-33.md | 17 | Reported Sales | 10 | 100 | 0 | **PASS** | 100% match against PDF render |

---

## Detailed Findings & Visual Analysis

### 1. Seabrokers 2019-05 (Page 8)
- **Document:** `corpus/05-seabrokers/pdfs/2019-05-01_markedsrapport-mai-2019.pdf`, Page 8.
- **Table:** Seabay Feature Spotlist UI widget table (14 vessel rows, 10 columns: Vessel Name, BHP, Deck (m³), BP, ROV, Current Charter, Port, Availability, Notes, Next Activity).
- **Visual description:** The printed page has an embedded web UI screenshot of the Seabay 2.0 interface showing active North Sea spotlist vessels.
- **Verification:** All 140 cells match exactly between MD and the graphic. High-res crop saved at `docs/handoff/evidence/l3-render/seabrokers_2019_05_p8_spotlist.png`.

### 2. Intermodal 2026 W08 & W09 (Pages 4 and 6)
- **Document W08:** `corpus/01-brokers/intermodal/2026/intermodal_2026_W08_Intermodal-Report-Week-08-2026.pdf`
  - Page 4: Tankers S&P (7 rows, 77 cells) and Bulk Carriers S&P (4 rows, 44 cells) match 100%.
  - Page 6: Indicative Demolition Prices (8 rows, 72 cells) and Currencies (4 rows, 20 cells) match 100%.
- **Document W09:** `corpus/01-brokers/intermodal/2026/intermodal_2026_W09_Intermodal-Report-Week-09-2026.pdf`
  - Page 4: Tankers S&P (4 rows, 44 cells) and Bulk Carriers S&P (5 rows, 55 cells) match 100%.
  - Page 6: Indicative Demolition Prices (8 rows, 72 cells) and Currencies (4 rows, 20 cells) match 100%.
- **Total cells verified:** 404 cells across 8 tables. 0 mismatches.

### 3. Fearnleys 2018 W29 (Page 3)
- **Document:** `corpus/01-brokers/fearnleys/2018/fearnleys_2018_W29_fw_week_29_2018b.pdf`, Page 3.
- **Tables:**
  - `Newbuilding Contracts`: 8 rows, 8 columns = 64 cells.
  - `Sale and Purchase Transactions`: 20 rows, 7 columns = 140 cells.
- **Visual description:** High-resolution render confirms this is a clean scan/graphic where rates on the left were omitted in favor of the Fearnpulse API feed, and the contracts/S&P tables on the right were extracted via OCR.
- **Verification:** Every single vessel, yard, buyer, price, and comment line matches the scan verbatim. Total: 204 cells checked, 0 mismatches.

### 4. Banchero Costa S&P Image Tables (20 Sampled MDs)
- **Sample Selection:** Deterministic random sample (seed 42) across 2023, 2024, 2025, and 2026.
- **Structural Discovery:**
  - In 2025 and 2026 (17 sampled issues): Banchero Costa updated their S&P template to include an explicit `IMO No.` column. In all 17 issues, the extracted MD tables match the PDF page images (e.g. `2025_W03` prints `92291781` on page 11 verbatim).
  - In 2023 and 2024 (3 sampled issues: `2023_W44`, `2024_W08`, `2024_W44`): The printed PDF tables did NOT include an IMO number column. The previous extraction script inserted `IMO No.` into the table header, which shifted all data columns to the left (DWT into IMO No., Year into DWT, Builder into Year, etc.). Per package instructions ("A table where more than 20% of cells are wrong: do not patch cell by cell — log it as 'rebuild needed' with the page number"), these 3 tables are classified as **REBUILD NEEDED**.
