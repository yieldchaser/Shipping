# GraphRAG Design Recommendation for the Maritime / Shipping Corpus

**Date:** 2026-11-08
**Basis:** `GRAPHRAG_BRIEF.md` from the public repository `yieldchaser/Shipping`, plus a sweep of 2025–2026 GraphRAG literature and production write-ups.

---

## Executive Summary

**Don't run Microsoft's full GraphRAG pipeline. Build a domain-ontology graph with LightRAG-style dual-layer retrieval, keep every number out of the LLM's hands, and store everything embedded and provenance-tagged.**

Three lanes, one query router:

1. **Numbers:** the 166 series CSVs and the 6,142 table sidecars go into DuckDB/SQLite as structured data — never through an LLM. Exact-value questions ("TD3C TCE in week 40 2025") are answered by a SQL/tool call against the series store, with the source file and row cited.
2. **Prose:** broker commentary, SEC narrative and books are chunked and processed through an extraction pipeline (LightRAG-style, using the cheapest model) into a knowledge graph over a small, hand-written maritime ontology (vessels, companies, routes, indices, ports, cargoes, events, documents). Every extracted fact carries provenance: document sha256, file path, character offsets.
3. **Retrieval:** a router sends each question to the right lane — SQL tool for numbers, graph+vector hybrid for entity and multi-hop questions ("what did every source say about this vessel?"), and vector/BM25 chunks for thematic prose questions — with a bitemporal graph (valid time + transaction time) so the system can reason over "2008 vs 2024 fleet supply" questions and be corrected without rebuilds.

---

## 1. Recommended Architecture, and What Was Rejected

### 1.1 What to build

#### Layer A — Structured numeric core (DuckDB + SQLite)

This is the crown jewel and the thing most GraphRAG designs get wrong: they force tables through LLM extraction. The corpus already has the authoritative long-format series (727k rows) and parsed table sidecars (deals, fixtures, rate grids). Load them as-is into DuckDB: one table per sidecar schema class, plus the series table with `(date, series, route, value, unit, source_file)`. Practitioner consensus for financial-disclosure GraphRAG reaches the same conclusion — keep structured data structured and route queries to it — and builds evaluation stratified by evidence type for exactly this reason.

#### Layer B — The graph, over a fixed domain ontology

Do not let the LLM invent the schema. Write ~15 entity types and ~30 relation types up front (Vessel, Company, Route, Index, Port, Cargo, Event, Deal, Fixture, Report, Filing, Book, Chapter, Sector…; e.g. `Vessel -FIXTURED_ON-> Route`, `Company -SOLD-> Vessel`, `Report -MENTIONS-> Entity`, `Series -MEASURES-> Route`). This is the "ontology-aware GraphRAG" pattern, which beat generic GraphRAG variants on faithfulness (0.933) and exact-match accuracy (0.48 vs 0.02 for pure retrieval baselines) in a 2025 question-answering benchmark — at some recall cost, which is why hybrid chunk retrieval is kept alongside it.

The graph store itself stays **embedded and boring**: SQLite for nodes/edges/relations tables (or DuckDB), NetworkX in-process for traversal, LanceDB (embedded, has full-text + HNSW vector) for chunk embeddings. Skip graph servers: Neo4j CE wants a JVM that 8 GB of RAM cannot spare, and Kuzu — the obvious embedded choice — was archived in October 2025 after its team's acquisition by Apple, so starting on it now means adopting an unmaintained codebase.

#### Layer C — Extraction and retrieval (LightRAG-style, self-built, not the framework)

