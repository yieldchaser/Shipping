"""Crash-resilient supervisor for the P4c bulk daemon.

The daemon can die with a CPython fatal error (`PyEval_SaveThread` with a NULL thread state) when a
pool thread is parked in an SSL read while the interpreter finalizes. That is an interpreter-level
abort, not a Python exception: it cannot be caught in-process, so recovery has to live outside the
process. This wrapper restarts the daemon after any exit while the pass is unfinished, with a short
back-off, and records every restart so a crash loop is visible instead of a silent stall.
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOGDIR = ROOT / "kb" / "logs"
RESTART_SLEEP_S = 20


def args_of(extra: list[str]) -> list[str]:
    return [sys.executable, "-X", "utf8", "-u", str(HERE / "p4c_daemon.py"), *extra]


def main() -> int:
    extra = sys.argv[1:]
    attempt = 0
    while True:
        attempt += 1
        started = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(LOGDIR / "p4c_bulk_supervisor.log", "a", encoding="utf-8") as fh:
            fh.write(f"[supervisor] launch #{attempt} at {started}\n")
        with open(LOGDIR / "p4c_bulk16.log", "a", encoding="utf-8") as out, \
                open(LOGDIR / "p4c_bulk16.err.log", "a", encoding="utf-8") as err:
            out.write(f"\n[supervisor] launch #{attempt} at {started}\n")
            out.flush()
            rc = subprocess.call(args_of(extra), stdout=out, stderr=err, cwd=str(ROOT))
        with open(LOGDIR / "p4c_bulk_supervisor.log", "a", encoding="utf-8") as fh:
            fh.write(f"[supervisor] launch #{attempt} exited rc={rc} at "
                     f"{time.strftime('%Y-%m-%dT%H:%M:%S')}; restarting in {RESTART_SLEEP_S}s\n")
        if rc == 0:
            return 0
        time.sleep(RESTART_SLEEP_S)


if __name__ == "__main__":
    raise SystemExit(main())
