"""Offline tests for the P7 tools and answer contract (no network, no real DB)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ask as A  # noqa: E402
import tools as T  # noqa: E402


def make_db(path: Path) -> Path:
    con = duckdb.connect(str(path))
    con.execute("""CREATE TABLE document (doc_id VARCHAR PRIMARY KEY, path VARCHAR, publisher_id VARCHAR,
                   doc_type VARCHAR, published_at DATE, title VARCHAR)""")
    con.execute("""CREATE TABLE chunk (chunk_id VARCHAR PRIMARY KEY, doc_id VARCHAR, section_id VARCHAR,
                   ord INTEGER, body VARCHAR)""")
    con.execute("""CREATE TABLE sentence (chunk_id VARCHAR, sid INTEGER, start_char INTEGER, end_char INTEGER)""")
    con.execute("""CREATE TABLE entity (entity_id VARCHAR PRIMARY KEY, type VARCHAR, canonical_name VARCHAR,
                   attrs JSON, status VARCHAR, created_by VARCHAR)""")
    con.execute("""CREATE TABLE edge (edge_id VARCHAR PRIMARY KEY, "type" VARCHAR, src VARCHAR, dst VARCHAR,
                   valid_from DATE, valid_to DATE, published_at DATE, doc_id VARCHAR, chunk_id VARCHAR,
                   "quote" VARCHAR, status VARCHAR)""")
    con.execute("""CREATE TABLE event (event_id VARCHAR PRIMARY KEY, "type" VARCHAR, summary VARCHAR,
                   occurred_from DATE, occurred_to DATE, published_at DATE, doc_id VARCHAR, chunk_id VARCHAR,
                   "quote" VARCHAR)""")
    con.execute("""CREATE TABLE claim (claim_id VARCHAR PRIMARY KEY, kind VARCHAR, subject_ids VARCHAR[],
                   text_printed VARCHAR, horizon VARCHAR, direction VARCHAR, published_at DATE,
                   doc_id VARCHAR, chunk_id VARCHAR, "quote" VARCHAR)""")
    con.execute("""CREATE TABLE series (series_id VARCHAR PRIMARY KEY, name VARCHAR, unit VARCHAR,
                   currency VARCHAR, basis VARCHAR, frequency VARCHAR)""")
    con.execute("""CREATE TABLE observation (obs_id BIGINT PRIMARY KEY, series_id VARCHAR, period_from DATE,
                   period_to DATE, value DOUBLE, unit VARCHAR, raw_cell VARCHAR, doc_id VARCHAR,
                   published_at DATE)""")
    con.execute("""CREATE TABLE transaction (txn_id VARCHAR PRIMARY KEY, kind VARCHAR, vessel_id VARCHAR,
                   date_from DATE, date_to DATE, terms JSON, status VARCHAR)""")
    con.execute("""CREATE VIEW v_series AS SELECT s.series_id, s.name, s.unit, count(o.obs_id) AS n
                   FROM series s LEFT JOIN observation o USING (series_id) GROUP BY 1,2,3""")
    con.execute("""CREATE VIEW v_observation AS SELECT obs_id, series_id, value, unit, period_to
                   FROM observation""")
    con.execute("""CREATE VIEW v_gaps AS SELECT 'rates'::VARCHAR AS scope, 'TD27X'::VARCHAR AS key,
                   DATE '2025-01-01' AS gap_from, DATE '2025-12-31' AS gap_to,
                   'no series mentions route code TD27X'::VARCHAR AS reason, 'p2_gaps'::VARCHAR AS source""")

    con.execute("INSERT INTO document VALUES ('d1','md/2026/broker_week_1.md','Banchero Costa','broker_weekly','2026-03-06','Weekly')")
    con.execute("INSERT INTO document VALUES ('d2','md/2026/broker_week_2.md','Banchero Costa','broker_weekly','2026-04-10','Weekly')")
    con.execute("""INSERT INTO chunk VALUES ('c1','d1','s1',1,'Capesize spot averaged USD 24,500/day in March on the Brazil-China run.')""")
    con.execute("""INSERT INTO chunk VALUES ('c2','d2','s2',1,'VLCC rates for the Middle East-China route eased to USD 51,000/day.')""")
    con.execute("INSERT INTO sentence VALUES ('c1',1,0,30),('c1',2,31,80),('c2',1,0,40)")
    con.execute("INSERT INTO entity VALUES ('vessel:imo:1','vessel','ROSCO POPLAR','{}','confirmed','p3_seed')")
    con.execute("INSERT INTO entity VALUES ('company:1','company','Banchero Costa','{}','confirmed','p3_seed')")
    con.execute("""INSERT INTO edge VALUES ('e1','OPERATES','company:1','vessel:imo:1',DATE '2026-01-01',NULL,
                   DATE '2026-03-06','d1','c1','operated by Banchero Costa','active')""")
    con.execute("""INSERT INTO event VALUES ('ev1','sale','Vessel sold for USD 17.6m.',DATE '2024-08-26',NULL,
                   DATE '2024-08-27','d1','c1','Sold for USD 17.6m.')""")
    con.execute("""INSERT INTO claim VALUES ('c:1','forecast',['vessel:imo:1'],'Rates to stay firm',
                   '2026-Q2','up',DATE '2026-03-06','d1','c1','Rates to stay firm')""")
    con.execute("INSERT INTO series VALUES ('s:cape','capesize_spot::rate | Capesize','$/day','USD','spot','daily')")
    con.execute("INSERT INTO observation VALUES (101,'s:cape',DATE '2026-03-01',DATE '2026-03-07',24500.0,'$/day','24,500','d1',DATE '2026-03-06')")
    con.execute("INSERT INTO transaction VALUES ('txn:1','sale','vessel:imo:1',DATE '2024-08-26',NULL,'{}','confirmed')")
    con.close()
    return path


@pytest.fixture()
def db(tmp_path):
    return make_db(tmp_path / "kb.duckdb")


@pytest.fixture()
def con(db):
    c = T.connect(db)
    yield c
    c.close()


# ------------------------------------------------------------------- sql
def test_sql_select_on_view(con):
    out = T.sql("SELECT series_id, n FROM v_series", con=con)
    assert out["columns"] == ["series_id", "n"]
    assert out["rows"] == [["s:cape", 1]]


def test_sql_allows_with_and_caps_rows(con):
    out = T.sql("WITH x AS (SELECT obs_id FROM v_observation) SELECT * FROM x", con=con)
    assert len(out["rows"]) == 1


@pytest.mark.parametrize("bad", [
    "DELETE FROM v_series",
    "SELECT * FROM chunk",
    "SELECT * FROM v_series; DROP TABLE chunk",
    "SELECT * FROM v_series JOIN chunk USING (series_id)",
    "",
    "PRAGMA database_list",
])
def test_sql_rejects_non_views_and_writes(con, bad):
    with pytest.raises(T.ToolError):
        T.sql(bad, con=con)


def test_sql_timeout_guard(monkeypatch, con):
    import threading

    class Slow:
        description = []

        def execute(self, *a, **k):
            raise RuntimeError("interrupted")

    with pytest.raises(T.ToolError):
        T.sql("SELECT * FROM v_series", con=Slow(), timeout_s=0.01)


# ---------------------------------------------------------------- search
def test_search_finds_chunk_and_metadata(con):
    out = T.search("capesize 24,500", con=con)
    assert out["results"], "fallback lexical search must find c1"
    hit = out["results"][0]
    assert hit["chunk_id"] == "c1"
    assert hit["path"].endswith("broker_week_1.md")
    assert hit["publisher"] == "Banchero Costa"
    assert hit["published_at"] == "2026-03-06"


def test_search_filter_excludes_after_cutoff(con):
    out = T.search("VLCC", filters={"published_to": "2026-03-31"}, con=con)
    assert all(r["published_at"] <= "2026-03-31" for r in out["results"])


def test_filter_sql_rejects_unknown_key():
    with pytest.raises(T.ToolError):
        T.filter_sql({"secret": 1})


# ----------------------------------------------------------------- graph
def test_graph_hops_and_window(con):
    one = T.graph("company:1", hops=1, con=con)
    ids = {n["entity_id"] for n in one["nodes"]}
    assert ids == {"company:1", "vessel:imo:1"}
    assert one["edges"][0]["type"] == "OPERATES"
    none = T.graph("company:1", window=("2025-01-01", "2025-12-31"), con=con)
    node_ids = {n["entity_id"] for n in none["nodes"]}
    assert node_ids == {"company:1"}


def test_graph_hops_clamped(con):
    out = T.graph("company:1", hops=9, con=con)
    assert out["hops"] == T.MAX_HOPS


def test_ppr_fallback_ranks_neighbours(con):
    out = T.ppr(["vessel:imo:1"], con=con)
    ranked = [n["entity_id"] for n in out["nodes"]]
    assert ranked[0] == "vessel:imo:1"
    assert "company:1" in ranked


# --------------------------------------------------------------- summary
def test_summary_reads_p6_index(tmp_path, monkeypatch):
    idx = {"capesize|2026-03": {"segment": "capesize", "grain": "month", "period": "2026-03",
                                "summary": "Capesize firmed.", "cites": [{"kind": "obs", "ref": "101"}]},
           "capesize|2026": {"segment": "capesize", "grain": "year", "period": "2026",
                             "summary": "Year view.", "cites": []},
           "vlcc|2026-04": {"segment": "vlcc", "grain": "month", "period": "2026-04",
                            "summary": "VLCC eased.", "cites": []}}
    monkeypatch.setattr(T, "P6_INDEX", tmp_path / "index.json")
    (tmp_path / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    out = T.summary(segment="capesize")
    assert len(out["nodes"]) == 2
    assert out["nodes"][0]["grain"] == "month"
    assert out["nodes"][1]["grain"] == "year"
    assert out["nodes"][0]["cites"] == ["obs:101"]
    month = T.summary(grain="month")
    assert [n["segment"] for n in month["nodes"]] == ["vlcc", "capesize"]


def test_summary_missing_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(T, "P6_INDEX", tmp_path / "nope.json")
    with pytest.raises(T.ToolError):
        T.summary()


# ------------------------------------------------------------------ gaps
def test_gaps_and_window(con):
    out = T.gaps(scope="rates", con=con)
    assert len(out["gaps"]) == 1 and out["gaps"][0]["key"] == "TD27X"
    assert T.gaps(scope="rates", window=("2026-06-01", "2026-12-31"), con=con)["gaps"] == []
    assert T.gaps(key="td27x", window=("2025-06-01", "2025-06-30"), con=con)["gaps"]


# ------------------------------------------------------------------ cite
def test_cite_each_kind(con):
    obs = T.cite("obs:101", con=con)
    assert obs["quote"].startswith("24,500") and obs["locator"]["series_id"] == "s:cape"
    chunk = T.cite("chunk:c1", con=con)
    assert chunk["path"].endswith("broker_week_1.md") and "Capesize" in chunk["quote"]
    event = T.cite("event:ev1", con=con)
    assert event["locator"]["type"] == "sale" and "17.6" in event["quote"]
    claim = T.cite("claim:c:1", con=con)
    assert claim["locator"]["direction"] == "up"
    txn = T.cite("txn:txn:1", con=con)
    assert txn["locator"]["vessel_id"] == "vessel:imo:1"


def test_cite_rejects_bad_handle(con):
    for bad in ("c1", "nope:1", "obs:"):
        with pytest.raises(T.ToolError):
            T.cite(bad, con=con)
    with pytest.raises(T.ToolError):
        T.cite("obs:999", con=con)


def test_dispatch_unknown_tool():
    with pytest.raises(T.ToolError):
        T.dispatch("nope", {})


def test_dispatch_routes(con):
    assert T.dispatch("cite", {"handle": "obs:101"}, con=con)["kind"] == "obs"
    assert T.dispatch("gaps", {"scope": "rates"}, con=con)["gaps"]
    assert T.dispatch("sql", {"query": "SELECT 1 AS x FROM v_series"}, con=con)["rows"] == [[1]]


# ------------------------------------------------------- ask: contract
def test_as_of_detection():
    assert A.as_of_of("What did we know as known on 2022-06-13 about capesize?") == "2022-06-13"
    assert A.as_of_of("As of 2026-01-05, what was TD3C?") == "2026-01-05"
    assert A.as_of_of("What was the capesize rate?") is None


def test_numbers_and_support():
    assert A.numbers_supported("USD 24,500/day", [24500.0])[0] is True
    ok, missing = A.numbers_supported("USD 24,500/day and 51000", [24500.0])
    assert ok is False and missing == [51000.0]
    assert A.number_ok(24500.0, [24501.0]) is True          # 0.005% relative
    assert A.number_ok(12.3, [12.31]) is True               # small-value absolute tolerance
    assert A.number_ok(12.3, [12.5]) is False


def test_an_unreadable_number_never_counts_as_supported():
    """Defect 29.

    `numbers_in` used `float()` raw, so a 400-digit literal became `inf`. The old
    `numbers_supported` then filtered with `not number_ok(inf, have)`, and `number_ok(inf, ...)` was
    True for *any* non-empty `have` (`abs(inf - h) == inf <= max(1e-9, 0.005 * inf, ...) == inf`), so
    the sentence was certified on a number nobody could read. The mirror case matters too: with the
    unreadable token simply dropped, the sentence would pass because it appears to assert nothing.
    Non-vacuity first: a real supported number still passes, a real unsupported one still fails.
    """
    assert A.numbers_supported("USD 24,500/day", [24500.0]) == (True, [])
    assert A.numbers_supported("Rates hit USD 99,999/day", [24500.0])[0] is False

    big = "1" + "0" * 400
    assert A.numbers_in("we saw " + big + " tonnes") == []
    assert A.numbers_claimed("we saw " + big + " tonnes") == [None]
    # the value side: unreadable literal in the answer text is not supportable...
    ok, missing = A.numbers_supported("we saw " + big + " tonnes", [24500.0])
    assert ok is False and missing == [None]
    # ...and not supportable by an unreadable `have` member either
    assert A.numbers_supported("we saw " + big + " tonnes", [24500.0])[0] is False
    for bad in (True, False, float("inf"), float("-inf"), float("nan"), "24500", [24500], {}):
        assert A.number_ok(bad, [24500.0]) is False, bad
        assert A.number_ok(None, [24500.0]) is False
    # the `have` side never carries an unreadable member into the tolerance arithmetic
    assert A.result_numbers([{"result": {"t": float("inf"), "n": float("nan"), "ok": 24500}}]) \
        == [24500.0]
    assert A.result_numbers([{"result": {"b": True, "s": "1" + "0" * 400}}]) == []
    # non-vacuity on the good path
    assert A.number_ok(24500.0, [24500.0]) is True
    assert A.result_numbers([{"result": {"n": 3, "price": 24500}}]) == [3.0, 24500.0]


def test_parse_answer_and_not_in_data():
    parsed = A.parse_answer("ANSWER: Capesize was USD 24,500/day [cite:obs:101].\n"
                            "- Brazil-China run firmed [cite:obs:101].")
    assert parsed["status"] == "ok"
    assert parsed["answer"].startswith("Capesize was")
    assert parsed["cites"] == ["obs:101", "obs:101"]
    assert A.parse_answer("NOT_IN_DATA")["status"] == "not_in_data"
    assert A.parse_answer("")["status"] == "empty"


def test_contract_filter_drops_uncited_and_unsupported(con):
    resolve = A._resolver(con, {})
    parsed = {"sentences": [
        {"sentence": "Capesize was USD 24,500/day.", "cites": ["obs:101"]},
        {"sentence": "No citation here.", "cites": []},
        {"sentence": "Rates hit USD 99,999/day.", "cites": ["obs:101"]},
        {"sentence": "Bogus handle.", "cites": ["obs:999"]},
    ]}
    final, dropped = A.contract_filter(parsed, [24500.0], resolve)
    assert final["status"] == "ok"
    assert dropped["no_cite"] == 1 and dropped["number_not_in_results"] == 1
    assert dropped["cite_unresolved"] == 1
    assert "24,500" in final["answer"] and "99,999" not in final["answer"]
    assert final["sentences"][0]["cites"][0]["kind"] == "obs"


def test_contract_filter_all_dropped_is_not_in_data(con):
    final, _drops = A.contract_filter({"sentences": [{"sentence": "x 5.", "cites": []}]},
                                      [5.0], A._resolver(con, {}))
    assert final["status"] == "not_in_data" and final["answer"] == A.NOT_IN_DATA


# ------------------------------------------------------- ask: pipeline
def _fake_chat(replies):
    calls = {"n": 0}

    def chat(model, messages, max_tokens=400, **kw):
        i = min(calls["n"], len(replies) - 1)
        calls["n"] += 1
        return replies[i], {"prompt_tokens": 10, "completion_tokens": 10}, 0.0

    return chat, calls


def test_answer_question_happy_path(tmp_path, db, monkeypatch):
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")
    chat, calls = _fake_chat([
        "[]",                                                   # planner
        "ANSWER: Capesize spot averaged USD 24,500/day [cite:obs:101].",  # composer
    ])
    rec = A.answer_question("What was the capesize spot rate in March 2026?", con=T.connect(db), chat=chat)
    assert rec["status"] == "ok", rec
    assert "24,500" in rec["answer"]
    assert rec["cites"] and rec["cites"][0]["kind"] == "obs"
    assert rec["escalated"] is False
    assert rec["tool_calls"][0]["tool"] == "search"


def test_answer_question_not_in_data(tmp_path, db, monkeypatch):
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")
    chat, _ = _fake_chat(["[]", "NOT_IN_DATA"])
    rec = A.answer_question("What was TD27X on 2025-05-14?", con=T.connect(db), chat=chat)
    assert rec["status"] == "not_in_data"
    assert rec["answer"] == A.NOT_IN_DATA


def test_answer_question_escalates_then_succeeds(tmp_path, db, monkeypatch):
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")
    chat, calls = _fake_chat([
        "[]",                                          # planner
        "ANSWER: Capesize hit USD 77,777/day [cite:obs:101].",   # bad number
        "ANSWER: Capesize averaged USD 24,500/day [cite:obs:101].",  # escalation fixes it
    ])
    rec = A.answer_question("Capesize rate?", con=T.connect(db), chat=chat)
    assert rec["escalated"] is True
    assert rec["model"] == A.ESCALATION_MODEL
    assert "24,500" in rec["answer"]
    assert calls["n"] == 3


def test_answer_question_plan_calls_used_and_clamped(tmp_path, db, monkeypatch):
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")
    plan = json.dumps([{"tool": "cite", "args": {"handle": "obs:101"}},
                       {"tool": "gaps", "args": {"scope": "rates"}},
                       {"tool": "sql", "args": {"query": "SELECT * FROM v_series"}}])
    chat, _ = _fake_chat([plan, "NOT_IN_DATA"])
    rec = A.answer_question("Capesize?", con=T.connect(db), chat=chat, escalate=False)
    names = [c["tool"] for c in rec["tool_calls"]]
    assert names[0] == "search"
    assert names[1:] == ["cite", "gaps"]      # third planner call dropped by MAX_TOOL_CALLS


def test_answer_question_as_of_filters_search(tmp_path, db, monkeypatch):
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")
    seen = {}

    def fake_search(query, filters=None, k=20, con=None):
        seen["filters"] = filters
        return {"query": query, "results": []}

    monkeypatch.setattr(T, "search", fake_search)
    chat, _ = _fake_chat(["[]", "NOT_IN_DATA"])
    A.answer_question("As known on 2026-03-31, what was the VLCC rate?", con=T.connect(db), chat=chat)
    assert seen["filters"] == {"published_to": "2026-03-31"}


def test_answer_question_model_error_is_recorded(tmp_path, db, monkeypatch):
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")

    def boom(model, messages, max_tokens=400, **kw):
        if len(messages) > 0 and messages[0]["content"] == A.PLANNER_SYSTEM:
            raise RuntimeError("planner down")
        raise RuntimeError("composer down")

    rec = A.answer_question("Capesize?", con=T.connect(db), chat=boom, escalate=False)
    assert rec["status"] == "model_error"
    assert rec["answer"] == A.NOT_IN_DATA


def test_answer_question_no_citation_degrades(tmp_path, db, monkeypatch):
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")
    chat, _ = _fake_chat(["[]", "ANSWER: Capesize averaged USD 24,500/day.", "ANSWER: still uncited."])
    rec = A.answer_question("Capesize?", con=T.connect(db), chat=chat)
    assert rec["status"] == "not_in_data"
    assert rec["escalated"] is True


def test_trim_results_shrinks_lists():
    results = [{"tool": "search", "result": {"results": [{"x": i} for i in range(50)]}}]
    trimmed = A._trim_results(results, budget=200)
    assert len(trimmed[0]["result"]["results"]) <= 5


def test_cli_main_json(tmp_path, db, monkeypatch, capsys):
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")
    chat, _ = _fake_chat(["[]", "ANSWER: Capesize averaged USD 24,500/day [cite:obs:101]."])
    monkeypatch.setattr(A, "_chat", chat)
    rc = A.main(["--json", "--db", str(db), "What was the capesize rate?"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "ok"


# ------------------------------------------------------- ask: ledger booking (Defect 15b)
def _scratch_ledger(tmp_path, monkeypatch):
    import runner as R
    path = tmp_path / "ledger.sqlite"
    monkeypatch.setattr(A, "LEDGER", path)
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")
    return path, R


def _rows(path, sql="SELECT pass, model, status, in_tok, cached_tok, out_tok, cost_usd FROM jobs"):
    import sqlite3
    con = sqlite3.connect(str(path))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_chat_books_its_spend_into_the_jobs_ledger(tmp_path, monkeypatch):
    """Defect 15b: the JSONL call log alone left P7 spend invisible to runner.spent()."""
    import runner as R
    path, _ = _scratch_ledger(tmp_path, monkeypatch)

    def fake_llm_chat(model, messages, **kw):
        return {"choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0}}

    monkeypatch.setattr(A.llm_runner, "chat", fake_llm_chat)
    text, usage, cost = A._chat(A.DEFAULT_MODEL, [{"role": "user", "content": "x"}])
    assert text == "hi"
    expected = R.price_table()[A.DEFAULT_MODEL]["in"]
    assert cost == pytest.approx(expected), "priced by runner.cost_usd, not a literal 0.0"
    rows = _rows(path)
    assert len(rows) == 1
    assert rows[0][0] == "p7_ask" and rows[0][1] == A.DEFAULT_MODEL and rows[0][2] == "ok"
    assert rows[0][6] == pytest.approx(expected)


def test_booked_p7_spend_is_visible_to_runner_spent(tmp_path, monkeypatch):
    path, R = _scratch_ledger(tmp_path, monkeypatch)
    monkeypatch.setattr(A.llm_runner, "chat",
                        lambda *a, **k: {"choices": [{"message": {"content": "x"}}],
                                         "usage": {"prompt_tokens": 500_000,
                                                   "completion_tokens": 100_000}})
    A._chat(A.DEFAULT_MODEL, [{"role": "user", "content": "x"}])
    real = R.LEDGER
    monkeypatch.setattr(R, "LEDGER", path)
    try:
        spent = R.spent(passes=[A.PASS_NAME])
    finally:
        monkeypatch.setattr(R, "LEDGER", real)
    pt = R.price_table()[A.DEFAULT_MODEL]
    assert spent == pytest.approx((500_000 * pt["in"] + 100_000 * pt["out"]) / 1e6)
    assert spent > 0.0


def test_failed_chat_is_booked_as_an_error_row(tmp_path, monkeypatch):
    path, _ = _scratch_ledger(tmp_path, monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(A.llm_runner, "chat", boom)
    with pytest.raises(RuntimeError):
        A._chat(A.DEFAULT_MODEL, [{"role": "user", "content": "x"}])
    rows = _rows(path)
    assert len(rows) == 1 and rows[0][2] == "error"


def test_ledger_booking_failure_never_breaks_an_answer(tmp_path, monkeypatch):
    """Best-effort by design: an unwritable ledger must not take the answer engine down."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(A, "LEDGER", blocker / "ledger.sqlite")  # mkdir/sqlite must fail here
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")
    out = A._book(A.DEFAULT_MODEL, {"prompt_tokens": 10}, 0.001)
    assert out == pytest.approx(0.001), "the caller still gets its cost back"


