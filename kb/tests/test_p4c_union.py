"""Unit tests for `p4c_union` - merge/dedupe determinism and the audit-compatible row shape."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kb"))

import p4c_audit as A  # noqa: E402
import p4c_union as U  # noqa: E402


def pack(cid: str = "c1", chunk_id: str = "chunk_a") -> dict:
    return {"n": 0, "pack_id": "p000000", "doc_id": "doc_a", "ord_first": 0,
            "key": f"doc_a|{chunk_id}", "chunk_ids": [chunk_id], "tokens": 10,
            "doc": {"publisher": "broker_x", "doc_type": "broker_report",
                    "published_at": "2024-01-05", "heading": "h"},
            "year": 2024, "section_class": "mdna",
            "blocks": [{"cid": cid, "sentences": [[1, "The ship SHIP TWO was sold for $10m."],
                                                   [2, "Delivery is due in 2025."]]}],
            "known": [{"id": "E1", "type": "vessel", "name": "SHIP ONE", "key": "imo1"}]}


def rec_row(rkind: str, **body) -> dict:
    base = {"record_kind": rkind, "chunk": "c1", "sids": [1], "quote": "The ship SHIP TWO was sold for $10m.",
            "sources": ["p4c_bulk"], "confidence": 0.8}
    base.update(body)
    return base


def test_sig_of_mirrors_p4b_record_sig():
    r = rec_row("state_facts", type="OWNS", src="E1", dst="E2")
    assert U.sig_of(r) == ("state_facts", "OWNS", frozenset(["E1", "E2"]))
    ev = rec_row("events", type="sale", roles=[{"entity": "E1", "role": "seller"},
                                               {"entity": "E2", "role": "buyer"}])
    assert U.sig_of(ev) == ("events", "sale", frozenset(["E1", "E2"]))
    cl = rec_row("claims", kind="forecast", subjects=["E1"])
    assert U.sig_of(cl) == ("claims", "forecast", frozenset(["E1"]))


def test_merge_dedupes_same_fact_and_keeps_provenance():
    acc: list[dict] = []
    first = rec_row("state_facts", type="OWNS", src="E1", dst="E2", sources=["p4c_bulk"])
    assert U.merge_records(acc, [first], "p4c_bulk") == (1, 0)
    dup = rec_row("state_facts", type="OWNS", src="E1", dst="E2", sources=["p4c_glean"],
                  confidence=0.9)
    assert U.merge_records(acc, [dup], "p4c_glean") == (0, 1)
    assert len(acc) == 1
    assert acc[0]["sources"] == ["p4c_bulk", "p4c_glean"]
    assert acc[0]["confidence"] == 0.9  # highest-confidence copy wins
    other = rec_row("state_facts", type="OWNS", src="E1", dst="E3")
    assert U.merge_records(acc, [other], "p4c_glean") == (1, 0)
    assert len(acc) == 2


def _dup_pair(ca, cb) -> tuple[list[dict], int]:
    """Seed one record with confidence `ca`, then merge an identical fact carrying `cb`."""
    acc: list[dict] = []
    assert U.merge_records(acc, [rec_row("state_facts", type="OWNS", src="E1", dst="E2",
                                         confidence=ca)], "p4c_bulk") == (1, 0)
    added, dup = U.merge_records(acc, [rec_row("state_facts", type="OWNS", src="E1", dst="E2",
                                               confidence=cb)], "p4c_glean")
    assert (added, dup) == (0, 1)
    return acc, acc[0]["confidence"]


def test_merge_confidence_reads_both_copies_through_the_grade_guard():
    """Defect 25: the duplicate merge is a max-merge of an LLM score carried in a plain row dict.

    `confidence` reaches P5's `coalesce(confidence, 0.5)` edge weights and `p4c_ladder`'s
    `low_confidence` trigger, so a `True` (== 1) or `inf` challenger must not beat a real 0.9, and a
    broken incumbent must not silently win by default.
    """
    # A readable, higher challenger wins; a readable lower one does not.
    assert _dup_pair(0.8, 0.9)[1] == 0.9
    assert _dup_pair(0.9, 0.8)[1] == 0.9
    # `True` is not a score of 1.0: it cannot displace a readable 0.8.
    assert _dup_pair(0.8, True)[1] == 0.8
    # A non-finite challenger cannot win a max-merge either.
    assert _dup_pair(0.8, float("inf"))[1] == 0.8
    # Off-scale and stringified copies are unreadable too.
    for bad in (1.5, -0.1, float("nan"), "0.9", None, [0.9]):
        assert _dup_pair(0.8, bad)[1] == 0.8, bad


def test_merge_confidence_lets_a_readable_challenger_repair_a_broken_incumbent():
    """A broken incumbent must not win by default; two broken copies stay UNMEASURED (`None`)."""
    assert _dup_pair(True, 0.4)[1] == 0.4
    assert _dup_pair(float("inf"), 0.4)[1] == 0.4
    assert _dup_pair(True, "0.9")[1] is None
    assert _dup_pair(float("nan"), 1.5)[1] is None
    # A readable zero is measured, so it repairs nothing and is not confused with UNMEASURED.
    assert _dup_pair(0.0, 0.0)[1] == 0.0


def test_merge_keeps_records_with_identical_identity_but_different_evidence():
    acc: list[dict] = []
    a = rec_row("claims", kind="view", subjects=["E1"])
    b = rec_row("claims", kind="view", subjects=["E1"],
                quote="Delivery is due in 2025.", sids=[2])
    U.merge_records(acc, [a], "p4c_bulk")
    assert U.merge_records(acc, [b], "p4c_glean") == (1, 0)  # no sentence overlap -> distinct fact


def test_union_pack_merges_two_sources(monkeypatch):
    p = pack()

    def fake_kept_for(pack_, pass_name, model, mode=None):
        base = {"call": "ok", "total": 1, "dropped": 0,
                "chunks": {pack_["chunk_ids"][0]: {"state_facts": [], "events": [], "claims": []}}}
        if pass_name == "p4c_bulk":
            base["chunks"]["chunk_a"]["state_facts"] = [_Model(state_facts=True)]
        elif pass_name == "p4c_glm2":
            base["chunks"]["chunk_a"]["state_facts"] = [_Model(state_facts=True),
                                                       _Model(dst="E3")]
            base["new_entities"] = {"E9": "SHIP TWO"}
        return base

    monkeypatch.setattr(U, "kept_for", fake_kept_for)
    got = U.union_pack(p, [("p4c_bulk", "m1"), ("p4c_glm2", "m2")], modes={"m1": "tools",
                                                                          "m2": "tools"})
    row = got["rows"][0]
    assert row["chunk_id"] == "chunk_a"
    assert row["records_total"] == 2  # duplicate collapsed, distinct second record kept
    # provenance counts contributing records per source: the dup carries both, the extra one only glm2
    assert row["provenance"]["p4c_bulk"] == 1
    assert row["provenance"]["p4c_glm2"] == 2
    assert got["stats"]["duplicates"] == 1
    assert row["new_entities"] == {"E9": "SHIP TWO"}
    assert row["kept"]["state_facts"] == row["state_facts"]


def test_union_pack_flags_broken_chunk_when_every_call_failed(monkeypatch):
    p = pack()

    def fake_kept_for(pack_, pass_name, model, mode=None):
        return {"call": "schema_fail", "total": 0, "dropped": 0,
                "chunks": {pack_["chunk_ids"][0]: {"state_facts": [], "events": [], "claims": []}}}

    monkeypatch.setattr(U, "kept_for", fake_kept_for)
    got = U.union_pack(p, [("p4c_bulk", "m1"), ("p4c_glm2", "m2")],
                       modes={"m1": "tools", "m2": "tools"})
    row = got["rows"][0]
    assert row["call_broken"] is True
    assert row["no_content"] is False  # broken != legitimately empty
    assert row["records_total"] == 0


def test_union_pack_empty_chunk_is_not_broken_when_a_sibling_has_records(monkeypatch):
    """Defect 11: an empty-but-fine chunk must not inherit a sibling chunk's activity.

    The gate's per-chunk truth is that chunk's own `records_total`; a pack sum used to be compared
    against a per-chunk kept count, so every heading/boilerplate chunk inside a pack that returned
    records elsewhere was queued for D12 repair (~9x inflation of `failure_queue_rate`).
    """
    p = pack()
    p["chunk_ids"] = ["chunk_a", "chunk_b"]
    p["key"] = "doc_a|chunk_a"
    p["blocks"] = [dict(p["blocks"][0]),
                   {"cid": "c2", "sentences": [[3, "Table of contents"]]}]

    def fake_kept_for(pack_, pass_name, model, mode=None):
        return {"call": "ok", "total": 1, "dropped": 0,
                "chunk_total": {"chunk_a": 1, "chunk_b": 0},
                "chunks": {"chunk_a": {"state_facts": [_Model()], "events": [], "claims": []},
                           "chunk_b": {"state_facts": [], "events": [], "claims": []}}}

    monkeypatch.setattr(U, "kept_for", fake_kept_for)
    got = U.union_pack(p, [("p4c_bulk", "m1")], modes={"m1": "tools"})
    by_id = {r["chunk_id"]: r for r in got["rows"]}
    assert by_id["chunk_a"]["call_broken"] is False
    assert by_id["chunk_b"]["call_broken"] is False
    assert by_id["chunk_b"]["no_content"] is True  # legitimately empty, not broken
    assert got["stats"]["duplicates"] == 0


def test_union_pack_chunk_with_all_records_dropped_is_broken(monkeypatch):
    """The real D12 case: the chunk returned records and every one failed gates 2-4."""
    p = pack()
    p["chunk_ids"] = ["chunk_a", "chunk_b"]
    p["blocks"] = [dict(p["blocks"][0]), {"cid": "c2", "sentences": [[3, "More"]]}]

    def fake_kept_for(pack_, pass_name, model, mode=None):
        return {"call": "ok", "total": 1, "dropped": 1,
                "chunk_total": {"chunk_a": 1, "chunk_b": 1},
                "chunks": {"chunk_a": {"state_facts": [_Model()], "events": [], "claims": []},
                           "chunk_b": {"state_facts": [], "events": [], "claims": []}}}

    monkeypatch.setattr(U, "kept_for", fake_kept_for)
    got = U.union_pack(p, [("p4c_bulk", "m1")], modes={"m1": "tools"})
    by_id = {r["chunk_id"]: r for r in got["rows"]}
    assert by_id["chunk_a"]["call_broken"] is False  # kept a record
    assert by_id["chunk_b"]["call_broken"] is True   # returned one, kept none
    assert by_id["chunk_b"]["no_content"] is False


def test_kept_for_counts_records_per_chunk(monkeypatch):
    """`kept_for` must expose per-chunk returned counts, not just the pack sum."""
    p = pack()
    p["chunk_ids"] = ["chunk_a", "chunk_b"]
    p["blocks"] = [dict(p["blocks"][0]), {"cid": "c2", "sentences": [[3, "More"]]}]
    answer = json.dumps({"no_content": False, "state_facts": [
        {"type": "OWNS", "src": "E1", "dst": "N#1", "sids": [1], "confidence": 0.9,
         "chunk": "c1", "attr_notes": ""}], "events": [], "claims": [],
        "new_entities": [{"id": "N#1", "type": "vessel", "name": "SHIP TWO",
                          "chunk": "c1", "sids": [1]}]})
    monkeypatch.setattr(U.G, "raw_for", lambda *a, **k: Path("unused.json"))
    monkeypatch.setattr(U.G, "read_raw", lambda path: (answer, {}))
    got = U.kept_for(p, "p4c_bulk", "m1", "tools")
    assert got["total"] == 1
    assert got["chunk_total"] == {"chunk_a": 1, "chunk_b": 0}


def test_build_writes_audit_compatible_rows(monkeypatch, tmp_path):
    packs = tmp_path / "packs.jsonl"
    packs.write_text(json.dumps(pack()) + "\n", encoding="utf-8")

    def fake_kept_for(pack_, pass_name, model, mode=None):
        return {"call": "ok", "total": 1, "dropped": 0,
                "chunks": {pack_["chunk_ids"][0]: {"state_facts": [_Model(state_facts=True)],
                                                  "events": [], "claims": []}}}

    monkeypatch.setattr(U, "kept_for", fake_kept_for)
    monkeypatch.setattr(U.RUN, "load_modes", lambda: {"m1": "tools"})
    out = U.build([("p4c_bulk", "m1")], packs, tmp_path / "union")
    assert out["chunks"] == 1 and out["records"] == 1
    assert out["coverage_complete"] is False  # limited run
    assert out["failure_queue_rate"] == 0.0
    rows = [json.loads(line) for line in
            (tmp_path / "union/gated_union.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    flat = A.flat_records(rows)  # the audit step must see the union records unchanged
    assert len(flat) == 1
    assert flat[0]["kind"] == "state_facts"
    assert flat[0]["quote"] == "The ship SHIP TWO was sold for $10m."
    assert flat[0]["record"]["record_kind"] == "state_facts"


def test_parse_sources_accepts_defaults_and_overrides():
    assert [p for p, _ in U.parse_sources(None)] == [p for p, _ in U.SOURCE_SPEC]
    assert U.parse_sources("p4c_bulk,p4c_glm2:glm-5.3") == [("p4c_bulk", U.AMD),
                                                            ("p4c_glm2", "glm-5.3")]


class _Model:
    """Minimal stand-in for a pydantic extraction record (only what the union reads)."""

    def __init__(self, state_facts: bool = True, dst: str = "E2"):
        self.chunk = "c1"
        self.sids = [1]
        self.confidence = 0.7
        self.type = "OWNS"
        self.src = "E1"
        self.dst = dst

    def model_dump(self, mode: str = "json") -> dict:
        return {"chunk": self.chunk, "sids": self.sids, "confidence": self.confidence,
                "type": self.type, "src": self.src, "dst": self.dst}


def test_kept_for_reads_a_stored_raw(monkeypatch):
    p = pack()
    answer = json.dumps({"no_content": False, "state_facts": [
        {"type": "OWNS", "src": "E1", "dst": "N#1", "sids": [1], "confidence": 0.9,
         "chunk": "c1", "attr_notes": ""}], "events": [], "claims": [],
        "new_entities": [{"id": "N#1", "type": "vessel", "name": "SHIP TWO",
                          "chunk": "c1", "sids": [1]}]})
    monkeypatch.setattr(U.G, "raw_for", lambda *a, **k: Path("unused.json"))
    monkeypatch.setattr(U.G, "read_raw", lambda path: (answer, {}))
    got = U.kept_for(p, "p4c_bulk", "m1", "tools")
    assert got["call"] == "ok"
    assert got["total"] == 1 and got["dropped"] == 0
    assert len(got["chunks"]["chunk_a"]["state_facts"]) == 1


def test_kept_for_reports_blank_and_missing(monkeypatch):
    p = pack()
    monkeypatch.setattr(U.G, "raw_for", lambda *a, **k: Path("unused.json"))
    monkeypatch.setattr(U.G, "read_raw", lambda path: (None, None))
    assert U.kept_for(p, "p4c_bulk", "m1", "tools")["call"] == "missing"
    monkeypatch.setattr(U.G, "read_raw", lambda path: ("   ", {}))
    assert U.kept_for(p, "p4c_bulk", "m1", "tools")["call"] == "blank"


def _two_chunk_pack() -> dict:
    """A pack whose own key differs from either chunk's single-chunk key (Defect 12 shape)."""
    p = pack()
    p["chunk_ids"] = ["chunk_a", "chunk_b"]
    p["blocks"] = [{"cid": "c1", "sentences": [[1, "The ship SHIP TWO was sold for $10m."]]},
                   {"cid": "c2", "sentences": [[1, "The ship SHIP TWO was sold for $10m."]]}]
    p["key"] = "doc_a|aaa+bbb"  # multi-chunk key: not equal to any single-chunk key
    return p


