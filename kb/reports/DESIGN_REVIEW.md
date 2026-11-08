# Design review — GraphRAG build plan

Reviewed against: `docs/GRAPHRAG_BUILD_PLAN.md` (§0–§16), `docs/GRAPHRAG_AGENT_TASK.md` (§0–§11),
`docs/GRAPHRAG_BRIEF.md`, `docs/PRE_GRAPHRAG_OPEN_ITEMS.md`, `kb/gates.yaml`, and the six review docs in
`docs/Recommendations/`. Date: 2026-11-08. Author: build agent (deepseek-v4-pro).

This review attacks the plan, lists where it can produce wrong answers or miss facts, lists cheaper
same-quality paths, and records every change adopted. No gate in `kb/gates.yaml` is lowered; no scope is
narrowed; no frozen file is edited. Changes that touch the DDL are recorded here as "names adjusted once
before P1" (allowed by plan §3).

---

## 1. What the plan gets right (do not touch)

- **Numbers never pass through the LLM.** Layer A from CSVs/XBRL/parsers only; every LLM number must sit in a
  code-sliced quote (§7.4). This is the single strongest correctness guarantee in the design.
- **P2 before any LLM spend.** Most numeric questions are answered for $0; this is why the $97 pipeline cap is
  credible.
- **Bitemporal observations** (`period_from/period_to` valid time vs `published_at` knowledge time) with
  `supersedes` revisions — this is what makes "as known on D" answerable at all.
- **Identity from keys, never names alone.** IMO/CIK/Baltic/LOCODE plus Splink with key gating and an undoable
  `merge_log`.
- **Canonical transactions vs mentions (D9)** — prevents "same deal counted six times".
- **`corpus_known_gaps`** — turns "not in corpus" into a first-class, citable answer instead of a hallucination.
- **Ledger-first resumability, single prompt/model per pass, drift guard (`model_returned`).**
- **Exact (not ANN) vector search + BM25 + RRF + rerank** — correct for this corpus size on 8 GB.

The six review docs converge on exactly these points and the plan has absorbed them (§16). No objection.

---

## 2. Where the plan can produce wrong answers or miss facts

### 2.1 Dedup masks numbers, silently dropping real changes  *(riskiest — adopt fix)*

§5.2 dedups by `norm_sha` = sha of the body **with numbers and dates masked**. §5.1 separately keeps SEC risk
factors whose paragraphs "changed later (MinHash, Jaccard < 0.8)".

The conflict: a paragraph whose **only** change is a number — e.g. an operating-review line "orderbook stands at
8% of fleet" becoming "9% of fleet", or a boilerplate block with a changed threshold — has an identical
`norm_sha` before and after. Number-masked dedup will mark the later one `is_duplicate_of` the first and **the
changed fact is dropped**, with no signal it ever existed.

Worse, 39% of SEC prose and 29% of broker prose are already measured as "repeats"; if any meaningful fraction of
that repeat rate is numeric-only drift, a measurable share of the factual drift in the corpus is silently lost.

**Fix (adopted):** deduplication uses **two keys**.
- `norm_sha_no_nums` (numbers/dates masked) only for sections classified `boilerplate` (disclaimers, contact
  blocks, footers, certifications, TOC) — where a numeric change is immaterial.
- `norm_sha_strict` (numbers preserved, case/whitespace normalised only) for prose sections (`business`,
  operating review, MD&A, press release, fleet, subsequent events, market commentary).
- A chunk is a duplicate only when its own key matches. The masked key is never used on fact-bearing prose.
- Consequence is recorded in `meta` so the dedup rate is re-measured and reported (it will be *lower* than the
  39%/29% headline; that lower number is the honest one).

### 2.2 Dedup collapses provenance, breaking "what did every broker say"

§5.2 stores a repeat once and points later occurrences to the first via `is_duplicate_of`. If five brokers
reprint the same syndicated paragraph, the answer layer can cite only one `doc_id`. The end-goal (task §0)
explicitly needs "what did every broker say about Simandou before and after start-up" — the *breadth* is the
measure of success.

**Fix (adopted):** add `chunk_source(doc_id, chunk_id, ord, PRIMARY KEY(doc_id, chunk_id))` listing every
document whose text maps to a canonical chunk. Dedup still saves embedding/extraction cost exactly once, but the
query agent answers "every broker" by enumerating `chunk_source`, and `cite()` shows the full source list.

### 2.3 XBRL `companyfacts` returns restated values, breaking "as known on D"

