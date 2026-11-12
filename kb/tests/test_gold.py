"""Tests for kb/gold_set.py and kb/gold_report.py (PLAN 12.1, AGENT_TASK row 8)."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import gold_set as G  # noqa: E402


def test_clean_sig_normalises_unit_separator():
    assert G.clean_sig("VLCC\x1f260k WAF-CHINA") == "VLCC / 260k WAF-CHINA"
    assert G.clean_sig("  a   b  ") == "a b"
    assert G.clean_sig(None) == ""


def test_human_reads_measurement():
    assert G.human("tce_usd_per_day") == "Tce usd per day"
    assert G.human("") == "Value"


def test_unit_for_falls_back_to_measurement_map():
    assert G.unit_for("USD/day", "whatever") == "USD/day"
    assert G.unit_for(None, "tce_usd_day_current") == "USD/day"
    assert G.unit_for(None, "c3_tubarao_usd_t") == "USD/t"
    assert G.unit_for(None, "unknown_measurement") is None


def test_round_and_format():
    assert G.round_sig(1.23456, 2) == 1.23
    assert G.fmt_num(1521.0) == "1,521"
    assert G.fmt_num(12.5) == "12.50"
    assert G.fmt_num(0.5) == "0.50"


def test_builder_assigns_incrementing_ids_and_keeps_schema():
    b = G.Builder(None, random.Random(0))  # type: ignore[arg-type]
    b.add("a_single_number", "q1", {"value": 1.0, "unit": "USD", "tolerance": 0.01},
          "1 USD", [], {"checks": ["x"], "passed": True}, {})
    b.add("h_unanswerable", "q2", {"answerable": False, "gap_reason": "absent"},
          "gap", [], {"checks": ["y"], "passed": True}, {})
    assert [i["id"] for i in b.items] == ["G-001", "G-002"]
    for it in b.items:
        assert set(it) == {"id", "type", "question", "answer", "answer_text",
                           "sources", "verification", "filters", "judge_only"}
        assert it["judge_only"] is False


def test_targets_cover_plan_strata():
    assert G.TARGETS == {
        "a_single_number": 50, "b_window_aggregate": 25, "c_multihop_entity": 35,
        "d_event_market": 25, "e_sec_section": 35, "f_summary_trend": 25,
        "g_as_known_on_date": 15, "h_unanswerable": 40,
    }
    assert sum(G.TARGETS.values()) == 250


SET = KB / "state" / "gold" / "gold_set.json"


@pytest.mark.skipif(not SET.exists(), reason="gold set not built yet")
def test_built_set_structure_and_verification():
    payload = json.loads(SET.read_text(encoding="utf-8"))
    items = payload["items"]
    assert len(items) == len({i["id"] for i in items})
    assert payload["sample_seed"] == G.seed_for("GOLD_SET")
    for it in items:
        assert it["type"] in G.TARGETS
        assert it["question"].strip()
        assert it["verification"]["passed"] is True
        assert it["verification"]["checks"]
        if it["type"] == "h_unanswerable":
            assert it["answer"]["answerable"] is False
            assert it["answer"]["gap_reason"]
            assert it["sources"] == []
        else:
            assert it["sources"], it["id"]
        if it["type"] in ("a_single_number", "b_window_aggregate", "g_as_known_on_date"):
            assert it["answer"]["tolerance"] > 0
            assert it["answer"]["unit"]
        if it["type"] == "c_multihop_entity":
            assert isinstance(it["answer"]["publishers"], list)
            assert it["answer"]["n_docs"] >= 1
        if it["type"] == "e_sec_section":
            assert it["answer"]["heading"]
            assert it["sources"][0]["section_id"]


@pytest.mark.skipif(not (KB / "reports" / "gold_set.json").exists(),
                    reason="gold report not generated yet")
def test_report_manifest_matches_set():
    rep = json.loads((KB / "reports" / "gold_set.json").read_text(encoding="utf-8"))
    if not SET.exists():
        pytest.skip("state set missing")
    payload = json.loads(SET.read_text(encoding="utf-8"))
    assert len(rep["manifest"]) == len(payload["items"])
    assert sum(rep["counts"].values()) == len(payload["items"])
