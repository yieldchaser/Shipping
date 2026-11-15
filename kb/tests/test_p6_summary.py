"""Tests for P6 (time-tree summaries). Pure functions + fixture-DB integration, no network."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kb"))

import p6_summary as P  # noqa: E402


# ------------------------------------------------------------------ fixture DB
def make_db(path: Path) -> Path:
    con = duckdb.connect(str(path))
    con.execute("""CREATE TABLE document(doc_id VARCHAR PRIMARY KEY, path VARCHAR, publisher_id VARCHAR,
                   doc_type VARCHAR, published_at DATE NOT NULL)""")
    con.execute("""CREATE TABLE chunk(chunk_id VARCHAR PRIMARY KEY, doc_id VARCHAR, section_id VARCHAR,
                   ord INTEGER, kind VARCHAR, context_prefix VARCHAR, body VARCHAR, tokens INTEGER,
                   sha256 VARCHAR, norm_sha VARCHAR, is_duplicate_of VARCHAR, entity_ids VARCHAR[],
                   vec_row BIGINT, extract BOOLEAN)""")
    con.execute("""CREATE TABLE series(series_id VARCHAR PRIMARY KEY, name VARCHAR, unit VARCHAR,
                   currency VARCHAR, basis VARCHAR, frequency VARCHAR, entity_ids VARCHAR[],
                   source_csv VARCHAR, definition JSON)""")
    con.execute("""CREATE TABLE observation(obs_id BIGINT PRIMARY KEY, series_id VARCHAR,
                   period_from DATE, period_to DATE, value DOUBLE, unit VARCHAR, raw_cell VARCHAR,
                   doc_id VARCHAR, table_ord INTEGER, row_ord INTEGER, col_ord INTEGER,
                   published_at DATE, ingested_at TIMESTAMP, method VARCHAR, provenance VARCHAR,
                   supersedes BIGINT)""")
    con.execute("""CREATE TABLE event(event_id VARCHAR PRIMARY KEY, type VARCHAR, summary VARCHAR,
                   occurred_from DATE, occurred_to DATE, published_at DATE, location VARCHAR,
                   magnitude_printed VARCHAR, doc_id VARCHAR, chunk_id VARCHAR, sids INTEGER[],
                   quote VARCHAR, extractor VARCHAR, confidence DOUBLE)""")
    con.execute("""CREATE TABLE claim(claim_id VARCHAR PRIMARY KEY, kind VARCHAR, subject_ids VARCHAR[],
                   text_printed VARCHAR, horizon VARCHAR, direction VARCHAR, published_at DATE,
                   doc_id VARCHAR, chunk_id VARCHAR, sids INTEGER[], quote VARCHAR, extractor VARCHAR,
                   confidence DOUBLE)""")

    con.execute("INSERT INTO document VALUES ('d1','corpus/broker/w1.pdf','p1','broker_weekly',DATE '2026-03-06')")
    con.execute("INSERT INTO document VALUES ('d2','corpus/broker/w2.pdf','p1','broker_weekly',DATE '2026-04-10')")
    con.execute("""INSERT INTO chunk VALUES ('c1','d1','s1',0,'prose','',
                   'Capesize spot averaged USD 24,500/day this week. Panamax softened.',40,'x','x',NULL,NULL,NULL,TRUE)""")
    con.execute("""INSERT INTO chunk VALUES ('c2','d2','s1',0,'prose','',
                   'VLCC rates rose to USD 51,000/day on the Middle East route.',30,'y','y',NULL,NULL,NULL,TRUE)""")
    con.execute("""INSERT INTO chunk VALUES ('c3','d1','s2',0,'prose','',
                   'The corner shop sold nothing and iron ore stayed flat.',20,'z','z',NULL,NULL,NULL,TRUE)""")
    con.execute("""INSERT INTO series VALUES ('s:cape','capesize_spot::rate | Capesize','usd/day',NULL,NULL,
                   'weekly',NULL,'bancosta_freight_rates_series','{}')""")
    con.execute("""INSERT INTO series VALUES ('s:vlcc','vlcc_spot::rate | VLCC','usd/day',NULL,NULL,
                   'weekly',NULL,'gibson_tanker_spot_series','{}')""")
    con.execute("""INSERT INTO series VALUES ('s:grain','grain_index::value | Corn','usd/bu',NULL,NULL,
                   'weekly',NULL,'bancosta_commodities_series','{}')""")
    con.execute("""INSERT INTO observation VALUES (101,'s:cape',DATE '2026-03-01',DATE '2026-03-07',24500,'usd/day',
                   '24,500','d1',0,0,0,DATE '2026-03-06',TIMESTAMP '2026-03-06 10:00:00','csv','reported_table',NULL)""")
    con.execute("""INSERT INTO observation VALUES (102,'s:vlcc',DATE '2026-04-01',DATE '2026-04-07',51000,'usd/day',
                   '51,000','d2',0,0,0,DATE '2026-04-10',TIMESTAMP '2026-04-10 10:00:00','csv','reported_table',NULL)""")
    con.execute("""INSERT INTO event VALUES ('ev1','sale','Capesize vessel sold for USD 26 M',DATE '2026-03-02',
                   DATE '2026-03-02',DATE '2026-03-06',NULL,'USD 26 M','d1','c1',[1],'Sold for USD 26 M','x',0.9)""")
    con.execute("""INSERT INTO claim VALUES ('cl1','forecast',[],'Capesize rates to rise in Q2','Q2','up',
                   DATE '2026-03-06','d1','c1',[1],'Rates to rise','x',0.7)""")
    con.close()
    return path


@pytest.fixture()
def db(tmp_path):
    return make_db(tmp_path / "kb_fixture.duckdb")


@pytest.fixture()
def con(db):
    c = duckdb.connect(str(db), read_only=True)
    yield c
    c.close()


# ------------------------------------------------------------------ periods
def test_period_roundtrip():
    assert P.period_of(date(2026, 3, 6), "month") == "2026-03"
    assert P.period_of(date(2026, 3, 6), "quarter") == "2026-Q1"
    assert P.period_of(date(2026, 3, 6), "year") == "2026"
    assert P.period_bounds("2026-03") == (date(2026, 3, 1), date(2026, 3, 31))
    assert P.period_bounds("2026-12") == (date(2026, 12, 1), date(2026, 12, 31))
    assert P.period_bounds("2026-Q1") == (date(2026, 1, 1), date(2026, 3, 31))
    assert P.period_bounds("2026") == (date(2026, 1, 1), date(2026, 12, 31))


def test_parent_and_child_periods():
    assert P.parent_period("2026-05") == "2026-Q2"
    assert P.parent_period("2026-Q2") == "2026"
    assert P.parent_period("2026") is None
    assert P.child_periods("2026-Q2") == ["2026-04", "2026-05", "2026-06"]
    assert P.child_periods("2026") == ["2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"]
    assert P.child_periods("2026-03") == []


def test_node_id_is_stable_and_distinct():
    a = P.node_id("capesize", "month", "2026-03")
    assert a == P.node_id("capesize", "month", "2026-03")
    assert a != P.node_id("panamax", "month", "2026-03")
    assert a.startswith("n:")


# ------------------------------------------------------------------ segments
def test_segment_of_text_matches_plan_segments():
    assert "capesize" in P.segment_of_text("Capesize spot averaged USD 24,500/day")
    assert "vlcc" in P.segment_of_text("the VLCC market")
    assert "grains" in P.segment_of_text("corn and wheat futures")
    assert "bunkers" in P.segment_of_text("VLSFO bunkers fell")
    assert "mr_lr" in P.segment_of_text("LR2 product tanker rates")


def test_segment_of_text_word_boundaries():
    # "corner" must not be tagged as grains, "scraper" must not be demolition
    assert P.segment_of_text("the corner shop") == []
    assert P.segment_of_text("a scraper") == []


def test_series_segment_map_uses_name_and_source(con):
    segmap = P.series_segment_map(con)
    assert segmap["s:cape"] == ["capesize"]
    assert segmap["s:vlcc"] == ["vlcc"]
    assert "grains" in segmap["s:grain"]
    assert "s:none" not in segmap


# ------------------------------------------------------------------ evidence
def test_leaf_evidence_collects_all_four_kinds(con):
    segmap = P.series_segment_map(con)
    ev = P.leaf_evidence(con, "capesize", "2026-03", segmap)
    kinds = {e["kind"] for e in ev}
    assert {"obs", "chunk", "event", "claim"} <= kinds
    obs = [e for e in ev if e["kind"] == "obs"][0]
    assert obs["ref"] == "101"
    assert "24500" in obs["text"] or "24,500" in obs["text"]
    assert all(e["signature"] for e in ev)


def test_leaf_evidence_respects_month_window(con):
    segmap = P.series_segment_map(con)
    march = P.leaf_evidence(con, "vlcc", "2026-03", segmap)
    assert [e for e in march if e["kind"] == "obs"] == []  # VLCC obs is April
    april = P.leaf_evidence(con, "vlcc", "2026-04", segmap)
    assert [e for e in april if e["kind"] == "obs"][0]["ref"] == "102"


def test_leaf_evidence_caps_and_is_deterministic(con):
    segmap = P.series_segment_map(con)
    a = P.leaf_evidence(con, "capesize", "2026-03", segmap)
    b = P.leaf_evidence(con, "capesize", "2026-03", segmap)
    assert [e["ref"] for e in a] == [e["ref"] for e in b]
    assert len([e for e in a if e["kind"] == "chunk"]) <= P.LEAF_CHUNKS


def test_node_input_hash_changes_with_evidence():
    ev = [{"kind": "obs", "ref": "1", "text": "x", "signature": "aa"}]
    h1 = P.node_input_hash("capesize", "month", "2026-03", ev)
    h2 = P.node_input_hash("capesize", "month", "2026-03", ev)
    ev2 = [{"kind": "obs", "ref": "1", "text": "x", "signature": "bb"}]
    h3 = P.node_input_hash("capesize", "month", "2026-03", ev2)
    assert h1 == h2 and h1 != h3
    assert len(h1) == 32


# ------------------------------------------------------------------ parse / validate
def test_parse_summary_strips_bullets_and_reads_cites():
    text = ("- Capesize spot averaged USD 24,500/day [obs:101]\n"
            "2) Panamax softened [chunk:c1][obs:101]\n"
            "\n"
            "* no citation here\n")
    cands = P.parse_summary(text)
    assert len(cands) == 3
    assert cands[0]["sentence"] == "Capesize spot averaged USD 24,500/day"
    assert cands[0]["cites"] == ["obs:101"]
    assert cands[1]["cites"] == ["chunk:c1", "obs:101"]
    assert cands[2]["cites"] == []


def test_validate_sentences_keeps_good_drops_bad():
    ev = [{"kind": "obs", "ref": "101", "text": "capesize_spot: value 24,500 usd/day", "signature": "a"},
          {"kind": "chunk", "ref": "c1", "text": "Panamax softened.", "signature": "b"}]
    cands = [
        {"sentence": "Capesize spot averaged USD 24,500/day", "cites": ["obs:101"]},
        {"sentence": "Capesize averaged USD 99,999/day", "cites": ["obs:101"]},   # number not in evidence
        {"sentence": "Something with no citation", "cites": []},
        {"sentence": "Bogus cite", "cites": ["obs:999"]},
        {"sentence": "Panamax softened in Asia", "cites": ["chunk:c1"]},          # no numbers -> ok
    ]
    kept, drops = P.validate_sentences(cands, ev, max_sent=5)
    assert [k["sentence"] for k in kept] == ["Capesize spot averaged USD 24,500/day",
                                             "Panamax softened in Asia"]
    assert drops["number_not_in_evidence"] == 1
    assert drops["no_cite"] == 1
    assert drops["unknown_cite"] == 1
    assert drops["no_number_sentence_ok"] == 1


def test_validate_sentences_enforces_limit():
    ev = [{"kind": "obs", "ref": "1", "text": "x 5", "signature": "a"}]
    words = ["one", "two", "three", "four", "five"]
    cands = [{"sentence": f"line {w}", "cites": ["obs:1"]} for w in words]
    kept, drops = P.validate_sentences(cands, ev, max_sent=2)
    assert len(kept) == 2
    assert drops["over_limit"] == 3


def test_number_check_tolerates_units_and_rounding():
    # extracted evidence prints "24,500 usd/day"; a summary may write "USD 24,500/day"
    assert P.number_check_ok("spot averaged USD 24,500/day", "value 24,500 usd/day") is True
    assert P.number_check_ok("spot averaged USD 24,500/day", "value 24.5 thousand usd/day") is False
    assert P.number_check_ok("no digits at all", "value 24,500") is True
    assert P.number_check_ok("USD 30,000/day", "value 24,500 usd/day") is False


def test_summary_text_and_cites_dedupe():
    kept = [{"sentence": "A", "cites": ["obs:1", "chunk:2"]},
            {"sentence": "B", "cites": ["chunk:2", "event:3"]}]
    txt = P.summary_text(kept)
    assert txt == "A [obs:1][chunk:2] B [chunk:2][event:3]"
    assert P.summary_cites(kept) == ["obs:1", "chunk:2", "event:3"]


# ------------------------------------------------------------------ writer / judge injection
def good_writer(messages, **_kw):
    return {"status": "ok", "text": "- Capesize spot averaged USD 24,500/day [obs:101]", "usage": {}, "error": None}


def bad_writer(messages, **_kw):
    return {"status": "ok", "text": "- Capesize averaged USD 99,999/day [obs:101]", "usage": {}, "error": None}


def test_build_leaf_with_injected_writer(con, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "OUT", tmp_path)
    monkeypatch.setattr(P, "NODES", tmp_path / "nodes.jsonl")
    monkeypatch.setattr(P, "INDEX", tmp_path / "index.json")
    monkeypatch.setattr(P, "TREE", tmp_path / "tree.json")
    segmap = P.series_segment_map(con)
    node = P.build_leaf(con, {}, "capesize", "2026-03", segmap, writer=good_writer)
    assert node["status"] == "ok"
    assert node["segment"] == "capesize" and node["grain"] == "month" and node["period"] == "2026-03"
    assert node["sentences"][0]["cites"] == ["obs:101"]
    assert node["input_hash"]


def test_build_leaf_drops_unverifiable_numbers(con, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "OUT", tmp_path)
    segmap = P.series_segment_map(con)
    node = P.build_leaf(con, {}, "capesize", "2026-03", segmap, writer=bad_writer)
    assert node["status"] == "no_sentences"
    assert node["summary"] == ""
    assert node["drops"]["number_not_in_evidence"] == 1


def test_build_leaf_is_cached_when_hash_matches(con, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "OUT", tmp_path)
    segmap = P.series_segment_map(con)
    first = P.build_leaf(con, {}, "capesize", "2026-03", segmap, writer=good_writer)
    index = {first["node_id"]: {"input_hash": first["input_hash"], "status": "ok",
                                "summary": first["summary"], "sentences": first["sentences"]}}
    calls = []

    def counting_writer(messages, **kw):
        calls.append(1)
        return good_writer(messages)

    second = P.build_leaf(con, index, "capesize", "2026-03", segmap, writer=counting_writer)
    assert second["cached"] is True
    assert calls == []  # no model call on unchanged evidence


def test_build_leaf_without_evidence_is_marked(con, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "OUT", tmp_path)
    segmap = P.series_segment_map(con)
    node = P.build_leaf(con, {}, "lpg", "2026-03", segmap, writer=good_writer)
    assert node["status"] == "no_evidence"


# ------------------------------------------------------------------ parents
def test_top_evidence_dedupes_and_caps():
    children = [{"evidence": [{"kind": "obs", "ref": "1", "text": "a"},
                              {"kind": "obs", "ref": "1", "text": "a"}]},
                {"evidence": [{"kind": "chunk", "ref": "2", "text": "b"},
                              {"kind": "obs", "ref": "3", "text": "c"}]}]
    top = P.top_evidence(children, 2)
    assert [(e["kind"], e["ref"]) for e in top] == [("obs", "1"), ("chunk", "2")]


def test_build_parent_uses_children_and_carries_child_hashes(con, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "OUT", tmp_path)
    segmap = P.series_segment_map(con)
    leaves = [P.build_leaf(con, {}, "capesize", "2026-03", segmap, writer=good_writer)]
    ev_top = P.top_evidence(leaves, P.PARENT_TOP)
    parent = P.build_parent(con, {}, "capesize", "quarter", "2026-Q1", leaves, ev_top, writer=good_writer)
    assert parent["grain"] == "quarter" and parent["period"] == "2026-Q1"
    assert parent["children"] == [leaves[0]["node_id"]]
    assert parent["status"] == "ok"
    # changing a child's hash changes the parent's hash -> parent rebuilt
    h_before = parent["input_hash"]
    leaves2 = [dict(leaves[0], input_hash="deadbeef")]
    parent2 = P.build_parent(con, {}, "capesize", "quarter", "2026-Q1", leaves2, ev_top, writer=good_writer)
    assert parent2["input_hash"] != h_before


def test_build_parent_without_usable_children_is_empty(con, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "OUT", tmp_path)
    parent = P.build_parent(con, {}, "capesize", "year", "2026",
                            [{"node_id": "n:x", "input_hash": "aa", "status": "no_sentences", "summary": ""}],
                            [], writer=good_writer)
    assert parent["status"] == "no_evidence"


# ------------------------------------------------------------------ tree / report
def test_build_tree_dry_run_has_no_model_calls(con, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "OUT", tmp_path)
    monkeypatch.setattr(P, "NODES", tmp_path / "nodes.jsonl")
    monkeypatch.setattr(P, "INDEX", tmp_path / "index.json")
    monkeypatch.setattr(P, "TREE", tmp_path / "tree.json")

    def boom(*a, **kw):
        raise AssertionError("writer must not be called in dry mode")

    out = P.build_tree(con, months_back=1, segments=["capesize"], dry=True, writer=boom, progress=False)
    assert out["dry"] is True
    assert out["counts"]["leaves"] >= 1
    assert not (tmp_path / "nodes.jsonl").exists()


def test_build_tree_writes_index_and_tree(con, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "OUT", tmp_path)
    monkeypatch.setattr(P, "NODES", tmp_path / "nodes.jsonl")
    monkeypatch.setattr(P, "INDEX", tmp_path / "index.json")
    monkeypatch.setattr(P, "TREE", tmp_path / "tree.json")
    out = P.build_tree(con, months_back=2, segments=["capesize"], writer=good_writer, progress=False)
    assert out["counts"]["leaves"] >= 1
    index = json.loads((tmp_path / "index.json").read_text())
    assert any(v["grain"] == "month" for v in index.values())
    tree = json.loads((tmp_path / "tree.json").read_text())
    assert tree["segments"] == ["capesize"]
    # node lines are jsonl and re-loadable
    lines = [json.loads(x) for x in (tmp_path / "nodes.jsonl").read_text().splitlines() if x.strip()]
    assert len(lines) >= out["counts"]["leaves"]


def test_report_gate_requires_judge_faithfulness():
    index = {"n:a": {"grain": "month", "segment": "capesize", "period": "2026-03", "input_hash": "x",
                     "summary": "s", "sentences": [{"sentence": "s", "cites": ["obs:1"]}]}}
    build = {"counts": {"leaves": 1, "parents_q": 0, "parents_y": 0, "cached": 0, "empty": 0,
                        "sentences": 1, "dropped": 0}, "wall_seconds": 1.0}
    low = P.build_report(index, build, {"sampled": 60, "mean_score": 0.5, "faithful_rate": 0.8})
    assert low["gate_passed"] is False
    high = P.build_report(index, build, {"sampled": 60, "mean_score": 0.97, "faithful_rate": 0.97})
    assert high["gate_passed"] is True
    assert high["judge_family_differs_from_writer"] is True
    assert high["sample_seed"] == P.seed_for("P6")


def test_report_markdown_declares_design_and_gates():
    index = {"n:a": {"grain": "month", "segment": "capesize", "period": "2026-03", "input_hash": "x",
                     "summary": "s", "sentences": [{"sentence": "s", "cites": ["obs:1"]}]}}
    build = {"counts": {"leaves": 1, "parents_q": 0, "parents_y": 0, "cached": 0, "empty": 0,
                        "sentences": 1, "dropped": 0}, "wall_seconds": 2.0}
    md = P._md(P.build_report(index, build, {"sampled": 60, "mean_score": 0.99, "faithful_rate": 0.99}))
    assert "Design note" in md
    assert "number check" in md
    assert "PASSED" in md
    assert P.JUDGE_MODEL in md, "report must name the judge actually used (owner amendment 2026-11-15)"


def test_run_judge_streams_evidence_and_scores(monkeypatch, tmp_path):
    nodes = tmp_path / "nodes.jsonl"
    ev = [{"kind": "obs", "ref": "1", "text": "value 5", "signature": "a"}]
    rec = {"node_id": "n:a", "segment": "capesize", "grain": "month", "period": "2026-03",
           "evidence": ev, "sentences": [{"sentence": "spot was 5", "cites": ["obs:1"]}], "summary": "spot was 5 [obs:1]"}
    nodes.write_text(json.dumps(rec) + "\n")
    seen = {}

    def fake_judge(text, ev_arg, **_kw):
        seen["ev"] = ev_arg
        return {"score": 1.0, "verdict": "supported", "why": "ok", "error": None}

    index = {"n:a": {"grain": "month", "segment": "capesize", "period": "2026-03",
                     "summary": "spot was 5 [obs:1]",
                     "sentences": [{"sentence": "spot was 5", "cites": ["obs:1"]}]}}
    out = P.run_judge(index, n=1, seed=1, judge=fake_judge, path=nodes)
    assert out["sampled"] == 1
    assert out["faithful_rate"] == 1.0
    assert seen["ev"] == ev  # judge saw the stored evidence, not an empty list


def test_cli_dry_run_returns_zero(db, monkeypatch, tmp_path):
    monkeypatch.setattr(P, "OUT", tmp_path)
    monkeypatch.setattr(P, "NODES", tmp_path / "nodes.jsonl")
    monkeypatch.setattr(P, "INDEX", tmp_path / "index.json")
    monkeypatch.setattr(P, "TREE", tmp_path / "tree.json")
    monkeypatch.setattr(P, "REPORTS", tmp_path / "reports")
    rc = P.main(["--db", str(db), "--months-back", "1", "--segment", "capesize", "--dry"])
    assert rc == 0


# ------------------------------------------------------------------ ledger cost
def test_log_prices_paid_writer_from_usage(monkeypatch, tmp_path):
    """Defect 14: the writer runs on the PAID amd_tokenlab route, so _log must book real cost."""
    import sqlite3

    import runner as R

    ledger = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(R, "LEDGER", ledger)
    monkeypatch.setattr(R, "_SCHEMA_INIT", False)

    usage = {"prompt_tokens": 5310, "completion_tokens": 1169, "cached_tokens": 3840,
             "cost": 0.001087744}
    booked = P._log("p6:cost-probe", "p6_summary", P.WRITER_MODEL, usage)

    assert booked == pytest.approx(0.001087744), "provider-reported measured cost must win"
    con = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT cost_usd, in_tok, cached_tok, out_tok FROM jobs "
                          "WHERE job_key='p6:cost-probe'").fetchone()
    finally:
        con.close()
    assert row is not None
    assert row[0] == pytest.approx(0.001087744)
    assert (row[1], row[2], row[3]) == (5310, 3840, 1169)


def test_log_prices_writer_from_config_tariff_without_measured_cost(monkeypatch, tmp_path):
    """No provider-reported cost: fall back to the config tariff, cache-aware, never silently 0."""
    import sqlite3

    import runner as R

    ledger = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(R, "LEDGER", ledger)
    monkeypatch.setattr(R, "_SCHEMA_INIT", False)

    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000, "cached_tokens": 0}
    booked = P._log("p6:tariff-probe", "p6_summary", P.WRITER_MODEL, usage)

    spec = R.price_table()[P.WRITER_MODEL]
    expected = (1_000_000 * spec["in"] + 1_000_000 * spec["out"]) / 1e6
    assert booked == pytest.approx(expected)
    assert booked > 0.0, "a paid writer must never book 0.0 when usage and a tariff exist"
    con = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    try:
        got = con.execute("SELECT cost_usd FROM jobs WHERE job_key='p6:tariff-probe'").fetchone()[0]
    finally:
        con.close()
    assert got == pytest.approx(expected)


def test_log_keeps_explicit_zero_for_free_judge(monkeypatch, tmp_path):
    """Explicit 0.0 is still honoured (any genuinely free route), not silently re-priced."""
    import sqlite3

    import runner as R

    ledger = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(R, "LEDGER", ledger)
    monkeypatch.setattr(R, "_SCHEMA_INIT", False)

    booked = P._log("p6judge:free-probe", "p6_judge", "openai/gpt-oss-120b",
                    {"prompt_tokens": 900, "completion_tokens": 40}, 0.0)
    assert booked == 0.0
    con = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    try:
        got = con.execute("SELECT cost_usd FROM jobs WHERE job_key='p6judge:free-probe'").fetchone()[0]
    finally:
        con.close()
    assert got == 0.0


def test_log_leaves_an_unpriceable_call_unmeasured_not_zero(monkeypatch, tmp_path):
    """Defect 17/21 class: no usage block / a null tariff must book NULL, never a measured 0.0."""
    import sqlite3

    import runner as R

    ledger = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(R, "LEDGER", ledger)
    monkeypatch.setattr(R, "_SCHEMA_INIT", False)

    # no usage at all: nothing to price, so nothing may be invented
    assert P._log("p6:unmeasured-probe", "p6_summary", P.WRITER_MODEL, {}) is None
    # tariff still `null` in kb/config.yaml (measured in P-1) => unknown price, not free
    assert P._log("p6:null-price-probe", "p6_summary", "deepseek-v4-flash",
                  {"prompt_tokens": 500, "completion_tokens": 50}) is None
    con = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT job_key, cost_usd FROM jobs ORDER BY job_key").fetchall()
    finally:
        con.close()
    assert [r[0] for r in rows] == ["p6:null-price-probe", "p6:unmeasured-probe"]
    assert all(r[1] is None for r in rows), f"unmeasured rows must stay NULL, got {rows}"
    # phase_spend_usd() must report UNMEASURED rather than an omission of those two rows
    monkeypatch.setattr(R, "spent_exact", lambda passes=None, prefix=None: None)
    assert P.phase_spend_usd() is None


# ------------------------------------------------------------------ judge score trust
def test_clamp_score_rejects_unusable_judge_scores():
    """Defect 17: a judge score outside [0, 1] (or non-numeric) must never be graded."""
    assert P.clamp_score(0.75) == 0.75
    assert P.clamp_score(1) == 1.0
    assert P.clamp_score(3) == 1.0, "out-of-range score is clamped, not passed through"
    assert P.clamp_score(-0.4) == 0.0
    assert P.clamp_score(None) is None
    assert P.clamp_score("0.9") is None, "a stringified number is not a usable score"
    assert P.clamp_score(True) is None, "bool is an int subclass but not a judge score"
    assert P.clamp_score(float("nan")) is None


def _judge_stub(monkeypatch, replies):
    """Feed judge_node a scripted reply per attempt and capture the pass it books."""
    seen = []

    def fake_chat(model, msgs, **_kw):
        seen.append(model)
        text = replies[min(len(seen) - 1, len(replies) - 1)]
        return {"choices": [{"message": {"content": text}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    monkeypatch.setattr(P, "chat", fake_chat)
    monkeypatch.setattr(P, "_log", lambda *a, **k: 0.0)
    return seen


def test_judge_node_rejects_inflated_score(monkeypatch):
    """A `"score": 3` reply used to inflate faithful_rate past the 0.95 gate; now clamped to 1.0."""
    _judge_stub(monkeypatch, ['{"verdict": "supported", "score": 3, "why": "x"}'])
    out = P.judge_node("spot was 5 [obs:1]", [])
    assert out["score"] == 1.0
    assert out["error"] is None


def test_judge_node_does_not_silently_grade_a_missing_score(monkeypatch):
    """Defect 21: a JSON reply without a usable score must be retried, then left UNGRADED (None).

    This test used to assert `out["score"] == 0.0`, which cemented the bug: `run_judge` classifies
    ungraded rows by `score is None`, so a 0.0 was booked as a *graded* zero and the outage never
    reached `ungraded`.
    """
    _judge_stub(monkeypatch, ['{"verdict": "supported", "why": "no score here"}'])
    out = P.judge_node("spot was 5 [obs:1]", [], retries=2)
    assert out["score"] is None, "an exhausted judge must not be graded 0.0"
    assert out["verdict"] is None
    assert out["error"] is not None and out["error"].startswith("bad_score"), out


def test_judge_node_returns_none_after_a_dead_judge(monkeypatch):
    """Defect 21: a raising judge must return score=None so `run_judge` counts the row ungraded."""
    def dead_chat(model, msgs, **_kw):
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr(P, "chat", dead_chat)
    monkeypatch.setattr(P.time, "sleep", lambda _s: None)
    out = P.judge_node("spot was 5 [obs:1]", [], retries=2)
    assert out["score"] is None, out
    assert "429" in (out["error"] or ""), out


def test_a_dead_judge_is_reported_as_ungraded_not_as_unfaithful(monkeypatch, tmp_path):
    """Defect 21 end to end: the producer, the classifier and the gate must agree on ONE sentinel.

    The old contract had a producer emitting 0.0 and a classifier testing for None, so a judge that
    never answered produced `graded=sampled, ungraded=0, ungraded_errors=[]` -- a fabricated benign
    zero -- and the gate failed only via `faithful_rate 0.0`, i.e. it blamed the writer.
    """
    nodes = tmp_path / "nodes.jsonl"
    rows = [{"node_id": f"n:{i}", "segment": "capesize", "grain": "month", "period": "2026-03",
             "evidence": [], "sentences": [{"sentence": f"spot was {i}", "cites": ["obs:1"]}]}
            for i in range(4)]
    nodes.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    index = {r["node_id"]: {k: v for k, v in r.items() if k != "evidence"} for r in rows}

    def dead_chat(model, msgs, **_kw):
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr(P, "chat", dead_chat)
    monkeypatch.setattr(P.time, "sleep", lambda _s: None)
    out = P.run_judge(index, n=4, seed=1,
                      judge=lambda text, ev, **_kw: P.judge_node(text, ev, retries=2), path=nodes)

    assert out["sampled"] == 4, out
    assert out["graded"] == 0, "nothing was graded, so nothing may be counted as a grade"
    assert out["ungraded"] == out["sampled"] == 4
    assert out["ungraded_rate"] == 1.0
    assert out["mean_score"] is None and out["faithful_rate"] is None, \
        "no graded row means no mean; 0.0 would read as unfaithfulness"
    assert out["ungraded_errors"] and all("429" in e for e in out["ungraded_errors"]), out

    build = {"counts": {"leaves": 4, "parents_q": 0, "parents_y": 0, "cached": 0, "empty": 0,
                        "sentences": 4, "dropped": 0}, "wall_seconds": 1.0}
    rep = P.build_report(index, build, out)
    assert rep["gate_passed"] is False, "a dead judge must fail the P6 gate"
    assert rep["judge"]["ungraded"] == 4 and rep["judge"]["faithful_rate"] is None


def test_run_judge_reports_none_when_it_grades_nothing(tmp_path):
    """Defect 21 corollary: `if scores else 0.0` faked a `faithful_rate 0.0` out of an empty run."""
    nodes = tmp_path / "nodes.jsonl"
    rec = {"node_id": "n:0", "segment": "capesize", "grain": "month", "period": "2026-03",
           "evidence": [], "sentences": [{"sentence": "spot was 5", "cites": ["obs:1"]}]}
    nodes.write_text(json.dumps(rec) + "\n")
    index = {"n:0": {k: v for k, v in rec.items() if k != "evidence"}}
    out = P.run_judge(index, n=1, seed=1,
                      judge=lambda text, ev, **_kw: {"score": None, "verdict": None,
                                                     "why": None, "error": "bad_score:None"},
                      path=nodes)
    assert out["graded"] == 0 and out["ungraded"] == 1
    assert out["mean_score"] is None and out["faithful_rate"] is None
    assert out["ungraded_rate"] == 1.0


def test_judge_node_falls_back_to_the_fallback_model_on_bad_score(monkeypatch):
    seen = _judge_stub(monkeypatch, ['{"score": "high", "verdict": "supported"}',
                                     '{"score": 0.9, "verdict": "supported"}'])
    out = P.judge_node("spot was 5 [obs:1]", [], retries=2)
    assert out["score"] == 0.9
    assert seen[0] == P.JUDGE_MODEL and seen[1] == P.JUDGE_FALLBACK_MODEL


def test_run_judge_counts_ungraded_rows(monkeypatch, tmp_path):
    """Defect 17: an unanswered row used to vanish, so a half-dead judge scored 1.0."""
    nodes = tmp_path / "nodes.jsonl"
    rows = []
    for i in range(4):
        rows.append({"node_id": f"n:{i}", "segment": "capesize", "grain": "month",
                     "period": "2026-03", "evidence": [],
                     "sentences": [{"sentence": f"spot was {i}", "cites": ["obs:1"]}]})
    nodes.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    def fake_judge(text, ev, **_kw):
        good = "spot was 0" in text
        return {"score": 1.0 if good else None, "verdict": "supported" if good else None,
                "why": "x", "error": None if good else "bad_score:None"}

    index = {r["node_id"]: {k: v for k, v in r.items() if k != "evidence"} for r in rows}
    out = P.run_judge(index, n=4, seed=1, judge=fake_judge, path=nodes)
    assert out["sampled"] == 4 and out["graded"] == 1 and out["ungraded"] == 3
    assert out["ungraded_rate"] == 0.75
    assert out["faithful_rate"] == 1.0, "rate is over the graded rows only; ungraded is reported apart"
    assert any("bad_score" in e for e in out["ungraded_errors"])

    build = {"counts": {"leaves": 4, "parents_q": 0, "parents_y": 0, "cached": 0, "empty": 0,
                        "sentences": 4, "dropped": 0}, "wall_seconds": 1.0}
    rep = P.build_report(index, build, out)
    assert rep["gate_passed"] is False, "ungraded rows must block the P6 gate"


def test_build_report_reports_measured_spend_not_a_literal_zero(monkeypatch, tmp_path):
    """Defect 17: `spend_usd` was hardcoded 0.0 while both P6 routes are PAID (Defect 14 class)."""
    import runner as R

    ledger = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(R, "LEDGER", ledger)
    monkeypatch.setattr(R, "_SCHEMA_INIT", False)
    P._log("p6:spend-probe", "p6_judge", P.JUDGE_MODEL,
           {"prompt_tokens": 1_000_000, "completion_tokens": 0})

    index = {"n:a": {"grain": "month", "segment": "capesize", "period": "2026-03", "input_hash": "x",
                     "summary": "s", "sentences": [{"sentence": "s", "cites": ["obs:1"]}]}}
    build = {"counts": {"leaves": 1, "parents_q": 0, "parents_y": 0, "cached": 0, "empty": 0,
                        "sentences": 1, "dropped": 0}, "wall_seconds": 1.0}
    rep = P.build_report(index, build, {"sampled": 1, "graded": 1, "ungraded": 0,
                                        "faithful_rate": 0.99})
    spec = R.price_table()[P.JUDGE_MODEL]
    assert rep["spend_usd"] == pytest.approx(1_000_000 * spec["in"] / 1e6)
    assert rep["spend_usd"] > 0.0, "a PAID phase must not report a hardcoded 0.0 spend"
    assert "$" in P._md(rep)


def test_build_report_spend_is_none_not_zero_when_ledger_unreadable(monkeypatch):
    monkeypatch.setattr(P, "phase_spend_usd", lambda: None)
    index = {"n:a": {"grain": "month", "segment": "capesize", "period": "2026-03", "input_hash": "x",
                     "summary": "s", "sentences": [{"sentence": "s", "cites": ["obs:1"]}]}}
    build = {"counts": {"leaves": 1, "parents_q": 0, "parents_y": 0, "cached": 0, "empty": 0,
                        "sentences": 1, "dropped": 0}, "wall_seconds": 1.0}
    rep = P.build_report(index, build, None)
    assert rep["spend_usd"] is None
    md = P._md(rep)
    assert "UNMEASURED" in md and "0.0000" not in md


def test_build_report_marks_for_a_real_tiny_spend_are_visible(monkeypatch):
    """Defect-17 class, third instance: P6's whole phase spend renders as `$0.00001`, not `$0.0000`.

    P6's real tracked spend is on the order of $0.000013. A fixed `:.4f` printed that as the exact
    string reserved for a measured zero, so the owner read "free" for a paid phase. The renderer must
    widen the decimals rather than flatten a real amount into the zero claim.
    """
    monkeypatch.setattr(P, "phase_spend_usd", lambda: 1.3e-05)
    index = {"n:a": {"grain": "month", "segment": "capesize", "period": "2026-03", "input_hash": "x",
                     "summary": "s", "sentences": [{"sentence": "s", "cites": ["obs:1"]}]}}
    build = {"counts": {"leaves": 1, "parents_q": 0, "parents_y": 0, "cached": 0, "empty": 0,
                        "sentences": 1, "dropped": 0}, "wall_seconds": 1.0}
    rep = P.build_report(index, build, {"sampled": 1, "graded": 1, "ungraded": 0,
                                        "faithful_rate": 0.99})
    line = [ln for ln in P._md(rep).splitlines() if ln.startswith("- spend")][0]
    assert "$0.00001" in line, line
    assert "$0.0000," not in line, "a real spend must not read as measured zero"
    # A genuine measured zero keeps its own, different rendering.
    monkeypatch.setattr(P, "phase_spend_usd", lambda: 0.0)
    rep0 = P.build_report(index, build, {"sampled": 1, "graded": 1, "ungraded": 0,
                                         "faithful_rate": 0.99})
    line0 = [ln for ln in P._md(rep0).splitlines() if ln.startswith("- spend")][0]
    assert "$0.0000," in line0 and line0 != line


# ------------------------------------------------------------------ ledger keying (Defect 18)
def _scratch_ledger(monkeypatch, tmp_path):
    """Point the real `runner` ledger at a scratch file so `P._log` writes for real."""
    import runner as R

    ledger = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(R, "LEDGER", ledger)
    monkeypatch.setattr(R, "_SCHEMA_INIT", False)
    return ledger


def _judge_rows(ledger, pass_name="p6_judge"):
    import sqlite3

    con = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    try:
        return con.execute("SELECT job_key, model, cost_usd FROM jobs WHERE pass=?",
                           [pass_name]).fetchall()
    finally:
        con.close()


def test_judge_retry_attempts_each_book_a_separate_row(monkeypatch, tmp_path):
    """Defect 18: key was sha256(summary) alone, so the retry's upsert erased the first paid call."""
    import runner as R

    ledger = _scratch_ledger(monkeypatch, tmp_path)
    seen = []

    def fake_chat(model, msgs, **_kw):
        seen.append(model)
        txt = ('{"verdict": "supported", "why": "no score here"}' if len(seen) == 1
               else '{"score": 0.9, "verdict": "supported", "why": "ok"}')
        return {"choices": [{"message": {"content": txt}}],
                "usage": {"prompt_tokens": 216, "completion_tokens": 39}}

    monkeypatch.setattr(P, "chat", fake_chat)
    out = P.judge_node("spot was 5 [obs:1]",
                       [{"kind": "chunk", "ref": "t#1", "text": "spot was 5"}], retries=2)
    assert out["score"] == 0.9 and out["error"] is None
    assert seen == [P.JUDGE_MODEL, P.JUDGE_FALLBACK_MODEL], "second attempt is the fallback judge"

    rows = _judge_rows(ledger)
    assert len(rows) == 2, rows
    assert len({r[0] for r in rows}) == 2, "one key per paid attempt"
    assert {r[1] for r in rows} == {P.JUDGE_MODEL, P.JUDGE_FALLBACK_MODEL}
    assert all(r[2] > 0.0 for r in rows), "both attempts are paid and must stay visible"
    assert R.spent(passes=["p6_judge"]) == pytest.approx(sum(r[2] for r in rows))


