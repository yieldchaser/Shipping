# GraphRAG brief: what we have and what we want

A brief for anyone (human or AI) asked to design the knowledge graph / GraphRAG layer of this repository.
It states the goal, the material and the constraints. It does not prescribe a design: that is what we are asking for.
All figures below were measured from the repository on 2026-11-08.

## The ask

Design the best retrieval and knowledge-graph system that can be built over this maritime / shipping corpus.

- **Built once.** We will do one full build, carefully, not a series of experiments. Then it must stay current.
- **New material flows in by itself.** Scrapers and parsers already run on GitHub Actions (daily / weekly / monthly)
  and add new reports, filings and data points. Whatever is built must take new files (and new rows of numbers)
  incrementally, without a rebuild and without a person in the loop.
- **Questions it should answer well** (examples, not a spec): how freight rates, asset prices and fleet supply moved
  together over a period and what the brokers said caused it; what every source said about one vessel, company,
  route or event; how a listed owner's own filings line up with broker commentary and market data; long-horizon
  structural questions drawing on the books; exact numbers ("TD3C TCE in week 40 2025") with their source.
- **Faithfulness first.** Every fact, number and relation must be traceable to the document (and ideally the
  passage or table cell) it came from. A plausible but unsupported answer is worse than "not in the corpus".

Research freely (current GraphRAG / hybrid / agentic / temporal-graph approaches, papers, open-source projects,
what has worked in finance or other domains with dense numbers). Propose what you think is genuinely best, with
reasons, costs and risks. Then say how you would build it here, step by step, and how you would know it works.

## What we have

Three kinds of material: prose and tables in Markdown, structured numeric series, and the source files.

| Material | Where | Files | Size | Notes |
|---|---|---|---|---|
| Broker / market reports, parsed | `data/extracted/md/<publisher>/` | 19,329 MD | 149 MB | 23 publishers, 2004 → this week |
| Per-report tables (JSON sidecars) | next to the MDs, `*.tables.json` | 6,142 | | sale & purchase deals, fixtures, rate tables, commentary by sector |
| SEC filings of 25 listed shipping / mining issuers | `corpus/10-companies/<TICKER>/<FORM>/` | 1,364 MD | 247 MB | 10-K, 10-Q, 20-F, 6-K, 8-K (+ EX-99 exhibits); heavy in tables |
| Books (maritime economics, finance, history) | `corpus/books/` | 12 MD (+ PDF) | 10 MB | Stopford, Kavussanos & Visvikis, Paine, Harlaftis et al., Duru, ... |
| Numeric time series | `data/extracted/series/` | 166 CSV | 727,192 rows | freight indices, routes, TCEs, asset prices, S&P, fleet, bunkers ... |
| Raw source files (PDF / HTML / images) | `corpus/01-brokers ... 11-other` | | | the originals every MD was parsed from |

Roughly 105-110 million tokens of Markdown in total; a large share of it is tables, not prose.

Broker MD counts by publisher (date range of file dates where present):
Fearnleys 5,067 (2018-09 → 2026-11) · Breakwave 3,549 (2018-07 → 2026-11) · Hellenic 2,769 (2021-07 → 2026-11) ·
Baltic Exchange 2,254 (2015-01 → 2026-11) · Poten 1,093 (2004-01 → 2026-10) · Drewry 864 (2017-11 → 2026-11) ·
SSY 527 · Signal Ocean 458 · Xclusiv 268 · Gibson 265 · Intermodal 260 · Advanced Shipping 256 · Affinity 253 ·
Banchero Costa 252 · Agora 217 · Star Asia 201 · Fearnleys app 189 · Clarksons 184 · Carriers 137 · ISM 114 ·
Seabrokers 99 · Lion 52.

SEC issuers: ASC BHP CTRM DHT DSX ECO EDRY FRO GLBS GNK GOGL INSW LPG NAT NVGS RIO SB SBLK SFL SHIP STNG TNK TNP TRMD VALE.

### How the material looks

- Every MD starts with YAML frontmatter: publisher, source, `issue_date`, source file and its sha256, parser and
  version, and per-publisher fields (e.g. report week, deals parsed / unparsed). SEC MDs carry ticker, CIK, form,
  filing date, accession number and the exhibit list.
- Reports mix narrative commentary (by sector: dry bulk, tankers, gas, containers, S&P, newbuilding, demolition)
  with tables (fixtures, deals, rate grids). Charts are referenced by title and source line; chart images are not
  turned into numbers unless the figure is printed.
- The same entities recur everywhere under varying names: vessels (with built year / DWT / yard), owners and
  buyers (often "undisclosed" or nicknamed), ports, routes with Baltic codes (C5, P1A, TD3C ...), indices, cargoes,
  events.
- Series CSVs are long-format (date, series / route, value, unit, source file); they are built from the MDs and
  sidecars and are the authoritative numbers.
- `corpus/CORPUS_REGISTRY_AND_CADENCE_AUDIT.md` lists every source, its publication cadence and freshness;
  `docs/PRE_GRAPHRAG_OPEN_ITEMS.md` lists known data-quality limits; `corpus/RAG_SYSTEM_EVOLUTION_AND_KNOWLEDGE_ARCHITECTURE.md`
  describes the earlier flat RAG (`knowledge/`, legacy, not an input).

### Quality rules already in force

- Only printed values are stored: nothing estimated, read off a chart image or invented by a parser.
- Known gaps are documented rather than filled (e.g. partner-country trade shares stop at 2026-08: no source).

## Constraints

- **LLM budget:** about USD 145 of API credit on one router (OpenAI-compatible API) with these models
  (USD per 1M input / output tokens): GPT-OSS 120B 0.10 / 0.50 (131k ctx) · DeepSeek V4 Flash 0.13 / 0.26 ·
  GLM 5.3 Flash 0.15 / 0.50 · DeepSeek V4.1 Flash 0.30 / 1.20 · MiniMax M3 0.30 / 1.20 · Nemotron 3 Ultra
  0.60 / 2.40 · Mistral Large 4 0.75 / 2.30 · DeepSeek V4 Pro 1.32 / 3.96 · GLM 5.3 1.40 / 4.40 · Qwen 3.8 Max
  2.00 / 6.00 · Kimi K3 2.70 / 13.50 (most with ~1M context). The router has closed new sign-ups, so the credit
  should be used soon, and a run must survive interruption (checkpointing / resumable).
- **Machine:** Windows 11 laptop, Intel i3-1215U, 8 GB RAM, no discrete GPU, ~40 GB free disk. Anything local
  (embeddings, graph database, reranker) must fit that, or use free hosted options.
- **Repository is public.** No keys, tokens or personal contact data may be committed; keys stay in environment
  variables.
- **Automation:** GitHub Actions free runners (time limits per job; crons run hours late). Incremental updates
  should be able to run there or on this laptop.
- **One owner,** no team: operation must be simple and self-checking.

## What we would like back

1. The architecture you recommend (and the main alternatives you rejected, with why), including how prose,
   tables and the numeric series are each handled, and how entities are resolved across sources and time.
2. Tools / libraries / storage you would use, and why they fit the constraints above.
3. A cost and time estimate for the one-time build within the budget, and for each weekly update.
4. How new files and new series rows enter the graph incrementally, and how a wrong extraction is corrected later.
5. How quality is measured before and after the full build (a small pilot first?), and what "good enough" means.
6. The risks you see, and what you would not do.
