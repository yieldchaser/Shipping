# GraphRAG Architecture Recommendation for the Maritime / Shipping Corpus

**Date:** 2026-11-08  
**Scope:** One-time build + incremental updates over broker reports, SEC filings, maritime books, and numeric time series.  
**Constraints observed:** ~USD 145 LLM budget, Windows 11 laptop (i3-1215U, 8 GB RAM), public repository, GitHub Actions automation, single operator.

---

## 1. Recommended Architecture

**Hybrid temporal entity graph + dual-index retrieval**  
(LightRAG-style core, domain-specific numeric layer, provenance-first design)

This is the best practical system for the stated constraints, corpus shape, and question types. It prioritises faithfulness, incremental updates, exact numbers, cross-source entity linking, and low ongoing cost on a single low-spec machine.

### Core Design

- **Entity-centric knowledge graph** with rich provenance and temporal edges.  
  **Nodes:** Vessel, Company/Owner, Route/Index (TD3C, C5…), Port, Cargo, Event, Report/Filing, BookConcept, NumericSeries.  
  **Edges** carry: relation type, timestamps (`issue_date` / `filing_date` / series date), source document ID + passage or table-cell locator, confidence, and extractor version.

- **Dual retrieval**
  - Graph traversal / neighbourhood expansion for multi-hop and “what every source said about X” queries.
  - Dense vector search over chunks + entity descriptions for semantic/local search.
  - Hybrid fusion (graph hits + vector hits) ranked by a lightweight reranker or reciprocal rank fusion.

- **Separate authoritative numeric layer**  
  The existing long-format CSVs (and any new rows) live in a queryable store (SQLite or DuckDB). Graph nodes for series/routes point to the exact series key. Answers that need a precise number (“TD3C TCE week 40 2025”) go straight to the series table and cite the source file. **Never** let an LLM invent or approximate a number that exists in the series.

- **Tables**  
  Treat structured tables (fixtures, S&P deals, rate grids) as first-class. Either:
  - (a) keep the `.tables.json` sidecars and link table rows as nodes/edges with cell-level provenance, or
  - (b) convert key tables into typed triples at ingestion.  
  Prefer (a) + selective triple extraction for high-value relations.

- **Prose / reports / filings / books**  
  Chunk by semantic units (section, paragraph, or table-aware). Extract entities + relations with an LLM, resolve them against the growing entity registry, attach provenance, and embed both the chunk and a short entity/relation description.

- **Entity resolution across sources and time**
  - Canonical registry with aliases and attributes (IMO / DWT / yard / built year for vessels; ticker / CIK for companies; Baltic code for routes).
  - Blocking (name + type + key attributes) + embedding similarity + LLM judge for ambiguous cases.
  - Temporal: same surface form at different times can be the same entity (most vessels/companies) or distinct facts (ownership changes, rate observations). Edges are timestamped; identical facts at different times are distinct edges.
  - “Undisclosed” / nicknames are kept as provisional nodes and linked later when evidence appears.

- **Temporal handling**  
  Every fact/edge carries validity or observation time. Retrieval can filter or weight by time window. For long-horizon structural questions the books supply durable concepts that link to market entities.

- **Community / global summaries**  
  Optional and cheap. Run a lightweight community detection (or simple clustering on high-degree entities) only on a pilot or periodically. Do **not** rebuild hierarchical Microsoft-style community reports on every update. Global questions are answered by retrieving relevant communities or high-centrality paths + vector context, or by an agent that plans multiple retrievals.

### Why This Over Pure Alternatives

