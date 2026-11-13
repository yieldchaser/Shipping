"""Build kb/reports/C1_REVIEW.md — the C1 checkpoint packet (AGENT_TASK §5).

Reads only committed/derived JSON: p4b.json, p4b_flagged.json, gold_set.json,
p3_owner_sample.json. No model calls, no randomness.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "kb" / "reports"


def load(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out)


def bakeoff_table(p4b: dict) -> str:
    rows = []
    for name, m in p4b["models"].items():
        role = "reference" if name in p4b["roles"]["reference_models"] else "candidate"
        rows.append([
            f"`{name}`",
            role,
            f"{m.get('coverage_chunks', 0)}/120",
            f"{m['precision']:.4f}",
            f"{m['precision_ci95'][0]:.4f}-{m['precision_ci95'][1]:.4f}",
            f"{m['recall']:.4f}",
            f"{m['f1']:.4f}",
            f"{m.get('gate_pass_rate', 0):.4f}",
            f"{m.get('call_success_rate', 0):.4f}",
            f"${m.get('cost_usd', 0):.4f}",
            f"${m.get('projected_full_scope_usd', 0):.2f}",
        ])
    return md_table(
        ["model", "role", "coverage", "P", "P 95% CI", "R", "F1", "gate pass",
         "call success", "bake-off cost", "projected full scope"],
        rows,
    )


def flagged_section(fl: dict) -> str:
    lines = [f"Source: `kb/reports/p4b_flagged.md` (machine copy `kb/reports/p4b_flagged.json`). "
             f"{fl['scope']['sample_size']} of {fl['scope']['flagged_pool']} flagged reference records, "
             f"seed {fl['sample_seed']}, pool keep {fl['scope']['pool_by_decision']['keep']} / "
             f"drop {fl['scope']['pool_by_decision']['drop']}.", ""]
    for i, it in enumerate(fl["items"], 1):
        ent = ", ".join(it.get("entities") or []) or "-"
        quote = (it.get("evidence_quote") or "").replace("\n", " ")[:220]
        lines.append(
            f"{i}. **{it['adjudicator_decision'].upper()}** — `{it['kind']}/{it['type']}` "
            f"[{ent}] — {it['publisher']}, {it['published_at']} ({it['doc_type']}) — "
            f"path `{it.get('source_path')}`")
        lines.append(f"   - quote: {quote}")
        lines.append(f"   - adjudicator why: {it.get('adjudicator_why', '')[:220]}")
    return "\n".join(lines)


def gold_section(gold: dict) -> str:
    md = (REPORTS / "gold_set.md").read_text(encoding="utf-8")
    start = md.index("## C1 sample packet")
    end = md.index("## Known risks / deviations")
    return md[start:end].replace("## C1 sample packet", "### C1 sample packet", 1).strip()


def merge_section(own: dict) -> str:
    rows = []
    for r in own["records"]:
        a, b = r["a"], r["b"]
        rows.append([
            f"`{a['name']}` ({a['entity_id'].split(':')[0]}:{a['entity_id'].split(':')[-1][:12]})",
            f"`{b['name']}` ({b['entity_id'].split(':')[0]}:{b['entity_id'].split(':')[-1][:12]})",
            r.get("method", ""),
            r.get("verdict", ""),
            (r.get("reason") or "").replace("\n", " ")[:150],
        ])
    return md_table(["a", "b", "method", "verdict", "model reason"], rows)


def main() -> int:
    p4b = load("p4b.json")
    fl = load("p4b_flagged.json")
    gold = load("gold_set.json")
    own = load("p3_owner_sample.json")
    sel = p4b["selected"]
    feas = p4b["p4c_feasibility"]
    spend = p4b["spend"]
    gr = p4b["gate_results"]
    opt = feas["mixed_pool_one_day"]
    call = feas["calls_at_gold_pack_depth"]
    out_tok = feas["out_tokens_full_scope"]
    days = feas["wall_days_at_daily_cap"]

    gate_rows = [[f"`{k}`", str(v["measured"]), str(v["required"]), "PASS" if v.get("pass") else "FAIL"]
                 for k, v in gr.items() if isinstance(v, dict) and "pass" in v]

    doc = f"""# C1 review — extraction bake-off, label flags, merge sample, gold packet

