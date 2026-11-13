# C1 checkpoint — owner reply (verbatim)

checkpoint: C1
received: 2026-02-19
owner_message:
C1 decision (owner):
1. Approve bulk extraction with deepseek-v4.1-flash-1017-ultrafast, shape (a), free. Wall time is fine.
2. Recall 0.54 vs the glm reference is the weak spot. Add a free recall pass: after bulk, run Ultrafast again over every chunk as a gleaning pass ("list facts the first pass missed", same sentence-id and quote rules), merge, dedupe. Gate it on the same precision threshold.
3. Escalation: do NOT use nemotron (gate pass 0.59, weaker than the extractor). Escalate gate-failing chunks after one free retry to glm-5.3, inside the $17 escalation cap, prioritised by doc value.
4. Spare budget: after booking all remaining phase caps, spend what is left of the $82 (about $40) on glm-5.3 as a second extractor on the highest-value chunks (SEC 10-K/20-F/6-K MD&A and fleet sections, broker forecasts, fixtures and S&P), union with the Ultrafast output, same gates. Report recall gain on the gold set.
5. Judge/auditor: glm-5.3 approved (different family from the extractor).
6. Gold labels: accept the adjudicator's keep/drop for all 304 flagged records, including the 30 sampled.

# Decisions applied

- bulk extractor: `deepseek-v4.1-flash-1017-ultrafast` (free tier), shape (a).
- gleaning recall pass: same free model, second prompt ("facts the first pass missed"), same
  sentence-id/quote gates, union + dedupe with the bulk records.
- escalation: one free retry, then `glm-5.3` (paid, enclave), ordered by doc value, cap $17.
- spare budget: `glm-5.3` second extractor over the highest-value chunks, unioned with Ultrafast,
  same gates, cap ~$40, recall gain reported on the gold set.
- judge/auditor: `glm-5.3` (family differs from the deepseek extractor).
- gold labels: adjudicator keep/drop accepted for all 304 flagged records (273 keep / 31 drop).
- nemotron escalation path dropped per owner decision (supersedes D11 planning note).

# Amendment 1 — bulk extractor moved off Ultrafast (owner, 2026-11-13)

Owner directive (chat, 2026-11-13), recorded here without altering the C1 owner_message above:

- Ultrafast is congested (47 calls queued, 5/5 slots full, timeouts) ⇒ **excluded** from bulk
  extraction. Its config entry stays for the record only; no new Ultrafast calls.
- Bulk extractor is now the **AMD Token Lab** pool, exact API id `DeepSeek-V4.1-Flash`
  (same 1017 weights that led the P4b bake-off), fallback `DeepSeek-V4-Flash`. The string
  `DeepSeek-V4.1-Flash-1017` is never sent: it 404s on that provider.
- Pool size is **8 verified accounts** (`AMD_TOKENLAB_API_KEY_1..8`), 160 RPM aggregate. Every key is
  individually valid. A transient 401/403/429 on one call is a **soft failure**: the runner rotates to
  the next key and continues; it is never fatal for the shard. `key_pool_size("auto",
  "DeepSeek-V4.1-Flash") == 8` is asserted before every pass.
- Measured refusal mode is uniform: every rejection is `HTTP 429`
  `model_concurrency_rate_limit_exceeded` — a **model-wide concurrency ceiling (144)**, *not* per-key
  quota. An 8-call-per-key probe (48 calls) saw zero 401/403. Observed acceptance ≈0.56 ok/call, flat in
  pacing (8 s/5 s/3 s rungs: 9/16, 9/16, 7/16), so no pacing value recovers the deficit; the runner
  retries within the same call and the daemon skips already-stored raws cost-free on the next sweep.
- **AMD Token Lab is NOT free.** The route reports a real `usage.cost`; the tariff fits exactly
  (max abs err $0.000000) from 11 stored parity usages: in $0.28/M, cached in $0.0056/M, out $0.56/M ⇒
  blended $0.001249/call, **$0.00134 per accepted pack** at real pack depth. Full remaining scope
  (23,488 packs) ≈ $31.5, booked under `p4c_bulk_extraction` ($31.25). `kind: paid` in `kb/config.yaml`.
- Extraction bypasses the agent gateway, so the gateway's 76 USD agent cap is untouched.

Unchanged by this amendment: the C1 quality gates (valid JSON, code-sliced quotes, resolvable ids,
every printed number inside its quote, dates resolved in code, rule-6 escalation), the one-free-retry
then glm-5.3 escalation ladder inside $17, the glm-5.3 second-extractor spare budget, and the
`judge_family_differs_from_extractor` rule. This is an amendment to D10's provider choice only; it
lowers no gate.
