#!/usr/bin/env python3
"""
Fetch ground-truth monthly export records from MDIC ComexStat API (2017-01 to 2026-08)
for all 5 commodities in 3-year chunks with robust retry/backoff on 429.
"""
import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = REPO_ROOT / "data" / "commodities" / "brazil_comexstat_exports.csv"

URL = "https://api-comexstat.mdic.gov.br/general"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

COMMODITY_NCMS = {
    "Iron Ore": ["26011100"],
    "Crude Oil": ["27090010"],
    "Soybeans": ["12011000", "12019000"],
    "Raw Sugar": ["17011300", "17011400"],
    "Corn": ["10059010"],
}

CHUNKS = [
    ("2017-01", "2019-12"),
    ("2020-01", "2022-12"),
    ("2023-01", "2025-12"),
    ("2026-01", "2026-08")
]

def query_comexstat(from_ym: str, to_ym: str, ncms: list[str]) -> list[dict]:
    payload = {
        "flow": "export",
        "monthDetail": True,
        "period": {"from": from_ym, "to": to_ym},
        "filters": [{"filter": "ncm", "values": ncms}],
        "metrics": ["metricFOB", "metricKG"]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
    )
    
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=45, context=_CTX) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res.get("data", {}).get("list", [])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = 10 * (2 ** attempt)
                print(f"HTTP 429 Rate Limited. Backing off for {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"HTTP Error {e.code}: {e.reason}")
                time.sleep(5)
        except Exception as e:
            print(f"Network error: {e}")
            time.sleep(5)
    return []

def main():
    api_records = {} # (commodity, "YYYY-MM") -> {"metric_tonnes": float, "fob_usd": float, "payload": dict, "retrieved_at": str}
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for cmd, ncms in COMMODITY_NCMS.items():
        print(f"\n--- Fetching {cmd} (NCM {ncms}) ---")
        for from_ym, to_ym in CHUNKS:
            print(f"Querying {cmd} {from_ym} to {to_ym}...")
            chunk_payload = {
                "flow": "export",
                "monthDetail": True,
                "period": {"from": from_ym, "to": to_ym},
                "filters": [{"filter": "ncm", "values": ncms}],
                "metrics": ["metricFOB", "metricKG"]
            }
            items = query_comexstat(from_ym, to_ym, ncms)
            print(f"  Received {len(items)} monthly records.")
            for it in items:
                ym = f"{it['year']}-{int(it['monthNumber']):02d}"
                kg = float(it["metricKG"])
                fob = float(it["metricFOB"])
                tonnes = kg / 1000.0
                api_records[(cmd, ym)] = {
                    "metric_tonnes": tonnes,
                    "fob_usd": fob,
                    "request_payload": chunk_payload,
                    "retrieved_at": now_str
                }
            time.sleep(2.0)

    print(f"\nTotal API records harvested: {len(api_records)}")
    
    # Save cache of raw API harvest
    out_cache = REPO_ROOT / "data" / "reference" / "comexstat_api_harvest_2017_2026.json"
    cache_serializable = {
        f"{k[0]}|{k[1]}": v for k, v in api_records.items()
    }
    with open(out_cache, "w", encoding="utf-8") as f:
        json.dump(cache_serializable, f, indent=2)
    print(f"Saved raw harvest to {out_cache}")

if __name__ == "__main__":
    main()
