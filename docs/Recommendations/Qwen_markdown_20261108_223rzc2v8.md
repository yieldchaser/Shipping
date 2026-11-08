# Maritime GraphRAG System Architecture & Implementation Plan

**Project:** Maritime / Shipping Knowledge Graph & GraphRAG System  
**Corpus Size:** ~105-110M tokens (Prose, Tables, 727k Time-Series Rows)  
**Hardware Constraints:** Windows 11 Laptop, Intel i3-1215U, 8GB RAM, ~40GB Disk  
**Budget Constraint:** ~$145 API Credit (OpenAI-compatible router)  
**Date:** November 8, 2026  

---

## Executive Summary

To build a faithful, incremental, and hardware-constrained GraphRAG system over 105M tokens of maritime data, you must abandon "one-size-fits-all" vector search. The recommended architecture is a **Hybrid Agentic System** that routes data types to their optimal storage: **LightRAG** for prose narratives, **KAG (Knowledge Augmented Generation)** for tabular deals, and **Agentic SQL** for numeric time series. 

This approach fits strictly within your $145 budget (costing ~$16 for the full build), respects the 8GB RAM / 40GB disk limits via embedded databases (SQLite/DuckDB), and guarantees 100% numeric faithfulness and absolute traceability.

---

## 1. Architecture: Recommended vs. Rejected Alternatives

### Rejected Alternatives
*   **Microsoft GraphRAG:** Rejected. It relies on global Leiden community detection and hierarchical summarization. It is extremely token-heavy, slow, and expensive for 100M+ tokens. It is built primarily for prose and struggles natively with dense tables and exact numeric lookups.
*   **Heavy Graph Databases (Neo4j / Memgraph / NebulaGraph):** Rejected. Your hardware (i3-1215U, 8GB RAM) cannot comfortably run a JVM-based or memory-hungry graph database alongside local LLM/embedding processes without constant out-of-memory (OOM) crashes.
*   **Naive Vector RAG (Standard Chunking + Embeddings):** Rejected. It fails at multi-hop reasoning (e.g., "how freight rates and fleet supply moved together") and cannot perform exact math on time series data.

### Recommended Architecture: LightRAG + KAG + Agentic SQL
Instead of forcing all data into a single graph structure, we route data types to their optimal retrieval paradigms:

1.  **Prose (Broker Commentaries, SEC MD&A):** Processed via **LightRAG** (HKUST). Unlike MS GraphRAG, LightRAG uses a lightweight dual-layer architecture (low-level entities and high-level relationships) that natively supports fast, incremental graph updates without global rebuilds. It excels at capturing qualitative sentiment, causal explanations, and broker narratives.
2.  **Tables (Fixtures, S&P Deals, Rate Grids):** Processed using a **KAG (Knowledge Augmented Generation)** approach. KAG uses schema-guided logical extraction to overcome the noise of traditional Open Information Extraction (OpenIE). We do not turn tables into unstructured text. Instead, the JSON sidecars (`*.tables.json`) are parsed into strict relational tables (e.g., `Fixtures`, `S&P_Deals`) and linked to the Graph nodes via typed edges (e.g., `Vessel_X -[WAS_FIXTURE_ON]-> Date_Y`).
3.  **Numeric Time Series:** Left as raw CSVs and loaded into **DuckDB**. Handled via an **Agentic SQL Tool** layer. The LLM does not read 727k rows. When asked "what was the TD3C TCE in week 40 2025?", the agent writes a SQL query, DuckDB executes it instantly, and returns the exact number to the LLM for final prose generation. This guarantees 100% numeric faithfulness.
4.  **Entity Resolution:** Deterministic rules first, then fuzzy matching. Vessels are resolved by IMO number; SEC issuers by CIK/Ticker; routes by Baltic codes. For unstructured names ("undisclosed buyer"), we use a manually curated alias dictionary combined with lightweight embedding similarity.

---

## 2. Tools, Libraries, and Storage

Given the 8GB RAM constraint, all storage must be embedded and zero-ops.

*   **Storage (SQLite + DuckDB):** 
    *   **SQLite** with the `sqlite-vec` extension will be used for vector search and graph persistence. SQLite is a single-file, zero-dependency database that easily fits on your 40GB disk and uses minimal RAM compared to enterprise DBs. Concepts from `sqlite-graphrag` will be used to persist nodes, edges, and metadata in relational tables.
    *   **DuckDB** will be used exclusively for the time-series CSVs. It is the gold standard for fast, local, columnar analytical SQL and handles window functions natively.
*   **GraphRAG Framework:** The open-source **LightRAG** Python library.
*   **Embeddings:** **Free hosted APIs** (e.g., HuggingFace Serverless Inference API, Cohere free tier). Running local embedding models on 8GB RAM while parsing 100M tokens risks OOM errors. If you must run locally, use a quantized ONNX model like `bge-small-en-v1.5` via `optimum` (uses ~200MB RAM).
*   **LLM Router:** Use your provided router with **GPT-OSS 120B** ($0.10 / 1M input) or **DeepSeek V4 Flash** ($0.13 / 1M input) for extraction and summarization.
*   **Orchestration:** **LlamaIndex** or **LangGraph** to manage the agentic SQL routing and tool calling.