def _rung_answer(cid: str = "c2") -> str:
    return json.dumps({"no_content": False, "state_facts": [
        {"type": "OWNS", "src": "E1", "dst": "N#1", "sids": [1], "confidence": 0.9,
         "chunk": cid, "attr_notes": ""}], "events": [], "claims": [],
        "new_entities": [{"id": "N#1", "type": "vessel", "name": "SHIP TWO",
                          "chunk": cid, "sids": [1]}]})


def _address_only_raw(monkeypatch, answered_key: str | None):
    """Make `raw_for` return a path that carries the addressed key, and answer only for one key."""
    monkeypatch.setattr(U.G, "raw_for", lambda pass_name, model, mode, p: Path(f"{p['key']}.json"))
    monkeypatch.setattr(U.G, "read_raw",
                        lambda path: (_rung_answer(), {}) if path.name == f"{answered_key}.json"
                        else (None, None))


def test_kept_for_reads_a_single_chunk_rung_raw(monkeypatch):
    """A ladder rung raw is keyed by `f"{doc_id}|{cid}"`, not by the parent pack key (Defect 12).

    Reading only the pack-keyed path made every retry/escalation answer look `missing`, so the
    D12 repair rungs could never move `failure_queue_rate` and `p4c_recall` never saw them either.
    """
    p = _two_chunk_pack()
    _address_only_raw(monkeypatch, "doc_a|chunk_b")  # the single-chunk key of the second cid
    got = U.kept_for(p, "p4c_bulk_retry", "DeepSeek-V4.1-Flash", "tools")
    assert got["call"] == "ok"
    assert got["chunk_total"] == {"chunk_a": 0, "chunk_b": 1}
    assert len(got["chunks"]["chunk_b"]["state_facts"]) == 1
    assert got["chunks"]["chunk_a"]["state_facts"] == []


