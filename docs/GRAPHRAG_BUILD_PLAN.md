# Maritime knowledge base: GraphRAG build plan (DeepSeek)

Written 2026-11-01. Owner runs the build with the USD 700 DeepSeek credit; this document is the full structure.
Research behind it (fetched 2026-11-01, sources listed at the end): current GraphRAG variants, hybrid retrieval,
table and number handling, entity resolution, stores, and the DeepSeek API (models, prices, caching, limits,
structured output, the Harness / dsh-superagent agents).

> **One sentence.** Build a *knowledge base*, not a chatbot index: numbers go into a typed fact store parsed without
> an LLM; text goes into a hybrid search index; the LLM builds only a thin, quote-verified event graph from the
> narrative text; and a tool-using agent answers by querying all three. Every number in an answer comes from a row.

---

## 0. Decisions (read first)

| Decision | Choice | Why |
|---|---|---|
| Framework | **Own pipeline in Python on PostgreSQL**; borrow algorithms (HippoRAG 2 PPR, TG-RAG time tree, Anthropic contextual retrieval), not frameworks | Microsoft GraphRAG / LightRAG / KAG / Graphiti flatten numbers into LLM-written descriptions and have no time model; that is exactly where invented values entered this repo before. Kuzu is dead (archived Oct 2025), KAG has had no release since Jun 2025, LazyGraphRAG has no confirmed OSS release |
| Layers | **A** fact store (deterministic) · **B** hybrid text index · **C** LLM event/state graph · shared **entity registry** · **period summaries** | Most questions about this corpus are numeric/temporal lookups (SQL), then text lookups (BM25+dense), then entity hops (graph). Benchmarks (GraphRAG-Bench, ICLR 2026) show reranked vector RAG beats MS-GraphRAG on simple fact questions; graphs win only on multi-hop and summarisation |
| Numbers | **Never through the LLM.** Broker tables → existing parsers/series; SEC → XBRL `companyfacts` + table parser; 168 series CSVs loaded as-is | Anti-fabrication history (chart estimates, parser-invented tables, hardcoded estimates). Every observation keeps doc / table / row / column / raw cell text |
| LLM | `deepseek-flash` (V4.1-Flash-1017), **thinking disabled**, strict tool calling on `/beta`, **off-peak only**; `deepseek-v4-pro` only for escalations and the top period summaries | Flash off-peak: $0.003 cache-hit / $0.15 miss / $0.60 output per 1M. Thinking is ON by default and would multiply cost |
| Orchestration | Plain `asyncio` + `openai` SDK + SQLite job table. **Not** DeepSeek Harness / dsh-superagent | dsh-superagent is a real `deepseek-ai` repo but its README calls it a research prototype; it is a GitHub-ticket coding agent (one agent session per ticket). Harness is a developer-preview coding agent that uploads session logs by default. Neither fits 60k stateless, schema-validated calls with per-call cost accounting |
| Store | **PostgreSQL 17 + pgvector + pg_trgm** (+ ParadeDB `pg_search` for true BM25 if wanted). Graph = plain edge tables + recursive CTE / igraph for PPR | One database for facts, chunks, vectors, edges, time columns. Graph size here (tens of thousands of entities, a few hundred thousand edges) does not need a graph DB |
| Embeddings | `Qwen3-Embedding-0.6B` (DeepInfra ≈ $0.01/M tokens, or local), fixed for the life of the index | DeepSeek has no embeddings endpoint |
| Reranker | `Qwen3-Reranker-0.6B` or `bge-reranker-v2-m3` (local), choose on the gold set | Open licence; route codes / IMO / tickers need BM25 + rerank more than bigger embeddings |
| Budget | Plan ≈ **$60–110** for the first full build, cap **$400** in the runner, keep ≥ $250 for re-runs after prompt fixes | One-time builds are re-run 3–5 times while prompts are tuned |

---

## 1. Inputs and readiness (state 2026-11-01)

### 1.1 What goes in

| Input | Path | Files | Size | Of which table rows | Route |
|---|---|---|---|---|---|
| Broker / publisher MDs (27 publishers) | `data/extracted/md/<publisher>/<year>/*.md` | 19,272 | 146.8 MB | 46.4 MB | tables → A (existing parsers + series); prose → B and C |
| SEC filings (10-K, 20-F, 6-K, 10-Q, 8-K, 40-F, amendments) | `corpus/10-companies/<TICKER>/<FORM>/*.md` | 1,346 | 244.6 MB | 38.7 MB | financial statements → A via XBRL; narrative sections (Item 4/5, MD&A, fleet, charters, financing) → B and C; boilerplate dropped |
| Books | `corpus/books/` | 12 | 10.1 MB | 0.6 MB | B and C (domain concepts, definitions) |
| Joined series | `data/extracted/series/*.csv` (168), `data/commodities/*.csv`, `data/derived/*.csv` | ~230 CSV | — | all | A as-is (each row already carries source doc/date) |
| Reference | `data/reference/baltic_route_taxonomy.json`, `benchmark_core_fleet.json`, `commodity_normalisation.json`, `fearnleys_tsid_registry.json` | — | — | — | registry seeds |

Measured by a scan of every MD on 2026-11-01: **20,630 MDs, 401.5 MB, of which 85.1 MB markdown table rows and
314.4 MB prose**. At ~4 characters/token prose and ~2.5 characters/token tables that is roughly 80M prose tokens +
35M table tokens. **Re-measure with the DeepSeek tokenizer in phase P0** before budgeting (number-dense text
tokenises worse).

