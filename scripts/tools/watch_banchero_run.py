#!/usr/bin/env python3
"""Watchdog for the banchero LlamaParse run.

Written in Python, not bash, because the cron scheduler resolved `.sh` through
C:/Windows/System32/bash.exe - the WSL launcher, which has no distro installed on
this host - and the job failed with "WSL has no installed distributions". The
interactive terminal uses MSYS git-bash at C:/Program Files/Git/bin/bash.exe, so a
shell script appears to work there and silently fails in cron. Python is
unambiguous: one interpreter, no PATH ambiguity.

Contract for the no-agent cron slot: stdout is the only signal that reaches the
user, so print NOTHING while healthy. Output appears only on news (restart or
completion). Recovery is "start it again if it is not running" - the runner is
resumable, so a restart never loses work.

Safety: when liveness cannot be determined, this refuses to restart. Two concurrent
runs would double-spend credits on the same documents, which is worse than a run
sitting idle until the next tick.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("C:/Users/Dell/Github/Shipping")
LOGDIR = ROOT / "data/extracted/llamaparse_banchero"
LOG = LOGDIR / "run.log"
STATE = LOGDIR / "_run_state.json"
WATCHLOG = LOGDIR / "watchdog.log"
RUNNER = ROOT / "scripts/extract/publishers/run_banchero_llamaparse.py"
PYTHON = Path("C:/Users/Dell/AppData/Local/Programs/Python/Python314/python.exe")
PS = Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")

STALE_SECONDS = 600          # log untouched this long AND no process => treat as dead


def stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    try:
        LOGDIR.mkdir(parents=True, exist_ok=True)
        with open(WATCHLOG, "a", encoding="utf-8") as f:
            f.write(f"{stamp()} {msg}\n")
    except Exception:
        pass


def read_state():
    try:
        st = json.loads(STATE.read_text())
        return len(st.get("done", {})), len(st.get("failed", {})), \
               st.get("pages_parsed", 0), st.get("credits_estimated", 0)
    except Exception:
        return 0, 0, 0, 0


def total_docs() -> int:
    try:
        return len(list((ROOT / "corpus/01-brokers/banchero_costa").glob("*/*.pdf")))
    except Exception:
        return 0


def runner_alive() -> int | None:
    """1 alive, 0 not alive, None unknown."""
    ps = str(PS) if PS.exists() else "powershell"
    cmd = ("(Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
           "Where-Object { $_.CommandLine -like '*run_banchero_llamaparse*' } | "
           "Measure-Object).Count")
    try:
        out = subprocess.run([ps, "-NoProfile", "-Command", cmd],
                             capture_output=True, text=True, timeout=90)
        txt = (out.stdout or "").strip()
        if txt.isdigit():
            return 1 if int(txt) > 0 else 0
    except Exception:
        pass
    return None


def log_age() -> float | None:
    try:
        return time.time() - LOG.stat().st_mtime
    except Exception:
        return None


def restart() -> int | None:
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            p = subprocess.Popen(
                [str(PYTHON), str(RUNNER), "--tier", "cost_effective"],
                cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                | getattr(subprocess, "DETACHED_PROCESS", 0),
            )
        return p.pid
    except Exception as e:
        log(f"restart FAILED: {e}")
        return None


def main() -> int:
    done, failed, pages, credits = read_state()
    total = total_docs()
    alive = runner_alive()
    age = log_age()

    # Unknown liveness: fall back to the log heartbeat, else refuse to act.
    if alive is None:
        if age is not None and age < STALE_SECONDS:
            log(f"liveness unknown, log fresh ({age:.0f}s) - no action")
            return 0
        log("liveness unknown and log stale - NOT restarting (avoid double-spend)")
        print(f"{stamp()} banchero watchdog: cannot determine liveness and the log is "
              f"stale. Not restarting to avoid double-spending credits. Check manually.")
        return 0

    log(f"alive={alive} done={done} failed={failed} credits={credits}")

    if alive:
        return 0                       # healthy -> silence

    # Not running. Finished?
    if total and done >= total - 1:
        if not (LOGDIR / "_complete_reported").exists():
            try:
                (LOGDIR / "_complete_reported").touch()
            except Exception:
                pass
            print(f"banchero LlamaParse run COMPLETE: {done}/{total} docs, {pages} pages, "
                  f"~{credits} credits, {failed} failures.")
            if failed:
                print(f"Failures to triage: see {STATE}")
        return 0

    pid = restart()
    if pid:
        print(f"banchero LlamaParse run was DEAD at {done}/{total} docs "
              f"({failed} failures, ~{credits} credits spent). Restarted as pid {pid}; "
              f"it resumes from the checkpoint so no work is lost.")
    else:
        print(f"{stamp()} banchero watchdog: run is dead and the restart FAILED at "
              f"{done}/{total} docs. Manual attention needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
