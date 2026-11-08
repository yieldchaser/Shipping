# GraphRAG for the maritime corpus: architecture, cost, and risk

The system I would build is not a GraphRAG index. It is a time-aware maritime knowledge base with three retrieval planes over one canonical store: a deterministic fact plane for numbers, a hybrid evidence plane for text, and a thin temporal entity graph for relations. The LLM does four jobs and no others, namely selective quote-gated extraction of relations and events, reranking, period summarisation, and answer synthesis under a citation contract. Every number in an answer comes from a parsed cell or a stored row, never from a model's memory.

That choice follows from the corpus rather than from GraphRAG in general. Across 362 sampled broker reports, 59.7% of non-empty lines are markdown table rows, and roughly 60% of corpus tokens sit in SEC filings. A graph-first pipeline would spend its budget summarising the material that needs the least interpretation, namely tables whose printed cells are already harvested into 166 series files, and pay the most for the material that needs it least, namely broker commentary, which a hybrid index retrieves well once a reranker is applied.

The benchmarking evidence points the same way, and it is not a close call on this corpus. GraphRAG-Bench measures chunk-based retrieval with reranking at 60.92 on simple fact retrieval against the best graph system's 56.95; graph methods win by roughly 17 points on complex multi-hop reasoning and 13 on contextual summarisation, and they lose on creative generation [1]. A mid-2026 evaluation across three corpora concludes that cross-encoder reranking is the single most impactful component in the stack, that chunk pipelines dominate factoid retrieval, and that LightRAG's advantage is confined to creative and relational queries [2]. Separately, a financial-domain comparison of four retrieval strategies puts graph indexing at 100-500x vector RAG cost, roughly $37 and 12.8 hours against $0.23 and six minutes to index one FinanceBench corpus [3].

A second finding matters more than the architecture: the $145 is not the binding constraint. Measured token volumes priced against the model list in the brief put the one-time build at roughly $35 and the weekly update at about $0.41. The same corpus extracted end to end with a strong model costs about $610, which is more than the entire credit. That is what makes "scope discipline beats model quality" a quantitative claim rather than a slogan. Spending the whole $145 would be a mistake, because the reserve is worth more than the spend: it funds prompt iteration, a second higher-quality pass over the highest-value slice, and years of weekly updates.

The repository already contains `docs/GRAPHRAG_BUILD_PLAN.md`, written on 2026-11-01 around a $700 DeepSeek credit and a different model menu [4]. Its layering, a deterministic fact store, a hybrid text index, a thin quote-verified relation graph, and period summaries over a shared entity registry, is the right shape, and its list of things not to do is close to right. Three things have to change for the $145 router, and two assumptions in it are contradicted by the corpus as it actually stands. I set those out in section 1 rather than re-deriving the whole plan.

The six sections below map one to one onto the six questions in the brief [5].

## 1. Architecture and the rejected alternatives

### The three retrieval planes

**Plane A, numbers, deterministic, never through a model.** The corpus already contains most of this layer: 166 series CSVs holding 727,192 rows, each carrying a source file and an issue date, plus 5,371 per-report table sidecars. What the layer needs is a shape that fits what is actually there, and a census of all 166 CSV headers shows the `series/` directory is not one kind of thing. It holds tidy time series with an issue date, a series or route key, a value and a unit; flat event records that are the deal tables flattened, with columns such as NAME, TYPE, DWT, PRICE, BUYERS and SS; and specials including chart-derived spot rates, multi-source comparison files and pre-aggregated series carrying min and max columns.

Forcing all three into a single observation row would destroy provenance, so the fact plane holds two shapes. An observation is a number for a period, with the series, the period it describes, the value, the unit, the verbatim source cell, the provenance class, the document, the publication date, the ingestion date, the producing method, and a pointer to the observation it revises. A fact event is a deal-shaped record: a sale, a fixture, a demolition, a newbuilding order, with the vessel, the attributes printed in the row, and the same provenance fields. A weekly C5 rate is an observation, while "the Capesize Springbank, 177,066 dwt, sold to Greek buyers for $26.5m" is an event. Modelling them separately is what keeps the answer to "TD3C TCE in week 40 2025" exact and sourced while the answer to "who bought the biggest Capesize in Q3 2025" is still a fact rather than a guess.

SEC financials come from XBRL first, not from the markdown tables. The `companyfacts` API needs no key, returns each fact with its accession, form, filed date and fiscal period, and covers standard concepts for all 25 issuers. Shipping operating metrics such as TCE per day, fleet days, OPEX per day and utilisation are custom extension concepts and are not in `companyfacts`, so they are taken from the filing's XBRL instance, and only from the markdown tables where neither source carries them.