§4.3 says each XBRL fact becomes an observation. SEC's `companyfacts` endpoint returns, per `(concept, unit,
period)`, the **frames from every amended filing** — each with its own `accn`, `filed`, and `val`. A number
restated in 2025 for a 2024 period sits beside the original 2024 print. If the loader collapses to "latest
`filed`", a query "what was 2024 Q3 net income, as known on 2024-11-01" returns the restatement, which was not
knowable then.

**Fix (adopted):** keep every frame, not just the latest. Store `as_filed` (the frame with the earliest `filed`
for the period) and `as_restated` (the latest), keyed by `accn`. The as-known-on-D tool filters on
`filed <= D`; the latest-known default uses the latest `filed`. The "25 SEC text-only files" from the
merged-cell detector remain quotable text, never facts (§4.3 already correct).

### 2.4 Chart-derived vs reported provenance is asserted, not enforced

§4.1 names `provenance` including `chart_derived` and says such rows are "excluded from answers unless asked for
explicitly." But nothing in the loader *proves* a series is chart-derived vs reported; the flag is trusted to be
set correctly on every one of 168 CSVs. A single mislabeled chart-derived series (a number that came from a
graph's pixel estimate, not a printed figure) would enter answers as a hard fact.

**Fix (adopted):** `series_map.yaml` carries an explicit `provenance` field per series with one of
`reported_table | xbrl | parser_text | computed | chart_derived`, and the audit gate P2 additionally asserts the
`chart_derived` allowlist is exactly the set named in the cadence audit (gibson spot-chart daily, and the known
unlabelled-chart estimates already deleted per `PRE_GRAPHRAG_OPEN_ITEMS`). A series not on the allowlist may not
be loaded as `chart_derived`. This raises trust with zero new LLM cost.

### 2.5 Commodity → route through vessel_class alone produces false links

Capability #1 (task §0) demands "Brazilian iron ore exports → C3 → Capesize → Star Bulk." The natural
deterministic joins are: commodity → **load/discharge country+port** (from parsed fixture/flow tables and AIS)
and route → load/discharge (from the Baltic route taxonomy text, e.g. "C3 = Tubarao→Qingdao"). Both exist.
But `commodity_normalisation.json` maps commodity → `vessel_class`, and `baltic_route_taxonomy.json` maps route →
`vessel_class`. Routing the link *through* `vessel_class` would claim "iron ore → C3" merely because both are
Capesize, which also false-links iron ore to C5 (West Australia→Qingdao) with equal confidence.

**Fix (adopted):** the cross-domain link map is built only on **nameable terminals** — country and port — plus
`vessel_class` as a *property, not a link*. `vessel_class` participates only as a filter/bridge, never as the
sole justification for a commodity→route edge. Load/discharge ports come from parsed tables and the AIS/LOCODE
gazetteer, never from the LLM.

### 2.6 The six required capabilities have no schema home in the plan DDL

This is the largest structural gap. Task §0 lists six capabilities and §0.1 requires the review to "say exactly
where each lives and how it is tested." The plan DDL (§3) stops at `series/observation/transaction/mention/
edge/event/claim/period_summary/corpus_known_gaps/meta`. There is **no table** for:

- computed series relationships (#2),
- the market-state snapshot (#3),
- forecast→outcome matching (#4),
- cycle indicators (#5),
- book principles (#5),
- discovered links (#6).

`discovered_link` is named in the task but absent from the plan; `forecast` exists as a `claim.kind` value but
there is no table to match a forecast to the layer-A outcome it did or did not predict.

**Fix (adopted):** add the following tables before P1 (DDL "adjusted once before P1" per §3 is exercised here):

```sql
CREATE TABLE computed_relationship (rel_id VARCHAR PRIMARY KEY, a_series VARCHAR, b_series VARCHAR,
  method VARCHAR,              -- corr | lead_lag | coint | event_study
  window VARCHAR, lag_days INT, rho REAL, p_value REAL, fdr_q REAL, n INT,
  in_sample_from DATE, in_sample_to DATE, out_of_sample_from DATE, out_of_sample_to DATE,
  oos_rho REAL, oos_sign_matches BOOL, label VARCHAR DEFAULT 'computed', evidence_ids VARCHAR[]);
CREATE TABLE cycle_indicator (indicator_id VARCHAR PRIMARY KEY, segment VARCHAR, name VARCHAR,
  value REAL, period DATE, percentile REAL, history_range VARCHAR, method VARCHAR, computed_at TIMESTAMP);