Hard stop per `docs/GRAPHRAG_AGENT_TASK.md` §5. Owner rules on the items below in chat; nothing here
is approved until then. Branch `kb-build`, P4b commit on top of the gold-set commit, tripwire clean,
82 tests pass. Spend so far ${spend['total_usd']:.4f} of the $82 pipeline cap; agent spine
(enclave) $66.04/$66.00 — over cap, unchanged, no paid agent calls since P2.

## 1. Bake-off table (plan §10.2, gates P4b)

{md_table(["gate", "measured", "required", "verdict"], gate_rows)}

Gold set: 120 stratified chunks / 29 packs / 9 doc types / 12 years / 19 publishers, mean pack depth
{p4b['gold'].get('mean_pack_depth', 'n/a')}. References: `deepseek-v4-pro` + `glm-5.3` (different
families), coverage 120/120 each. Their {p4b['reference_set']['flagged_one_reference']} disagreements
adjudicated by `nvidia/nemotron-3-ultra-550b-a55b` (third family, free NIM): keep
{p4b['reference_set']['adjudicated']['keep']} / drop {p4b['reference_set']['adjudicated']['drop']}.
Reference union = {p4b['reference_set']['records']} records; two references fully agree on only
{p4b['reference_set']['two_reference_agreement']}, and the record counts are glm 381 vs pro 176, so the
reference is glm-shaped.

{bakeoff_table(p4b)}

Caveats (also in `p4b.md`): absolute F1 is relative to the glm-shaped reference union, not truth;
precision point estimates sit inside their own 95% sampling interval; the 120-chunk sample cannot
certify precision above its CI, which matters for the 0.92 gate; three candidates have coverage holes
(gpt-oss-120b 109/120, ultrafast 119/120, v4.1-flash 119/120) filled by a same-model hole-fill pass.

## 2. Models I chose, and what I need approved

| role | model | family | why | cost basis |
|---|---|---|---|---|
| bulk extraction | `DeepSeek-V4.1-Flash` on the 8-account AMD Token Lab pool (owner amendment 2026-11-13 to the ultrafast pick below) | deepseek | same 1017 weights as the F1 leader `deepseek-v4.1-flash-1017-ultrafast` (P4b F1 {sel['f1']:.4f}, precision {sel['precision']:.4f}, call success {sel['call_success_rate']:.2f}); Ultrafast excluded as congested | **paid**: $0.00134/accepted pack ($0.28/M in, $0.0056/M cached, $0.56/M out); ≈$31.5 booked at $31.25 |
| escalation (gate-failing chunks) | approved: `glm-5.3`, one free same-model retry first, ordered by doc value | glm | owner decision 3; kept inside the escalation line by cap-prioritised partial coverage (D12); plan §10.2's "ref with higher agreement" is the same model at $0.0197/chunk = ${0.019673 * 86607 * 0.3:.0f} worst case for 30% escalation, which busts the cap | $11 booked |
| judge / auditor (P4c audit + failure queue) | approved: `glm-5.3` | glm (≠ deepseek extractor) | satisfies `judge_family_differs_from_extractor`; judged 285 gold records at P4b; per-record calls ≈ $0.002 | ≈ $5 for ~1.9k judged records |
| label adjudicator (already used at P4b) | `nvidia/nemotron-3-ultra-550b-a55b` | nvidia | third family, not a reference, free | $0.05 spent |

Owner rulings on the two open choices: (i) escalation = `glm-5.3` (not nemotron), one free retry
first, cap-prioritised inside the escalation line; (ii) judge = `glm-5.3` (paid, strong). The judge
stays a different family from the extractor. Owner ruling 4 (the ~$40 glm-5.3 second extractor) is
**booked at $0**: the AMD bulk pass over every pack now IS the second extractor, and the honest AMD
tariff consumes the budget that ruling 4 was premised on being spare.

## 3. Projected full-build cost

