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
    assert rc == 0 and out.exists() and rep.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["tests"] >= 1
