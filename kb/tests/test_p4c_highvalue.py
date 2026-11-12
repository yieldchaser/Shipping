"""Unit tests for kb/p4c_highvalue.py (tiers, ranking, budget-greedy selection, writer)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import p4c_highvalue as H


def mk(pack_id="p1", chunk_ids=("c1",), text="vessel sale fixture", doc_type="broker_weekly",
       publisher="Fearnleys", heading="Tanker Report", section="prose", tokens=1000, year=2024):
    return {"pack_id": pack_id, "doc_id": "d1", "ord_first": 0, "key": pack_id,
            "chunk_ids": list(chunk_ids), "tokens": tokens, "doc": {
                "publisher": publisher, "doc_type": doc_type, "published_at": "2024-01-01",
                "heading": heading}, "year": year, "section_class": section,
            "blocks": [{"cid": chunk_ids[0], "sentences": [[1, text]]}],
            "known": [], "known_ids": [], "n": 0}


def test_tier_gold_wins_over_everything():
    assert H.tier_of(mk(chunk_ids=("gold1",), doc_type="sec_10k"), {"gold1"}) == "gold"


def test_tier_sec_mda_by_section_class():
    assert H.tier_of(mk(doc_type="sec_10k", section="md_a", text="no keywords"),
                     {"gold1"}) == "sec_mda_fleet"


def test_tier_sec_by_fleet_keyword():
    p = mk(doc_type="sec_20f", section="prose", text="our fleet of 40 vessels")
    assert H.tier_of(p, set()) == "sec_mda_fleet"


def test_tier_broker_forecast_before_fixture():
    p = mk(text="outlook for the market is strong", doc_type="broker_daily")
    assert H.tier_of(p, set()) == "broker_forecast"
    q = mk(text="time charter fixture done at 20000", doc_type="broker_daily")
    assert H.tier_of(q, set()) == "fixtures_tc"


def test_tier_sp_index_and_other():
    assert H.tier_of(mk(doc_type="book", publisher="S&P Global", heading="Platts"),
                     set()) == "sp_index"
    assert H.tier_of(mk(doc_type="book", publisher="Reference Literature",
                        heading="History", text="plain text"), set()) == "other"


def test_score_prefers_keyword_hits_over_recency():
    dense = mk(text="outlook forecast expect projection guidance", year=2004)
    recency = mk(text="plain prose here", year=2026)
    assert H.score_of(dense) > H.score_of(recency)


def test_est_cost_scales_with_tokens():
    assert H.est_cost(mk(tokens=100)) < H.est_cost(mk(tokens=3000))
    # a mean pack must stay in the ledger-observed ballpark (~$0.013-$0.03/call)
    assert 0.01 < H.est_cost(mk(tokens=1146)) < 0.035


def test_plan_respects_budget_and_tier_order(tmp_path):
    packs = [mk("p%02d" % i, chunk_ids=("c%d" % i,), text="plain text", year=2000)
             for i in range(20)]
    packs[10] = mk("gold", chunk_ids=("g1",), text="plain gold")
    path = tmp_path / "packs.jsonl"
    path.write_text("\n".join(json.dumps(p) for p in packs) + "\n", encoding="utf-8")
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps([{"chunk_id": "g1"}]), encoding="utf-8")
    H.GOLD_ITEMS = gold
    try:
        res = H.plan(path, budget=0.03, safety=0.9)
    finally:
        H.GOLD_ITEMS = H.STATE / "gold" / "p4b_items.json"
    assert res["picked"], "budget must buy at least the gold pack"
    assert res["picked"][0]["pack_id"] == "gold"
    assert res["spent"] <= res["effective_budget"]
    assert res["candidates"] == 20


def test_write_keeps_pack_rows_and_stats(tmp_path):
    packs = [mk("p1", chunk_ids=("c1", "c2")), mk("p2")]
    path = tmp_path / "packs.jsonl"
    path.write_text("\n".join(json.dumps(p) for p in packs) + "\n", encoding="utf-8")
    plan = {"picked": [{"pack_id": "p2", "tier": 1, "score": 1.0, "chunks": 1,
                        "tokens": 1000, "cost": 0.02, "i": 1}],
            "spent": 0.02, "effective_budget": 22.7, "budget": 25.25,
            "tiers": {"sec_mda_fleet": {"packs": 1, "chunks": 1, "est_cost": 0.02}},
            "candidates": 2, "tier_candidates": {}}
    out = tmp_path / "sel.jsonl"
    stats = H.write(plan, path, out)
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert [r["pack_id"] for r in rows] == ["p2"]
    assert stats["packs_written"] == 1
    assert stats["est_cost_per_chunk"] == pytest.approx(0.02)
    assert stats["partial_coverage"] is True
    assert "glm" in H.summarise(stats)


def test_main_dry_writes_stats_only(tmp_path, capsys):
    packs = [mk("p1")]
    path = tmp_path / "packs.jsonl"
    path.write_text(json.dumps(packs[0]) + "\n", encoding="utf-8")
    out = tmp_path / "sel.jsonl"
    stats = tmp_path / "stats.json"
    sys.argv = ["p4c_highvalue", "--packs", str(path), "--out", str(out),
                "--stats", str(stats), "--budget", "5", "--dry"]
    assert H.main() == 0
    assert not out.exists()
    assert json.loads(stats.read_text(encoding="utf-8"))["candidates"] == 1
