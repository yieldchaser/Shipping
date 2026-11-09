# STATUS — GraphRAG build (kb)

Live run status. Real spend read from `http://127.0.0.1:4100/stats`.

| Phase | State | Gate | Next |
|---|---|---|---|
| 0 smoke | done | PASS (model `cyberouter/deepseek-v4-flash`) | — |
| P0 | done | PASS (R1–R7 all PASS) | commit+push |
| P0.5 | blocked | tripwire RED (17 protected data/) | owner decision — see `kb/reports/BLOCKED.md` |
| P-1 | not started | — | router probe |
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
| Enclave (agent, paid V4 Pro) | $21.56 | $45.00 |
| Pipeline | $0.00 so far | $97 |
| Ultrafast output today | 45 | 5,000,000 (pipeline share 3M) |

Smoke-test usage: prompt_tokens 13, completion_tokens 5, model `cyberouter/deepseek-v4-flash`, cost $0.000003.

## Integrity

Tripwire RED before P0.5 gate — 17 protected `data/` paths vs `origin/main`. None agent-made.
See `kb/reports/BLOCKED.md`. Head `df7fd0feb4`, branch `kb-build`. Next: owner decision (§6 L194/L198).
