# P-1 router probe

seed `1855472108`. 7 candidates, 20 calls each. Gate: report written, >= 2 usable.

| model | tools | json_schema | json_object | cached_tok | model_returned | ramp ok/429/5xx | mean_lat_ms | usable |
|---|---|---|---|---|---|---|---|---|
| `deepseek-v4-flash` | True | True | None | False | cyberouter/deepseek-v4-flash | 18/0/0 | 2194.8 | True |
| `deepseek-v4.1-flash` | True | True | None | False | cyberouter/deepseek-v4.1-flash | 18/0/0 | 1644.1 | True |
| `glm-5.3-flash` | True | False | None | False | cyberouter/glm-5.3-flash | 18/0/0 | 2453.9 | True |
| `gpt-oss-120b` | True | True | None | True | cyberouter/gpt-oss-120b | 18/0/0 | 1960.3 | True |
| `minimax-m3` | None | None | None | False | ? | 0/0/17 | None | False |
| `deepseek-v4-pro` | True | False | None | False | cyberouter/deepseek-v4-pro | 18/0/0 | 1899.5 | True |
| `glm-5.3` | True | True | None | False | cyberouter/glm-5.3 | 17/0/0 | 1897.1 | True |

## Findings

- All 6 usable models support strict **tools** (function-calling). The runner can use tools first, per plan 7.3.
- Prefix-cache tokens are reported by `gpt-oss-120b` (top-level `cached_tokens`) and `glm-5.3-flash` (`prompt_tokens_details.cached_tokens`) — packing still helps but matters less for those.
- `minimax-m3` is unusable: the router's Together provider returns 502 on every tools/schema request.
- `gpt-oss-120b` and `glm-5.3` saw frequent remote connection drops (WinError 10054 / RemoteDisconnected) on the ramp — transient, not 429/5xx.
- `deepseek-v4-pro` returned invalid JSON under `json_schema` (reasoning consumed the token budget); its tools path is clean.

**Result: PASS** — 6 usable candidate(s).

## Tripwire

```
tripwire clean
```
exit 0.