CREATE TABLE market_state_snapshot (snapshot_id VARCHAR PRIMARY KEY, segment VARCHAR, as_of DATE,
  latest_rate JSON, trend JSON, orderbook_fleet JSON, open_events VARCHAR[], broker_view JSON,
  freshness_days INT, built_at TIMESTAMP, cited_ids VARCHAR[]);
CREATE TABLE forecast_outcome (claim_id VARCHAR PRIMARY KEY, forecast_value VARCHAR, observed_value REAL,
  observed_series VARCHAR, observed_at DATE, realised BOOL, error REAL, method VARCHAR,
  FOREIGN KEY (claim_id) REFERENCES claim(claim_id));
CREATE TABLE book_principle (principle_id VARCHAR PRIMARY KEY, book_doc_id VARCHAR, principle TEXT,
  tags VARCHAR[], chunk_id VARCHAR, sids INT[], quote VARCHAR NOT NULL);
CREATE TABLE discovered_link (link_id VARCHAR PRIMARY KEY, a VARCHAR, b VARCHAR, kind VARCHAR,
  method VARCHAR, p_value REAL, fdr_q REAL, n INT, window VARCHAR, oos_checked BOOL, oos_result VARCHAR,
  evidence_ids VARCHAR[], label VARCHAR DEFAULT 'computed', status VARCHAR);
