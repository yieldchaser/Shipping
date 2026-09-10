"""Phase 1 backfill probe: fetch FULL history for the 11 dry-route tsIds + probe 7 stale MB tsIds.

Writes probe output to .hermes/dryroutes_probe.json for later use. Never fabricates data.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

TS_URL = "https://fearnpulse.com/api/marketapi/TS"
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ShippingRepoDryRoutes/1.0",
    "Origin": "https://fearnpulse.com",
    "Referer": "https://fearnpulse.com/",
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dryroutes_probe.json")

DRY_ROUTES = {
    120655: ("Capesize TCE Cont/Far East", "usd/day"),
    10002: ("Capesize Australia/China", "usd/tonne"),
    120654: ("Capesize Pacific RV", "usd/day"),
    10010: ("Panamax Transatlantic RV", "usd/day"),
    10011: ("Panamax TCE Cont/Far East", "usd/day"),
    10013: ("Panamax TCE Far East/Cont", "usd/day"),
    10012: ("Panamax TCE Far East RV", "usd/day"),
    120132: ("Supramax Transatlantic RV (raw A)", "usd/day"),
    120133: ("Supramax Transatlantic RV (raw B)", "usd/day"),
    120129: ("Supramax US Gulf - China/South Japan", "usd/day"),
    120137: ("Supramax South China - Indonesia RV", "usd/day"),
}
MB_STALE = {
    306: "Singapore 380CST",
    307: "Singapore MGO",
    303: "Rotterdam 380CST",
    304: "Rotterdam MGO",
    5002: "USD/NOK",
    5001: "USD/KRW",
    5003: "EUR/USD",
    12100: "SOFR",
    316: "Brent",
}


def fetch_all(tsid):
    r = requests.get(TS_URL, headers=HDRS, params={"id": tsid}, timeout=60)
    r.raise_for_status()
    payload = r.json()
    cols = payload.get("columns") or []
    data = payload.get("data") or []
    newest_first = all(
        data[i][2] >= data[i + 1][2] for i in range(len(data) - 1)
    )
    return cols, data, newest_first


def main():
    results = {}
    for tsid in list(DRY_ROUTES) + list(MB_STALE):
        try:
            cols, data, newest_first = fetch_all(tsid)
            # verify newest-first, reverse to chronological, dedupe by date keep last
            rows = list(data)
            rows.reverse()
            seen = {}
            for _tsid_c, value, epoch, _seq in rows:
                seen[epoch] = value
            epochs = sorted(seen)
            results[str(tsid)] = {
                "label": DRY_ROUTES.get(tsid, MB_STALE.get(tsid))[0],
                "columns": cols,
                "n_raw": len(data),
                "newest_first": newest_first,
                "n_dedup": len(seen),
                "dupes": len(data) - len(seen),
                "first_date": (
                    datetime.fromtimestamp(epochs[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    if epochs
                    else None
                ),
                "last_date": (
                    datetime.fromtimestamp(epochs[-1] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    if epochs
                    else None
                ),
                "last_value": seen[epochs[-1]] if epochs else None,
                "sample_pts": [[e, seen[e]] for e in epochs[-3:]],
            }
            print(f"tsId {tsid}: n_raw={len(data)} newest_first={newest_first} "
                  f"dedup={len(seen)} span={results[str(tsid)]['first_date']}..{results[str(tsid)]['last_date']}", flush=True)
            time.sleep(0.6)
        except Exception as e:
            results[str(tsid)] = {"error": str(e)}
            print(f"tsId {tsid}: ERROR {e}", flush=True)
            time.sleep(1.0)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print("saved", OUT)


if __name__ == "__main__":
    main()