def test_rung_fallback_keeps_a_missing_pack_missing(monkeypatch):
    """No rung call anywhere must stay `missing` - never reported as answered."""
    _address_only_raw(monkeypatch, "some_other_key")
    got = U.kept_for(_two_chunk_pack(), "p4c_bulk_retry", "DeepSeek-V4.1-Flash", "tools")
    assert got["call"] == "missing"
    assert got["total"] == 0


def test_rung_fallback_only_applies_to_single_keyed_passes(monkeypatch):
    """Full-pack passes (`p4c_bulk`) must keep their pack-keyed address only."""
    p = _two_chunk_pack()
    _address_only_raw(monkeypatch, "doc_a|chunk_b")
    assert U.kept_for(p, "p4c_bulk", "DeepSeek-V4.1-Flash", "tools")["call"] == "missing"
    assert "p4c_bulk" not in U.SINGLE_RUNG_PASSES
    assert {"p4c_bulk_retry", "p4c_esc"} <= U.SINGLE_RUNG_PASSES


def test_union_pack_sees_a_recovered_rung_chunk(monkeypatch):
    """The union row must flip off `call_missing` once the rung raw is addressable."""
    p = _two_chunk_pack()
    _address_only_raw(monkeypatch, "doc_a|chunk_b")
    got = U.union_pack(p, [("p4c_bulk_retry", "DeepSeek-V4.1-Flash")], modes={"DeepSeek-V4.1-Flash": "tools"})
    rows = {r["chunk_id"]: r for r in got["rows"]}
    assert rows["chunk_b"]["call_missing"] is False
    assert rows["chunk_b"]["records_ok"] == 1


