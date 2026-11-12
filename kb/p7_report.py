"""P7 gate report + C2 evaluation packet.

Design note (D20):
- P7 has no spend of its own except the glm-5.3 escalation calls; this module only reads the
  artefacts other P7 scripts wrote and applies the §11/§12 gates mechanically. It never
  re-runs models, so a FAIL is a FAIL.
- Gate inputs: §12 Q&A eval (exact a/b/e/g, recall@20, multi-hop F1, refusal, faithfulness),
  the 30-question analyst rubric (mean >= 0.8, all graded), the >= 20-date backtest hit rate,
  and the discovery pass (>= 30 findings with evidence, 20 cross-domain questions with >= 3
  hops, `discovered_link` rows labelled `computed`).
- On PASS it writes kb/reports/p7.json + p7.md and the owner packet kb/reports/C2_EVAL.md.
  It never writes C2_APPROVED.md: only the owner's chat message can approve C2.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(KB_DIR))

ROOT = KB_DIR.parent
PHASE = "P7"
STATE = ROOT / "kb" / "state" / "p7"
REPORTS = ROOT / "kb" / "reports"
LEDGER = ROOT / "kb" / "state" / "ledger.sqlite"
TARGETS = {"exact_a_b_e_g": 0.97, "recall_at_20": 0.85, "multihop_f1": 0.75,
           "refusal": 0.95, "faithfulness": 0.95}
RUBRIC_TARGET = 0.8
MIN_QUESTIONS = 30
MIN_BACKTEST = 20
MIN_FINDINGS = 30
MIN_DISCOVERY_Q = 20


def load_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def spend_usd() -> float:
    try:
        con = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT coalesce(sum(cost_usd), 0) FROM jobs").fetchone()
        finally:
            con.close()
        return round(float(row[0] or 0.0), 4)
    except sqlite3.Error:
        return 0.0


def _mean(values: list[float]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else None


def check_eval(ev: dict) -> dict:
    m = (ev or {}).get("metrics") or {}
    gates = {}
    for k, target in TARGETS.items():
        v = m.get(k)
        gates[k] = {"value": v, "target": target,
                    "ok": (v is not None and isinstance(v, (int, float)) and v >= target)}
    count = (ev or {}).get("counts", {}).get("items", 0)
    return {"present": bool(ev), "counts": (ev or {}).get("counts", {}), "items": count,
            "metrics": m, "gates": gates,
            "ok": bool(ev) and count > 0 and all(g["ok"] for g in gates.values())}


def check_rubric(rb: dict) -> dict:
    c = (rb or {}).get("counts", {})
    graded = c.get("graded", 0) or 0
    score = (rb or {}).get("mean_score")
    ok = bool(rb) and isinstance(score, (int, float)) and score >= RUBRIC_TARGET \
        and graded >= MIN_QUESTIONS
    return {"present": bool(rb), "mean_score": score, "graded": graded,
            "target": RUBRIC_TARGET, "ok": ok,
            "field_means": (rb or {}).get("field_means", {})}


def check_backtest(bt: dict) -> dict:
    if not bt:
        return {"present": False, "dates": 0, "hit_rate": None, "ok": False}
    if "segments" in bt:  # multi-segment aggregate
        rows = bt["segments"]
        dates = max((r.get("dates", 0) for r in rows), default=0)
        n = sum(r.get("n", 0) for r in rows)
        hits = sum(r.get("hits", 0) for r in rows)
        rate = round(hits / n, 4) if n else None
    else:
        dates = bt.get("dates", 0)
        rate = bt.get("hit_rate")
        n = bt.get("n", 0)
    ok = dates >= MIN_BACKTEST and rate is not None
    return {"present": True, "dates": dates, "n": n, "hit_rate": rate,
            "target_dates": MIN_BACKTEST, "ok": ok}


def check_discovery(dc: dict) -> dict:
    if not dc:
        return {"present": False, "findings": 0, "questions": 0, "survivors": 0,
                "written": 0, "hops_ok": False, "findings_have_evidence": False,
                "ok": False}
    c = dc.get("counts", {})
    fnd = dc.get("findings") or []
    qs = dc.get("questions") or []
    hops_ok = all((q.get("hops") or 0) >= 3 for q in qs) if qs else False
    with_ev = all(bool(q.get("evidence")) for q in fnd) if fnd else False
    ok = len(fnd) >= MIN_FINDINGS \
        and len(qs) >= MIN_DISCOVERY_Q and hops_ok \
        and c.get("survivors", 0) >= len(fnd) and c.get("written", 0) == c.get("survivors", -1) \
        and with_ev
    return {"present": True, "findings": len(fnd), "questions": len(qs),
            "survivors": c.get("survivors", 0), "written": c.get("written", 0),
            "hops_ok": hops_ok, "findings_have_evidence": with_ev, "ok": bool(ok)}


def build(ev: dict | None, rb: dict | None, bt: dict | None, dc: dict | None,
          spend: float, wall: float | None = None) -> dict:
    eval_c = check_eval(ev or {})
    rubric_c = check_rubric(rb or {})
    bt_c = check_backtest(bt or {})
    dc_c = check_discovery(dc or {})
    checks = {"eval": eval_c, "rubric": rubric_c, "backtest": bt_c, "discovery": dc_c}
    ok = all(c["ok"] for c in checks.values())
    report = {
        "phase": PHASE, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_seconds": wall if wall is not None else 0.0,
        "money_spent_usd": round(float(spend or 0.0), 4),
        "targets": TARGETS, "rubric_target": RUBRIC_TARGET,
        "checks": checks,
        "gate": {"p7": ok},
        "pass": ok,
        "counts": {
            "eval_items": eval_c["items"],
            "rubric_graded": rubric_c["graded"],
            "backtest_dates": bt_c["dates"],
            "discovery_findings": dc_c["findings"],
            "discovery_questions": dc_c["questions"],
            "discovered_links": dc_c["written"],
        },
        "metrics": eval_c["metrics"],
        "model": (ev or {}).get("model"),
        "judge_model": (ev or {}).get("judge_model"),
    }
    return report


def _md(report: dict) -> str:
    c = report["checks"]
    lines = [
        "# P7 — tools, answer contract, CLI, Q&A eval",
        "",
        f"- result: **{'PASS' if report['pass'] else 'FAIL'}** · spend ${report['money_spent_usd']:.4f}"
        f" · wall {report['wall_seconds']} s",
        f"- eval items: {report['counts']['eval_items']} · writer `{report['model']}` · "
        f"judge `{report['judge_model']}`",
        "",
        "## §12 Q&A eval",
        "",
        "| metric | value | target | ok |",
        "|---|---|---|---|",
    ]
    for k, g in c["eval"]["gates"].items():
        lines.append(f"| {k} | {g['value']} | {g['target']} | {'yes' if g['ok'] else 'NO'} |")
    lines += ["", "## Gold-set additions", "",
              f"- analyst rubric: mean {c['rubric']['mean_score']} over "
              f"{c['rubric']['graded']} graded (target >= {RUBRIC_TARGET}) — "
              f"{'PASS' if c['rubric']['ok'] else 'FAIL'}",
              f"- backtest: {c['backtest']['dates']} dates, hit rate "
              f"{c['backtest']['hit_rate']} (>= {MIN_BACKTEST} dates) — "
              f"{'PASS' if c['backtest']['ok'] else 'FAIL'}",
              f"- discovery: {c['discovery']['findings']} findings · "
              f"{c['discovery']['questions']} questions (>= 3 hops: "
              f"{c['discovery']['hops_ok']}) · {c['discovery']['written']} "
              f"`discovered_link` rows — {'PASS' if c['discovery']['ok'] else 'FAIL'}",
              "", "## Deviations", "",
              "- D16: exact-match scoring compares gold numbers (with tolerance) against numbers "
              "printed in the answer; unit/rounding tolerant.",
              "- D17: faithfulness is judged by nim `openai/gpt-oss-120b` on a seeded, reproducible "
              "sample of answers.",
              "- D18: discovery statistics are Pearson lead/lag and co-movement on monthly percent "
              "changes with BH-FDR and an out-of-sample split; bridges/events/claims are "
              "descriptive and labelled `computed`.",
              "- D19: 30 analyst-mode questions on a segment × topic grid, rubric-graded by a "
              "different model family; all 30 must be graded to pass.",
              "- D20: this report only aggregates artefacts; it never re-runs models, so skipped "
              "metrics fail the gate."]
    return "\n".join(lines) + "\n"


def _c2_md(report: dict, dc: dict | None, rb: dict | None, bt: dict | None,
           ev: dict | None) -> str:
    c = report["checks"]
    lines = [
        "# C2 evaluation — P7 complete, request to publish the snapshot",
        "",
        f"Built {report['built_at']} · real pipeline spend ${report['money_spent_usd']:.4f} of the "
        f"$82 cap · result **{'PASS' if report['pass'] else 'FAIL'}**.",
        "",
        "## 1. Q&A eval (§12 targets)",
        "",
    ]
    for k, g in c["eval"]["gates"].items():
        lines.append(f"- {k}: {g['value']} (target {g['target']}) — {'PASS' if g['ok'] else 'FAIL'}")
    lines += ["", f"Items in the gold set: {report['counts']['eval_items']}.", "",
              "## 2. Gold-set additions", "",
              f"- Analyst-mode rubric: {c['rubric']['graded']} questions graded, mean "
              f"{c['rubric']['mean_score']} (target {RUBRIC_TARGET}), judge "
              f"`{(rb or {}).get('judge_model')}`.",
              f"- Backtest: {c['backtest']['dates']} historical dates, directional hit rate "
              f"{c['backtest']['hit_rate']} (reported, not a gate).",
              f"- Discovery: {c['discovery']['findings']} findings, "
              f"{c['discovery']['questions']} cross-domain questions needing >= 3 hops, "
              f"{c['discovery']['written']} rows in `discovered_link` labelled `computed`.",
              "", "## 3. Top 30 discovered findings (computed, with evidence)", ""]
    fnd = (dc or {}).get("findings") or []
    for i, f in enumerate(fnd[:MIN_FINDINGS], 1):
        lines.append(f"{i}. **{f['kind']}** {f['a']} -> {f['b']} · stat {f.get('stat')} · "
                     f"q {f.get('q')} · n {f.get('n')} · window {f.get('window_from')}.."
                     f"{f.get('window_to')} · evidence {', '.join(str(e) for e in (f.get('evidence') or [])[:6])}")
    lines += ["", "## 4. Discovery questions (>= 3 hops)", ""]
    for q in ((dc or {}).get("questions") or [])[:MIN_DISCOVERY_Q]:
        lines.append(f"- {q['id']} ({q['kind']}, hops {q['hops']}): {q['question']}")
    if not (dc or {}).get("questions"):
        lines.append("- none produced")
    lines += ["", "## 5. Recommendation", "",
              f"- P7 gate: {'PASS' if report['pass'] else 'FAIL'}. "
              f"{'Recommend publishing the snapshot and starting P8.' if report['pass'] else 'Do not publish yet.'}",
              "- C2 needs the owner's chat approval before P8 and the release; this file is the "
              "evaluation packet only (`kb/reports/C2_APPROVED.md` is written from the owner's "
              "message, never by the agent)."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb.p7_report", description="P7 gate + C2 packet")
    ap.add_argument("--eval", default=str(REPORTS / "p7_eval.json"))
    ap.add_argument("--rubric", default=str(STATE / "rubric.json"))
    ap.add_argument("--backtest", default=str(STATE / "backtest.json"))
    ap.add_argument("--discovery", default=str(STATE / "discovery.json"))
    ap.add_argument("--out", default=str(REPORTS / "p7.json"))
    ap.add_argument("--md", default=str(REPORTS / "p7.md"))
    ap.add_argument("--c2", default=str(REPORTS / "C2_EVAL.md"))
    ap.add_argument("--write", action="store_true", help="write reports and the C2 packet")
    a = ap.parse_args(argv)
    ev = load_json(Path(a.eval), None)
    rb = load_json(Path(a.rubric), None)
    bt = load_json(Path(a.backtest), None)
    dc = load_json(Path(a.discovery), None)
    wall = 0.0
    for d in (ev, rb, bt, dc):
        if isinstance(d, dict):
            wall += float(d.get("wall_seconds") or 0.0)
    report = build(ev, rb, bt, dc, spend_usd(), wall)
    print(json.dumps(report, indent=1, default=str))
    if a.write:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        Path(a.md).write_text(_md(report), encoding="utf-8")
        Path(a.c2).write_text(_c2_md(report, dc, rb, bt, ev), encoding="utf-8")
        print(f"wrote {out.name}, {Path(a.md).name}, {Path(a.c2).name}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
