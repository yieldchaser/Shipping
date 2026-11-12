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
