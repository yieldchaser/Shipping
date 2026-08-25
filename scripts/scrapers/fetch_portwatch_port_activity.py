#!/usr/bin/env python3
"""
IMF PortWatch Port Activity Engine (REAL DATA ONLY)
Pulls daily per-port observations (port calls by class, import/export tonnages)
from the IMF PortWatch public ArcGIS FeatureServer:
  https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Ports_Data/FeatureServer
Dataset catalog: https://portwatch.imf.org/ (Daily_Ports_Data, IMF PortWatch).

IMPORTANT PROVENANCE NOTE (2026-08-25 audit):
An earlier version of this file SYNTHESIZED waiting-time and anchorage-queue series
with a seeded random walk (np.random AR(1)). That output was removed from the
platform: waiting-days / vessels-at-anchorage are NOT published in the open
PortWatch feature service and are NOT fabricated here anymore. This engine now
writes only measured fields served by IMF PortWatch.

Outputs:
  data/congestion/port_calls_daily.csv        - real daily port calls + import/export kt
  data/congestion/portwatch_port_congestion.csv - DEPRECATED alias of the same real data
        (columns waiting_days_7dma / avg_waiting_days intentionally ABSENT).
"""
import json
import logging
import time
import urllib.parse
import urllib.request
import ssl
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "congestion"
DATA_DIR.mkdir(parents=True, exist_ok=True)

LAYER_URL = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/"
             "arcgis/rest/services/Daily_Ports_Data/FeatureServer/0/query")

# portid values verified against the live service (2026-08-25):
HUBS = {
    "port1069": "CNQDG",       # Qingdao Port, China
    "port824":  "CNNGB",       # Ningbo-Zhoushan, China
    "port944":  "CNNGB2",      # placeholder replaced during discovery if absent
    "AUPHE":    "AUPHE",
}

# Real hub portids discovered from the Ports database item / Daily_Ports_Data queries.
DISCOVERY_QUERIES = {
    "port1069": "Qingdao",
    "port824": "Ningbo",
}
FALLBACK_NAME_SEARCH = ["Caofeidian", "Hedland", "Newcastle", "Singapore", "Rotterdam", "Houston"]

FIELDS = ("date,portid,portname,country,portcalls,portcalls_dry_bulk,portcalls_tanker,"
          "portcalls_container,import_dry_bulk,export_dry_bulk,import_tanker,export_tanker,"
          "import_cargo,export_cargo")

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def _http_json(url: str, retries: int = 3) -> dict:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "shipping-dashboard/1.0"})
            with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"PortWatch query failed after {retries} attempts: {last}")


def discover_hub_portids() -> dict:
    """Resolve portid for each hub name via server-side LIKE query."""
    found = {}
    for name in list(DISCOVERY_QUERIES.values()) + FALLBACK_NAME_SEARCH:
        params = urllib.parse.urlencode({
            "f": "json", "where": f"portname LIKE '%{name}%'",
            "outFields": "portid,portname,country",
            "returnGeometry": "false", "resultRecordCount": "5",
        })
        try:
            d = _http_json(f"{LAYER_URL}?{params}")
            feats = d.get("features") or []
            if feats:
                a = feats[0]["attributes"]
                found[a["portid"]] = {"portname": a.get("portname"), "country": a.get("country")}
        except Exception as e:  # noqa: BLE001
            logging.warning("Discovery failed for %s: %s", name, e)
    return found


def fetch_port_history(port_id: str, max_records: int = 1000) -> list[dict]:
    """Fetch full daily history for one portid (paged at server max page size)."""
    rows: list[dict] = []
    offset = 0
    while True:
        params = urllib.parse.urlencode({
            "f": "json", "where": f"portid='{port_id}'",
            "outFields": FIELDS, "returnGeometry": "false",
            "orderByFields": "date ASC", "resultRecordCount": str(max_records),
            "resultOffset": str(offset),
        })
        d = _http_json(f"{LAYER_URL}?{params}")
        feats = d.get("features") or []
        rows += [f["attributes"] for f in feats]
        got = len(feats)
        if got == 0:
            break
        offset += got
        if not d.get("exceededTransferLimit") and got < max_records:
            break
    return rows


def main() -> pd.DataFrame:
    hubs = {}
    for pid, meta in discover_hub_portids().items():
        hubs[pid] = meta
    if not hubs:
        raise SystemExit("No hub ports resolved - aborting rather than writing synthetic data.")

    frames = []
    for pid, meta in hubs.items():
        logging.info("Fetching %s (%s)...", meta.get("portname"), pid)
        hist = fetch_port_history(pid)
        if not hist:
            # transient server behavior observed: retry once after a pause
            time.sleep(5)
            hist = fetch_port_history(pid)
        logging.info("  %d daily records", len(hist))
        df = pd.DataFrame(hist)
        if df.empty:
            continue
        df["hub_code"] = pid
        frames.append(df)

    if not frames:
        raise SystemExit("No data returned for any hub - aborting.")

    fresh = pd.concat(frames, ignore_index=True)

    # Upsert semantics: existing real observations are never downgraded by a
    # partial re-fetch (the FeatureServer occasionally serves short pages).
    prev_path = DATA_DIR / "port_calls_daily_v2.csv"
    if prev_path.exists():
        try:
            prev = pd.read_csv(prev_path, dtype={"portid": str})
            fresh = pd.concat([prev, fresh], ignore_index=True)
        except Exception as e:  # noqa: BLE001
            logging.warning("Could not merge previous file: %s", e)

    out = fresh.drop_duplicates(subset=["portid", "date"], keep="last").sort_values(["portid", "date"])
    keep = out.rename(columns={
        "portcalls": "daily_port_calls_total",
        "portcalls_dry_bulk": "daily_port_calls_dry_bulk",
        "portcalls_tanker": "daily_port_calls_tanker",
        "portcalls_container": "daily_port_calls_container",
    })
    # tonnages come as metric tons; report kilotonnes for chart scale
    for c in ("import_dry_bulk", "export_dry_bulk", "import_tanker", "export_tanker"):
        if c in keep.columns:
            keep[c + "_kt"] = (pd.to_numeric(keep[c], errors="coerce") / 1000.0).round(2)

    cols = ["date", "portid", "portname", "country", "hub_code",
            "daily_port_calls_total", "daily_port_calls_dry_bulk",
            "daily_port_calls_tanker", "daily_port_calls_container",
            "import_dry_bulk_kt", "export_dry_bulk_kt",
            "import_tanker_kt", "export_tanker_kt"]
    cols = [c for c in cols if c in keep.columns]
    keep = keep[cols].drop_duplicates(subset=["portid", "date"])

    # primary output: real measured fields only
    keep.to_csv(DATA_DIR / "port_calls_daily_v2.csv", index=False)
    # backward-compatible filename; same REAL data (no waiting-day columns)
    keep.to_csv(DATA_DIR / "portwatch_port_congestion.csv", index=False)
    logging.info("Wrote %d rows to %s and port_calls_daily_v2.csv", len(keep), "portwatch_port_congestion.csv")
    return keep


if __name__ == "__main__":
    main()
