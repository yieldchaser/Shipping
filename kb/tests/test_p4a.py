"""Unit tests for the P4a retrieval layer (no DB, no network)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import p4a_recall_set as RS  # noqa: E402
import p4a_retrieve as R  # noqa: E402
from p4a_eval import summarise  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "kb/reports/p4a_recall_set.json"


# ---- filter_sql ---------------------------------------------------------------
def test_filter_sql_empty():
    where, params = R.filter_sql(None)
    assert where == "TRUE" and params == []


def test_filter_sql_full():
    where, params = R.filter_sql({"publisher": ["Fearnleys", "SSY"], "doc_type": ["broker_weekly"],
                                  "date_from": "2021-01-01", "date_to": "2021-12-31",
                                  "entity_ids": ["vessel:imo:1"], "public_ok": True})
    assert "d.publisher_id IN (?,?)" in where
    assert "d.doc_type IN (?)" in where
    assert "d.published_at >= ?" in where and "d.published_at <= ?" in where
    assert "list_has_any(c.entity_ids, CAST(? AS VARCHAR[]))" in where
    assert "d.public_ok = ?" in where
    assert params == ["Fearnleys", "SSY", "broker_weekly", "2021-01-01", "2021-12-31",
                      ["vessel:imo:1"], True]


def test_filter_sql_public_false_is_applied():
    where, params = R.filter_sql({"public_ok": False})
    assert where == "d.public_ok = ?" and params == [False]


# ---- RRF fusion ---------------------------------------------------------------
def _fake_retriever(vec_rows: dict[int, list[str]]) -> R.Retriever:
    r = R.Retriever.__new__(R.Retriever)
    r.vec_row_chunks = lambda rows: {vr: vec_rows[vr] for vr in rows if vr in vec_rows}
    return r


def test_fuse_rrf_math_and_order():
    r = _fake_retriever({5: ["c3"], 6: ["c1"]})
    bm = [("c1", 9.0), ("c2", 5.0)]
    dn = [(5, 0.9), (6, 0.8)]
    hits = r.fuse(bm, dn, k=10)
    ids = [h["chunk_id"] for h in hits]
    assert ids[0] == "c1"                      # in both arms -> highest RRF
    assert set(hits[0]) >= {"chunk_id", "rrf", "bm25_rank", "dense_rank"}
    assert hits[0]["rrf"] == pytest.approx(1 / 61 + 1 / 62)
    assert hits[0]["bm25_rank"] == 1 and hits[0]["dense_rank"] == 2
    assert set(ids) == {"c1", "c2", "c3"}


def test_fuse_dense_only_rows_and_k_limit():
    r = _fake_retriever({7: ["x1", "x2"]})
    hits = r.fuse([], [(7, 0.5)], k=1)
    assert len(hits) == 1
    assert hits[0]["bm25_rank"] is None and hits[0]["dense_rank"] == 1


def test_fuse_orders_equal_rrf_by_chunk_id():
    r = _fake_retriever({})
    hits = r.fuse([("b", 1.0)], [])
    assert hits[0]["chunk_id"] == "b"


# ---- deterministic reranker (plan 5.5 step 4 substitute, deviation D5) --------
def test_content_tokens_drops_stopwords_keeps_codes():
    toks = R.content_tokens("What was the TD3C rate for BALTIC WIND on 1-Oct-21?")
    assert "td3c" in toks and "baltic" in toks and "wind" in toks
    assert "1-oct-21" in toks
    assert "the" not in toks and "was" not in toks and "on" not in toks


def test_lex_score_prefers_phrase_and_coverage():
    q = "moisture percent port stock carajas fines"
    qt = R.content_tokens(q)
    qb = set(zip(qt, qt[1:]))
    good = R.lex_score(qt, qb, "Moisture percent for Port Stock Carajas Fines was 8.5.")
    shuffled = R.lex_score(qt, qb, "Fines stock moisture 8.5 percent port carajas.")
    other = R.lex_score(qt, qb, "Moisture percent for Port Stock Tubarao Fines was 7.1.")
    assert good > other > shuffled
    assert R.lex_score(qt, qb, "") == 0


def test_rerank_reorders_fused_head_only():
    r = _fake_retriever({})
    r.con = _FakeCon({"a": "port stock carajas fines moisture percent 8.5",
                      "b": "unrelated commentary about the panamax market",
                      "c": "port stock carajas fines loading"})
    fused = [{"chunk_id": "b", "rrf": 0.03}, {"chunk_id": "c", "rrf": 0.02},
             {"chunk_id": "a", "rrf": 0.01}]
    out = r.rerank("moisture percent port stock carajas fines", fused, keep=2)
    assert [e["chunk_id"] for e in out] == ["a", "c"]
    assert out[0]["rerank_lex"] > out[1]["rerank_lex"]
    assert all("rerank_lex" in e for e in fused)          # scores annotated in place
    # window is capped at RERANK_WINDOW candidates
    assert len(r.rerank("anything", fused, keep=10)) == 3


def test_rerank_respects_window():
    r = _fake_retriever({})
    from unittest import mock
    fused = [{"chunk_id": f"c{i}", "rrf": 1.0 / (i + 1)} for i in range(R.RERANK_WINDOW + 5)]
    r.con = mock.MagicMock()
    r.con.execute.return_value.fetchall.return_value = []
    r.rerank("query", fused, keep=20)
    ids = r.con.execute.call_args[0][1]
    assert len(ids) == R.RERANK_WINDOW


class _FakeCon:
    def __init__(self, texts: dict[str, str]):
        self.texts = texts

    def execute(self, sql, ids):
        rows = [(cid, "", self.texts.get(cid, "")) for cid in ids]
        return _Rows(rows)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


# ---- query cache / normalisation ---------------------------------------------
def test_embed_query_normalises_and_caches(tmp_path):
    r = _fake_retriever({})
    r.qcache = {}
    r.cache_path = tmp_path / "q.json"
    r._embed_remote = lambda q: np.array([3.0, 4.0], dtype=np.float32)
    v1 = r.embed_query("hello")
    assert np.allclose(np.linalg.norm(v1), 1.0) and np.allclose(v1, [0.6, 0.8])
    r._embed_remote = lambda q: pytest.fail("cache miss")
    v2 = r.embed_query("hello")
    assert np.allclose(v1, v2)
    assert json.loads(r.cache_path.read_text())  # persisted


# ---- dense arm ----------------------------------------------------------------
def test_dense_topk_and_filters(monkeypatch):
    r = _fake_retriever({})
    rows = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7], [0.2, 0.1]], dtype=np.float16)
    r.mm = rows
    monkeypatch.setattr(r, "eligible_rows", lambda filters, use_vec_rows: None)
    hits = r.dense(np.array([1.0, 0.0], dtype=np.float32), None, k=2)
    assert [vr for vr, _ in hits] == [0, 2]           # exact match then 45-degree
    assert hits[0][1] == pytest.approx(1.0)
    # a filter that keeps only rows 1 and 3 tightens the candidate set
    monkeypatch.setattr(r, "eligible_rows", lambda filters, use_vec_rows: np.array([1, 3]))
    hits = r.dense(np.array([1.0, 0.0], dtype=np.float32), {"doc_type": ["book"]}, k=2)
    assert [vr for vr, _ in hits] == [3, 1]
    # empty eligible set -> no hits, no crash
    monkeypatch.setattr(r, "eligible_rows", lambda filters, use_vec_rows: np.array([], dtype=np.int64))
    assert r.dense(np.array([1.0, 0.0], dtype=np.float32), {"doc_type": ["book"]}) == []


# ---- recall-set question rendering --------------------------------------------
def test_phrase_expands_internal_tokens():
    assert RS.phrase("change_wow") == "change week-on-week"
    assert RS.phrase("iopi65_eq_usd_dmt") == "IOPi65 Eq USD DMT"
    assert RS.phrase("m_minus_1") == "month minus one"
    assert RS.phrase("") == ""


def test_humanise_keeps_discriminating_detail():
    q = RS.humanise("stem::iopi65_eq_usd_dmt | 1-Oct-21\x1fvector_estimate",
                    {"measurement": "iopi65_eq_usd_dmt",
                     "entity_signature": "1-Oct-21\x1fvector_estimate"})
    assert "IOPi65 Eq USD DMT" in q
    assert "1-Oct-21" in q and "vector estimate" in q
    # unit-only signature is not silently dropped
    q2 = RS.humanise("stem::change_wow | USD/mt",
                     {"measurement": "change_wow", "entity_signature": "USD/mt"})
    assert "USD/mt" in q2


def test_heading_tail_split():
    assert RS.heading_tail("Market > Iron Ore > Maritime Stock Data") == "Maritime Stock Data"
    assert RS.heading_tail("Freight / C5") == "C5"
    assert RS.heading_tail("") == ""


def test_month_window_covers_calendar_month():
    from datetime import date
    assert RS.month_window(date(2024, 12, 18)) == ("2024-12-01", "2024-12-31")
    assert RS.month_window(date(2024, 2, 29)) == ("2024-02-01", "2024-02-29")



def _rec(qid, stratum, hit_at, arms=(1, 1), rank=1, secs=1.0):
    hit = bool(hit_at)
    return {"qid": qid, "stratum": stratum, "first_gold_rank": rank if hit else None,
            "hit": hit, "hit_at": {str(k): bool(hit and rank <= k) for k in (5, 10, 20)},
            "arms": {"bm25": arms[0], "dense": arms[1], "both": min(arms)},
            "timing": {"total_s": secs}}


def test_summarise_overall_and_strata():
    recs = [_rec("a1", "vessel_entity", 1), _rec("a2", "vessel_entity", 0, arms=(0, 0)),
            _rec("b1", "section_lookup", 1, arms=(0, 1)), _rec("b2", "section_lookup", 1, arms=(1, 0), rank=8)]
    out = summarise(recs, (5, 10, 20))
    ov = out["overall"]
    assert ov["n"] == 4 and ov["hit_count"] == 3
    assert ov["hit_at_20"] == 0.75
    assert ov["recall"]["at_10"] == 0.75
    assert ov["gold_only_dense"] == 1 and ov["gold_only_bm25"] == 1 and ov["gold_both_arms"] == 1
    assert out["by_stratum"]["vessel_entity"]["recall"]["at_20"] == 0.5
    assert out["by_stratum"]["section_lookup"]["misses"] == []
    assert out["strata_counts"] == {"vessel_entity": 2, "section_lookup": 2}


def test_summarise_handles_empty():
    out = summarise([], (20,))
    assert out["overall"]["n"] == 0 and out["overall"]["hit_at_20"] == 0.0
    assert out["by_stratum"] == {}


# ---- gold set integrity -------------------------------------------------------
@pytest.mark.skipif(not GOLD.exists(), reason="gold set not built yet")
def test_gold_set_shape():
    data = json.loads(GOLD.read_text(encoding="utf-8"))
    assert data["phase"] == "P4a" and isinstance(data["sample_seed"], int)
    qs = data["queries"]
    assert len(qs) == 200
    assert len({q["qid"] for q in qs}) == len(qs)
    assert set(data["counts"]) == {"vessel_entity", "company_entity", "numeric_series", "section_lookup"}
    valid = {"publisher", "doc_type", "date_from", "date_to", "entity_ids", "public_ok"}
    for q in qs:
        assert q["gold"], q["qid"]
        assert set(q["filters"]) <= valid
        assert all(g["chunk_id"] and g["path"] for g in q["gold"])
        assert len(q["query"]) > 15
    assert sum(1 for q in qs if q["filters"]) > 100


@pytest.mark.skipif(not GOLD.exists(), reason="gold set not built yet")
def test_gold_paths_exist():
    data = json.loads(GOLD.read_text(encoding="utf-8"))
    for q in data["queries"][:10]:
        assert (ROOT / q["gold"][0]["path"]).exists(), q["gold"][0]["path"]
