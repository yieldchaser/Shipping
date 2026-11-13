"""Tests for kb/p4c_daemon.py - quota accounting, shard loop and the --glean wiring (no calls)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import p4c_daemon as D  # noqa: E402
import p4c_glean as GL  # noqa: E402


def packs_file(tmp_path, n=2) -> Path:
    path = tmp_path / "packs.jsonl"
    rows = [{"key": f"k{i}", "chunk_ids": [f"c{i}"], "doc_id": "d1"} for i in range(n)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_total_packs_counts_non_blank_lines(tmp_path):
    path = tmp_path / "p.jsonl"
    path.write_text('{"a":1}\n\n{"a":2}\n', encoding="utf-8")
    assert D.total_packs(path) == 2


def test_run_stops_when_every_pack_has_a_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(D.PR, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(D, "scope_done", lambda pass_name, model, packs_path: 2)
    monkeypatch.setattr(D.PR, "run_packs", lambda *a, **k: pytest.fail("should not run"))
    assert D.run("p", "m", packs_file(tmp_path), 10, 5, 200, 5.0) == 0


def test_run_forwards_job_maker_and_counts_errors(tmp_path, monkeypatch):
    calls = {}

    def fake_run_packs(pass_name, model, cap, packs_path=None, limit=0, shard=200,
                       job_maker=None, start=0):
        calls.update(packs_path=packs_path, limit=limit, job_maker=job_maker, start=start)
        return {"packs": 2, "chunks": 4, "start_next": start + 2}

    seen_done = {"n": 0}

    def scope_done(pass_name, model, packs_path):
        seen_done["n"] += 1
        return 0 if seen_done["n"] <= 2 else 2   # 1st call = [start] banner, 2nd = loop head

    monkeypatch.setattr(D.PR, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(D, "scope_done", scope_done)
    monkeypatch.setattr(D, "day_out_tokens", lambda model: 0)
    monkeypatch.setattr(D, "ledger_errors", lambda pass_name, since: 0)
    monkeypatch.setattr(D.PR, "run_packs", fake_run_packs)
    sentinel = object()
    packs = packs_file(tmp_path)
    assert D.run("p", "m", packs, 10, 5, 200, 5.0, job_maker=sentinel) == 0
    assert calls["job_maker"] is sentinel and calls["packs_path"] == packs and calls["limit"] == 5
    assert calls["start"] == 0


def test_run_advances_cursor_over_fully_cached_windows(tmp_path, monkeypatch):
    """Regression: a window whose packs all have raws must advance the cursor, not spin forever."""
    seen_starts = []

    def fake_run_packs(pass_name, model, cap, packs_path=None, limit=0, shard=200,
                       job_maker=None, start=0):
        seen_starts.append(start)
        if start == 0:
            return {"packs": 0, "chunks": 0, "start_next": 200}   # cached window
        return {"packs": 1, "chunks": 1, "start_next": start + 200}

    def scope_done(pass_name, model, packs_path):
        return 0 if len(seen_starts) < 2 else 500

    monkeypatch.setattr(D.PR, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(D, "scope_done", scope_done)
    monkeypatch.setattr(D, "day_out_tokens", lambda model: 0)
    monkeypatch.setattr(D, "ledger_errors", lambda pass_name, since: 0)
    monkeypatch.setattr(D.PR, "run_packs", fake_run_packs)
    assert D.run("p", "m", packs_file(tmp_path, n=500), 10, 5, 200, 5.0) == 0
    assert seen_starts == [0, 200]


def test_done_n_is_model_scoped(tmp_path, monkeypatch):
    """Regression: the raw dir also holds the earlier free-Ultrafast raws of the same pass, so a
    directory count made the AMD run look finished before it had sent a call. Count ledger rows."""
    rows = [(f"k{i}", "p4c_bulk", "old-free-model", "ok") for i in range(3)]
    rows += [("k4", "p4c_bulk", "AMD", "ok"), ("k5", "p4c_bulk", "AMD", "error")]

    class Con:
        def __init__(self):
            self.sql, self.params = "", []

        def execute(self, sql, params):
            self.sql, self.params = sql, list(params)
            wanted, model = params[0], (params[1] if len(params) > 1 else "")
            self.n = len({r[0] for r in rows
                          if r[1] == wanted and r[3] == "ok" and (not model or r[2] == model)})
            return self

        def fetchone(self):
            return (self.n,)

        def close(self):
            pass

    monkeypatch.setattr(D.R, "connect", lambda: Con())
    assert D.done_n("p4c_bulk") == 4              # all models: old free raws + the AMD one
    assert D.done_n("p4c_bulk", "AMD") == 1       # only this model


def test_done_n_excludes_truncated_answers(tmp_path, monkeypatch):
    """Regression: `finish_reason='length'` rows are stored as `ok` but are unusable, so they must
    not count toward completion (and must not mask a cap-driven re-key)."""
    seen = {}

    class Con:
        def execute(self, sql, params):
            seen["sql"] = sql
            return self

        def fetchone(self):
            return (3,)

        def close(self):
            pass

    monkeypatch.setattr(D.R, "connect", lambda: Con())
    assert D.done_n("p4c_bulk", "DeepSeek-V4.1-Flash") == 3
    assert "finish_reason" in seen["sql"] and "'length'" in seen["sql"]


def test_scope_done_is_key_exact(tmp_path, monkeypatch):
    """Regression: a cap raise orphans every stored raw but leaves its `ok` ledger row, so the
    completion test must recompute the expected job_key per pack instead of counting ledger rows."""
    seen = {}
    monkeypatch.setattr(D.PR, "load_modes", lambda: {"m": "tools"})

    def fake_done_packs(pass_name, model, mode, packs_path=None, limit=0):
        seen.update(pass_name=pass_name, model=model, mode=mode, path=packs_path)
        return 7

    monkeypatch.setattr(D.PR, "done_packs", fake_done_packs)
    assert D.scope_done("p4c_bulk", "m", tmp_path / "packs.jsonl") == 7
    assert seen == {"pass_name": "p4c_bulk", "model": "m", "mode": "tools",
                    "path": tmp_path / "packs.jsonl"}


def test_scope_done_falls_back_to_ledger_without_a_transport(tmp_path, monkeypatch):
    monkeypatch.setattr(D.PR, "load_modes", lambda: {})
    monkeypatch.setattr(D, "done_n", lambda pass_name, model="": 5)
    assert D.scope_done("p4c_bulk", "m", tmp_path / "packs.jsonl") == 5


def test_run_backs_off_when_pool_unhealthy_without_quota(tmp_path, monkeypatch):
    """`--quota 0` (AMD pool) must back off rather than sleep to UTC midnight."""
    slept, ran = [], {"n": 0}

    def fake_run_packs(pass_name, model, cap, packs_path=None, limit=0, shard=200,
                       job_maker=None, start=0):
        ran["n"] += 1
        if ran["n"] >= 3:
            raise SystemExit(0)          # leave the loop once the branch under test has run
        return {"packs": 10, "chunks": 20, "start_next": 10}

    monkeypatch.setattr(D.PR, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(D, "scope_done", lambda pass_name, model, packs_path: 0)
    monkeypatch.setattr(D, "day_out_tokens", lambda model: 0)
    monkeypatch.setattr(D, "ledger_errors", lambda pass_name, since: 9)   # 90% broken
    monkeypatch.setattr(D, "sleep_until", lambda ts: pytest.fail("must not wait for UTC midnight"))
    monkeypatch.setattr(D.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(D.PR, "run_packs", fake_run_packs)
    with pytest.raises(SystemExit):
        D.run("p", "m", packs_file(tmp_path, n=200), 0, 10, 200, 5.0)
    assert slept and slept[0] == D.STALL_SLEEP_S


def test_main_glean_refuses_without_pack_list(tmp_path, monkeypatch):
    monkeypatch.setattr(D.PR, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(GL, "GLEAN_PACKS", tmp_path / "missing.jsonl")
    monkeypatch.setattr(D, "run", lambda *a, **k: pytest.fail("should not run"))
    monkeypatch.setattr(sys, "argv", ["p4c_daemon.py", "--glean", "--model", "m"])
    with pytest.raises(SystemExit) as exc:
        D.main()
    assert "glean pack list" in str(exc.value)


def test_main_glean_passes_job_maker(tmp_path, monkeypatch):
    seen = {}
    packs = packs_file(tmp_path)

    def fake_run(pass_name, model, packs_path, quota, chunk, shard, cap, job_maker=None):
        seen.update(pass_name=pass_name, packs_path=packs_path, has_maker=job_maker is not None)
        return 0

    monkeypatch.setattr(D.PR, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(GL, "GLEAN_PACKS", packs)
    monkeypatch.setattr(D, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["p4c_daemon.py", "--glean", "--model", "m"])
    assert D.main() == 0
    assert seen == {"pass_name": GL.GLEAN_PASS, "packs_path": packs, "has_maker": True}


def test_ledger_clock_is_naive_local_not_utc():
    """Regression: `jobs.created_at` is written by `time.strftime` (naive local). Comparing it to a
    UTC ISO string matched every row of the day, including the previous run's, so the stall detector
    fired on `errors 223/400` when only 67 rows were `error`, and `day_out_tokens` read 0 forever."""
    import datetime as dt
    assert D.ledger_now().tzinfo is None
    # the two clocks must agree on the date substring the ledger stores
    assert D.ledger_now().strftime("%Y-%m-%d") == dt.datetime.now().strftime("%Y-%m-%d")
    assert "Z" not in D.ledger_now().isoformat(timespec="seconds")
    assert "+00:00" not in D.ledger_now().isoformat(timespec="seconds")


def test_ledger_error_window_counts_only_this_round(tmp_path, monkeypatch):
    """A `t0` stamped on the ledger clock must not match the previous run's rows."""
    import datetime as dt
    con = None
    try:
        import sqlite3
        p = tmp_path / "led.sqlite"
        con = sqlite3.connect(str(p))
        con.execute("CREATE TABLE jobs (pass TEXT, created_at TEXT, status TEXT)")
        old = (dt.datetime.now() - dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S")
        fresh = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        con.executemany("INSERT INTO jobs VALUES (?,?,?)",
                        [("p4c_bulk", old, "error")] * 156
                        + [("p4c_bulk", fresh, "error")] * 67
                        + [("p4c_bulk", fresh, "ok")] * 333)
        con.commit()
        monkeypatch.setattr(D.R, "connect", lambda: sqlite3.connect(str(p)))
        t0 = D.ledger_now().isoformat(timespec="seconds")
        assert D.ledger_errors("p4c_bulk", t0) == 67          # not 223
    finally:
        if con is not None:
            con.close()


def test_main_bulk_defaults_to_the_full_pack_list(monkeypatch):
    seen = {}

    def fake_run(pass_name, model, packs_path, quota, chunk, shard, cap, job_maker=None):
        seen.update(pass_name=pass_name, has_maker=job_maker is not None)
        return 0

    monkeypatch.setattr(D.PR, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(D, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["p4c_daemon.py", "--model", "m"])
    assert D.main() == 0
    assert seen == {"pass_name": D.PR.BULK_PASS, "has_maker": False}
