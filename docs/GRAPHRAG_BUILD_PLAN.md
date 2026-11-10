# Maritime knowledge base: GraphRAG build plan (v2, 2026-11-08)

Version 2. It replaces the 2026-11-01 plan, which assumed a $700 DeepSeek credit and PostgreSQL. What changed:

- The budget is now **about $145 of credit on one OpenAI-compatible router**, and router sign-ups are closed.
- The build machine is an **8 GB RAM laptop**.
- Six independent design reviews were read in full (`docs/Recommendations/`, written against `docs/GRAPHRAG_BRIEF.md`). This plan keeps their good ideas and rejects the rest; see §16.

The executable instructions for the agent that builds this are in `docs/GRAPHRAG_AGENT_TASK.md`. This file is the design; that file is the procedure.

---

## 0. Decisions (read first)

| # | Decision | Why |
|---|---|---|
| D1 | **Own Python pipeline, no GraphRAG framework** (no Microsoft GraphRAG, no LightRAG ingest, no LlamaIndex/LangGraph). | Every reviewer agreed on what to reject: full MS GraphRAG costs too much and its communities must be rebuilt on every update. LightRAG's generic extraction prompts invent entities and cannot keep table cells exact. The useful parts are each about 100 lines of our own code: closed ontology, quote gates, entity registry, PPR, and the time tree. |
| D2 | **Three layers.** A = exact facts with no LLM (series CSVs, XBRL, parsed tables). B = hybrid text index (BM25 + dense + reranker). C = event/state graph extracted by an LLM from prose only, quote-verified. Plus the entity registry and period summaries. | Numbers never pass through an LLM. The LLM budget goes only to prose, which is the only place it adds anything. |
| D3 | **Embedded, file-based storage with no server.** DuckDB for facts, documents, registry, graph and summaries. SQLite FTS5 for BM25. fp16 `.npy` vector shards, memory-mapped, searched exactly. A SQLite job ledger. | On 8 GB of RAM, Postgres with an HNSW index competes with the extraction run for memory. The whole corpus produces fewer than 400k chunks, so an exact cosine scan over memory-mapped fp16 vectors (about 0.8 GB on disk) takes well under a second. It has no approximation error and needs no index to maintain. |
| D4 | **Heavy compute goes to free machines, not the laptop.** Embedding runs as a GitHub Actions matrix (public repos get free standard runners). LLM calls are I/O-bound, so the laptop drives them asynchronously while using almost no RAM. | Embedding about 70M tokens on an i3 CPU would take days; 20 parallel runner jobs take hours. |
| D5 | **Every LLM call goes through one provider-agnostic runner** (`kb/llm_runner.py`). It reads `ROUTER_BASE_URL` and `ROUTER_API_KEY` from the environment and the model per pass from `kb/config.yaml`. | Router credit is finite and cannot be topped up. The incremental path must be able to switch to any OpenAI-compatible provider by changing configuration only. |
| D6 | **The model is chosen by measurement, not by reputation.** A bake-off on a hand-checked extraction set picks the bulk extractor, the escalation model and the judge (§10). | Prices and quality on the router are unverified claims until measured. |
| D7 | **The LLM cites sentences; code makes the quotes.** Each prose chunk is split into numbered sentences, and the model returns sentence ids, not quote text (§7). | Quotes are verbatim by construction and output tokens fall. The number gate then checks the cited sentences. |
| D8 | **Identity comes from keys, never from names.** IMO for vessels, CIK/LEI for companies, the Baltic code for routes, UN/LOCODE for ports. A name alone never creates or merges a vessel. | Name collisions over 20+ years and 23 publishers are certain. |
| D9 | **Deals are deduplicated into canonical transactions.** One S&P sale reported by six brokers over three weeks is one `transaction` with six `mention`s. Conflicting prices are kept as separate claims. | Without this, counts and "who bought the most" questions are wrong. |
| D10 | **Known gaps are data.** A `corpus_known_gaps` table records them, and the agent answers "the corpus has a gap here" instead of guessing or saying "did not happen". | Several series stop early (partner-country shares end at 2026-08), and publishers have missing weeks. |
| D11 | **The coding agent is DeepSeek Harness (dsh), and its calls go through `tools/agent_gateway/`.** The **main agent** uses Enclave `cyberouter/deepseek-v4-pro` (reasoning) first, with a hard $60 cap enforced by the gateway (raised from $45 by the owner on 2026-11-10), not by the agent. **Subagents** (at most 4) use the free Ultrafast DeepSeek V4.1 Flash queue with thinking on. Each side falls back to the other. The pipeline runner gets $82; $3 covers overshoot. Enclave credit may expire (the service may shut down), so it is spent on quality early, never hoarded. The pipeline itself runs as plain Python, so the agent's own tokens go to writing and fixing code, not to watching long runs. | The owner decided (2026-11-08) not to use a Claude subscription for this. The router is the only credit available, so the split must be explicit, or the agent's own tokens eat the extraction budget. |
| D12 | **Book content stays out of every public artifact.** Books are indexed in the local knowledge base only. Their chunks, quotes and summaries are never committed and never published to a GitHub Release. | The repo is public and the books are copyrighted. Whether the book MDs themselves stay in the repo is still an open owner decision (ledger). |

---

## 1. Inputs and readiness (measured 2026-11-08)

### 1.1 What goes in