---

## 3. Cost and Time Estimates

*   **Total Budget:** $145.
*   **Token Math:** You have ~105M tokens of Markdown.
    *   **Input Cost:** 105M input tokens using GPT-OSS 120B ($0.10 / 1M input tokens) ≈ **$10.50**.
    *   **Output Cost:** Output tokens for extraction (assuming a 10% output ratio for KG triples, JSON schemas, and summaries) = 10.5M output tokens at $0.50 / 1M = **$5.25**.
    *   **Total LLM Cost for Full Build:** **~$15.75**. You will have ~$129 left for iterative testing, prompt engineering, and future updates.
*   **Time Estimate (One-Time Build):** Processing 105M tokens at standard API batch rates will take roughly **3 to 5 days** of background running. Because the laptop might sleep or disconnect, the pipeline must be heavily checkpointed.
*   **Weekly Updates:** ~50 new reports/week (~500k tokens). 
    *   **Cost:** **<$0.10 per week**. 
    *   **Time:** **< 30 minutes**. This easily runs on GitHub Actions free tier.

---

## 4. Incremental Updates and Corrections

### How New Material Enters
*   **Prose/Graph:** LightRAG natively supports incremental `insert()` operations. It appends new nodes and edges to the existing SQLite graph without triggering expensive global community rebuilds. New MDs are chunked, embedded, and appended to the vector tables.
*   **Time Series:** New CSV rows are simply appended to the DuckDB tables via a lightweight Python script. No re-indexing is required.
*   **Automation:** A GitHub Actions cron job triggers the ingestion script. The script reads the `CORPUS_REGISTRY_AND_CADENCE_AUDIT.md` to check for new files, processes them, and pushes the updated SQLite/DuckDB files back to the repo (or an attached cloud storage if the DB exceeds GitHub's file size limits, though 105M tokens in SQLite will likely be <2GB).

### How Corrections Are Made
If a parser extracts a wrong deal (e.g., misreads a vessel name in a rate grid):
1.  Because every extracted node and edge in SQLite carries a `source_file` and `source_sha256` metadata column, you simply run a targeted SQL delete: 
    `DELETE FROM edges WHERE source_file = 'xyz.pdf' AND entity = 'Vessel A'`.
2.  You then re-run the extraction pipeline *only* on that specific MD file. No full rebuild is required.

---

## 5. Quality Measurement and "Good Enough"

### The Pilot (Crucial First Step)
Do not run the 5-day build immediately. Select a 2-week slice of data (e.g., 500 MDs from Fearnleys and Breakwater, plus 1 SEC 10-K, and 10 time series). Run the full pipeline to tune prompts, regex rules, and KAG schemas. 

### Measurement Metrics
1.  **Faithfulness/Traceability:** Sample 100 extracted facts. Verify that the `source_passage` actually supports the extracted triple.
2.  **Numeric Accuracy:** Ask 20 specific questions ("What was the TD3C TCE in week 40 2025?"). Compare the Agentic SQL output against the raw CSV.
3.  **Recall:** Ask a multi-hop question ("Which brokers predicted a dry bulk slump in Q3 2024 and why?"). Check if the system retrieves both the broker reports and the corresponding freight index data.

### Definition of "Good Enough"
*   **100%** of exact numbers must match the CSVs (handled by Agentic SQL).
*   **Zero** hallucinated numbers. If the system doesn't know, it must say "Not in corpus" or "Data gap until 2026-08".
*   **Traceability:** Every claim in the final answer has a clickable link to the source MD file, table sidecar, or CSV row.
*   **95%** of extracted entities correctly resolved to canonical IDs.

---

## 6. Risks and What Not To Do

### Primary Risks
*   **Table Parsing Errors:** Broker PDFs often have complex, multi-column rate grids. If the upstream MD parser mangles the table, the LLM will extract garbage. 
    *   *Mitigation:* Rely heavily on the `*.tables.json` sidecars; use LLMs only to clean up specific malformed tables, not to parse raw PDF grids from scratch.
*   **Context Window Overload:** SEC 10-Ks are massive. Feeding a whole 10-K into an LLM for extraction will fail or hallucinate. 
    *   *Mitigation:* Strict chunking with overlap, or hierarchical summarization (using a cheaper model to summarize sections before extracting entities).
*   **API Rate Limits/Interruptions:** A multi-day build on a laptop will face network drops or API rate limits. 
    *   *Mitigation:* SQLite transactions and strict checkpointing; the script must track `last_processed_file` and resume seamlessly.

### Anti-Patterns (What NOT To Do)
*   **DO NOT** use Microsoft GraphRAG's Leiden community detection; it is too slow and expensive for this hardware.
*   **DO NOT** embed raw CSV rows into the vector database; it wastes disk/RAM and ruins semantic search. Let DuckDB handle numbers.
*   **DO NOT** try to run local LLMs (e.g., Llama 3 8B) on an i3-1215U with 8GB RAM; it will be excruciatingly slow and crash. Use the cheap API router.
*   **DO NOT** attempt to resolve "undisclosed buyers" using pure NLP guess-work; it's a known data gap. Document it as a gap rather than guessing.