The agent never writes SQL across 727,192 rows. It queries named views that expose a route and week, a time-charter assessment, a fixture, a sale, a demolition, a newbuilding order, company financials, a commodity flow and a generic series, each row carrying the observation or event identifier. This is the mechanism behind the faithfulness requirement: the answer cannot cite a number it did not read from a view row.

**Plane B, evidence, hybrid retrieval with an LLM rerank.** Broker reports split on their headings, which they have. SEC filings do not have usable headings, which I measured and return to below. Every chunk carries a deterministic context prefix built from publisher, title, issue date, heading path and tagged entities, which costs no tokens and gives most of the benefit that a generated context prefix gives elsewhere. Tables are kept atomic in the fact plane, but for the embedding plane each table row is additionally emitted as one self-contained sentence using its column headers, because the dominant measured failure mode on the T2-RAGBench financial retrieval set is table structure mismatch at 73% of failures, where a query like "what was net income in 2019" cannot be matched to a row because the label and the value land in different cells [6]. Row-level normalisation is the fix the recent literature converges on: it lifts hybrid MRR from 0.358 to 0.595 and BM25-only recall at 1 from 0.366 to 0.754 on the structure-aware chunking benchmark [7], and the table-to-prose variant reports recall at 6 rising from 0.717 to 0.798 against fixed-size chunking of the same text [8].

Retrieval is BM25 and dense fused by reciprocal rank fusion, then reranked. BM25 is not optional here, because route codes such as TD3C, C5 and P1A_82, IMO numbers, tickers and vessel names are exact tokens that a dense vector blurs. In the pilot index built for this assessment, BM25 over SQLite FTS5 put the exact TD3C definition, the exact Springbank sale sentence and the correct Capesize resale matrix rows at the top of their respective queries. It also failed informatively on "Baltic Dry Index", returning a Newbuilding Index table, which is precisely the sense-ambiguity gap a reranker closes and that no amount of embedding tuning fixes.

**Plane C, relations, thin, temporal and quote-carrying.** Entities, aliases, edges, events and mentions, with a closed type vocabulary and a fixed schema. Every edge carries a verbatim quote of at most forty words, the chunk identifier, the document identifier, the interval during which the fact is true in the world, the date it was published, a confidence, a status, and the model and prompt version that produced it. An event is the n-ary case: port congestion, canal disruption, weather, labour strike, sanction, regulation, trade policy, production guidance, company guidance, casualty, newbuilding wave, demolition wave, or a market move.

Extraction is limited to prose and to chunks that pass a deterministic pre-filter, meaning the chunk contains a tagged entity or an event keyword. Tables never reach the model. The scope rule that follows from this, roughly 54% of all prose tokens, is what keeps the build inside the budget.

### The relation graph's role as join key and time axis

The graph is not the reasoning substrate in this design. Its three jobs are narrower and more valuable.

First, entity stitching across 23 publishers and 25 issuers that name the same thing differently. The repository already ships the seeds for this, and they are better than anything that would be built from scratch: a benchmark core fleet of 4,914 hulls with an IMO number on every record [9], a Baltic Exchange route taxonomy with 109 routes plus index formulas and baskets [10], a commodity and region normalisation map covering 81 commodity aliases and 624 region aliases [11], and a Fearnleys series-id registry with 34 time-bounded code mappings carrying evidence, including the TD3 to TD3C transition with a straddle flag and a discontinuation note [12]. That last file is the precedent for the whole alias design: a route code is a name that was true in an interval, not a permanent string.

Second, time-bounded state. Ownership changes, vessel renames, charter periods and delivery windows are relations with validity intervals, and the corpus spans 2004 to 2026 with weekly publication, so the interval is where the meaning lives.

Third, a citation surface. Every answer terminates in a set of identifiers that resolve to a path, a section and a quote.

The edge that does the most work is the mention edge, entity by document by time. "What every source said about one vessel" is a query that fans out over mentions, filters by date and publisher, and pulls the text from Plane B. It is not a traversal over OWNS and SOLD_TO. Building the relation graph as a reasoning engine would be a much more expensive design that produces worse answers on exactly the questions this corpus asks most.

### The query agent and the answer contract

The answering model gets five tools: SQL against the named views, hybrid search with filters, a graph tool for mentions, edges and events over an entity and a date window, a period-summary lookup, and a citation resolver. The agent loops until it can answer or until it decides it cannot.

The answer contract is enforced in code, not requested in the prompt. Every number in the final answer must be matched against a value returned by a tool, with unit and rounding tolerance, and a mismatch triggers one regeneration before the answer is downgraded to "not in the corpus". Every claim carries at least one identifier. An answer with an unmatched number is discarded, not hedged.

