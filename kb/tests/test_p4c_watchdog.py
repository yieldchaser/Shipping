"""Tests for the P4c fleet watchdog (`kb/p4c_watchdog.py`).

The watchdog is the outer ring around `p4c_supervisor.py`: the supervisor restarts the daemon after a
crash, but nothing restarted the supervisor itself after a host reboot, so an unattended restart
silently ended the drain. These tests pin the two properties that make the watchdog safe to run on
every logon: it stays completely quiet while the fleet is alive (never a duplicate supervisor, which
would contend for the shared AMD pool), and it launches exactly once when the fleet is gone.
"""
import subprocess
import sys
from pathlib import Path

import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p4c_watchdog as W  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_log(tmp_path, monkeypatch):
    """Never touch the real watchdog log from a test."""
    monkeypatch.setattr(W, "LOG", tmp_path / "watchdog.log")


def test_quiet_and_no_launch_when_fleet_alive(monkeypatch):
    """Fleet alive => exact silent no-op: no log line, no subprocess."""
    launched = []
    monkeypatch.setattr(W, "fleet_alive", lambda: ["111", "222"])
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: launched.append(a))

    assert W.main([]) == 0
    assert launched == []
    assert not W.LOG.exists()


def test_force_refuses_to_double_launch(monkeypatch):
    """--force must report and refuse, not start a second supervisor on the same pool."""
    launched = []
    monkeypatch.setattr(W, "fleet_alive", lambda: ["111"])
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: launched.append(a))

    assert W.main(["--force"]) == 0
    assert launched == []
    assert "already alive" in W.LOG.read_text(encoding="utf-8")


def test_launches_exactly_once_when_fleet_dead(monkeypatch):
    """Fleet gone => one detached supervisor launch, and the command points at the supervisor."""
    launched = []

    class FakeProc:
        pass

    def fake_popen(cmd, **kwargs):
        launched.append((cmd, kwargs))
        return FakeProc()

    monkeypatch.setattr(W, "fleet_alive", lambda: [])
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    assert W.main([]) == 0
    assert len(launched) == 1
    cmd, kwargs = launched[0]
    assert cmd[0] == sys.executable
    assert cmd[1:3] == ["-X", "utf8"]
    # The launched script is the supervisor (launching the daemon directly is the supervisor's job),
    # and the verified fleet flags are carried through unchanged.
    assert sum(1 for a in cmd if a.endswith("p4c_supervisor.py")) == 1
    assert cmd[5:] == W.SUPERVISOR_ARGS
    # Detached + no visible window + no inherited stdio: a -Force kill of an SSL-busy child has
    # aborted the interpreter before, so the fleet must outlive the launching console.
    assert kwargs["creationflags"] & 0x00000008
    assert kwargs["creationflags"] & 0x08000000
    assert "launching supervisor" in W.LOG.read_text(encoding="utf-8")


def test_fleet_alive_is_false_for_absent_processes():
    """The real liveness probe must not report a fleet from an unrelated python process."""
    import psutil

    assert isinstance(W.fleet_alive(), list)
    assert all(isinstance(p, str) for p in W.fleet_alive())
    # This pytest process is python but not the supervisor/daemon, so it must never match.
    assert str(psutil.Process().pid) not in W.fleet_alive()


def test_launch_failure_is_logged_and_reported(monkeypatch):
    """A failed relaunch must be visible in the log, not swallowed."""
    def boom(*a, **k):
        raise OSError("no such executable")

    monkeypatch.setattr(W, "fleet_alive", lambda: [])
    monkeypatch.setattr(subprocess, "Popen", boom)

    assert W.main([]) == 1
    text = W.LOG.read_text(encoding="utf-8")
    assert "launch failed" in text and "no such executable" in text