def _rung_raws(monkeypatch, by_key: dict[str, str | None]):
    """Address each single-chunk rung raw by its own key and answer with the mapped text."""
    monkeypatch.setattr(U.G, "raw_for", lambda pass_name, model, mode, p: Path(f"{p['key']}.json"))
    monkeypatch.setattr(U.G, "read_raw", lambda path: (by_key.get(path.stem), {}))


def test_kept_for_recovers_a_rung_chunk_when_a_sibling_raw_is_unparseable(monkeypatch):
    """Defect 36: one broken rung raw must not discard the sibling that parses.

    `p017656` escalated to four single-chunk `p4c_esc` raws; three failed schema (`events.0.sids:
    Field required`) and one parsed. The old first-wins probe gated the whole pack against whichever
    candidate came first, so every chunk came out `call_broken=True total=0` and the readable sibling's
    records were silently dropped from the union - a lost measurement, never a real absence.
    """
    _rung_raws(monkeypatch, {"doc_a|chunk_a": '{"no_content": false, "events": [{"sids": null}]}',
                             "doc_a|chunk_b": _rung_answer("c2")})
    got = U.kept_for(_two_chunk_pack(), "p4c_esc", "glm-5.3", "tools")
    assert got["call"] == "ok"
    assert got["total"] == 1
    assert got["chunk_total"] == {"chunk_a": 0, "chunk_b": 1}
    assert len(got["chunks"]["chunk_b"]["state_facts"]) == 1
    assert got["chunks"]["chunk_a"]["state_facts"] == []


