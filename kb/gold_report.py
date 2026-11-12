"""kb/gold_report.py -- render the gold Q&A set report (PLAN 12.1 / AGENT_TASK row 8).

Reads kb/state/gold/gold_set.json and writes
  kb/reports/gold_set.md   (human report, 10 sampled records, 25 C1-sample questions)
  kb/reports/gold_set.json (copy of the set with summary fields, for the gate log)

Usage:
    python kb/gold_report.py [--samples 10] [--c1-samples 25]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tripwire import seed_for  # noqa: E402

KB = Path(__file__).resolve().parent
SRC = KB / "state" / "gold" / "gold_set.json"
OUT_MD = KB / "reports" / "gold_set.md"
OUT_JSON = KB / "reports" / "gold_set.json"

TYPE_ORDER = ["a_single_number", "b_window_aggregate", "c_multihop_entity",
              "d_event_market", "e_sec_section", "f_summary_trend",
              "g_as_known_on_date", "h_unanswerable"]
TYPE_DESC = {
    "a_single_number": "one verified observation value (exact match)",
    "b_window_aggregate": "mean over a contiguous window of observations",
    "c_multihop_entity": "vessel entity -> transaction -> the documents that reported it",
    "d_event_market": "transaction event date -> market series move over the next month",
    "e_sec_section": "SEC filing -> section heading that discusses a given term",
    "f_summary_trend": "start/end values and percentage change of a series window",
    "g_as_known_on_date": "latest known value as of a past date (published_at <= date)",
    "h_unanswerable": "question the corpus cannot answer; must be refused with a gap statement",
}

DESIGN_NOTE = """\
# Gold Q&A set -- design note (PLAN 12.1, AGENT_TASK row 8)

* Purpose: 250-question held-out evaluation set for P7 answer scoring, spread over the
  eight plan strata (a 50, b 25, c 35, d 25, e 35, f 25, g 15, h 40).
* Generation is code-only: every question is a template filled with values read from
  `kb/state/kb.duckdb`. No LLM invents facts, so no answer can be hallucinated here.
* Every candidate answer is re-read from the database before the item is kept
  (`verification.checks` names the re-read); a candidate that cannot be reproduced is
  dropped, so set size can shrink rather than carry an unverifiable answer.
* Sources are recorded per item (observation id + doc_id + corpus path, transaction id,
  section id + filing path, or the absence proof for the unanswerable stratum), which is
  what P7 needs to score citations as well as answers.
* SEC XBRL was skipped upstream (no `SEC_USER_AGENT`, see `kb/reports/upstream_defects.md`),
  so the SEC stratum (e) is prose/section lookup from 10-K/20-F/10-Q/8-K/6-K filings
  instead of XBRL facts -- deviation D6.
* (d) is a temporal association (event date -> next 30 days of a market series), not a
  causal claim; it is judge-graded and the judge is told the association is temporal.
* (f) and (d) are judge-graded (`judge_only: true`); (a), (b), (g) carry numeric
  tolerances; (c) and (e) have exact string-set answers; (h) requires a refusal.
* Determinism: `sample_seed = seed_for("GOLD_SET")`; the seed is stored in the set and
  every report sample is drawn from it, so re-running the builder reproduces the same set.
