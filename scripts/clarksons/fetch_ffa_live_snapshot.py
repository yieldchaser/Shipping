#!/usr/bin/env python3
"""
fetch_ffa_live_snapshot.py
==========================
Live dry-bulk FFA market snapshot for the Broker Desk forward strip.

Reads a public broker FFA screen (no login) for Capesize, Panamax, Supramax and
Handysize at five tenors (prompt month, next month, next quarter, the quarter
after, next calendar year). Each product carries two numbers:

  price       the screen's current market price, which moves during London
              trading hours (verified 2026-09-14: prices changed minute to minute)
  prevClose   the previous SGX settlement for that tenor (verified equal to our
              data/futures/sgx_*_futures.csv settlements; quarter/calendar tenors
              equal the average of their monthly settlements)

Writes data/clarksons/ffa_live_snapshot.json with the UTC fetch time. On any
failure it leaves the previous snapshot untouched and exits non-zero, so the
page keeps showing the last good snapshot with its real timestamp.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = REPO_ROOT / "data" / "clarksons" / "ffa_live_snapshot.json"

ENDPOINT = "https://api.braemarscreen.com/api/graphql"
QUERY = "{ brokerSite { ticker { name products { id name price prevClose } } } }"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Content-Type": "application/json",
}
SEGMENTS = {"Cape": ("cape", "CAPESIZE"), "Pmax": ("panamax", "PANAMAX"),
            "Smax": ("supramax", "SUPRAMAX"), "Handy": ("handysize", "HANDYSIZE")}


def tenor_label(name):
    return "Cal " + name[3:] if name.startswith("Cal") else name


def fetch():
    last_exc = None
    for _ in range(3):
        try:
            resp = requests.post(ENDPOINT, json={"query": QUERY}, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            body = resp.json()
            if body.get("errors"):
                raise RuntimeError(body["errors"])
            return body["data"]["brokerSite"]["ticker"]
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise RuntimeError(f"FFA screen unavailable: {last_exc}")


def build(ticker, fetched_at):
    segments = []
    for t in ticker:
        if t.get("name") not in SEGMENTS:
            continue
        key, label = SEGMENTS[t["name"]]
        tenors = []
        for p in t.get("products") or []:
            price, settle = float(p["price"]), float(p["prevClose"])
            if price <= 0 or settle <= 0:
                raise RuntimeError(f"non-positive price for {t['name']} {p.get('name')}")
            tenors.append({"name": tenor_label(p["name"]), "price": round(price, 2), "settle": round(settle, 2)})
        if not tenors:
            raise RuntimeError(f"no tenors for {t['name']}")
        segments.append({"key": key, "label": label, "tenors": tenors})
    if len(segments) != len(SEGMENTS):
        raise RuntimeError(f"expected {len(SEGMENTS)} segments, got {len(segments)}")
    return {
        "fetched_at_utc": fetched_at,
        "unit": "USD/day",
        "price_basis": "live market price at fetch time",
        "settle_basis": "previous SGX settlement (quarter and calendar tenors: average of monthly settlements)",
        "segments": segments,
    }


def main():
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        payload = build(fetch(), fetched_at)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}. Keeping the previous snapshot.", file=sys.stderr)
        return 1
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    cape = payload["segments"][0]["tenors"][0]
    print(f"FFA snapshot {fetched_at}: {payload['segments'][0]['label']} {cape['name']} {cape['price']:,.0f} (settle {cape['settle']:,.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
