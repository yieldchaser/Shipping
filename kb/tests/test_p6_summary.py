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
    assert "gpt-oss-120b" in md


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
