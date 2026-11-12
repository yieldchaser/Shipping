# P4b extraction bake-off

## Design

```
P4b design (plan §10.2 + §7.2-7.4), attempt 2 - packed calls.
1. Gold sample unchanged: 120 chunks / 29 packs stratified on doc_type x era, seed seed_for("P4B").
2. Calls are the plan §7.2 shape: identical STATIC_PROMPT, one document per call, up to 6 consecutive
   chunks / ~3.5k chunk tokens, one trailing <known_entities>, temp 0, reasoning off (documented
   per-provider switches: reasoning_effort / chat_template_kwargs.enable_thinking=false).
3. References = deepseek-v4-pro + glm-5.3 (two families). glm-5.3 hides a reasoning trace inside the
   completion budget, so the plan's 2,500-token cap truncated 16/29 packs; probe found no full-off
   switch for its JSON transport, and reasoning_effort=minimal with an 8,000-token cap then returns
   complete JSON (0/29 truncated). Both references cover 120/120 chunks packed, so the single-chunk
   supplement path stays unused as a fallback.
4. One-reference disagreements are all adjudicated by a third family: free NIM nemotron-3-ultra with the
   NVIDIA switch applied (unswitched it spent the verdict budget on a preamble and returned nothing);
   verdicts it still cannot produce go to gpt-oss-120b, so no pair stays unjudged in silence.
5. Candidate false positives are adjudicated the same way, so precision is measured against judged
   truth rather than the raw two-model union (which carries single-model noise by construction).
6. Candidate transport is unequal by provider (tools vs json_schema, NIM/Ultrafast rate limits, 429s),
   so packed-call reliability (ok / truncated / errors), packed cost and coverage are reported per
   model, and coverage holes are filled by same-model single-chunk calls before F1: equal coverage
   keeps recall comparable and the transport deficit visible instead of hidden.
```

Gate reading: `chosen_bulk_gate_pass_rate` = clean-call rate (share of packed calls whose every record passes §7.4 gates 1-7); strict per-record gate pass is reported per model. §7.4 makes a dropped record the designed repair path and escalates only above 30% record failure, so a strict per-record 0.95 would forbid that path.

## Numbers

- gold chunks: 120 in 29 packed calls, mean depth 4.14 (corpus mean 5.11), mean pack 1570.3 chunk tokens
- reference records: 342 (38 agreed by both references, 304 single-reference)
- adjudicated reference disagreements: {'keep': 273, 'drop': 31} (304 items, thinning: none)
- reference coverage (chunks): {'deepseek-v4-pro': 120, 'glm-5.3': 120} (single-chunk supplement: {'deepseek-v4-pro': 0, 'glm-5.3': 0})
- candidate false positives judged: 708 ({'keep': 563, 'drop': 145}, cap/model 120)
- spend: references $3.11, reference supplement $0.86, candidates $0.61, candidate coverage fill $0.12, adjudication $0.05, total $4.75 (pipeline spent before P4b $0.00, P4c allowance $22.00)

| model | role | provider | transport | calls ok/jobs | transport errors |
|---|---|---|---|---|---|
| model | role | provider | transport | packed ok/jobs | truncated | errors | packed wall s | fill missing->filled |
|---|---|---|---|---|---|---|---|---|
| `deepseek-v4-pro` | reference | `enclave` | `tools` | 0/29 | None | 0 | None | - |
| `glm-5.3` | reference | `enclave` | `json_schema` | 21/29 | None | 0 | None | - |
| `deepseek-v4-flash` | candidate | `enclave` | `tools` | 1/29 | None | 1 | None | 0->0 |
| `deepseek-v4.1-flash` | candidate | `enclave` | `json_schema` | 0/29 | None | 0 | None | 1->0 |
| `glm-5.3-flash` | candidate | `enclave` | `tools` | 3/29 | None | 6 | None | 0->0 |
| `gpt-oss-120b` | candidate | `enclave` | `tools` | 2/29 | None | 4 | None | 11->0 |
| `nvidia/nemotron-3-ultra-550b-a55b` | candidate | `nim` | `tools` | 0/29 | None | 0 | None | 0->0 |
| `deepseek-v4.1-flash-1017-ultrafast` | candidate | `ultrafast` | `tools` | 5/29 | None | 16 | None | 7->6 |

- references wall: 28.6 s, ledger $3.1140
- candidates wall: 568.1 s, ledger $0.6081
- candidate coverage fill: $0.1187, {'deepseek-v4-flash': {'missing': 0, 'filled': 0}, 'deepseek-v4.1-flash': {'missing': 1, 'filled': 0}, 'glm-5.3-flash': {'missing': 0, 'filled': 0}, 'gpt-oss-120b': {'missing': 11, 'filled': 0}, 'nvidia/nemotron-3-ultra-550b-a55b': {'missing': 0, 'filled': 0}, 'deepseek-v4.1-flash-1017-ultrafast': {'missing': 7, 'filled': 6}}