### Rejected architectures

The alternatives below were weighed against the constraints rather than dismissed generically.

| Option | Verdict | Reason |
|---|---|---|
| Microsoft GraphRAG, full, with community summaries | Rejected | Its own README says the project is largely in maintenance mode [23]; community summaries are unauditable prose with no citation obligation; index cost is 100-500x vector RAG [3]; and it would summarise tables, the exact failure this corpus already carries scars from |
| LightRAG as the backbone | Rejected | Its published win rates against GraphRAG are 49.6-54.8%, a narrow margin, and it is weaker on multi-hop than the sparse-graph alternative [27][1]. Its incremental-update lesson is worth taking, its extraction philosophy is not |
| LazyGraphRAG as the backbone | Partly adopted | Its core insight is right, that index-time LLM work is the expensive part, and Microsoft reports indexing at 0.1% of full GraphRAG cost [29]. But its open-source surface is partial: the NLP extraction function was open-sourced in graphrag 2.0.0 with no tutorial, and the team was still awaiting approval to release the full source in June 2025 [28]. It also answers global sensemaking questions that the period-summary tree handles here more cheaply and with citations attached |
| HippoRAG 2 personalised PageRank | Adopted as a primitive, not a framework | Personalised PageRank over a sparse entity graph is the strongest evidence-recall primitive for multi-hop: HippoRAG reaches 90.95% evidence recall on complex reasoning against 79.25% for HippoRAG 2, because PPR amplifies a few good edges while a dense graph accumulates noise [1]. Implement it over our own entity-chunk-event graph rather than adopting the pipeline |
| Graphiti and Zep | Adopted as a reference design | Its bi-temporal model, its treatment of episodes as the provenance substrate and its fact-invalidation discipline are the right shape for this corpus [31]. Not adopted as a dependency: it requires a graph database backend, its extraction philosophy is LLM-driven with fuzzy entity dedup, and it has no representation for a printed numeric fact with a source cell |
| Kuzu as the embedded graph store | Rejected | Archived on 10 October 2025 after an acquisition by Apple, with no further releases or security patches [24][25]. Fork lineage exists but carries no maintainer [26] |
| Neo4j, FalkorDB, HelixDB or ArcadeDB | Rejected for now | Each is a server to install, run and back up on an 8 GB Windows laptop, for a graph of tens of thousands of nodes and a few hundred thousand edges that edge tables and recursive CTEs handle |
| One extraction pass over the whole corpus | Rejected | Costs about $610 on a strong model, above the entire credit, and noisy triples measurably damage downstream faithfulness: with noisy triplets present, hallucination detectors lose 44-84% of their Matthews correlation, and only embedding-based detectors stay robust [30] |
| Postgres with pgvector as the primary store | Deferred, not rejected | Workable and capable, but it is a database server to install, upgrade and back up on the owner's machine. The data model stays portable, so this remains a migration rather than a rewrite |

Two things in that table generalise. Every graph framework on it is either in maintenance mode or is a server to operate, and every one of them treats extracted prose as the primary artefact, which is the wrong primary artefact for a corpus that is mostly printed tables.

### Differences from the existing build plan

Four substantive changes, plus one addition, each driven by a measurement rather than a preference.

The storage choice changes, because a single-owner machine with 8 GB of RAM and 40 GB of disk makes a server a tax rather than an asset. The cost model is re-derived for the $145 router and for the scoped extraction range, because the previous figures assumed a different provider, a different model menu and a larger extraction scope. The frontmatter contract is replaced with a per-publisher normaliser, because the assumed uniform contract does not exist for the broker corpus: across the 362 sampled reports, `source_file` appears in 359, `issue_date` in 315, and the publisher field is variously named `publisher` or `broker` in 268 of them between them, while `source_sha256`, `parser` and `parser_version` appear in none. The heading-based sectioning is replaced for SEC filings by a rule-based sectioner, because the filings have no headings to split on: a 1 MB VALE 20-F carries zero to one markdown headings and no `ITEM n.` markers at all, with the structure living instead in 327 standalone capitalised lines and 216 bold pseudo-headings. And every fact gains a provenance class, because at least one series in the corpus is chart-derived and therefore sits in tension with the house rule that charts are not converted into numbers [33].

One assumption in the previous plan deserves an explicit correction, because it changes the budget. Weekly-report cadence suggests heavy redundancy, and de-duplication is worth doing. It is not worth 40 to 60% of the extraction bill, though. Measured on the sample with numbers masked, which makes the estimate an upper bound, only 10.3% of prose paragraphs are near-identical to an earlier one at a Jaccard threshold of 0.9, and 12.5% at 0.6. The rate is wildly publisher-dependent, from 93.8% redundant at Agora and 61.1% at SSY down to 0% at Affinity, 0.8% at Banchero Costa and 0.5% at Poten. De-duplication therefore buys about a tenth of the prose cost and should be applied as a publisher-level optimisation rather than as a global assumption.