Not inputs: `knowledge/` (legacy BM25 build), `corpus/archive/`, PDFs/PNGs (the MDs are the normalised text; the
PDF path is kept in frontmatter `source_file` for citation and audit).

### 1.2 MD frontmatter contract (already present, used as metadata — no LLM)

Broker MD: `title, publisher, source, issue_date, document_header_date, issue_date_conflict, year, source_file,
source_sha256, pages_total, pages_parsed, parser, parsed_at`. SEC MD: `ticker, company_name, cik, form,
filing_date, accession_number, source, source_file`.

`issue_date` is the publication (knowledge) time. Where `issue_date_conflict: true`, use `issue_date` and keep
`document_header_date` as a second attribute; never guess.

### 1.3 Readiness checklist (run before P1; every box must pass)

| # | Check | Command / source | State 2026-11-08 |
|---|---|---|---|
| R1 | Knowledge validator PASS | `python scripts/validate_knowledge.py` (run alone, ~30 min) | **PASS 2026-11-08** on this branch (content-gate failures 0) |
| R2 | No open **Blocker** in `docs/PRE_GRAPHRAG_OPEN_ITEMS.md` | ledger | **PASS 2026-11-08**: no open Blocker; the CI-ingest regression blocker closed 2026-11-01 (re-ingest proof for every publisher) |
| R3 | Every MD has `source_file` that exists and `source_sha256` matching the PDF | P0 script `kb/p0_inventory.py` | **PASS 2026-11-08**: 20,687 MDs, 0 failing (2026-11-02: 20,630); 1,066 carry `source_sha256`, all match. PDFs are gitignored, so sources are looked up in the main checkout too; API records (Fearnleys voice/app) pass on their record id |
| R4 | Every MD has a parseable publication date | same | **PASS 2026-11-08**, 0 failing (59 Agora issues dated from the PDF creation date, `issue_date_basis`) |
| R5 | Series CSVs: no duplicate (series, date) keys, no future dates | `scripts/verify/validate_cargo_data.py` + series inventory audit | **PASS 2026-11-08**: 166 series, 0 future-dated rows; no duplicate (date, route) key in NCFI after the 11-08 fix; 5 identical rows left in deal tables (Advanced, Carriers, Clarksons, Star Asia x2), each printed twice in its PDF |
| R6 | Known residuals recorded and routed | ledger "open" items | **SEC (2026-11-02): converter fixed; 174 filings re-rendered (numbers identical, or values the old conversion lost put back from the SEC source). 26 flagged files left: 9 PDF-origin exhibits, 12 source-faithful text tables, 1 false positive, 2 real stacked VALE blocks (values present, rows merged). Details in the ledger.** Route: SEC numbers come from XBRL (§4.3), not from those cells, so this does not block; the narrative text of those MDs is fine. **2026-11-08**: Xclusiv split rows, Banchero label tables (213/245 identical to the PDF text, rest render-checked), NCFI fixed; remaining residuals listed in the ledger |
| R7 | Secrets absent from MDs | grep `llx-`, `sk-`, `ghp_`, `AKIA`, `Bearer`, `nace_sk_` over the inputs | **PASS 2026-11-08**, 0 hits. Inventory: 402.1 MB, about 111.5M tokens (estimated: the DeepSeek tokenizer runs out of memory on the 7.7 GB box), `kb/reports/p0_inventory.json` |

Owner can start **P0 now**: it only reads the repo.

---

## 2. Architecture

```
                    ┌───────────────────────────── ENTITY REGISTRY (Postgres) ─────────────────────────────┐
                    │ vessel(IMO) company(CIK/LEI/ticker) port(UN/LOCODE) route(Baltic code) commodity       │
                    │ index/series  publisher  person(low priority)   alias(+provenance, merged_by, undo)      │
                    └───────▲──────────────────────────▲───────────────────────────────▲────────────────────────┘
                            │ deterministic tagging    │ resolution (Splink + LLM band) │
 MD files ──► P0 inventory ─┼─► P2 tables ──► parsers ─┴──► (A) OBSERVATIONS  bi-temporal, per-cell provenance
   (20,630)   hash/dedupe   │   SEC ──► XBRL companyfacts ──► (A)                 ▲  SQL views
              sections      │   168+ series CSVs ──────────► (A)                 │
                            │                                                    │
                            ├─► P3 chunks (heading-aware, tables whole, header repeated, metadata prefix)
                            │        └─► (B) BM25 (tsvector / pg_search) + pgvector  ──► RRF ──► rerank
                            │
                            └─► P4 narrative chunks ─► DeepSeek Flash, strict tool schema, evidence quote
                                     verify quote ⊂ chunk · numbers ⊂ quote · ids ∈ registry · escalate to Pro
                                     └─► (C) EVENTS / STATE FACTS  valid_from/valid_to + published_at + quote
                                 P6 PERIOD SUMMARIES  segment × week → month → quarter → year (TG-RAG pattern)

 QUERY AGENT (P7): tools = sql(views) | search(B) | graph(entity, window, PPR) | summary(segment, period) | cite
                   → answer with [obs:…] [chunk:…] [edge:…] citations → numeric post-check against tool rows
```

Why three layers and not one graph: a weekly C5 rate is an **observation** (a number for a period, published on a
date, possibly revised), not a relationship. An ownership, a charter or a sale **is** a relationship with a validity
interval. A port strike or guidance cut is an **event**. Each is stored in the shape that keeps it exact.

---

## 3. Data model (PostgreSQL 17)

Schema `kb`. DDL below is the contract; types are exact, names can be adjusted once.

