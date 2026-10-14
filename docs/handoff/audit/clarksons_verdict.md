# Clarksons — Audit Verdict (antigravity-gemini-1, 2026-10-14)

## Summary
- **Source**: Clarksons Hellas S&P Weekly Bulletin
- **Total MDs**: 180 (across 2021–2026)
- **Machine Audit**: 180 / 180 clean (100.0%)
  - Total numbers audited: 5,814
  - Numbers absent from PDF text layer: 0
  - Results logged in: `docs/handoff/audit/clarksons_machine.csv`
- **Eye Audit (Manual 4a)**: 12 stratified issues (2 per year, earliest and latest in each year 2021–2026)
  - Inspected with `page_view.py side`
  - Total cells inspected: 648
  - OCR misreads: 0
  - Column shifts: 0
  - Sign flips: 0
  - Dropped headers/rows: 0
  - Defects found: 0
- **Final Status**: AUDITED — PASS (100% clean)

---

## Machine Sweep Details
- **Corpus Coverage**: 180 MD files checked against primary PDFs under `corpus/02-hellenic/shipbuilding/pdfs/<year>/` and `corpus/01-brokers/clarksons/2026/`.
- **PDF Resolution**:
  - `clarksons_2026_Weekly-Sales-9th-October-2026.md` verified against `corpus/01-brokers/clarksons/2026/clarksons_2026_Weekly-Sales-9th-October-2026.pdf` (clean, 48 numbers matched).
  - Resolved potential edge-case numbers:
    - In `2022-11-04_clarksons-platou-hellas-snp-weekly-bulletin-43_report-04-11-2022_6cc2aef6c200.md`, `3,6000` is printed verbatim in the PDF text layer ("3,6000 TEU").
    - In `2024-02-09_clarksons-platou-hellas-snp-weekly-bulletin-105_weekly-report-090224-fn_cab02cf47631.md`, `2021` was conjoined with `NEW` in the raw text stream (`2021NEW TIMES`).

---

## Stratified Eye Inspection Log (12 Issues)
1. **2021 First** (`2021-07-02_clarkson-platou-hellas-sp-weekly-bulletin-107_report-02-07-2021_e704689b98db.md`):
   - Page 1 inspected: Bulk Carriers (6 rows: Springbank, Vialli, Madonna III, N Discovery, Dream Island, King Cotton) and Tankers (3 rows: Nissos Antiparos, Nissos Santorini, Jasmine Express).
   - 9 rows, 72 cells. Merged en bloc pricing ($180M) correctly distributed. 0 defects.
2. **2021 Last** (`2021-12-24_clarksons-platou-hellas-snp-weekly-bulletin-2_report-24-12-2021_e3fa7387bb9d.md`):
   - Page 1 inspected: Bulk Carriers (5 rows: Atlantic Legend, Scarlet Albatross, Pacific Bless, Pacific Crown, As Elbia) and Tankers (1 row: Voyager).
   - 6 rows, 48 cells. 0 defects.
3. **2022 First** (`2022-01-07_clarksons-platou-hellas-snp-weekly-bulletin-3_report-07-01-2022_aef50b22d82c.md`):
   - Page 1 inspected: Bulk Carriers (4 rows: El Sol Sal, Ikan Senyur, Longshore, Universe Honesty) and Tankers (1 row: Chloe V).
   - 5 rows, 40 cells. 0 defects.
4. **2022 Last** (`2022-12-23_clarksons-platou-hellas-snp-weekly-bulletin-50_report-23-12-2022_55384c8ec8c2.md`):
   - Page 1 inspected: Bulk Carriers (1 row: Alegre III) and Tankers (4 rows: Delta Pioneer, Delta Victory, Delta Captain, Delta Sailor).
   - 5 rows, 40 cells. Multi-row en bloc grouping parsed accurately into 4 rows. 0 defects.
5. **2023 First** (`2023-01-09_clarksons-platou-hellas-snp-weekly-bulletin-51_report-07-01-2023_bcf1cb1da902.md`):
   - Page 1 inspected: Bulk Carriers (3 rows: Aquasalwador, Aquanavigator, Kirishima Sky) and Tankers (3 rows: Cosgreat Lake, Ice Transporter, Syra).
   - 6 rows, 48 cells. 0 defects.
6. **2023 Last** (`2023-12-22_clarksons-platou-hellas-snp-weekly-bulletin-101_report-22-12-2023_5e10d7a044e3.md`):
   - Page 1 inspected: Bulk Carriers empty table; Tankers (1 row: Jag Prabha).
   - 1 row, 8 cells. 0 defects.
7. **2024 First** (`2024-01-05_clarksons-platou-hellas-snp-weekly-bulletin-102_report-05-01-2024_0395b59872c7.md`):
   - Page 1 inspected: Bulk Carriers (8 rows: Capt Tasos, Highland Park, Xing He Hai, Xing Hao Hai, Xing Xi Hai, Xing Shou Hai, Hai Yang Zhi Hua, Ikan Parang); Tankers empty.
   - 8 rows, 64 cells. 0 defects.
8. **2024 Last** (`2024-02-23_clarksons-platou-hellas-snp-weekly-bulletin-107_report-23-02-2024_550496b5b810.md`):
   - Page 1 inspected: Bulk Carriers (9 rows: Pacific Assurance, True Cartier, CMB Pomerol, Zhong Xin Pearl, Angelina, Darya Padma, Paific Integrity, Ultra Vanscoy, Australian Bulker) and Tankers (2 rows: Shogun, Beatrice).
   - 11 rows, 88 cells. 0 defects.
9. **2025 First** (`2025-10-24_clarksons-platou-hellas-snp-weekly-bulletin-111_weekly-sales-24th-oct-2025_e721320e3ba1.md`):
   - Page 3 inspected: Bulker Sales (9 rows: Bulk Sao Paulo, Mineral Subic, AP Power, Fjeld Saga, Ince Ege, Ocean Tact, Arawana, Vega Falktind, Danship Bulker) and Tanker Sales (2 rows: Seavoyager, Jag Pooja).
   - 11 rows, 88 cells. 0 defects.
10. **2025 Last** (`2025-12-19_clarksons-platou-hellas-snp-weekly-bulletin-115_weekly-sales-19th-dec-2025_25b3d59450d8.md`):
    - Page 2 inspected: Bulker Sales (1 row: Wariya Naree) and Tanker Sales (3 rows: STI Gallantry, STI Goal, Nord Superior).
    - 4 rows, 32 cells. 0 defects.
11. **2026 First** (`2026-01-09_clarksons-platou-hellas-snp-weekly-bulletin-116_weekly-sales-09th-jan-2026_bad01e933afa.md`):
    - Page 3 inspected: Bulker Sales (5 rows: Century Shanghai, Starry Night, Jiang Yuan Nan Jing, Fethiye-M, Bulker Bee 30).
    - 5 rows, 40 cells. 0 defects.
12. **2026 Last** (`clarksons_2026_Weekly-Sales-9th-October-2026.md`):
    - Page 3 inspected: Bulker Sales (3 rows: World Diana, AH Globe, Locomotion) and Tanker Sales (7 rows: Marlin Santorini, Marlin Sicily, Marlin Shikoku, SFL Panther, SFL Puma, SFL Lion, SFL Tiger).
    - 10 rows, 80 cells. 0 defects.

**Total Inspected**: 12 issues, 648 cells, 0 defects.
