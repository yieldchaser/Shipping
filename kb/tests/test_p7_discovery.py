"""Tests for kb/p7_discovery.py — cross-domain statistics, FDR, bridges, links, CLI."""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p7_discovery as D  # noqa: E402

MONTHS = [(2023 + (i // 12), 1 + i % 12) for i in range(36)]


def make_db(path: Path) -> Path:
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE series (series_id VARCHAR, name VARCHAR, unit VARCHAR,"
                " currency VARCHAR, basis VARCHAR, frequency VARCHAR,"
                " entity_ids VARCHAR[], source_csv VARCHAR, definition JSON)")
    con.execute("CREATE TABLE observation (series_id VARCHAR, period_from DATE, value DOUBLE,"
                " doc_id VARCHAR)")
    con.execute("CREATE TABLE event (event_id VARCHAR, type VARCHAR, occurred_from DATE)")
    con.execute("CREATE TABLE claim (claim_id VARCHAR, subject_ids VARCHAR[], published_at DATE)")
    specs = [("D1", "Capesize TC Average | Capesize", "freight"), ("D2", "Panamax TC Average", "freight"),
             ("W1", "VLCC 300k TD3 | VLCC", "wet"), ("W2", "Suezmax TD2", "wet"),
             ("O1", "iron ore 62% fe fines", "commodity")]
    rows = []
    for si, (sid, name, _dom) in enumerate(specs):
        ent = ["vessel:imo:1", f"series:{sid}"] if si in (0, 2) else [f"series:{sid}"]
        con.execute("INSERT INTO series VALUES (?, ?, 'usd', 'usd', 'spot', 'monthly', ?, ?, '{}')",
                    [sid, name, ent, f"csv_{sid}"])
        for i, (y, m) in enumerate(MONTHS):
            base = {"D1": 100.0, "D2": 90.0, "W1": 80.0, "W2": 70.0, "O1": 120.0}[sid]
            val = base * (1.0 + 0.20 * math.sin(i / 3.0) + 0.01 * (si + 1))
            if sid in ("D1", "W2"):
                val *= 1.0 + 0.03 * math.sin(i / 2.0)
            rows.append([sid, date(y, m, 1), round(val, 3), f"doc:{sid}"])
    con.executemany("INSERT INTO observation VALUES (?, ?, ?, ?)", rows)
    con.execute("INSERT INTO event VALUES ('ev:1', 'charter', DATE '2024-06-15')")
    con.execute("INSERT INTO claim VALUES ('c:1', ['vessel:imo:1'], DATE '2024-06-20')")
    con.execute("INSERT INTO claim VALUES ('c:2', ['series:D1'], DATE '2024-07-01')")
    con.close()
    return path


@pytest.fixture()
def db(tmp_path):
    return make_db(tmp_path / "kb.duckdb")


@pytest.fixture()
def con(db):
    c = duckdb.connect(str(db), read_only=True)
    yield c
    c.close()


def test_classify_series():
    assert D.classify_series("Capesize TC Average") == "freight_dry"
    assert D.classify_series("VLCC 300k TD3") == "freight_wet"
    assert D.classify_series("iron ore 62% fe fines") == "commodity_iron_ore"
    assert D.classify_series("Newbuild resale price") == "asset_newbuild"
    assert D.classify_series("random text") is None


def test_load_monthly_and_changes(con):
    data = D.load_monthly(con)
    assert set(data["series"]) >= {"D1", "D2", "W1", "W2", "O1"}
    rec = data["series"]["D1"]
    months, ch = D.monthly_changes(rec)
    assert len(months) == 35 and len(ch) == 35
    assert all(abs(v) <= 1.0 for v in ch)


def test_pearson_and_oos(con):
    data = D.load_monthly(con)
    x, y, common = D.align(data["series"]["D1"], data["series"]["D2"])
    pr = D.pearson(x, y)
    assert pr and -1 <= pr[0] <= 1 and pr[2] == len(common)
    assert D.pearson(np.zeros(30), np.ones(30)) is None
    assert D.oos_ok(np.linspace(-1, 1, 40), np.linspace(-1, 1, 40) * 2) is True
    assert D.oos_ok(np.linspace(-1, 1, 40), np.zeros(40)) is False
    assert D.oos_ok(np.arange(10.0), np.arange(10.0)) is False


def test_bh_fdr_bounds():
    q = D.bh_fdr([0.001, 0.01, 0.5, 0.9])
    assert len(q) == 4 and all(0.0 <= v <= 1.0 for v in q)
    assert q[0] <= q[-1]
    assert D.bh_fdr([]) == []


def test_lead_lag_and_comovement(con):
    data = D.load_monthly(con)
    ll = D.lead_lag(data["series"])
    assert ll and all(x["kind"] == "lead_lag" for x in ll)
    assert all(len(x["evidence"]) == 2 for x in ll)
    co = D.comovement(data["series"])
    assert co and all(x["kind"] == "comovement" for x in co)
    assert all(x["lag"] == 0 and x["n"] >= D.MIN_OVERLAP for x in co)


def test_bridges_entities(con):
    data = D.load_monthly(con)
    D.attach_entities(data["series"], con)
    br = D.bridges(data["series"], con)
    assert br and br[0]["a"] == "vessel:imo:1"
    assert br[0]["kind"] == "bridge" and br[0]["hops"] >= 3


def test_event_study_and_claims(con):
    data = D.load_monthly(con)
    D.attach_entities(data["series"], con)
    ev = D.event_study(data["series"], con)
    assert ev and all(x["kind"] == "event" for x in ev)
    cl = D.claims_cross_domain(data["series"], con)
    assert cl and cl[0]["a"] == "c:1"
    assert "c:2" not in [x["a"] for x in cl]


def test_survive_and_write_links(db):
    tests = [{"kind": "comovement", "a": "a", "b": "b", "stat": 0.5, "p": p, "lag": 0,
              "n": 30, "evidence": ["a", "b"]} for p in (1e-8, 0.4, 0.9)]
    kept = D.survive(tests)
    assert len(kept) == 1 and kept[0]["q"] <= D.ALPHA
    links = D.add_ids(kept + [{"kind": "bridge", "a": "e", "b": "d", "stat": 2.0, "p": 0.0,
                               "lag": 0, "n": 3, "evidence": ["e"]}])
    assert {l["label"] for l in links} == {"computed"}
    w = duckdb.connect(str(db))
    n = D.write_links(w, links)
    w.close()
    assert n == 2
    w = duckdb.connect(str(db), read_only=True)
    rows = w.execute("SELECT link_id, kind, label, evidence_ids FROM discovered_link"
                     " ORDER BY link_id").fetchall()
    w.close()
    assert len(rows) == 2 and rows[0][2] == "computed" and rows[0][3]


def test_build_report_counts(con):
    rep = D.build(con)
    assert rep["phase"] == "P7" and rep["sample_seed"] == D.seed_for("P7")
    assert rep["counts"]["series"] >= 5 and rep["counts"]["survivors"] >= 1
    assert rep["counts"]["written"] == 0
    assert len(rep["findings"]) <= D.MAX_FINDINGS
    qs = rep["questions"]
    assert 1 <= len(qs) <= D.N_QUESTIONS
    assert all(q["hops"] >= 3 and q["evidence"] for q in qs)


def test_main_writes_files(db, tmp_path, monkeypatch):
    out = tmp_path / "discovery.json"
    rep = tmp_path / "report.json"
    monkeypatch.setattr(D, "REPORT", rep)
    rc = D.main(["--db", str(db), "--out", str(out), "--report"])
    # Defect 10: both artefacts are written on every run, and the exit code is the frozen-gate
    # verdict — the five-series fixture cannot reach `discovery_questions_3hop: 20`, so it exits 1.
    assert out.exists() and rep.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["tests"] >= 1
    assert rc == (0 if data["pass"] else 1)
    assert rc == 1, "a discovery pass below the frozen gate must not report success"


# ---- Defect 35 (limb 3): on-disk stat/count reads, render guards, JSON writers ----
BIG = float("1" + "0" * 400)


def test_unreadable_readings_are_unmeasured_never_raised_or_fabricated():
    """Defect 35: a poisoned link row must read as unmeasured, not crash and not fake a number.

    `round(r, 4)` raised `OverflowError` on a 401-digit int literal, `float(len(...))`/`int(ln["n"])`
    raised `TypeError` on a string, and `inf`/`True` passed through as a real statistic.
    """
    assert D._stat(BIG) is None
    assert D._stat(float("inf")) is None and D._stat(float("nan")) is None
    assert D._stat(True) is None and D._stat("0.5") is None and D._stat(None) is None
    assert D._stat(0.123456) == 0.1235          # a real read survives, rounded
    assert D._stat(0.0) == 0.0                  # measured zero is not unmeasured

    assert D._count(BIG) is None
    assert D._count(float("inf")) is None and D._count(True) is None
    assert D._count("3") is None and D._count(None) is None
    assert D._count(2.5) is None                # a broken count, not a rounding
    assert D._count(3.0) == 3 and D._count(0) == 0

    # the render guards: unmeasured prints `n/a`, never `None`/`True`/`inf`, and an ISO date is text
    assert D._r(None) == "n/a" and D._r(BIG) == "n/a" and D._r(True) == "n/a"
    assert D._r(0.5) == "0.5" and D._r(0) == "0"
    assert D._text("2020-01-01") == "2020-01-01"
    assert D._text(None) == "n/a" and D._text("nan") == "n/a" and D._text("") == "n/a"


def test_json_safe_nullifies_non_finite_so_the_artefact_stays_parsable():
    """Defect 35: `json.dumps` emits bare `Infinity`/`NaN` tokens for a non-finite float."""
    safe = D._json_safe({"stat": BIG, "p": float("nan"), "nested": [float("-inf"), {"x": "inf"}]})
    text = json.dumps(safe)
    assert "Infinity" not in text and "NaN" not in text
    assert safe["stat"] is None and safe["p"] is None and safe["nested"][0] is None
    assert safe["nested"][1]["x"] == "inf"      # a *string* reading is data, left alone


def test_a_poisoned_row_degrades_to_sql_null_instead_of_raising(db):
    """Defect 35: the writer is where a poisoned upstream read used to kill the whole pass."""
    links = D.add_ids([{"kind": "comovement", "a": "a", "b": "b", "stat": BIG, "p": float("nan"),
                        "lag": "x", "n": True, "evidence": ["a"]}])
    w = duckdb.connect(str(db))
    try:
        assert D.write_links(w, links) == 1
        row = w.execute("SELECT stat, p_value, q_value, lag_months, n FROM discovered_link").fetchone()
    finally:
        w.close()
    assert row[0] is None and row[1] is None and row[2] is None
    assert row[3] is None and row[4] is None


def test_main_writes_strict_json_when_a_stat_is_non_finite(db, tmp_path, monkeypatch):
    """Defect 35, end-to-end: the writer, not just the helper, must keep the artefact parseable.

    Only `json.dumps(_json_safe(...))` survives: the default encoder writes `Infinity`, which
    `json.loads` (tests here) accepts but no strict JSON reader does, and the raw `default=str`
    fallback does not sanitise native floats at all.

    Defect 10: the exit code is now the frozen-gate verdict, so this case asserts the artefact stays
    strict JSON *and* that the code matches the verdict the pass actually computed.
    """
    real_build = D.build
    seen = {}

    def poisoned(con, **kw):
        rep = real_build(con, **kw)
        seen["pass"] = rep["pass"]
        rep["links"] = [{"kind": "comovement", "a": "a", "b": "b", "stat": BIG, "p": float("nan"),
                         "q": float("inf"), "lag": 0, "n": 30, "window_from": None,
                         "window_to": None, "evidence": ["a"], "link_id": "dl:00001",
                         "label": "computed"}]
        rep["counts"]["by_kind"]["comovement"] = 1
        return rep

    monkeypatch.setattr(D, "build", poisoned)
    out = tmp_path / "discovery.json"
    rep_path = tmp_path / "report.json"
    monkeypatch.setattr(D, "REPORT", rep_path)
    code = D.main(["--db", str(db), "--out", str(out), "--report"])
    assert code == (0 if seen["pass"] else 1), seen
    for path in (out, rep_path):
        text = path.read_text(encoding="utf-8")
        assert "Infinity" not in text and "NaN" not in text, path
        data = json.loads(text)
        assert data["links"][0]["stat"] is None
        assert data["links"][0]["p"] is None
        assert data["links"][0]["q"] is None


def test_main_exit_code_is_the_frozen_gate_verdict(db, tmp_path, monkeypatch):
    """Defect 10: `main` used to `return 0` unconditionally — a discovery pass that met nothing at
    all exited "success", and the frozen `discovered_links_*` operands were never read.

    Every way of missing the frozen gate must exit non-zero, including an unreadable `kb/gates.yaml`
    operand (UNMEASURED fails closed).
    """
    out = tmp_path / "discovery.json"
    monkeypatch.setattr(D, "REPORT", tmp_path / "report.json")
    assert D.main(["--db", str(db), "--out", str(out)]) == 1  # tiny fixture: gates unmet

    # a poisoned operand (readable nowhere) must not be able to look satisfied
    monkeypatch.setattr(D, "FDR_MAX", None)
    assert D.main(["--db", str(db), "--out", str(out)]) == 1
    monkeypatch.setattr(D, "FDR_MAX", 0.10)

    # and a pass is reported as pass only when every operand is readable and satisfied
    real_build = D.build

    def forced(con, **kw):
        rep = real_build(con, **kw)
        rep["gates"] = {k: {**g, "ok": True} for k, g in rep["gates"].items()}
        rep["pass"] = True
        return rep

    monkeypatch.setattr(D, "build", forced)
    assert D.main(["--db", str(db), "--out", str(out)]) == 0


# ---- Defect 40 (limb 3): the frozen `discovery_multihop_f1: 0.70` operand's missing producer ----


def test_discovery_multihop_f1_arm_reads_the_frozen_threshold(con):
    """Defect 40 (limb 3): `p7_report.check_discovery` read `dc["multihop_f1"]`, but `build` never
    wrote it and no module produced it — the C2 discovery arm was permanently UNMEASURED.

    The new arm must use the frozen operand name, READ `0.70` from `kb/gates.yaml` (never a literal),
    and sit in the same `{"value","target","ok"}` shape as the three existing arms.
    """
    rep = D.build(con)
    arm = rep["gates"]["discovery_multihop_f1"]
    assert set(arm) == {"value", "target", "ok"}
    assert arm["target"] == 0.70 == D.MIN_DISCOVERY_F1
    assert rep["multihop_f1"] == arm["value"]                 # the frozen consumer-facing key
    assert isinstance(rep["counts"]["questions_graded"], int)
    assert rep["counts"]["questions_graded"] == sum(
        1 for r in rep["graded_questions"] if r["status"] == "graded")
    assert rep["counts"]["questions_graded"] + sum(
        1 for r in rep["graded_questions"] if r["status"] == "ungraded") == len(rep["questions"])
    # `ok` is null exactly when either side is UNMEASURED; otherwise it is the comparison itself
    assert arm["ok"] == (None if (arm["value"] is None or arm["target"] is None)
                         else (arm["value"] >= arm["target"]))
    # the five-series fixture cannot reach `discovery_questions_3hop: 20`, so the pass still fails —
    # but the new arm is MEASURED here, not vacuous
    assert arm["ok"] is True and rep["pass"] is False
    text = json.dumps(D._json_safe(rep))
    assert "Infinity" not in text and "NaN" not in text


def test_multihop_f1_arm_satisfied_only_by_a_real_graded_mean(db, monkeypatch):
    """Defect 40 (limb 3): non-vacuity both ways — an UNMEASURED mean must fail closed, and a real
    graded mean must be what satisfies the arm. A `None` mean must never read as `ok: true`."""
    con = duckdb.connect(str(db), read_only=True)
    try:
        real = D.build(con)
    finally:
        con.close()
    arm = real["gates"]["discovery_multihop_f1"]
    assert real["counts"]["questions_graded"] >= 1
    assert arm["value"] is not None and arm["value"] >= arm["target"]
    assert arm["ok"] is True and real["multihop_f1"] is not None

    monkeypatch.setattr(D, "grade_questions",
                        lambda *a, **k: {"questions_f1": None, "graded": 0, "ungraded": 0, "rows": []})
    con = duckdb.connect(str(db), read_only=True)
    try:
        unmeasured = D.build(con)
    finally:
        con.close()
    arm = unmeasured["gates"]["discovery_multihop_f1"]
    assert arm["value"] is None and arm["target"] == 0.70 and arm["ok"] is None
    assert unmeasured["multihop_f1"] is None and unmeasured["counts"]["questions_graded"] == 0
    assert unmeasured["pass"] is False


def test_graded_mean_is_never_non_finite_or_bool(con):
    """Defect 40 (limb 3): a poisoned link `stat`/`n` (`True`, `inf`, `nan`, `"0.5"`, a 401-digit int)
    must read as an ABSENT component or an UNGRADED question — never `inf`, never `True` (which is a
    README-visible `bool` where a float belongs and, being a subclass of `int`, would also JSON-encode
    as `true`) and never a hardcoded `1.0`."""
    data = D.load_monthly(con)
    D.attach_entities(data["series"], con)
    qs = [{"id": f"D-{i:03d}", "question": "?", "kind": "comovement", "link_id": f"dl:{i:05d}",
           "hops": 3, "evidence": ["D1", "D2"]} for i in range(1, 3)]
    for poison in (True, False, float("inf"), float("-inf"), float("nan"), "0.5", BIG, None, 0.974):
        links = [{"link_id": f"dl:{i:05d}", "kind": "comovement", "a": "D1", "b": "D2",
                  "stat": poison, "p": 0.0, "lag": 0, "n": poison, "evidence": ["D1", "D2"],
                  "window_from": "2023-02-01 00:00:00", "window_to": "2025-12-01 00:00:00"}
                 for i in range(1, 3)]
        got = D.grade_questions(qs, links, data, con=con)
        f1 = got["questions_f1"]
        assert not isinstance(f1, bool), (poison, got)
        assert f1 is None or (isinstance(f1, float) and math.isfinite(f1)), (poison, got)
        assert got["graded"] + got["ungraded"] == len(qs)
        text = json.dumps(D._json_safe(got))
        assert "Infinity" not in text and "NaN" not in text, (poison, text)


def test_graded_mean_divides_by_graded_questions_only(con):
    """Defect 40 (limb 3): an ungradable question is dropped from the mean, not scored `0.0`, so the
    denominator is the graded count and `graded + ungraded == len(questions)` always holds."""
    data = D.load_monthly(con)
    D.attach_entities(data["series"], con)
    links = D.add_ids(D.survive(D.lead_lag(data["series"]) + D.comovement(data["series"])
                                + D.bridges(data["series"], con)))
    qs = D.bridge_questions(links)
    full = D.grade_questions(qs, links, data, con=con)
    assert full["graded"] == len(qs) and full["ungraded"] == 0
    assert full["questions_f1"] is not None

    victim = qs[-1]["link_id"]                      # lose one question's link row -> UNGRADED
    fewer = D.grade_questions(qs, [l for l in links if l["link_id"] != victim], data, con=con)
    assert fewer["graded"] == full["graded"] - 1 and fewer["ungraded"] == 1
    assert fewer["graded"] + fewer["ungraded"] == len(qs)
    remaining = [r["multihop_f1"] for r in fewer["rows"] if r["status"] == "graded"]
    assert fewer["questions_f1"] == round(sum(remaining) / len(remaining), 4)

    # nothing gradable at all is UNMEASURED, never `0.0`
    empty = D.grade_questions(qs, [], data, con=con)
    assert empty["questions_f1"] is None and empty["graded"] == 0
    assert empty["ungraded"] == len(qs) and all(r["status"] == "ungraded" for r in empty["rows"])

