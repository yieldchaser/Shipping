#!/usr/bin/env python3
"""
kb/run_job.py <name> -- <command ...>   (docs/GRAPHRAG_BUILD_PLAN.md §10.1, §10.4)

Starts <command> detached and records kb/state/jobs/<name>.json with pid, command,
start time, log path and a heartbeat the job refreshes every 60 s. The job writes
`status: done` or `status: failed` when it ends. The runner's own heartbeat is
refreshed by a background thread that watches the child; when the child exits it does
one final heartbeat and writes status done/failed from the exit code.

This wrapper is the ONLY thing that may spawn long jobs; unit-skipping/resume logic
lives in each long-running script, not here.
"""
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "kb" / "state"
JOBS = STATE / "jobs"
LOGS = STATE / "logs"


def main() -> int:
    if len(sys.argv) < 4 or sys.argv[2] != "--":
        print("usage: python kb/run_job.py <name> -- <command ...>")
        return 2
    name = sys.argv[1]
    if not name.replace("-", "").replace("_", "").isalnum():
        print(f"invalid job name: {name}")
        return 2
    cmd = sys.argv[3:]
    JOBS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    log_path = LOGS / f"{name}.log"
    job_path = JOBS / f"{name}.json"
    start = time.time()

    with open(log_path, "ab") as logf:
        logf.write(f"\n=== {name} start {datetime.now(timezone.utc).isoformat()} cmd={cmd}\n".encode())
        popen = subprocess.Popen(
            cmd, cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )

    def write_job(status, pid=None, heartbeat=None):
        rec = {
            "name": name,
            "command": cmd,
            "pid": pid,
            "started": start,
            "status": status,
            "heartbeat": heartbeat or time.time(),
            "log": str(log_path.relative_to(ROOT)),
        }
        tmp = job_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        tmp.replace(job_path)

    write_job("running", pid=popen.pid)

    def watch():
        rc = popen.wait()
        write_job("done" if rc == 0 else "failed", pid=popen.pid)
        with open(log_path, "ab") as logf:
            logf.write(f"=== {name} exit rc={rc} at {datetime.now(timezone.utc).isoformat()}\n".encode())

    threading.Thread(target=watch, daemon=True).start()

    # refresh heartbeat every 60 s while the child lives
    while popen.poll() is None:
        time.sleep(20)
        if popen.poll() is None:
            write_job("running", pid=popen.pid)
    popen.wait()
    # ensure final status landed even if the watch thread raced
    time.sleep(0.5)
    print(f"{name}: pid={popen.pid} rc={popen.returncode} log={log_path}")
    return popen.returncode


if __name__ == "__main__":
    sys.exit(main())