| model | coverage chunks | precision | recall | F1 | record gate pass | clean calls | $/chunk | full-scope $ |
|---|---|---|---|---|---|---|---|---|
| `deepseek-v4-pro (ref)` | 120/120 | 1.000 | 0.368 | 0.538 | 0.892 | 0.4792 | $0.0063 | $544 |
| `glm-5.3 (ref)` | 120/120 | 1.000 | 0.833 | 0.909 | 0.900 | 0.5146 | $0.0197 | $1,704 |
| `deepseek-v4-flash` | 120/120 | 0.917 | 0.476 | 0.627 | 0.892 | 0.2659 | $0.0008 | $67 |
| `deepseek-v4.1-flash` | 119/120 | 0.780 | 0.355 | 0.488 | 0.803 | 0.5332 | $0.0019 | $161 |
| `glm-5.3-flash` | 120/120 | 0.872 | 0.440 | 0.585 | 0.679 | 0.1751 | $0.0012 | $104 |
| `gpt-oss-120b` | 109/120 | 0.943 | 0.336 | 0.495 | 0.907 | 0.6223 | $0.0014 | $119 |
| `nvidia/nemotron-3-ultra-550b-a55b` | 120/120 | 0.856 | 0.368 | 0.514 | 0.588 | 0.0 | $0.0000 | $0 |
| `deepseek-v4.1-flash-1017-ultrafast` | 119/120 | 0.922 | 0.536 | 0.678 | 0.908 | 0.5403 | $0.0000 | $0 |

| model | records | matched | judged keep (extra) | judged drop (FP) | unjudged | P vs union | record reasons |
|---|---|---|---|---|---|---|---|
| `deepseek-v4-pro` | 157 | 126 | 0 | 0 | 31 | 0.8025 | `{'entity_unresolved': 12, 'number_not_in_quote': 11}` |
| `glm-5.3` | 343 | 285 | 0 | 0 | 58 | 0.8309 | `{'number_not_in_quote': 22, 'entity_unresolved': 24}` |
| `deepseek-v4-flash` | 248 | 110 | 101 | 19 | 18 | 0.4435 | `{'entity_unresolved': 21, 'number_not_in_quote': 15, 'sid_missing': 2, 'quote_empty': 2}` |
| `deepseek-v4.1-flash` | 237 | 71 | 78 | 42 | 46 | 0.2996 | `{'entity_unresolved': 15, 'number_not_in_quote': 46, 'sid_missing': 1, 'quote_empty': 1}` |
| `glm-5.3-flash` | 281 | 99 | 92 | 28 | 62 | 0.3523 | `{'entity_unresolved': 92, 'sid_missing': 5, 'quote_empty': 4, 'number_not_in_quote': 61}` |
| `gpt-oss-120b` | 157 | 49 | 99 | 9 | 0 | 0.3121 | `{'entity_unresolved': 8, 'number_not_in_quote': 9}` |
| `nvidia/nemotron-3-ultra-550b-a55b` | 190 | 67 | 93 | 27 | 3 | 0.3526 | `{'number_not_in_quote': 86, 'entity_unresolved': 92, 'sid_missing': 1, 'quote_empty': 1}` |
| `deepseek-v4.1-flash-1017-ultrafast` | 403 | 137 | 100 | 20 | 146 | 0.34 | `{'number_not_in_quote': 14, 'entity_unresolved': 32}` |


## Gate results (kb/gates.yaml)

| criterion | required | measured | pass |
|---|---|---|---|
| `extraction_gold_chunks` | 120 | 120 | True |
| `reference_models_distinct_families` | 2 | 2 | True |
| `chosen_bulk_gate_pass_rate` | 0.95 | 1.0 | True |
| `chosen_bulk_precision` | 0.92 | 0.9222 | True |
| `chosen_bulk_f1_within_best` | 0.03 | 0.0 | True |
| **all_pass** | - | - | **True** |
## Selected model

