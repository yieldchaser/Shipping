# RAG System Evolution and Knowledge Architecture

This dossier provides a comprehensive architectural audit and comparative reference detailing the two distinct data and retrieval systems within this repository:
1. **The Earlier Simple Document RAG System (`knowledge/`)**: A classical, flat document chunking, BM25-indexed, and regex-signal knowledge base built by [`scripts/process_knowledge.py`](file:///c:/Users/Dell/Github/Shipping/scripts/process_knowledge.py). This system directly powers the live dashboard ([`index.html`](file:///c:/Users/Dell/Github/Shipping/index.html)), client-side search, and the automated daily brief compiler ([`generate_brief.py`](file:///c:/Users/Dell/Github/Shipping/generate_brief.py)).
2. **The New Canonical Data Foundation (`corpus/` and `data/extracted/`)**: An immutable, complete raw data lake organizing all maritime intelligence into 10 structured namespaces, accompanied by cover-to-cover Markdown extractions ([`data/extracted/md/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md/)) and over 60 stacked relational time-series datasets ([`data/extracted/series/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/series/)). This layer serves as the verified data substrate upon which future Graph RAG systems will be built.

---

## PART 1: THE EARLIER KNOWLEDGE & SIMPLE RAG SYSTEM (`knowledge/`)

### 1.1 Architectural Paradigm: Simple Document RAG (Not Graph RAG)

The earlier retrieval system built in [`knowledge/`](file:///c:/Users/Dell/Github/Shipping/knowledge/) is a traditional, flat **Document Chunk RAG**, not a Graph RAG. It possesses no concept of graph nodes, entity resolution, typed directional edges, or multi-hop relationship traversals. 

Instead, it was constructed around:
* Fixed-token sliding window chunking (`cl100k_base` BPE tokenizer via `tiktoken`).
* Heading-level Abstract Syntax Tree (AST) document hierarchy JSON trees.
* Sparse inverted-index term shards for client-side BM25 search.
* Heuristic regex pattern matching for extracting market rate signals and forward sentiment flags.
* Summarization blobs generated via local Ollama/NIM LLM prompts.

```
                      +---------------------------------------+
                      | Legacy Raw Archive (reports/ & misc)  |
                      | (corpus/ did NOT exist at this stage) |
                      +---------------------------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |      scripts/process_knowledge.py     |
                      |  (4,621-line monolithic chunk engine) |
                      +---------------------------------------+
                                          |
         +--------------------------------+--------------------------------+
         |                                |                                |
         v                                v                                v
+------------------+             +------------------+             +------------------+
| knowledge/docs/  |             | knowledge/chunks/|             | knowledge/trees/ |
| Frontmatter MD   |             | Sharded JSONL    |             | Outline JSON     |
+------------------+             +------------------+             +------------------+
         |                                |                                |
         +--------------------------------+--------------------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |           knowledge/derived/          |
                      |   signals_public.jsonl (scalar feeds) |
                      |   section_index.jsonl (AST anchors)   |
                      |   chunks/search/ (inverted shards)    |
                      +---------------------------------------+
                                          |
                     +--------------------+--------------------+
                     |                                         |
                     v                                         v
+------------------------------------------+ +-----------------------------------+
|          Client-Side Dashboard           | |      Daily Intelligence Brief     |
|                index.html                | |         generate_brief.py         |
| (Intelligence, Q&A, and Analytics Tabs)  | |  (Compiles morning macro briefs)  |
+------------------------------------------+ +-----------------------------------+
```

---

### 1.2 Physical Storage Topology Prior to `corpus/`

**Critical Historical Context:** When the earlier knowledge system was originally designed and built, the [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/) directory **did not exist**. 

Raw source documents lived in the legacy [`reports/`](file:///c:/Users/Dell/Github/Shipping/reports/) directory or were scattered across temporary scripts and scratch directories:
* Foundational textbooks were placed loose in the root: `reports/*.pdf`.
* Breakwave biweekly reports were in `reports/drybulk/*.pdf` and `reports/tankers/*.pdf`.
* Breakwave Insights web articles were in `reports/breakwave/<year>/*.html`.
* Baltic Exchange weekly roundups were in `reports/baltic/<category>/*.html`.
* Hellenic Shipping News articles were in `reports/hellenic/<category>/*.html` (with companion media in `assets/`).
* Shipbroker summaries were in `reports/broker_reports/<year>/<broker>/*.md`.
* Poten article previews were in `reports/poten/*.md`.
* Drewry AIS reports were misplaced in `scripts/drewry_ais_pdfs/` (gitignored).
* Pilbara Ports Authority (PPA) files were scattered across `scratch/ppa_pdf/` and `scratch/`.
* Raw broker PDF weeklies were left unorganized in `reports/shipbrokers/<broker>/<year>/`.

#### Addressing the Poten and Broker Digestion Question
How did the earlier system reference "poten" and "broker reports" if `corpus/` did not exist?
1. **The Broker Reports in the Earlier System Were Only Web Digests**:
   The earlier compiler (`process_knowledge.py`) **never processed the thousands of raw broker PDFs** (Clarksons, Xclusiv, Banchero Costa, Intermodal, Star Asia, etc.). It only ingested a tiny collection of 138 markdown files located at `reports/broker_reports/<year>/<broker>/*.md` (later aliased to `corpus/01-brokers/_digests/`). These were third-party qualitative summaries syndicated on Hellenic Shipping News, containing high-level prose commentary but zero granular transaction tables.
2. **The Poten Files in the Earlier System Were Only Truncated Web Previews**:
   The earlier compiler only ingested web markdown preview files stored in `reports/poten/*.md`. These were web article scrapes where 545 files were erroneously stamped with `unknown-01-01` dates, and 188 files were truncated with trailing `... Read More" />` boilerplate. The 1,087 authoritative Poten PDF reports (spanning 2004 to 2026) were **never ingested** into the earlier RAG system.
3. **Completely Absent Sources**:
   The earlier RAG system had zero coverage of:
   * 2,058 raw shipbroker weekly PDFs across all 16 broker desks.
   * 277 Drewry AIS vessel deployment and congestion tracking reports.
   * 97 Seabrokers monthly OSV and offshore drilling Seascope reviews.
   * 492 Pilbara Ports Authority (PPA) bulk export statistics.
   * Signal Ocean live fleet positions, vessel counts, and port queue telemetry.
   * CFTC freight derivatives positioning statements.

---

### 1.3 Data Extraction Limitations in the Earlier System

The data extraction in the earlier knowledge system was incomplete, unstructured, and flat:

1. **No Layout-Aware or Vision Parsing**:
   * Documents were processed using standard BeautifulSoup tag stripping (for HTML) or basic PyMuPDF plain-text streams (for PDFs).
   * Multi-column layouts in PDFs caused sentences to merge across columns (e.g. text from the left column interweaving with text from the right column).
   * Encrypted/ciphered PDF font encodings (such as Banchero Costa W39) decoded into garbled mojibake characters.
2. **No Multi-Column Tabular Extraction**:
   * Complex tabular records (S&P transaction lists, demolition beaching deals, newbuilding orders, vessel valuation matrices) were completely unparsed as structured data.
   * In HTML reports, tables were either dumped as crude newline-separated text strings or skipped entirely.
   * In PDFs, table gridlines and cell boundaries were ignored, resulting in disconnected fragments of numbers and vessel names floating in prose.
3. **Brittle Heuristic Regex Signal Extraction**:
   * Freight rates and commodity prices were extracted using basic regular expressions, such as:
     ```python
     re.compile(r"\$[\d,]+\s*/\s*(?:day|mt|tonne)")
     ```
   * Segment categorization relied on short keyword matching without strict word boundaries (e.g., matching `"cape"`, `"pana"`, `"supra"`, `"won"`, `"won"` as handysize, or `"pa"` as panamax), producing high rates of false positives.
   * Rates were captured as isolated scalar values without associating them with specific vessel names, deadweight tonnage, build year, buyer, seller, or duration tenor.
4. **Zero Relational Data Output**:
   * The earlier system did not output structured time-series CSVs, database tables, or primary-key records.
   * It produced only unstructured text chunks and summary strings.

---

### 1.4 The Processing Pipeline: `scripts/process_knowledge.py`

The compilation engine for the earlier RAG system is [`scripts/process_knowledge.py`](file:///c:/Users/Dell/Github/Shipping/scripts/process_knowledge.py), a 4,621-line script.

#### Ingestion Workflow (`iter_source_files`)
The compiler traverses source files based on hardcoded source filters:
* `book`: Reads `reports/*.pdf` (the 12 maritime textbooks).
* `breakwave`: Reads `reports/drybulk/*.pdf` and `reports/tankers/*.pdf`.
* `baltic`: Reads `reports/baltic/{category}/**/*.html` across 5 categories (`dry`, `tanker`, `gas`, `container`, `ningbo`).
* `breakwave_insights`: Reads `reports/breakwave/**/*.html`.
* `hellenic`: Reads `reports/hellenic/{category}/**/*.html` across 6 categories (`dry_charter`, `tanker_charter`, `iron_ore`, `vessel_valuations`, `demolition`, `shipbuilding`).
* `broker_reports`: Reads `reports/broker_reports/<year>/<broker>/*.md` (aliased to `_digests/`).
* `poten`: Reads `reports/poten/*.md` (the flat web preview markdown files).

#### Artifacts Materialized in `knowledge/`
1. **[`knowledge/docs/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/)**:
   Structured Markdown files partitioned by `{source}/{category}/{year}/{doc_id}.md` with YAML frontmatter containing metadata tags (`vessel_classes`, `regions`, `commodities`, `summary`, `market_tone`).
2. **[`knowledge/chunks/`](file:///c:/Users/Dell/Github/Shipping/knowledge/chunks/)**:
   Tokenized JSONL shards partitioned by source, category, and year (`{source}_{category}_{year}.jsonl`).
   * Sizing: 450 tokens (Breakwave), 600 tokens (Baltic), 500 tokens (General/Books) with 60 to 100 token overlaps.
   * Record schema: `chunk_id`, `doc_id`, `source`, `category`, `year`, `text`, `has_rates`, `has_forecast`, `vessel_classes_matched`, `regions_matched`, `snippet`.
3. **[`knowledge/trees/`](file:///c:/Users/Dell/Github/Shipping/knowledge/trees/)**:
   JSON trees modeling document heading structure (`node_id`, `level`, `ordinal`, `token_count`).
4. **[`knowledge/derived/`](file:///c:/Users/Dell/Github/Shipping/knowledge/derived/)**:
   * `signals_public.jsonl`: The primary data feed read by [`index.html`](file:///c:/Users/Dell/Github/Shipping/index.html). Stripped of heavy LLM blobs to stay lightweight, containing document summaries, dates, titles, and topic tags.
   * `signals.jsonl`: Heavy internal archive (~92 MB) containing raw LLM output blobs.
   * `section_index.jsonl`: Flat index of all document section anchors.
5. **[`knowledge/chunks/search/`](file:///c:/Users/Dell/Github/Shipping/knowledge/chunks/search/)**:
   Pre-tokenized inverted-index shards compiled by [`scripts/search_index_build.py`](file:///c:/Users/Dell/Github/Shipping/scripts/search_index_build.py) for fast in-browser BM25 token lookups.
6. **[`knowledge/wiki/`](file:///c:/Users/Dell/Github/Shipping/knowledge/wiki/)**:
   Static encyclopedia articles generated by [`scripts/build_wiki.py`](file:///c:/Users/Dell/Github/Shipping/scripts/build_wiki.py) for vessel classes and key maritime trade corridors.

---

### 1.5 Incremental Updating Mechanics & Historical Baseline

#### Incremental Compilation Logic
The compiler implements an incremental caching layer:
* **Manifest Registers**:
  * [`knowledge/manifests/documents.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/documents.jsonl): Logs every compiled document, recording `doc_id`, `source_path`, `source_hash`, `compiler_version`, and timestamp.
  * [`knowledge/manifests/derived_cache.json`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/derived_cache.json): Tracks SHA-256 byte hashes of input files.
* **Skip Condition**:
  When `process_knowledge.py` runs, it computes the SHA-256 hash of each input file. If the hash matches `derived_cache.json` and the document exists in `documents.jsonl`, compilation is skipped.

#### Brittleness and Path Fragility
Because `documents.jsonl` recorded absolute or relative file paths from the legacy directory layout (e.g., `reports/hellenic/...`), moving files broke cache lookups. For instance, migrating Hellenic files to `corpus/02-hellenic/` left 2,702 entries in `documents.jsonl` pointing to obsolete paths, causing re-ingestion passes to skip them unless an explicit path translation layer was applied.

---

### 1.6 How the Earlier System is Consumed in the Live UI (`index.html`)

The legacy knowledge base directly drives several UI components in [`index.html`](file:///c:/Users/Dell/Github/Shipping/index.html):

1. **Intelligence Tab**:
   * Fetches [`knowledge/derived/signals_public.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/derived/signals_public.jsonl).
   * Renders the executive market intelligence feed, filtering articles by vessel class, commodity, and market tone (bullish, bearish, neutral).
2. **Q&A and Context Retrieval (`QA_CHUNK_FILES`)**:
   * Lines 38145 to 38220 of `index.html` define `QA_CHUNK_FILES`, an explicit registry of JSONL chunk shards mapped to UI categories:
     * **Breakwave Tab**: Loads `breakwave_drybulk_*.jsonl`, `breakwave_tankers_*.jsonl`, `breakwave_insights_insights_*.jsonl`, `broker_reports_broker_report_2026.jsonl`, and `poten_tankers_*.jsonl`.
     * **Baltic Tab**: Loads `baltic_dry_*.jsonl`, `baltic_tanker_*.jsonl`, `baltic_container_*.jsonl`, `baltic_gas_*.jsonl`, and `baltic_ningbo_*.jsonl`.
     * **Hellenic Tab**: Loads `hellenic_dry_charter_*.jsonl`, `hellenic_tanker_charter_*.jsonl`, and `hellenic_vessel_valuations_*.jsonl`.
     * **Iron Ore Tab**: Loads `hellenic_iron_ore_*.jsonl` and `broker_reports_broker_report_2026.jsonl`.
     * **Shipbuilding Tab**: Loads `hellenic_shipbuilding_*.jsonl`, `hellenic_demolition_*.jsonl`, and `fleet_orderbook_*.jsonl`.
     * **Books Tab**: Loads `books.jsonl`.
   * Queries dynamically rank chunks using client-side TF-IDF / BM25 algorithms in JavaScript.
3. **Automated Daily Briefing ([`generate_brief.py`](file:///c:/Users/Dell/Github/Shipping/generate_brief.py))**:
   * Reads `signals_public.jsonl` to compile daily morning shipping macro briefings across chartering, S&P, and commodity flows.

---

## PART 2: THE NEW CANONICAL DATA FOUNDATION (`corpus/` and `data/extracted/`)

The limitations of the earlier simple RAG system led to the creation of the **Canonical Data Foundation**. This layer separates raw immutable documents from structured extractions, establishing a verified data substrate.

---

### 2.1 The Canonical Raw Corpus (`corpus/`)

The [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/) directory unites all raw shipping intelligence into 10 structured, numbered source namespaces:

| Namespace | Source Publisher | Scope & File Population | Cadence | Content Types |
| :--- | :--- | :--- | :--- | :--- |
| [`01-brokers/`](file:///c:/Users/Dell/Github/Shipping/corpus/01-brokers/) | 16 Live Shipbroking Firms | 2,058 PDFs (2021–2026) across Clarksons, Xclusiv, Banchero Costa, Intermodal, Star Asia, Advanced Shipping, Fearnleys, SSY, Agora, Affinity, ISM, Lion, Carriers | Weekly | Desk commentary, S&P fixtures, demolition sales, newbuilding orders, charter rates |
| [`02-hellenic/`](file:///c:/Users/Dell/Github/Shipping/corpus/02-hellenic/) | Hellenic Shipping News | 18,183 reports across Demolition, Dry Charter, Tanker Charter, Iron Ore, Shipbuilding, Vessel Valuations | Daily / Weekly | Fixtures, scrap prices, MMi iron ore daily indexes, valuation matrices, companion charts |
| [`03-breakwave/`](file:///c:/Users/Dell/Github/Shipping/corpus/03-breakwave/) | Breakwave Advisors | 211 Dry Bulk PDFs, 80 Tanker PDFs, and 3,194 Breakwave Insights HTML articles | Daily / Weekly | Macro dry bulk & tanker reviews, research essays, 14,700 high-resolution charts |
| [`04-poten/`](file:///c:/Users/Dell/Github/Shipping/corpus/04-poten/) | Poten & Partners | 1,087 authoritative PDFs (2004–2026) | Weekly | Tanker market opinions, annual/midterm Top Dirty Spot Charterer rankings |
| [`05-seabrokers/`](file:///c:/Users/Dell/Github/Shipping/corpus/05-seabrokers/) | Seabrokers Group | 97 monthly Seascope PDFs (2018–2026) | Monthly | Offshore support vessels (OSV), rig utilization, dayrates, subsea market analysis |
| [`06-drewry/`](file:///c:/Users/Dell/Github/Shipping/corpus/06-drewry/) | Drewry Maritime | 277 weekly AIS vessel tracking PDFs and 1,091 Maritime Opinion briefings | Weekly | Fleet performance, AIS port queues, container freight indexes (WCI), opinions |
| [`07-signal/`](file:///c:/Users/Dell/Github/Shipping/corpus/07-signal/) | Signal Ocean | 2,369 files (API telemetry, weekly market monitors, dry bulk & tanker snapshots) | Weekly | Vessel availability counts, port congestion queues, tanker commercial speeds |
| [`08-baltic/`](file:///c:/Users/Dell/Github/Shipping/corpus/08-baltic/) | Baltic Exchange | 5,261 market roundup HTML snapshots (Dry, Tanker, Gas, Container, Ningbo NCFI) | Weekly | Official freight assessments, route fixtures, BDA demolition assessments |
| [`09-ppa/`](file:///c:/Users/Dell/Github/Shipping/corpus/09-ppa/) | Pilbara Ports Authority | 492 monthly reports (Port Hedland & Dampier iron ore export statistics) | Monthly | Real iron ore throughput tonnage, destination nation breakdowns (China, Japan, Korea) |
| [`10-cftc/`](file:///c:/Users/Dell/Github/Shipping/corpus/10-cftc/) | CFTC | 138 Commitment of Traders derivative reports | Monthly | Freight and energy futures trader positioning |
| [`books/`](file:///c:/Users/Dell/Github/Shipping/corpus/books/) | Academic Textbooks | 12 foundational maritime economics and shipping finance reference books | Reference | Foundational industry economics, legal principles, voyage modeling |
| [`archive/`](file:///c:/Users/Dell/Github/Shipping/corpus/archive/) | Inactive Publishers | Historical reports from Allied, Gibson, Anchor, Golden Destiny | Archived | Historical market cycle context |

---

### 2.2 Publication-Grade Cover-to-Cover Extractions (`data/extracted/md/`)

Unlike the chunked snippets in `knowledge/chunks/`, files in [`data/extracted/md/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md/) represent complete, cover-to-cover transcriptions produced with PyMuPDF and LlamaParse:
* **Zero Truncation**: Preserves complete desk commentary, market overviews, and regional analysis without token limits.
* **Standardized Frontmatter**: YAML metadata including `title`, `issue_date` (`YYYY-MM-DD`), `year`, `broker`/`source`, `pages`, and `source_file`.
* **Structured Markdown Pipe Tables**: Every table is rendered as clean Markdown and mirrored into structured JSON sidecars (`<stem>.tables.json`) for programmatic querying.
* **Embedded Visual Artifacts**: High-resolution chart figures are clipped at 200 DPI into `data/extracted/charts/` and linked directly in the markdown body.

---

### 2.3 Stacked Relational Time-Series Layer (`data/extracted/series/`)

The structured series layer contains over 60 stacked CSV datasets with over 140,000 structured rows. Every record is standardized with an ISO date (`issue_date`), report week (`report_week`), primary keys, and source provenance:

1. **Secondhand S&P Sales**:
   * Master series: `clarksons_sales_series.csv`, `bancosta_sales_series.csv`, `intermodal_sales_series.csv`, `xclusiv_sales_series.csv`, `advanced_shipping_sales_series.csv`, `carriers_sales_series.csv`, `lion_sales_series.csv`.
   * Standardized fields: `issue_date`, `vessel_name`, `vessel_type`, `imo`, `dwt`, `built_year`, `shipyard`, `price_usd_m`, `buyer`, `seller`.
2. **Demolition and Ship Recycling**:
   * Master series: `star_asia_demolition_series.csv`, `star_asia_deals_series.csv`, `hellenic_athenian_demolition_series.csv`, `hellenic_gms_demolition_series.csv`, `hellenic_best_oasis_deals_series.csv`, `intermodal_demolition_series.csv`, `xclusiv_demolition_series.csv`, `advanced_shipping_demolition_series.csv`.
   * Captures indicative $/LDT scrap prices across Bangladesh, India, Pakistan, and Turkey alongside individual beaching fixtures.
3. **Time Charter (TC) & Spot Freight Rates**:
   * Master series: `hellenic_alibra_dry_tc_series.csv`, `hellenic_alibra_tanker_tc_series.csv`, `affinity_tce_series.csv` (dirty & clean routes), `intermodal_tc_rates_series.csv`, `intermodal_tanker_spot_series.csv`.
4. **Newbuilding Contracting and Price Matrices**:
   * Master series: `bancosta_newbuilding_series.csv`, `intermodal_newbuilding_series.csv`, `advanced_shipping_newbuilding_series.csv`, `xclusiv_newbuilding_series.csv`.
5. **AIS Fleet Telemetry & Congestion Queues**:
   * Master series: `drewry_ais_fleet_performance_series.csv`, `drewry_ais_regional_congestion_series.csv`, `drewry_ais_deployment_speed_series.csv`.
6. **Offshore & Energy**:
   * Master series: `seabrokers_osv_spot_rates_series.csv`, `seabrokers_rigs_market_series.csv`, `seabrokers_osv_utilisation_series.csv`.
7. **Econometric Lead-Indicator Models**:
   * Master workbook: [`fearnleys_md_master_econometric_series.xlsx`](file:///c:/Users/Dell/Github/Shipping/data/extracted/series/fearnleys_md_master_econometric_series.xlsx), tracking 26 lead-indicator predictive models (copper vs Supramax TC, coal futures curve vs Kamsarmax RV, steel mill margins vs iron ore consumption).

---

### 2.4 Vector Chart Extraction Engine

Documented in [`docs/CHART_EXTRACTION_ENGINE.md`](file:///c:/Users/Dell/Github/Shipping/docs/CHART_EXTRACTION_ENGINE.md), this engine extracts numerical data from vector line graphics in PDFs:
* Detects plot bounding boxes via PyMuPDF vector drawing paths (`get_drawings()`).
* Calibrates Y-axis scales by aligning tick label numbers to geometric pixel heights.
* Traces polyline vector vertices (filtering for continuous lines with >500 vertices).
* Matches line colors to chart legends using Euclidean RGB color distance.
* Converts pixel coordinates to date-value time series, verifying extracted curves against consensus values across consecutive reports.

---

### 2.5 Dual-Save Mirroring Architecture

To keep the live dashboard operational while populating the canonical corpus, all data scrapers write simultaneously to both targets:

```
[Live Scraper]
      |
      +---> Primary Write  ---> corpus/   (Canonical data lake)
      |
      +---> Secondary Mirror -> reports/  (Legacy store for process_knowledge.py)
```

Dual-save routines are enforced across:
* [`scripts/baltic_scraper.py`](file:///c:/Users/Dell/Github/Shipping/scripts/baltic_scraper.py): Writes to `corpus/08-baltic/` and mirrors to `reports/baltic/`.
* [`scripts/hellenic_scraper.py`](file:///c:/Users/Dell/Github/Shipping/scripts/hellenic_scraper.py): Writes to `corpus/02-hellenic/` and mirrors to `reports/hellenic/`.
* [`scripts/breakwave_insights_scraper.py`](file:///c:/Users/Dell/Github/Shipping/scripts/breakwave_insights_scraper.py): Writes to `corpus/03-breakwave/insights/` and mirrors to `reports/breakwave/`.
* [`scripts/scrapers/fetch_drewry_opinions_incremental.py`](file:///c:/Users/Dell/Github/Shipping/scripts/scrapers/fetch_drewry_opinions_incremental.py): Writes to `corpus/06-drewry/opinions/` and mirrors to `reports/drewry/opinions/`.
* [`scripts/acquire/sync_hellenic_live.py`](file:///c:/Users/Dell/Github/Shipping/scripts/acquire/sync_hellenic_live.py): Writes to `corpus/02-hellenic/` and mirrors to `reports/hellenic/`.

---

### 2.6 Substrate for Future Graph RAG (Scope Boundary)

*Note: The actual construction and implementation of the future Graph RAG system is out of scope for the current phase and will be executed separately by the user. The canonical data foundation established here provides the necessary structural substrate.*

By converting unstructured documents into relational time series, verified cover-to-cover text, and structured table sidecars, the data layer provides the foundational elements required for future knowledge graph modeling:
* **Distinct Entities**: Standardized vessel records (with IMO numbers), commercial charterers, shipowners, brokers, shipyards, recycling facilities, trade routes, and freight indices.
* **Typed Directional Relationships**: Verified links for sales (`REPORTED_SOLD`), charter fixtures (`CHARTERED_BY`), recycling deals (`BEACHED_AT`), newbuilding orders (`ORDERED_AT`), and index routes (`ASSESSED_BY`).
* **Multi-Modal Evidence**: Co-locates structured numeric time series with full qualitative desk analysis, allowing future graph retrieval algorithms to connect numerical market trends with underlying analyst reasoning.

---

## PART 3: LEGACY SYSTEM 1:1 RESTORATION & DUAL-PATH INTEGRITY AUDIT

### 3.1 Migration Defect & Root Cause

During initial directory reorganizations (commits `8c6665067`, `b20829464`, and `0ccaf3ab6`), legacy files were moved (`git mv`) out of [`reports/`](file:///c:/Users/Dell/Github/Shipping/reports/) into [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/) or quarantined into `data/stashed_redundant_sources/` rather than retaining a 1:1 mirror copy.

This created several breaking issues for the earlier knowledge system:
1. **Manifest Path Resolution Failures**: The earlier compiler's cache register ([`knowledge/manifests/documents.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/documents.jsonl)) contained 10,202 document records mapped strictly to `reports/` paths. When files were moved, cache verification failed for 2,702 Hellenic files, 2,703 Breakwave files, 2,036 Baltic files, and 1,096 Poten files.
2. **Chunk Shard Depopulation**: Running compilation scripts while source paths were unresolvable caused 11 chunk shards in [`knowledge/chunks/`](file:///c:/Users/Dell/Github/Shipping/knowledge/chunks/) (across `hellenic_shipbuilding` and `hellenic_vessel_valuations`) to be truncated or emptied.
3. **Legacy Ingestion Stoppage**: Older scripts that expected static source paths in `reports/` could not discover new files or re-chunk historical data.

### 3.2 1:1 Restoration of All Legacy Files in `reports/`

To restore complete backwards compatibility with the earlier knowledge system without altering the canonical `corpus/` data lake, exact 1:1 copies of all legacy sources were restored directly to [`reports/`](file:///c:/Users/Dell/Github/Shipping/reports/).

#### Manifest Verification Audit (`knowledge/manifests/documents.jsonl`)
An automated audit across all 10,202 manifest rows verified 100.0% physical presence on disk:

| Source Category | Legacy Target Directory | Manifest Documents | Files on Disk | Missing Count | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Hellenic Shipping News | [`reports/hellenic/`](file:///c:/Users/Dell/Github/Shipping/reports/hellenic/) | 3,214 | 3,214 | 0 | 100.0% Verified |
| Breakwave Insights | [`reports/breakwave/`](file:///c:/Users/Dell/Github/Shipping/reports/breakwave/) | 3,207 | 3,207 | 0 | 100.0% Verified |
| Baltic Exchange | [`reports/baltic/`](file:///c:/Users/Dell/Github/Shipping/reports/baltic/) | 2,223 | 2,223 | 0 | 100.0% Verified |
| Poten & Partners | [`reports/poten/`](file:///c:/Users/Dell/Github/Shipping/reports/poten/) | 1,096 | 1,096 | 0 | 100.0% Verified |
| Breakwave Dry Bulk | [`reports/drybulk/`](file:///c:/Users/Dell/Github/Shipping/reports/drybulk/) | 211 | 211 | 0 | 100.0% Verified |
| Breakwave Tankers | [`reports/tankers/`](file:///c:/Users/Dell/Github/Shipping/reports/tankers/) | 80 | 80 | 0 | 100.0% Verified |
| Broker Reports | [`reports/broker_reports/`](file:///c:/Users/Dell/Github/Shipping/reports/broker_reports/) | 159 | 159 | 0 | 100.0% Verified |
| Maritime Textbooks | [`reports/`](file:///c:/Users/Dell/Github/Shipping/reports/) | 12 | 12 | 0 | 100.0% Verified |
| **Total Manifest Records** | **Repository Root** | **10,202** | **10,202** | **0** | **100.0% Verified** |

### 3.3 Chunk Shard Repair & Compiler Validation

1. **Shard Repair Execution**:
   * [`scripts/repair_hellenic_shards.py`](file:///c:/Users/Dell/Github/Shipping/scripts/repair_hellenic_shards.py) was executed across the 11 affected shards (`hellenic_shipbuilding` and `hellenic_vessel_valuations` for 2014, 2021-2026).
   * 539 documents were re-ingested and compacted without calling LLMs, restoring shards to 100% of their declared chunk counts (e.g. `hellenic_shipbuilding_2023.jsonl` restored to 506 chunks, `hellenic_vessel_valuations_2023.jsonl` restored to 240 chunks).
   * Shard integrity verification confirmed: **89 yeared shards total, 0 empty shards**.
2. **Ingestion Engine Discovery**:
   * [`scripts/process_knowledge.py`](file:///c:/Users/Dell/Github/Shipping/scripts/process_knowledge.py) was updated to discover files from both the restored `reports/` mirrors and canonical groups, accepting filter aliases (`books`/`book`, `breakwave_insights`/`insights`).
   * Discovery test (`iter_source_files`) yields **11,303 source documents** across all active categories with zero errors:
     - Hellenic: 3,221 files
     - Baltic: 2,228 files
     - Breakwave Insights: 3,210 files
     - Breakwave Drybulk/Tankers: 291 files
     - Broker Reports: 159 files
     - Poten: 2,182 files
     - Books: 12 files

### 3.4 Operational Rules & System Separation

1. **Strict Zero-Interference Boundary**:
   * The earlier knowledge system operates strictly within [`reports/`](file:///c:/Users/Dell/Github/Shipping/reports/), [`knowledge/`](file:///c:/Users/Dell/Github/Shipping/knowledge/), and [`scripts/process_knowledge.py`](file:///c:/Users/Dell/Github/Shipping/scripts/process_knowledge.py).
   * The new canonical data foundation operates strictly within [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/), [`data/extracted/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/), and [`scripts/extract/`](file:///c:/Users/Dell/Github/Shipping/scripts/extract/).
   * Future Graph RAG development will build upon [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/) and [`data/extracted/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/) without disrupting the legacy pipeline.
2. **Automated Dual-Save Synchronization**:
   * All live acquisition scripts write incoming reports simultaneously to `corpus/` (primary) and `reports/` (secondary mirror).
   * As new reports arrive in 2026 and subsequent years (2027+), directory paths and year subfolders are dynamically created in both locations, maintaining continuous parity between the live legacy dashboard and the canonical Graph RAG data lake.

