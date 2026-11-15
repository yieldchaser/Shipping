"""Unit tests for kb/p4c_ladder.py (rule-6 triggers, medians, retry + capped escalation plan)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import p4c_ladder as L


def row(cid="c1", doc_type="broker_weekly", section="prose", tokens=900,
        total=4, ok=4, conf=0.9, fail=None, call_missing=False) -> dict:
    return {"chunk_id": cid, "doc_id": "d1", "doc_type": doc_type, "section_class": section,
            "approx_tokens": tokens, "records_total": total, "records_ok": ok,
            "call_missing": call_missing,
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


def test_missing_rows_are_not_gated_and_do_not_lower_medians():
    """A never-extracted row must not enter the queue, its rate, or the rule 6c medians."""
    rows = [row("a", total=10, ok=1), row("m1", call_missing=True, tokens=900, ok=0),
            row("m2", call_missing=True, tokens=900, ok=0), row("b", conf=0.2), row("c")]
    q = L.build_queue(rows)
    assert q["chunks_gated"] == 3
    assert [x["chunk_id"] for x in q["queue"]] == ["a", "b"]
    assert q["queue_rate"] == pytest.approx(0.6667)
    # medians see only real rows [1,4,4] -> 4.0; including the two zero-record missing rows would
    # give median([1,0,0,4,4]) == 0.0, which would make every real long chunk look "thin".
    assert L.section_medians(rows) == {"broker_weekly/prose": 4.0}


def test_load_gated_flattens_pack_rows(tmp_path):
    path = tmp_path / "gated.jsonl"
    path.write_text(
        json.dumps({"pack_key": "k", "chunks": {"c1": row("c1")}}) + "\n"
        + json.dumps(row("c2")) + "\n", encoding="utf-8")
    assert [r["chunk_id"] for r in L.load_gated(path)] == ["c1", "c2"]


def _write_gate(tmp_path, name, rows):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_merged_rows_matches_materialising_map_on_order_and_overrides(tmp_path):
    """Memory fix must not change which row wins, nor the order the queue is built in.

    Later files override per chunk; chunks introduced only by a later file keep that file's order
    and are appended after the shared ones — exactly `gated_chunk_map(...).values()`.
    """
    a = _write_gate(tmp_path, "a.jsonl", [row("c1", conf=0.1), row("c2", conf=0.1),
                                          row("onlyA", conf=0.1)])
    b = _write_gate(tmp_path, "b.jsonl", [row("c2", conf=0.9), row("onlyB", conf=0.9)])
    c = _write_gate(tmp_path, "c.jsonl", [row("c1", conf=0.3), row("onlyC", conf=0.9)])
    paths = [a, b, c]
    expected = list(L.gated_chunk_map(paths=paths).values())
    got = list(L._merged_rows(paths))
    assert [r["chunk_id"] for r in got] == [r["chunk_id"] for r in expected]
    assert [r["chunk_id"] for r in got] == ["c1", "c2", "onlyA", "onlyB", "onlyC"]
    # overrides really did take effect: c1 <- c, c2 <- b
    assert {r["chunk_id"]: r["mean_confidence"] for r in got} == {
        "c1": 0.3, "c2": 0.9, "onlyA": 0.1, "onlyB": 0.9, "onlyC": 0.9}
    # and the streaming queue agrees with the materialising build_queue on the same rows
    assert L.build_queue_stream(paths) == L.build_queue(expected)


def test_merged_rows_is_exact_when_a_file_repeats_a_chunk_id(tmp_path):
    """Duplicated chunk_ids (pathological) must still resolve last-wins, as the dict does."""
    a = _write_gate(tmp_path, "a.jsonl", [row("c1", conf=0.1), row("c1", conf=0.7)])
    b = _write_gate(tmp_path, "b.jsonl", [row("c1", conf=0.2)])
    paths = [a, b]
    expected = list(L.gated_chunk_map(paths=paths).values())
    got = list(L._merged_rows(paths))
    assert [(r["chunk_id"], r["mean_confidence"]) for r in got] == \
           [(r["chunk_id"], r["mean_confidence"]) for r in expected]
    assert [r["mean_confidence"] for r in got] == [0.2]


def test_merged_rows_single_file_streams_without_buffering(tmp_path):
    a = _write_gate(tmp_path, "a.jsonl", [row("c1"), row("c2")])
    assert [r["chunk_id"] for r in L._merged_rows([a])] == ["c1", "c2"]
    assert L.build_queue_stream([a]) == L.build_queue([row("c1"), row("c2")])


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


def test_esc_gated_overrides_only_the_escalation_ranking(tmp_path):
    """--esc-gated repoints esc at the post-retry residual; the bulk rule-6 queue is untouched."""
    packs = write_packs(tmp_path, [mk_pack("p1", ["c1"]), mk_pack("p2", ["c2"])])
    bulk = tmp_path / "bulk.jsonl"
    # c1 and c2 both fail pre-retry, so both queue and both are esc candidates
    bulk.write_text("\n".join(json.dumps(r) for r in
                              [row("c1", total=10, ok=1), row("c2", total=10, ok=1)]) + "\n",
                    encoding="utf-8")
    post = tmp_path / "post.jsonl"
    # post-retry: c1 is now clean, c2 is still failing
    post.write_text("\n".join(json.dumps(r) for r in
                              [row("c1", total=4, ok=4), row("c2", total=10, ok=1)]) + "\n",
                     encoding="utf-8")
    plan = tmp_path / "plan.json"
    sys.argv = ["p4c_ladder", "--gated", str(bulk), "--esc-gated", str(post),
                "--packs", str(packs), "--plan", str(plan),
                "--retry-out", str(tmp_path / "r.jsonl"),
                "--esc-out", str(tmp_path / "e.jsonl"), "--cap", "10"]
    assert L.main() == 0
    d = json.loads(plan.read_text(encoding="utf-8"))
    # the free-retry queue still follows the BULK gate: both chunks were failing there
    assert d["retry"]["singles"] == 2
    assert d["queue"]["chunks_gated"] == 2
    # esc follows the POST slice: only the still-broken chunk is bought. `skipped` counts chunks
    # dropped by the CAP, not chunks filtered out by the gate, so it stays 0 here.
    assert d["escalation"]["candidates"] == 1
    assert d["escalation"]["skipped"] == 0
    assert d["escalation"]["esc_source"] == str(post)
    esc = [json.loads(line) for line in (tmp_path / "e.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [p["chunk_ids"] for p in esc] == [["c2"]]


def test_escalation_cap_defaults_to_the_config_booking_not_a_hardcoded_17():
    """The ladder must spend the booking that config actually authorises.

    `ESC_CAP_USD = 17.0` outlived the C1 rebooking that cut `escalation_plus_gleaning` to 11 (the AMD
    bulk pass is paid, so it came out of the other lines). A stale hardcoded cap silently authorises
    six dollars of escalation the owner never booked - the third-site defect class, where the number
    the reader trusts is the *denominator*.
    """
    import yaml
    cfg = yaml.safe_load((L.KB / "config.yaml").read_text(encoding="utf-8"))
    booked = float(cfg["budget"]["passes"]["escalation_plus_gleaning"])
    assert L.escalation_cap() == booked
    assert booked != 17.0, "if the booking moves back to 17 this test no longer proves anything"


def test_cap_missing_from_config_is_unmeasured_and_never_a_fallback_constant(monkeypatch):
    """An unreadable config must read as UNMEASURED, not as a cap the owner never booked.

    The old reader returned `FALLBACK_ESC_CAP_USD = 11.0` here, so a broken config silently booked
    against a fabricated `$11` denominator and the plan printed it as measured (Defect 17 class).
    """
    monkeypatch.setattr(L, "KB", L.Path("no/such/dir"))
    assert L.escalation_cap() is None
    assert not hasattr(L, "FALLBACK_ESC_CAP_USD"), (
        "a fallback cap constant is the defect: an unreadable config must not resolve to a number")
    with pytest.raises(ValueError):
        L.rank_escalation(L.PACKS, [], None)


def test_a_missing_or_bool_cap_is_unmeasured(monkeypatch, tmp_path):
    """`isinstance(True, (int, float))` is True, so a `true` booking would read as a `$1` cap."""
    cfg = tmp_path / "config.yaml"

    def reader(value):
        cfg.write_text("budget:\n  passes:\n    escalation_plus_gleaning: "
                       + ("null\n" if value is None else f"{value!r}\n"), encoding="utf-8")
        monkeypatch.setattr(L, "KB", tmp_path)
        return L.escalation_cap()

    assert reader(None) is None
    assert reader(True) is None
    assert reader("17") is None
    assert reader(11) == 11.0


def test_summarise_renders_money_through_the_three_state_formatter():
    """A sub-cent tier estimate and an unmeasured cap must not both print as `$0.00`."""
    plan = {"queue": {"chunks_gated": 10, "queue": [1], "queue_rate": 0.1,
                      "trigger_counts": {"fail_pct": 1}},
            "retry": {"singles": 1, "unmatched": 0},
            "escalation": {"picked": [1], "spent": 1.3e-05, "cap": None, "skipped": 0,
                           "tiers": {1: {"calls": 1, "est_cost": 1.3e-05}}}}
    text = L.summarise(plan)
    assert "est $0.00001/UNMEASURED" in text, text
    assert "$0.00 " not in text, "the old `:.2f` renderer flattened a real sub-cent estimate to $0.00"
    tier_line = next(ln for ln in text.splitlines() if "sec_mda_fleet" in ln)
    assert tier_line.rstrip().endswith("est $0.00001"), tier_line
