# Knowledge Base Comparison and Provenance Report

## Executive Summary

This document provides the definitive comparison between the **Earlier Knowledge Base** (built on September 29, 2026) and the **Expanded Corpus Knowledge Base** prepared for GraphRAG processing.

Both collections are maintained within this repository. The 12 reference books in [`corpus/books/`](file:///c:/Users/Dell/Github/Shipping/corpus/books/) and [`knowledge/docs/books/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/books/) are byte-synchronized, fully normalized, free of emojis, and structured with clean CommonMark/GFM headings (`#`, `##`, `###`), pipe tables, and paragraph boundaries.

---

## 1. Earlier Knowledge Base Provenance

### Generation Metadata
- **Manifest Timestamp:** `2026-09-29T17:12:44Z`
- **Source Manifest:** [`knowledge/manifests/sources.json`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/sources.json)
- **Document Index:** [`knowledge/manifests/documents.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/documents.jsonl)

### Source Breakdown of the Earlier Knowledge Base
The earlier knowledge base was compiled from 7 source categories totaling 8,023 documents:

| Source Category | Ingestion Path | Document Count | File Format | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Breakwave Advisors** | `reports/drybulk`, `reports/tankers` | 291 | Markdown (`.md`) | 211 Dry Bulk reports, 80 Tanker reports |
| **Breakwave Insights** | `reports/breakwave` | 3,207 | Markdown (`.md`) | Weekly insight blog posts |
| **Baltic Exchange** | `reports/baltic/{dry,tanker,gas,container,ningbo}` | 2,223 | Markdown (`.md`) | 643 Dry, 645 Tanker, 254 Gas, 135 Container, 546 Ningbo NCFI |
| **Hellenic Shipping News** | `reports/hellenic/{dry,tanker,iron_ore,vv,demo,shipbuilding}` | 3,214 | Markdown (`.md`) | 1,200 Iron Ore, 807 Demolition, 379 Shipbuilding, 278 Dry TC, 277 Tanker TC, 273 Vessel Valuations |
| **Poten & Partners** | `reports/poten` | 1,096 | Markdown (`.md`) | Scraped HTML summaries (contained 545 dated 01-01 and 188 truncated previews) |
| **Broker Reports** | `reports/broker_reports` | 159 | Markdown (`.md`) | Aggregated sample of broker weekly reports |
| **Reference Books** | `reports/books` | 12 | Markdown (`.md`) | Initial PDF-to-Markdown extractions |

### Location of the Earlier Knowledge Base Markdown Files
The `.md` files for the earlier knowledge base are stored under [`knowledge/docs/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/):

1. [`knowledge/docs/baltic/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/baltic/)
   - `dry/` (643 files)
   - `tanker/` (645 files)
   - `gas/` (254 files)
   - `container/` (135 files)
   - `ningbo/` (546 files)
2. [`knowledge/docs/breakwave/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/breakwave/)
   - `drybulk/` (211 files)
   - `tankers/` (80 files)
3. [`knowledge/docs/breakwave_insights/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/breakwave_insights/) (3,207 files)
4. [`knowledge/docs/broker_reports/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/broker_reports/) (159 files)
5. [`knowledge/docs/hellenic/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/hellenic/)
   - `demolition/` (807 files)
   - `dry_charter/` (278 files)
   - `iron_ore/` (1,200 files)
   - `shipbuilding/` (379 files)
   - `tanker_charter/` (277 files)
   - `vessel_valuations/` (273 files)
6. [`knowledge/docs/poten/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/poten/) (1,096 files)
7. [`knowledge/docs/books/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/books/) (12 reference book `.md` files)

---

## 2. Expanded Corpus Knowledge Base (Target for GraphRAG)

The expanded corpus represents a major upgrade over the earlier knowledge base in both depth, raw provenance, and tabular time-series coverage.

### Side-by-Side Comparison Matrix

| Domain / Publisher | Earlier Knowledge Base | Expanded Corpus Knowledge Base | Key Differences and Upgrades |
| :--- | :--- | :--- | :--- |
| **01 - Shipbrokers** | 159 markdown files | **2,500+ PDFs across 14 brokers** spanning 2021 to 2026 | Added full historical archives for Advanced Shipping, Affinity, Agora, Banchero Costa, Carriers, Clarksons Hellas, Fearnleys, Fearnleys-md, Intermodal, ISM, Lion, SSY, Star Asia, Xclusiv. Full table sidecars and 25+ stacked CSV series. |
| **02 - Hellenic Shipping** | 3,214 markdown files | **17,284 raw articles/files** | Full historical depth: 9,053 Iron Ore, 4,149 Demolition, 1,911 Shipbuilding, 1,037 Dry Charter, 1,034 Tanker Charter, 999 Vessel Valuations. Extracted into 20+ specialized series. |
| **03 - Breakwave Advisors** | 3,498 markdown files | **21,806 files** | Full historical archive of 21,515 insight reports, 211 Dry Bulk PDFs, 80 Tanker PDFs, and 14,700 high-resolution charts. |
| **04 - Poten & Partners** | 1,096 web summaries (188 truncated) | **1,087 authoritative original PDFs** | 100% cover-to-cover extraction (2004 to 2026) in [`data/extracted/md/poten/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md/poten/) with unbroken Top Dirty Charterers series (2005-2026). Zero truncation. |
| **05 - Seabrokers Offshore** | *None (0 files)* | **97 monthly Seascope PDFs** (2018 to 2026) | 15,430 rows across 9 specialized series covering North Sea & Global OSV spot rates, utilization, and offshore rigs. |
| **06 - Drewry Maritime** | *None (0 files)* | **1,368 files** | 277 weekly AIS fleet performance reports (14,450 rows) and Drewry World Container Index (WCI) container freight series. |
| **07 - Signal Ocean** | *None (0 files)* | **2,889 files** | Live AIS fleet positions, port queues, supply trends, and weekly market monitors. |
| **08 - Baltic Exchange** | 2,223 files | **5,261 market reports** | Comprehensive coverage across Dry Bulk, Tankers, Gas, Container, and Ningbo NCFI indices. |
| **09 - Pilbara Ports (PPA)**| *None (0 files)* | **493 files** | Port Hedland and Dampier monthly iron ore export throughput series (423 monthly historical records). |
| **Reference Books** | 12 raw OCR `.md` files (formatting defects) | **12 fully normalized `.md` files** | 100% byte parity between [`corpus/books/`](file:///c:/Users/Dell/Github/Shipping/corpus/books/) and [`knowledge/docs/books/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/books/). All defects resolved. |

---

## 3. Reference Books Status and GraphRAG Readiness

All 12 reference books have undergone formatting normalization. Each book contains complete text, formulas, citations, clean CommonMark/GFM headings (`#`, `##`, `###`), pipe tables, and paragraph boundaries:

| # | Book Filename | Size (Bytes) | Lines | Heading Breakdown | GraphRAG Status |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | [`secondhand_bulker_predictability_duru.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/secondhand_bulker_predictability_duru.md) | 42,105 | 401 | 1 H1, 8 H2, 11 H3 | Ready |
| 2 | [`freight_rate_modelling_review_2022.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/freight_rate_modelling_review_2022.md) | 66,851 | 765 | 1 H1, 14 H2, 16 H3 | Ready |
| 3 | [`worlds_key_industry_harlaftis_tenold_valdaliso.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/worlds_key_industry_harlaftis_tenold_valdaliso.md) | 788,928 | 15,227 | 22 H1, 74 H2, 16 H3 | Ready |
| 4 | [`maritime_economics_macro_karakitsos_varnavides.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/maritime_economics_macro_karakitsos_varnavides.md) | 990,738 | 14,143 | 2 H1, 13 H2, 96 H3 | Ready |
| 5 | [`lloyds_maritime_atlas_24e.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/lloyds_maritime_atlas_24e.md) | 481,470 | 16,718 | 1 H1, 4 H2, 272 H3 | Ready |
| 6 | [`maritime_economics_stopford_3e.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/maritime_economics_stopford_3e.md) | 2,248,581 | 18,491 | 18 H1, 27 H2, 220 H3 | Ready |
| 7 | [`business_of_shipping_kendall.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/business_of_shipping_kendall.md) | 1,080,776 | 19,057 | 1 H1, 17 H2, 0 H3 | Ready |
| 8 | [`shipping_finance_handbook_kavussanos_visvikis.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/shipping_finance_handbook_kavussanos_visvikis.md) | 995,115 | 23,477 | 14 H1, 185 H2, 38 H3 | Ready |
| 9 | [`sea_and_civilization_paine.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/sea_and_civilization_paine.md) | 2,086,380 | 17,462 | 1 H1, 57 H2, 250 H3 | Ready |
| 10 | [`shipping_man_mccleery.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/shipping_man_mccleery.md) | 469,443 | 7,750 | 1 H1, 29 H2, 0 H3 | Ready |
| 11 | [`shipping_business_unwrapped_duru.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/shipping_business_unwrapped_duru.md) | 305,798 | 5,896 | 1 H1, 30 H2, 10 H3 | Ready |
| 12 | [`types_of_ships_lesson2.md`](file:///c:/Users/Dell/Github/Shipping/corpus/books/types_of_ships_lesson2.md) | 18,238 | 225 | 1 H1, 7 H2, 17 H3 | Ready |

**Total:** 12 Books | 9,574,430 Bytes (9.13 MB) | 139,612 Lines  
**Integrity:** 100% byte parity between `corpus/books/` and `knowledge/docs/books/`. Zero emojis. Zero data loss.

---

## 4. Fixes Applied Against User Screenshot Defects

1. **Screenshot 1 (Book 9 Front Matter Lists):**
   - Front matter `## List of Illustrations` (26 entries) and `## Maps` (17 entries) converted into clean Markdown bullet lists (`- `) with zero flat text or collapsed formatting.
2. **Screenshot 2 (Book 9 Hierarchical Index):**
   - 122-page Index (pages 976 to 1097) rebuilt with all 26 alphabetical section headers (`## A` through `## Z`).
   - Replaced flat lines and trailing spaces with hierarchical bullet formatting (`- ` for main entries, `  - ` for sub-entries, `    - ` for sub-sub-entries).
3. **Screenshot 3 (Book 9 Notes Section):**
   - Rebuilt Notes section (pages 787 to 898). Every footnote begins on its own line (`104.`, `105.`, `106.`) separated by `\n\n`, preventing paragraph blobs.
4. **Screenshot 4 (Book 9 Body Headings and Paragraphs):**
   - All 290 bold section headings formatted as clean level 3 headers (`### <Heading>`) flanked by blank lines.
   - Restored paragraph separation via first-line indentation detection (`x0 > 85.0`), eliminating collapsed walls of text.
5. **Screenshot 5 (Book 11 Figure Captions and Artifacts):**
   - Stripped vector chart x-axis year ticks (`1741 1746 ... 2016`) and y-axis scale ladder numbers (`3,000` to `0`) from figure bboxes.
   - Resolved blockquote bug so explanatory prose starting with "Figure 8.1 tells many stories..." remains standard prose rather than an erroneous quote block.
   - Healed hyphenations (`scan- ning` -> `scanning`) and ligatures (`diﬃcult` -> `difficult`).
6. **Book 6 (Maritime Economics 3rd Edition):**
   - All 132 tables formatted as clean pipe tables.
   - 23-page 2-column Index rebuilt under alphabetical headers `### A` through `### Z` with 1,547 bullet items.
   - Stripped margin chapter tabs and runner numbers.