```sql
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- fuzzy alias lookup

-- documents and their structure -------------------------------------------------
CREATE TABLE kb.document (
  doc_id        text PRIMARY KEY,           -- sha256 of the MD bytes (first 16 hex) - stable across runs
  path          text NOT NULL UNIQUE,       -- repo-relative MD path
  source_file   text,                       -- PDF / HTML the MD came from
  source_sha256 text,
  publisher     text NOT NULL,              -- registry publisher id
  doc_type      text NOT NULL,              -- broker_weekly | broker_daily | sec_10k | sec_20f | sec_6k | book | ...
  title         text,
  published_at  date NOT NULL,              -- issue_date / filing_date  (knowledge time)
  period_hint   daterange,                  -- what the report covers, when known (week of, quarter of)
  company_id    text,                       -- SEC: registry company id
  frontmatter   jsonb NOT NULL,
  ingested_at   timestamptz NOT NULL DEFAULT now(),
  parser_version text NOT NULL
);
CREATE TABLE kb.section (
  section_id  text PRIMARY KEY, doc_id text REFERENCES kb.document,
  ord int, heading_path text[],             -- ["TANKERS","VLCC"]
  kind text,                                -- prose | table | list | boilerplate
  text text, sha256 text, tokens int
);

-- layer B: chunks -------------------------------------------------------------
CREATE TABLE kb.chunk (
  chunk_id    text PRIMARY KEY, doc_id text REFERENCES kb.document, section_id text,
  ord int, kind text,                       -- prose | table
  context_prefix text,                      -- generated from metadata (§5.3)
  body text NOT NULL, tokens int, sha256 text,
  is_duplicate_of text,                     -- same normalised body seen earlier (boilerplate / repeated tables)
  entity_ids text[],                        -- deterministic tags (§6.2)
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(context_prefix,'')||' '||body)) STORED,
  embedding vector(1024)
);
CREATE INDEX ON kb.chunk USING gin (tsv);
CREATE INDEX ON kb.chunk USING hnsw (embedding vector_cosine_ops);

-- registry ------------------------------------------------------------------------
CREATE TABLE kb.entity (
  entity_id text PRIMARY KEY,               -- vessel:9xxxxxx | company:cik0001577437 | port:CNQDG | route:C5 | commodity:iron_ore
  type text NOT NULL, canonical_name text NOT NULL,
  attrs jsonb NOT NULL DEFAULT '{}',        -- vessel: dwt, built, yard, type; company: ticker, lei, country
  created_by text NOT NULL                  -- seed:<file> | resolver:<run> | manual
);
CREATE TABLE kb.alias (
  alias text, alias_norm text, entity_id text REFERENCES kb.entity,
  source text, confidence real, merged_by text, valid daterange,   -- names are reused: an alias can be time-bound
  PRIMARY KEY (alias_norm, entity_id)
);
CREATE INDEX ON kb.alias USING gin (alias_norm gin_trgm_ops);

-- layer A: observations (bi-temporal) --------------------------------------------
CREATE TABLE kb.series (
  series_id text PRIMARY KEY,               -- e.g. baltic:C5 | fearnleys:VLCC_MEG_CHINA_WS | sec:STNG:Revenues
  name text, unit text, currency text, basis text, frequency text,
  entity_ids text[], source_csv text, definition jsonb
);
CREATE TABLE kb.observation (
  obs_id bigserial PRIMARY KEY,
  series_id text REFERENCES kb.series,
  period daterange NOT NULL,                -- VALID time: what the number refers to
  value numeric NOT NULL, unit text, raw_cell text NOT NULL,   -- raw_cell must literally exist in the source
  doc_id text, table_ord int, row_ord int, col_ord int,
  published_at date NOT NULL,               -- KNOWLEDGE time: when it became known
  ingested_at timestamptz DEFAULT now(),
  method text NOT NULL,                     -- parser:<name>@<ver> | xbrl:<accn> | csv:<file>
  supersedes bigint                         -- a revision points at the row it revises; nothing is overwritten
);
CREATE INDEX ON kb.observation (series_id, period);
-- "as known on D": WHERE published_at <= D, latest published_at per (series_id, period)

-- layer C: events and state facts -----------------------------------------------
CREATE TABLE kb.edge (
  edge_id text PRIMARY KEY,                 -- hash(type, src, dst, valid_from, doc_id)
  type text NOT NULL,                       -- closed enum (§6.1)
  src text REFERENCES kb.entity, dst text REFERENCES kb.entity,
  attrs jsonb NOT NULL DEFAULT '{}',        -- typed per edge type (price, rate, period, direction ...)
  valid_from date, valid_to date,           -- when it is true in the world (null = unknown / open)
  published_at date NOT NULL, doc_id text, chunk_id text,
  quote text NOT NULL,                      -- verbatim, ≤ 40 words, verified substring of the chunk
  extractor text NOT NULL,                  -- model@prompt_version
  confidence real, status text DEFAULT 'active'   -- active | superseded | rejected
);
CREATE TABLE kb.event (                     -- n-ary events (strike, congestion, sanction, guidance change...)
  event_id text PRIMARY KEY, type text, summary text,
  occurred daterange, published_at date, location text, magnitude jsonb,
  doc_id text, chunk_id text, quote text NOT NULL, extractor text, confidence real
);
CREATE TABLE kb.event_role (event_id text REFERENCES kb.event, role text, entity_id text REFERENCES kb.entity);

-- period summaries (TG-RAG time tree) -------------------------------------------
CREATE TABLE kb.period_summary (
  segment text, grain text, period daterange,   -- segment: capesize | panamax | vlcc | mr | lng | snp | demolition | iron_ore ...
  summary text, cited_ids text[], model text, prompt_version text, built_at timestamptz,
  PRIMARY KEY (segment, grain, period)
);

-- LLM job ledger (lives in SQLite during runs, copied here afterwards) -----------
CREATE TABLE kb.llm_call (
  chunk_sha text, prompt_version text, pass text, model text,
  status text, attempts int, cache_hit_tokens int, cache_miss_tokens int, output_tokens int,
  cost_usd numeric, finish_reason text, raw_response jsonb, error text, created_at timestamptz,
  PRIMARY KEY (chunk_sha, prompt_version, pass)
);
```