Bulk pass shape on the frozen prose-only scope (86,607 chunks, 16,945 docs): {call:,} packed calls,
{out_tok:,} output tokens, {days:.2f} wall days on the free daily cap ({feas['free_tier_daily_out_cap']:,}
output tok/day) **if the route were a free daily cap — the chosen AMD route has no daily cap; it has
a shared concurrency ceiling of 144 and a real per-token tariff**. Three run shapes, not self-approved:

| shape | bulk cost | wall time | total booked incl. spent ${spend['total_usd']:.2f} | fits $82 cap? |
|---|---|---|---|---|
| (a) `DeepSeek-V4.1-Flash` on the 8-account AMD Token Lab pool, ultrafast excluded | **${31.25:.2f} booked** ($0.00134/pack measured) | ~{days:.2f} days at free-tier pacing; ~2 days at measured AMD concurrency | ${spend['total_usd'] + 35:.2f} | yes, after rebooking ruling 4 to $0 |
| (b) paid `deepseek-v4-flash` alone | ${feas['paid_overflow']['deepseek-v4-flash']['projected_full_scope_usd']:.2f} | hours | ${spend['total_usd'] + feas['paid_overflow']['deepseek-v4-flash']['projected_full_scope_usd'] + 35:.2f} | no |
| (c) mixed one-day pool: primary + flash overflow ({opt['paid_chunk_share'] * 100:.1f}% of chunks paid) | ${opt['paid_cost_usd']:.2f} | {opt['wall_days']:.1f} day | ${opt['total_with_spent_usd']:.2f} + remaining phase budgets = ${opt['total_with_spent_usd'] + 35:.2f} | no (bulk alone fits, the rest of the build does not) |

So (a) is the only shape that fits the frozen $82 cap. The honest correction the owner should note:
this table was drafted while the bulk route was believed to be free; AMD Token Lab reports a real
`usage.cost`, so the $31.25 line is now a **measured** charge, not zero. It is funded by rebooking the
owner's ruling-4 second extractor to $0 (the AMD pass IS that second extractor) and trimming
`escalation_plus_gleaning` from $17 to $11 — an amendment to D10's provider choice that lowers no
gate. (c) would need either a cap raise of ~$15 or dropping later-phase budgets. (b) additionally
lands at F1
{feas['paid_overflow']['deepseek-v4-flash']['f1']:.4f} (chosen minus {sel['f1'] - feas['paid_overflow']['deepseek-v4-flash']['f1']:.3f})
and precision {feas['paid_overflow']['deepseek-v4-flash']['precision']:.4f}, under the 0.92 gate, so it is
worse on quality too. Remaining pipeline budget right now: ${feas['remaining_pipeline_usd']:.2f}.

## 4. Thirty flagged gold-label items to rule on

Each item is a reference record the two reference families disagreed on, sampled across both
adjudicator verdicts. Rule each as `ok` / `over-claim` / `wrong entity` / `wrong number` /
`missing (should have been extracted)`; the non-sampled {fl['scope']['flagged_pool'] - fl['scope']['sample_size']}
keep their adjudicator verdict unless you say otherwise. Full 600-char quotes and record JSON:
`kb/reports/p4b_flagged.md`.

{flagged_section(fl)}

## 5. Twenty-five sampled gold questions

Full set: {gold['total']} questions, seed {gold['sample_seed']}, {gold.get('verified_total', gold['total'])} verified,
{json.dumps(gold.get('counts', {}))}. The rest stays unapproved until C2.

{gold_section(gold)}

## 6. Thirty sampled entity merges

From `kb/reports/p3_owner_sample.json` (seed {own['sample_seed']}); rule `same` / `different`; P3 is
committed and its merge precision gate already passed at 0.99, so this is a spot check for systematic
over-merging.

{merge_section(own)}

## 7. What happens on your reply

Write `kb/reports/C1_APPROVED.md` with your message verbatim under `owner_message:`, apply any model or
label overrides, then continue P4c (bulk extraction on the frozen scope) → P5 → P6 → P7 → C2. I stop
here until you reply.
"""
    (REPORTS / "C1_REVIEW.md").write_text(doc, encoding="utf-8")
    print(f"wrote kb/reports/C1_REVIEW.md ({len(doc)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