* Cost: $0 (no paid model calls; DB reads only).
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--c1-samples", type=int, default=25)
    args = ap.parse_args()
    if not SRC.exists():
        print(f"missing {SRC}; run kb/gold_set.py first")
        return 1
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    items = payload["items"]
    seed = payload["sample_seed"]
    rng = random.Random(seed)
    counts = {t: sum(1 for i in items if i["type"] == t) for t in TYPE_ORDER}
    short = [t for t in TYPE_ORDER if counts[t] < payload["targets"][t]]
    verified = sum(1 for i in items if i["verification"].get("passed"))
    judge = sum(1 for i in items if i.get("judge_only"))

    samples = items[:]
    rng.shuffle(samples)
    samples = samples[:args.samples]
    # C1 sample: spread over strata, deterministic
    by_type: dict[str, list[dict]] = {}
    for it in items:
        by_type.setdefault(it["type"], []).append(it)
    pool: list[dict] = []
    while len(pool) < len(items):
        for t in TYPE_ORDER:
            rest = [x for x in by_type.get(t, []) if x not in pool]
            if rest:
                pool.append(rest[0])
    c1 = pool[:args.c1_samples]

    lines = [DESIGN_NOTE]
    lines.append("## Result\n")
    lines.append("| stratum | description | target | built | verified | judge-graded |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for t in TYPE_ORDER:
        jn = sum(1 for i in items if i["type"] == t and i.get("judge_only"))
        lines.append(f"| {t} | {TYPE_DESC[t]} | {payload['targets'][t]} | "
                     f"{counts[t]} | {sum(1 for i in items if i['type'] == t and i['verification'].get('passed'))} | {jn} |")
    lines.append(f"| **total** |  | **{sum(payload['targets'].values())}** | "
                 f"**{len(items)}** | **{verified}** | **{judge}** |")
    lines.append("")
    lines.append(f"- sample_seed: `{seed}`")
    lines.append(f"- built_at: {payload['built_at']}")
    lines.append(f"- wall_seconds: {payload['wall_seconds']}")
    lines.append(f"- money_spent_usd: {payload['money_spent_usd']}")
    lines.append(f"- short strata: {short or 'none'}")
    lines.append(f"- verification failures: {payload['verification_failures'] or 'none'}")
    lines.append(f"- model roles: answer/question generator = deterministic code (no LLM); "
                 f"judge = free NIM model, different family from the extractor, opened at P7; "
                 f"extraction family for the KB = local parser + free NIM embeddings")
    lines.append("")

    lines.append("## Sampled records (10, deterministic)\n")
    for it in samples:
        lines.append(f"### {it['id']} [{it['type']}]\n")
        lines.append(f"- question: {it['question']}")
        lines.append(f"- gold answer: {it['answer_text']}")
        if it["sources"]:
            for s in it["sources"][:4]:
                bits = [f"{k}={v}" for k, v in s.items() if v not in (None, "", [])]
                lines.append(f"- source: {', '.join(bits)}")
        else:
            lines.append("- source: none by design (unanswerable)")
        lines.append(f"- verification: {it['verification']['checks']} passed={it['verification']['passed']}")
        lines.append("")

    lines.append(f"## C1 sample packet ({len(c1)} questions)\n")
    lines.append("For the C1 checkpoint review: these are the questions proposed for the "
                 "held-out set. Approve or flag; the rest of the set stays unapproved until C2.\n")
    for it in c1:
        lines.append(f"{it['id']}\t{it['type']}\t{it['question']}\t=> {it['answer_text']}")
    lines.append("")

    lines.append("## Known risks / deviations\n")
    lines.append("- D6: SEC stratum is prose/section lookup, not XBRL facts (XBRL skipped, no "
                 "`SEC_USER_AGENT`; see upstream_defects.md). If the owner exports "
                 "`SEC_USER_AGENT` later, XBRL can be ingested and this stratum can gain "
                 "numeric SEC questions in a v2 set.")
    lines.append("- Numeric question wording is template-generated and can read stiffly "
                 "(\"What was the <measurement> for <signature> on <date>?\"). Wording was not "
                 "tuned after seeing retrieval scores; it is fixed before the P4a measurement run.")
    lines.append("- (d) pairs an event date with a market series over the following month; the "
                 "answer is a computed market move, not proof of causation.")
    lines.append("- Series units are sometimes NULL in the DB; where the measurement name encodes "
                 "the unit an explicit measurement->unit map is used, and the unit shown in the "
                 "question is that resolved unit.")
    lines.append("- (h) refusal questions are verified by absence (entity/series/FTS zero rows); "
                 "a model that answers them must also state the corpus gap to score.")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    summary = {k: v for k, v in payload.items() if k != "items"}
    summary["counts"] = counts
    summary["verified_total"] = verified
    summary["manifest"] = [
        {"id": i["id"], "type": i["type"], "judge_only": bool(i.get("judge_only")),
         "answer_text": i["answer_text"]} for i in items]
    OUT_JSON.write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT_MD} and {OUT_JSON} ({len(items)} items, short={short})")
    return 0 if not short and not payload["verification_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