# ------------------------------------------------- ask: record cost is every paid call (Defect 19)
def test_answer_record_cost_includes_the_planner_call(tmp_path, db, monkeypatch):
    """The planner is billed too; a record that counts only the composer understates the run."""
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")

    def chat(model, messages, max_tokens=400, **kw):
        if "Plan tool calls" in messages[-1]["content"]:
            return "[]", {"prompt_tokens": 10}, 0.003          # planner
        return ("ANSWER: Capesize averaged USD 24,500/day [cite:obs:101].",
                {"prompt_tokens": 10}, 0.007)                  # composer
    rec = A.answer_question("Capesize rate?", con=T.connect(db), chat=chat, escalate=False)
    assert rec["status"] == "ok"
    assert rec["cost_usd"] == pytest.approx(0.010), "0.003 planner + 0.007 composer"


def test_answer_record_cost_accumulates_the_escalation(tmp_path, db, monkeypatch):
    """A successful escalation used to *replace* the first-pass cost instead of adding to it."""
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")

    def chat(model, messages, max_tokens=400, **kw):
        if "Plan tool calls" in messages[-1]["content"]:
            return "[]", {}, 0.001
        if model == A.ESCALATION_MODEL:
            return "ANSWER: Capesize averaged USD 24,500/day [cite:obs:101].", {}, 0.050
        return "ANSWER: Capesize hit USD 77,777/day [cite:obs:101].", {}, 0.004
    rec = A.answer_question("Capesize rate?", con=T.connect(db), chat=chat)
    assert rec["escalated"] is True and rec["model"] == A.ESCALATION_MODEL
    assert rec["cost_usd"] == pytest.approx(0.055), "0.001 + 0.004 + 0.050"