| Approach | Why rejected or limited |
|----------|-------------------------|
| Full Microsoft GraphRAG (community hierarchy + global summaries) | Excellent for pure thematic “what does the whole corpus say” questions, but indexing is expensive, incremental updates force expensive rebuilds of communities, and the project is largely in maintenance mode. Budget and daily/weekly inflow make it unsuitable as the primary path. |
| Pure vector RAG | Fails multi-hop, “everything about vessel X”, and cross-document causal stories. Faithfulness is weaker without explicit relations and provenance. |
| Heavy temporal GraphRAG (full bi-level time hierarchy + multi-granularity summaries everywhere) | Powerful for pure time-sensitive finance QA, but overkill and costly for the mix of exact series + broker commentary. Use temporal edges + filtered retrieval instead. |
| Fully agentic multi-step reasoning at query time with no graph | Too slow and expensive for routine use; hard to keep faithful. Use agents only for complex queries on top of the graph + series. |
| Neo4j / full server graph DB as the only store | Memory and ops overhead on an 8 GB laptop; unnecessary for this scale. |

The hybrid captures the relational and temporal strengths of GraphRAG while keeping indexing and updates in the LightRAG cost regime, and it treats the numeric series as the single source of truth for numbers.

---

## 2. Tools, Libraries and Storage

| Component | Recommendation | Rationale |
|-----------|----------------|-----------|
| Core framework | LightRAG (HKUDS) or thin custom pipeline inspired by it | Native incremental insert, dual-level retrieval, flexible storage backends, active maintenance. Extend entity/relation extraction prompts and the resolution step for maritime entities. |
| Graph storage | NetworkX (in-memory / pickle) or embedded option (Kuzu / LadybugDB-style columnar graph, or SQLite + adjacency table) | Fits 8 GB RAM. Avoid Neo4j/Memgraph server processes unless moving to a larger machine later. FalkorDB Lite is also viable if Cypher is desired. |
| Vector store | LanceDB, Chroma, or FAISS on disk | All fit the hardware. Prefer models with good numeric/table handling. |
| Numeric series | DuckDB or SQLite | Already long-format; add indexes on `(series, date)`. Graph nodes reference the series key. |
| Extraction / LLM | Cheapest capable models on the router first (DeepSeek V4 Flash / GLM 5.3 Flash / GPT-OSS 120B) for bulk work; stronger models only for hard resolution and final answers | All calls must be checkpointed and resumable. |
| Entity registry | Simple SQLite/JSON + embedding index of canonical names + aliases + key attributes | Updated incrementally. |
| Provenance | Every node/edge stores `source_file`, `sha256`, `issue_date`/`filing_date`, `chunk_id` or `table_row_id`/`cell` | Answers always surface the citation. |
| Orchestration | Python scripts + GitHub Actions for the incremental path; local laptop runs for the one-time build and corrections | Matches existing automation. |
| Optional later | Thin agent layer (LangGraph or plain tool-calling) | Can decide “query series”, “expand graph neighbourhood of vessel X”, “retrieve filings for ticker Y in date range”. |

Everything above runs on the stated hardware or free/cheap hosted pieces. No keys or tokens are committed to the repository.

---

## 3. Cost and Time Estimates

### One-time Build
(~105–110 M tokens of Markdown + tables + series)

- Aggressive filtering and smart chunking (tables stay structured; only high-value prose is fully extracted) can keep LLM input under ~40–60 M tokens of actual extraction work.
- Using the cheapest flash models (≈ $0.10–0.30 / 1 M input): expect **$40–90** for extraction + resolution + embedding. Stronger models for a small fraction of ambiguous cases add another **$20–40**.
- **Total LLM spend** comfortably inside the $145 budget (leave headroom for retries and pilot). Embeddings are cheap or free if local.
- **Wall-clock:** several days of intermittent laptop runs with checkpointing (i3 + 8 GB is the bottleneck, not the API). Parallelise by publisher or by date batches. GitHub Actions can help for non-LLM steps.

### Weekly / Daily Incremental

- New reports are a few dozen to a couple of hundred files per week at most.
- **Cost:** a few dollars (often < $5) using the same cheap models. Only new material is processed; entity resolution touches the registry but does not rebuild the graph.
- **Runtime:** minutes to low tens of minutes on the laptop or a GitHub Actions job.

---

## 4. Incremental Ingestion and Correction

### Ingestion Flow

