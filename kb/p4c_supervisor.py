"""Crash-resilient supervisor for the P4c bulk daemon.

The daemon can die with a CPython fatal error (`PyEval_SaveThread` with a NULL thread state) when a
pool thread is parked in an SSL read while the interpreter finalizes. That is an interpreter-level
abort, not a Python exception: it cannot be caught in-process, so recovery has to live outside the
process. This wrapper restarts the daemon after any exit while the pass is unfinished, with a back-off,
and records every restart so a crash loop is visible instead of a silent stall.

The ledger is the resume point, so a restart never re-does completed work: the daemon re-derives the
pending set from the ledger on start. Restarting is therefore always safe, and the only question is
how hard to retry. A child that ran for a useful stretch made progress and is restarted promptly; a
child that dies immediately (missing key, disk full, host resource exhaustion) gets an exponentially
longer pause, capped, so a permanent fault degrades to a slow visible loop instead of a tight spin.
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOGDIR = ROOT / "kb" / "logs"
RESTART_SLEEP_S = 20
RESTART_MAX_S = 300
# A child that stayed up at least this long is treated as having made progress, so the back-off
# resets and the next restart is immediate.
PRODUCTIVE_S = 120


def restart_delay(consecutive_failures: int) -> int:
    """Back-off after `consecutive_failures` quick deaths; capped at RESTART_MAX_S."""
    if consecutive_failures <= 0:
        return RESTART_SLEEP_S
    return min(RESTART_SLEEP_S * (2 ** (consecutive_failures - 1)), RESTART_MAX_S)


def args_of(extra: list[str]) -> list[str]:
    return [sys.executable, "-X", "utf8", "-u", str(HERE / "p4c_daemon.py"), *extra]


def log_line(text: str, logdir: Path | None = None) -> None:
    base = logdir or LOGDIR
    with open(base / "p4c_bulk_supervisor.log", "a", encoding="utf-8") as fh:
        fh.write(text + "\n")


def main() -> int:
    extra = sys.argv[1:]
    attempt = 0
    fails = 0
    while True:
        attempt += 1
        started = time.strftime("%Y-%m-%dT%H:%M:%S")
        t0 = time.monotonic()
        log_line(f"[supervisor] launch #{attempt} at {started}")
        with open(LOGDIR / "p4c_bulk16.log", "a", encoding="utf-8") as out, \
                open(LOGDIR / "p4c_bulk16.err.log", "a", encoding="utf-8") as err:
            out.write(f"\n[supervisor] launch #{attempt} at {started}\n")
            out.flush()
            rc = subprocess.call(args_of(extra), stdout=out, stderr=err, cwd=str(ROOT))
        ran_s = time.monotonic() - t0
        if rc == 0:
            log_line(f"[supervisor] launch #{attempt} exited rc=0 after {ran_s:.0f}s; pass finished")
            return 0
        if ran_s >= PRODUCTIVE_S:
            fails = 0
        fails += 1
        delay = restart_delay(fails)
        log_line(f"[supervisor] launch #{attempt} exited rc={rc} after {ran_s:.0f}s "
                 f"(quick deaths in a row: {fails}); restarting in {delay}s")
        time.sleep(delay)


if __name__ == "__main__":
    raise SystemExit(main())