```

These are additive. No existing table or gate changes.

### 2.7 Analyst-mode and computed relationships are trust-critical but loosely specified

Capability #5 (analyst mode) rests on *computed* cycle indicators (earnings percentile, asset P/E = secondhand
price ÷ annual TCE, newbuild–secondhand–scrap spread, orderbook ÷ fleet, fleet age). Every one of these numbers is
derived, not printed. If they are not stored with their denominator, window, source series and sample, "is the
tanker market overheated" degenerates into an un-auditable opinion.

The plan gates the *discovery pass* (#6) for FDR and out-of-sample, but the *computed relationships* (#2) — the
"non-obvious connections the owner wants surfaced" — carry no equivalent discipline in the plan.

**Fix (adopted):** capability #2 and every analyst-mode cycle indicator inherit the same discipline as #6:
FDR control, minimum sample, and an out-of-sample check, all recorded in `computed_relationship` /
`cycle_indicator`. A computed number that cannot state its method, window and sample size is not surfaced.
This is a consistency rule, not a new gate: the existing FDR gate (0.10) and OOS-check gate already exist for #6
and are applied uniformly.

### 2.8 SEC `item` coverage gate measures the wrong population for correctness

§5.1 gates "≥ 95% of 10-K/20-F files have item_5/item_7 found, measured on the 25 largest filers." Good for
coverage, but the harder cases are the 26 stacked-table files and 9 PDF-origin single-line exhibits named in
`PRE_GRAPHRAG_OPEN_ITEMS` — a few of which are among the largest filers (VALE, RIO, BHP). The plan's §4.3 already
correctly demotes them to "text only, never facts." No change needed, but **this review records the dependency**:
P2's "all SEC raw_cell found" must not silently fail or skip these 26 files — they must appear in the P2 report
explicitly as "excluded from facts, searchable text only, per open-items".

### 2.9 Period-summary month leaves can miss a one-off weekly spike

§8 skips weekly leaves ("weekly questions go straight to layer A and B"). A single anomalous week (a canal
disruption, a strike) is diluted by a month aggregate and, if the top-chunk retrieval de-ranks that week's prose,
the month leaf can omit it. Low-probability but high-value for "why a market moved."

**Fix (adopted, no cost):** a month-leaf builder appends the top *event* rows in that month (from the `event`
table) to its evidence set even when no chunk in the top-k cites them, so an event is never invisible in a month
summary. Faithfulness gate (every sentence cites an id) still applies, unchanged.

### 2.10 The 11 duplicate-MD groups must be deduplicated at the document layer

`PRE_GRAPHRAG_OPEN_ITEMS` Blocker 2 records 11 byte-duplicate MD groups. The transaction/mention model (D9)
handles *deal* double-counting, but duplicate **MDs** would still double-count chunk scope, embedding and
extraction spend, and inflate "every broker said X" source counts (§2.2). 

**Fix (adopted):** P0.5 normalisation computes `doc_id` from MD bytes (first 16 hex of sha256, already §3), which
canonicalises exact duplicates to one document automatically; `chunk_source` (§2.2) then lists each path that
carried it. No corpus file is edited; the duplicate source paths are recorded, not deleted.

---

## 3. Cheaper paths to the same or better quality

The plan is already cost-frugal (cheapest bulk model that meets precision ≥ 0.92; free Ultrafast where the same
model exists; no local LLM; embeddings on free runners; exact search). The following are the only material
savings left, and each **keeps** quality:

1. **Adjudicate the P3 middle band only** (already the plan: "middle band only"). Keep it: do not let the
   adjudication cache grow to full-pair review.
2. **Reserve escalation for the top of the confidence-fail spectrum.** Rule 6 already caps escalation at the
   chunk level; add a pass-level stop when escalation share would exceed the $17 cap *before* it is spent, so a
   pathological provider never burns the reserve. (Cost discipline, not a gate.)
3. **Do not pay to embed `boilerplate` or deduplicated chunks** — dedup (§2.1) already excludes them from
   `extract`; extend the same skip to the embed matrix so runner time is not spent on footers.
4. **Reference labels for the bake-off use the free Ultrafast tier where available** for the *second* family, so
   the $7 bake-off budget is spent on the pro-tier family only.
5. **XBRL-first SEC** already removes the most expensive table-parsing LLM temptation: keep the deterministic
   parser, never let the LLM read cells (the plan already forbids it; this is a confirmation, not a change).

No cheaper path is adopted that would weaken a gate. Money released by a cheaper bulk model flows to escalation
and reserve exactly as §10.3 states.

---

## 4. Where each required capability lives, and how it is tested

| # | Capability | Lives in | Built from | Tested by |
|---|---|---|---|---|
| 1 | Cross-domain link map | `entity` + `edge` + deterministic `commodity→country/port→route` joins; `vessel_class` as property only | reference seeds + parsed tables + AIS/LOCODE (never LLM) | synthetic "hop" probes: Brazil-iron-ore→C3→Capesize→owner→ticker; sampled link audit at P3 |
| 2 | Computed series relationships | `computed_relationship` | layer-A observations only | FDR ≤ 0.10, min n, OOS sign-match; sampled in the C2 report |
| 3 | Market-state snapshot | `market_state_snapshot` + `cycle_indicator` | latest observations + top chunks + open events + broker views | freshness reported per segment; number check = cited id |
| 4 | Forecast ledger | `forecast_outcome` (join `claim.kind='forecast'` → matched observation) | layer-A outcome vs printed forecast | "who called it right" spot list; matched-measurable rate reported |
| 5 | Analyst mode + book principles | `cycle_indicator` + `book_principle` + forecast ledger + snapshot | computed indicators, cited book rules, track record | 30 analyst Qs (rubric ≥ 0.80), 20 backtest dates, hit rate reported honestly |
| 6 | Discovery pass | `discovered_link` | all-pairs lead/lag, event studies, graph bridges, cross-domain claims | FDR ≤ 0.10, OOS check, ≥ 3-hop discovery Qs (F1 ≥ 0.70); top 30 in C2 |

---

## 5. Changes adopted (summary)

1. **Two-key dedup** — masked key for boilerplate only; strict key for prose, so numeric-only drift is never dropped (§2.1).
2. **`chunk_source`** provenance table — dedup still costs once, "every broker said" still enumerates all sources (§2.2).
3. **XBRL `as_filed`/`as_restated`** split, every frame kept, as-known-on-D uses `filed <= D` (§2.3).
4. **Chart-derived allowlist enforced from `series_map.yaml`**, cross-checked in P2 (§2.4).
5. **Cross-domain joins on country/port, not vessel_class** (§2.5).
6. **Six new tables** for capabilities #2–#6 (§2.6).
7. **FDR/OOS discipline extended uniformly** to computed relationships and cycle indicators (§2.7).
8. **26 text-only SEC files** reported explicitly in P2 as "excluded from facts", never silently skipped (§2.8).
9. **Month summaries always include that month's events** (no cost) (§2.9).
10. **Document-level dedup via sha-derived `doc_id`**, with source paths preserved in `chunk_source` (§2.10).

No gate in `kb/gates.yaml` was lowered. No frozen file was edited. No scope was narrowed. The changes are
additive schema, deterministic loader behaviour, and consistency rules; none increase LLM spend beyond the
already-budgeted caps, and two (#1, #3) reduce the risk of *wrong* answers rather than their cost.

## 6. Open questions carried into P0/P0.5 (not blocking)

- Exact repeat-rate split (boilerplate vs numeric-drift) to be measured at P0.5 and reported; this *may* raise the
  honest dedup-adjusted coverage number.
- Whether the router reports cached-token usage (P-1 probe) — this decides packing but not correctness.
- Confirmation of the `chart_derived` allowlist against the cadence audit's per-series notes before P2.
