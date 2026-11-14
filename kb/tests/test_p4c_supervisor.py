"""Supervisor tests: the crash wrapper must restart safely and back off on a crash loop."""
from __future__ import annotations

import sys
from pathlib import Path

import kb.p4c_supervisor as S


def test_args_of_targets_the_daemon_with_extra_args():
    argv = S.args_of(["--model", "DeepSeek-V4.1-Flash"])
    assert argv[0] == sys.executable
    assert argv[-1] == "DeepSeek-V4.1-Flash"
    assert argv[-2:] == ["--model", "DeepSeek-V4.1-Flash"]
    assert argv[1:3] == ["-X", "utf8"]
    assert argv[4].endswith("p4c_daemon.py")


def test_restart_delay_grows_then_caps():
    assert S.restart_delay(0) == S.RESTART_SLEEP_S
    assert S.restart_delay(1) == S.RESTART_SLEEP_S
    assert S.restart_delay(2) == S.RESTART_SLEEP_S * 2
    assert S.restart_delay(3) == S.RESTART_SLEEP_S * 4
    # a permanent fault must degrade to a slow loop, never a tight spin
    assert S.restart_delay(50) == S.RESTART_MAX_S


def test_main_restarts_after_a_crash_then_exits_on_success(monkeypatch, tmp_path):
    """A crashed child is relaunched; a child that exits 0 ends the loop."""
    calls: list[list[str]] = []
    sleeps: list[int] = []
    rcs = [1, 0]

    def fake_call(args, stdout=None, stderr=None, cwd=None):
        calls.append(args)
        return rcs[len(calls) - 1]

    monkeypatch.setattr(S, "args_of", lambda extra: ["py", "daemon", *extra])
    monkeypatch.setattr(S.subprocess, "call", fake_call)
    monkeypatch.setattr(S.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(S, "LOGDIR", tmp_path)
    monkeypatch.setattr(S.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(sys, "argv", ["supervisor", "--model", "m"])

    assert S.main() == 0
    assert len(calls) == 2
    assert sleeps == [S.RESTART_SLEEP_S]
    log = (tmp_path / "p4c_bulk_supervisor.log").read_text(encoding="utf-8")
    assert "[supervisor] launch #1" in log
    assert "launch #2" in log
    assert "rc=0" in log


def test_main_backs_off_harder_when_every_child_dies_immediately(monkeypatch, tmp_path):
    """Quick deaths in a row must escalate the pause, not hammer the host."""
    sleeps: list[int] = []
    seen = {"n": 0}

    def fake_call(args, stdout=None, stderr=None, cwd=None):
        seen["n"] += 1
        return 3 if seen["n"] < 4 else 0

    monkeypatch.setattr(S, "args_of", lambda extra: ["py", "daemon", *extra])
    monkeypatch.setattr(S.subprocess, "call", fake_call)
    monkeypatch.setattr(S.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(S, "LOGDIR", tmp_path)
    monkeypatch.setattr(S.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(sys, "argv", ["supervisor"])

    assert S.main() == 0
    # 120 s of uptime is the productivity line; instantaneous deaths never reach it
    assert S.RESTART_SLEEP_S in sleeps
    assert sleeps[-1] >= sleeps[0] * 2
    assert all(s <= S.RESTART_MAX_S for s in sleeps)


def test_ledger_is_the_resume_point_so_restarts_are_safe():
    """The supervisor must never pass a `start` cursor: dense mode re-derives pending from the ledger."""
    argv = S.args_of(["--quota", "0"])
    assert "--start" not in argv