## 2. Tools, storage, and the operating envelope

### Storage layout

Three files, each with one job.

`kb_facts.duckdb` holds observations, fact events, the series catalogue, XBRL facts and the named views. DuckDB is a single file with no server, reads the 166 CSVs and the sidecar JSON directly, and is comfortable at this size. It is also the right tool for the analyst question the corpus invites, correlating fleet growth against time-charter rates across publishers, because that is SQL over a columnar store rather than a retrieval problem.

`kb_text.sqlite` holds documents, sections, chunks, the FTS5 lexical index, entities, aliases, edges, events, mentions, the LLM job ledger and the override table. FTS5 gives real BM25 through its `bm25()` ranking function, trigram tokenisation for fuzzy alias lookup, recursive CTEs for graph traversal, and incremental updates without a reindex. In the pilot, 362 documents produced 5,990 chunks in 1.0 second, about 373 documents per second in plain Python, and the resulting database projects to roughly 0.8 GB for the full broker corpus, so the complete lexical index including SEC filings lands in the low gigabytes.

`kb_vectors.npy` holds the dense embeddings as one fp16 matrix with an identifier mapping beside it.

Why not a graph database and why not Postgres: the graph here is small enough that adjacency queries over indexed edge tables with recursive CTEs are sufficient, and the operational simplicity of file-based stores matters more than query expressiveness for a one-person system. The upgrade path stays open because the schema, not the engine, holds the design. If concurrency or a second user ever arrives, Postgres and pgvector are a configuration change over the same tables.

### Model allocation across stages

Embeddings use Qwen3-Embedding-0.6B truncated through its native Matryoshka support to 384 dimensions and stored in fp16 [17]. The INT8 ONNX build is about 573 MB and runs without a PyTorch install [18]. Hosted, the whole corpus costs roughly $1.10 assuming a rate of about one cent per million tokens, which is a rounding error against the budget but should be re-priced at build time. The alternative is GitHub Actions, where standard runners on a public repository are free and unlimited, at 4 vCPU and 16 GB on `ubuntu-latest` with 14 GB of SSD, capped at 20 concurrent jobs and a six-hour job limit [13][14][15]. The path to avoid is embedding on the owner's laptop, where 80 to 110 million tokens at a few hundred tokens per second on a two-core i3 is a hundred hours and counting.

Reranking is bought with tokens rather than with the laptop's CPU. A local cross-encoder is available and small, with the INT8 AVX2 build of bge-reranker-v2-m3 at roughly 0.55 GB [16], but at 384 to 512 tokens per candidate it costs minutes per query on this hardware. Reranking 40 candidates with a cheap router model costs about 20,000 input tokens, on the order of two thousandths of a dollar per query. Since reranking is the component the literature identifies as most impactful [2], spending the router credit here is the highest-return use of the budget.

Per-stage model allocation follows from the prices in the brief. Extraction and reranking run on DeepSeek V4 Flash at 0.13/0.26 per million tokens or GPT-OSS 120B at 0.10/0.50, with the extraction pass costing $16 and $17 respectively against a measured scope. The hard tenth escalates to Nemotron 3 Ultra at $93 for that pass. Summarisation uses the cheap model for weekly and monthly nodes and a stronger model for the annual ones. One model serves each stage, chosen after the pilot measures schema compliance, and models are never mixed inside a pass because the cost ledger and the failure modes both become unreadable.

Structured output uses strict tool calling where the model supports it, otherwise JSON mode with schema validation and one repair attempt. The guarantee comes from the client-side acceptance gate, not from the model's compliance.

### Entity resolution

Resolution is probabilistic record linkage, not string similarity. Splink implements the Fellegi-Sunter model and links a million records on a laptop in about a minute on a DuckDB backend, with Splink 5 released in September 2026 [21][22]. Blocking is the first phase and it is where the quality is decided: blocking on last name alone was not viable in a comparable exercise, while adding another attribute reduced comparisons without losing true matches, and blocking for prediction and blocking for parameter estimation are different jobs that need separate passes.

For vessels, the comparison fields are normalised name, deadweight within about two percent, built year, yard and owner, with IMO as the decisive key where both sides carry one. For companies, name, ticker, country and role, with CIK decisive. Auto-merge requires a high probability and IMO or CIK agreement wherever both records have one; the middle band goes to a cached LLM adjudication call returning same, different or unsure with a reason, and unsure stays unmerged. Name similarity alone never merges, which is the specific failure the corpus invites: "Greek (Kassian Maritime)" is a nationality plus a company name, not a company identifier, and "UAE based" is a country tag. Every merge records who merged it, so it can be undone.

