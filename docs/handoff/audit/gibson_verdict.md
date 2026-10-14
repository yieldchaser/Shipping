# Gibson — Full-Sample Audit Verdict (Lane L3 / antigravity-gemini-1, 2026-10-14)

## Summary

- **Total MDs Audited**: 262 (109 PDF-era from 2021-07 to 2023-09; 153 HTML-era from 2023-10 to 2026-10).
- **Machine Pass**: 262 clean / 0 absent / 0 missing source (`docs/handoff/audit/gibson_machine.csv`). Every number (>= 3 digits) in MD bodies was verified against the source PDF text layers and source HTML DOMs / embedded Chart.js JSON payloads.
- **Stratified Eye Sample**: 12 issues (first and last of each year 2021-2026, including PDF-to-HTML transition points in 2023) visually inspected cell-by-cell against source PDF page renders (via `scripts/verify/page_view.py side`) and HTML source DOMs.
- **Defects Found / Fixed**: 0 defects found. No MD edits or extractor modifications required.
- **Open Questions**: None.

---

## Detailed Eye-Sample Audit Log

### 1. 2021 First Issue: `gibson_2021_2021-02-07-Oil-production-its-a-game-of-two-halves.md`
- **Source**: `corpus/01-brokers/gibson/2021/gibson_2021_2021-02-07-Oil-production-its-a-game-of-two-halves.pdf` (p7)
- **Visual Inspection**: Rendered side-by-side using `page_view.py side`.
- **Tables Checked**:
  - Dirty Tanker Spot Market Developments - Spot Worldscale (3 rows: TD3C, TD20, TD7; 8 cols): 24 cells. All match printed page.
  - Dirty Tanker Spot Market Developments - $/day tce (a) (3 rows, 8 cols): 24 cells. All match printed page.
  - Clean Tanker Spot Market Developments - Spot Worldscale (4 rows: TC1, TC2, TC5, TC7; 8 cols): 32 cells. All match printed page.
  - Clean Tanker Spot Market Developments - $/day tce (a) (4 rows, 8 cols): 32 cells. All match printed page.
  - Bunker Prices ($/tonne) (4 rows: Rotterdam VLSFO, Fujairah VLSFO, Singapore VLSFO, Rotterdam LSMGO; 5 cols): 20 cells. All match printed page.
- **Verdict**: 132/132 cells verified 100%.

### 2. 2021 Last Issue: `gibson_2021_2021-12-17-A-Year-to-Forget.md`
- **Source**: `corpus/01-brokers/gibson/2021/gibson_2021_2021-12-17-A-Year-to-Forget.pdf` (p8)
- **Visual Inspection**: Rendered side-by-side using `page_view.py side`.
- **Tables Checked**: 5 assessment tables (Dirty WS, Dirty TCE, Clean WS, Clean TCE, Bunker Prices). 132 cells compared directly against PDF text and graphic layer.
- **Verdict**: 132/132 cells verified 100%.

### 3. 2022 First Issue: `gibson_2022_2022-01-07-Sticking-to-the-Plan.md`
- **Source**: `corpus/01-brokers/gibson/2022/gibson_2022_2022-01-07-Sticking-to-the-Plan.pdf` (p7)
- **Visual Inspection**: Rendered side-by-side using `page_view.py side`.
- **Tables Checked**: 5 assessment tables (Dirty WS, Dirty TCE, Clean WS, Clean TCE, Bunker Prices). 132 cells checked.
- **Verdict**: 132/132 cells verified 100%.

### 4. 2022 Last Issue: `gibson_2022_2022-12-16-What-the-hell-just-happened.md`
- **Source**: `corpus/01-brokers/gibson/2022/gibson_2022_2022-12-16-What-the-hell-just-happened.pdf` (p8)
- **Visual Inspection**: Rendered side-by-side using `page_view.py side`.
- **Tables Checked**: 5 assessment tables (Dirty WS, Dirty TCE, Clean WS, Clean TCE, Bunker Prices). Footnote records non-eco, non-scrubber basis. 132 cells checked.
- **Verdict**: 132/132 cells verified 100%.

