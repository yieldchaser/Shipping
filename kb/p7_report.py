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

import money as M  # noqa: E402

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


def spend_usd() -> float | None:
    """Real pipeline spend from the ledger, or None if it cannot be read.

    Was `-> float` with `except sqlite3.Error: return 0.0`. That is the Defect 17 shape a second time:
    the C2 packet is the owner's *approval* artefact and it prints "real pipeline spend $X of the $82
    cap", so an unreadable/locked ledger made it assert **$0.0000** — a confident false statement about
    money, in the one document whose whole purpose is to justify publishing. `p6_summary.phase_spend_usd`
    already returns None for exactly this reason; \"unmeasured\" is the honest value, and a reader can
    tell it apart from \"measured, and it was zero\".
    """
    try:
        con = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT count(*), sum(cost_usd) FROM jobs").fetchone()
        finally:
            con.close()
        if not row or not row[0]:
            return None  # nothing booked at all: unmeasured, not a measured $0.0000
        # Defect 34, same read: a `sum(cost_usd)` that is NaN/+-inf is an unreadable ledger, not a
        # spend, and `round_usd(inf)` returned `inf` so `fmt_usd` rendered `$inf` into the C2 packet.
        total = M.as_float(row[1])
        if total is None:
            return None
        # 6 dp, not 4: `round(x, 4)` turned the real P6 phase spend (`$0.000013`) into `0.0`, so the
        # later `M.round_usd(spend)` in `build()` could not recover what this line had already
        # destroyed (Defect-17 class, Lesson 67 - a fixed-precision read is a lossy read).
        return M.round_usd(total)
    except (sqlite3.Error, OSError, ValueError):
        return None


def spend_text(report: dict) -> str:
    """`$1.2345`, or `UNMEASURED (ledger unreadable)` — never a fake `$0.0000` for a real spend."""
    return M.fmt_usd(report.get("money_spent_usd"),
                     unmeasured="UNMEASURED (ledger unreadable)")


def _cap_num(v) -> float | None:
    """Config/report cap as a true finite float, or None — the money-path guard, single-sourced.

    Kept as a local alias so call sites read in this module's vocabulary; the rule itself (bool and
    NaN/inf are broken reads, not denominators) lives in `money.as_float` so no module can re-implement
    it slightly differently.
    """
    return M.as_float(v)


def pipeline_cap() -> float | None:
    """The committed pipeline cap from `kb/config.yaml` `budget.pipeline_cap_usd`.

    The C2 packet used to hardcode the string `$82` in its first line while the cap actually lives in
    config and has already been amended once on this project. That denominator is exactly the kind of
    number a reader trusts without checking, and a stale one turns "spend of cap" into a false
    statement in the approval artefact. Read it; return None rather than guessing if unreadable, so the
    packet says so instead of printing a number it cannot support.
    """
    try:
        import yaml
        cfg = yaml.safe_load((KB_DIR / "config.yaml").read_text(encoding="utf-8")) or {}
        return _cap_num((cfg.get("budget") or {}).get("pipeline_cap_usd"))
    except (OSError, ValueError, ImportError, AttributeError):
        return None


def spend_text_full(report: dict) -> str:
    """`$1.2345 of the $82 cap`, degrading to a riderless amount / UNMEASURED.

    Takes the cap from the report when `build` recorded it (so the rendered text matches the JSON),
    and only falls back to reading config for reports built before the cap was added. Both routes go
    through `_cap_num`, so the report-supplied cap is guarded by the same bool/NaN rule as the config
    read — the packet must not render "of the $1 cap" from either source.
    """
    cap = _cap_num(report.get("pipeline_cap_usd"))
    if cap is None:
        cap = _cap_num(pipeline_cap())
    tail = f" of the ${cap:g} cap" if cap is not None else ""
    return spend_text(report) + tail