SQL views the agent sees (small, well-named schema = much better text-to-SQL):
`v_rate_weekly(route, week, value, unit, publisher, doc)`, `v_tc_assessment(segment, period, tenor, value)`,
`v_fixture(date, vessel, dwt, cargo, load, disch, rate, charterer, publisher)`,
`v_sale(date, vessel, imo, dwt, built, yard, price_usd_m, buyer, seller, publisher)`,
`v_demolition(date, vessel, ldt, price_usd_ldt, country, publisher)`, `v_newbuilding(...)`,
`v_company_fin(ticker, fiscal_period, concept, value, unit, form, accn)`, `v_commodity_flow(series, period, value, unit)`,
`v_series(series_id, period, value, unit, published_at)` (generic), each with the `obs_id`.

---

## 4. Layer A: fact store (no LLM)

### 4.1 Series CSVs (already joined)
Load every CSV under `data/extracted/series/`, `data/commodities/`, `data/derived/` with a per-file mapping
(`kb/series_map.yaml`: file → series_id pattern, date column, value columns, unit, entity ids). The CSVs already
carry `source_url`/`source_file`/`issue_date`; map them to `doc_id` and `published_at`. Rows without a source
document get `method = csv:<file>` and `published_at = file's ingest date from git log` (never invented).

### 4.2 Broker tables not yet in a series
The table rows in the MDs (46 MB) are mostly already harvested into the 168 series. For the rest (sale lists,
demolition lists, fixture lists, newbuilding orders), extend the existing per-publisher parsers to emit
`observation`/`v_sale`/`v_fixture` rows. Unknown table layouts: the LLM may *classify the header* into a known table
type (one call per distinct header signature, cached, reviewed), never read the cells. Gate: every stored cell's
`raw_cell` is found verbatim in the MD row.

### 4.3 SEC financials: XBRL first
- `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` per company (no key; set a `User-Agent` with a
  contact email, ≤ 10 requests/s), or the nightly `companyfacts.zip`. Covers 10-K/10-Q/8-K/20-F/40-F/6-K facts in
  `us-gaap`, `ifrs-full`, `dei`, `srt`, each with `accn`, `form`, `filed`, `fy`, `fp`, `frame`.
- Load each fact as an observation: `series_id = sec:<TICKER>:<concept>`, `period` from `start/end`,
  `published_at = filed`, `method = xbrl:<accn>`, `doc_id` = the MD with that accession number.
- Shipping KPIs (TCE/day, fleet days, OPEX/day, utilisation) are usually **custom extension concepts** and are *not*
  in companyfacts. Get them from the filing's XBRL instance (`<accn>/..._htm.xml`) or from the MD tables with a
  deterministic parser. The 208 MDs with stacked numeric cells are exactly where table parsing is weak; prefer XBRL
  for those filings and only parse what XBRL lacks.
- Foreign private issuers' 6-K press releases often have no XBRL: parse their tables deterministically; if a table
  cannot be parsed exactly, leave it as text in layer B (searchable, quotable, not a fact).

### 4.4 Revisions
A re-stated number (broker corrects last week, SEC restatement, TurkStat revision) is a new row with a later
`published_at` and `supersedes` set. Queries default to "latest known"; back-tests use "as known on D".

---

## 5. Layer B: hybrid text index

### 5.1 Sectioning
Split each MD on headings into `section` rows. Mark `boilerplate` deterministically:
- SEC: cover page, table of contents, signatures, exhibits index, certifications (302/906), forward-looking
  statement block, XBRL residue; risk factors: fingerprint (MinHash on paragraphs) across a company's filings,
  keep the first occurrence and later *changed* paragraphs only.
- Brokers: disclaimers, contact blocks, footers (hash-repeated across issues of a publisher).

### 5.2 Chunking
- Prose: 400–800 tokens on paragraph boundaries inside a section; never across sections.
- Tables: one chunk per table; long tables split every N rows **with the header row repeated** and the caption /
  heading path repeated. Never split a row.
