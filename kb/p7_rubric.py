"""P7 gold-set additions: 30 analyst-mode questions graded on a rubric (AGENT_TASK L63-66).

Design note (D19):
- 30 questions are generated deterministically from the §8 segments x analyst rubric topics,
  so they can be re-run and diffed. They are stored in kb/state/p7/rubric.json.
- Each answer is produced by `p7_analyst.analyse` (facts / indicators / judgement separated,
  numbers post-checked against computed evidence) and graded by a model from a different
  family than the extractor (default nim `openai/gpt-oss-120b`, free) on the rubric
  facts_cited / indicators_correct / judgment_reasoned / counter_argument_present.
- Gate: mean rubric score >= 0.8 over >= 30 graded questions. Scores are not fabricated:
  ungraded questions are excluded and reported, and the gate needs every question graded.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(KB_DIR))

import ask as A  # noqa: E402
import p7_analyst as PA  # noqa: E402

ROOT = KB_DIR.parent
PHASE = "P7"
OUT = ROOT / "kb" / "state" / "p7" / "rubric.json"
REPORT = ROOT / "kb" / "reports" / "p7_rubric.json"
TARGET = 0.8
N_QUESTIONS = 30

SEGMENTS = ["capesize", "panamax", "supramax", "handysize", "vlcc", "suezmax", "aframax",
            "mr_lr", "lng", "lpg", "container", "snp", "demolition", "newbuilding",
            "iron_ore", "coal", "grains", "bunkers"]

TOPICS = [
    ("earnings_percentile",
     "Where do current {seg} earnings sit versus their own history, and how unusual is that?"),
    ("asset_pe",
     "Is {seg} secondhand tonnage cheap or expensive relative to its earnings? Give the "
     "number you use and the reasoning."),
    ("spreads",
     "What do the newbuild, secondhand and scrap spreads say about {seg} right now?"),
    ("orderbook",
     "How does the {seg} orderbook compare with the fleet, and what does that imply for "
     "supply over the next two years?"),
    ("scrapping",
     "How old is the {seg} fleet, what is being scrapped, and what does that mean for "
     "effective supply?"),
    ("sentiment",
     "What is the sentence-level broker sentiment on {seg} over the last 90 days, and does "
     "it agree with the earnings trend?"),
    ("valuation",
     "Is the market valuing {seg} assets consistently with earnings? State the view as a "
     "judgment with confidence."),
    ("forecast_ledger",
     "Who has been right about {seg} recently? Use the forecast ledger and say who is "
     "credible now."),
    ("state_snapshot",
     "Give the current state of {seg}: earnings, asset values, supply, sentiment, and the "
     "main thing that would change the picture."),
    ("cycle",
     "Where is {seg} in its cycle, what evidence supports that, and what would falsify it?"),
]


def questions(n: int = N_QUESTIONS) -> list[dict]:
    out = []
    i = 0
    while len(out) < n:
        seg = SEGMENTS[i % len(SEGMENTS)]
        topic, tmpl = TOPICS[(i // len(SEGMENTS)) % len(TOPICS)]
        out.append({"id": f"A-{len(out) + 1:03d}", "segment": seg, "topic": topic,
                    "question": tmpl.format(seg=seg)})
        i += 1
    return out


def mean(vals: list[float]) -> float | None:
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else None


def rubric_fields(judged: dict) -> dict:
    fields = ("facts_cited", "indicators_correct", "judgment_reasoned", "counter_argument_present")
    got = {f: judged.get(f) for f in fields}
    score = judged.get("score")
    if not isinstance(score, (int, float)):
        parts = [got[f] for f in fields if isinstance(got[f], (int, float))]
        score = round(sum(parts) / len(parts), 4) if parts else None
    got["score"] = score
    got["notes"] = judged.get("notes", "")
    return got


def run(con=None, chat=None, judge_chat=None, n: int = N_QUESTIONS,
        model: str = A.DEFAULT_MODEL, judge_model: str = PA.JUDGE_MODEL) -> dict:
    own = con is None
    con = con or PA.connect()
    t0 = time.time()
    items, failures = [], []
    try:
        for q in questions(n):
            try:
                rec = PA.analyse(q["question"], q["segment"], con=con, chat=chat, model=model)
            except Exception as exc:  # noqa: BLE001 - keep the set, record the failure
                failures.append({"id": q["id"], "error": f"{type(exc).__name__}: {exc}"})
                items.append({**q, "status": "error", "score": None, "cost_usd": 0.0})
                continue
            item = {**q, "status": rec.get("status"), "model": rec.get("model"),
                    "escalated": rec.get("escalated"), "cost_usd": rec.get("cost_usd", 0.0),
                    "answer": rec.get("answer", ""), "confidence": rec.get("confidence"),
                    "dropped": (rec.get("dropped") or {}).get("sentences", 0)
                    if isinstance(rec.get("dropped"), dict) else rec.get("dropped"),
                    "indicators": [i.get("name") for i in
                                   (rec.get("indicators") or {}).get("indicators", [])]}
            if rec.get("status") == "ok":
                try:
                    judged = PA.judge_answer(q["question"], rec, model=judge_model, chat=judge_chat)
                except Exception as exc:  # noqa: BLE001 - judge unavailable: ungraded
                    judged = {}
                    item["judge_error"] = f"{type(exc).__name__}: {exc}"
                item.update(rubric_fields(judged))
                item["judged"] = bool(judged)
            else:
                item["judged"] = False
                item.update({"score": None, "notes": f"status={rec.get('status')}"})
            items.append(item)
    finally:
        if own:
            con.close()
    graded = [i for i in items if i.get("judged") and isinstance(i.get("score"), (int, float))]
    scores = [i["score"] for i in graded]
    fields = ("facts_cited", "indicators_correct", "judgment_reasoned", "counter_argument_present")
    report = {
        "phase": PHASE, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_seconds": round(time.time() - t0, 1),
        "model": model, "judge_model": judge_model,
        "money_spent_usd": round(sum(i.get("cost_usd") or 0.0 for i in items), 6),
        "target": TARGET,
        "counts": {"questions": len(items), "ok": sum(1 for i in items if i.get("status") == "ok"),
                   "graded": len(graded), "failures": len(failures),
                   "not_enough_data": sum(1 for i in items if i.get("status") == "not_enough_data")},
        "mean_score": mean(scores),
        "field_means": {f: mean([i.get(f) for i in graded]) for f in fields},
        "failures": failures,
        "items": items,
    }
    report["pass"] = bool(report["mean_score"] is not None
                          and report["mean_score"] >= TARGET
                          and len(graded) >= N_QUESTIONS)
    return report


def _md(report: dict) -> str:
    c = report["counts"]
    lines = [
        "# P7 rubric — 30 analyst-mode questions (gold-set addition)",
        "",
        f"- questions: {c['questions']} · ok: {c['ok']} · graded: {c['graded']} · "
        f"failures: {c['failures']}",
        f"- writer: `{report['model']}` · judge: `{report['judge_model']}` "
        f"(different family from the extractor)",
        f"- mean rubric score: {report['mean_score']} (target >= {report['target']}) · "
        f"result: {'PASS' if report['pass'] else 'FAIL'}",
        f"- spend: ${report['money_spent_usd']:.4f} · wall: {report['wall_seconds']} s",
        "",
        "| rubric field | mean |",
        "|---|---|",
    ]
    for f, v in report["field_means"].items():
        lines.append(f"| {f} | {v} |")
    lines += ["", "## Sampled items", "",
              "| id | segment | topic | status | score |", "|---|---|---|---|---|"]
    for i in report["items"][:10]:
        lines.append(f"| {i['id']} | {i['segment']} | {i['topic']} | {i.get('status')} | "
                     f"{i.get('score')} |")
    lines += ["", "## Deviations", "",
              "- D19: rubric-graded analyst set (30 questions, segment × topic grid), judge from "
              "a different model family; ungraded questions are excluded and the gate needs all "
              "30 graded."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb.p7_rubric",
                                 description="analyst-mode rubric set (P7 gold addition)")
    ap.add_argument("--n", type=int, default=N_QUESTIONS)
    ap.add_argument("--model", default=A.DEFAULT_MODEL)
    ap.add_argument("--judge-model", default=PA.JUDGE_MODEL)
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--report", action="store_true", help="also write kb/reports/p7_rubric.json")
    a = ap.parse_args(argv)
    con = PA.connect(a.db)
    try:
        report = run(con=con, n=a.n, model=a.model, judge_model=a.judge_model)
    finally:
        con.close()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    if a.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    counts = report.get("counts") or {}
    print(f"questions {counts.get('questions')} graded {counts.get('graded')} "
          f"mean {report.get('mean_score')} pass {report.get('pass')}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