## 3. Cost and schedule

### Token budget and price sensitivity

The scope that reaches the model is books in full at 2.8 million tokens, SEC narrative after boilerplate and table removal and de-duplication at about 14.5 million, and broker prose after the entity and event pre-filter at about 16.2 million. That is 33.5 million tokens, or 54% of all prose in the corpus, and it excludes every table cell.

At 1,500 tokens per chunk with a 2,500-token static system prompt and about 700 tokens of output per call, the full extraction pass is roughly 22,300 calls. The stage costs below are priced at DeepSeek V4 Flash rates with no prompt caching.

| Stage | Volume | Cost |
|---|---|---|
| Extraction pass, 33.5M tokens in scope | 22,300 calls | $16.03 |
| Gleaning pass on 25% of chunks | 5,600 calls | $4.01 |
| Escalation to Nemotron 3 Ultra on 10% of chunks | 2,200 calls | $9.28 |
| Entity adjudication, 15,000 short calls | 15,000 calls | $0.53 |
| Period summaries, week leaf to year | 3,000 calls | $1.17 |
| Table header classification for unknown layouts | 400 calls | $0.07 |
| Pilot and three prompt iterations | 3,600 calls | $2.58 |
| Gold-set evaluation, 300 questions | 300 calls | $0.58 |
| Embeddings, hosted, 111.5M tokens | n/a | $1.11 |
| **One-time build** | | **$35** |

The shape of that table is the argument rather than its total. Extraction is less than half the bill, escalation and the gleaning pass are another third between them, and everything else is rounding. Three levers move it, all measured rather than assumed. Prefix caching on the static prompt is worth about a fifth, because cache reads typically bill at 0.1x to 0.5x of the input price [19]. A batch endpoint halves the remainder, since batch pricing is typically half of the synchronous rate [20]. And moving the whole corpus through a stronger model is the failure mode: the extraction pass alone costs $183 on DeepSeek V4 Pro and $198 on GLM 5.3, and the same 111.5 million tokens extracted end to end come to about $610 on DeepSeek V4 Pro against $57 on GPT-OSS 120B. The reserve of roughly $110 against the $145 credit is the point of the design, not a leftover.

The weekly update runs on the same machinery: about 300 new broker reports and 40 new filings, roughly 550 extraction calls, about $0.41 and a few minutes of CI wall clock.

### Wall-clock schedule

Engineering effort, not token spend, is the real constraint. The fact plane and the SEC sectioner are the long poles and cost nothing in tokens.

The first two weeks go to the inventory and the frontmatter normaliser, then to loading the 166 CSVs and 5,371 sidecars into the fact plane and wiring the named views. The third week is the SEC sectioner and the XBRL loader, which together are worth more than anything the LLM can do here. The fourth week is entity resolution, the chunker, the FTS5 index and the dense index. The fifth week is the extraction prompt and its pilot, the only genuinely uncertain part, which deserves to be the loop that eats slack. The sixth week is the full extraction run, roughly 22,300 calls and about half a day of CI wall clock across 20 concurrent jobs, fully resumable. The seventh and eighth weeks cover summaries, the agent, the answer contract and the evaluation harness. Three to five weeks of one person's time is a realistic estimate, with roughly 40% of it in the fact plane and the SEC sectioner.

## 4. Incremental ingestion and correction

### Change detection and idempotency

Identity is content-addressed throughout. The document identifier is the SHA-256 of the markdown bytes, the chunk identifier is the SHA-256 of the normalised body, and the event identifier is a hash of its type, endpoints, validity start and document. This matters more than it looks, because the corpus's own ledger records that live extractors lag behind the repaired stored markdown, with a documented regression in which new Star Asia issues arrived with dropped tables and every anchorage row mislabelled [32]. The consequence for the knowledge base is a rule: the markdown file is the artifact of record, and the pipeline never re-derives text from the PDF.

Change detection is git. The existing workflows already commit new material on a schedule, with report ingest running three times on weekdays and separate weekly, daily and monthly jobs, so the knowledge-base pipeline runs downstream of a commit and diffs the tree against the previous build. Counting files is not a valid trigger, since the brief, the ledger and the live tree already disagree with each other, with the broker count given as 19,329 in one place and 19,326 in another, and the SEC count as 1,364 in one place and 1,346 in another. Hashes do not drift.