def _metric(v) -> float | None:
    """A §12 metric as a true in-range score, or None — the one grade-scale rule, single-sourced.

    Kept as a local alias so call sites read in this module's vocabulary. The rule (a bool, NaN, +-inf
    or an off-scale number is a broken read, not a passing metric) lives in `money.unit_score`, so this
    gate module cannot re-implement it slightly differently (Defect 24 / Lesson 73).
    """
    return M.unit_score(v)


def _count(v) -> float | None:
    """An artefact count that a gate *compares*, as a true finite number — or None.

    Defect 27: `items`, `graded`, `dates`, `n`, `hits`, `hops`, `survivors` and `written` are read out
    of on-disk artefact JSON and then compared (`>= MIN_BACKTEST`, `>= MIN_QUESTIONS`, `> 0`, `>= 3`,
    `==`). Passed through raw, an artefact holding `true` read as 1 and one holding an overflow
    to `inf` read as a huge number, so `inf >= 20` / `inf >= 30` / `True > 0` all PASSED a §13 gate
    the artefact cannot support; a string count (`"20"`) raised `TypeError` straight out of `main()`
    instead of producing a FAIL packet. `inf` in a `sum()` also fabricated a `hit_rate`. This is the
    Defect-24 shape one field over — a gate-operand read of an untrusted artefact — so it goes through
    the single-sourced numeric guard: unreadable ⇒ None ⇒ the gate FAILS as unmeasured.
    Integral results stay `int` so this module's renders and comparisons are unchanged in vocabulary.
    """
    f = M.as_float(v)
    if f is None:
        return None
    # A *count* is a whole number of things. `20.5 dates` cannot come from any producer (`len(rows)`),
    # so it is a broken artefact; letting it through would satisfy `>= MIN_BACKTEST` (20) on a count the
    # producer can never emit. This is a type rule layered on the shared finite guard, not a rival copy
    # of it: `M.as_float` has already rejected bool/NaN/inf, and `_count` still reaches it (R3-pinned).
    if not f.is_integer():
        return None
    return int(f)


