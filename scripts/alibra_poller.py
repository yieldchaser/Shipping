"""
Alibra Shipping — Automated Data Poller & Integration Engine
------------------------------------------------------------
Pulls all 10 published Google Sheets CSV endpoints behind alibrashipping.com/data
and archives each week's snapshot with canonical timestamping, building real forward
curve and period rate history over time.

Usage:
    python scripts/alibra_poller.py               # Polls and saves to docs/alibra_data/
    python scripts/alibra_poller.py --integrate   # Polls and immediately triggers dataset integration
"""

import argparse
import csv
import io
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "alibra_data"
MASTER_LOG = OUTPUT_DIR / "master_log.csv"
TIMEOUT_SECONDS = 20
RETRIES = 2
RETRY_DELAY = 5

BASE_A = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQk6073LStJEfzv418WKYluN2zykXon3KL58hPVNnqoOPiZVhBVzBCi9QnnAETwm_QbMvltcNCuzTzH/pub"
BASE_B = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQkGGniHOjjs_0booelgLP3pGwySZLvMLskYlJCxNLcq6uf9EaH50Wcpob87lH7xw/pub"
BASE_C = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSm3hFo3WpdJQ86FaGIy-S151biJvr2J31-kbmYmO9kOwJ2sDjbz-v8ooNpsufCepZS0tCUavO5iUrI/pub"

ENDPOINTS = {
    "last_updated_stamp":     f"{BASE_A}?gid=92942855&single=true&output=csv",
    "dry_bulk_tce_table":     f"{BASE_A}?gid=1944138367&single=true&output=csv",
    "tanker_tce_table":       f"{BASE_A}?gid=1458966001&single=true&output=csv",
    "forward_curves":         f"{BASE_B}?gid=1196769730&single=true&output=csv",
    "dry_bulk_trend_atl":     f"{BASE_C}?gid=409746990&single=true&output=csv",
    "dry_bulk_trend_pac":     f"{BASE_C}?gid=779118968&single=true&output=csv",
    "tanker_trend_1yr":       f"{BASE_C}?gid=137918187&single=true&output=csv",
    "tanker_trend_3yr":       f"{BASE_C}?gid=1501135879&single=true&output=csv",
    "dry_bulk_archive_atl":   f"{BASE_C}?gid=1609275035&single=true&output=csv",
    "dry_bulk_archive_pac":   f"{BASE_C}?gid=1656242999&single=true&output=csv",
}

def fetch_csv(name, url):
    """Fetches CSV endpoint with retries and content validation."""
    last_reason = "Unknown error"
    for attempt in range(1, RETRIES + 2):
        try:
            resp = requests.get(
                url,
                timeout=TIMEOUT_SECONDS,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AlibraPoller/2.0)"},
            )
        except requests.exceptions.Timeout:
            last_reason = f"Timeout after {TIMEOUT_SECONDS}s (attempt {attempt})"
        except requests.exceptions.ConnectionError as e:
            last_reason = f"Connection error (attempt {attempt}): {e.__class__.__name__}"
        except requests.exceptions.RequestException as e:
            last_reason = f"Request exception (attempt {attempt}): {e}"
        else:
            if resp.status_code != 200:
                last_reason = f"HTTP {resp.status_code} (attempt {attempt})"
            elif not resp.text.strip():
                last_reason = f"Empty response body (attempt {attempt})"
            elif resp.text.lstrip().lower().startswith("<!doctype html") or "<html" in resp.text[:200].lower():
                last_reason = f"Got HTML instead of CSV (attempt {attempt})"
            else:
                try:
                    reader = csv.reader(io.StringIO(resp.text))
                    rows = list(reader)
                    if len(rows) < 1:
                        last_reason = f"CSV contained 0 rows (attempt {attempt})"
                    else:
                        return True, resp.text, "OK"
                except csv.Error as e:
                    last_reason = f"CSV parse error (attempt {attempt}): {e}"

        if attempt <= RETRIES:
            time.sleep(RETRY_DELAY)

    return False, None, last_reason

def parse_report_date(stamp_content):
    """Converts DD/MM/YYYY or similar timestamp string to ISO YYYY-MM-DD."""
    if not stamp_content:
        return None
    cleaned = stamp_content.strip().splitlines()[0].strip()
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", cleaned)
    if m:
        d, m_val, y = m.group(1), m.group(2), m.group(3)
        return f"{int(y):04d}-{int(m_val):02d}-{int(d):02d}"
    return None

def main():
    parser = argparse.ArgumentParser(description="Alibra Shipping Data Poller & Ingestion Engine")
    parser.add_argument("--integrate", action="store_true", help="Trigger integrate_alibra_feed.py post-fetch")
    parser.add_argument("--date", type=str, default="", help="Override file timestamp date (YYYY-MM-DD)")
    args = parser.parse_args()

    run_timestamp = datetime.now(timezone.utc)
    fallback_date_str = run_timestamp.strftime("%Y-%m-%d")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Fetch timestamp first to determine canonical report date
    print(f"=== Alibra Data Poller started at {run_timestamp.isoformat()} ===")
    ok_stamp, stamp_content, stamp_reason = fetch_csv("last_updated_stamp", ENDPOINTS["last_updated_stamp"])
    
    canonical_date = args.date or fallback_date_str
    if ok_stamp and stamp_content:
        parsed = parse_report_date(stamp_content)
        if parsed:
            canonical_date = parsed
            print(f"[INFO] Detected canonical Alibra report date: {canonical_date}")

    log_rows = []
    successes, failures = 0, 0

    # 2. Fetch all endpoints
    for name, url in ENDPOINTS.items():
        endpoint_dir = OUTPUT_DIR / name
        endpoint_dir.mkdir(parents=True, exist_ok=True)
        out_path = endpoint_dir / f"{canonical_date}.csv"

        if name == "last_updated_stamp" and ok_stamp:
            content = stamp_content
            ok, reason = True, "OK"
        else:
            ok, content, reason = fetch_csv(name, url)

        if ok:
            with open(out_path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            successes += 1
            rel_path = out_path.relative_to(REPO_ROOT)
            print(f"[OK]   {name:<24} -> {rel_path}")
        else:
            failures += 1
            print(f"[FAIL] {name:<24} -> {reason}", file=sys.stderr)

        log_rows.append({
            "run_timestamp_utc": run_timestamp.isoformat(),
            "date": canonical_date,
            "endpoint": name,
            "url": url,
            "success": ok,
            "reason": reason,
            "output_file": str(out_path.relative_to(REPO_ROOT)) if ok else "",
        })

    # Append to master log
    write_header = not MASTER_LOG.exists()
    with open(MASTER_LOG, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=log_rows[0].keys())
        if write_header:
            writer.writeheader()
        writer.writerows(log_rows)

    print(f"\nDone: {successes} succeeded, {failures} failed. Log: {MASTER_LOG.relative_to(REPO_ROOT)}")

    # 3. Optional automated integration
    if args.integrate and successes > 0:
        print("\n--- Triggering dataset integration ---")
        import integrate_alibra_feed
        integrate_alibra_feed.main()

if __name__ == "__main__":
    main()