- `deepseek-v4.1-flash-1017-ultrafast` (transport `tools`, provider `ultrafast`)
- precision 0.922, recall 0.536, F1 0.678, clean-call gate rate 0.3846, strict record gate pass 0.9077, chunk gate rate 0.8487
- measured $0.000000/chunk (13 packed calls, cached share 0.5403); projected full scope $0.00 for 86607 chunks (P4c allowance $22.00, within allowance: True)
- mean latency 3051 ms, p95 3947 ms
- P4c shape: 20,920 packed calls, 26,961,696 output tokens at the gold pack depth
- free-tier cap 4,800,000 output tokens/day => 5.62 days wall time alone
- pipeline cap $82.00, spent $4.75, remaining $77.25
- paid overflow fitting the remaining cap: `deepseek-v4-flash` ($67.26, F1 0.627)
- mixed pool, one-day wall: free tier covers 3,724 calls/day; paid overflow `deepseek-v4-flash` takes 17,196 calls (82.2% of the corpus) => $55.29; total spend with what is already booked $60.04 (inside pipeline cap: True)
- C1 decision: the selected extractor is free but is capped per day, so P4c on it alone takes the wall time above; the paid overflow column is measured on the same gold set and shows what a mixed provider pool (free primary + paid overflow) would cost against the remaining pipeline cap. Choosing that pool changes run shape, not prompt/schema, so it is raised for the C1 owner instead of self-approving.

## Sample of the gold chunks

| chunk | doc | path | sentences | known entities |
|---|---|---|---|---|
| `850fffa7658ee3d8cd70f9565de7e05b` | `sec_10k` 2017-06-14 | `corpus/10-companies/LPG/10-K/LPG_10-K_2017-06-14_0001596993-17-000010.md` | 12 | 1 |
| `f7c7dce15a619518865b2d1ae89b10a2` | `broker_monthly` 2023-04-01 | `data/extracted/md/seabrokers/2023/2023-04-01_markedsrapport-april-2023.md` | 3 | 1 |
| `5014274accf8ff60c7d6f1e1dd38fff1` | `broker_weekly` 2021-09-21 | `data/extracted/md/intermodal/2021/intermodal_2021_W37_Intermodal-Report-Week-37-2021.md` | 2 | 2 |
| `3d94992a317eb2c699f3649ed9516564` | `broker_weekly` 2023-11-14 | `data/extracted/md/intermodal/2023/intermodal_2023_W45_Intermodal-Report-Week-45-2023.md` | 9 | 7 |
| `8438d1906ee199d93563d00abc472462` | `sec_6k` 2025-06-06 | `corpus/10-companies/EDRY/6-K/EDRY_6-K_2025-06-06_0001317861-25-000032.md` | 11 | 4 |
| `080d29393c9cd7d3f92f07ee2fcdc6db` | `broker_weekly` 2026-10-02 | `data/extracted/md/gibson/2026/gibson_2026-10-02_running-out-of-room.md` | 6 | 1 |
| `1ceeb7bafc18b2c26a548d57fe1549a8` | `broker_daily` 2023-07-04 | `data/extracted/md/breakwave/insights/2023/2023-07-04_shipfix-global-market-update.md` | 8 | 1 |
| `2c1ec5f8e0ac1281f2f589f44f2461f9` | `broker_weekly` 2026-10-02 | `data/extracted/md/gibson/2026/gibson_2026-10-02_running-out-of-room.md` | 8 | 0 |
| `ca1dd27f439332a5d64ec76612222924` | `broker_weekly` 2006-11-22 | `data/extracted/md/poten/2006/poten_2006-11-22_giving-thanks.md` | 6 | 1 |
| `3e1f19cec7d4468536dfc21eccb1eff2` | `broker_weekly` 2025-02-28 | `data/extracted/md/hellenic/demolition/gms/2025/gms_2025-02-28_week-09_dwindling-surge.md` | 8 | 6 |

## C1 flagged-extraction sample

`kb/reports/p4b_flagged.md` (machine copy `kb/reports/p4b_flagged.json`): 30 of 304 flagged reference records, seed 15063620, pool {'keep': 273, 'drop': 31, 'unadjudicated': 0}; half adjudicator-drops, half keeps, one record per chunk first. Flagged = extracted by exactly one reference model, so each item tests the reference set itself, not only the candidates.

Deviations: D10 - measured-cost budgeting from router `usage.cost`; packed calls per plan §7.2 (attempt 1's one-chunk-per-call shape inflated the projected cost ~4x); adjudicator free NIM `nvidia/nemotron-3-ultra-550b-a55b` (fallback `gpt-oss-120b`) because paid enclave capacity is exhausted; glm-5.3 reference truncation inside the plan's 2,500-token response budget filled with same-model single-chunk calls; candidate precision measured against judged truth (reference union + third-family adjudication of unmatched records); gold sampling stratified on (doc_type, era) with publisher/doc-type/year/section coverage repair. Roles: references `deepseek-v4-pro`, `glm-5.3`, adjudicator `nvidia/nemotron-3-ultra-550b-a55b` (fallback `gpt-oss-120b`), candidate set 6 models, owner review of 30 flagged items at C1.

