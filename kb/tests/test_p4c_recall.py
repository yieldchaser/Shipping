"""Unit tests for kb/p4c_recall.py - pure scoring, pack indexing and one-source flattenting."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kb"))

import p4c_recall as RC  # noqa: E402
import p4c_union as U  # noqa: E402


def rec_row(rkind: str, **body) -> dict:
    row = {"record_kind": rkind, "chunk": "c1", "sids": [1], "sources": ["s"]}
    row.update(body)
    return row


def pack(chunk_ids=("chunk_a",), blocks=None) -> dict:
    if blocks is None:
        blocks = [{"cid": "c1", "sentences": [[1, "The ship SHIP TWO was sold for $10m."]]}]
    return {"doc_id": "doc1", "chunk_ids": list(chunk_ids), "blocks": blocks,
            "ord_first": 0, "year": 2024, "section_class": "prose", "known": []}


def cand(typ: str, quote: str, kind: str = "events", **body) -> tuple:
    return (U.sig_of(rec_row(kind, type=typ, roles=[], **body)), quote, kind, rec_row(kind, type=typ, **body))


def ref(typ: str, quote: str, kind: str = "events", **body) -> dict:
    row = rec_row(kind, type=typ, **body)
    body = dict(row)
    body.pop("record_kind")
    return {"sig": U.sig_of(row), "quote": quote, "kind": kind, "rec": body, "models": {"m1", "m2"}}


def test_pack_sentences_returns_the_block_for_one_chunk():
    p = pack(chunk_ids=("chunk_a", "chunk_b"),
             blocks=[{"cid": "c1", "sentences": [[1, "alpha here"]]},
                     {"cid": "c2", "sentences": [[2, "beta here"]]}])
    assert RC.pack_sentences(p, "chunk_b") == [(2, "beta here")]


def test_item_rows_emits_one_row_per_kept_record_of_the_chunk():
    class Rec:
        def __init__(self, body):
            self._b = body

        def model_dump(self, mode="json"):
            return dict(self._b)

        def __getattr__(self, name):
            return self._b[name]

    kept = {"call": "ok", "chunks": {"chunk_a": {"state_facts": [Rec({"src": "E1", "dst": "E2",
                                                                      "type": "owns", "sids": [1],
                                                                      "chunk": "c1", "confidence": 0.9})],
                                      "events": [], "claims": []}}}
    rows = RC.item_rows(kept, "chunk_a", [(1, "The ship SHIP TWO was sold for $10m.")], "p4c_bulk")
    assert len(rows) == 1
    assert rows[0]["record_kind"] == "state_facts"
    assert rows[0]["quote"] == "The ship SHIP TWO was sold for $10m."


def test_flat_candidates_uses_closed_ontology_signature():
    rows = [rec_row("events", type="sale", quote="The sale closed.",
                    roles=[{"entity": "vessel:v1", "role": "object"}])]
    flat = RC.flat_candidates(rows)
    assert len(flat) == 1
    sig, quote, kind, _row = flat[0]
    assert kind == "events" and sig[1] == "sale" and "vessel:v1" in sig[2]


def test_score_counts_matched_reference_records():
    chunk_candidates = {"chunk_a": [cand("sale", "The ship SHIP TWO was sold for $10m."),
                                    cand("purchase", "Nobody bought the other one.")]}
    reference = {"chunk_a": {"records": [ref("sale", "The ship SHIP TWO was sold for $10m.")]}}
    sc = RC.score(chunk_candidates, reference)
    assert sc["matched"] == 1
    assert sc["candidates"] == 2
    assert sc["reference"] == 1
    assert sc["recall"] == 1.0
    assert sc["precision_optimistic"] == 0.5
    assert sc["f1_optimistic"] == pytest.approx(0.6667, abs=1e-4)


def test_score_recall_zero_when_reference_missed_entirely():
    chunk_candidates = {"chunk_a": [cand("sale", "Totally different words about grain.")]}
    reference = {"chunk_a": {"records": [ref("sale", "The ship SHIP TWO was sold for $10m.")]}}
    sc = RC.score(chunk_candidates, reference)
    assert sc["matched"] == 0
    assert sc["recall"] == 0.0
    assert sc["precision_optimistic"] == 0.0


def test_score_handles_chunk_missing_from_reference():
    sc = RC.score({"chunk_b": [cand("sale", "x y z")]}, {"chunk_a": {"records": []}})
    assert sc["reference"] == 0 and sc["matched"] == 0 and sc["recall"] == 0.0


def test_chunk_index_finds_gold_packs_and_stops_early(tmp_path):
    packs = tmp_path / "packs.jsonl"
    rows = [
        {"doc_id": "d1", "chunk_ids": ["chunk_a", "chunk_b"]},
        {"doc_id": "d2", "chunk_ids": ["chunk_c"]},
        {"doc_id": "d3", "chunk_ids": ["chunk_z"]},
    ]
    packs.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    items = [{"chunk_id": "chunk_c"}]
    idx = RC.chunk_index(items, packs)
    assert list(idx) == ["chunk_c"]
    assert idx["chunk_c"]["doc_id"] == "d2"


def test_source_candidates_regates_one_chunk(monkeypatch):
    sent = [(1, "The ship SHIP TWO was sold for $10m.")]

    class Rec:
        def model_dump(self, mode="json"):
            return {"type": "sale", "sids": [1], "chunk": "c1", "confidence": 0.9, "roles": []}

        def __getattr__(self, name):
            return {"chunk": "c1", "sids": [1]}[name]

    monkeypatch.setattr(U, "kept_for", lambda *a, **k: {
        "call": "ok", "chunks": {"chunk_a": {"state_facts": [], "events": [Rec()], "claims": []}}})
    p = pack(blocks=[{"cid": "c1", "sentences": [list(s) for s in sent]}])
    flat = RC.source_candidates(p, "chunk_a", "p4c_bulk", "ultrafast")
    assert len(flat) == 1
    assert flat[0][1] == sent[0][1]


def test_union_candidates_reads_the_merged_row(monkeypatch):
    row = {"chunk_id": "chunk_a", "kept": {"state_facts": [], "events": [],
                                          "claims": [rec_row("claims", kind="forecast",
                                                             subjects=["company:c1"], type=None,
                                                             quote="Rates will rise.")]}}
    monkeypatch.setattr(U, "union_pack", lambda p, srcs: {"rows": [row]})
    flat = RC.union_candidates(pack(), "chunk_a", [("p4c_bulk", "ultrafast")])
    assert len(flat) == 1
    assert flat[0][2] == "claims"
    assert flat[0][1] == "Rates will rise."


def test_measure_reports_every_source_plus_union(monkeypatch):
    items = [{"chunk_id": "chunk_a"}]
    fake = [cand("sale", "The ship SHIP TWO was sold for $10m.")]
    monkeypatch.setattr(RC, "source_candidates", lambda *a, **k: list(fake))
    monkeypatch.setattr(RC, "union_candidates", lambda *a, **k: list(fake))
    reference = {"chunk_a": {"records": [ref("sale", "The ship SHIP TWO was sold for $10m.")]}}
    res = RC.measure(items, {"chunk_a": pack()}, reference,
                     [("p4c_bulk", "ultrafast"), ("p4c_esc", "glm-5.3")])
    assert [s["pass"] for s in res["sources"]] == ["p4c_bulk", "p4c_esc"]
    assert all(s["recall"] == 1.0 for s in res["sources"])
    assert res["union"]["recall"] == 1.0
    assert res["union"]["pass"] == "union"


def test_measure_skips_items_without_a_pack(monkeypatch):
    monkeypatch.setattr(RC, "source_candidates", lambda *a, **k: [])
    monkeypatch.setattr(RC, "union_candidates", lambda *a, **k: [])
    reference = {"chunk_a": {"records": []}}
    res = RC.measure([{"chunk_id": "chunk_missing"}], {}, reference, [("p4c_bulk", "ultrafast")])
    assert res["sources"][0]["candidates"] == 0
    assert res["union"]["candidates"] == 0


def test_p4b_candidates_replays_through_evaluate(monkeypatch):
    seen = {}

    def fake_evaluate(pass_name, model, items):
        seen.update(pass_name=pass_name, model=model)
        return {"chunks": {"chunk_a": {"call": "ok", "chunk_id": "chunk_a"}}}

    def fake_flat(gated, sents):
        seen["sents"] = sents
        return [cand("sale", "The ship SHIP TWO was sold for $10m.")]

    monkeypatch.setattr(RC.B, "evaluate", fake_evaluate)
    monkeypatch.setattr(RC.B, "flat_records", fake_flat)
    items = [{"chunk_id": "chunk_a", "sentences": [[1, "The ship SHIP TWO was sold for $10m."]]}]
    got, ev = RC.p4b_candidates(items, "p4b_cand", "ultrafast")
    assert seen == {"pass_name": "p4b_cand", "model": "ultrafast",
                    "sents": [(1, "The ship SHIP TWO was sold for $10m.")]}
    assert len(got["chunk_a"]) == 1 and "chunk_a" in ev["chunks"]


def test_p4b_candidates_empty_when_chunk_ungated(monkeypatch):
    monkeypatch.setattr(RC.B, "evaluate", lambda *a, **k: {"chunks": {}})
    monkeypatch.setattr(RC.B, "flat_records", lambda *a, **k: pytest.fail("no gated chunk"))
    got, _ev = RC.p4b_candidates([{"chunk_id": "chunk_a", "sentences": []}], "p4b_cand", "m")
    assert got == {"chunk_a": []}


def test_cand_adjudication_indexes_the_nested_meta(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (state / "adjudication.json").write_text(json.dumps({"candidate_items": [
        {"phase": "p4b_cand", "meta": {"model": "m1", "chunk_id": "chunk_a", "idx": 0},
         "decision": "keep", "record": {}},
        {"phase": "p4b_cand", "meta": {"model": "m1", "chunk_id": "chunk_a", "idx": 1},
         "decision": "drop", "record": {}}]}), encoding="utf-8")
    monkeypatch.setattr(RC.B, "STATE", state)
    got = RC.cand_adjudication()
    assert got == {("m1", "chunk_a", 0): "keep", ("m1", "chunk_a", 1): "drop"}


def test_cand_adjudication_empty_without_the_file(tmp_path, monkeypatch):
    monkeypatch.setattr(RC.B, "STATE", tmp_path / "nowhere")
    assert RC.cand_adjudication() == {}


def test_measure_replays_p4b_sources_and_reports_style_recall(monkeypatch):
    items = [{"chunk_id": "chunk_a", "sentences": [[1, "The ship SHIP TWO was sold for $10m."]]}]
    fake = [cand("sale", "The ship SHIP TWO was sold for $10m.")]
    monkeypatch.setattr(RC, "p4b_candidates", lambda *a, **k: ({"chunk_a": list(fake)},
                                                               {"chunks": {}}))
    monkeypatch.setattr(RC.B, "score_model",
                        lambda *a, **k: {"recall": 0.4006, "precision": 0.9222})
    monkeypatch.setattr(RC, "cand_adjudication", lambda: {("m", "chunk_a", 0): "keep"})
    monkeypatch.setattr(RC, "union_candidates", lambda *a, **k: [])
    reference = {"chunk_a": {"records": [ref("sale", "The ship SHIP TWO was sold for $10m.")]}}
    res = RC.measure(items, {}, reference, [("p4b_cand", "ultrafast")])
    row = res["sources"][0]
    assert row["pass"] == "p4b_cand" and row["recall"] == 1.0
    assert row["p4b_style_recall"] == 0.4006 and row["p4b_style_precision"] == 0.9222
    assert res["union"]["candidates"] == 0