For each prose document: chunk (heading-aware, tables stripped and routed to Layer A), one cheap-LLM call per chunk extracting entities/relations **strictly as spans with offsets** (no paraphrase, no numbers unless quoted verbatim), deterministic registry matching first (see §4), then fuzzy+LLM-assisted resolution only for candidates. Retrieval = dual mode: entity-centric (seed nodes → 1–2 hop subgraph → facts with citations) and thematic (dense+BM25 over chunks, reranked), then merge. This is LightRAG's design, which was built specifically for incremental updates without community regeneration — Microsoft GraphRAG must dismantle and regenerate its community hierarchy on new data, while LightRAG just unions new entities/relations into the graph. Take the architecture, not the package: a custom ontology, provenance fields and bitemporal edges mean writing ~1,500 lines of pipeline code against the router API.

#### Bitemporality

Every edge gets `valid_from`/`valid_to` (when it was true in the world) and `recorded_at` (when it was learned). New information about a vessel's owner doesn't overwrite; it supersedes. This is the one idea worth stealing from Graphiti-style temporal graphs, adapted from agent memory to document provenance.

### 1.2 What was rejected, and why

| Alternative | Why rejected |
|---|---|
| **Microsoft GraphRAG (full pipeline)** | Community detection + hierarchical community reports are the best-in-class answer to "summarize the whole corpus," but indexing cost is brutal — roughly $50–200 at GPT-4 pricing for 500 pages — and every update threatens community regeneration. On a one-shot $145 credit with mandatory incremental flow, that's the wrong trade. GraphRAG 0.5.0 added incremental support but its behavior still needs validation against the exact release and storage config. |
| **LazyGraphRAG** | Genuinely interesting — indexing cost equal to plain vector RAG by deferring summarization to query time — but it shifts cost to query time, and the query budget is a finite, expiring credit on a closed router. |
| **Pure hybrid RAG (no graph)** | Cheapest and simplest, and for one-passage lookups it wins on recall — but it structurally cannot answer "what did every source say about this vessel" or trace a deal across a broker report, an SEC 8-K and a fixture table. Those are core questions here, so the graph earns its complexity. |
| **LLM-extracted numbers** | Rejected outright, per the faithfulness rule. The 2026 survey and practitioner consensus is that extraction quality and entity resolution — not the graph database — decide whether GraphRAG works. |

---

## 2. Tools and Storage

| Job | Choice | Why it fits |
|---|---|---|
| Numeric series, deal/fixture tables | DuckDB (+ SQLite for row-level writes) | Embedded, zero RAM overhead, fast time-series aggregates, one file to back up on a 40 GB disk |
| Graph | SQLite tables + NetworkX in-process | No server, no JVM, survives on 8 GB RAM; the graph is maybe 1–3M nodes/edges — trivially in-memory at query time |
| Chunk vectors + full-text | LanceDB | Embedded, HNSW + FTS in one store, Python-native |
| Embeddings | Local `bge-m3` (ONNX int8) or Qwen3-Embedding-0.6B | Free, offline, CPU-feasible; embed prose chunks + table *summaries*, never raw numeric cells |
| Extraction LLM | GPT-OSS 120B ($0.10/$0.50, 131k ctx) | Cheapest on the router by 3×, long context lets whole sections be sent with instructions |
| Resolution tie-breaker | DeepSeek V4 Flash ($0.13/$0.26) | Second cheapest; only used for ambiguous candidates |
| Query generation / final answers | Mid-tier (GLM 5.3 / DeepSeek V4.1 Flash) sparingly; default back to GPT-OSS | Answer quality is visibly better but 2–3× cost — use for hard multi-hop only |
| Orchestration | Plain Python + GitHub Actions, state in the repo | One owner; checkpoint files (JSONL per document) make runs resumable |

Everything runs embedded on the laptop; GitHub Actions only does the incremental top-up (see §4). Keys in env vars only.

---

## 3. Cost and Time

### 3.1 One-time build

| Item | Estimate |
|---|---|
| Prose sent to extraction (~60% of 110M tokens, tables stripped) ≈ 65M input tokens @ $0.10/M | ≈ **$6.50** |
| Extraction output: entity/relation JSON ≈ 15–20M output tokens @ $0.50/M | **$8–10** |
| Entity merge / description summarization ≈ 5–10M tokens | **$3–5** |
| Entity resolution passes (deterministic/free + ~1–2M tokens of LLM tie-breaks) | **≈ $1** |
| Pilot + evaluation + iteration | **$5–10** |
| Embeddings | **$0** (local, CPU time only) |