1. Scrapers/parsers drop new MD + `.tables.json` + series rows (already happening).
2. A watcher or Actions job detects new/changed files (by `sha256`).
3. Chunk → extract entities/relations (with the same prompts) → resolve against the live registry (blocking + embedding + optional LLM judge) → insert/merge nodes and timestamped edges with full provenance → embed new chunks and entity descriptions → update the numeric store if new series rows appear.
4. No community rebuild required. Graph and vector indexes grow by union + deduplication.

### Correction of a Wrong Extraction

- Soft-delete or mark the bad edge/node with a “superseded” flag and the correcting source.
- Or re-process the single source document with a corrected prompt / manual override and re-merge (the merge logic already handles re-ingestion of the same `source_id`).
- Keep an audit log of extractions so any fact can be traced and rolled back.
- For systematic errors, re-run extraction on a publisher or date range with checkpointing; the registry and merge logic make it safe.

---

## 5. Quality Measurement and “Good Enough”

### Pilot First (Mandatory)

Take 2–3 publishers (e.g. Fearnleys + Baltic + one SEC ticker) + the corresponding series for 12–18 months. Build the subgraph, then evaluate.

### Metrics (Before and After Full Build)

| Metric | Target / Method |
|--------|-----------------|
| Faithfulness / citation accuracy | Every atomic claim in an answer must link to a real passage, table cell, or series row. Human or LLM-as-judge on a held-out set of 50–100 questions. Target > 95 % of claims correctly grounded (unsupported claims = failure). |
| Entity resolution quality | Precision/recall on a hand-labelled set of vessel, company, and route mentions (sample across publishers and years). Target > 90 % precision on merges; high recall on known aliases. |
| Numeric exactness | 100 % of answers that cite a series value must match the CSV exactly and name the source file. |
| Retrieval usefulness | For the example question types in the brief, measure whether the correct sources and relations appear in the top-k context (context recall) and whether the final answer is complete and non-hallucinated. |
| End-to-end | Small gold set of questions with reference answers (or “not in corpus”). Prefer “I don’t know / not in corpus” over a plausible invention. |

### Definition of “Good Enough”

- Exact numbers always correct and cited.
- Multi-source questions about a vessel / company / route return the relevant reports and the key relations without major omissions or contradictions.
- Causal / market-move questions surface the broker commentary that actually discusses the drivers, with dates.
- Hallucination rate on grounded claims < 5 %.
- Incremental updates do not degrade the above.

**Process:** Run the pilot → fix extraction prompts and resolution rules → commit to the full build. After the full build, re-evaluate the same gold set plus a fresh sample.

---

## 6. Risks and What Not to Do

### Main Risks

| Risk | Mitigation |
|------|------------|
| Entity resolution errors (similar vessel names, “undisclosed” buyers, name variations across 20+ years and 23 publishers) | Attribute-rich blocking, human-reviewable merge log, conservative thresholds. |
| Extraction quality on dense tables and noisy OCR/parsed MD | Keep tables structured; only extract relations that matter. |
| Cost or time overrun on the full build | Checkpoint aggressively, start with cheapest models, pilot first. |
| Laptop resource limits during embedding or large graph operations | Process in batches; keep the working graph subset in memory; use on-disk vector and graph stores. |
| Drift between series CSVs and extracted commentary | Series are authoritative; graph only points to them. |
| Over-reliance on community summaries for global questions | Summaries are optional and cheap; prefer explicit retrieval + synthesis. |

### What Not to Do

- Full Microsoft GraphRAG community hierarchy as the primary index (too expensive to keep current).
- Let the LLM generate or approximate any number that exists in the series tables.
- Store secrets or personal data in the repository or the graph.
- Build a complex multi-agent system as the default query path (keep the base retrieval simple and faithful; add agents only where needed).
- Attempt to “complete” missing data or read numbers off chart images.
- Run continuous expensive re-summarisation or full re-indexing.

---

## Summary

This design directly serves the example questions in the brief, stays inside budget and hardware limits, supports true incremental flow from the existing scrapers, and puts faithfulness and provenance first.

**Recommended next step:** Start with the pilot on a few publishers. The rest of the pipeline follows cleanly from there.
