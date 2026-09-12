#!/usr/bin/env python3
"""
fetch_braemar_rates.py
======================
Polls Braemar ACM Shipbroking rates.

Note (Documented Gap per Prompt 18):
Braemar forward curves were captured via an unauthenticated GraphQL snapshot on
2026-09-10. Since then, the endpoint has moved / requires institutional auth.
This script attempts to reach the endpoint, and if unavailable or moved, preserves
the authoritative 2026-09-10 snapshot without fabricating data.
"""

import json
import os
import sys
from pathlib import Path
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = REPO_ROOT / "data" / "clarksons" / "braemar_live_rates.json"

BRAEMAR_ENDPOINT = "https://braemar.com/api/graphql"


def main():
    print(f"Checking Braemar ACM rates endpoint at {BRAEMAR_ENDPOINT}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }
    payload = {
        "query": "{ brokerSite { ticker { name products { id name price prevClose } } } }"
    }

    try:
        resp = requests.post(BRAEMAR_ENDPOINT, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data and "brokerSite" in data["data"]:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                print(f"Successfully updated {OUTPUT_FILE}")
                return
            else:
                print(f"[WARN] Unexpected GraphQL response structure: {data.keys()}")
        else:
            print(f"[WARN] Braemar endpoint returned HTTP {resp.status_code}")
    except Exception as e:
        print(f"[WARN] Could not connect to Braemar endpoint: {e}")

    # Fallback / Preserved snapshot
    if OUTPUT_FILE.exists():
        print(f"[INFO] Preserving existing authoritative Braemar snapshot (as of 2026-09-10) in {OUTPUT_FILE}")
    else:
        print(f"[ERROR] Authoritative snapshot not found at {OUTPUT_FILE}")
        sys.exit(1)


if __name__ == "__main__":
    main()
