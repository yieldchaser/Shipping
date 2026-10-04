# RAG System Evolution and Knowledge Architecture

## 1. Executive Summary and Architectural Purpose

This dossier provides a comprehensive architectural comparison and operational reference detailing the evolution of the shipping intelligence retrieval systems within this repository. 

The repository operates on a deliberate dual-system model:
1. **The Legacy Document RAG Pipeline (`knowledge/`)**: An operational document-compilation, token-chunking, BM25-indexed, and signal-derived knowledge base constructed by [`scripts/process_knowledge.py`](file:///c:/Users/Dell/Github/Shipping/scripts/process_knowledge.py). This system directly powers the live dashboard ([`index.html`](file:///c:/Users/Dell/Github/Shipping/index.html)), the automated briefing compiler ([`generate_brief.py`](file:///c:/Users/Dell/Github/Shipping/generate_brief.py)), and client-side topic search. It reads primarily from the legacy [`reports/`](file:///c:/Users/Dell/Github/Shipping/reports/) directory.
2. **The Canonical Corpus and Data Extraction Layer (`corpus/` and `data/extracted/`)**: An immutable, canonical raw repository spanning 10 core namespaces (`01-brokers` through `10-cftc`), accompanied by cover-to-cover Markdown files ([`data/extracted/md/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md/)) and over 60 stacked time-series datasets ([`data/extracted/series/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/series/)). This layer forms the structural, relational, and entity-resolved substrate for the upcoming GraphRAG knowledge graph extraction.

To maintain backward compatibility while ensuring the canonical corpus remains complete and up to date, all live scraping routines enforce a strict **Dual-Save Architecture**. Scraped publications are written into the canonical [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/) directories while simultaneously mirrored to legacy paths in [`reports/`](file:///c:/Users/Dell/Github/Shipping/reports/).

---

## 2. Legacy Document RAG Architecture (`knowledge/`)

### 2.1 Core Orchestration and Processing Flow

The legacy RAG engine is driven by [`scripts/process_knowledge.py`](file:///c:/Users/Dell/Github/Shipping/scripts/process_knowledge.py), a 4,621-line compiler that executes document normalization, text adaptation, semantic token-chunking, AST outline construction, signal extraction, and search index generation.

```
                      +-----------------------------+
                      | Legacy Raw Archive (reports)|
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      | scripts/process_knowledge.py|
                      +-----------------------------+
                                     |
        +----------------------------+----------------------------+
        |                            |                            |
        v                            v                            v
+------------------+         +------------------+         +------------------+
| knowledge/docs/  |         | knowledge/chunks/|         | knowledge/trees/ |
| Frontmatter MD   |         | Sharded JSONL    |         | Outline JSON     |
+------------------+         +------------------+         +------------------+
        |                            |                            |
        +----------------------------+----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |     knowledge/derived/      |
                      |  signals_public.jsonl       |
                      |  section_index.jsonl        |
                      |  scrappage_prices.csv       |
                      +-----------------------------+
                                     |
               +---------------------+---------------------+
               |                                           |
               v                                           v
+-----------------------------+             +-----------------------------+
|    Client-side Dashboard    |             |    Daily Intelligence Brief |
|         index.html          |             |      generate_brief.py      |
+-----------------------------+             +-----------------------------+
```

### 2.2 Input Corpus Sources

The legacy compiler discovers and ingests source documents via `iter_source_files()` using the following legacy mapping:

| Source Identifier | Source Filter | File System Discovery Path | Document Types & Formats |
| :--- | :--- | :--- | :--- |
| `book` | `books` | [`reports/*.pdf`](file:///c:/Users/Dell/Github/Shipping/reports/) | Maritime economics and shipping finance reference textbooks |
| `breakwave` | `breakwave` | [`reports/drybulk/*.pdf`](file:///c:/Users/Dell/Github/Shipping/reports/drybulk/), [`reports/tankers/*.pdf`](file:///c:/Users/Dell/Github/Shipping/reports/tankers/) | Biweekly dry bulk and tanker macroeconomic review PDFs |
| `baltic` | `baltic` | [`reports/baltic/{category}/**/*.html`](file:///c:/Users/Dell/Github/Shipping/reports/baltic/) | Weekly HTML roundups across dry, tanker, gas, container, ningbo |
| `breakwave_insights` | `breakwave_insights` | [`reports/breakwave/**/*.html`](file:///c:/Users/Dell/Github/Shipping/reports/breakwave/) | Daily and weekly market insight essays with embedded charts |
| `hellenic` | `hellenic` | [`reports/hellenic/{category}/**/*.html`](file:///c:/Users/Dell/Github/Shipping/reports/hellenic/) | Weekly reports across dry charter, tanker charter, iron ore, valuations, demo, shipbuilding |
| `broker_reports` | `broker_reports` | [`corpus/01-brokers/_digests/**/*.md`](file:///c:/Users/Dell/Github/Shipping/corpus/01-brokers/_digests/) | Markdown digests from Hellenic Shipping News broker feeds |
| `poten` | `poten` | [`corpus/04-poten/**/*.md`](file:///c:/Users/Dell/Github/Shipping/corpus/04-poten/) (filtered by `pdf_file:`) | Tanker opinion briefings and charterer ranking essays |

### 2.3 Artifact Topology within `knowledge/`

The compilation process materializes several discrete artifact layers within [`knowledge/`](file:///c:/Users/Dell/Github/Shipping/knowledge/):

1. **Normalized Documents ([`knowledge/docs/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/))**:
   - Structured Markdown files partitioned by `{source}/{category}/{year}/{doc_id}.md`.
   - Each file contains strict YAML frontmatter (`doc_id`, `source`, `category`, `date`, `title`, `source_path`, `vessel_classes`, `regions`, `commodities`, `summary`, `keywords`, `market_tone`).
   - Standardized Markdown body sections (`## Overview`, `## Fundamentals`, `## Section Title`).

2. **Tokenized Semantic Chunks ([`knowledge/chunks/`](file:///c:/Users/Dell/Github/Shipping/knowledge/chunks/))**:
   - Chunked using `tiktoken` with the `cl100k_base` BPE tokenizer.
   - Partitioned by year and category into newline-delimited JSON (`{source}_{category}_{year}.jsonl`).
   - Sizing parameters:
     - `breakwave`: 450 tokens max, 60 token overlap.
     - `baltic`: 600 tokens max, 60 token overlap.
     - General / Books: 500 tokens max, 100 token overlap.
   - Chunk metadata attributes:
     - `has_rates`: Boolean flag evaluating rate regexes (`\$[\d,]+\s*/\s*(?:day|mt|tonne)`).
     - `has_forecast`: Boolean flag detecting forward-looking market sentiment.
     - `vessel_classes_matched`, `regions_matched`: Pre-computed taxonomy tags.
     - `snippet`: Leading 200-character plain text context.

3. **Hierarchical Document Trees ([`knowledge/trees/`](file:///c:/Users/Dell/Github/Shipping/knowledge/trees/))**:
   - Stored in JSON format mirroring the [`knowledge/docs/`](file:///c:/Users/Dell/Github/Shipping/knowledge/docs/) structure.
   - Models the table of contents and heading hierarchy (`node_id`, `parent_id`, `level`, `ordinal`, `page_start`, `page_end`, `token_count`).
   - Enables structural navigation, section filtering, and tree-based document search.

4. **Manifests and Caching ([`knowledge/manifests/`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/))**:
   - [`documents.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/documents.jsonl): Master registry of all compiled documents, tracking `source_hash`, `source_hash_version`, `compiler_version`, and processing timestamps.
   - [`sources.json`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/sources.json): Inventory of document counts and directory paths.
   - [`derived_cache.json`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/derived_cache.json): SHA-256 state tracking of document bytes and tree bytes, enabling fast incremental compilation.
   - [`errors.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/errors.jsonl), [`lint_report.json`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/lint_report.json), and [`coverage_report.json`](file:///c:/Users/Dell/Github/Shipping/knowledge/manifests/coverage_report.json).

5. **Derived Signal Artifacts ([`knowledge/derived/`](file:///c:/Users/Dell/Github/Shipping/knowledge/derived/))**:
   - [`signals.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/derived/signals.jsonl): Full internal signal archive (~92 MB) containing detailed numeric observations and LLM extractions.
   - [`signals_public.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/derived/signals_public.jsonl): Lightweight, production-committed signal stream. Drops heavy internal LLM blobs while preserving all scalar fields (`doc_id`, `source`, `category`, `date`, `title`, `source_path`, `vessel_classes`, `regions`, `commodities`, `summary`, `market_tone`). Directly consumed by [`index.html`](file:///c:/Users/Dell/Github/Shipping/index.html) and [`generate_brief.py`](file:///c:/Users/Dell/Github/Shipping/generate_brief.py).
   - [`section_index.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/derived/section_index.jsonl): Flat index of all document sections.
   - [`topic_evidence.jsonl`](file:///c:/Users/Dell/Github/Shipping/knowledge/derived/topic_evidence.jsonl): Clustered text evidence for wiki topics.
   - Specialized CSVs: [`scrappage_prices.csv`](file:///c:/Users/Dell/Github/Shipping/knowledge/derived/scrappage_prices.csv) and [`iron_ore_daily.csv`](file:///c:/Users/Dell/Github/Shipping/knowledge/derived/iron_ore_daily.csv).

6. **Wiki Topic Knowledge Base ([`knowledge/wiki/`](file:///c:/Users/Dell/Github/Shipping/knowledge/wiki/))**:
   - Compiled by [`scripts/build_wiki.py`](file:///c:/Users/Dell/Github/Shipping/scripts/build_wiki.py).
   - Generates encyclopedia markdown pages for vessel classes (Capesize, Panamax, VLCC), trade corridors, and commodities.

7. **Health and Coverage Audits ([`knowledge/reports/`](file:///c:/Users/Dell/Github/Shipping/knowledge/reports/))**:
   - Compiled by [`scripts/build_health_report.py`](file:///c:/Users/Dell/Github/Shipping/scripts/build_health_report.py).
   - Produces [`health_summary.md`](file:///c:/Users/Dell/Github/Shipping/knowledge/reports/health_summary.md), evaluating publishing recency and reporting gaps.

8. **Inverted Search Shards ([`knowledge/chunks/search/`](file:///c:/Users/Dell/Github/Shipping/knowledge/chunks/search/))**:
   - Compiled by [`scripts/search_index_build.py`](file:///c:/Users/Dell/Github/Shipping/scripts/search_index_build.py).
   - Generates pre-tokenized, inverted term-index shards enabling client-side sub-50ms search in the browser without server dependencies.

---

## 3. Current Canonical Data Layer Architecture (`corpus/` and `data/`)

### 3.1 The Canonical Corpus (`corpus/`)

The [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/) directory serves as the immutable data lake designed for end-to-end data extraction and GraphRAG. It organizes raw documents into 10 structured source namespaces:

1. [`corpus/01-brokers/`](file:///c:/Users/Dell/Github/Shipping/corpus/01-brokers/): 16 broker desks (Advanced Shipping, Affinity, Agora, Allied, Anchor, Banchero Costa, Carriers, Clarksons Hellas, Compass, Fearnleys, Fearnleys-MD, Gibson, Intermodal, ISM, Lion, SSY, Star Asia, Xclusiv) containing 2,058 PDFs spanning 2021 through 2026.
2. [`corpus/02-hellenic/`](file:///c:/Users/Dell/Github/Shipping/corpus/02-hellenic/): 18,183 market reports and commodity updates across 6 sub-categories (Demolition, Dry Charter, Iron Ore, Shipbuilding, Tanker Charter, Vessel Valuations).
3. [`corpus/03-breakwave/`](file:///c:/Users/Dell/Github/Shipping/corpus/03-breakwave/): 211 Dry Bulk PDFs, 80 Tanker PDFs, and 3,194 Breakwave Insights HTML articles with 14,700 high-resolution charts.
4. [`corpus/04-poten/`](file:///c:/Users/Dell/Github/Shipping/corpus/04-poten/): 1,087 tanker opinion and dirty fixture PDFs spanning 2004 to 2026.
5. [`corpus/05-seabrokers/`](file:///c:/Users/Dell/Github/Shipping/corpus/05-seabrokers/): 97 monthly OSV and offshore drilling Seascope market reviews spanning 2018 to 2026.
6. [`corpus/06-drewry/`](file:///c:/Users/Dell/Github/Shipping/corpus/06-drewry/): 277 weekly AIS vessel deployment tracking reports and 1,091 Maritime Opinion briefings.
7. [`corpus/07-signal/`](file:///c:/Users/Dell/Github/Shipping/corpus/07-signal/): Live API telemetry, fleet monitoring snapshots, and market reports.
8. [`corpus/08-baltic/`](file:///c:/Users/Dell/Github/Shipping/corpus/08-baltic/): 5,261 market roundups across Dry Bulk, Tankers, Gas, Containers, and Ningbo Container Freight Index (NCFI).
9. [`corpus/09-ppa/`](file:///c:/Users/Dell/Github/Shipping/corpus/09-ppa/): Pilbara Ports Authority export statistics and vessel movement records.
10. [`corpus/10-cftc/`](file:///c:/Users/Dell/Github/Shipping/corpus/10-cftc/): Commitment of Traders shipping and freight derivatives positioning.

### 3.2 Structured Extractions (`data/extracted/md/`)

Unlike the chunked segments in `knowledge/chunks/`, files in [`data/extracted/md/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md/) represent complete, cover-to-cover document transcriptions generated using LlamaParse and PyMuPDF. Every report features:
- Complete YAML frontmatter with standardized metadata (`title`, `issue_date`, `year`, `broker`/`source`, `pages`, `source_file`).
- Full narrative commentary preserving desk analysis without truncation.
- Clean Markdown pipe tables with sidecar JSON files (`<stem>.tables.json`) for structured database querying.
- Embedded links to clipped vector chart screenshots.

### 3.3 Stacked Time-Series Layer (`data/extracted/series/`)

The structured series directory contains over 60 stacked CSV datasets with over 140,000 observations. Every row is strictly stamped with an ISO date (`YYYY-MM-DD`), report week (`Wxx`), and source reference:
- S&P Secondhand Sales Series: Clarksons, Banchero Costa, Intermodal, Xclusiv, Advanced Shipping, Carriers, Lion.
- Demolition and Recycling Series: Star Asia, GMS, Best Oasis, Athenian, Intermodal, Xclusiv, Advanced Shipping.
- Time Charter (TC) Rate Series: Alibra Dry/Tanker TC, Affinity Dirty/Clean TCE, Intermodal Baltic TC.
- Newbuilding Activity Series: Banchero Costa, Intermodal, Advanced Shipping, Xclusiv.
- Fleet Telemetry and Port Congestion: Drewry AIS Fleet Performance, Regional Port Queues, Deployment Speeds.
- Offshore and Energy: Seabrokers OSV Dayrates, Rig Utilization, Subsea Vessel Demand.
- Econometric Modeling: [`fearnleys_md_master_econometric_series.xlsx`](file:///c:/Users/Dell/Github/Shipping/data/extracted/series/fearnleys_md_master_econometric_series.xlsx), tracking 26 lead-indicator predictive models.

---

## 4. Dual-Save Mirroring Architecture and Operational Contracts

To prevent regressions in the legacy RAG system while populating the canonical corpus for GraphRAG, data scrapers implement dual-writing:

```
[Web / API Source]
       |
       +--> Primary Ingestion ---> corpus/ (Canonical Data Lake for GraphRAG)
       |
       +--> Secondary Mirror  ---> reports/ (Legacy Operational Store for process_knowledge.py)
```

### 4.1 Scraper Synchronization Matrix

| Scraper Script | Canonical Primary Path | Legacy Mirror Path | Dual-Save Implementation |
| :--- | :--- | :--- | :--- |
| [`scripts/baltic_scraper.py`](file:///c:/Users/Dell/Github/Shipping/scripts/baltic_scraper.py) | `corpus/08-baltic/{cat}/{year}/` | `reports/baltic/{cat}/{year}/` | `save_as_html_snapshot` & `mirror_asset` write to primary, mirror to `reports/baltic/` |
| [`scripts/hellenic_scraper.py`](file:///c:/Users/Dell/Github/Shipping/scripts/hellenic_scraper.py) | `corpus/02-hellenic/{cat}/{year}/` | `reports/hellenic/{cat}/{year}/` | `extract_and_save` & `mirror_asset` write to primary, mirror to `reports/hellenic/` |
| [`scripts/breakwave_insights_scraper.py`](file:///c:/Users/Dell/Github/Shipping/scripts/breakwave_insights_scraper.py) | `corpus/03-breakwave/insights/{year}/` | `reports/breakwave/{year}/` | Writes HTML and assets to primary, mirrors to `reports/breakwave/` |
| [`scripts/scrapers/fetch_drewry_opinions_incremental.py`](file:///c:/Users/Dell/Github/Shipping/scripts/scrapers/fetch_drewry_opinions_incremental.py) | `corpus/06-drewry/opinions/` | `reports/drewry/opinions/` | Writes Markdown and appends to `_manifest.csv` in both locations |
| [`scripts/scrapers/fetch_drewry_wci.py`](file:///c:/Users/Dell/Github/Shipping/scripts/scrapers/fetch_drewry_wci.py) | `corpus/06-drewry/opinions/{year}/` | `reports/drewry/{year}/` | Dual-writes to `reports/drewry/`, `corpus/06-drewry/opinions/`, and `data/extracted/md/` |
| [`scripts/acquire/sync_hellenic_live.py`](file:///c:/Users/Dell/Github/Shipping/scripts/acquire/sync_hellenic_live.py) | `corpus/02-hellenic/{cat}/pdfs/` | `reports/hellenic/{cat}/pdfs/` | `download_file` saves to primary and mirrors to `reports/hellenic/` |

### 4.2 Failure Isolation and Idempotency Rules

1. **Non-Blocking Secondary Mirrors**: Mirror writes are wrapped in exception guards. If writing to `reports/` encounters an issue, the primary write to `corpus/` remains intact.
2. **Deterministic File Names**: Files are identified by deterministic content hashes or normalized date-slug stamps, preventing duplicate files during re-runs.
3. **Forced Line Feeds**: File operations enforce `newline="\n"` to prevent Git line-ending discrepancies across Windows and POSIX environments.

---

## 5. Architectural Comparison: Legacy RAG vs. GraphRAG Foundation

| System Dimension | Earlier RAG System (`knowledge/`) | Canonical Data Layer for GraphRAG (`corpus/` + `data/`) |
| :--- | :--- | :--- |
| **Primary Goal** | Document chunk retrieval, keyword search, and web dashboard feeds | Entity-relationship modeling, knowledge graph construction, multi-hop reasoning |
| **Input Directory** | [`reports/`](file:///c:/Users/Dell/Github/Shipping/reports/) (Legacy) + [`corpus/01-brokers/_digests/`](file:///c:/Users/Dell/Github/Shipping/corpus/01-brokers/_digests/) | [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/) (Canonical 10-namespace data lake) |
| **Processing Script** | [`scripts/process_knowledge.py`](file:///c:/Users/Dell/Github/Shipping/scripts/process_knowledge.py) | Dedicated publisher extractors in [`scripts/extract/publishers/`](file:///c:/Users/Dell/Github/Shipping/scripts/extract/publishers/) |
| **Data Representation** | BPE token chunks (450-600 tokens), AST JSON trees | Cover-to-cover Markdown, sidecar JSON tables, 60+ stacked time-series CSVs |
| **Entity Resolution** | Heuristic taxonomy tagging (regex keyword matching) | Deterministic IMO numbers, standardized vessel names, charterer/broker entities |
| **Retrieval Mechanism** | BM25 sparse index shards + dense embeddings | Relational SQL/DuckDB queries + vector retrieval + multi-hop graph traversals |
| **Consumer Applications**| [`index.html`](file:///c:/Users/Dell/Github/Shipping/index.html) and [`generate_brief.py`](file:///c:/Users/Dell/Github/Shipping/generate_brief.py) | Econometric lead-indicator models, structured analytics, GraphRAG querying |
| **Storage Schema** | JSONL chunk shards and JSON manifest registers | Parquet, DuckDB, CSV series, publication-grade Markdown |

---

## 6. Blueprint for Upcoming GraphRAG System

With the canonical [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/) complete, verified, and supplemented by structured tables in [`data/extracted/series/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/series/), the repository is prepared for GraphRAG construction.

### 6.1 Proposed Knowledge Graph Ontology

```
                     +------------------------+
                     |         VESSEL         |
                     |  (IMO, Name, DWT, YOB) |
                     +------------------------+
                       /          |         \
         FIXTURED_BY  /           |          \  SOLD_TO / BOUGHT_BY
                     v            |           v
+------------------------+        |     +------------------------+
|       CHARTERER        |        |     |     SHIPPING PARTY     |
| (Vale, Rio Tinto, etc.)|        |     | (Buyer, Seller, Owner) |
+------------------------+        |     +------------------------+
                     \            |           /
           OPERATES_ON\           | BUILT_BY /
                       v          v         v
                     +------------------------+
                     |     SHIPYARD / ROUTE   |
                     | (Newbuilding / Voyage) |
                     +------------------------+
                                  |
                                  v ASSESSED_AT
                     +------------------------+
                     |    FREIGHT / PRICE     |
                     |  (Index, TCE, $/LDT)   |
                     +------------------------+
```

### 6.2 Target Entity Types and Schema Definitions

1. `Vessel`:
   - Properties: `imo` (7-digit primary key), `name`, `vessel_type`, `dwt`, `built_year`, `shipyard`, `flag`.
   - Data Sources: Banchero Costa S&P tables, Clarksons sales tables, Drewry AIS fleet logs.
2. `Charterer` / `CommercialOperator`:
   - Properties: `company_name`, `country_of_origin`, `operating_sector`.
   - Data Sources: Poten Top Charterers series, Alibra TC fixtures, Signal telemetry.
3. `Route` / `TradeCorridor`:
   - Properties: `route_code` (e.g., C5 Tubarao-Qingdao, TD3C MEG-China), `origin_port`, `destination_port`, `commodity`.
   - Data Sources: Baltic Exchange indexes, Intermodal spot rates, Drewry WCI container lanes.
4. `MarketAssessment` / `Fixture`:
   - Properties: `timestamp`, `rate_usd`, `worldscale`, `tenor`, `volume_mt`.
   - Data Sources: Baltic assessments, Affinity TCE matrices, Hellenic charter fixtures.
5. `AssetTransaction` (S&P / Demolition / Newbuilding):
   - Properties: `transaction_id`, `price_usd_m`, `price_usd_per_ldt`, `delivery_date`, `scrap_yard`.
   - Data Sources: Advanced Shipping, Xclusiv, Star Asia demolition deals, Intermodal S&P.

### 6.3 Target Relationship Types (Edges)

- `(:Vessel)-[:REPORTED_SOLD {date, price_usd_m, buyers, sellers}]->(:Company)`
- `(:Vessel)-[:CHARTERED_BY {rate_usd_day, tenor, route}]->(:Charterer)`
- `(:Vessel)-[:BEACHED_AT {price_usd_per_ldt, delivery_location}]->(:RecyclingYard)`
- `(:Route)-[:ASSESSED_BY {date, rate_value, unit}]->(:FreightIndex)`
- `(:MacroIndicator)-[:LEADS_CORRELATION {lag_months, r_squared}]->(:FreightRate)`

### 6.4 Hybrid Retrieval Strategy for GraphRAG

The planned retrieval architecture combines three search modalities:
1. **Vector Dense Search**: Vector embeddings for conceptual similarity across analyst commentary and market prose.
2. **BM25 Sparse Retrieval**: Exact token matching for specific vessel names, IMO numbers, and route codes.
3. **Multi-Hop Graph Traversal**: Querying entity graphs across linked relationships (for example: identifying all Capesize bulkers built in Japanese yards between 2010 and 2015 sold to Greek buyers during periods where Baltic C5 rates exceeded $25/mt).

---

## 7. Operational Guidelines for Maintenance

1. **Preserve Dual-Save Scrapers**: Any modification to scrapers in [`scripts/`](file:///c:/Users/Dell/Github/Shipping/scripts/) must maintain writes to both [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/) and [`reports/`](file:///c:/Users/Dell/Github/Shipping/reports/).
2. **Immutable Raw Corpus**: Never edit or reformat original PDFs or HTML files residing in [`corpus/`](file:///c:/Users/Dell/Github/Shipping/corpus/). All transformations belong in [`data/extracted/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/).
3. **Compiler Health**: Prior to committing major pipeline adjustments, run [`scripts/validate_knowledge.py`](file:///c:/Users/Dell/Github/Shipping/scripts/validate_knowledge.py) to confirm zero broken section references or empty token chunk stubs.
4. **Git Hygiene**: Maintain zero emojis across all code files, commit messages, and documentation artifacts.