Each artefact carries its own cache. Embeddings are keyed by model version and chunk hash, LLM responses are keyed by chunk hash, prompt version and model in a SQLite job ledger, and summaries are keyed by segment, granularity, period and the hash of their inputs. The consequences are the ones that matter operationally: a prompt change costs only the changed chunks, an interrupted run resumes without repeating a call, and a full re-run against an unchanged tree costs nothing and changes no rows. That last property should be asserted in CI.

### Revisions and the two time axes

Two clocks have to be kept apart. Valid time is when a fact was true in the world. Knowledge time is when the corpus learned it. A broker that restates last week's rate is not an error, it is a new observation with a later publication date. Nothing is overwritten: a revision is a new row pointing at the row it revises, and a query defaults to the latest known value while an "as known on" query filters by the knowledge clock and replays what was known on a given date. This is the same discipline Graphiti applies to its temporal edges, and it is what makes a twenty-year question answerable without rewriting history [31].

Relative dates are resolved in code from the publication date, never by the model. "A week ago", "last week" and "the start of this year" are arithmetic against the document date, because a model that resolves them hallucinates them.

### Correcting a wrong extraction

A wrong extraction is corrected without a rebuild, because the record was never the evidence. Every extracted edge carries its verbatim quote, the chunk and document identifiers, the raw model response, a confidence, and a status of active, superseded or rejected. The quote is checked against the chunk at write time, and a record whose quote is not a substring of the chunk, or whose printed numbers are not inside the quote, is never written.

Three correction paths exist. A rejection is a versioned override file in git, one line per identifier, and the next query simply does not return it. A correction of an extracted value re-runs the acceptance gate against the stored raw response, which costs nothing because the response was already paid for. A change of model or prompt version produces a new generation of records, with the previous generation marked superseded rather than deleted. When a record changes, only the period summaries that consumed it are regenerated, because a summary's cache key includes the hash of its inputs. The summaries form a time tree, week to month to quarter to year, and a new week leaf regenerates its ancestors and nothing else.

## 5. Evaluation and acceptance thresholds

### The gold set

The gold set is written before the build, not after, and it is written from the corpus rather than borrowed. Public benchmarks are informative but cannot serve as acceptance criteria: a 2026 analysis of the two main text-to-SQL benchmarks found annotation error rates of 52.8% in BIRD Mini-Dev and 66.1% in Spider 2.0-Snow [34].

The set is about 250 questions, each with the expected answer and the identifiers of the expected sources, stratified across the question families the brief names: a single number with its source, a window aggregate, a multi-hop entity question, an event-to-market question, a filing against broker commentary, a long-horizon structural question from the books, and roughly 25 questions that are unanswerable or out of range and must be refused. A synthetic regression set is generated from observations and edges with known answers, which is unlimited and catches breakage after every schema change. Twenty percent of the gold set is held out so the thresholds are not fitted to the questions used to tune them.

Two further points on measurement. Time-series questions are answered by SQL, and the text-to-SQL literature is sobering about how hard that is on non-relational sources: converting time-series databases to relational form raised execution accuracy from zero to 32.21%, and the best evaluated model still reached only 48.98% against a human 87.34% [35]. The mitigation is structural rather than clever, which is why the named views in Plane A exist. And retrieval quality is measured separately from answer quality, following the three-stage approach of separating context selection from synthesis [1], because a failure to retrieve and a failure to synthesise need different fixes.

### Metrics and thresholds

Good enough means all of the following, and the first group is about retrieval and answers.

- Exact match with unit on single-value lookups at 95% or better, and 90% or better on window aggregates.
- Retrieval recall at 20 of 0.85 and nDCG at 10 of 0.70, measured against gold evidence rather than against the answers.
- Multi-hop entity F1 at 0.75 or better.
- Citation coverage at 95% of claims, and a hard zero tolerance for numeric claims that do not appear in a tool row.

The second group is about whether the system is honest under pressure.

- Refusal accuracy at 90% or better on the unanswerable set.
- A blind human audit of 200 random answers showing no unsupported numeric claim, and a wrong-fact rate at or below 3% on sampled extracted records.
- p95 latency under 60 seconds and cost per question under one cent.

The single sharpest test is the one to state out loud: if a numeric question is answered from the model rather than from a fact row, that is a failure even when the number happens to be right. A system that answers "TD3C TCE in week 40 2025" from memory is exactly the failure this corpus has already paid for once.

The pilot gate sits before the full run and can stop it. On 500 stratified chunks: schema validity at 98% or better, quote verification at 90% or better of records, numbers inside quotes at 95% or better, wrong-fact rate at or below 3% on 100 hand-checked records, cache-hit ratio on the static prefix as designed, and measured cost per thousand chunks multiplied by the projected scope inside the budget. The gold-set slice answered by the fact plane alone must reach 95% exact before any LLM work is commissioned.

