"""Tests for the layer-C contract: kb/extract_schema.py, kb/extract_gates.py, kb/runner.py.

Plan §7.4 rules are code, so they get unit tests: a gate that silently passes everything would
make the P4b bake-off meaningless.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import extract_gates as G  # noqa: E402
import extract_schema as S  # noqa: E402
import runner as R  # noqa: E402


def _ext(**kw):
    base = {"no_content": False, "state_facts": [], "events": [], "claims": [], "new_entities": []}
    base.update(kw)
    return json.dumps(base)


def _chunk(known=("E1",), sentences=None, published=None):
    return {"chunk_id": "C1", "known_ids": set(known), "new_names": {},
            "sentences": sentences or [(0, "lead"), (1, "MV Aurora was sold to Nereus Shipping for USD 18.5 M.")],
            "published_at": published}


def test_taxonomy_and_prompt_are_complete():
    routes = S.baltic_routes()
    assert len(routes) == 109
    assert S.PROMPT_VERSION
    # every enum member appears in the static prompt so the model never has to guess
    for t in S.EDGE_TYPES:
        assert t in S.STATIC_PROMPT
    for t in S.EVENT_TYPES:
        assert t in S.STATIC_PROMPT
    for code, _ in routes:
        assert f"\n{code} " in S.STATIC_PROMPT or f"{code} " in S.STATIC_PROMPT


def test_tool_schema_closes_every_object():
    sch = S.tool_schema(["C1", "C2"])
    assert sch["additionalProperties"] is False
    assert sch["properties"]["state_facts"]["items"]["additionalProperties"] is False
    assert sch["properties"]["state_facts"]["items"]["properties"]["chunk"]["enum"] == ["C1", "C2"]
    assert "TIME_CHARTERED_TO" in sch["properties"]["state_facts"]["items"]["properties"]["type"]["enum"]


def test_parse_accepts_valid_and_rejects_bad_enum():
    good = _ext(state_facts=[{"type": "SOLD_TO", "src": "E1", "dst": "N1", "attrs_printed": [],
                              "valid_from_printed": "", "valid_to_printed": "", "chunk": "C1",
                              "sids": [1], "confidence": 0.9}])
    ext, err = S.parse_extraction(good)
    assert err is None and len(ext.state_facts) == 1
    bad = json.loads(good)
    bad["state_facts"][0]["type"] = "SOLD"
    ext, err = S.parse_extraction(json.dumps(bad))
    assert ext is None and err.startswith("schema:")
    assert S.parse_extraction("{not json")[1].startswith("json:")


def test_gate_rule2_caps_quote_at_three_sentences():
    sentences = [(i, f"sentence {i}") for i in range(6)]
    quote, keep = G.quote_for([5, 1, 2, 3, 4, 0], sentences)
    assert keep == [0, 1, 2]
    quote, keep = G.quote_for([1, 99], sentences)
    assert keep == [1] and "sentence 99" not in quote


def test_gate_rule3_drops_number_missing_from_quote():
    ext, _ = S.parse_extraction(_ext(state_facts=[{
        "type": "SOLD_TO", "src": "E1", "dst": "E1", "attrs_printed": [
            {"key": "price", "value_as_printed": "USD 19.5 M"}],
        "valid_from_printed": "", "valid_to_printed": "", "chunk": "C1", "sids": [1], "confidence": 0.9}]))
    res = G.gate_chunk(ext, _chunk())
    assert res["records_ok"] == 0
    assert any(r.startswith("number_not_in_quote") for r in res["records"][0]["reasons"])
    # the literal number is present but only inside a longer number -> still a failure
    assert not G.numbers_ok(["2"], "built in 2025")[0]
    assert G.numbers_ok(["18.5"], "USD 18.5 M")[0]


def test_gate_rule4_requires_resolvable_entities_and_new_entity_evidence():
    ext, _ = S.parse_extraction(_ext(
        state_facts=[{"type": "SOLD_TO", "src": "E1", "dst": "N1", "attrs_printed": [],
                      "valid_from_printed": "", "valid_to_printed": "", "chunk": "C1",
                      "sids": [1], "confidence": 0.9}],
        new_entities=[{"id": "N1", "type": "company", "name": "Nereus Shipping", "chunk": "C1", "sids": [1]}]))
    assert G.gate_chunk(ext, _chunk())["records_ok"] == 1
    # a new entity whose name is nowhere in its own sentences does not resolve
    ext2, _ = S.parse_extraction(_ext(
        state_facts=[{"type": "SOLD_TO", "src": "E1", "dst": "N9", "attrs_printed": [],
                      "valid_from_printed": "", "valid_to_printed": "", "chunk": "C1",
                      "sids": [1], "confidence": 0.9}],
        new_entities=[{"id": "N9", "type": "company", "name": "Ghost Shipping", "chunk": "C1", "sids": [1]}]))
    res = G.gate_chunk(ext2, _chunk())
    assert res["records_ok"] == 0
    assert any(r.startswith("entity_unresolved") for r in res["records"][0]["reasons"])
    # unknown src is unresolved too
    ext3, _ = S.parse_extraction(_ext(state_facts=[{
        "type": "OWNS", "src": "E7", "dst": "E1", "attrs_printed": [], "valid_from_printed": "",
        "valid_to_printed": "", "chunk": "C1", "sids": [1], "confidence": 0.9}]))
    assert G.gate_chunk(ext3, _chunk())["records_ok"] == 0


def test_gate_rule4_records_off_whitelist_attr_keys_as_notes_only():
    # plan §7.4 gates 1-7 never whitelist attribute keys: an unexpected key is a metric/warning,
    # not a drop reason, so recall is not punished for vocabulary the edge type did not enumerate.
    ext, _ = S.parse_extraction(_ext(state_facts=[{
        "type": "OWNS", "src": "E1", "dst": "E1", "attrs_printed": [
            {"key": "price", "value_as_printed": "USD 18.5 M"}],
        "valid_from_printed": "", "valid_to_printed": "", "chunk": "C1", "sids": [1], "confidence": 0.9}]))
    res = G.gate_chunk(ext, _chunk())
    assert res["records_ok"] == 1
    assert not res["records"][0]["dropped"]
    assert res["records"][0].get("attr_notes") == ["price"]


def test_gate_rule5_dates_resolved_by_code_only():
    pub = dt.date(2025, 3, 5)  # a Wednesday
    assert G.resolve_printed("this week", pub)["start"] == "2025-03-03"
    assert G.resolve_printed("last week", pub)["start"] == "2025-02-24"
    assert G.resolve_printed("Q3 2025", None)["end"] == "2025-09-30"
    assert G.resolve_printed("July 2024", None)["start"] == "2024-07-01"
    assert G.resolve_printed("2025-03-01", None)["grain"] == "day"
    assert G.resolve_printed("yesterday", pub)["start"] == "2025-03-04"
    assert G.resolve_printed("5 days ago", pub)["start"] == "2025-02-28"
    assert G.resolve_printed("three days", pub) is None


def test_gate_attaches_resolved_dates_and_counts_chunk_mismatch():
    ext, _ = S.parse_extraction(_ext(state_facts=[{
        "type": "TIME_CHARTERED_TO", "src": "E1", "dst": "E1", "attrs_printed": [
            {"key": "delivery", "value_as_printed": "this week"}],
        "valid_from_printed": "this week", "valid_to_printed": "", "chunk": "C1", "sids": [1],
        "confidence": 0.8}]))
    sentences = [(0, "lead"), (1, "MV Aurora was taken on charter this week at USD 18.5 M.")]
    res = G.gate_chunk(ext, _chunk(sentences=sentences, published=dt.date(2025, 3, 5)))
    assert res["records_ok"] == 1
    assert res["records"][0]["valid_from"]["start"] == "2025-03-03"
    ext2, _ = S.parse_extraction(_ext(state_facts=[{
        "type": "OWNS", "src": "E1", "dst": "E1", "attrs_printed": [], "valid_from_printed": "",
        "valid_to_printed": "", "chunk": "C9", "sids": [1], "confidence": 0.9}]))
    res2 = G.gate_chunk(ext2, _chunk())
    assert res2["records_ok"] == 0 and "chunk_mismatch" in res2["records"][0]["reasons"]


def test_user_prompt_numbers_sentences_and_known_entities():
    doc = {"publisher": "p", "doc_type": "broker_weekly", "published_at": "2025-03-05", "heading": "Dry"}
    blocks = [{"cid": "C1", "sentences": [(0, "lead sentence"), (1, "Aurora sold.")]}]
    known = [{"id": "E1", "type": "vessel", "name": "MV Aurora", "key": "9700001"}]
    p = S.user_prompt(doc, blocks, known)
    assert '[0] lead sentence' in p and 'id="C1"' in p
    assert "E1|vessel|MV Aurora|9700001" in p
    assert "none" in S.user_prompt(doc, blocks, [])


def test_runner_job_key_is_deterministic_and_packing_sensitive():
    a = R.job_key("C1", "v1", "p4b")
    assert a == R.job_key("C1", "v1", "p4b")
    assert a != R.job_key("C1", "v2", "p4b")
    assert len(a) == 32


def test_runner_cost_prefers_measured_cost_then_price_table():
    assert R.cost_usd("deepseek-v4-pro", {"prompt_tokens": 1_000_000, "completion_tokens": 0}) == 1.32
    assert R.cost_usd("deepseek-v4-pro", {"prompt_tokens": 10, "completion_tokens": 10, "cost": 0.5}) == 0.5
    assert R.cost_usd("nvidia/nemotron-3-ultra-550b-a55b", {"prompt_tokens": 10, "completion_tokens": 10}) == 0.0
    assert R.cost_usd("deepseek-v4-flash", {"prompt_tokens": 10, "completion_tokens": 10}) == 0.0


def test_ledger_roundtrip_and_spend_sum(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "LEDGER", tmp_path / "ledger.sqlite")
    con = R.connect()
    job = {"job_key": "k1", "model": "deepseek-v4-pro", "meta": {"chunk": "c1"}}
    R._ledger_lock = R.threading.Lock()
    r = R.Runner("p4b_test", "extraction-v1", cap_usd=1.0)
    r.con = con
    r._record(job, status="ok", in_tok=10, out_tok=5, cost=0.25, model_returned="cyberouter/deepseek-v4-pro")
    row = con.execute("SELECT status, cost_usd, model_returned FROM jobs WHERE job_key='k1'").fetchone()
    assert row == ("ok", 0.25, "cyberouter/deepseek-v4-pro")
    assert R.spent(passes=["p4b_test"], prefix=None) >= 0.0


def test_no_content_extraction_passes_gate():
    ext, err = S.parse_extraction(_ext(no_content=True))
    assert err is None
    res = G.gate_chunk(ext, _chunk())
    assert res["records_total"] == 0 and res["records_ok"] == 0 and res["no_content"] is True


# --- P4b: gold-sample allocation/selection ---------------------------------------------------
import p4b_gold as GS  # noqa: E402


def _rows(publishers=("P1", "P2"), doc_types=("broker_weekly", "sec_6k"), years=(2023, 2024), per=3):
    rows = []
    n = 0
    for p in publishers:
        for d in doc_types:
            for y in years:
                for i in range(per):
                    n += 1
                    rows.append({"chunk_id": f"c{n:04d}", "doc_id": f"d{n:04d}", "tokens": 300,
                                 "n_ent": 2, "doc_type": d, "publisher": p,
                                 "published_at": dt.date(y, 6, 1), "title": "t", "year": y,
                                 "section_class": "prose", "sec_item": ""})
    return rows


def test_allocate_is_exact_and_proportional_no_floor():
    quota = GS.allocate({"big": 900, "mid": 90, "tiny": 10}, 100)
    assert sum(quota.values()) == 100
    assert quota["big"] == 90 and quota["mid"] == 9 and quota["tiny"] == 1
    # a stratum far below one slot may legitimately get zero (no floor)
    tiny = GS.allocate({"a": 10_000, "b": 1}, 100)
    assert sum(tiny.values()) == 100 and tiny["b"] == 0
    assert GS.allocate({"a": 0, "b": 0}, 10) == {"a": 0, "b": 0}


def test_select_is_deterministic_exact_and_covers_dimensions():
    rows = _rows(publishers=("P1", "P2", "P3"), doc_types=("broker_weekly", "sec_6k", "book"),
                 years=(2019, 2024), per=4)
    a = GS.select(rows, target=20, seed=7)
    b = GS.select(rows, target=20, seed=7)
    assert [p["chunk_id"] for p in a["picks"]] == [p["chunk_id"] for p in b["picks"]]
    assert len({p["chunk_id"] for p in a["picks"]}) == 20
    # every dimension value present in scope survives the trim to `target`
    assert a["coverage"]["publishers"] == ["P1", "P2", "P3"]
    assert a["coverage"]["doc_types"] == ["book", "broker_weekly", "sec_6k"]
    assert a["coverage"]["years"] == ["2019", "2024"]
    assert a["stats"]["strata_used"] <= a["stats"]["strata_total"]


def test_select_keeps_rare_publisher_representative():
    rows = _rows(publishers=("P1", "P2", "P3", "RARE"), per=6)
    rows = [dict(r, chunk_id=r["chunk_id"] + r["publisher"]) for r in rows]
    sel = GS.select(rows, target=16, seed=11)
    assert "RARE" in {p["publisher"] for p in sel["picks"]}
    assert len(sel["picks"]) == 16


# --- P4b: record matching used for the reference set and scoring -----------------------------
import p4b_run as B  # noqa: E402


def _ref_fact(**kw):
    base = {"type": "SOLD_TO", "src": "E1", "dst": "E2", "attrs_printed": [],
            "valid_from_printed": "", "valid_to_printed": "", "chunk": "C1", "sids": [1],
            "confidence": 0.9}
    base.update(kw)
    return S.StateFact(**base)


def test_record_sig_uses_kind_type_and_entities():
    f = _ref_fact()
    assert B.record_sig("state_facts", f) == ("state_facts", "SOLD_TO", frozenset({"E1", "E2"}))
    ev = S.Event(type="market_move", summary="sale of MV Aurora", roles=[
        S.EventRole(entity="E1", role="seller"), S.EventRole(entity="E2", role="buyer")],
        when_printed="June 2024", magnitude_printed="", chunk="C1", sids=[1], confidence=0.8)
    assert B.record_sig("events", ev) == ("events", "market_move", frozenset({"E1", "E2"}))
    cl = S.Claim(kind="forecast", subjects=["E1"], direction="up", horizon_printed="2025",
                 chunk="C1", sids=[1], confidence=0.7)
    assert B.record_sig("claims", cl) == ("claims", "forecast", frozenset({"E1"}))


def test_records_match_requires_type_entity_and_quote_overlap():
    sents = [(0, "intro"), (1, "MV Aurora was sold to Nereus Shipping for USD 18.5 M."),
             (2, "The aurora sale to nereus shipping was completed in June.")]
    a = ("state_facts", "SOLD_TO", frozenset({"E1", "E2"}))
    b = ("state_facts", "SOLD_TO", frozenset({"E1", "E2"}))
    c = ("state_facts", "SOLD", frozenset({"E1", "E2"}))
    d = ("state_facts", "SOLD_TO", frozenset({"E3", "E4"}))
    qa, _ = G.quote_for([1], sents)
    qb, _ = G.quote_for([2], sents)
    assert B.records_match(a, b, qa, qb)
    assert not B.records_match(a, c, qa, qb)
    assert not B.records_match(a, d, qa, qb)


def test_match_lists_greedy_counts():
    sents = [(1, "MV Aurora was sold to Nereus Shipping for USD 18.5 M.")]
    q, _ = G.quote_for([1], sents)
    f1 = ("state_facts", "SOLD_TO", frozenset({"E1", "E2"}))
    f2 = ("state_facts", "SOLD_TO", frozenset({"E1", "E2"}))
    g1 = ("state_facts", "BUILT_BY", frozenset({"E1", "E2"}))
    matched, unmatched = B.match_lists([(f1, q, "state_facts", None), (g1, q, "state_facts", None)],
                                       [(f2, q, "state_facts", None)])
    assert matched == 1 and unmatched == [1]


def test_make_job_is_byte_identical_per_pack_and_mode():
    items = json.loads((GS.OUT / "p4b_items.json").read_text(encoding="utf-8")) \
        if (GS.OUT / "p4b_items.json").exists() else []
    if not items:
        return  # gold sample not built in this checkout
    pack = B.build_packs(items)[0]
    assert len(pack["chunk_ids"]) >= 1 and pack["blocks"]
    j1 = B.make_job("p4b_cand", "deepseek-v4.1-flash", "tools", pack)
    j2 = B.make_job("p4b_cand", "deepseek-v4.1-flash", "tools", pack)
    assert j1["job_key"] == j2["job_key"] and j1["messages"] == j2["messages"]
    j3 = B.make_job("p4b_cand", "deepseek-v4.1-flash", "json_object", pack)
    assert j3["job_key"] != j1["job_key"]
    assert j1["max_tokens"] == 2500 and j1["temperature"] == 0.0
    assert j1["messages"][0]["content"] == S.STATIC_PROMPT
    # one call carries every block of the pack, each with its own prompt id
    user = j1["messages"][1]["content"]
    for block in pack["blocks"]:
        assert f'<chunk id="{block["cid"]}">' in user
    assert "<known_entities>" in user


def test_split_gate_maps_packed_records_back_to_real_chunks():
    items = json.loads((GS.OUT / "p4b_items.json").read_text(encoding="utf-8")) \
        if (GS.OUT / "p4b_items.json").exists() else []
    if not items:
        return
    packs = B.build_packs(items)
    pack = next((p for p in packs if len(p["chunk_ids"]) >= 2), None)
    if pack is None:
        return
    g = {"records": [{"kind": "events", "index": 0, "quote": "", "dropped": False,
                      "chunk": "c2", "sids": [1]},
                     {"kind": "state_facts", "index": 0, "quote": "", "dropped": True,
                      "chunk": "c1", "sids": [1]}],
         "kept": {"state_facts": [], "events": [], "claims": []}, "new_entities_ok": {},
         "no_content": False}
    per = B.split_gate(g, pack)
    assert set(per) == set(pack["chunk_ids"])
    assert per[pack["chunk_ids"][1]]["records_ok"] == 1
    assert per[pack["chunk_ids"][0]]["records_ok"] == 0

# --- P4b gate report: the numbers in kb/reports/p4b.json are what C1 and the daily summary read,
# --- so they are asserted here rather than only described in prose.
def _p4b_report():
    import json as _json
    p = KB / "reports" / "p4b.json"
    return _json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def test_p4b_report_gate_results_all_pass():
    d = _p4b_report()
    if d is None:
        return
    gr = d["gate_results"]
    assert gr["all_pass"] is True
    for k, v in gr.items():
        if isinstance(v, dict):
            assert v["pass"] is True, k
            if k != "chosen_bulk_f1_within_best":
                assert v["measured"] >= v["required"], k
            else:
                assert v["measured"] <= v["required"], k


def test_p4b_selected_model_meets_selection_rule():
    d = _p4b_report()
    if d is None:
        return
    sel = d["selected"]
    assert sel, "P4b must select a bulk extractor"
    assert sel["precision"] >= 0.92
    assert sel["call_success_rate"] >= 0.95
    assert sel["record_drop_rate"] <= 0.30          # plan §7.4 escalation bound
    cands = [r for r in d["models"].values() if r.get("role") == "candidate"]
    best = max(r["f1"] for r in cands)
    assert best - sel["f1"] <= 0.03 + 1e-9
    assert sel["projected_full_scope_usd"] <= d["spend"]["p4c_allowance_usd"] + 1e-9


def test_p4b_feasibility_arithmetic_is_consistent():
    d = _p4b_report()
    if d is None:
        return
    fe = d["p4c_feasibility"]
    sel = d["selected"]
    depth = d["gold"]["mean_pack_depth"]
    assert fe["calls_at_gold_pack_depth"] == round(86607 / depth)
    assert fe["out_tokens_full_scope"] == round(
        fe["calls_at_gold_pack_depth"] * sel["out_tok_per_call"])
    mix = fe.get("mixed_pool_one_day")
    if mix:
        assert abs(mix["paid_chunk_share"]
                   - mix["paid_calls"] / fe["calls_at_gold_pack_depth"]) < 1e-4
        cheap = fe["paid_overflow"][mix["paid_overflow_model"]]
        assert abs(mix["paid_cost_usd"]
                   - mix["paid_chunk_share"] * cheap["projected_full_scope_usd"]) <= 0.02


def test_p4b_precision_ci_brackets_point_estimate():
    d = _p4b_report()
    if d is None:
        return
    for m, r in d["models"].items():
        lo, hi = r["precision_ci95"]
        assert lo <= r["precision"] <= hi, m
        assert r["precision_judged_n"] > 0, m


def test_p4b_report_seed_matches_gates_seed():
    d = _p4b_report()
    if d is None:
        return
    import p4b_run as B
    assert d["phase"] == "P4B"
    assert d["sample_seed"] == B.seed_for("P4B")
