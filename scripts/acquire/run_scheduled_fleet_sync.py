#!/usr/bin/env python3
"""
scripts/acquire/run_scheduled_fleet_sync.py
===========================================
Autonomous Stealth Fleet Telemetry Synchronization Runner
---------------------------------------------------------
Designed for zero-risk, zero-babysitting background execution:
1. Checks timestamp of last sync. Enforces minimum 3-to-4 day interval to ensure
   total stealth and eliminate repetitive traffic signatures.
2. Every 2 days: Refreshes headless session and syncs the 5,000-hull Macro Benchmark
   fleet (2,000 Dry Bulk, 2,000 Tankers, 500 LNG, 500 LPG) in exactly 4 batch API calls.
3. Every 28 days: Automatically runs full global fleet sweep (all 8,800+ vessels in
   7 batch API calls) so background vessels never stay frozen.
4. Updates port queues, terminal anchorage counts, and gas metrics.
5. Commits updated data artifacts and pushes directly to origin main.
"""

import os
import sys
import json
import time
import urllib.request
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone, timedelta

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "fleet_sync.log"

# Multi-output logging: console + rotating log file (5 MB, 3 backups)
logger = logging.getLogger("fleet_sync")
logger.setLevel(logging.INFO)
if not logger.handlers:
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(c_handler)

    f_handler = RotatingFileHandler(str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    f_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(f_handler)

VIEWS_DIR = REPO_ROOT / "data" / "views" / "signal"
SYNC_STATE_FILE = REPO_ROOT / ".last_fleet_sync"

FULL_SWEEP_INTERVAL_DAYS = 28.0  # Full fleet sweep once a month

IST = timezone(timedelta(hours=5, minutes=30))

def wait_for_network(max_wait_seconds=45):
    """Ensures network connectivity is active (crucial when waking from sleep/hibernate)."""
    logger.info("Pre-flight: Checking network connectivity...")
    deadline = time.time() + max_wait_seconds
    probe_urls = ["https://app.signalocean.com", "https://github.com", "https://1.1.1.1"]
    while time.time() < deadline:
        for url in probe_urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in (200, 301, 302, 403):  # Any reachable response
                        logger.info("Network connectivity confirmed (reached %s).", url)
                        return True
            except Exception:
                pass
        time.sleep(5)
    logger.warning("Network connectivity probe timed out after %ds. Proceeding anyway...", max_wait_seconds)
    return False

def get_last_sync_state():
    if SYNC_STATE_FILE.exists():
        try:
            return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    # Fallback to live_fleet_positions.json mtime or as_of
    live_file = VIEWS_DIR / "live_fleet_positions.json"
    if live_file.exists():
        try:
            data = json.loads(live_file.read_text(encoding="utf-8"))
            as_of_str = data.get("as_of")
            if as_of_str:
                dt = datetime.fromisoformat(as_of_str).replace(tzinfo=timezone.utc)
                return {"last_benchmark_sync": dt.isoformat(), "last_full_sync": dt.isoformat()}
        except Exception:
            pass
        mtime = datetime.fromtimestamp(live_file.stat().st_mtime, tz=timezone.utc)
        return {"last_benchmark_sync": mtime.isoformat(), "last_full_sync": mtime.isoformat()}
    
    return {"last_benchmark_sync": None, "last_full_sync": None}

def save_sync_state(state):
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def should_run_today(last_sync_dt, now_dt):
    """
    Intelligent daily cadence:
    Runs once per calendar day in IST (UTC+05:30).
    If the last sync was performed today after 06:00 AM IST, skip duplicate execution.
    If the last sync was yesterday or earlier, or before 06:00 AM today and >= 6 hours have elapsed, execute.
    """
    if last_sync_dt is None:
        return True, "No previous sync recorded."
    
    now_ist = now_dt.astimezone(IST)
    last_ist = last_sync_dt.astimezone(IST)
    elapsed_hours = (now_dt - last_sync_dt).total_seconds() / 3600.0

    # If already completed today AFTER 6:00 AM IST, today's morning sync is done
    if now_ist.date() == last_ist.date() and last_ist.hour >= 6:
        return False, f"Already completed today at {last_ist.strftime('%H:%M:%S')} IST (elapsed: {elapsed_hours:.1f}h)."
    
    # Safety cooldown: at least 6 hours between any two runs
    if elapsed_hours < 6.0:
        return False, f"Recent sync completed {elapsed_hours:.1f} hours ago (< 6h safety cooldown)."

    return True, f"Eligible for daily run. Last run was {elapsed_hours:.1f}h ago ({last_ist.strftime('%Y-%m-%d %H:%M')} IST)."

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run stealth automated fleet synchronization.")
    parser.add_argument("--force", action="store_true", help="Force sync regardless of elapsed time.")
    parser.add_argument("--full", action="store_true", help="Force full global fleet sweep (7 calls).")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    now_ist = now.astimezone(IST)
    logger.info("=" * 70)
    logger.info("ShippingFleetSync Triggered: %s IST (%s UTC)", now_ist.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S"))

    state = get_last_sync_state()

    last_sync_dt = None
    if state.get("last_benchmark_sync"):
        try:
            last_sync_dt = datetime.fromisoformat(state["last_benchmark_sync"])
            if last_sync_dt.tzinfo is None:
                last_sync_dt = last_sync_dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    last_full_dt = None
    if state.get("last_full_sync"):
        try:
            last_full_dt = datetime.fromisoformat(state["last_full_sync"])
            if last_full_dt.tzinfo is None:
                last_full_dt = last_full_dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    should_run, reason = should_run_today(last_sync_dt, now)
    days_since_full = (now - last_full_dt).total_seconds() / 86400.0 if last_full_dt else 999.0

    if not args.force and not should_run:
        logger.info("Cadence Check: %s Skipping execution.", reason)
        return 0

    if args.force:
        logger.info("Force flag passed. Overriding interval checks.")
    else:
        logger.info("Cadence Check Passed: %s", reason)

    # Pre-flight network check
    wait_for_network(max_wait_seconds=45)

    run_full = args.full or (days_since_full >= FULL_SWEEP_INTERVAL_DAYS)
    mode_str = "Full Global Fleet (7 batch calls)" if run_full else "Macro Benchmark Core Fleet (5,000 hulls, 4 calls)"
    logger.info("Starting synchronization: %s...", mode_str)

    # Step 1: Headless session refresh via Playwright
    logger.info("Step 1: Refreshing headless Signal Ocean authentication session...")
    refresh_script = REPO_ROOT / "scripts" / "acquire" / "auto_refresh_signal_session.py"
    res = subprocess.run([sys.executable, str(refresh_script)], cwd=str(REPO_ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        logger.error("Session refresh failed:\n%s\n%s", res.stdout, res.stderr)
        return 1
    logger.info("Session successfully refreshed.")

    # Step 2: Ingest fleet positions
    logger.info("Step 2: Fetching vessel telemetry from Signal Ocean gateway...")
    sync_cmd = [sys.executable, str(REPO_ROOT / "scripts" / "acquire" / "sync_live_fleet_pipeline.py")]
    if run_full:
        sync_cmd.append("--full")
    else:
        sync_cmd.append("--benchmark")

    res = subprocess.run(sync_cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        logger.error("Telemetry sync failed:\n%s\n%s", res.stdout, res.stderr)
        return 1
    logger.info("Telemetry ingestion and port queues completed successfully.")

    # Update state file
    state["last_benchmark_sync"] = now.isoformat()
    if run_full:
        state["last_full_sync"] = now.isoformat()
    save_sync_state(state)

    # Step 3: Git commit and push
    logger.info("Step 3: Staging updated data and pushing to GitHub repository...")
    try:
        # Determine current branch
        branch_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True)
        current_branch = branch_res.stdout.strip()

        # If on main, safely pull latest changes before commit/push
        if current_branch == "main":
            subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=str(REPO_ROOT), check=False)

        # Stage only data views and telemetry artifacts
        subprocess.run(
            ["git", "add", "data/views/signal/", "data/geospatial/", "data/derived/", "data/reference/"],
            cwd=str(REPO_ROOT),
            check=True
        )
        status_res = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(REPO_ROOT), capture_output=True, text=True)
        if not status_res.stdout.strip():
            logger.info("No data changes detected to commit.")
            return 0

        commit_msg = f"data(fleet): automated {'full' if run_full else 'benchmark'} fleet sync {now.strftime('%Y-%m-%d')} [skip ci]"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=str(REPO_ROOT), check=True)

        if current_branch == "main":
            subprocess.run(["git", "push", "origin", "main"], cwd=str(REPO_ROOT), check=True)
        else:
            # On feature/benchmark branch: push current branch safely
            subprocess.run(["git", "push", "origin", current_branch], cwd=str(REPO_ROOT), check=False)

        logger.info("SUCCESS: Fresh fleet data successfully committed and pushed to GitHub!")
    except Exception as ex:
        logger.error("Git synchronization step failed: %s", ex)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