## 6. Risks, non-goals, and the first three weeks

The table below lists the risks that would actually end this project, with the mitigation each one implies.

| Risk | What it breaks | Mitigation |
|---|---|---|
| An unscoped extraction pass | The budget, and the run's credibility | Scope rule at 54% of prose, a hard cap in the runner, the job ledger making re-runs free |
| The router closes sign-ups mid-build | The reserve and the update path | Front-load the build, keep every call behind an OpenAI-compatible client with a per-stage model map, and move the weekly path to another provider if needed |
| Live extractors regress against the repaired markdown | The evidence plane silently | The markdown file is the artifact of record, the pipeline never re-parses PDFs, and a changed file triggers a hash delta rather than an overwrite [32] |
| Vessel and company merge errors | Ownership and sale facts | IMO and CIK gating, Splink thresholds, undoable aliases, a precision gate at 0.98 on 300 hand-checked merges, and no name-only merges |
| Publication time, period, laycan and delivery conflated | Every temporal answer | Separate columns, relative dates resolved in code, and an explicit knowledge-time filter |
| Noisy graph triples | Faithfulness downstream | Quote-gated edges only, low density, a status field, and the measured 44-84% Matthews correlation degradation as the reason to keep the graph thin [30] |
| Table facts unreachable through retrieval | Any numeric question in a table | Row-level prose for the embedding plane, cells retained in the fact plane, and the named views as the primary route for table questions [6][7] |
| The laptop as the only machine | Throughput and memory | Heavy work runs in CI, where public-repository standard runners are free and unlimited [13], and the laptop only queries |
| Copyrighted books in a public repository | Legal exposure | The ledger records this as pending [32]; decide before indexing, and keep book embeddings and excerpts out of any public artefact if the books stay in |

The pattern across that table is that the dangerous failures are silent ones. Every one of them is caught by a validator rather than by an alert, which is what "operation must be simple and self-checking" has to mean in practice.

Two non-goals are worth stating because they are the tempting failures. The first is letting a framework own the data. Whether that is Microsoft GraphRAG, LightRAG, Graphiti or a hand-rolled pipeline, the canonical facts, evidence and relations must live in our own schema so that any of them can be replaced by a view. The second is letting a model produce a number. Tables are parsed deterministically, cells are stored verbatim, the model classifies a table layout once and never reads its cells, and chart imagery is never converted into data.

For the first three weeks I would do, in order: the frontmatter normaliser and the inventory, because every later stage keys off it; the fact plane loaded from the 166 CSVs and 5,371 sidecars with the named views working, because it answers most numeric questions at zero marginal cost; and the SEC sectioner, because the filings are roughly 60% of corpus tokens and have no headings to split on. The extraction prompt gets written in week four, against a pilot that can still be stopped cheaply.

The overall judgment is that this corpus rewards a system that is precise about numbers, careful about time, and modest about what a graph is for. The graph earns its place by stitching entities across 23 publishers and holding validity intervals. It does not earn the right to be the reasoning engine. The budget is sufficient and the discipline is what matters.

## References

[1] GraphRAG-Bench evaluation detail, including the 60.92 against 56.95 fact-retrieval comparison and HippoRAG evidence recall — https://huggingface.co/datasets/quantellence/public_ai_memory_slice/blob/main/datasets/public_ai_memory/papers/25_graphrag_bench.md

[2] "When Does GraphRAG Pay Off?", cross-corpus evaluation concluding that cross-encoder reranking is the single most impactful component — https://lup.lub.lu.se/luur/download?func=downloadFile&recordOId=9239602&fileOId=9239606

[3] "Benchmarking Graph-Based RAGs in the Financial Domain", reporting the 100-500x indexing cost gap — https://github.com/thomasbordes804/graph-based-rag-for-finance

[4] GRAPHRAG_BUILD_PLAN.md in the Shipping repository, written 2026-11-01 around a $700 DeepSeek credit — https://github.com/yieldchaser/Shipping/blob/main/docs/GRAPHRAG_BUILD_PLAN.md

[5] GRAPHRAG_BRIEF.md in the Shipping repository — https://github.com/yieldchaser/Shipping/blob/main/docs/GRAPHRAG_BRIEF.md

[6] "From BM25 to Corrective RAG", T2-RAGBench evaluation, table structure mismatch as 73% of failures — https://arxiv.org/html/2604.01733

[7] "Structure-Aware Chunking for Tabular Data in Retrieval-Augmented Generation", hybrid MRR from 0.358 to 0.595 — https://arxiv.org/html/2605.00318v1

[8] D-RAC, table-to-prose normalisation and retrieval gains on multi-format corpora — https://arxiv.org/html/2609.24220v1

