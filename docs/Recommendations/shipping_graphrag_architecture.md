# Maritime & Shipping GraphRAG Architecture Specification

**Target Corpus:** `yieldchaser/Shipping` (19,329 Broker MDs · 6,142 Table Sidecars · 1,364 SEC Filings · 12 Maritime Books · 166 Numeric Series CSVs / 727,192 Rows · ~105–110M Total Tokens)  
**Target Environment:** Windows 11 (`Intel i3-1215U`, `8 GB RAM`, `40 GB Free Disk`, No Discrete GPU) + GitHub Actions Free Runners + `$145` OpenAI-Compatible Router Budget  
**Architecture Pattern:** Bi-Temporal Relational-Graph-Vector Lakehouse (`DuckDB` + `LanceDB` + `FastEmbed ONNX` + `Splink` + `HippoRAG 2` Personalized PageRank)

## Executive Recommendation

An off-the-shelf "LLM-extract-everything" GraphRAG pipeline is the wrong architecture for this corpus. Feeding 105–110 million tokens of dense shipping tables and SEC filings into an open-schema LLM graph extractor will burn the API budget turning structured table cells into noisy, lossy triples, exceed 8 GB of RAM, and degrade exact numeric retrieval.

Empirical benchmarks from 2025–2026 ([GraphRAG-Bench, ICLR 2026](https://volcanicminds.com/en/insights/graphrag-vs-hybrid-rag); [Beri, 2026](https://www.beri.net/article/graphrag-vs-vector-rag-indexing-query-cost-lightrag-lazygraphrag-2026); [Mnemoverse, 2026](https://mnemoverse.com/docs/library/graphrag-tax)) establish two clear boundaries:

1. **Graphs lose to Hybrid RAG + SQL on point facts and numbers:** On single-fact retrieval, reranked hybrid RAG scores `60.92` vs. `49.29` for [Microsoft GraphRAG](https://github.com/microsoft/graphrag), while counts, rate series, and table aggregations fail in text/graph community summarization ([Volcanic Minds, Nov 2026](https://volcanicminds.com/en/insights/graphrag-vs-hybrid-rag)).
2. **Graphs win decisively on multi-hop synthesis (+27.23 points):** When a query connects a vessel, owner, or macro shock across SEC filings, broker fixture tables, and market commentary, graph traversal and Personalized PageRank ([HippoRAG 2, ICML 2025](https://arxiv.org/abs/2502.14802)) beat vector-only and hybrid RAG by a wide margin while consuming 12× fewer indexing tokens than Microsoft GraphRAG.

To achieve **100% numeric fidelity**, **multi-hop entity synthesis**, and **causal narrative alignment** within **$145**, **8 GB RAM**, and **GitHub Actions**, build a **Bi-Temporal Relational-Graph-Vector Lakehouse** backed by **DuckDB + LanceDB** (`shipping_kg.duckdb` + `chunks.lance`).

## 1. Recommended Architecture & Rejected Alternatives

### Core Principle: Separate Deterministic Structure from Narrative Extraction

Roughly 55–60% of the 110M tokens in this repository reside inside Markdown tables, `*.tables.json` sidecars, SEC financial grids, and `data/extracted/series/`. **An LLM must never touch a table or numeric time series during indexing.**

* **Deterministic Spine (Zero LLM Tokens):** `data/extracted/series/` (166 CSVs, 727,192 rows), `*.tables.json` (6,142 sidecars), YAML frontmatter (19,329 broker MDs + 1,364 SEC MDs), and SEC structured tables are parsed deterministically via Python into normalized DuckDB relational tables and typed graph edges (`FIXTURE_EVENT`, `SNP_DEAL`, `FLEET_LIST_ENTRY`, `SERIES_OBSERVATION`).
* **LLM-Extracted Causal & Event Layer (~42M Unique Prose Tokens Only):** Markdown tables and repeated SEC boilerplate are stripped before sending prose to the LLM. The LLM reads only narrative commentary (broker sector commentary, SEC Item 7 MD&A / Item 3D Risk Factors / EX-99 earnings releases, and the 12 maritime books) to extract a strict, closed-ontology set of **Causal Claims, Market Events, Corporate Actions, and Structural Rules**, anchored to exact `doc_id`, `chunk_id`, `issue_date`, and verbatim `quote_span`.

### Modality-by-Modality Ingestion, Storage, and Retrieval

| Modality | Ingestion Path | Storage Representation | Query & Retrieval Path |
| :--- | :--- | :--- | :--- |
| **Numeric Series** (`166 CSVs`, `727,192 rows`) | Direct [DuckDB](https://duckdb.org/) ingestion (`read_csv_auto`) with canonical registry mapping (`route_id`, `index_id`, `vessel_class_id`, `unit`). | `series_observations(series_id, obs_date, value, unit, source_file, source_sha256)` + precomputed weekly/monthly rollups (`delta_pct`, `z_score_52w`). | Parameterized SQL time-window & co-movement templates (never vector search). |
| **Report Tables** (`6,142 *.tables.json` & SEC tables) | Deterministic Python normalizer + **1-sentence programmatic row/table templates** (e.g., *"S&P Deal [2024-05-12, Fearnleys]: VLCC 'DHT Osprey' (300k DWT, blt 2015 Daewoo) sold by DHT (CIK 0001478497) to undisclosed Greek buyer for $85.0M"*). | 1. Typed SQL rows (`fixtures`, `snp_deals`, `newbuildings`, `demolitions`, `sec_fleet_rows`) + Graph edges.<br>2. Synthetic text summary embedded into [LanceDB](https://www.lancedb.com/) with exact cell provenance (`table_id`, `row_idx`). | SQL for filtering/aggregation; Graph traversal for vessel/owner history; Hybrid BM25+Vector for narrative discovery. |
| **Broker & SEC Prose** (`~42M tokens` across `20,693 MDs`) | Section-aware Markdown splitter (`400–600 tokens`, `64-token` overlap) preserving header breadcrumbs + YAML metadata. Extracted via **DeepSeek V4 Flash** into typed JSON nodes/edges. | 1. Chunks in LanceDB with **Contextual Retrieval prefixes** ([Anthropic pattern](https://volcanicminds.com/en/insights/graphrag-vs-hybrid-rag): `[Publisher \| Date \| Ticker \| Section]` prepended at zero LLM cost from YAML/headers).<br>2. Bi-temporal Graph triples (`edges` table in DuckDB). | Hybrid Search (BM25 + Dense ONNX + [FlashRank](https://github.com/zeeshan56656/flashrank-js) reranker) + Personalized PageRank (PPR) over the entity-passage bipartite graph. |
| **Maritime Books** (`12 MDs`, `10 MB`) | Hierarchical chapter/section chunking + extraction via **DeepSeek V4.1 Flash** for theoretical mechanisms (e.g., Stopford's shipping cycle stages, orderbook-to-fleet elasticity, scrapping triggers). | `concept_nodes` and `structural_rules` linked to canonical `MetricType`, `VesselClass`, and `MarketRegime` nodes. | Triggered on structural/long-horizon queries or joined automatically when explaining macro co-movements. |

### Bi-Temporal Knowledge Graph Schema (DDL Design)

Every statement and event in shipping has two distinct clocks: **when the document was published** (`t_pub` = `issue_date` or SEC `filing_date`) and **what historical or future window the statement applies to** (`t_valid_start`, `t_valid_end`, e.g., *"Q3 2025"* or *"Week 40 2025"*), following temporal knowledge graph best practices ([Graphiti](https://github.com/getzep/graphiti)).

* **10 Core Node Types (`nodes` table):**
  * `Vessel` (immutable `vessel_uid`, `imo`, `build_year`, `dwt`, `cbm`, `teu`, `yard_id`, `vessel_class_id`)
  * `Company` (`company_uid`, `canonical_name`, `role`: Owner / Charterer / Yard / Miner / Broker, `country`)
  * `SecIssuer` (`cik`, `ticker`, `company_uid`, `exchange`, `sector`) — covering all 25 issuers (`ASC`, `BHP`, `CTRM`, `DHT`, `DSX`, `ECO`, `EDRY`, `FRO`, `GLBS`, `GNK`, `GOGL`, `INSW`, `LPG`, `NAT`, `NVGS`, `RIO`, `SB`, `SBLK`, `SFL`, `SHIP`, `STNG`, `TNK`, `TNP`, `TRMD`, `VALE`)
  * `Route` (`route_id`, e.g., `TD3C`, `TD20`, `C3`, `C5`, `P1A_82`, `origin_port_id`, `dest_port_id`, `vessel_class_id`, `cargo_id`)
  * `IndexOrMetric` (`metric_id`, e.g., `BDI`, `BDTI`, `BCTI`, `CCFI`, `SCFI`, `VLCC_5YR_PRICE`, `VLSFO_SINGAPORE`)
  * `PortOrChokepoint` (`locode`, `name`, `region`, `is_chokepoint` — e.g., Suez Canal, Panama Canal, Strait of Hormuz, Bab el-Mandeb)
  * `Commodity` (`cargo_id`, e.g., `IRON_ORE`, `CRUDE_OIL`, `COAL`, `GRAIN`, `BAUXITE`, `LNG`, `LPG`, `CPP`)
  * `VesselClass` (`class_id`, e.g., `VLCC`, `SUEZMAX`, `AFRAMAX`, `LR2`, `MR`, `CAPESIZE`, `NEWCASTLEMAX`, `KAMSARMAX`, `PANAMAX`, `SUPRAMAX`, `VLGC`)
  * `MarketEvent` (`event_uid`, `event_type`: Geopolitical / Regulatory / Weather / Congestion / Macro, `canonical_name`, `start_date`, `end_date`)
  * `Concept` (`concept_uid`, `name`, `book_source`, `definition` — from Stopford, Kavussanos & Visvikis, Paine, Harlaftis, Duru)

* **8 Core Edge Types (`edges` table with full provenance):**
  * **Deterministic from tables & filings:**
    * `OWNS_VESSEL` (`Company/SecIssuer` $\rightarrow$ `Vessel`, `t_valid_start`, `t_valid_end`, `doc_id`, `table_id`)
    * `CHARTERED` (`Vessel` $\rightarrow$ `Company`, attributes: `route_id`, `rate_value`, `rate_unit`, `laycan_start`, `laycan_end`, `charter_type`, `doc_id`)
    * `SOLD_TO` (`Vessel` $\rightarrow$ `Company`, attributes: `seller_uid`, `price_musd`, `dd_due`, `scrubber_fitted`, `deal_date`, `doc_id`)
    * `OPERATES_IN_SECTOR` (`Company/SecIssuer` $\rightarrow$ `VesselClass` / `Route`, attributes: `fleet_count`, `dwt_share`, `doc_id`)
  * **LLM-extracted from narrative prose:**
    * `CAUSED_OR_DROVE` (`MarketEvent` / `Metric` $\rightarrow$ `Metric` / `Route` / `VesselClass`, attributes: `polarity` (`+1`/`-1`), `mechanism_summary`, `confidence`, `t_pub`, `t_valid_start`, `t_valid_end`, `doc_id`, `chunk_id`, `quote_span`)
    * `FORECASTS` (`Publisher` / `SecIssuer` $\rightarrow$ `Metric` / `VesselClass`, attributes: `horizon_start`, `horizon_end`, `direction`, `target_value`, `doc_id`, `chunk_id`, `quote_span`)
    * `EXPOSED_TO` (`SecIssuer` / `Company` $\rightarrow$ `MarketEvent` / `Route`, attributes: `exposure_type`, `mitigation`, `doc_id`, `chunk_id`, `quote_span`)
    * `THEORETICAL_MECHANISM` (`Concept` $\rightarrow$ `Metric` / `VesselClass`, attributes: `elasticity_or_rule`, `cycle_phase`, `book_doc_id`, `chunk_id`, `quote_span`)

### Entity Resolution Across Sources and Time (The 4-Stage Cascade)

Shipping entities recur under shifting aliases (*"Frontline"*, *"Frontline Ltd."*, *"Frontline plc"*, *"FRO"*; vessels renamed upon S&P sale; *"Undisclosed Greek interests"* later revealed in a 20-F fleet table). Pairwise LLM comparisons across 20,000+ documents are prohibitively expensive and inconsistent. Instead, use a **4-stage deterministic + probabilistic cascade**:

1. **Stage 1 — Authoritative Seed Dictionaries (Day 0, Zero LLM Cost):**
   * **Issuers & Tickers:** Seed the 25 SEC issuers (`ASC` through `VALE`), their CIKs, historical legal names, and vessel-owning subsidiaries parsed from SEC Exhibit 21 and 10-K/20-F fleet tables.
   * **Routes, Indices & Vessel Classes:** Seed a canonical YAML dictionary of all Baltic Exchange route codes (`TD3C`, `TD20`, `C3`, `C5`, `P1A_82`, `BSI`, etc.), broker shorthand (*"MEG-China 270k"* $\rightarrow$ `TD3C`, *"Tubarao-Qingdao"* $\rightarrow$ `C3`), and DWT/CBM brackets.
   * **Ports & Chokepoints:** Seed from the public [UN/LOCODE Code List](https://unece.org/trade/cefact/unlocode-code-list-country-and-territory) ([DataHub CSV](https://datahub.io/core/un-locode)) plus maritime basin aliases (*"USG"*, *"Continent"*, *"UKC"*, *"ECSA"*, *"MEG/AG"*, *"WAF"*).
   * **Vessels:** Seed from SEC filing fleet tables (which explicitly list Vessel Name, Built Year, DWT, Yard, and often IMO) plus the public [Equasis](https://www.equasis.org/) ship registry export (`IMO`, `Current Name`, `Former Names`, `Build Year`, `DWT`, `Shipyard`).
2. **Stage 2 — Composite-Key Vessel Splines ([Splink](https://moj-analytical-services.github.io/splink/index.html) on DuckDB):**
   * Broker fixture and S&P tables rarely print IMO numbers; they print `(Name, Built Year, DWT, Yard)`—e.g., `("M/V Star", 2016, 81600, "Tsuneishi")`.
   * Run [Splink](https://github.com/moj-analytical-services/splink) (Fellegi-Sunter probabilistic record linkage executing directly inside DuckDB at ~1M records/minute on CPU).
   * **Blocking Rules:** Block on `ABS(build_year_a - build_year_b) <= 1` AND `ABS(dwt_a - dwt_b) <= 2500`. Score pairs using Jaro-Winkler similarity on prefix-stripped names (stripping `M/V`, `MT`, `MV`, `SS`, `M.V.`) + shipyard token overlap.
   * **Temporal Vessel Identity Spline:** When an S&P table or SEC filing records a vessel sale or rename at date $t_{\text{sale}}$, the `Vessel` node retains one immutable `vessel_uid` anchored to its hull signature `(imo OR [build_year, dwt_norm, yard_id])`, while `vessel_aliases(vessel_uid, vessel_name, owner_uid, valid_from, valid_to, source_doc_id)` records its temporal name and ownership intervals. Queries about 2021 resolve the 2021 name; longitudinal queries stitch the vessel's entire history across renamings.
3. **Stage 3 — Retroactive Resolution of "Undisclosed" Counterparties:**
   * When a broker S&P table logs `buyer = "Undisclosed"` for `("Star", 2016, 81.6k DWT, $28.5M)` in May 2024, store a typed placeholder `unresolved_buyer:<deal_id>`.
   * When `SBLK` or `GOGL` files a subsequent `6-K` or `20-F` listing a newly acquired 2016-built 81.6k DWT Kamsarmax delivered in Q2/Q3 2024, a deterministic DuckDB join on `(vessel_uid, acquisition_window)` links `unresolved_buyer:<deal_id>` $\rightarrow$ `SBLK` via an `INFERRED_IDENTITY` edge (preserving both the broker's original `"undisclosed"` string and the SEC filing's confirmation).
4. **Stage 4 — LLM Tie-Breaker for Ambiguous Cluster Pairs Only:**
   * Only candidate entity pairs with Splink match probability between `0.45` and `0.88` (typically `<3,000` pairs across the entire corpus) are batched (`50` pairs per prompt) to **DeepSeek V4 Flash** for canonical merge/split adjudication.

### Alternatives Rejected (and Why)

| Alternative | Reason for Rejection Under Your Constraints |
| :--- | :--- |
| **[Microsoft GraphRAG](https://github.com/microsoft/graphrag) (Standard Pipeline)** | 1. **Maintenance-only status:** As of v3.3.0 (Oct/Nov 2026), the repository is in maintenance mode with no new features ([Volcanic Minds, 2026](https://volcanicminds.com/en/insights/graphrag-vs-hybrid-rag)).<br>2. **Token Bloat:** Consumes ~10×–12× more tokens than HippoRAG 2 due to multi-pass gleaning and Leiden community summarization.<br>3. **Lossy on Numbers:** Community summaries overwrite exact dates, TCE figures, and provenance with smoothed prose.<br>4. **Update Churn:** Incremental updates invalidate community hierarchies and require summary regeneration. |
| **[LazyGraphRAG](https://www.articsledge.com/post/lazygraphrag-retrieval-augmented-generation)** | Cuts indexing cost to 0.1% of full GraphRAG by deferring LLM summarization to query time, **but** it is not available in the open-source `microsoft/graphrag` package (restricted to Azure Local / Microsoft Discovery preview) and shifts heavy token consumption and latency onto every user query. |
| **[LightRAG](https://github.com/hkuds/lightrag)** | Supports incremental inserts, but extracts loosely typed entity-relation descriptions without a bi-temporal schema or deterministic table separation. Independent evaluations ([Gutiérrez et al., 2025](https://arxiv.org/abs/2502.14802); [Zeng et al., 2025](https://volcanicminds.com/en/insights/graphrag-vs-hybrid-rag)) show its factual precision drops below hybrid RAG once length bias is removed. |
| **Neo4j / Memgraph / Dockerized Graph Servers** | Running a JVM (Neo4j) or Docker/WSL2 daemon alongside Python and local embeddings on a Windows 11 laptop with **8 GB RAM** causes severe memory pressure and swap thrashing. |
| **[KùzuDB](https://www.puppygraph.com/blog/what-is-kuzudb)** | Was the leading embedded Cypher graph database for Python, but **Kùzu Inc. was acquired by Apple in October 2025 and the open-source repository was archived** ([PuppyGraph, 2026](https://www.puppygraph.com/blog/what-is-kuzudb); [ArcadeDB, 2026](https://arcadedb.com/blog/from-kuzudb-to-arcadedb-migration-guide/)). Building a long-term system on an archived engine creates unnecessary maintenance risk. |
| **DuckDB `vss` (In-Memory HNSW)** | DuckDB's experimental [`vss` extension](https://duckdb.org/docs/2.0/core_extensions/vss) holds HNSW indexes in memory and does not respect DuckDB's `memory_limit` setting ([Dev.to, Aug 2026](https://dev.to/muhammadikhwanfathulloh/vector-similarity-search-with-duckdb-a-practical-guide-to-the-vss-extension-p5c)). Disk-backed [LanceDB](https://www.lancedb.com/blog/make-your-sql-workflows-multimodal-with-lancedb-x-duckdb) keeps vector search RAM under 300 MB via memory-mapped columnar storage. |

## 2. Tools, Libraries, and Storage Fit for Hardware & CI Constraints

Every component runs **in-process in native Windows Python (3.11 / 3.12)**—requiring zero Docker containers, zero WSL2 virtualization overhead, and zero background database services.

| Component Layer | Selected Tool / Library | Why It Fits (`i3-1215U`, `8 GB RAM`, `40 GB Disk`, `GitHub Actions`) | Disk Usage | Peak RAM |
| :--- | :--- | :--- | :--- | :--- |
| **Relational, Time-Series & Graph Store** | **[DuckDB](https://duckdb.org/)** (`shipping_kg.duckdb`) | Single-file columnar OLAP engine (`SET memory_limit = '2.5GB'`, `SET threads = 4`). Stores all 727k series rows, normalized tables, document registry, nodes, and bi-temporal edges. Executes 1-to-3 hop graph traversals via SQL / recursive CTEs in `<15 ms`. | `~1.8 GB` | `1.5–2.5 GB` (hard-capped) |
| **Associative Multi-Hop Graph Engine** | **`scipy.sparse` (`csr_matrix`) + Personalized PageRank ([HippoRAG 2](https://arxiv.org/abs/2502.14802))** | DuckDB exports the `edges` + `chunk_entity_links` bipartite graph (~500k nodes, ~3M edges) into a compressed sparse row matrix (`<60 MB` in RAM). Runs 20 power iterations of Personalized PageRank in `<12 ms` on an i3 CPU to rank multi-hop connected passages. | `~45 MB` (`.npz` cache) | `<80 MB` |
| **Disk-Backed Hybrid Vector + BM25 Store** | **[LanceDB](https://www.lancedb.com/)** (`data/index/lancedb/`) | Embedded Apache Lance disk format. Provides native **Dense Vector + Tantivy Full-Text Search (BM25) + SQL metadata pre-filtering** (`issue_date`, `publisher`, `ticker`, `sector`) directly from disk via `mmap` ([LanceDB × DuckDB](https://www.lancedb.com/blog/make-your-sql-workflows-multimodal-with-lancedb-x-duckdb)). | `~2.2 GB` (`300k` chunks, `384d` fp16/int8) | `<300 MB` |
| **Local CPU Embeddings** | **[FastEmbed](https://github.com/qdrant/fastembed)** (`BAAI/bge-small-en-v1.5` or `Snowflake/snowflake-arctic-embed-s`, ONNX INT8) | Runs via C++ ONNX Runtime without PyTorch ([FastEmbed Docs](https://qdrant.tech/documentation/fastembed/)). `384` dimensions, `512` token context, ~90 MB weights. Paired with Contextual prefixes + Tantivy BM25 (which catches exact tickers, IMO numbers, and Baltic codes like `TD3C`), 384d ONNX runs 4× faster on CPU than 1024d models. | `~90 MB` model | `~350 MB` |
| **Local CPU Reranker** | **[FlashRank](https://hysenlabs.com/projects/prithivirajdamodaran-flashrank)** (`ms-marco-MiniLM-L-12-v2` ONNX INT8) | Cross-encodes and re-orders the top 30 RRF-fused chunks in `~60–90 ms` on an i3 CPU with zero API cost and `<150 MB` RAM. | `~35 MB` model | `<150 MB` |
| **Probabilistic Entity Resolution** | **[Splink](https://github.com/moj-analytical-services/splink)** + `rapidfuzz` | Executes Fellegi-Sunter record linkage directly inside DuckDB SQL. Deduplicates 100k+ vessel and company mentions in under 60 seconds on a laptop. | Negligible | Shared with DuckDB |
| **Async LLM Extractor & Checkpointer** | **`httpx` (Asyncio) + `Pydantic` + SQLite WAL Queue** | Asynchronous worker pool hitting the OpenAI-compatible router with exponential backoff, schema validation, and per-chunk SHA256 checkpointing in `extraction_state.sqlite`. | `~400 MB` | `<150 MB` |

* **Total Disk Footprint:** **`~4.6 GB`** (leaving `>35 GB` free on the `40 GB` drive).
* **Total Peak RAM Footprint:** **`~2.2–2.8 GB`** (leaving `>5 GB` available for Windows 11).

## 3. Cost and Time Estimate (One-Time Build & Weekly Updates)

### Corpus Token Accounting (`105–110M Total Tokens`)

Sending raw Markdown tables or repetitive SEC boilerplate to an LLM wastes money and degrades graph quality. Separating the corpus by structural type reduces the LLM token volume by **60%**:

1. **Report Tables & Numeric Series (~48M tokens of Markdown tables + 6,142 `*.tables.json` + 166 CSVs):** Parsed **100% deterministically** by Python scripts. **LLM Tokens: 0.**
2. **Boilerplate & Repeated SEC Carry-Over Text (~16M tokens):** In 1,364 SEC filings (`247 MB`), XBRL tables, legal boilerplate, and signature pages account for ~60% of the byte volume. Across sequential `10-Q`/`6-K` filings and weekly broker reports, ~15% of narrative paragraphs are verbatim carry-overs from prior filings—deduplicated via `sha256(normalized_paragraph)` prior to LLM extraction. **LLM Tokens: 0.**
3. **Unique Narrative Prose Requiring LLM Graph Extraction (~42M Input Tokens):**
   * `19,329` Broker reports narrative commentary (`~25M` tokens)
   * `1,364` SEC filings narrative sections—MD&A, Fleet Commentary, Market Outlook, Risk Factors, EX-99 press releases (`~14M` tokens)
   * `12` Maritime economics/finance books (`~3M` tokens)

### Compact Structured Output Schema

Rather than emitting verbose JSON with repeated field names and re-typed quotes, each chunk is sentence-indexed (`[S1] ... [S2] ...`) before sending to the LLM. The LLM outputs compact JSON arrays (`{"e": [...], "r": [...], "c": [...]}`) referencing integer sentence spans (`"span": [2, 3]`), allowing Python to slice the exact verbatim quote deterministically. This keeps output volume to **~18% of input tokens** (`~7.6M` output tokens across `42M` input tokens).

### One-Time Build Cost & Wall-Clock Breakdown

| Build Phase | Router Model Used | Price (In / Out per 1M) | Input Tokens | Output Tokens | API Cost (USD) | Wall-Clock Time |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **0. Pilot & Prompt Calibration** (`300` sample docs + eval generation) | DeepSeek V4 Flash + DeepSeek V4.1 Flash | `$0.13/$0.26` & `$0.30/$1.20` | `1.5M` | `0.4M` | **$0.65** | `~25 mins` |
| **1. Deterministic Spine Ingestion** (`166` CSVs, `6,142` `*.tables.json`, YAML metadata, SEC fleet tables) | *None (Python + DuckDB)* | `$0.00` | `0` | `0` | **$0.00** | `~12 mins` (i3 CPU) |
| **2. Bulk Prose Graph & Causal Extraction** (`19,329` Broker MDs + `1,364` SEC MDs narrative) | **DeepSeek V4 Flash** | `$0.13 / $0.26` | `39.0M` | `7.0M` | **$6.89** | `~2.5–3.5 hrs` (at 40 concurrent requests) |
| **3. High-Precision Extraction on Books & Core SEC 10-K/20-F MD&A** (`12` Books + `25` latest annual filings) | **DeepSeek V4.1 Flash** | `$0.30 / $1.20` | `5.0M` | `1.2M` | **$2.94** | `~35 mins` |
| **4. Retry / Self-Healing Pass** (`~5%` malformed JSON or dense chunks) | **GLM 5.3 Flash** | `$0.15 / $0.50` | `2.5M` | `0.6M` | **$0.68** | `~15 mins` |
| **5. Entity Resolution Adjudication** (`~3,000` ambiguous Splink pairs + Sector/Event Taxonomy) | **DeepSeek V4.1 Flash** | `$0.30 / $1.20` | `2.0M` | `0.5M` | **$1.20** | `~15 mins` |
| **6. Local ONNX Embedding** (`~300k` chunks: prose + synthetic table summaries via FastEmbed) | *None (Local i3-1215U CPU)* | `$0.00` | `0` | `0` | **$0.00** | `~3.5–4.5 hrs` (resumable batches of 1,000) |
| **TOTAL ONE-TIME BUILD (RECOMMENDED)** | | | **`50.0M`** | **`9.7M`** | **`$12.36`** | **`~7.5–9 hours total`** |
| *Optional Upgrade: Run 100% of Prose on DeepSeek V4.1 Flash* | *DeepSeek V4.1 Flash* | *`$0.30 / $1.20`* | *`50.0M`* | *`9.7M`* | ***`$26.64`*** | *`~8.0–9.5 hours total`* |

### Why Preserving ~$120–$132 of the $145 Router Credit Is Essential

Because the LLM router has closed new sign-ups, the **$145 balance is a non-renewable endowment** that must fund the initial build, years of automated weekly ingestion, and multi-hop query synthesis:

* Spending **`$12.36`** (or **`$26.64`** if using `DeepSeek V4.1 Flash` everywhere) leaves **`~$118–$132`** on the router.
* That remaining balance funds **5+ years of automated weekly updates AND ~15,000+ deep multi-hop analytical queries** using `DeepSeek V4.1 Flash` (`$0.30/$1.20`) or `DeepSeek V4 Pro` (`$1.32/$3.96`).

### Weekly Automated Update Cost & Time

* **Weekly Incremental Volume:** ~40–60 new broker MDs (`~120k` prose tokens), ~5–15 SEC filings (`~80k` prose tokens), ~15–25 `*.tables.json` sidecars, and ~500–2,000 new CSV series rows.
* **Weekly API Cost:** `200k` input tokens + `40k` output tokens on `DeepSeek V4 Flash` = **`$0.036 / week`** (**`~$1.90 / year`**). On `DeepSeek V4.1 Flash`, it costs **`$0.108 / week`** (**`~$5.60 / year`**).
* **Weekly Execution Time:** **`~90–150 seconds`** total (CSV upsert: `2s`; table JSON parse: `3s`; async LLM extraction: `45s`; FastEmbed ONNX on ~400 new chunks: `35s`; CSR matrix rebuild: `5s`). Runs comfortably inside a **GitHub Actions free runner** (`2 vCPU`, `7 GB RAM`).

## 4. Incremental Ingestion & Surgical Error Correction

### Automated Incremental Flow (Zero Rebuild, Zero Human-in-the-Loop)

Every source artifact is tracked by `doc_id` and `source_sha256` (from YAML frontmatter) inside DuckDB's `corpus_manifest` table:

1. **Manifest Diff (`1 sec`):** `python -m shipping_graph sync` scans `data/extracted/md/`, `*.tables.json`, `corpus/10-companies/`, and `data/extracted/series/*.csv` against `corpus_manifest(file_path, sha256, parser_version, extractor_version)` to isolate newly added or modified files.
2. **Series Delta Upsert (`2 sec`):** Executes `INSERT OR REPLACE INTO series_observations` keyed on `(series_id, obs_date, source_file)` and refreshes rolling 4w/12w/52w percentage changes and z-scores for updated series.
3. **Deterministic Table & YAML Ingestion (`5 sec`):** Parses new `*.tables.json` and SEC fleet/financial tables into `fixtures`, `snp_deals`, and `sec_fleet_rows`, generating deterministic 1-sentence text summaries for each row.
4. **Prose Chunking & Resumable LLM Extraction (`45 sec`):** Strips tables, splits narrative sections into chunks (`chunk_id = sha256(doc_id + span_offset)`), skips any `chunk_id` already present in `extraction_cache`, and extracts new nodes/edges via `DeepSeek V4 Flash`.
5. **Incremental Entity Linking (`10 sec`):** Matches new entity strings against `canonical_entities` and `entity_aliases` (exact match + Splink blocking against existing canonical clusters). High-confidence novel entities receive a new `entity_uid`; ambiguous matches link provisionally and log to a review view.
6. **Vector Append & Sparse Adjacency Refresh (`40 sec`):** Embeds new chunks with FastEmbed ONNX, appends them to LanceDB (`table.add()`), runs `table.optimize()`, and exports the updated DuckDB `edges` table to `graph_csr.npz` (`~4 sec` for 3M edges).

### Artifact Storage Strategy on GitHub Actions (Avoiding Git Bloat)

Never commit multi-gigabyte binary database files directly into Git commits:

* **Commit Append-Only JSONL Extraction Logs to Git (`data/kg_extractions/<YYYY-MM>.jsonl`):** Text extractions compressed or stored as JSONL grow by only `~2–3 MB/month`. Committing these to the repo ensures **every LLM token ever spent is permanently version-controlled in Git**. If the binary database is ever deleted, DuckDB and LanceDB can be rebuilt deterministically from the JSONL logs in 15 minutes at `$0.00` LLM cost.
* **Publish Binary Index Snapshots (`shipping_kg.duckdb` + `lancedb.tar.zst`) to a Rolling GitHub Release Tag (`kg-latest`) or Cloudflare R2 Free Tier:** The GitHub Action downloads `kg-latest` at the start of the cron job, applies the 2-minute incremental delta, runs the self-check suite, and uploads the updated snapshot back to `kg-latest` (and your laptop pulls it with a single command: `gh release download kg-latest`).

### Surgical Correction of Wrong Extractions or Entity Merges

Because every node, edge, table row, and vector chunk stores foreign-key lineage (`doc_id`, `chunk_id`, `extractor_version`, `raw_source_mention`, `resolved_entity_uid`), fixing mistakes never triggers a full rebuild:

* **Fixing an Upstream Parser or Source File:** When a parser bug is fixed and `source_sha256` changes in a Markdown file, `sync` runs a transactional cascade delete (`DELETE FROM edges WHERE doc_id = ?; DELETE FROM fixtures WHERE doc_id = ?;` + `lance_table.delete(f"doc_id = '{doc_id}'")`) and re-ingests only that document in `<2 seconds`.
* **Fixing a Bad Entity Merge or Alias (`data/kg_overrides/entity_overrides.yaml`):** Because the `edges` table preserves both `raw_source_mention` (immutable) and `resolved_source_uid` (mutable pointer), adding a `force_merge`, `force_split`, or `alias_map` entry to `entity_overrides.yaml` and running `python -m shipping_graph apply-overrides` updates the pointers in DuckDB and rebuilds `graph_csr.npz` in **`<5 seconds` with zero LLM calls**.
* **Fixing a Bad LLM Extraction:** Specific bad edges can be suppressed via `data/kg_overrides/edge_blacklist.yaml` or re-extracted by bumping `PROMPT_VERSION` for specific `doc_id`s and running `sync --reextract-doc <doc_id>`.

## 5. Quality Measurement: Pilot Design, Evaluation Suite & Acceptance Gates

### Phase 0: The 1% Stratified Pilot (`~$0.65`, `25 Minutes`)

Before running the full 20,705-document build, execute a **Stratified Vertical Slice Pilot** spanning two well-known market regimes (**2023-10 to 2024-06 Red Sea / Panama Canal disruptions** and **2020 Q1–Q2 VLCC floating storage spike**):

* **Pilot Dataset:** `300` Broker MDs across 10 publishers + `100` `*.tables.json` sidecars + `30` SEC filings (`FRO`, `DHT`, `SBLK`, `GOGL`, `STNG`, `VALE`) + `2` Books (Stopford + Kavussanos) + all `166` Series CSVs.
* **Pilot Verification:** Measure JSON schema validity (`target >= 99.5%`), Splink vessel deduplication precision/recall on 200 hand-checked vessels, and query latency (`target < 3s` local retrieval before LLM synthesis) before unlocking the full build.

### The 120-Question Golden Evaluation Suite (`tests/eval_benchmark.jsonl`)

Measure quality before and after the full build against a permanent **120-question benchmark** across the five target question archetypes described in the brief:

| Benchmark Category | Example Test Query | Automated Metric | "Good Enough" Acceptance Gate |
| :--- | :--- | :--- | :--- |
| **1. Exact Numeric & Table Lookup (`25 Qs`)** | *"What was the TD3C TCE in Week 40 2025, and which VLCC fixtures were reported that week?"* | **Exact Value Match (EVM)** against `series/` CSV & `*.tables.json` + **Source File Citation Match** | **$\ge 98\%$** Exact Value Match; **100%** zero invented numbers; **$\ge 95\%$** exact source citation |
| **2. Single-Entity 360° Timeline (`25 Qs`)** | *"List every fixture, S&P deal, valuation, and SEC filing mention of M/V [Vessel Name] (or DHT Holdings) from 2021 to 2026."* | **Entity Recall@K** against ground-truth SQL index + chronological ordering | **$\ge 90\%$** recall of known corpus mentions across brokers & SEC filings |
| **3. Multi-Series Co-Movement + Broker Attribution (`25 Qs`)** | *"How did Capesize 5TC rates, 5-year Capesize asset prices, and fleet supply move in Q3 2024, and what did brokers say caused it?"* | **Directional Sign Agreement** (SQL series vs. prose claims) + **Publisher Attribution Recall** | **100%** numeric accuracy on series deltas; **$\ge 85\%$** recall of distinct publisher causal explanations |
| **4. SEC Filing vs. Broker & Market Alignment (`20 Qs`)** | *"How did Star Bulk's (SBLK) reported Q2 2025 TCE and fleet renewal commentary line up with Baltic benchmark rates and broker S&P tables?"* | **Cross-Source Join Hit Rate** (retrieves SEC filing + matching period broker + series data) | **$\ge 88\%$** hit rate retrieving all 3 modalities (SEC + Series + Broker) in top-15 context |
| **5. Structural Theory + Negative Abstention Traps (`25 Qs`: `15` Book + `10` Unanswerable)** | *Book:* *"How does orderbook-to-fleet ratio affect secondhand price volatility at cycle peaks?"*<br>*Trap:* *"What was the partner-country trade share in Oct 2026?"* (known gap after `2026-08`) | **Citation Groundedness** (claims verified in cited chunk) + **Abstention Accuracy** on known gaps (`PRE_GRAPHRAG_OPEN_ITEMS.md`) | **$\ge 95\%$** Abstention Rate on out-of-corpus/gap traps; **$< 1\%$** unsupported factual claims |

### Automated Post-Ingestion Self-Checks (`verify_kg.py`)

Every build and weekly cron run executes three deterministic checks (zero LLM cost):

1. **Substring & Number Grounding Check:** Verifies that every LLM-extracted `CAUSED_OR_DROVE` or `FORECASTS` edge references a sentence span that exists verbatim in the parent chunk, and that any number inside the extracted claim appears in the source chunk.
2. **Bi-Temporal Sanity Check:** Flags any non-forecast edge where `t_valid_start > t_pub + 180 days` or where `doc_id` is missing from `corpus_manifest`.
3. **Swap-Order LLM Judge Protocol ([Zeng et al., 2025](https://volcanicminds.com/en/insights/graphrag-vs-hybrid-rag)):** Whenever an LLM judge evaluates answer quality during benchmarking, every comparison is run twice with swapped order `(A, B)` and `(B, A)` to eliminate position and length bias.

## 6. Key Risks & What Not To Do

### Top 6 Domain & Operational Risks (and Mitigations)

| Risk | How It Manifests in Shipping Data | Architectural Mitigation |
| :--- | :--- | :--- |
| **1. Vessel Homonyms & Sister-Ship Collisions** | Dozens of ships share names like *"Star"*, *"Eagle"*, *"Pacific"*, or *"Athena"* across decades, or sister ships share `(2015, 81,500 DWT, Japan)`. | Never merge vessel nodes on name alone. Require `(Cleaned Name + Build Year ± 1 + DWT ± 3%)` or an exact `IMO`. Bare names in prose without DWT/class context attach as `AmbiguousVesselMention` edges rather than polluting canonical vessel nodes. |
| **2. Double-Counting the Same S&P Deal or Fixture Across 23 Brokers** | When a VLCC sells for `$85M`, Fearnleys, Gibson, Hellenic, Banchero Costa, and Xclusiv all list it across 1–3 consecutive weeks with minor rounding (`299,999` vs. `300,000` DWT). | Separate **`DealReportMention`** (1 row per broker report) from **`CanonicalSnPTransaction`** (deduplicated cluster where `same_vessel_uid` AND `\|date_1 - date_2\| <= 28 days` AND `\|price_1 - price_2\| <= 5%`), storing `reported_by = [Fearnleys, Gibson, ...]` on the canonical record. |
| **3. SEC Filing Date vs. Fiscal Period Confusion** | A `20-F` filed in March 2026 reports FY 2025 numbers alongside 2024/2023 comparatives and Q1 2026 subsequent events. | Enforce bi-temporal columns (`t_pub` = filing date; `t_valid_start` / `t_valid_end` = fiscal period parsed from table/section headers) on every SEC chunk, table row, and graph edge. |
| **4. Unit & Rate Basis Mismatches** | Freight quoted in `$/day` (TCE), `Worldscale (WS)`, `$/mt` (voyage), or index points; capacity in `DWT`, `CBM` (gas), or `TEU`. | Make `unit` and `rate_basis` mandatory columns on all numeric tables. SQL aggregation templates group by `(metric_id, unit)` and refuse to average `WS` points with `$/day`. |
| **5. Router Interruption or Closure** | Sign-ups on your router are closed; long batch jobs can hit rate limits, drop connections, or face future endpoint deprecation. | Checkpoint every chunk in local SQLite WAL + Git-committed JSONL logs keyed by `chunk_sha256`. Any interrupted job resumes from the exact next chunk. Standard OpenAI-compatible JSON schemas allow future weekly updates (`~$2/yr`) to switch to any provider in 1 line of config. |
| **6. Hallucinating Over Known Corpus Gaps** | An LLM fills in missing data (e.g., partner-country trade shares after `2026-08` or unprinted chart values) using pre-trained knowledge. | Parse `docs/PRE_GRAPHRAG_OPEN_ITEMS.md` and `corpus/CORPUS_REGISTRY_AND_CADENCE_AUDIT.md` into a `corpus_known_gaps` table in DuckDB. The query router checks `corpus_known_gaps` before synthesis and injects a mandatory abstention notice when a query overlaps a documented gap. |

### What I Would Explicitly NOT Do

* **Do NOT use an LLM to extract numbers from `*.tables.json` or `series/*.csv`.** It costs 50× more and introduces transcription errors into clean data.
* **Do NOT generate static Leiden community summaries (Microsoft GraphRAG style).** Static community summaries blend 2008 supercycle commentary with 2024 Red Sea commentary and go stale on every weekly update. Synthesize dynamically at query time over time-filtered subgraphs (`t_valid_start` to `t_valid_end`).
* **Do NOT run Neo4j, Docker, Qdrant Server, or a local 7B/8B LLM on the laptop.** On an `i3-1215U` with `8 GB RAM`, background database servers and local LLM weights will cause swap thrashing; keep storage embedded (`DuckDB` + `LanceDB`), embeddings/reranking in-process via quantized ONNX (`FastEmbed` + `FlashRank`), and LLM generation on the API router.
* **Do NOT OCR or estimate numbers from chart images.** Preserve your corpus quality rule: index chart titles and source captions so users can locate the visual in the original PDF, but never invent numbers from pixels.

## 7. End-to-End Query Execution Flow (How a Question Is Answered)

When a user asks a question, a lightweight router call (`DeepSeek V4 Flash`, `~300` tokens) decomposes the question into a structured execution plan across four deterministic tools before synthesizing the final response:

1. **`sql_series_and_tables(entities, routes, metrics, date_from, date_to)`:** Queries DuckDB `series_observations`, `fixtures`, `snp_deals`, and `sec_fleet_rows` to retrieve exact printed numbers, period-over-period deltas, co-movement correlations, and source file paths.
2. **`graph_ppr_traverse(seed_entity_uids, date_from, date_to, edge_types)`:** Executes Personalized PageRank ([HippoRAG 2](https://arxiv.org/abs/2502.14802)) over the time-filtered DuckDB/CSR graph to surface multi-hop connected vessels, counterparties, broker causal claims (`CAUSED_OR_DROVE`), and book mechanisms (`THEORETICAL_MECHANISM`).
3. **`hybrid_chunk_search(queries, metadata_filters, top_k=30 -> rerank_k=10)`:** Runs LanceDB hybrid retrieval (Tantivy BM25 + 384d ONNX dense vectors) pre-filtered by `issue_date`, `publisher`, or `ticker`, followed by local FlashRank cross-encoding.
4. **`gap_and_citation_auditor(draft_answer, retrieved_evidence)`:** Checks `corpus_known_gaps` for documented missing series, verifies that every figure in the response matches a retrieved SQL row or verbatim passage, and enforces inline `[Publisher / Ticker Form, Issue Date, Section/Table](file_path#chunk_id)` citations.

## References & Benchmarks Cited

* **GraphRAG vs. Hybrid RAG Multi-Corpus Benchmarks (Nov 2026):** [Volcanic Minds — GraphRAG or Hybrid RAG: When the Graph Is Worth What It Costs](https://volcanicminds.com/en/insights/graphrag-vs-hybrid-rag) (synthesizing GraphRAG-Bench ICLR 2026, Fan et al. 2026, Han et al. 2026, Zeng et al. 2025, and Akarsu et al. 2026).
* **Indexing & Query Token Cost Analysis (2026):** [Beri — GraphRAG vs Vector RAG: Indexing and Query Cost Across LightRAG and LazyGraphRAG](https://www.beri.net/article/graphrag-vs-vector-rag-indexing-query-cost-lightrag-lazygraphrag-2026) and [Mnemoverse — The GraphRAG Tax: When a Knowledge Graph Doesn't Pay](https://mnemoverse.com/docs/library/graphrag-tax).
* **HippoRAG 2 (Personalized PageRank + Passage Integration, ICML 2025):** [Gutiérrez et al. — From RAG to Memory: Non-Parametric Continual Learning for Large Language Models (arXiv:2502.14802)](https://arxiv.org/abs/2502.14802) and [OSU-NLP-Group/HippoRAG GitHub Repository](https://github.com/osu-nlp-group/hipporag).
* **LightRAG & Microsoft GraphRAG Cost Verification (Oct 2026):** [Kim — LightRAG vs Microsoft GraphRAG in 2026: Verified Costs and Benchmarks](https://dev.to/jangwook_kim_e31e7291ad98/lightrag-vs-microsoft-graphrag-in-2026-the-costs-we-could-verify-and-the-benchmark-numbers-we-5bci) and [HKUDS/LightRAG GitHub Repository](https://github.com/hkuds/lightrag).
* **LazyGraphRAG Cost & Benchmark Overview:** [ArticSledge — Microsoft Research LazyGraphRAG Analysis](https://www.articsledge.com/post/lazygraphrag-retrieval-augmented-generation).
* **Temporal Knowledge Graphs for Evolving Data:** [Zep — Graphiti: Real-Time Temporal Knowledge Graphs](https://github.com/getzep/graphiti).
* **Embedded Analytical, Vector & Graph Storage:** [DuckDB Official Documentation](https://duckdb.org/library/), [DuckDB VSS Memory Behavior Guide](https://dev.to/muhammadikhwanfathulloh/vector-similarity-search-with-duckdb-a-practical-guide-to-the-vss-extension-p5c), [LanceDB × DuckDB Multimodal SQL Retrieval](https://www.lancedb.com/blog/make-your-sql-workflows-multimodal-with-lancedb-x-duckdb), and [KùzuDB Archival & Embedded Graph Landscape (2026)](https://www.puppygraph.com/blog/what-is-kuzudb).
* **Probabilistic Entity Resolution on DuckDB:** [UK Ministry of Justice — Splink Probabilistic Record Linkage Documentation](https://moj-analytical-services.github.io/splink/index.html) and [Splink GitHub Repository](https://github.com/moj-analytical-services/splink).
* **CPU-Optimized ONNX Embeddings & Reranking:** [Qdrant FastEmbed ONNX Documentation](https://qdrant.tech/documentation/fastembed/) and [FlashRank CPU Cross-Encoder Reranking](https://hysenlabs.com/projects/prithivirajdamodaran-flashrank).
* **Public Maritime Entity Seed Registries:** [Equasis Public Ship & Company Registry](https://www.equasis.org/) and [UNECE UN/LOCODE Code List by Country and Territory](https://unece.org/trade/cefact/unlocode-code-list-country-and-territory) ([DataHub UN/LOCODE CSV](https://datahub.io/core/un-locode)).