def test_answer_record_cost_keeps_the_planner_when_the_composer_fails(tmp_path, db, monkeypatch):
    monkeypatch.setattr(A, "CALL_LOG", tmp_path / "calls.jsonl")

    def chat(model, messages, max_tokens=400, **kw):
        if "Plan tool calls" in messages[-1]["content"]:
            return "[]", {}, 0.002
        raise RuntimeError("composer down")
    rec = A.answer_question("Capesize rate?", con=T.connect(db), chat=chat, escalate=False)
    assert rec["status"] == "model_error"
    assert rec["cost_usd"] == pytest.approx(0.002), "the planner was still paid for"


def test_chat_books_an_error_row_when_llm_runner_chat_returns_garbage(tmp_path, monkeypatch):
    path, _ = _scratch_ledger(tmp_path, monkeypatch)
    monkeypatch.setattr(A.llm_runner, "chat", lambda *a, **k: {})
    text, usage, cost = A._chat(A.DEFAULT_MODEL, [{"role": "user", "content": "x"}])
    # No usage block came back, so nothing priced the call: UNMEASURED (`None`), not a fake `0.0`
    # (Defect 17/21 class). A genuinely free route reports its explicit `0.0` tariff instead.
    assert text == "" and usage == {} and cost is None
    assert _rows(path)[0][2] == "ok"
    assert _rows(path)[0][6] is None, "the NULL row keeps the unmeasured state at rest"


def test_unmeasured_chat_spend_stays_null_and_is_not_a_measured_zero(tmp_path, monkeypatch):
    """`None` cost must survive the round-trip through the ledger as SQL NULL."""
    path, R = _scratch_ledger(tmp_path, monkeypatch)
    monkeypatch.setattr(A.llm_runner, "chat",
                        lambda *a, **k: {"choices": [{"message": {"content": "x"}}]})
    A._chat(A.DEFAULT_MODEL, [{"role": "user", "content": "x"}])
    real = R.LEDGER
    monkeypatch.setattr(R, "LEDGER", path)
    try:
        total, rows = R.spent_rows(passes=[A.PASS_NAME])
    finally:
        monkeypatch.setattr(R, "LEDGER", real)
    assert rows == 1 and total is None, "one unmeasured row, not $0.00"