### 5. 2023 Earliest Issue: `gibson_2023_2023-01-06-Stepping-into-2023.md`
- **Source**: `corpus/01-brokers/gibson/2023/gibson_2023_2023-01-06-Stepping-into-2023.pdf` (p7)
- **Visual Inspection**: Rendered side-by-side using `page_view.py side`.
- **Tables Checked**: 5 assessment tables. 132 cells checked.
- **Verdict**: 132/132 cells verified 100%.

### 6. 2023 PDF/HTML Transition (Last PDF): `gibson_2023_2023-09-29-Dream-or-Reality.md`
- **Source**: `corpus/01-brokers/gibson/2023/gibson_2023_2023-09-29-Dream-or-Reality.pdf` (p8)
- **Visual Inspection**: Rendered side-by-side using `page_view.py side`.
- **Tables Checked**: 5 assessment tables. 132 cells checked.
- **Verdict**: 132/132 cells verified 100%.

### 7. 2023 HTML-Era Sample: `gibson_2023-12-15_2023-turmoil.md`
- **Source**: `corpus/01-brokers/gibson/html/2023/2023-12-15_2023-turmoil.html`
- **Visual Inspection**: Compared MD table structures against HTML DOM `<table>` elements and embedded `wpDataCharts` Chart.js vectors.
- **Tables Checked**: Spot Market Developments (14 routes, 6 cols = 84 cells) and Bunker Prices (4 grades, 5 cols = 20 cells).
- **Verdict**: 104/104 cells verified 100%.

### 8. 2024 First Issue: `gibson_2024-01-05_a-year-ahead.md`
- **Source**: `corpus/01-brokers/gibson/html/2024/2024-01-05_a-year-ahead.html`
- **Visual Inspection**: Compared against HTML source DOM and embedded JSON chart arrays.
- **Tables Checked**: Clean and Dirty Tanker Spot Developments + Bunker Prices tables.
- **Verdict**: 104/104 cells verified 100%.

### 9. 2024 Last Issue: `gibson_2024-12-20_the-year-in-review.md`
- **Source**: `corpus/01-brokers/gibson/html/2024/2024-12-20_the-year-in-review.html`
- **Visual Inspection**: Annual review edition with 5 tables (Rates MTD/High/Low, Fleet Size comparison, World Oil Supply/OPEC, Spot Developments, Bunker Prices).
- **Verdict**: All 5 tables match HTML DOM tables 100%.

### 10. 2025 First Issue: `gibson_2025-01-10_sanctions-sting.md`
- **Source**: `corpus/01-brokers/gibson/html/2025/2025-01-10_sanctions-sting.html`
- **Visual Inspection**: Feature chart table (Russian Federation, Iran, Venezuela exports 2019-2024) + Spot Developments + Bunker Prices.
- **Verdict**: 100% exact match against HTML DOM and Chart.js dataset.

### 11. 2025 Last Issue: `gibson_2025-12-19_year-in-review.md`
- **Source**: `corpus/01-brokers/gibson/html/2025/2025-12-19_year-in-review.html`
- **Visual Inspection**: Feature transit chart table (Via Suez Canal vs COGH vs Unknown) + Spot Developments + Bunker Prices.
- **Verdict**: 100% exact match.

### 12. 2026 First Issue: `gibson_2026-01-09_venezuela-reset.md`
- **Source**: `corpus/01-brokers/gibson/html/2026/2026-01-09_venezuela-reset.html`
- **Visual Inspection**: Historical Venezuelan oil production series table (1973-2025) + Spot Developments + Bunker Prices.
- **Verdict**: 100% exact match.

### 13. 2026 Latest Issue: `gibson_2026-10-09_damage-control.md`
- **Source**: `corpus/01-brokers/gibson/html/2026/2026-10-09_damage-control.html`
- **Visual Inspection**: Spot Developments (TD3C, TD20, TD25, TC1, TC18, TC5, TC7 WS and TCE) + Bunker Prices (Rotterdam VLSFO, Fujairah VLSFO, Singapore VLSFO, Rotterdam LSMGO).
- **Verdict**: 104/104 cells verified 100%.