def test_rung_schema_fail_needs_every_candidate_to_be_unreadable(monkeypatch):
    """`schema_fail` means *no* candidate parsed - not that the first one happened to be broken."""
    _rung_raws(monkeypatch, {"doc_a|chunk_a": "{not json",
                             "doc_a|chunk_b": '{"no_content": false, "events": [{"sids": null}]}'})
    got = U.kept_for(_two_chunk_pack(), "p4c_esc", "glm-5.3", "tools")
    assert got["call"] == "schema_fail"
    assert got["total"] == 0
    _rung_raws(monkeypatch, {"doc_a|chunk_a": None, "doc_a|chunk_b": '{"no_content": false, "events": []}'})
    assert U.kept_for(_two_chunk_pack(), "p4c_esc", "glm-5.3", "tools")["call"] == "ok"


def test_union_pack_keeps_a_chunk_whose_sibling_rung_raw_failed_to_parse(monkeypatch):
    """The recovered chunk must stay off `call_broken` in the union row, and keep its records."""
    _rung_raws(monkeypatch, {"doc_a|chunk_a": '{"no_content": false, "events": [{"sids": null}]}',
                             "doc_a|chunk_b": _rung_answer("c2")})
    got = U.union_pack(_two_chunk_pack(), [("p4c_esc", "glm-5.3")], modes={"glm-5.3": "tools"})
    rows = {r["chunk_id"]: r for r in got["rows"]}
    assert rows["chunk_b"]["call_broken"] is False
    assert rows["chunk_b"]["records_ok"] == 1
    assert rows["chunk_b"]["provenance"] == {"p4c_esc": 1}
    assert rows["chunk_b"]["call_missing"] is False