def _mean(values: list[float]) -> float | None:
    vals = [f for f in (M.as_float(v) for v in values) if f is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _r(v) -> str:
    """Render a possibly-unmeasured artefact read; UNMEASURED must never print as `None`/raw `True`.

    Defect 27 twin: `hit_rate` is reported rather than gated, and the discovery questions are printed
    straight from the artefact, so both still reach this output file. A broken read is unmeasured and
    says so — it must not render `inf`, `True`, `"0.5"` or a bare `None` into the C2 packet.

    Defect 34: guarding only `None` was not enough. Every *non-`None* broken read still rendered
    itself — an overflow-to-`inf` metric printed `inf`, a YAML/JSON `true` printed `True`, a quoted
    `"0.5"` printed `0.5` — straight into `p7.md` and the owner's approval packet. The render is a
    numeric read of an untrusted artefact, so it goes through the single-sourced finite guard:
    unreadable reads as `n/a`, and a real read still renders itself.
    """
    return "n/a" if M.as_float(v) is None else str(v)


def _text(v) -> str:
    """Render a genuinely-textual artefact field the way `_r` renders a numeric one.

    The findings' `window_from`/`window_to` are ISO dates (`p7_discovery` writes `str(min(common))`),
    not the `..`-joined month pair an offline reader would assume, so `_count` would reject the honest
    `"2020-01-01"` and `_r` would reject it too. A string still gets the Defect-34 treatment: an
    unreadable sentinel (`None`, `""`, `"nan"`, `"inf"`) reads as `n/a`, never as itself.
    """
    if not isinstance(v, str):
        return _r(v)
    return "n/a" if v.strip().lower() in ("", "none", "nan", "inf", "-inf", "infinity") else v


def _json_safe(obj):
    """A report tree safe to `json.dumps`: a non-finite float is unmeasured (`null`), never `Infinity`.

    Defect 34: `json.dumps` writes the non-standard tokens `Infinity`/`NaN` by default, so a broken
    artefact metric reachable from the report made `kb/reports/p7.json` *not JSON* — every downstream
    reader (and any strict parser) fails on the artefact the C2 packet is built from. The guard is the
    same shared one, so an unreadable number serialises as `null` (unmeasured), never a fake number.
    """
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and M.as_float(obj) is None:
        return None
    return obj


def check_eval(ev: dict) -> dict:
    m = (ev or {}).get("metrics") or {}
    gates = {}
    scores = {}
    for k, target in TARGETS.items():
        v = m.get(k)
        score = _metric(v)
        # Defect 34: the row stored the *raw* artefact read, so the render sites downstream (`p7.md`,
        # `C2_EVAL.md`, `p7.json`) reprinted an unreadable `inf`/`true`/`"0.5"` verbatim. The row now
        # carries the guarded read — a real metric renders itself, a broken one is None ⇒ `n/a`.
        gates[k] = {"value": score, "target": target,
                    "ok": (score is not None and score >= target)}
        scores[k] = score
    # Defect 27: `items` is the §12 gate operand (`count > 0`), read out of an on-disk artefact.
    count = _count((ev or {}).get("counts", {}).get("items", 0))
    return {"present": bool(ev), "counts": (ev or {}).get("counts", {}), "items": count,
            "metrics": scores, "gates": gates,
            "ok": bool(ev) and count is not None and count > 0
            and all(g["ok"] for g in gates.values())}


def check_rubric(rb: dict) -> dict:
    c = (rb or {}).get("counts", {})
    # Absent `graded` keeps the artefact's documented zero-count convention; a *present* but unreadable
    # one is a broken read (Defect 23 distinction), and `_count` then returns None so the §13 arm FAILS.
    graded = _count(c["graded"]) if "graded" in c else 0
    score = (rb or {}).get("mean_score")
    mean = _metric(score)
    ok = bool(rb) and mean is not None and mean >= RUBRIC_TARGET \
        and graded is not None and graded >= MIN_QUESTIONS
    # Defect 34: store the guarded read (see `check_eval`), not the raw artefact value the packet used
    # to reprint. `field_means` is rendered nowhere, but it is still sanitised on the JSON write path.
    return {"present": bool(rb), "mean_score": mean, "graded": graded,
            "target": RUBRIC_TARGET, "ok": ok,
            "field_means": (rb or {}).get("field_means", {})}


def _seg_count(rows: list, key: str):
    """One segment's guarded count; a segment that is not a row dict reads as unmeasured."""
    return [_count(r.get(key, 0)) if isinstance(r, dict) else None for r in rows]


def _agg(vals: list, how: str = "sum"):
    """Aggregate guarded segment counts: any unreadable member makes the whole aggregate unmeasured."""
    if any(v is None for v in vals):
        return None
    return (max(vals) if how == "max" else sum(vals)) if vals else 0


def check_backtest(bt: dict) -> dict:
    if not bt:
        return {"present": False, "dates": 0, "hit_rate": None, "ok": False}
    if "segments" in bt:  # multi-segment aggregate
        rows = bt["segments"] if isinstance(bt["segments"], list) else []
        dates = _agg(_seg_count(rows, "dates"), "max")
        n = _agg(_seg_count(rows, "n"))
        hits = _agg(_seg_count(rows, "hits"))
        # The rate is computed from guarded counts and is itself a gate operand (`rate is not None`),
        # so an incoherent pair (hits > n) is a broken read rather than a rendered `1.5`.
        rate = _metric(round(hits / n, 4)) if (n and hits is not None) else None
    else:
        dates = _count(bt.get("dates", 0))
        rate = _metric(bt.get("hit_rate"))
        n = _count(bt.get("n", 0))
    ok = dates is not None and dates >= MIN_BACKTEST and rate is not None
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
    hops = [_count(q["hops"]) if isinstance(q, dict) and "hops" in q else 0 for q in qs]
    hops_ok = bool(hops) and all(h is not None and h >= 3 for h in hops)
    with_ev = all(bool(q.get("evidence")) for q in fnd) if fnd else False
    # The `-1` default preserves the artefact's existing sentinel semantics for a missing `survivors`
    # key: the equality arm must FAIL then, not read as `0 == 0` and pass on an absent count.
    survivors = _count(c.get("survivors", -1))
    written = _count(c.get("written", 0))
    ok = len(fnd) >= MIN_FINDINGS \
        and len(qs) >= MIN_DISCOVERY_Q and hops_ok \
        and survivors is not None and survivors >= len(fnd) \
        and written is not None and written == survivors and with_ev
    return {"present": True, "findings": len(fnd), "questions": len(qs),
            "survivors": _count(c.get("survivors", 0)), "written": _count(c.get("written", 0)),
            "hops_ok": hops_ok, "findings_have_evidence": with_ev, "ok": bool(ok)}


def build(ev: dict | None, rb: dict | None, bt: dict | None, dc: dict | None,
          spend: float | None, wall: float | None = None) -> dict:
    eval_c = check_eval(ev or {})
    rubric_c = check_rubric(rb or {})
    bt_c = check_backtest(bt or {})
    dc_c = check_discovery(dc or {})
    checks = {"eval": eval_c, "rubric": rubric_c, "backtest": bt_c, "discovery": dc_c}
    ok = all(c["ok"] for c in checks.values())
    # Defect 34, the same read one field over: `wall` is summed from artefact `wall_seconds` and
    # `spend` is a return value, so an overflow-to-`inf` either way rendered `wall inf s` and
    # `money_spent_usd: Infinity` into the report the C2 packet quotes. Unreadable ⇒ unmeasured.
    wall_f = M.as_float(wall)
    spend_f = M.as_float(spend)
    report = {
        "phase": PHASE, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_seconds": wall_f if wall_f is not None else 0.0,
        "money_spent_usd": M.round_usd(spend_f) if spend_f is not None else None,  # 6 dp: see spend_usd
        "pipeline_cap_usd": pipeline_cap(),
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
        f"- result: **{'PASS' if report['pass'] else 'FAIL'}** · spend {spend_text(report)}"
        f" · wall {_r(report['wall_seconds'])} s",
        f"- eval items: {_r(report['counts']['eval_items'])} · writer `{report['model']}` · "
        f"judge `{report['judge_model']}`",
        "",
        "## §12 Q&A eval",
        "",
        "| metric | value | target | ok |",
        "|---|---|---|---|",
    ]
    for k, g in c["eval"]["gates"].items():
        lines.append(f"| {k} | {_r(g['value'])} | {g['target']} | {'yes' if g['ok'] else 'NO'} |")
    lines += ["", "## Gold-set additions", "",
              f"- analyst rubric: mean {_r(c['rubric']['mean_score'])} over "
              f"{_r(c['rubric']['graded'])} graded (target >= {RUBRIC_TARGET}) — "
              f"{'PASS' if c['rubric']['ok'] else 'FAIL'}",
              f"- backtest: {_r(c['backtest']['dates'])} dates, hit rate "
              f"{_r(c['backtest']['hit_rate'])} (>= {MIN_BACKTEST} dates) — "
              f"{'PASS' if c['backtest']['ok'] else 'FAIL'}",
              f"- discovery: {_r(c['discovery']['findings'])} findings · "
              f"{_r(c['discovery']['questions'])} questions (>= 3 hops: "
              f"{'yes' if c['discovery']['hops_ok'] else 'NO'}) · {_r(c['discovery']['written'])} "
              f"`discovered_link` rows — {'PASS' if c['discovery']['ok'] else 'FAIL'}",
              "", "## Deviations", "",
              "- D16: exact-match scoring compares gold numbers (with tolerance) against numbers "
              "printed in the answer; unit/rounding tolerant.",
              "- D17: faithfulness is judged by Google `Gemma-4-31B-IT` on AMD Token Lab (family "
              "gemma, owner amendment 2026-11-15 replacing the NIM free tier; fallback "
              "`Qwen3.8-27B`) on a seeded, reproducible sample of answers.",
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
        f"Built {report['built_at']} · real pipeline spend {spend_text_full(report)} · "
        f"result **{'PASS' if report['pass'] else 'FAIL'}**.",
        "",
        "## 1. Q&A eval (§12 targets)",
        "",
    ]
    for k, g in c["eval"]["gates"].items():
        lines.append(f"- {k}: {_r(g['value'])} (target {g['target']}) — {'PASS' if g['ok'] else 'FAIL'}")
    lines += ["", f"Items in the gold set: {_r(report['counts']['eval_items'])}.", "",
              "## 2. Gold-set additions", "",
              f"- Analyst-mode rubric: {_r(c['rubric']['graded'])} questions graded, mean "
              f"{_r(c['rubric']['mean_score'])} (target {RUBRIC_TARGET}), judge "
              f"`{(rb or {}).get('judge_model')}`.",
              f"- Backtest: {_r(c['backtest']['dates'])} historical dates, directional hit rate "
              f"{_r(c['backtest']['hit_rate'])} (reported, not a gate).",
              f"- Discovery: {_r(c['discovery']['findings'])} findings, "
              f"{_r(c['discovery']['questions'])} cross-domain questions needing >= 3 hops, "
              f"{_r(c['discovery']['written'])} rows in `discovered_link` labelled `computed`.",
              "", "## 3. Top 30 discovered findings (computed, with evidence)", ""]
    fnd = (dc or {}).get("findings") or []
    for i, f in enumerate(fnd[:MIN_FINDINGS], 1):
        # Defect 34: `stat`, `q` and `n` are printed straight from the artefact. A Pearson `stat` or
        # BH-FDR `q` that overflowed to `inf` used to print `inf` into the owner packet. `stat`/`q` are
        # real fractions (a `_count` would wrongly reject the honest `0.4`), so they go through the
        # finite read; `n`/window bounds are counts and take the count rule. All render via `_r`.
        lines.append(f"{i}. **{f['kind']}** {f['a']} -> {f['b']} · stat {_r(f.get('stat'))} · "
                     f"q {_r(f.get('q'))} · n {_r(_count(f.get('n')))} · window "
                     f"{_text(f.get('window_from'))}..{_text(f.get('window_to'))} · "
                     f"evidence {', '.join(str(e) for e in (f.get('evidence') or [])[:6])}")
    lines += ["", "## 4. Discovery questions (>= 3 hops)", ""]
    for q in ((dc or {}).get("questions") or [])[:MIN_DISCOVERY_Q]:
        lines.append(f"- {q['id']} ({q['kind']}, hops {_r(_count(q.get('hops')))})"
                     f": {q['question']}")
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
        # Defect 34: `float(d.get("wall_seconds") or 0.0)` raised `ValueError` straight out of `main()`
        # on a string artefact field and read `inf` as a real wall time. Either way it is a broken read.
        w = M.as_float((d or {}).get("wall_seconds")) if isinstance(d, dict) else None
        if w is not None:
            wall += w
    report = build(ev, rb, bt, dc, spend_usd(), wall)
    # `_json_safe` before `dumps`: a non-finite artefact metric must not become the non-standard
    # `Infinity` token in `kb/reports/p7.json` (Defect 34 - the file must stay parseable JSON).
    dump = json.dumps(_json_safe(report), indent=1, default=str)
    print(dump)
    if a.write:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(dump, encoding="utf-8")
        Path(a.md).write_text(_md(report), encoding="utf-8")
        Path(a.c2).write_text(_c2_md(report, dc, rb, bt, ev), encoding="utf-8")
        print(f"wrote {out.name}, {Path(a.md).name}, {Path(a.c2).name}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
