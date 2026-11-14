"""Watchdog: relaunch the P4c bulk supervisor if no supervisor/daemon is alive.

Why this exists: ``p4c_supervisor.py`` restarts the *daemon* after a crash, but nothing restarts the
*supervisor* after a host reboot. A Windows OS update restart already killed the fleet once
(2026-11-14 04:45), and the remaining drain needs ~11-21 h of uninterrupted wall clock. This script
is the outer ring: it is registered as a user-scope scheduled task at logon and every 10 minutes, and
it does nothing at all while a supervisor or daemon process is already running.

It deliberately does not import any ``kb`` module, so it keeps working even if the pipeline code is
mid-edit. Safe by construction: the ledger is the resume point, so an extra launch never re-does
completed work -- but the process check makes an extra launch the rare case rather than the norm.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOGDIR = ROOT / "kb" / "logs"
LOG = LOGDIR / "p4c_watchdog.log"

# The exact fleet command that was verified live (see STATUS.md). Kept in one place so the watchdog
# and the manual launch cannot drift apart.
SUPERVISOR_ARGS = ["--model", "DeepSeek-V4.1-Flash", "--quota", "0", "--chunk", "400"]
MARKERS = ("p4c_supervisor.py", "p4c_daemon.py")


def _log(text: str) -> None:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(text + "\n")


def fleet_alive() -> list[str]:
    """Names of live fleet processes. psutil-only; returns [] if psutil is unavailable."""
    try:
        import psutil
    except Exception:  # pragma: no cover - environment guard
        return []
    found = []
    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmd = " ".join(proc.info.get("cmdline") or [])
        except Exception:
            continue
        if any(m in cmd for m in MARKERS):
            found.append(str(proc.pid))
    return found


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    force = "--force" in argv
    alive = fleet_alive()
    if alive and not force:
        return 0  # quiet: normal case, nothing to say
    import time
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    if alive:
        _log(f"[{stamp}] --force with pids {alive} already alive; not launching")
        return 0
    _log(f"[{stamp}] no supervisor/daemon alive; launching supervisor")
    cmd = [sys.executable, "-X", "utf8", "-u", str(HERE / "p4c_supervisor.py"), *SUPERVISOR_ARGS]
    # Detached, hidden: a -Force kill of an SSL-busy child has produced an interpreter abort before,
    # so the fleet is launched independently of any console/session lifetime.
    try:
        subprocess.Popen(cmd, cwd=str(ROOT), creationflags=0x00000008 | 0x08000000,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
    except Exception as exc:  # pragma: no cover - reported, never raised
        _log(f"[{stamp}] launch failed: {exc!r}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