- Dedup: normalise (lowercase, collapse whitespace, strip dates/week numbers) → sha256; a repeated chunk is stored
  once with `is_duplicate_of` (weekly reports repeat last week's commentary and tables).

### 5.3 Context prefix (deterministic, free)
`"{publisher} · {title} · {published_at} · {heading_path joined} · entities: {top tagged entities}"` — this gives
most of Anthropic's contextual-retrieval gain (−35% to −49% retrieval failures in their tests) without an LLM call.
Use an LLM-written prefix only for sections whose heading path is empty or generic (measure how many in P0).

### 5.4 Retrieval
BM25 (`tsvector` 'simple' config, or ParadeDB `pg_search`) top 150 ∪ dense (pgvector HNSW) top 150 → Reciprocal
Rank Fusion (k = 60) → reranker → top 20. Filters before ranking: publisher, doc_type, date range, entity ids.
Route codes (C5, TD3C, P1A_82), IMO numbers, tickers, vessel names are exact tokens: keep BM25 on.

### 5.5 Embeddings
`Qwen3-Embedding-0.6B` (1024 dims), same model for documents and queries, recorded in `kb.meta`. ~110M tokens
≈ $1–2 on DeepInfra, or a few GPU-hours locally. Changing the model means re-embedding everything: decide once.

---

## 6. Ontology and deterministic tagging

### 6.1 Closed type lists (the LLM can only choose from these)

**Entity types:** `vessel` (key IMO, 7 digits with check digit), `company` (CIK / LEI / internal; roles: owner,
operator, manager, charterer, shipyard, broker, miner, trader, bank, lessor), `port` (UN/LOCODE),
`route` (Baltic code per `baltic_route_taxonomy.json`), `index` (BDI, BCI, BDTI, BCTI, FBX, SCFI...),
`commodity` (`commodity_normalisation.json`), `country`, `publisher`, `person` (low priority).

**Edge types (state facts, have validity intervals):**
`OWNS`, `MANAGES`, `OPERATES`, `TIME_CHARTERED_TO {rate_usd_day, period_months, delivery, redelivery}`,
`SOLD_TO {price_usd_m, date, en_bloc}` (vessel→buyer, seller in attrs), `BUILT_BY {yard, delivered}`,
`ORDERED_AT {yard, price_usd_m, delivery, units}`, `DEMOLISHED_AT {country, ldt, price_usd_ldt}`,
`RENAMED {from, to}`, `FLAG {flag}`, `SUBSIDIARY_OF`, `LISTED_AS {exchange, ticker}`, `FINANCED_BY {lender, amount, type}`,
`FIXED {cargo, qty, load, disch, laycan, rate}` (vessel→charterer, only from narrative; fixture tables go to A).

**Event types (n-ary):** `market_move` (segment, direction, magnitude quote), `port_congestion`, `canal_disruption`
(Suez, Panama, Bosphorus, Hormuz, Red Sea), `weather`, `strike_labour`, `sanction_policy`, `regulation`
(IMO, EU ETS, CII), `trade_policy` (tariff, export ban), `production_guidance` (miner/producer guidance change),
`company_guidance`, `accident_casualty`, `newbuilding_wave`, `demolition_wave`, `other` (must be mapped later).

Every edge/event attribute that is a number is stored **as printed** (string) and parsed into a numeric attr only if
the printed string parses unambiguously; the quote must contain it.

### 6.2 Deterministic pre-tagging (before any LLM call)
- Regex: IMO (`IMO\s*\d{7}` + check digit), Baltic route codes (taxonomy list), tickers (registry), dates, money
  (`USD 26 M`, `$1.2bn`, `$/day`, `WS 65`), DWT.
- Aho–Corasick over all registry aliases (vessel names only when a corroborating attribute — DWT/built/yard — is in
  the same table row or sentence).
- Pass the tags into the extraction prompt as `known_entities`, so the LLM links and classifies instead of
  inventing ids.

### 6.3 Registry seeding
- Vessels: S&P / demolition / newbuilding tables already parsed (name, DWT, built, yard, IMO where printed),
  `benchmark_core_fleet.json`, AIS-derived voyage history (`data/geospatial/`). IMO is the key; a name alone never
  creates or merges a vessel.
- Companies: SEC `ticker/cik/company_name`, `company_tickers.json` from SEC, broker buyer/seller columns
  (aliases like "GREEKS" are *nationality groups*, not companies — keep as `country` tags).
- Ports: UN/LOCODE list + the gazetteer the cargo pipeline already uses (`load_locode`, `disch_locode`).
- Routes/indices/commodities: the reference JSONs, hard-coded, never LLM-created.

### 6.4 Resolution
Blocking + Splink (Fellegi–Sunter, DuckDB backend) on (normalised name, DWT ±2%, built year, yard, owner, date) for
vessels; (name, ticker, country) for companies. Auto-merge only above a high threshold **and** with IMO/CIK
agreement where present; the middle band goes to a cached LLM adjudication (Flash, strict tool: `same | different |
unsure` + reason); `unsure` stays separate. Every merge writes `alias.merged_by`, so it can be undone.

---

## 7. Layer C: LLM extraction with DeepSeek

### 7.1 What is sent
Only `chunk.kind = prose`, not `is_duplicate_of`, not `boilerplate`, and with at least one tagged entity or event
keyword. Expected scope: broker prose (~25M tokens before dedup), SEC narrative sections (~15–20M after boilerplate
removal), books (~2.4M). **Measure in P0**; budget assumes 30–45M tokens.

### 7.2 Call shape (maximises prefix-cache hits)
```
messages = [
  {"role":"system", "content": STATIC_PROMPT},        # ~2–3k tokens, byte-identical for the whole run:
                                                      #   rules, closed enums, Baltic route list, 6 few-shot examples
  {"role":"user",   "content": CHUNK_BLOCK}           # variable part LAST:
                                                      #   <doc publisher=… date=… heading=…> chunk text </doc>
                                                      #   <known_entities> id|type|alias … </known_entities>
]
tools = [EXTRACT_TOOL]      # identical across calls (tools are part of the cached prefix)
tool_choice = {"type":"function","function":{"name":"record_extraction"}}
model = "deepseek-flash"; base_url = "https://api.deepseek.com/beta"   # strict tool calling
extra_body = {"thinking": {"type": "disabled"}}; temperature = 0.0; max_tokens = 1500
user_id = "kb-build-<run>"  # one id for the run: the cache is isolated per user_id
```
Never put a timestamp, chunk id or file name before the static block. Warm the cache with ~20 sequential calls
before fanning out. Log `usage.prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` on every call.

### 7.3 Tool schema (strict mode: every property required, `additionalProperties:false`, enums closed)
```json
{"name":"record_extraction","strict":true,"parameters":{"type":"object","additionalProperties":false,
 "required":["state_facts","events","new_entities","no_content"],
 "properties":{
  "no_content":{"type":"boolean"},
  "state_facts":{"type":"array","items":{"type":"object","additionalProperties":false,
    "required":["type","src","dst","attrs_printed","valid_from","valid_to","quote","confidence"],
    "properties":{
      "type":{"type":"string","enum":["OWNS","MANAGES","OPERATES","TIME_CHARTERED_TO","SOLD_TO","BUILT_BY",
              "ORDERED_AT","DEMOLISHED_AT","RENAMED","FLAG","SUBSIDIARY_OF","LISTED_AS","FINANCED_BY","FIXED"]},
      "src":{"type":"string"}, "dst":{"type":"string"},
      "attrs_printed":{"type":"array","items":{"type":"object","additionalProperties":false,
         "required":["key","value_as_printed"],"properties":{"key":{"type":"string"},"value_as_printed":{"type":"string"}}}},
      "valid_from":{"type":"string"}, "valid_to":{"type":"string"},
      "quote":{"type":"string"}, "confidence":{"type":"number","minimum":0,"maximum":1}}}},
  "events":{"type":"array","items":{"type":"object","additionalProperties":false,
    "required":["type","summary","roles","when_printed","magnitude_printed","quote","confidence"],
    "properties":{
      "type":{"type":"string","enum":["market_move","port_congestion","canal_disruption","weather","strike_labour",
              "sanction_policy","regulation","trade_policy","production_guidance","company_guidance",
              "accident_casualty","newbuilding_wave","demolition_wave","other"]},
      "summary":{"type":"string"},
      "roles":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["role","entity"],
               "properties":{"role":{"type":"string"},"entity":{"type":"string"}}}},
      "when_printed":{"type":"string"}, "magnitude_printed":{"type":"string"},
      "quote":{"type":"string"}, "confidence":{"type":"number","minimum":0,"maximum":1}}}},
  "new_entities":{"type":"array","items":{"type":"object","additionalProperties":false,
    "required":["type","name","evidence_quote"],
    "properties":{"type":{"type":"string","enum":["vessel","company","port","country","person"]},
                  "name":{"type":"string"},"evidence_quote":{"type":"string"}}}}}}}
```
`src`/`dst`/`entity` must be an id from `known_entities` or a name listed in `new_entities`. Max lengths/items are
not supported by strict mode: enforce client-side (quote ≤ 40 words, ≤ 30 facts per chunk).

### 7.4 Acceptance gate (client-side, every record)
1. JSON valid against the schema (pydantic); `finish_reason == "tool_calls"`; blank content = retry (≤ 3).
2. `normalise(quote) ⊂ normalise(chunk.body)` (whitespace/quote-mark normalisation only). **Else drop.**
3. Every printed number in `attrs_printed`/`magnitude_printed` occurs in the quote. **Else drop.**
4. `src`/`dst` resolve to the registry or to a `new_entities` item with its own verified quote.
5. Dates: `valid_from`/`when_printed` must be printed in the quote or be the document's period; relative dates
   ("this week") are resolved from `published_at` by code, not by the model.
6. Confidence < 0.5, or gate 2/3 failures > 30% of the chunk's records → re-queue the chunk to **V4-Pro** once.
7. Keep every raw response in the job table so the gate can be re-run without paying again.

### 7.5 Runner (`kb/llm_runner.py`, to write)
- SQLite `jobs(chunk_sha, prompt_version, pass, status, attempts, request, raw_response, hit, miss, out, cost,
  finish_reason, error)`, unique on `(chunk_sha, prompt_version, pass)` → idempotent and resumable; commit after
  every response.
- `asyncio.Semaphore(200)` to start (limit is 2,500 for Flash, 500 for Pro); exponential backoff on 429/5xx.
- **Off-peak gate**: do not launch new calls 01:00–04:00 and 06:00–10:00 UTC Mon–Fri (IST 06:30–09:30 and
  11:30–15:30); weekends are fully off-peak. Off-peak price is half.
- **Budget guard**: live sum of `cost_usd` from the usage fields with the price table in config; hard stop at the
  cap (default $400); cross-check with `GET /user/balance` every 500 calls.
- Log the `model` string returned on every call (Flash was upgraded in place on 2026-10-17); a changed model
  string pauses the run until the eval set is re-run.
- API key from the environment (`DEEPSEEK_API_KEY`), never in the repo.

### 7.6 Gleaning
At most one extra pass, only on long narrative chunks (SEC MD&A, monthly outlooks > 600 tokens), continuing the
same conversation ("List anything in the same schema that you missed; return no_content if nothing.") — the prior
turn is a cache hit.

---

## 8. Period summaries (P6)

Segments: capesize, panamax, supramax, handysize, vlcc, suezmax, aframax, mr/lr, lng, lpg, container, snp,
demolition, newbuilding, iron_ore, coal, grains, bunkers, companies (per ticker, quarterly).
Grain tree: week → month → quarter → year. A leaf (segment × week) summary is generated from: that week's layer-A
observations (as a small table), top-k chunks for the segment and week, and the week's events; the model must cite
`obs_id`/`chunk_id`/`event_id` for each sentence and may not state a number that is not in a cited observation.
Parents summarise their children. New data regenerates only the new leaf and its ancestors.
Model: Flash for leaves; V4-Pro for quarter/year nodes (a few hundred calls).

---

## 9. Query agent (P7)

Tools exposed to the answering model (V4-Pro for quality, Flash for cheap):
`sql(query)` read-only on the `v_*` views (row limit, statement timeout); `search(query, filters)` → chunks with ids;
`graph(entity_id, window, hops≤2, types)` → edges/events with quotes; `ppr(seed_entities, window)` HippoRAG-2-style
personalised PageRank over entity–chunk–event graph; `summary(segment, grain, period)`; `cite(id)` returns the
source path, page and quote.

Answer contract: every number must equal a value in a tool result row (post-check: regex every number in the answer,
match against tool outputs with unit and rounding tolerance; mismatch → regenerate once, then return "not in the
data"). Every claim carries citations. Questions about a date use "as known on" semantics when the user asks
"what did we know".

---

## 10. Cost budget (prices fetched 2026-11-01, per 1M tokens; off-peak = half of peak)

| Model | cache hit | cache miss | output |
|---|---|---|---|
| deepseek-flash peak / off-peak | 0.006 / 0.003 | 0.30 / 0.15 | 1.20 / 0.60 |
| deepseek-v4-pro peak / off-peak | 0.044 / 0.022 | 1.32 / 0.66 | 3.96 / 1.98 |

| Pass | Volume (estimate, re-measure in P0) | Off-peak | Peak |
|---|---|---|---|
| Extraction, Flash | 30–45M chunk tokens ≈ 30–40k calls; 2.5k cached prefix + 1.1k chunk + 450 out per call | $14–20 | $28–40 |
| Gleaning (30% of calls) | ~10k calls | $2–4 | $4–8 |
| Escalation to V4-Pro (≤ 10% of chunks) | ~4k calls | $5–8 | $10–16 |
| Entity adjudication (middle band only) | ~20k short calls | $2–4 | $4–8 |
| LLM context prefixes for generic sections only | ≤ 20k calls × 100 out | ≤ $2 | ≤ $4 |
| Period summaries (19 segments × ~350 weeks + parents) | ~8k Flash + ~600 Pro calls | $10–15 | $20–30 |
| Embeddings (Qwen3-Embedding-0.6B, ~110M tokens) | DeepInfra | ~$1–2 | ~$1–2 |
| Pilot + 2 prompt iterations on 1,000 chunks | | ~$2 | ~$4 |
| **First full build** | | **≈ $40–60** | **≈ $75–110** |

Accidentally leaving thinking on adds ~1k reasoning tokens per call (+$40–80 on Flash). Running the whole
corpus including tables through the LLM GraphRAG-style on V4-Pro would cost ≈ $600+ — the entire credit — and
produce worse numbers. Hence the layer split.

---

## 11. Phases and runbook

Each phase has a script (to write under `kb/`), an output, and a gate. Do not start a phase until the previous gate
passes. All scripts are idempotent (re-runnable) and log to `kb/logs/`.

| Phase | Script | Does | Gate |
|---|---|---|---|
| **P0** inventory | `kb/p0_inventory.py` | walk inputs; hash; parse frontmatter; section split; boilerplate marks; dedup; **token counts with the DeepSeek tokenizer**; report per publisher/doc_type | R3, R4, R7 pass; token report written; owner reviews scope numbers |
| **P1** database | `kb/schema.sql`, `kb/p1_load_docs.py` | create schema; load `document`, `section` | row counts = P0 report |
| **P2** facts | `kb/p2_series.py`, `kb/p2_sec_xbrl.py`, `kb/p2_tables.py` | load series CSVs, XBRL companyfacts, remaining tables | every observation has `raw_cell` found in its source (sample 1,000 + all SEC); spot-check 50 numbers against PDFs; `v_*` views answer 30 known values exactly |
| **P3** registry | `kb/p3_registry_seed.py`, `kb/p3_resolve.py` | seed entities/aliases; Splink resolution; tag chunks | precision ≥ 0.98 on 300 hand-checked vessel merges; zero merges without IMO agreement where both have IMO |
| **P4a** chunks + index | `kb/p4_chunk.py`, `kb/p4_embed.py` | chunks, prefixes, tsvector, embeddings | retrieval recall@20 ≥ 0.85 on the retrieval part of the gold set (§12) |
| **P4b** pilot | `kb/llm_runner.py --pilot 500` | 500 stratified chunks (publisher × doc_type × year) | schema-valid ≥ 98%; quote-verified ≥ 90% of records; cache-hit ratio ≥ 60% of input tokens; human audit of 100 records: wrong-fact rate ≤ 3%; measured cost per 1k chunks × scope ≤ budget |
| **P4c** full extraction | `kb/llm_runner.py --all` (off-peak) | all in-scope chunks | budget not exceeded; failure queue < 2%; second audit of 200 random records ≤ 3% wrong |
| **P5** graph build | `kb/p5_edges.py` | gate → `edge`/`event`; attach to registry; state-fact intervals; PPR graph export | no edge without verified quote; no dangling entity ids |
| **P6** summaries | `kb/p6_summaries.py` | week → year tree per segment | every number in a summary matches a cited observation (automatic check) |
| **P7** agent | `kb/agent.py` (+ simple web UI or the dashboard later) | tools + answer contract | eval (§12) thresholds met |
| **P8** incremental | `kb/update.py` in CI after the ingest workflows | new MDs/series only | weekly cost < $1; eval re-run on prompt/parser change |

Order of work for the owner: P0 → P1 → P2 (biggest value, no LLM cost) → P3 → P4a → **P4b pilot (≈ $1)** → review
→ P4c → P5 → P6 → P7. P2 alone already answers most numeric questions exactly.

---

## 12. Evaluation (build the gold set before P4)

- 200 questions, written from the data, each with exact answer and source ids:
  (a) single number ("BCI C5 on 2026-03-13", "Fearnleys VLCC MEG–China WS on week 12 2026") — 50;
  (b) window aggregate ("average TD3C in Q2 2026") — 25;
  (c) multi-hop entity ("which buyers took the most Capesize resales in 2025 and what did they pay") — 30;
  (d) event → market ("how did C3 move in the two weeks after the 2026 Simandou start-up was reported") — 25;
  (e) SEC ("Star Bulk 2025 net income", "Scorpio Tankers fleet at end-2024") — 30;
  (f) summary/trend ("what drove Supramax rates in H1 2026 according to the brokers") — 20;
  (g) unanswerable / out of range (must refuse) — 20.
- Synthetic, unlimited: random `observation` rows → generated question with known answer; random verified edges →
  "who bought X in month Y". Use to catch regressions.
- Metrics: exact match with unit for (a)(b)(e) (target ≥ 95%); retrieval recall@20 and MRR (target ≥ 0.85);
  multi-hop F1 (target ≥ 0.75); refusal accuracy on (g) ≥ 90%; faithfulness (every sentence supported by a cited
  id) ≥ 95% by automatic check + 50 human-graded; cost and latency per question.
- Judge for (f) with a different model from the generator.

---

## 13. Incremental updates (P8)

Weekly CI (after `orchestrate_incremental_ingest.py` and the series writers): new/changed MDs by sha → P1 rows; new
series rows → observations (revisions as new rows); new prose chunks → embed + extract (cache by chunk sha, so
re-runs cost nothing); resolver on new aliases; regenerate only the new week leaf + ancestors per segment; re-run the
synthetic eval subset. Expected: a few hundred calls per week, < $1.

---

## 14. Risks and how the plan handles them

| Risk | Handling |
|---|---|
| Invented numbers | Numbers only from parsers/XBRL/CSVs; LLM output numbers must be inside a verified quote; answer post-check |
| DeepSeek JSON reliability | Strict tool calling on `/beta`; pydantic; blank-content retry; pilot measures failure rate first |
| Cache misses inflate cost | Static prefix first and byte-identical; tools identical; one `user_id`; warm-up; hit ratio is a pilot gate |
| Token count larger than estimated | P0 measures with the real tokenizer; runner budget cap; scope can drop SEC risk factors / repeated commentary |
| Wrong vessel merges | IMO required to merge where present; name alone never merges; undoable alias table; precision gate |
| Temporal confusion (publication vs period vs laycan) | Separate columns; relative dates resolved by code from `published_at` |
| Model swapped under the same name | Model string logged per call; change pauses the run |
| Framework churn | Canonical data lives in our own Postgres schema; any framework is a replaceable view |
| Peak pricing | Off-peak gate in the runner |
| Data drift after the build | P8 incremental path; validators and the knowledge validator stay the gate for inputs |

---

## 15. What not to do

- Do not run Microsoft GraphRAG / LightRAG over the whole corpus, and never let any framework ingest the tables.
- Do not embed and "regenerate" numbers; do not let the LLM read table cells.
- Do not use chart images or estimates (house rule: chart-image numbers never ship).
- Do not leave `thinking` enabled; do not run during peak hours; do not change the prompt mid-run.
- Do not merge entities on name similarity alone.

---

## Sources (fetched 2026-11-01)

DeepSeek: pricing https://api-docs.deepseek.com/quick_start/pricing · rate limits
https://api-docs.deepseek.com/quick_start/rate_limit · context caching https://api-docs.deepseek.com/guides/kv_cache ·
JSON mode https://api-docs.deepseek.com/guides/json_mode · strict tool calls
https://api-docs.deepseek.com/guides/tool_calls · thinking https://api-docs.deepseek.com/guides/thinking_mode ·
changelog https://api-docs.deepseek.com/updates · Harness https://github.com/deepseek-ai/deepseek-harness ·
dsh-superagent https://github.com/deepseek-ai/dsh-superagent-prototype (the X post linked by the owner could not be
fetched: HTTP 402).
Methods: Microsoft GraphRAG https://github.com/microsoft/graphrag · LazyGraphRAG
https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/ ·
LightRAG https://github.com/HKUDS/LightRAG · HippoRAG 2 https://arxiv.org/abs/2502.14802 · KAG
https://github.com/OpenSPG/KAG · Graphiti/Zep https://arxiv.org/abs/2501.13956 · TG-RAG
https://arxiv.org/abs/2510.13590 · LinearRAG https://arxiv.org/abs/2510.10114 · GraphRAG-Bench
https://github.com/GraphRAG-Bench/GraphRAG-Benchmark · Contextual Retrieval
https://www.anthropic.com/news/contextual-retrieval · T²-RAGBench https://arxiv.org/html/2506.12071v1 ·
SEC EDGAR APIs https://www.sec.gov/search-filings/edgar-application-programming-interfaces · Splink
https://github.com/moj-analytical-services/splink · RAGAS https://docs.ragas.io · Kuzu archived
https://www.theregister.com/2025/10/14/kuzudb_abandoned/ · Apache AGE 1.7.0.1
https://www.enterprisedb.com/docs/pg_extensions/apache_age/rel_notes/apache_age_1.7.0.1_rel_notes ·
Qwen3-Embedding https://deepinfra.com/Qwen/Qwen3-Embedding-0.6B.
