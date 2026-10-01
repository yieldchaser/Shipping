#!/usr/bin/env python3
"""
scripts/scrapers/sweep_drewry_fast.py
=====================================
Multi-threaded fast sweeper for Drewry AIS DAM PDF assets across all 10 vessel classes.
"""

import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://www.drewry.co.uk/AcuCustom/Sitename/DAM"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

VESSEL_CLASSES = [
    "Crude_Suezmax", "Crude_VLCC", "Crude_Aframax",
    "Drybulk_Panamax", "Drybulk_Capesize", "Drybulk_Supramax", "Drybulk_Handysize",
    "Product_LR2", "Product_LR1",
    "LPG_FR",
]

out_dir = ROOT / "corpus" / "06-drewry" / "ais"
out_dir.mkdir(parents=True, exist_ok=True)

existing_files = set(f.name for f in out_dir.glob("*.pdf"))

tasks = []
# Probe weeks 32 to 42 for 2026 across DAM 032 to 038
for dam in range(32, 39):
    for week in range(32, 42):
        for cls in VESSEL_CLASSES:
            fname = f"Drewry_AIS_{cls}_Week{str(week).zfill(2)}_2026.pdf"
            if fname not in existing_files:
                tasks.append((dam, week, cls, fname))

print(f"Total candidate probes: {len(tasks)}")

hits = []


def probe_task(item):
    dam, week, cls, fname = item
    url = f"{BASE}/{dam:03d}/{fname}"
    try:
        r = requests.head(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            return (dam, week, cls, fname, url)
    except Exception:
        pass
    return None


def main():
    if not tasks:
        print("All target Drewry AIS reports already present in corpus.")
        return

    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(probe_task, t) for t in tasks]
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                dam, week, cls, fname, url = res
                print(f"[HIT] DAM/{dam:03d} -> {fname}", flush=True)
                hits.append((dam, week, cls, fname, url))

    print(f"\nTotal hits found: {len(hits)}")

    # Download all hits
    downloaded = []
    for dam, week, cls, fname, url in hits:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                dest = out_dir / fname
                with open(dest, "wb") as f:
                    f.write(r.content)
                print(f"  [SAVED] {dest.name} ({len(r.content):,} bytes)")
                downloaded.append(dest)
        except Exception as e:
            print(f"  [ERROR] {fname}: {e}")

    print(f"\nFinished! Downloaded {len(downloaded)} new reports.")


if __name__ == "__main__":
    main()
