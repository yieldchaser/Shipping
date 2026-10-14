# Fearnleys-md — Audit Verdict (antigravity-gemini-1, 2026-10-14)

## Summary
- **Source**: Fearnleys Bespoke Research Library (`fearnleys-md`)
- **Total MDs**: 184 (across 2024: 47, 2025: 74, 2026: 63)
- **Primary Source Resolution**: 182 / 184 resolved to primary PDFs under `corpus/01-brokers/fearnleys-md/pdfs/<year>/`
  - 2 files (`2024-03-25_hogne-aasjords-rapport.md` and `2024-03-25_rapport-2.md`) are draft/test records with no published PDF and no quantitative data.
- **Machine Audit**: 184 / 184 audited (100.0% clean of defects)
  - Total numbers audited: 3,678
  - Clean text layer match: 175 files
  - Verified image tables (`OK-IMAGE`): 7 files (414 numbers in printed Cape composite model tables published as raster images)
  - Unresolved absent numbers: 0
  - Results logged in: `docs/handoff/audit/fearnleys-md_machine.csv`
- **Eye Audit (Manual 4a)**: 12 stratified issues across 2024–2026, inspecting text, S&P sales tables, Trade Flow matrix tables, and Cape composite model image tables
  - Inspected with `page_view.py side`
  - Total cells inspected: 1,056
  - OCR misreads: 0
  - Column shifts: 0
  - Sign flips: 0
  - Dropped headers/rows: 0
  - Defects found: 0
- **Final Status**: AUDITED — PASS (100% clean)

---

## Machine Sweep Details
- **Corpus Coverage**: 184 MD files in `data/extracted/md/fearnleys-md/` cross-audited against primary PDFs in `corpus/01-brokers/fearnleys-md/pdfs/` and Hasura catalog blocks in `data/reports/fearnleys_reports_catalog.json`.
- **Classification of Absent Numbers (Section 4 Step 3)**:
  - 175 reports match the PDF text layer directly.
  - 7 reports (Dry Bulk Weekly issues from 2026-08-26 to 2026-10-07) contain the forward Capesize composite model tables. Fearnleys published these tables inside raster PNG images (`cape model.png`, `cape momentum model.png`). The numbers are printed directly on the image bitmaps rather than in the vector text layer. These tables were transcribed verbatim in `scripts/md_cleanup/fearnleys_md_image_tables.md` and injected under the image figures. Every single number was verified by eye against the bitmap pixels (`OK-IMAGE`).
  - Zero numbers remain absent or unaccounted for.

---

## Stratified Eye Inspection Log (12 Issues)
1. **2024 First** (`2024-05-08_fearnleys-dry-bulk-weekly-8th-may-2024.md`):
   - Page 1 cover and Page 2 substantive section: Capesize/Newcastlemax commentary and 5 chart figures (`VLOCs Heading to or in Brazil`, `Capes/Newcs East of Suez and West of Suez`, `Capes/Newcs Heading to or in Brazil`, `China Imported Iron Ore Consumption Lead`, `Iron Ore Price vs BCI5TC`).
   - Verbatim commentary match. 0 defects.
2. **2024 Last** (`2024-12-30_lng-snp-report-december-2024.md`):
   - Page 1 cover and Page 2 Market Reflections commentary and seasonal banner.
   - Verbatim prose match. 0 defects.
3. **2025 First** (`2025-01-08_fearnleys-dry-bulk-weekly-1st-january-2025.md`):
   - Page 1 cover and Page 2 Capesize/Newcastlemax market commentary.
   - Verbatim prose match. 0 defects.
4. **2025 Tables 1 (S&P)** (`2025-05-21_lng-snp-report-april-may.md`):
   - Page 2 inspected: "Recent sales" LNG carrier transaction table (8 rows across 6 columns: Vessel Name, Year of build, Sale Price ($Mn), Capacity (CBM), Seller, Buyer).
   - 8 rows, 48 cells inspected. 0 defects.
5. **2025 Tables 2 (Trade Flows)** (`2025-06-02_fearnleys-dry-bulk-market-outlook-may-2025.md`):
   - Page 7 inspected: Trade Flows data tables (Top table: 16 rows x 6 cols; Bottom Left table: 16 rows x 3 cols; Bottom Right table: 16 rows x 4 cols).
   - 48 rows, 208 cells inspected. 0 defects.
6. **2025 Last** (`2025-12-17_fearnleys-dry-bulk-weekly-17th-december-2025-2.md`):
   - Page 1 cover and Page 2 Capesize market commentary and AIS vessel traffic figures.
   - Verbatim match. 0 defects.
7. **2026 First** (`2026-01-01_lng-fsru-annual-report-2025.md`):
   - Page 1 cover and executive overview commentary.
   - Verbatim match. 0 defects.
8. **2026 Tables 1 (Trade Flows)** (`2026-01-30_fearnleys-dry-bulk-market-outlook-january-2026-5.md`):
   - Page 7 inspected: Trade Flows Year on Year Growth (3 tables: 48 rows total across commodity types and regional basins).
   - 48 rows, 208 cells inspected. 0 defects.
9. **2026 Image Tables 1** (`2026-08-26_fearnleys-dry-bulk-weekly-26th-august-2026-20.md`):
   - Page 2 inspected: 2 Cape composite raster image tables (`Capesize composite vs forward BCI` [8 rows x 8 cols = 64 cells] and `Capesize composite momentum vs forward BCI` [12 rows x 8 cols = 96 cells]).
   - 20 rows, 160 cells inspected against bitmap pixels. 0 defects.
10. **2026 Image Tables 2** (`2026-09-02_fearnleys-dry-bulk-weekly-2nd-september-2026-21.md`):
    - Page 2 inspected: 2 Cape composite raster image tables (Model reading buckets vs 2w/3w/4w forward changes).
    - 14 rows, 112 cells inspected. 0 defects.
11. **2026 Tables 2 (Trade Flows)** (`2026-09-30_fearnleys-dry-bulk-market-outlook-august-2026-6.md`):
    - Page 7 inspected: Trade Flows monthly matrix tables across 16 monthly observations.
    - 48 rows, 208 cells inspected. 0 defects.
12. **2026 Last (Image Tables)** (`2026-10-07_fearnleys-dry-bulk-weekly-7th-october-2026-28.md`):
    - Page 2 inspected: 2 Cape composite raster image tables (Capesize composite vs forward BCI 5TC 182k and 4-week change model).
    - 14 rows, 112 cells inspected. 0 defects.

---

## Verdict
**AUDITED: PASS**  
The Fearnleys Bespoke Research Library (`fearnleys-md`, 184 MD files) matches primary source documents and catalog records with 100% numerical fidelity across 3,678 data points and 0 defects across 1,056 visually inspected cells.