[9] data/reference/benchmark_core_fleet.json, 4,914 IMO-keyed hulls — https://github.com/yieldchaser/Shipping/blob/main/data/reference/benchmark_core_fleet.json

[10] data/reference/baltic_route_taxonomy.json, 109 routes with index formulas and baskets — https://github.com/yieldchaser/Shipping/blob/main/data/reference/baltic_route_taxonomy.json

[11] data/reference/commodity_normalisation.json, 81 commodity aliases and 624 region aliases — https://github.com/yieldchaser/Shipping/blob/main/data/reference/commodity_normalisation.json

[12] data/reference/fearnleys_tsid_registry.json, time-bounded route-code mappings with evidence — https://github.com/yieldchaser/Shipping/blob/main/data/reference/fearnleys_tsid_registry.json

[13] GitHub Actions billing: standard runners in public repositories are free — https://docs.github.com/en/billing/concepts/product-billing/github-actions

[14] GitHub-hosted runners reference: 4 vCPU, 16 GB RAM, 14 GB SSD on ubuntu-latest — https://docs.github.com/en/actions/reference/runners/github-hosted-runners

[15] GitHub Actions usage limits: 20 concurrent jobs on the Free plan and a 6-hour job cap — https://docs.github.com/en/actions/reference/limits

[16] bge-reranker-v2-m3 INT8 ONNX AVX2 build, about 0.55 GB — https://huggingface.co/kftof/bge-reranker-v2-m3-onnx-int8-avx2

[17] Qwen3-Embedding model family, including 0.6B size, 1024 dimensions and Matryoshka truncation — https://github.com/QwenLM/Qwen3-Embedding

[18] qwen3-embed, ONNX and GGUF embedding and reranking without a PyTorch dependency — https://pypi.org/project/qwen3-embed/1.8.0/

[19] OpenRouter prompt caching: cache reads at 0.1x to 0.5x of input price — https://openrouter.ai/docs/guides/best-practices/prompt-caching

[20] OpenRouter Batch API: typically 50% of synchronous per-token price — https://openrouter.ai/docs/guides/features/batch-api

[21] Splink documentation: Fellegi-Sunter linkage, DuckDB backend and million-record scale on a laptop — https://moj-analytical-services.github.io/splink/index.html

[22] "Same Person, Five Records", record linkage practice, blocking for prediction versus estimation, Splink 5 — https://m-clark.github.io/posts/2026-11-05-identity-resolution/

[23] microsoft/graphrag repository README, describing the project as largely in maintenance mode — https://github.com/microsoft/graphrag

[24] Kuzu repository, archived 10 October 2025 — https://github.com/kuzudb/kuzu

[25] "KuzuDB graph database abandoned, community mulls options", The Register — https://www.theregister.com/software/2025/10/14/kuzudb-graph-database-abandoned-community-mulls-options/1142229

[26] "Open Source Knowledge Graph and GraphRAG Databases Compared", 2026, including FalkorDB lineage — https://arcadedb.com/blog/open-source-knowledge-graph-graphrag-databases-compared/

[27] LightRAG paper summary with the 49.6-54.8% win rates against GraphRAG — https://huggingface.co/datasets/quantellence/public_ai_memory_slice/raw/main/datasets/public_ai_memory/papers/29_lightrag.md

[28] microsoft/graphrag issue #1935, LazyGraphRAG source awaiting release approval — https://github.com/microsoft/graphrag/issues/1935

[29] "LazyGraphRAG: Setting a new standard for quality and cost" — https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/

[30] FinReflectKG HalluBench, hallucination detection over KG-augmented SEC 10-K QA and the effect of noisy triplets — https://arxiv.org/html/2603.20252v1

[31] Graphiti documentation: bi-temporal model, episodes as provenance and hybrid retrieval — https://help.getzep.com/graphiti/getting-started/overview

[32] PRE_GRAPHRAG_OPEN_ITEMS.md, the corpus data-quality ledger — https://github.com/yieldchaser/Shipping/blob/main/docs/PRE_GRAPHRAG_OPEN_ITEMS.md

[33] data/extracted/series/gibson_spot_chart_daily.csv, a chart-derived series — https://github.com/yieldchaser/Shipping/blob/main/data/extracted/series/gibson_spot_chart_daily.csv

[34] "Text-to-SQL Benchmarks are Broken: An In-Depth Analysis", CIDR 2026, annotation error rates of 52.8% and 66.1% — https://www.cidrdb.org/cidr2026/papers/p5-jin.pdf

[35] TQTS-Bench, text-to-query over time-series databases, and the 0% to 32.21% gain from relational conversion — https://arxiv.org/html/2609.34783v1