def test_rung_blank_candidates_make_a_blank_pack_and_absent_ones_make_it_missing(monkeypatch):
    """`blank` is a delivered-but-empty answer; `missing` is no answer at all - never conflated."""
    _rung_raws(monkeypatch, {"doc_a|chunk_a": "   ", "doc_a|chunk_b": ""})
    got = U.kept_for(_two_chunk_pack(), "p4c_esc", "glm-5.3", "tools")
    assert got["call"] == "blank"
    assert got["total"] == 0
    _rung_raws(monkeypatch, {"doc_a|chunk_a": None, "doc_a|chunk_b": None})
    assert U.kept_for(_two_chunk_pack(), "p4c_esc", "glm-5.3", "tools")["call"] == "missing"


def test_a_blank_primary_raw_cannot_bury_a_readable_rung_sibling(monkeypatch):
    """Defect 36 top half: the pack-keyed raw arriving blank must not stop the rung read."""
    _rung_raws(monkeypatch, {"doc_a|aaa+bbb": "  ", "doc_a|chunk_b": _rung_answer("c2")})
    got = U.kept_for(_two_chunk_pack(), "p4c_esc", "glm-5.3", "tools")
    assert got["call"] == "ok"
    assert got["chunk_total"] == {"chunk_a": 0, "chunk_b": 1}