| Input | Path | Size | Notes |
|---|---|---|---|
| Broker MDs | `data/extracted/md/**` | 19,329 MDs, 149 MB | 23 publishers. Table share 32%. Prose ≈ 27.3M tokens, of which **19.3M are unique** after exact-duplicate removal with numbers masked (weekly reports repeat last week's text). |
| SEC filings | `corpus/10-companies/**` | 1,364 MDs, 247 MB | 10-K/10-Q/20-F/6-K/8-K. Table share 16%. Prose ≈ 48.8M tokens, **29.5M unique** (20-F 34.4M→20.5M, 6-K 7.9M→5.5M, 10-K 4.2M→2.3M). |
| Books | `corpus/**` (book folders) | 12 MDs, 10 MB | Prose ≈ 2M tokens. Local only (D12). |
| Table sidecars | `**/*.tables.json` | 6,142 files | Structured cells with row and column positions. |
| Series | `data/extracted/series/`, `data/commodities/`, `data/derived/` | 166 CSVs, 727,192 rows | Long format, already joined. |
| Reference seeds | `data/reference/` | | `benchmark_core_fleet.json` (4,914 IMO hulls), `baltic_route_taxonomy.json`, `commodity_normalisation.json`, `fearnleys_tsid_registry.json`, `signal_orderbook_status_map.json`, `fearnpulse_*`. |
| Cadence and gaps | `docs/CORPUS_REGISTRY_AND_CADENCE_AUDIT.md`, `docs/PRE_GRAPHRAG_OPEN_ITEMS.md` | | Seeds for `corpus_known_gaps`. |

Unique prose to extract from is therefore about **51M tokens** (19.3 + 29.5 + 2), not 111M. Removing SEC boilerplate in P0 shrinks it further (§5.1).

### 1.2 Frontmatter is inconsistent, so it is normalised first

Of the 19,329 broker MDs:

| Field | MDs that have it |
|---|---|
| `issue_date` | 8,722 |
| `publisher` | 5,804 |
| `source_file` | 14,527 |
| `broker` | 1,301 |
| `source_sha256` | 1,070 |
| `parser` | 1,070 |
| `parser_version` | 260 |

P0.5 writes a **per-publisher frontmatter normaliser**. It does not edit the MDs; it outputs canonical `document` rows. Each row gets `publisher_id`, `doc_type`, `published_at` and `date_source` (frontmatter | filename | registry | folder), plus `period_hint`, `source_file` and `source_sha256` (computed from the source file if present, else null). Every row must get a date: readiness item R4 already proved that a date can be parsed for every MD.

### 1.3 Readiness checklist

R1–R7 in `kb/reports/p0_inventory.json` all PASS (2026-11-08). The build re-runs `kb/p0_inventory.py` at the start and stops if any item fails.

---

## 2. Architecture

```
            ┌──────────── inputs (read-only) ──────────────┐
            │ MDs · tables.json · series CSVs · ref seeds  │
            └──────┬──────────────┬──────────────┬─────────┘
   P0/P0.5 inventory+normalise    │              │
            ▼                     ▼              ▼
   document/section rows    Layer A facts   Registry seed
   (DuckDB)                 (DuckDB: obs,   (IMO, CIK, routes,
            │               transactions,    ports, commodities)
            ▼               known_gaps)            │
   chunks + sentence ids ───────────┐              │
   (DuckDB) │                       │              │
            ├─► BM25 (SQLite FTS5)  │              │
            ├─► embeddings (GH Actions matrix → fp16 .npy shards)
            ▼                                      │
   Layer C extraction (router, async, ledger) ─► gates ─► resolution (Splink, keys)
            │                                      │
            ▼                                      ▼
   edges / events / mentions (bitemporal, quote = code-sliced sentences)
            │
            ▼
   period summaries (time tree, cite-or-drop)
            │
            ▼
   query agent: sql · search · graph · ppr · summary · gaps · cite   (+ answer post-check)
```

All state lives in `kb/state/` (git-ignored):

- `kb.duckdb`
- `fts.sqlite`
- `vec/*.npy` plus `vec/ids.parquet`
- `ledger.sqlite`
- `raw/*.jsonl.zst` (every raw LLM response)

Everything except `raw/` and `ledger.sqlite` can be rebuilt from the inputs plus `raw/` without paying for an LLM call again.

**RAM discipline (8 GB):**

- DuckDB runs with `SET memory_limit='2GB'` and `SET temp_directory='kb/state/tmp'`.
- Every pass streams file by file and never loads the corpus at once.
- Vector search uses `np.load(mmap_mode='r')`.
- PPR uses a `scipy.sparse` CSR matrix of fewer than 5M edges (under 100 MB).
- Splink uses its DuckDB backend with blocking rules, so pair counts stay small.
- No local LLM, and no server process of any kind.

---

## 3. Data model (DuckDB)

DuckDB has no `daterange` type, so intervals are stored as `*_from`/`*_to` date pairs. `JSON` replaces `jsonb` and `VARCHAR[]` replaces `text[]`. The DDL below is the contract; names can be adjusted once, before P1.

```sql
-- documents ---------------------------------------------------------------
CREATE TABLE document (
  doc_id VARCHAR PRIMARY KEY,         -- first 16 hex of sha256(MD bytes)
  path VARCHAR UNIQUE NOT NULL, source_file VARCHAR, source_sha256 VARCHAR,
  publisher_id VARCHAR NOT NULL, doc_type VARCHAR NOT NULL,   -- broker_weekly|broker_daily|broker_monthly|sec_10k|sec_20f|sec_6k|sec_10q|sec_8k|book
  title VARCHAR, published_at DATE NOT NULL, date_source VARCHAR NOT NULL,
  period_from DATE, period_to DATE, company_id VARCHAR,
  public_ok BOOLEAN NOT NULL,         -- false for books (D12)
  frontmatter JSON, parser_version VARCHAR, ingested_at TIMESTAMP DEFAULT now());
CREATE TABLE section (section_id VARCHAR PRIMARY KEY, doc_id VARCHAR, ord INT,
  heading_path VARCHAR[], kind VARCHAR,   -- prose|table|list|boilerplate
  sec_item VARCHAR,                       -- SEC: item_1|item_4|item_5|item_7|item_3d|press_release|...
  sha256 VARCHAR, tokens INT);
CREATE TABLE chunk (chunk_id VARCHAR PRIMARY KEY, doc_id VARCHAR, section_id VARCHAR, ord INT,
  kind VARCHAR, context_prefix VARCHAR, body VARCHAR, tokens INT, sha256 VARCHAR,
  norm_sha VARCHAR,                       -- sha of normalised body (numbers masked)
  is_duplicate_of VARCHAR, entity_ids VARCHAR[], vec_row INT, extract BOOLEAN);
CREATE TABLE sentence (chunk_id VARCHAR, sid INT, start_char INT, end_char INT,
  PRIMARY KEY (chunk_id, sid));           -- offsets into chunk.body (D7)

-- registry ------------------------------------------------------------------
CREATE TABLE entity (entity_id VARCHAR PRIMARY KEY,   -- vessel:imo9xxxxxx | vessel:prov:<hash> | company:cik0001577437 | company:int:<slug> | port:CNQDG | route:C5 | commodity:iron_ore | country:GR
  type VARCHAR NOT NULL, canonical_name VARCHAR NOT NULL, attrs JSON, status VARCHAR,  -- confirmed|provisional
  created_by VARCHAR NOT NULL);
CREATE TABLE alias (alias VARCHAR, alias_norm VARCHAR, entity_id VARCHAR, source VARCHAR,
  confidence REAL, merged_by VARCHAR, valid_from DATE, valid_to DATE,   -- names get reused: aliases can be time-bound
  PRIMARY KEY (alias_norm, entity_id));
CREATE TABLE merge_log (run VARCHAR, a VARCHAR, b VARCHAR, decision VARCHAR, method VARCHAR,
  score REAL, evidence JSON, at TIMESTAMP);    -- every merge can be undone

-- layer A: observations (bitemporal) ------------------------------------------
CREATE TABLE series (series_id VARCHAR PRIMARY KEY, name VARCHAR, unit VARCHAR, currency VARCHAR,
  basis VARCHAR, frequency VARCHAR, entity_ids VARCHAR[], source_csv VARCHAR, definition JSON);
CREATE TABLE observation (obs_id BIGINT PRIMARY KEY, series_id VARCHAR,
  period_from DATE NOT NULL, period_to DATE NOT NULL,        -- VALID time
  value DOUBLE NOT NULL, unit VARCHAR, raw_cell VARCHAR NOT NULL,
  doc_id VARCHAR, table_ord INT, row_ord INT, col_ord INT,
  published_at DATE NOT NULL, ingested_at TIMESTAMP DEFAULT now(),   -- KNOWLEDGE time
  method VARCHAR NOT NULL,                 -- csv:<file> | xbrl:<accn> | parser:<name>@<ver>
  provenance VARCHAR NOT NULL,             -- reported_table | xbrl | parser_text | computed | chart_derived
  supersedes BIGINT);
-- chart_derived rows (e.g. gibson_spot_chart_daily.csv) are excluded from answers unless asked for explicitly.

-- layer A: canonical deals (D9) ------------------------------------------------
CREATE TABLE transaction (txn_id VARCHAR PRIMARY KEY, kind VARCHAR,  -- sale|demolition|newbuild_order|time_charter|fixture
  vessel_id VARCHAR, counterparties JSON, date_from DATE, date_to DATE,
  terms JSON,                              -- consensus values with the claims behind each one
  status VARCHAR);                         -- reported|conflicting|retracted
CREATE TABLE mention (txn_id VARCHAR, doc_id VARCHAR, table_ord INT, row_ord INT, chunk_id VARCHAR,
  sids INT[], published_at DATE, claimed JSON);   -- what this source said, as printed

-- layer C: state facts and events -------------------------------------------------
CREATE TABLE edge (edge_id VARCHAR PRIMARY KEY, type VARCHAR NOT NULL, src VARCHAR, dst VARCHAR,
  attrs_printed JSON, attrs JSON, valid_from DATE, valid_to DATE,
  published_at DATE NOT NULL, doc_id VARCHAR, chunk_id VARCHAR, sids INT[], quote VARCHAR NOT NULL,
  extractor VARCHAR NOT NULL, confidence REAL, status VARCHAR DEFAULT 'active');   -- active|superseded|rejected
CREATE TABLE event (event_id VARCHAR PRIMARY KEY, type VARCHAR, summary VARCHAR,
  occurred_from DATE, occurred_to DATE, published_at DATE, location VARCHAR, magnitude_printed VARCHAR,
  doc_id VARCHAR, chunk_id VARCHAR, sids INT[], quote VARCHAR NOT NULL, extractor VARCHAR, confidence REAL);
CREATE TABLE event_role (event_id VARCHAR, role VARCHAR, entity_id VARCHAR);
CREATE TABLE claim (claim_id VARCHAR PRIMARY KEY, kind VARCHAR,   -- forecast|view|causal
  subject_ids VARCHAR[], text_printed VARCHAR, horizon VARCHAR, direction VARCHAR,
  published_at DATE, doc_id VARCHAR, chunk_id VARCHAR, sids INT[], quote VARCHAR NOT NULL,
  extractor VARCHAR, confidence REAL);

-- gaps, summaries, meta ----------------------------------------------------------------
CREATE TABLE corpus_known_gaps (scope VARCHAR, key VARCHAR, gap_from DATE, gap_to DATE,
  reason VARCHAR, source VARCHAR);         -- e.g. ('series','partner_usd_share','2026-09-01',NULL,'source stops','PRE_GRAPHRAG_OPEN_ITEMS')
CREATE TABLE period_summary (segment VARCHAR, grain VARCHAR, period_from DATE, period_to DATE,
  summary VARCHAR, cited_ids VARCHAR[], model VARCHAR, prompt_version VARCHAR, input_hash VARCHAR,
  built_at TIMESTAMP, PRIMARY KEY (segment, grain, period_from));
CREATE TABLE meta (key VARCHAR PRIMARY KEY, value JSON);   -- embedding model+dims, prompt versions, price table
```

Views the query agent sees (a small, well-named schema makes text-to-SQL much more reliable):

- `v_rate(route, period_from, period_to, value, unit, publisher, doc_id, obs_id)`
- `v_tc_assessment`
- `v_fixture`
- `v_sale` (one row per **transaction**, with the mention count)
- `v_demolition`
- `v_newbuilding`
- `v_company_fin(ticker, fiscal_period, concept, value, unit, form, accn)`
- `v_commodity_flow`
- `v_series` (generic)
- `v_gaps`

---

## 4. Layer A: exact facts (no LLM)

### 4.1 Series CSVs

Load every series CSV through `kb/series_map.yaml`, which gives for each file: the series_id pattern, date column, value columns, unit, entities and provenance class.

- Rows that carry `source_file`/`issue_date` map to `doc_id`/`published_at`.
- Rows without them get `method=csv:<file>`, and `published_at` = the first git commit that contains the row. It is never invented.

### 4.2 Broker tables not yet in a series

Extend the existing per-publisher parsers to emit sale, demolition, fixture and newbuild rows from `*.tables.json`.

- For an unknown layout, the LLM may classify the **header signature** into a known table type. That is one cached call per distinct signature, logged for review. The LLM never reads cells.
- Gate: every stored `raw_cell` is found verbatim in the source row.

### 4.3 SEC numbers: XBRL first

- Source: `data.sec.gov/api/xbrl/companyfacts/CIK##########.json`. No key is needed. The User-Agent is a generic project string with a contact address the owner sets in an env var (`SEC_USER_AGENT`), never hard-coded. Stay at or under 10 requests/s.
- Each fact becomes an observation with `series_id=sec:<TICKER>:<concept>`, `provenance=xbrl`, `published_at=filed`, and `doc_id` = the MD with that accession number.
- Shipping KPIs (TCE/day, OPEX/day, fleet days, utilisation) are usually custom extension concepts. Take them from the filing's XBRL instance first, then from MD tables with the deterministic parser.
- The 25 SEC files still on the merged-cell detector list (source-faithful or PDF-text exhibits) are **text only**: searchable and quotable, but never facts.

### 4.4 Transactions (D9)

Cluster sale, demolition, newbuild and charter rows into transactions using:

- vessel key (IMO; else normalised name + DWT ±2% + built year),
- kind,
- a date window of ±45 days,
- counterparties.

A price that is consistent within 2% across sources becomes the consensus value. Anything else sets `status=conflicting` and keeps every claim. Narrative mentions found in layer C (for example "sold to Greek buyers") attach to an existing transaction when the keys agree; otherwise they become a provisional transaction.

### 4.5 Revisions

A restated number is a new row, with a later `published_at` and `supersedes` set. Queries default to "latest known"; "as known on D" filters on `published_at <= D`.

### 4.6 Known gaps

Seed `corpus_known_gaps` from the cadence audit and the open-items doc, then add gaps computed per series and per publisher. A gap is a missing period longer than 1.5× the median cadence. Seabrokers is monthly, published at the start of the next month, so its cadence is set from the registry rather than inferred.

---

## 5. Layer B: hybrid text index

### 5.1 Sectioning

**Broker MDs:** split on headings. Mark as `boilerplate` any disclaimers, contact blocks and footers that repeat by hash across issues of the same publisher.

**SEC MDs:** they have weak or no headings, so `kb/sec_sectioner.py` splits on Item markers (regex on "Item 1.", "Item 4. Information on the Company", "Item 5. Operating and Financial Review", "Item 7.", "Item 3.D Risk Factors", ...).

- Fallback for files without Item markers: XBRL `dei` facts plus the filing index from EDGAR.
- 6-K press releases are one section each.
- `boilerplate`: cover page, TOC, signatures, exhibit index, 302/906 certifications, the forward-looking-statements block.
- Risk factors: keep the first occurrence per company, plus paragraphs that changed later (MinHash, Jaccard < 0.8).
- Gate: at least 95% of 10-K/20-F files have `item_5`/`item_7` found. Measured on the 25 largest filers.

### 5.2 Chunking and sentences

- **Prose:** 300–700 tokens on paragraph boundaries inside a section, never across sections. Each chunk is split into sentences by a rule splitter that knows shipping abbreviations: "abt.", "dwt", "m/t", "U.S.", decimals, "w/c". Sentence offsets go to `sentence`.
- **Tables:** one chunk per table. Long tables are split every 40 rows, with the header row and caption repeated. A row is never split.
- **Dedup:** normalise (lowercase, collapse whitespace, mask numbers and dates), then hash to `norm_sha`. A repeat is stored once and points to the first occurrence with `is_duplicate_of`. Repeats are embedded once and extracted once. Measured: 39% of SEC prose and 29% of broker prose are repeats.

### 5.3 Context prefix (deterministic, free)

The prefix is `"{publisher} · {title} · {published_at} · {heading_path} · {sec_item} · entities: {top tagged}"`. This captures most of the contextual-retrieval gain without an LLM call. An LLM-written prefix is used only for chunks whose heading path is empty or generic, and only if P0 shows that more than 10% of chunks are like that.

### 5.4 Embeddings (D4)

- **Model:** `Qwen3-Embedding-0.6B` at 1024 dims, the same model for documents and queries, recorded in `meta`. Running it with ONNX int8 on CPU keeps runners fast and the laptop query path light, at about 0.6 GB.
- **Build:** `.github/workflows/kb_embed.yml` is a manually dispatched matrix of 20 shards, split by `chunk_id` hash. Each shard embeds its chunks and uploads `vec_<shard>.npy` (fp16) plus ids as an artifact. A merge job builds one `vec/` set and attaches it to a draft GitHub Release `kb-vectors-<date>` **that contains no book chunks**. Book chunks (about 2M tokens) are embedded on the laptop overnight with the same model.
- **Pre-flight:** a 1-shard pilot measures tokens/s on a runner. If projected wall time per shard exceeds 5h, increase the shard count. The 6h job limit must not be hit.
- **Query time:** embed the query on the laptop, under 1 s on CPU.

### 5.5 Retrieval

1. Apply filters first: publisher, doc_type, date window, entity ids, `public_ok`.
2. Take the BM25 top 150 from FTS5. The tokenizer keeps route codes (C5, TD3C, P1A_82), IMO numbers and tickers as whole tokens. Take the exact dense top 150 from the memory-mapped fp16 vectors.
3. Fuse with RRF (k = 60).
4. Rerank with `bge-reranker-v2-m3` (ONNX int8, CPU, top 40 pairs, a few seconds) to get the top 15.

The reranker runs only at query time, so its CPU cost is acceptable.

---

## 6. Ontology and deterministic tagging

### 6.1 Closed lists (the LLM chooses only from these)

**Entity types:**

- `vessel`
- `company`, with roles: owner, operator, manager, charterer, shipyard, broker, miner, trader, bank, lessor
- `port`
- `route`
- `index`
- `commodity`
- `country`
- `publisher`
- `person` (low priority)

**Edge types (state facts, with validity intervals):**

- `OWNS`, `MANAGES`, `OPERATES`
- `TIME_CHARTERED_TO {rate_usd_day, period_months, delivery, redelivery}`
- `SOLD_TO {price, date, en_bloc}`
- `BUILT_BY {delivered}`
- `ORDERED_AT {price, delivery, units}`
- `DEMOLISHED_AT {country, ldt, price_usd_ldt}`
- `RENAMED {from, to}`
- `FLAG`, `SUBSIDIARY_OF`, `LISTED_AS {exchange, ticker}`
- `FINANCED_BY {lender, amount, type}`
- `FIXED {cargo, qty, load, disch, laycan, rate}` (narrative only; fixture tables go to layer A)

**Event types:**

- `market_move`, `port_congestion`, `canal_disruption`, `weather`, `strike_labour`
- `sanction_policy`, `regulation`, `trade_policy`
- `production_guidance`, `company_guidance`
- `accident_casualty`, `newbuilding_wave`, `demolition_wave`
- `other` (must be mapped later)

**Claim kinds:**

- `forecast`: a broker's or company's expectation with a horizon
- `view`: a market assessment
- `causal`: "X because Y", with both sides tagged

Claims answer questions such as "what drove Supramax in H1" and "who predicted the slump".

Every numeric attribute is stored **as printed**. It is parsed into `attrs` only if the parse is unambiguous, and it must appear in the cited sentences.

### 6.2 Deterministic pre-tagging (before any LLM call)

- **Regex:** IMO numbers with the check digit, Baltic codes from the taxonomy, tickers, dates, money (`USD 26 M`, `$1.2bn`, `$/day`, `WS 65`), DWT.
- **Aho–Corasick over registry aliases.** A vessel name counts only if a corroborating attribute (DWT, built year or yard) is in the same row or sentence, or the name is unique in the registry.
- The tags go into the prompt as `known_entities` with short ids (`E1`, `E2`, ...), so the model links to existing ids instead of inventing them.

### 6.3 Registry seeding

- **Vessels:** parsed S&P, demolition and newbuild tables (with the IMO where printed), `benchmark_core_fleet.json`, and the AIS voyage data under `data/geospatial/`.
- **Companies:** SEC ticker, CIK and name, plus `company_tickers.json` from SEC, plus buyer and seller columns. Nationality groups such as "GREEKS" and "CHINESE" are `country` tags, not companies.
- **Ports:** the UN/LOCODE list plus the cargo pipeline's gazetteer.
- **Routes, indices and commodities:** the reference JSONs only, never created by the LLM.

### 6.4 Resolution

Use Splink (Fellegi–Sunter, DuckDB backend) with blocking:

- vessels on (normalised name, DWT ±2%, built year, yard, owner, date),
- companies on (name, ticker, country).

Auto-merge only above a high threshold **and** only when IMO/CIK agree where both are present. Pairs in the middle band go to a cached LLM adjudication with a strict tool: `same | different | unsure` plus a reason. `unsure` stays separate. Unresolved names become `provisional` entities that can be promoted later.

Every decision is written to `merge_log` and can be undone.

---

## 7. Layer C: LLM extraction

### 7.1 What is sent

A chunk is sent only if all of these hold:

- `kind=prose`
- not a duplicate
- not boilerplate
- for SEC, `sec_item` is in {business, operating review, MD&A, subsequent events, press release, fleet}
- at least one tagged entity or event keyword is present

Risk factors and accounting notes are indexed in layer B but not extracted. P0 measures the expected scope; the planning number is **25–35M chunk tokens**.

### 7.2 Packing and call shape

```
system: STATIC_PROMPT   (rules, closed enums, Baltic list, 6 few-shots; byte-identical all run)
user:   <doc publisher=… date=… doc_type=… heading=…>
          <chunk id="c1"> [1] sentence … [2] sentence … </chunk>
          <chunk id="c2"> … </chunk>            ← up to ~3,500 chunk tokens per call, same document only
        </doc>
        <known_entities> E1|vessel|NAME|imo… E2|company|… </known_entities>
response: tool call record_extraction (or json_schema), temperature 0, max_tokens 2,500, reasoning off
```

Packing several chunks from the same document into one call spreads the cost of the static prompt (about 2.5k tokens) when the router gives no prefix-cache discount. The pilot measures whether the router reports cached tokens. If it does, packing still helps but matters less.

### 7.3 Output schema (strict where supported; pydantic everywhere)

```json
{"no_content": bool,
 "state_facts": [{"type": <edge enum>, "src": "E#|N#", "dst": "E#|N#",
                  "attrs_printed": [{"key": str, "value_as_printed": str}],
                  "valid_from_printed": str, "valid_to_printed": str,
                  "chunk": "c#", "sids": [int], "confidence": 0..1}],
 "events":      [{"type": <event enum>, "summary": str, "roles": [{"role": str, "entity": "E#|N#"}],
                  "when_printed": str, "magnitude_printed": str, "chunk": "c#", "sids": [int], "confidence": 0..1}],
 "claims":      [{"kind": "forecast|view|causal", "subjects": ["E#|N#"], "direction": "up|down|flat|mixed|na",
                  "horizon_printed": str, "chunk": "c#", "sids": [int], "confidence": 0..1}],
 "new_entities":[{"id": "N#", "type": <entity enum>, "name": str, "chunk": "c#", "sids": [int]}]}
```

The runner probes the router once to learn whether it accepts strict `tools`. If not, it uses `response_format={"type":"json_schema"}`, and if that fails too, `json_object` with the schema in the prompt. Pydantic validates every response regardless.

### 7.4 Acceptance gate (code, every record)

1. The response is valid JSON matching the schema. A blank or truncated response is retried, at most 3 times.
2. `sids` exist in the cited chunk. The quote is sliced by code from the sentence offsets (D7) and capped at 3 sentences.
3. Every printed number in `attrs_printed`, `magnitude_printed`, `when_printed` and `horizon_printed` occurs in the sliced quote. **Otherwise the record is dropped.**
4. `src`, `dst` and roles resolve to a `known_entities` id or to a `new_entities` item. A `new_entities` name must occur in its own cited sentences.
5. Dates are resolved by code from the printed text and `published_at` ("this week", "Q3"); the model never computes dates.
6. A chunk is escalated once to the escalation model (§10) if any of these hold:
   - more than 30% of its records fail gates 2–4,
   - mean confidence is below 0.5,
   - it is a long SEC MD&A chunk whose cheap-model record count is less than half the pilot median for its section type.
7. Every raw response is kept in `raw/` and the ledger, so gates can be re-run for free.

### 7.5 Runner (`kb/llm_runner.py`)

- **Ledger:** SQLite `jobs(job_key, pass, prompt_version, model, status, attempts, request_hash, in_tok, cached_tok, out_tok, cost_usd, finish_reason, latency_ms, model_returned, error, created_at)`. `job_key` = sha256(packed chunk shas + prompt_version + pass). Calls are idempotent and resumable, with a commit after every response.
- **Concurrency:** asyncio. Start at 8 concurrent calls and ramp up to the highest level with error rate under 2% (cap 48). Exponential backoff with jitter on 429/5xx.
- **Budget guard:** live spend is computed from the usage fields × the price table in `kb/config.yaml`. Each pass has its own hard cap (§10), and the pipeline's global cap is **$82** (the coding agent has its own $60; $3 covers overshoot). The runner stops cleanly at any cap.
- **Drift guard:** `model_returned` is logged on every call. If it changes mid-run, the run pauses and the extraction gold set is re-scored before resuming.
- **Provider pool:** `kb/config.yaml` lists providers (Enclave paid; Ultrafast free, concurrency 1, ≤ 3M output tokens/day for the pipeline; later NVIDIA NIM or other DeepSeek credits). One pass uses one model version. A second provider of the same model joins a pass only after it matches the gate pass rate within 2 points on the same 50 chunks. Free capacity is used before paid. Every record stores provider and model.
- **Partial coverage beats lower quality:** if caps are hit, the pass stops with coverage declared. Remaining chunks wait for more capacity and are run with the same prompt, model and gates.
- **Ordering:** short documents and 6-Ks go first; the largest 20-F MD&A chunks go last. A cap stop then leaves the most coverage done.
- **Keys:** `ROUTER_API_KEY` from the environment if set; otherwise `refs.ENCLAVE_API_KEY` from `~/.dsh/.credentials.yaml` (the key dsh already uses). `ROUTER_BASE_URL` defaults to `https://router.enclave.ai/v1`. Model ids carry the `cyberouter/` prefix. The key is never printed, logged, copied to another file or committed.

### 7.6 Gleaning

There is no blanket gleaning pass. Gleaning (one continuation turn: "anything missed, same schema") runs only on chunks that rule 6 escalates, and only if the escalated call itself returns fewer records than the pilot median.

---

## 8. Period summaries (time tree)

**Segments:** capesize, panamax, supramax, handysize, vlcc, suezmax, aframax, mr_lr, lng, lpg, container, snp, demolition, newbuilding, iron_ore, coal, grains, bunkers, plus companies (per ticker, quarterly).

**Grains:** month, then quarter, then year. Week leaves are skipped: weekly questions go straight to layer A and B, so a month leaf halves the call count with no loss.

- **Leaves:** a leaf is built from that month's layer-A observations (a small table), the top chunks for the segment and month, the events and the claims.
- **Parents:** parents are built from their children **plus** the top-10 underlying evidence items, so errors do not compound up the tree.
- **Citation rule:** every sentence must cite an `obs_id`, `chunk_id`, `event_id` or `claim_id`. A number not present in a cited observation or quote fails the automatic check, and that sentence is dropped.
- **Updates:** `input_hash` makes a rebuild touch only leaves whose evidence changed, plus their ancestors.

---

## 9. Query agent

**Tools:**

- `sql(query)`: read-only on the `v_*` views, with a 500-row limit and a 10 s timeout.
- `search(query, filters)`
- `graph(entity_id, window, hops≤2, types)`
- `ppr(seed_entities, window)`: personalised PageRank (HippoRAG-2 style) over entity–chunk–event–claim nodes, with edges weighted by confidence and recency.
- `summary(segment, grain, period)`
- `gaps(scope, key, window)`
- `cite(id)`: returns the path, page and quote.

**Answer contract:**

- Every number must equal a value in a tool result. A post-check regex-matches every number against the tool outputs, with unit and rounding tolerance. On a mismatch, regenerate once; if it still fails, answer "not in the data".
- Every claim carries a citation. "What did we know on D" uses `published_at <= D`.
- If a gap covers the window, say so.

**Default models:** the bulk model answers. The escalation model handles multi-hop and summary questions when the first answer fails the post-check.

**Interface:** a CLI first (`python -m kb.ask "..."`). A dashboard tab can come later.

---

## 10. Models, budget and the bake-off

### 10.1 Router price list (from the owner's catalogue screenshots, unverified until the pilot)

USD per 1M tokens, input / output:

| Model | Input | Output |
|---|---|---|
| gpt-oss-120b | 0.10 | 0.50 |
| deepseek-v4-flash | 0.13 | 0.26 |
| glm-5.3-flash | 0.15 | 0.50 |
| deepseek-v4.1-flash | 0.30 | 1.20 |
| minimax-m3 | 0.30 | 1.20 |
| nemotron-ultra | 0.60 | 2.40 |
| deepseek-v4-pro | 1.32 | 3.96 |
| glm-5.3 | 1.40 | 4.40 |
| qwen3.8-max | 2.00 | 6.00 |
| kimi-k3 | 2.70 | 13.50 |

### 10.2 Bake-off (phase P4b, about $6)

1. **Build the extraction gold set: 120 chunks**, stratified by publisher, doc_type, year and section type.
   - Reference labels come from the two strongest affordable models of **different families** (deepseek-v4-pro and glm-5.3).
   - Where they agree, the label is accepted. Where they disagree, a third strong model (qwen3.8-max) decides, and the case is flagged.
   - All references go through the §7.4 gates.
   - The owner checkpoint (agent task, C1) reviews 30 flagged items.
2. **Score the candidates:** deepseek-v4-flash, deepseek-v4.1-flash, glm-5.3-flash, gpt-oss-120b, minimax-m3, deepseek-v4-pro and glm-5.3, all with the same prompt. Also score **reasoning-on variants** of the best two, including Ultrafast V4.1 Flash with thinking, which is free.
3. **Metrics:** gate pass rate, and precision and recall of edges, events and claims against the reference (matched on type, entities and sentence overlap). Also schema failures, latency, real cost per 1k chunks, and cached-token reporting.
4. **Choose (the owner ruled on 2026-11-08 that quality beats saving dollars):**
   - Bulk extractor = **the highest-F1 candidate whose projected full-scope cost fits the extraction plus escalation caps together**, with precision at least 0.92. Free capacity (Ultrafast) is used for it wherever the same model and settings are available. If the best model cannot cover the whole scope within the caps, it covers what it can and the rest waits for more capacity (partial coverage over lower quality).
   - Escalation model = the reference model with higher agreement with the adjudicated labels.
   - Judge (for eval and adjudication) = a model from a different family than the bulk extractor.

### 10.3 Budget (hard caps enforced by the runner)

| Pass | Planning volume | Cap |
|---|---|---|
| **Coding agent (dsh): writing, testing and fixing the pipeline** | main agent V4 Pro (Enclave), subagents V4.1 Flash thinking (Ultrafast, free), ≤ 4 at once | **$60** (enforced by the gateway; raised from $45 on 2026-11-10, owner: the whole credit is for this build) |
| P-1 router probe + P4b bake-off + gold labels | ~1,200 calls | $7 |
| P4c bulk extraction | 25–35M chunk tokens, ~9–11k packed calls, ~3.5k chunk + 2.5k prompt in, ~1.8k out | $22 (v4-flash ≈ $11–14; glm-5.3-flash ≈ $15–19; v4.1-flash only if its projection fits) |
| Escalation + targeted gleaning (≤ 10% of packed calls) | ~1k calls on the pro-tier model | $17 |
| Entity adjudication (middle band only) | ~15k short calls | $4 |
| LLM prefixes for generic chunks (only if more than 10%) | ≤ 15k short calls | $1 |
| Period summaries (19 segments × ~150 months + parents) | ~3.5k leaf + ~700 parent calls | $13 |
| Eval: gold Q&A generation + judging + 2 regression runs | | $8 |
| Re-run reserve (one prompt fix over the failing slice) | | $9 |
| Incremental reserve (left after the build) | | $1 (cut from $16 on 2026-11-10: owner put the credit into this build) |
| Overshoot margin | | $3 |
| **Total** | | **$145** (pipeline caps sum to $82: the re-run reserve is $9) |

Money released by a cheaper bulk model goes first to escalation (raising the escalated share towards 25%), then to the reserve. (2026-11-10: owner moved $15 of the incremental reserve to the coding agent.)

Embedding, BM25, resolution, PPR and all layer-A work cost $0: they run on runners or the laptop.

---

## 11. Phases (each has a script, an output report and a gate)

All scripts live under `kb/`, are idempotent, and write `kb/reports/<phase>.md` plus a JSON with the gate numbers. A phase does not start until the previous gate passes. The procedure, including stop rules, is in `docs/GRAPHRAG_AGENT_TASK.md`.

| Phase | Does | Gate |
|---|---|---|
| **P0** inventory | Re-run `kb/p0_inventory.py` with real token counts (tiktoken `o200k_base` as a proxy). | R1–R7 pass. Token report written. |
| **P0.5** normalise | Frontmatter normaliser into `document` rows. SEC sectioner. Boilerplate. Dedup. | 100% of MDs get a `published_at` and `publisher_id`. SEC item coverage ≥ 95% on the top 25 filers. Measured extraction scope written. |
| **P-1** router probe | 20 calls per candidate model: tool or schema support, usage fields, cached tokens, `model_returned`, latency, a rate-limit ramp. | Report written. At least 2 candidates usable. |
| **P1** load | DuckDB schema; `document`, `section`, `chunk`, `sentence`. FTS5 build. | Row counts equal the P0.5 report. 50 random chunks round-trip to their source text exactly. |
| **P2** facts | Series map, XBRL, table parsers, transactions, gaps. | Every observation's `raw_cell` is found in its source (sample 2,000 + all SEC). 40 known values answered exactly through `v_*`. Transaction dedup spot-check of 50 clusters ≥ 96% correct. |
| **P3** registry | Seed + Splink + tagging. | 300-pair merge audit (judge model + owner sample of 30) precision ≥ 0.98. Zero merges with conflicting IMO/CIK. |
| **P4a** embed + index | Matrix embed, merge, retrieval. | Retrieval recall@20 ≥ 0.85 on the retrieval part of the Q&A gold set. |
| **P4b** bake-off | §10.2 | Gates pass rate ≥ 95% for the chosen model; precision ≥ 0.92. **Owner checkpoint C1.** |
| **P4c** extraction | All in-scope chunks, short first. | Failure queue < 2%. 200-record random audit by the judge ≤ 3% wrong. Budget respected. |
| **P5** graph | Gate into `edge`/`event`/`claim`; resolve; attach to transactions; PPR export. | No record without a code-sliced quote. No dangling ids. |
| **P6** summaries | Time tree. | Automatic number check 100%. Judge-graded faithfulness ≥ 95% on 60 nodes. |
| **P7** agent | Tools + answer contract + CLI. | Q&A eval (§12) thresholds met. **Owner checkpoint C2** (reads the eval report). |
| **P8** incremental | `kb/update.py` in CI after the ingest workflows, plus snapshot publishing. | A dry run on the last 2 weeks of new MDs costs < $1. The eval regression subset passes. |

Order: P0 → P0.5 → P-1 → P1 → P2 → P3 → P4a, then the Q&A gold set, then P4b → C1 → P4c → P5 → P6 → P7 → C2 → P8.

P2 alone answers most numeric questions exactly. That is why it comes before any LLM spend.

---

## 12. Evaluation

### 12.1 Q&A gold set (250 questions, built after P3 and before P4b)

Each question has an exact answer and source ids. The set is generated by code and by the judge model from verified data, and the owner samples 25 at C1.

| Type | Count | Example |
|---|---|---|
| (a) single number | 50 | |
| (b) window aggregate | 25 | |
| (c) multi-hop entity | 35 | |
| (d) event → market | 25 | |
| (e) SEC | 35 | |
| (f) summary / trend | 25 | |
| (g) as-known-on-date | 15 | |
| (h) unanswerable or gap | 40 | must refuse or report the gap |

### 12.2 Synthetic regression

Random observations, verified edges and transactions are turned into questions automatically, with unlimited supply. This set runs in CI on prompt or parser changes.

### 12.3 Targets

- Exact match with unit on (a), (b), (e) and (g): ≥ 97%.
- Retrieval recall@20: ≥ 0.85.
- Multi-hop F1: ≥ 0.75.
- Refusal and gap accuracy on (h): ≥ 95%.
- Faithfulness, meaning every sentence is supported by a cited id: ≥ 95% (automatic check plus a judge model from another family).
- Cost and latency per question are reported.

---

## 13. Incremental updates and publishing

### 13.1 Weekly CI (after the ingest workflows)

1. New or changed MDs, by sha, go through P0.5 → P1 rows.
2. New series rows become observations; revisions become new rows.
3. New chunks are embedded on the runner and extracted. The ledger key makes re-runs free.
4. The resolver runs on new aliases.
5. Only month leaves whose `input_hash` changed are rebuilt, plus their ancestors.
6. The synthetic regression subset is re-run.

Expected cost: a few hundred calls, under $0.50/week. The router key would be a repository secret set by the owner. Until the owner sets it, the LLM step is skipped and the job only queues the work.

### 13.2 Corrections

Mark the edge `status=rejected` with a reason (soft delete, kept for audit), or re-run one document. Deleting by `doc_id` and re-extracting is free while the ledger holds the raw response, and costs one call with a new prompt version.

### 13.3 Snapshots

Before each build is declared done, a `kb-snapshot-<date>` GitHub Release is published. It contains:

- `kb.duckdb` without book rows
- `fts.sqlite` without book rows
- `vec/` without book rows
- the `raw/` JSONL with book entries removed

The local copy keeps everything.

---

## 14. Risks and how the plan handles them

| Risk | Handling |
|---|---|
| Invented numbers | Numbers come only from parsers, XBRL and CSVs. LLM numbers must appear inside code-sliced quotes. Answers pass a post-check. |
| Router limits, outage or price change | P-1 probe, ramped concurrency, resumable ledger, per-pass caps, and a provider-agnostic runner. |
| No prefix cache on the router | Packing; the cost table already assumes no cache. |
| Model swapped under the same name | `model_returned` is logged; a change pauses the run and triggers a gold-set re-score. |
| Wrong vessel merges | Keys required; name alone never merges; undoable `merge_log`; precision gate. |
| Same deal counted six times | Transactions and mentions (D9). |
| Temporal confusion | Separate valid time and knowledge time; relative dates resolved by code. |
| "Not in corpus" vs "did not happen" | `corpus_known_gaps` plus the gaps tool. |
| Laptop runs out of memory | DuckDB memory limit, streaming, memory-mapped vectors, no servers, embedding off-box. |
| Laptop sleeps mid-run | The ledger resumes exactly. The runner keeps the machine awake only while running (`SetThreadExecutionState`). |
| Copyright | `public_ok=false` for books. Release builder asserts zero book rows. |
| Key leakage | Keys only in env vars; the secret scan runs before every commit; runner logs redact `Authorization`. |
| Upstream parser defect found during the build | Logged to `kb/reports/upstream_defects.md`, never patched silently inside `kb/`. The fix goes through the normal parser process and the doc is re-run. |

---

## 15. What not to do

- No GraphRAG framework over the corpus. Never let an LLM read table cells or produce a number.
- No chart-image numbers. `chart_derived` rows are excluded from answers by default.
- No name-only merges. No "undisclosed buyer" guessing: those stay provisional.
- No local LLM on the laptop. No server databases.
- No prompt change mid-pass. A changed prompt is a new `prompt_version`, re-run over a defined slice.
- No book content in any public artifact.
- Do not edit corpus MDs, series or data from inside `kb/`, and never while pytest is running: the conftest checks data back out.

---

## 16. What came from the six reviews

The reviews are in `docs/Recommendations/` (local, not committed).

**Adopted:**

- Every reviewer agreed: separate numeric layer, embedded storage on 8 GB, pilot before the full build, IMO/CIK resolution, provenance on every fact.
- Sentence-indexed span output instead of model-written quotes.
- `corpus_known_gaps`.
- Canonical transactions vs mentions.
- A provenance class for chart-derived series.
- Claims (forecast, view, causal) as first-class records.
- Splink plus key gating.
- Unanswerable questions in the gold set.
- A model bake-off rather than an assumed model.
- Time-tree parents re-grounded on evidence.
- Exact vector search instead of ANN at this scale.

**Rejected:**

- LightRAG or KAG as the ingest framework (generic extraction, no cell-exact tables).
- NetworkX pickles as the store.
- Free hosted embedding APIs (rate limits, and the model could change under us).
- LangGraph/LlamaIndex orchestration.
- A $16 full-build estimate that ignored prompt overhead and escalation.
- Postgres on this laptop.