**Total LLM one-time build: roughly $25–35**, comfortably inside $145 with ~$100 of reserve for query-time usage. The published contrast is stark: LightRAG indexed a 500-page corpus for ~$0.50 where full GraphRAG ran $50–200; this corpus is ~200× that benchmark corpus, hence the $25–35 above.

### 3.2 Time

- The build is **API-throughput-bound**, not laptop-bound: at sensible concurrency, expect **3–7 wall-clock days** with checkpointing every N documents (mandatory anyway — the run must survive interruption on a router that closed sign-ups).
- Local embedding of ~150–250k chunks on an i3 is another **1–2 days** of background CPU.
- Disk: graph + vectors + chunks ≈ **8–15 GB**, fits the 40 GB free.

### 3.3 Weekly update

~100–400 new MDs + sidecars + series rows ≈ 1–4M tokens in, ~0.5–1.5M out ≈ **$0.50–2.00 per week**, a few hours of laptop or Actions time. Near-zero marginal cost is precisely LightRAG's argument against community-report architectures: incremental text update costs only the extraction of the new text, versus GraphRAG's ~5,000 tokens per community report to regenerate.

---

## 4. Incremental Flow and Correction

### 4.1 New file arrives (via existing GitHub Actions scrapers → a `pending/` directory)

1. **Deduplicate by sha256** (frontmatter already carries it). New hash → enqueue; known hash → skip. This makes re-runs idempotent.
2. **Series/sidecar rows** are appended to DuckDB with `source_file` provenance per row — no LLM involved, ever.
3. **Prose** goes through the same extraction pipeline as the build. New entities/relations are **upserted, not unioned blindly**: matched against registries first (IMO number for vessels — the strongest key available; Baltic route codes; ticker/CIK for listed companies; normalized names with deterministic rules like alphabetically-tokenized hub keys, which hit 97.15% precision in a commercial-registry study), then fuzzy candidates with confidence, then LLM tie-break only above a threshold.
4. **Never auto-merge ambiguous cases.** Store candidate links with confidence and method — probabilistic inference should not silently become authoritative master data. A weekly report lists unresolved candidates; a 10-minute human review is the one acceptable manual step, and it's tiny.

### 4.2 Correcting a wrong extraction — three levels

- **One document was parsed badly:** invalidate by document id — every fact/edge/chunk carries `source_sha256`, so deleting one document's contributions is a single indexed delete and rebuild of only its affected entity descriptions (LightRAG does exactly this with its LLM cache; document deletion triggers KG regeneration for the affected entities).
- **A wrong merge:** un-merge the hub — edges carry resolution provenance, so a hub can be split and only what it introduced re-pointed.
- **A wrong number:** it came from Layer A, so it's fixed in the CSV/parser and the DuckDB row is regenerated. No LLM fact was ever involved.

---

## 5. How We Know It Works

### 5.1 Pilot first, deliberately

Before touching the full corpus: ~150 reports spanning 5–6 publishers, 20 SEC filings, one book, all series. Cost: a few dollars. Purpose: freeze the ontology, chunking, prompts and registries **before** the one-shot build, because a full build with a wrong ontology is the biggest unrecoverable risk.

### 5.2 Golden set

Because the series CSVs are authoritative and the MDs are dated, ~150–300 eval questions with ground truth can be generated automatically: "TD3C TCE week 40 2025" (SQL lane), "all fixtures of vessel X in 2019" (graph+table lane), "what did broker commentary cite as the cause of the Capesize spike in Q3 2023?" (prose lane, LLM-judged with citation checks). Stratify the eval by evidence type (number / table / narrative / multi-source) so a lane that structurally can't answer a question doesn't pollute the pooled score.

### 5.3 Metrics, in priority order

