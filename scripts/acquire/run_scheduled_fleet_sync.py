#!/usr/bin/env python3
"""
scripts/acquire/run_scheduled_fleet_sync.py
===========================================
Autonomous Stealth Fleet Telemetry Synchronization Runner
---------------------------------------------------------
Designed for zero-risk, zero-babysitting background execution:
1. Checks timestamp of last sync. Enforces minimum 3-to-4 day interval to ensure
   total stealth and eliminate repetitive traffic signatures.
2. Every 4 days: Refreshes headless session and syncs the 1,400-hull Macro Benchmark
   fleet (700 Dry Bulk, 500 Tankers, 100 LNG, 100 LPG) in exactly 4 batch API calls.
3. Every 28 days: Automatically runs full global fleet sweep (all 8,600+ vessels in
   7 batch API calls) so background vessels never stay frozen.
4. Updates port queues, terminal anchorage counts, and gas metrics.
5. Commits updated data artifacts and pushes directly to origin main.
"""

import os
import sys
import json
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VIEWS_DIR = REPO_ROOT / "data" / "views" / "signal"
SYNC_STATE_FILE = REPO_ROOT / ".last_fleet_sync"

MIN_INTERVAL_DAYS = 3.5  # Sync every ~4 days
FULL_SWEEP_INTERVAL_DAYS = 28.0  # Full fleet sweep once a month

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

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run stealth automated fleet synchronization.")
    parser.add_argument("--force", action="store_true", help="Force sync regardless of elapsed time.")
    parser.add_argument("--full", action="store_true", help="Force full global fleet sweep (7 calls).")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
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

    days_since_sync = (now - last_sync_dt).total_seconds() / 86400.0 if last_sync_dt else 999.0
    days_since_full = (now - last_full_dt).total_seconds() / 86400.0 if last_full_dt else 999.0

    if not args.force and days_since_sync < MIN_INTERVAL_DAYS:
        logging.info(
            "Stealth Protection: Last fleet sync was %.1f days ago (minimum interval: %.1f days). Skipping execution.",
            days_since_sync, MIN_INTERVAL_DAYS
        )
        return 0

    run_full = args.full or (days_since_full >= FULL_SWEEP_INTERVAL_DAYS)
    mode_str = "Full Global Fleet (7 batch calls)" if run_full else "Macro Benchmark Core Fleet (1,400 hulls, 4 calls)"
    logging.info("Starting stealth sync: %s (days since last sync: %.1f)...", mode_str, days_since_sync)

    # Step 1: Headless session refresh
    logging.info("Step 1: Refreshing headless Signal Ocean authentication session...")
    refresh_script = REPO_ROOT / "scripts" / "acquire" / "auto_refresh_signal_session.py"
    res = subprocess.run([sys.executable, str(refresh_script)], cwd=str(REPO_ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        logging.error("Session refresh failed:\n%s\n%s", res.stdout, res.stderr)
        return 1
    logging.info("Session successfully refreshed.")

    # Step 2: Ingest fleet positions
    logging.info("Step 2: Fetching vessel telemetry from Signal Ocean gateway...")
    sync_cmd = [sys.executable, str(REPO_ROOT / "scripts" / "acquire" / "sync_live_fleet_pipeline.py")]
    if run_full:
        sync_cmd.append("--full")
    else:
        sync_cmd.append("--benchmark")

    res = subprocess.run(sync_cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        logging.error("Telemetry sync failed:\n%s\n%s", res.stdout, res.stderr)
        return 1
    logging.info("Telemetry ingestion and port queues completed successfully.")

    # Update state file
    state["last_benchmark_sync"] = now.isoformat()
    if run_full:
        state["last_full_sync"] = now.isoformat()
    save_sync_state(state)

    # Step 3: Git commit and push
    logging.info("Step 3: Staging updated data and pushing to GitHub repository...")
    try:
        subprocess.run(["git", "add", "data/views/signal/", "data/geospatial/", "data/derived/", "data/reference/"], cwd=str(REPO_ROOT), check=True)
        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT), capture_output=True, text=True)
        if not status_res.stdout.strip():
            logging.info("No data changes detected to commit.")
            return 0

        commit_msg = f"data(fleet): automated {'full' if run_full else 'benchmark'} fleet sync {now.strftime('%Y-%m-%d')} [skip ci]"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=str(REPO_ROOT), check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=str(REPO_ROOT), check=True)
        logging.info("SUCCESS: Fresh fleet data successfully committed and pushed to main!")
    except Exception as ex:
        logging.error("Git push step failed: %s", ex)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
