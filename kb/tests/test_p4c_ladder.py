"""Unit tests for kb/p4c_ladder.py (rule-6 triggers, medians, retry + capped escalation plan)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import p4c_ladder as L


def row(cid="c1", doc_type="broker_weekly", section="prose", tokens=900,
        total=4, ok=4, conf=0.9, fail=None) -> dict:
    return {"chunk_id": cid, "doc_id": "d1", "doc_type": doc_type, "section_class": section,
            "approx_tokens": tokens, "records_total": total, "records_ok": ok,
            "failed_pct": round((total - ok) / total, 4) if fail is None and total else (fail or 0.0),
            "mean_confidence": conf}


def test_trigger_fail_pct_only_above_30pct():
    med = {}
    assert L.triggers(row(total=10, ok=7), med) == []          # exactly 30% is not ">30%"
    assert L.triggers(row(total=10, ok=6), med) == ["fail_pct"]


def test_trigger_low_confidence_and_empty_chunk():
    med = {}
    assert L.triggers(row(conf=0.49), med) == ["low_confidence"]
    assert L.triggers(row(conf=0.5), med) == []
    # a chunk with no records at all is not a confidence signal by itself
    assert L.triggers(row(total=0, ok=0, conf=None), med) == []


def test_trigger_thin_long_sec_chunk():
    med = {"sec_10k/md_a": 8.0}
    base = dict(doc_type="sec_10k", section="md_a", tokens=1500)
    assert L.triggers(row(**base, total=8, ok=3, fail=0.0), med) == ["thin_long_sec"]
    assert L.triggers(row(**base, total=8, ok=4, fail=0.0), med) == []
    # short SEC chunk does not fire, and non-SEC doc types never fire on this rule
    assert L.triggers(row(**{**base, "tokens": 300}, total=8, ok=1, fail=0.0), med) == []
    assert L.triggers(row(doc_type="broker_weekly", tokens=1500, total=8, ok=1, fail=0.0),
                      {"broker_weekly/prose": 8.0}) == []


def test_section_medians_use_long_chunks_only():
    rows = [row("a", tokens=900, ok=2), row("b", tokens=900, ok=4),
            row("c", tokens=900, ok=6), row("short", tokens=100, ok=99)]
    med = L.section_medians(rows)
    assert med == {"broker_weekly/prose": 4.0}


def test_build_queue_counts_and_rate():
    rows = [row("a", total=10, ok=1), row("b", conf=0.2), row("c")]
    q = L.build_queue(rows)
    assert q["chunks_gated"] == 3
    assert [x["chunk_id"] for x in q["queue"]] == ["a", "b"]
    assert q["trigger_counts"] == {"fail_pct": 1, "low_confidence": 1}
    assert q["queue_rate"] == pytest.approx(0.6667)


def test_load_gated_flattens_pack_rows(tmp_path):
    path = tmp_path / "gated.jsonl"
    path.write_text(
        json.dumps({"pack_key": "k", "chunks": {"c1": row("c1")}}) + "\n"
        + json.dumps(row("c2")) + "\n", encoding="utf-8")
    assert [r["chunk_id"] for r in L.load_gated(path)] == ["c1", "c2"]


def mk_pack(pid, cids, doc_type="broker_weekly", text="plain text", tokens=800):
    return {"n": 0, "pack_id": pid, "doc_id": "d1", "ord_first": 0, "key": pid,
            "chunk_ids": list(cids), "tokens": tokens,
            "doc": {"publisher": "Fearnleys", "doc_type": doc_type,
                    "published_at": "2024-01-01", "heading": "Weekly"},
            "year": 2024, "section_class": "prose",
            "blocks": [{"cid": c, "sentences": [[1, text]]} for c in cids],
            "known": [], "known_ids": []}


def write_packs(tmp_path, packs):
    path = tmp_path / "packs.jsonl"
    path.write_text("\n".join(json.dumps(p) for p in packs) + "\n", encoding="utf-8")
    return path


def test_plan_retry_and_escalation_writers(tmp_path):
    packs = write_packs(tmp_path, [mk_pack("p1", ["c1", "c2"]), mk_pack("p2", ["c3"])])
    retry = L.plan_retry(packs, [{"chunk_id": "c1"}, {"chunk_id": "c3"}],
                         tmp_path / "retry.jsonl")
    assert retry["singles"] == 2 and retry["unmatched"] == 0
    rows = [json.loads(x) for x in (tmp_path / "retry.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["chunk_ids"] for r in rows] == [["c1"], ["c3"]]
    assert all(r["blocks"][0]["cid"] == r["chunk_ids"][0] for r in rows)
    esc = L.rank_escalation(packs, [{"chunk_id": "c1"}, {"chunk_id": "c3"}], cap=10.0)
    assert esc["candidates"] == 2 and esc["skipped"] == 0
    n = L.write_escalation(esc["picked"], packs, tmp_path / "esc.jsonl")
    assert n == 2
    assert len((tmp_path / "esc.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_rank_escalation_is_doc_value_ordered_and_capped(tmp_path):
    # c1 sits in a gold chunk; c2 is a dense broker-forecast chunk; c3 is plain prose
    packs = write_packs(tmp_path, [
        mk_pack("p1", ["c1"], text="plain gold"),
        mk_pack("p2", ["c2"], text="outlook forecast expect projection guidance"),
        mk_pack("p3", ["c3"], text="plain text")])
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps([{"chunk_id": "c1"}]), encoding="utf-8")
    old = L.HV.GOLD_ITEMS
    L.HV.GOLD_ITEMS = gold
    try:
        esc = L.rank_escalation(packs, [{"chunk_id": c} for c in ("c1", "c2", "c3")], cap=1.0)
    finally:
        L.HV.GOLD_ITEMS = old
    tiers = [m["tier"] for m in esc["picked"]]
    assert tiers == sorted(tiers), "picked order must follow the doc-value tier ladder"
    assert esc["picked"][0]["chunk_id"] == "c1"
    assert esc["spent"] <= esc["cap"]
    # a cap below one call buys nothing but is reported, never silently overrun
    old = L.HV.GOLD_ITEMS
    L.HV.GOLD_ITEMS = gold
    try:
        none = L.rank_escalation(packs, [{"chunk_id": "c1"}], cap=0.0001)
    finally:
        L.HV.GOLD_ITEMS = old
    assert none["picked"] == [] and none["skipped"] == 1 and none["spent"] == 0.0


def test_summarise_names_every_rung():
    plan = {"queue": {"chunks_gated": 10, "queue": [1], "queue_rate": 0.1,
                      "trigger_counts": {"fail_pct": 1}},
            "retry": {"singles": 1, "unmatched": 0},
            "escalation": {"picked": [1], "spent": 0.02, "cap": 17.0, "skipped": 0,
                           "tiers": {1: {"calls": 1, "est_cost": 0.02}}}}
    text = L.summarise(plan)
    assert "free retry singles 1" in text
    assert "glm-5.3 escalation 1 calls" in text
    assert "sec_mda_fleet" in text


def test_cli_plan_only_writes_plan_and_packs(tmp_path):
    packs = write_packs(tmp_path, [mk_pack("p1", ["c1"]), mk_pack("p2", ["c2"])])
    gated = tmp_path / "gated.jsonl"
    gated.write_text("\n".join(json.dumps(r) for r in
                               [row("c1", total=10, ok=1), row("c2")]) + "\n", encoding="utf-8")
    plan = tmp_path / "plan.json"
    sys.argv = ["p4c_ladder", "--gated", str(gated), "--packs", str(packs),
                "--plan", str(plan), "--retry-out", str(tmp_path / "r.jsonl"),
                "--esc-out", str(tmp_path / "e.jsonl"), "--cap", "0.5"]
    assert L.main() == 0
    d = json.loads(plan.read_text(encoding="utf-8"))
    assert d["queue"]["chunks_gated"] == 2
    assert d["queue_head"][0]["chunk_id"] == "c1"
    assert d["retry"]["singles"] == 1
    assert d["escalation"]["packs_written"] == 1
    assert d["escalation"]["partial_coverage"] is True
    esc = [json.loads(line) for line in (tmp_path / "e.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [p["chunk_ids"] for p in esc] == [["c1"]]
