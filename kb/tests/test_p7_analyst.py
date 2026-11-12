"""Tests for kb/p7_analyst.py — analyst mode indicators, judgment contract, backtest."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p7_analyst as P  # noqa: E402


# --------------------------------------------------------------------------- fixtures
def make_db(path: Path) -> None:
    con = duckdb.connect(str(path))
    con.execute("""CREATE TABLE document (doc_id VARCHAR PRIMARY KEY, path VARCHAR, publisher_id VARCHAR,
                   doc_type VARCHAR, published_at DATE)""")
    con.execute("""CREATE TABLE chunk (chunk_id VARCHAR PRIMARY KEY, doc_id VARCHAR, body VARCHAR,
                   ord INTEGER)""")
    con.execute("""CREATE TABLE series (series_id VARCHAR PRIMARY KEY, name VARCHAR, unit VARCHAR,
                   definition JSON)""")
    con.execute("""CREATE TABLE observation (obs_id BIGINT, series_id VARCHAR, period_from DATE,
                   period_to DATE, value DOUBLE, unit VARCHAR, doc_id VARCHAR)""")
    con.execute("""CREATE TABLE transaction (txn_id VARCHAR, kind VARCHAR, vessel_id VARCHAR,
                   counterparties JSON, date_from DATE, date_to DATE, terms JSON, status VARCHAR)""")
    con.execute("""CREATE TABLE claim (claim_id VARCHAR PRIMARY KEY, kind VARCHAR, subject_ids VARCHAR[],
                   text_printed VARCHAR, horizon VARCHAR, direction VARCHAR, published_at DATE,
                   doc_id VARCHAR, chunk_id VARCHAR, sids INTEGER[], quote VARCHAR,
                   extractor VARCHAR, confidence DOUBLE)""")
    con.execute("""CREATE VIEW v_rate AS SELECT s.name AS route, o.period_from, o.period_to, o.value,
                   o.unit, d.publisher_id AS publisher, o.doc_id, o.obs_id FROM observation o
                   LEFT JOIN series s ON s.series_id = o.series_id
                   LEFT JOIN document d ON d.doc_id = o.doc_id""")
    con.execute("""CREATE VIEW v_sale AS SELECT t.txn_id, t.vessel_id, t.counterparties, t.date_from,
                   t.date_to, json_extract(t.terms, '$.price') AS price,
                   json_extract_string(t.terms, '$.price_unit') AS price_unit,
                   json_extract_string(t.terms, '$.vessel.name') AS vessel_name, t.status,
                   1 AS mention_count FROM transaction t WHERE t.kind = 'sale'""")
    con.execute("""CREATE VIEW v_newbuilding AS SELECT t.txn_id, t.vessel_id, t.counterparties,
                   t.date_from, t.date_to, json_extract(t.terms, '$.price') AS price,
                   json_extract_string(t.terms, '$.price_unit') AS price_unit,
                   json_extract_string(t.terms, '$.vessel.name') AS vessel_name, t.status,
                   1 AS mention_count FROM transaction t WHERE t.kind = 'newbuild_order'""")
    con.execute("""CREATE VIEW v_demolition AS SELECT t.txn_id, t.vessel_id, t.counterparties,
                   t.date_from, t.date_to, json_extract(t.terms, '$.price') AS price,
                   json_extract_string(t.terms, '$.price_unit') AS price_unit,
                   json_extract_string(t.terms, '$.vessel.name') AS vessel_name, t.status,
                   1 AS mention_count FROM transaction t WHERE t.kind = 'demolition'""")

    con.execute("INSERT INTO document VALUES ('d1','corpus/x.md','broker_a','broker_weekly', DATE '2026-03-06')")
    con.execute("INSERT INTO document VALUES ('d2','corpus/y.md','broker_b','book', DATE '2019-05-01')")
    con.execute("INSERT INTO chunk VALUES ('c1','d2','Old owners buy ships when earnings are terrible.', 1)")
    con.execute("INSERT INTO chunk VALUES ('c2','d2','Asset values peak when orderbook is huge.', 2)")

    con.execute("INSERT INTO series VALUES ('s:cape','Capesize 180k TCE','usd/day','{\"source\":\"baltic\"}')")
    con.execute("INSERT INTO series VALUES ('s:cape2','Capesize 172k TCE','usd/day','{\"source\":\"baltic\"}')")
    # 60 monthly observations 2020-01..2024-12, flat 11,400 usd/day (percentile top)
    obs_id = 101
    for i in range(60):
        y = 2020 + i // 12
        m = 1 + i % 12
        v = 11400.0
        sid = "s:cape" if i % 2 == 0 else "s:cape2"
        con.execute("INSERT INTO observation VALUES (?,?,?,?,?,?,?)",
                    [obs_id, sid, date(y, m, 1), date(y, m, 28), float(v), "usd/day", "d1"])
        obs_id += 1

    # sales: 12 capesize sales, price in millions
    for i in range(12):
        con.execute("INSERT INTO transaction VALUES (?,?,?,?,?,?,?,?)",
                    [f"txn:s{i}", "sale", f"vessel:imo:{i}", "[]", date(2024, 1 + (i % 12), 10),
                     date(2024, 1 + (i % 12), 15),
                     json.dumps({"price": str(20 + i), "price_unit": "usd_m",
                                 "vessel": {"name": "Capesize Star"}}), "active"])
    for i in range(6):
        con.execute("INSERT INTO transaction VALUES (?,?,?,?,?,?,?,?)",
                    [f"txn:n{i}", "newbuild_order", f"vessel:imo:n{i}", "[]",
                     date(2025, 1 + i, 5), date(2025, 1 + i, 9),
                     json.dumps({"price": "60", "price_unit": "usd_m",
                                 "vessel": {"name": "Capesize New"}}), "active"])
    for i in range(4):
        con.execute("INSERT INTO transaction VALUES (?,?,?,?,?,?,?,?)",
                    [f"txn:d{i}", "demolition", f"vessel:imo:d{i}", "[]",
                     date(2025, 10, 1 + i), date(2025, 10, 2 + i),
                     json.dumps({"price": "420", "price_unit": "usd/ldt",
                                 "vessel": {"name": "Capesize Old"}}), "active"])

    con.execute("""INSERT INTO claim VALUES ('c:1','forecast',ARRAY['vessel:imo:1'],'firm','1m','up',
                   DATE '2025-01-15','d1','c1',ARRAY[1],'Capesize rates look firm into Q2.','glm-5.3',0.7)""")
    con.execute("""INSERT INTO claim VALUES ('c:2','forecast',ARRAY['vessel:imo:2'],'weak','1m','down',
                   DATE '2025-02-15','d1','c1',ARRAY[1],'Capesize rates look weak on oversupply.','glm-5.3',0.6)""")
    con.close()


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "kb.duckdb"
    make_db(p)
    return p


@pytest.fixture()
def con(db):
    c = P.connect(db)
    yield c
    c.close()


def _chat(replies):
    seq = list(replies)

    def chat(model, messages, max_tokens=400, **kw):
        text = seq.pop(0) if seq else "NOT_ENOUGH_DATA"
        return text, {"prompt_tokens": 10, "completion_tokens": 10}, 0.0

    return chat


GOOD = ("FACTS: Capesize earnings sit at 11400 usd/day [cite:obs:160].\n"
        "INDICATORS: earnings value 11400 percentile 1.0 [cite:obs:160]; "
        "asset_pe pe_years 6.128 [cite:txn:s11].\n"
        "JUDGMENT: Judgment: late-cycle, so asset values are vulnerable.\n"
        "CONFIDENCE: 0.6\nCOUNTER_ARGUMENT: Demand could surprise on the upside.")


# --------------------------------------------------------------------------- unit
def test_pct_rank_bounds():
    vals = [float(i) for i in range(20)]
    assert P.pct_rank(vals, 19.0) == 1.0
    assert P.pct_rank(vals, 0.0) == 0.05
    assert P.pct_rank(vals[:5], 1.0) is None           # too short
    assert P.pct_rank(vals, None) is None


def test_segment_terms_and_like():
    assert "capesize" in P.segment_terms("capesize")
    sql, params = P._like_any("vessel_name", ["a", "b"])
    assert sql.count("ILIKE") == 2 and params == ["%a%", "%b%"]


def test_earnings_indicator(con):
    ind = P.indicator_earnings(con, "capesize", date(2026, 1, 1))
    assert ind["status"] == "ok"
    assert ind["percentile"] is not None and 0.0 <= ind["percentile"] <= 1.0
    assert ind["cites"] and ind["cites"][0].startswith("obs:")
    assert ind["n"] >= P.MIN_HISTORY


def test_earnings_insufficient(con):
    ind = P.indicator_earnings(con, "lng", date(2026, 1, 1))
    assert ind["status"] == "insufficient" and ind["cites"] == []


def test_asset_pe_and_spreads(con):
    earn = P.indicator_earnings(con, "capesize", date(2026, 1, 1))
    pe = P.indicator_asset_pe(con, "capesize", date(2026, 1, 1), earn)
    assert pe["status"] == "ok" and pe["pe_years"] > 0
    sp = P.indicator_spreads(con, "capesize", date(2026, 1, 1))
    assert sp["status"] == "ok"
    assert sp["newbuild_usd"] == pytest.approx(60e6, rel=1e-6)
    assert sp["secondhand_minus_newbuild_usd"] < 0     # secondhand 25.5m vs newbuild 60m
    assert sp["n_demolition"] == 4


def test_orderbook_scrapping_sentiment(con):
    ob = P.indicator_orderbook(con, "capesize", date(2026, 1, 1))
    assert ob["status"] == "ok" and ob["orders_last_12m"] >= 1
    sc = P.indicator_scrapping(con, "capesize", date(2026, 1, 1))
    assert sc["status"] == "ok" and sc["demolitions_last_12m"] >= 4
    se = P.indicator_sentiment(con, "capesize", date(2025, 4, 1))
    assert se["status"] == "ok" and se["up"] == 1 and se["down"] == 1 and se["net"] == 0.0


def test_indicators_bundle_and_valuation_label(con):
    bundle = P.indicators(con, "capesize", date(2026, 1, 1))
    assert bundle["ok"] >= 4 and bundle["cites"]
    val = P.valuation_label(bundle)
    assert isinstance(val, str) and val


def test_forecast_ledger_scores_publishers(con):
    led = P.forecast_ledger(con, "capesize", date(2026, 1, 1))
    assert led["status"] in ("ok", "thin")
    for p in led["publishers"]:
        assert p["scored"] >= 3 and 0.0 <= p["hit_rate"] <= 1.0


def test_book_rules_use_search(monkeypatch, con):
    def fake_search(query, filters=None, k=20, con=None):
        return {"results": [{"chunk_id": "c1", "path": "corpus/y.md", "snippet": "old owners buy ships"}]}

    monkeypatch.setattr(P.T, "search", fake_search)
    rules = P.book_rules(con, "capesize")
    assert rules and rules[0]["cite"] == "chunk:c1" and rules[0]["topic"] in P.BOOK_QUERIES


def test_parse_analyst_sections_and_channel():
    parsed = P.parse_analyst(GOOD)
    assert parsed["status"] == "ok" and parsed["confidence"] == 0.6
    assert parsed["counter_argument"].startswith("Demand")
    assert [s["part"] for s in parsed["sentences"]].count("judgment") == 1
    assert P.parse_analyst("no data here")["status"] == "malformed"
    assert P.parse_analyst("NOT_ENOUGH_DATA")["status"] == "not_enough_data"


def test_check_analyst_drops_uncited_and_bad_numbers():
    parsed = P.parse_analyst(GOOD)
    parsed["sentences"].append({"part": "facts", "sentence": "Rates hit 99999 usd/day [cite:obs:160]."})
    parsed["sentences"].append({"part": "facts", "sentence": "Uncited claim about rates."})
    parsed, drops = P.check_analyst(parsed, [11400.0, 1.0, 6.128], resolve=lambda h: True)
    assert drops["no_cite"] == 1
    assert drops["number_not_in_evidence"] == 1
    assert len(parsed["sentences"]) == len(P.parse_analyst(GOOD)["sentences"])


def test_check_analyst_unresolved_cite():
    parsed = {"status": "ok", "sentences": [{"part": "facts", "sentence": "X [cite:obs:999]."}],
              "confidence": 0.5, "counter_argument": "c"}
    parsed, drops = P.check_analyst(parsed, [], resolve=lambda h: False)
    assert drops["cite_unresolved"] == 1 and parsed["status"] == "not_in_data"


def test_analyse_happy_path(db, monkeypatch):
    monkeypatch.setattr(P.A, "_resolver", lambda con, cache: (lambda h: True))
    monkeypatch.setattr(P.A, "_chat", _chat([GOOD]))
    rec = P.analyse("Where are capesize rates going?", "capesize", date(2026, 1, 1), db=db)
    assert rec["status"] == "ok"
    assert rec["answer"].startswith("FACTS") is False          # rendered body only
    assert "CONFIDENCE: 0.6" in rec["answer"]
    assert rec["judgment"] and rec["counter_argument"]
    assert rec["cites"] and rec["indicators"]["ok"] >= 4
    assert rec["dropped"]["number_not_in_evidence"] == 0


def test_analyse_escalates_on_malformed(db, monkeypatch):
    monkeypatch.setattr(P.A, "_resolver", lambda con, cache: (lambda h: True))
    monkeypatch.setattr(P.A, "_chat", _chat(["garbage output", GOOD]))
    rec = P.analyse("q", "capesize", date(2026, 1, 1), db=db)
    assert rec["status"] == "ok" and rec["escalated"] is True
    assert rec["model"] == P.A.ESCALATION_MODEL


def test_analyse_not_in_data_when_thin(db):
    rec = P.analyse("q", "lng", date(2026, 1, 1), db=db)
    assert rec["status"] == "not_in_data" and rec["answer"] == P.A.NOT_IN_DATA


def test_call_direction_and_score():
    assert P.call_direction("rates look firm into Q2") == "up"
    assert P.call_direction("oversupply may weaken rates") == "down"
    assert P.call_direction("mixed picture") is None
    rows = [{"call": "up", "realised": 0.2}, {"call": "up", "realised": -0.2},
            {"call": "down", "realised": -0.3}, {"call": None, "realised": 0.1}]
    sc = P.score_calls(rows)
    assert sc == {"n": 3, "hits": 2, "hit_rate": 0.6667}


def test_backtest_dates_and_realised(con):
    dates = P.backtest_dates(con, "capesize", 20)
    assert 15 <= len(dates) <= 20 and all(isinstance(d, date) for d in dates)
    d = dates[0]
    mv = P.realised_move(con, "capesize", d)
    assert mv is None or isinstance(mv, float)


def test_run_backtest_scores(db, monkeypatch):
    monkeypatch.setattr(P.A, "_resolver", lambda con, cache: (lambda h: True))
    monkeypatch.setattr(P.A, "_chat", _chat([GOOD] * 40))
    res = P.run_backtest("capesize", 20, db=db)
    assert res["dates"] >= 15 and "hit_rate" in res
    assert res["n"] <= res["dates"]


def test_main_backtest_writes_json(db, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(P.A, "_resolver", lambda con, cache: (lambda h: True))
    monkeypatch.setattr(P.A, "_chat", _chat([GOOD] * 40))
    out = tmp_path / "bt.json"
    rc = P.main(["--backtest", "--segment", "capesize", "--dates", "20", "--db", str(db),
                 "--out", str(out)])
    assert rc == 0 and out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["segment"] == "capesize" and "rows" in payload


def test_main_requires_question(monkeypatch):
    with pytest.raises(SystemExit):
        P.main(["--segment", "capesize"])