1. **Faithfulness / citation validity:** every number and claim in an answer resolves to a real source span or row. Target ≥ 98%; anything unsupported must render as "not in the corpus," not as a guess.
2. **Entity-resolution precision** on a sampled audit — target ≥ 95%; recall reported but not gated, since exhaustive recall is unauditable.
3. **Answer correctness** on the golden set, per lane.
4. **Retrieval recall** per lane (secondary — the CEUR result that ontology-aware graphs trail BM25 on recall while crushing it on exact match is the formal argument for keeping both).

### 5.4 "Good enough"

On the golden set: citation validity ≥ 98%, entity-merge precision ≥ 95%, numeric questions answered exactly with source ~100% (this lane is deterministic — if it's not 100%, the tool is broken, not the model), and multi-source questions answered with correct entity stitching in ≥ 80% of cases. Below that, fix resolution and prompts; above it, ship.

### 5.5 After the full build

The same eval runs weekly against the incremental batch (regression gate), plus a drift report — new entities merged, unresolved candidates, documents skipped as duplicates, series gaps vs. the cadence audit.

---

## 6. Risks, and What Not to Do

### 6.1 Risks, ranked

1. **Entity resolution is the whole ballgame.** "Undisclosed" buyers, nicknamed owners, renamed vessels, and the same company as "Navios Maritime Holdings", "Navios" and a ticker will split or corrupt the graph. Mitigation: IMO/CIK/Baltic-code registries first, deterministic normalization, precision-first merging, the weekly human glance. A graph with merged-entity contamination is worse than no graph — practitioners are blunt that teams "build the graph and then discover, in production, that the entity resolution wasn't good enough."
2. **The router credit dies mid-build or the models change.** Hence: checkpoint every batch, all artifacts (graph, vectors, chunks) are local files owned by the repo, prompts and outputs versioned, and the pipeline is model-agnostic (any OpenAI-compatible endpoint). Burn the credit on extraction first, in priority order — extraction is the irreplaceable part; queries can always run against local artifacts later with any model.
3. **Scope creep into "global synthesis."** The one thing this architecture does worse than full GraphRAG is corpus-wide thematic summarization ("main themes across 20 years of dry bulk reporting"). Resist rebuilding community reports. If that question matters, add a cheap, *lazy* version: on such a query, retrieve top thematic chunks and pay for one summarization call at query time — LazyGraphRAG's deferral idea, without its framework.
4. **8 GB RAM / 40 GB disk.** Never load the whole corpus; stream documents through the pipeline; keep only the graph+vectors+chunk store resident. If disk tightens, store chunks as compressed JSONL and re-materialize on demand.
5. **GitHub Actions flakiness** (late crons, 6-hour limits). Actions only ever runs the *incremental* path, which is small and resumable; the one-time build runs on the laptop with checkpoint files committed back.
6. **Parser regressions upstream.** Scrapers already version parsers in frontmatter — the graph keys on document sha256, so a reparsed document is a new document version whose old version can be invalidated cleanly (incremental *insertion* is not the same as editing, and deterministic document IDs are needed for the edit case).

### 6.2 What not to do

- Full Microsoft GraphRAG with community reports.
- LLM extraction of numbers from prose or tables (the printed-values rule stays absolute — verbatim spans only).
- A hosted graph/vector database (Neo4j, Pinecone, FalkorDB — a server + RAM + ops not needed at this scale).
- Multimodal/chart-image reading (figures stay referenced by title, per the existing rule).
- Auto-merging of low-confidence entities to make the graph look cleaner.
- Any design that requires a human to operate it daily beyond the 10-minute weekly merge review.

---

## 7. Honest Caveat

All cost figures above are estimates built from published per-500-page benchmarks scaled to this corpus and the router's price card. The architecture is robust to that measurement coming in 2–3× higher; it is **not** robust to skipping the pilot. The pilot's first job is to replace estimates with measured per-document costs before committing the full build.
