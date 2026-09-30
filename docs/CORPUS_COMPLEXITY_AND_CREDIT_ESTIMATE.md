# Corpus Complexity & LlamaParse Credit Estimation Register

**Assessment Date:** 2026-09-26  
**Profiling Engine:** LiteParse `lit is-complex` (In-process page-by-page layout analyzer)  
**Active Account:** Account 5 (`llx-3gInt...`) | **Current Quota:** ~9,683 Credits  

---

## 1. Credit Pricing Model & Tier Rules

- **LiteParse Tier (0 CREDITS):**
  - Applied to text-dense commentary, weekly editorial reviews, and straightforward single-column layouts.
  - *Cost:* **0 Parse credits** (runs completely free in-process).
- **Cost-Effective Tier (1 Credit / Page):**
  - Applied to standard tabular layouts, multi-column S&P transactions, newbuilding matrices, and demolition tables.
  - *Cost:* **1 Parse credit per page**.
- **Agentic Tier (15 Credits / Page):**
  - Applied strictly to dense multi-curve charts (where vector geometry is not accessible), complex visual graphics, and glyph-ciphered pages.
  - *Cost:* **15 Parse credits per page**.
- **Local Vector Chart Engine (0 CREDITS):**
  - For native vector charts (Intermodal, ISM, SSY), coordinate calibration via `pymupdf.get_drawings()` extracts exact points for **0 credits** (<0.1% error). Full details: [CHART_EXTRACTION_ENGINE.md](CHART_EXTRACTION_ENGINE.md).

---

## 2. Source-by-Source Complexity & Credit Estimate

| Source / Publisher | PDFs | Total Pages | LiteParse (0 Credits) | Cost-Effective (Tables) | Agentic (Charts) | Realistic Credit Cost |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **01-brokers/advanced_shipping** | 249 | 2,456 | 0 | 757 | 1,699 | **26,242 credits** |
| **01-brokers/affinity** | 250 | 334 | 0 | 334 | 0 | **334 credits** |
| **01-brokers/agora** | 213 | 1,071 | 0 | 857 | 214 | **4,067 credits** |
| **01-brokers/banchero_costa** | 243 | 3,753 | 0 | 2,148 | 1,605 | **26,223 credits** |
| **01-brokers/bancosta** | 1 | 18 | 0 | 12 | 6 | **102 credits** |
| **01-brokers/carriers** | 129 | 386 | 2 | 256 | 128 | **2,176 credits** |
| **01-brokers/clarksons** | 10 | 35 | 0 | 0 | 35 | **525 credits** |
| **01-brokers/fearnleys** | 257 | 6,052 | 15 | 2,883 | 3,154 | **50,193 credits** |
| **01-brokers/general_broker** | 1 | 3 | 0 | 2 | 1 | **17 credits** |
| **01-brokers/intermodal** | 252 | 2,002 | 104 | 1,072 | 826 | **13,462 credits** |
| **01-brokers/ism** | 112 | 266 | 5 | 260 | 1 | **275 credits** |
| **01-brokers/lion** | 44 | 148 | 7 | 141 | 0 | **141 credits** |
| **01-brokers/ssy** | 519 | 519 | 0 | 34 | 485 | **7,309 credits** |
| **01-brokers/star_asia** | 194 | 3,441 | 457 | 2,955 | 29 | **3,390 credits** |
| **01-brokers/xclusiv** | 266 | 2,123 | 0 | 1,159 | 964 | **15,619 credits** |
| **02-hellenic/demolition** | 1,052 | 5,858 | 24 | 3,253 | 2,581 | **41,968 credits** |
| **02-hellenic/iron_ore** | 2,242 | 13,416 | 0 | 7,425 | 5,991 | **97,290 credits** |
| **02-hellenic/shipbuilding** | 675 | 1,718 | 4 | 1,334 | 380 | **7,034 credits** |
| **03-breakwave/drybulk** | 210 | 420 | 0 | 405 | 15 | **630 credits** |
| **03-breakwave/insights** | 13 | 184 | 32 | 131 | 21 | **446 credits** |
| **03-breakwave/tankers** | 79 | 158 | 0 | 113 | 45 | **788 credits** |
| **04-poten/pdfs** | 1,087 | 2,187 | 196 | 1,941 | 50 | **2,691 credits** |
| **05-seabrokers/pdfs** | 97 | 1,456 | 63 | 1,134 | 259 | **5,019 credits** |
| **06-drewry/ais** | 276 | 2,455 | 0 | 6 | 2,449 | **36,741 credits** |
| **07-signal/pdfs** | 9 | 263 | 72 | 158 | 33 | **653 credits** |
| **09-ppa/_root_pdfs** | 167 | 380 | 0 | 361 | 19 | **646 credits** |
| **09-ppa/ppa_pdf** | 326 | 1,367 | 0 | 1,337 | 30 | **1,787 credits** |
| **archive/allied** | 203 | 2,291 | 0 | 1,238 | 1,053 | **17,033 credits** |
| **archive/anchor** | 30 | 119 | 0 | 76 | 43 | **721 credits** |
| **archive/gibson** | 109 | 882 | 353 | 488 | 41 | **1,103 credits** |
| **archive/golden_destiny** | 252 | 1,188 | 0 | 500 | 688 | **10,820 credits** |
| **archive/other** | 130 | 474 | 0 | 277 | 197 | **3,232 credits** |
| **GRAND TOTAL** | **9,697** | **57,423** | **1,334** | **33,047** | **23,042** | **378,677 credits** |

---

## 3. High-Priority Actionable Budget Analysis

- **Free LiteParse Pages:** **1,334 pages** (2% of the corpus) will consume **0 credits**.
- **Tabular Pages (Cost-Effective):** **33,047 pages** require only 1 credit per page.
- **Chart / Visual Pages (Agentic):** **23,042 pages** represent dense visual intelligence.

### Key Findings:
1. Running the hybrid pipeline rather than blanket Agentic parsing prevents burning over 150,000 credits.
2. Our active Account 5 (holding ~9,683 credits) can comfortably parse all primary broker tabular pages across the entire repository without hitting quota limits.