def test_union_pack_keeps_each_parsed_rung_candidate_for_its_own_chunk(monkeypatch):
    """Two parseable rung candidates must each keep their records - never the last one only.

    A one-chunk rung raw carries its own block's labels (`c1`/`c2`), and `G.pack_ctx` holds the whole
    pack's chunk ids, so folding each candidate in attributes it to the right chunk. Overwriting the
    accumulator per candidate would silently drop every earlier chunk's records (Defect 36, one level
    down).
    """
    p = _two_chunk_pack()
    _rung_raws(monkeypatch, {"doc_a|chunk_a": _rung_answer("c1"),
                             "doc_a|chunk_b": _rung_answer("c2")})
    got = U.kept_for(p, "p4c_esc", "glm-5.3", "tools")
    assert got["chunk_total"] == {"chunk_a": 1, "chunk_b": 1}
    assert got["total"] == 2
    assert got["chunks"]["chunk_a"]["state_facts"][0].chunk == "c1"
    assert got["chunks"]["chunk_b"]["state_facts"][0].chunk == "c2"
    rows = {r["chunk_id"]: r for r in U.union_pack(
        p, [("p4c_esc", "glm-5.3")], modes={"glm-5.3": "tools"})["rows"]}
    assert rows["chunk_a"]["records_ok"] == 1
    assert rows["chunk_b"]["records_ok"] == 1


def test_record_row_stamps_the_real_chunk_id_not_the_prompt_label():
    """`chunk` must be the DB chunk id, never the prompt-local label the extractor saw.

    P5's `chunk_mismatch` rejects any record whose `chunk` differs from the row it arrived in, so a
    prompt-local label makes every union record unusable and the graph silently comes out empty.
    """
    rec = _Model()
    assert rec.chunk == "c1"  # the raw record still carries the prompt-local label
    body = U.record_row("claims", rec, [(1, "The ship SHIP TWO was sold for $10m.")], "p4c_bulk",
                        "chunk_a")
    assert body["chunk"] == "chunk_a"
    assert body["sids"] == [1]


def test_union_pack_rows_carry_ids_that_match_their_pack(monkeypatch):
    p = pack()

    def fake_kept_for(pack_, pass_name, model, mode=None):
        return {"call": "ok", "total": 1, "dropped": 0,
                "chunks": {pack_["chunk_ids"][0]: {"state_facts": [_Model()], "events": [],
                                                   "claims": []}},
                "new_entities": {}}

    monkeypatch.setattr(U, "kept_for", fake_kept_for)
    got = U.union_pack(p, [("p4c_bulk", "m1")], modes={"m1": "tools"})
    row = got["rows"][0]
    assert row["chunk_id"] == "chunk_a"
    kept = row["kept"]["state_facts"]
    assert kept and all(r["chunk"] == row["chunk_id"] for r in kept)
