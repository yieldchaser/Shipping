# P4c - full-scope extraction (plan §7, §10.3)

Seed `196579347` (phase `P4C`). Generated 2026-11-16T22:06:10.

## Design note

Bulk step runs the selected extractor over the frozen prose scope in ~3.5k-token packed calls (same document, static prompt, known entities, temp 0). Chunks that lose any record to gates 2-4 or come back blank/schema-broken go to a failure queue, retried one chunk per call by the same model and then by the escalation model; only a fully clean retry replaces the bulk verdict. Everything below is computed from stored raws - no re-calls. 200 stored records are re-judged by another family for the audit gate.

Deviations declared: **D11** the owner overrode plan §7.6 (no blanket gleaning) - a free gleaning pass re-reads every chunk with its own first-pass answer in the prompt and keeps only missed records; it runs through the identical gates. **D10/D11** escalation to `glm-5.3` (owner choice, not nemotron) is cap-prioritised, so escalation coverage is partial by design (**D12**). **D14** the spare budget funds a second extractor (`glm-5.3`) on the highest-value chunks, quota-split across SEC/fleet, broker forecasts, fixtures and S&P. **D13** the union dedupes the same kind+type with overlapping quotes, keeps the highest-confidence copy and the provenance of every copy.

## Scope coverage (declared)

| metric | covered | frozen scope | share |
|---|---|---|---|
| chunks | 86,607 | 86,607 | 100.00% |
| documents | 16,945 | 16,945 | 100.00% |
| publishers | 59 | 59 | - |
| doc types | 9 | 19 | - |
| years | 24 | 24 (1986-2026) | - |

**Full scope covered.**

## Extraction

| metric | value |
|---|---|
| chunks attempted | 86,607 |
| chunks clean (every returned record survived gates 2-4) | 84,877 |
| chunks escalated then clean | 0 |
| broken chunks (D12 failure queue, gated) | 1,730 (2.00%) |
| chunks with >=1 dropped record (diagnostic, **not** gated) | 1,730 (2.00%) |
| chunks answering `no_content` | 34,236 |
| records kept | 183,486 (state_facts 23,666, events 80,409, claims 79,411) |
| records dropped by gates | 108,969 (59.39% of attempted records) |
| final rung | {"union": 86607} |

## Gates (`kb/gates.yaml` P4c)

| gate | required | measured | pass |
|---|---|---|---|
| `failure_queue_max` | 0.02 | 0.02 | PASS |
| `random_audit_records` | 200 | 200 | PASS |
| `random_audit_wrong_max` | 0.03 | 0.005 | PASS |
| `judge_family_differs_from_extractor` | True | True | PASS |
| `coverage_of_frozen_scope_reported` | True | True | PASS |

**all_pass: True**

Final record set read from: **union**.

## Union of extraction passes (D13)

| metric | value |
|---|---|
| records after merge | 183,486 |
| duplicates removed | 11181 (6.09%) |
| records per source | {"p4c_bulk_retry": 2108, "p4c_bulk": 180400, "p4c_esc": 999} |
| records dropped by gates | 23936 |
| broken chunks (D12) | 1730 (2.00%) |

## Rule-6 escalation queue (D12)

| metric | value |
|---|---|
| chunks in the bulk gate | None |
| chunks triggering rule 6 | None (0.0939) |
| triggers | null |
| free retry singles | None (unmatched 0) |
| escalated to `glm-5.3` | None (skipped by cap 0) |
| escalation spend | $5.6380 of $17.0000 cap |
| partial coverage declared | True |


## Audit

Judge `glm-5.3` (glm family) vs extractor `DeepSeek-V4.1-Flash` (deepseek family): 200 sampled, 200 judged, 1 dropped, 0 unparseable -> wrong rate **0.50%** (max 3%).

## Money and wall time

| pass | cost USD | wall s | packs | packs/min |
|---|---|---|---|---|
| `p4c_bulk` | $24.1422 | 851.9 | 2 | 0.14 |
| `p4c_bulk_retry` | $0.4970 | 1279.7 | 549 | n/a |
| `p4c_glean` | $0.0000 | 23.2 | 2 | 5.17 |
| `p4c_esc` | $6.3428 | 152.3 | 256 | 100.85 |
| `p4c_glm2` | UNMEASURED | n/a | n/a | n/a |
| `p4c_audit` | $1.1975 | n/a | n/a | n/a |
| **total** | **$32.1796** | | | |

## Ten sampled chunks (seeded)

| chunk | publisher | type | date | records | source path |
|---|---|---|---|---|---|
| `231baf511b63ac8259936b26578de017` | Breakwave Advisors | broker_daily | 2022-10-14 | 3 | `data/extracted/md/breakwave/insights/2022/2022-10-14_braemar-weekly-dry-market-report.md` |
| `3f163fcc8eee7f1d8dc761476eec4071` | Poten & Partners | broker_weekly | 2006-03-03 | 6 | `data/extracted/md/poten/2006/poten_2006-03-03_the-return-of-the-double-exponential.md` |
| `67120b381b7198a778f2aab483fd8fb2` | Breakwave Advisors | broker_weekly | 2019-09-17 | 1 | `data/extracted/md/breakwave/drybulk/2019/2019-09-17_Breakwave_Dry_Bulk.md` |
| `2bcf0e730e4103a65a03ee849529946b` | Seanergy Maritime Holdings Corp. | sec_6k | 2025-03-28 | 2 | `corpus/10-companies/SHIP/6-K/SHIP_6-K_2025-03-28_0001140361-25-010987.md` |
| `4e2842bfcf35f19d90da6ff2a800aac7` | Banchero Costa | broker_weekly | 2025-01-20 | 1 | `data/extracted/md/banchero_costa/2025/banchero_costa_2025_W03_Bancosta-Weekly-2025-03.md` |
| `f2749f63e9b421861d009dab41a745d8` | Seanergy Maritime Holdings Corp. | sec_6k | 2023-12-15 | 1 | `corpus/10-companies/SHIP/6-K/SHIP_6-K_2023-12-15_0001140361-23-057943.md` |
| `e9a5ce99325575d7f38c68f314506d7b` | Seabrokers Chartering | broker_monthly | 2018-05-01 | 3 | `data/extracted/md/seabrokers/2018/2018-05-01_markedsrapport-mai-2018.md` |
| `79e3c6b5c4a0108a4f6bf9afe3072e8a` | Poten & Partners | broker_weekly | 2026-10-02 | 10 | `data/extracted/md/poten/2026/poten_2026-10-02_tanker-demand-destruction.md` |
| `312ee9a28d92a2da32dfc1abbf5ca58a` | Baltic Exchange | broker_weekly | 2017-06-30 | 2 | `data/extracted/md/baltic/tanker/2017/2017_tanker-report-week26_tanker.md` |
| `1318ed94c733d40437b9bbc729dbcf39` | Baltic Exchange | broker_weekly | 2015-09-04 | 2 | `data/extracted/md/baltic/tanker/2015/2015_tanker-report-week36_tanker.md` |
