#!/usr/bin/env python3
"""
Resume helper (docs/GRAPHRAG_AGENT_TASK.md §10.2). Run at the start of every session.

Reports, without changing anything:
  - current phase + next action from kb/reports/STATUS.md;
  - every job in kb/state/jobs/ and its state: done | paused | running | dead;
  - ledger totals (kb/state/ledger.sqlite, if present) — the paid-work source of truth;
  - whether the gateway answers on http://127.0.0.1:4100/stats (and current spend);
  - git status (branch, head, dirty paths).

Exit 0 always. Restarting dead/paused jobs is a separate, deliberate action by the router.

Usage: python kb/resume.py
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "kb"
STATE = KB / "state"
JOBS = STATE / "jobs"
LEDGER = STATE / "ledger.sqlite"
STATUS_MD = KB / "reports" / "STATUS.md"
HEARTBEAT_MAX_AGE_S = 180  # §10.2: older than 3 min AND no live PID => dead


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def heartbeat_age(s: float) -> str:
    age = time.time() - s
    if age < 60:
        return f"{age:.0f}s ago"
    if age < 3600:
        return f"{age/60:.1f}m ago"
    return f"{age/3600:.1f}h ago"


def pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        import ctypes

        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:
        return False


def section(title):
    print(f"\n== {title} ==")


def main() -> int:
    print(f"resume @ {datetime.now(timezone.utc).isoformat()}  workdir {ROOT}")

    # ---- STATUS.md phase / next action ----
    section("STATUS.md")
    if STATUS_MD.exists():
        text = STATUS_MD.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.startswith("| P") and ("not started" in line or "running" in line or "next" in line.lower()):
                print("  " + line.strip())
        for line in text.splitlines():
            if "next action" in line.lower() or line.strip().startswith("Next"):
                print("  " + line.strip())
    else:
        print("  (missing) kb/reports/STATUS.md")

    # ---- jobs ----
    section("jobs (kb/state/jobs/)")
    if not JOBS.exists():
        print("  none — no job directory yet")
    else:
        for jf in sorted(JOBS.glob("*.json")):
            try:
                j = json.loads(jf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                print(f"  {jf.stem}: UNREADABLE")
                continue
            pid = int(j.get("pid") or 0)
            hb = j.get("heartbeat")
            age = heartbeat_age(hb) if hb else "n/a"
            status = str(j.get("status", "?"))
            if status == "done":
                state = "done"
            elif status == "failed":
                state = "failed"
            elif status == "paused":
                state = "paused"
            elif pid_alive(pid):
                state = "running"
            elif hb and (time.time() - hb) > HEARTBEAT_MAX_AGE_S:
                state = "dead"
            elif hb:
                state = "running (no pid, fresh heartbeat)"
            else:
                state = "dead (no pid, no heartbeat)"
            print(f"  {jf.stem}: {state}  pid={pid or '-'}  heartbeat={age}  log={j.get('log','-')}")
            if state in ("dead", "paused", "failed"):
                print(f"     resume cmd: {j.get('command','-')}")

    # ---- ledger ----
    section("ledger (kb/state/ledger.sqlite)")
    if not LEDGER.exists():
        print("  none — no paid-work ledger yet (P4b/P4c will create it)")
    else:
        try:
            import sqlite3

            con = sqlite3.connect(LEDGER)
            for t in ("response", "call"):
                try:
                    n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                    print(f"  {t} rows: {n}")
                except sqlite3.OperationalError:
                    pass
            con.close()
        except Exception as e:
            print(f"  ledger read error: {e}")

    # ---- gateway ----
    section("gateway (127.0.0.1:4100)")
    try:
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:4100/stats", timeout=5) as r:
            stats = json.loads(r.read().decode("utf-8"))
        print(f"  UP  enclave ${stats.get('enclave_spent_usd'):.2f} / ${stats.get('enclave_cap_usd'):.2f}"
              f"  ultrafast_out_today {stats.get('ultrafast_output_today')}")
    except Exception as e:
        print(f"  DOWN ({e}) — start with tools/agent_gateway/start_gateway.bat")

    # ---- git ----
    section("git")
    br = git("branch", "--show-current").stdout.strip()
    head = git("rev-parse", "--short", "HEAD").stdout.strip()
    print(f"  branch {br}  head {head}")
    for line in git("status", "--porcelain").stdout.splitlines():
        print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