def test_distinct_summaries_sharing_a_summary_text_key_stay_separate(monkeypatch, tmp_path):
    """The old key hashed only the summary, so the same sentence on other evidence collided."""
    ledger = _scratch_ledger(monkeypatch, tmp_path)

    def fake_chat(model, msgs, **_kw):
        return {"choices": [{"message": {"content": '{"score": 1.0, "verdict": "supported"}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10}}

    monkeypatch.setattr(P, "chat", fake_chat)
    same = "spot was 5 in March."
    P.judge_node(same, [{"kind": "chunk", "ref": "a#1", "text": "spot was 5"}])
    P.judge_node(same, [{"kind": "chunk", "ref": "b#9", "text": "spot was 5"}])

    rows = _judge_rows(ledger)
    assert len(rows) == 2, rows
    assert len({r[0] for r in rows}) == 2, "evidence must be part of the key"


def test_write_node_retries_book_one_row_per_paid_attempt(monkeypatch, tmp_path):
    """A blank writer reply is retried; both paid calls must survive in the ledger."""
    import runner as R

    ledger = _scratch_ledger(monkeypatch, tmp_path)
    n = {"i": 0}

    def fake_chat(model, msgs, **_kw):
        n["i"] += 1
        return {"choices": [{"message": {"content": "" if n["i"] == 1 else "spot was 5."}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20}}

    monkeypatch.setattr(P, "chat", fake_chat)
    res = P.write_node([{"role": "user", "content": "hi"}], job_key="p6:test-node", retries=2)
    assert res["status"] == "ok" and n["i"] == 2

    rows = _judge_rows(ledger, "p6_summary")
    assert len(rows) == 2, rows
    assert len({r[0] for r in rows}) == 2, "the retry must not upsert over the first attempt"
    assert all(r[2] > 0.0 for r in rows)
    assert R.spent(passes=["p6_summary"]) == pytest.approx(sum(r[2] for r in rows))


def test_write_node_keeps_one_row_when_the_first_attempt_succeeds(monkeypatch, tmp_path):
    """No retry: keying must stay stable so a cached/re-run node reuses its row."""
    ledger = _scratch_ledger(monkeypatch, tmp_path)

    def fake_chat(model, msgs, **_kw):
        return {"choices": [{"message": {"content": "spot was 5."}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20}}

    monkeypatch.setattr(P, "chat", fake_chat)
    P.write_node([{"role": "user", "content": "hi"}], job_key="p6:stable", retries=2)
    P.write_node([{"role": "user", "content": "hi"}], job_key="p6:stable", retries=2)

    rows = _judge_rows(ledger, "p6_summary")
    assert len(rows) == 1, rows
    assert rows[0][0] == "p6:stable"
