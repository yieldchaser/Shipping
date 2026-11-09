# STATUS — GraphRAG build (kb)

Live run status. Real spend read from `http://127.0.0.1:4100/stats`.

| Phase | State | Gate | Next |
|---|---|---|---|
| 0 smoke | done | PASS (model `cyberouter/deepseek-v4-flash`) | — |
| P0 | done | PASS (R1–R7 all PASS) | commit+push |
| P0.5 | done | PASS (4 gates, scope frozen 20,704 docs) | commit `7419fd3df7` |
| P-1 | done | PASS (6/7 candidates usable; tools support confirmed) | report `kb/reports/p_m1.md` |
| P1 | not started | — | |
| P2 | not started | — | |
| P3 | not started | — | |
| P4a | not started | — | |
| gold | not started | — | |
| P4b | not started | — | checkpoint C1 after |
| P4c | not started | — | |
| P5 | not started | — | |
| P6 | not started | — | |
| P7 | not started | — | checkpoint C2 after |
| P8 | not started | — | |

## Spend

| Metric | Value | Cap |
|---|---|---|
| Enclave (agent, paid V4 Pro) | $22.58 | $45.00 |
| Ultrafast (free flash) | $0.00 (0 output tok today) | free |
| Pipeline | $0.00 so far | $97 |

Smoke-test usage: prompt_tokens 13, completion_tokens 5, model `cyberouter/deepseek-v4-flash`, cost $0.000003.

## Integrity

Tripwire clean for P0.5 and P-1 (fleet/ffa-live drift absorbed by `git merge origin/main`).
Head `7419fd3df7`, branch `kb-build`. Next: P1 chunking.
