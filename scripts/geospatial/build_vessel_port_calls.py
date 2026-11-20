#!/usr/bin/env python3
"""Rebuild data/views/signal/vessel_voyages_lookup.json from the AIS archive.

The Tracking tab's vessel drill-down ("Voyage History") reads this view, but
nothing in the repo wrote it any more: it stopped at 2026-09-25 while the AIS
archive (data/geospatial/history/ais_positions_YYYY_MM.parquet) kept growing.
This derives port calls from that archive. It is offline (no network).

Method, stated plainly so the UI can describe it:
- A port fix is an AIS position with status Moored / At Anchor, or speed
  <= 0.5 kn, within MAX_PORT_NM of a port in the PortWatch ports master.
- Consecutive port fixes at the same port are one call. Arrival / departure
  are the FIRST and LAST AIS fix seen at that port, so they bound the stay
  from inside (fixes are roughly weekly per vessel).
- Transit (d) = arrival at this call minus departure from the previous call;
  distance = great-circle nm between the two ports.
- The previous contents are NOT carried over: every one of its 19,529 legs
  had departure = arrival + 3 days exactly (synthetic), which the repo's
  no-fabrication rule rejects. The view now holds only AIS-observed calls
  within the archive window; it grows as the archive does.

Columns (unchanged): leg_id, portname, locode, arr, dep, days, dist_nm, lat, lon
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HIST = ROOT / "data" / "geospatial" / "history"
PORTS = ROOT / "data" / "geospatial" / "portwatch_ports_master.csv"
OUT = ROOT / "data" / "views" / "signal" / "vessel_voyages_lookup.json"
COLS = ["leg_id", "portname", "locode", "arr", "dep", "days", "dist_nm", "lat", "lon"]
MAX_PORT_NM = 12.0
PORT_STATUSES = {"Moored", "At Anchor"}
MONTHS_BACK = 6


def _hav_nm(lat1, lon1, lat2, lon2):
    r = 3440.065
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def load_archive(months_back=MONTHS_BACK) -> pd.DataFrame:
    files = sorted(HIST.glob("ais_positions_*.parquet"))[-months_back:]
    if not files:
        return pd.DataFrame()
    cols = ["timestamp", "imo", "lat", "lon", "speed", "status"]
    df = pd.concat([pd.read_parquet(f, columns=cols) for f in files], ignore_index=True)
    df = df.dropna(subset=["timestamp", "imo", "lat", "lon"])
    df["imo"] = df["imo"].astype("int64").astype(str)
    df["timestamp"] = df["timestamp"].astype("int64")
    df["status"] = df["status"].astype(str)
    df["speed"] = pd.to_numeric(df["speed"], errors="coerce")
    return df.drop_duplicates(["imo", "timestamp"]).sort_values(["imo", "timestamp"])


def load_ports() -> pd.DataFrame:
    p = pd.read_csv(PORTS, usecols=["portname", "lat", "lon", "LOCODE"])
    p = p.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    p["locode"] = p["LOCODE"].fillna("").astype(str).str.replace(" ", "", regex=False)
    return p


def nearest_port(lat, lon, ports, chunk=4000):
    plat = ports["lat"].to_numpy()[None, :]
    plon = ports["lon"].to_numpy()[None, :]
    idx = np.empty(len(lat), dtype=np.int64)
    dist = np.empty(len(lat))
    for s in range(0, len(lat), chunk):
        d = _hav_nm(lat[s:s + chunk, None], lon[s:s + chunk, None], plat, plon)
        j = d.argmin(axis=1)
        idx[s:s + chunk] = j
        dist[s:s + chunk] = d[np.arange(len(j)), j]
    return idx, dist


def derive_calls(df: pd.DataFrame, ports: pd.DataFrame) -> dict:
    at_port = df["status"].isin(PORT_STATUSES) | (df["speed"] <= 0.5)
    pf = df[at_port].copy()
    if pf.empty:
        return {}
    j, d = nearest_port(pf["lat"].to_numpy(), pf["lon"].to_numpy(), ports)
    pf["pidx"] = j
    pf = pf[d <= MAX_PORT_NM]
    calls = {}
    for imo, g in pf.groupby("imo", sort=False):
        out, cur = [], None
        for ts, pidx in zip(g["timestamp"].to_numpy(), g["pidx"].to_numpy()):
            if cur and cur["pidx"] == pidx:
                cur["last"] = ts
            else:
                cur = {"pidx": int(pidx), "first": int(ts), "last": int(ts)}
                out.append(cur)
        calls[imo] = out
    return calls


def to_rows(call_list, ports):
    rows = []
    for c in call_list:
        pr = ports.iloc[c["pidx"]]
        rows.append({
            "portname": str(pr["portname"]), "locode": pr["locode"],
            "arr": datetime.fromtimestamp(c["first"], timezone.utc).strftime("%Y-%m-%d"),
            "dep": datetime.fromtimestamp(c["last"], timezone.utc).strftime("%Y-%m-%d"),
            "lat": round(float(pr["lat"]), 2), "lon": round(float(pr["lon"]), 2),
        })
    return rows


def finalize(legs):
    """Renumber, and compute transit days / distance from the previous call."""
    out = []
    prev = None
    for i, L in enumerate(sorted(legs, key=lambda x: (x["arr"], x["dep"])), start=1):
        days, dist = 0, 0.0
        if prev is not None:
            try:
                days = max(0, (datetime.fromisoformat(L["arr"]) - datetime.fromisoformat(prev["dep"])).days)
            except ValueError:
                days = 0
            if prev.get("lat") is not None and L.get("lat") is not None:
                dist = round(float(_hav_nm(prev["lat"], prev["lon"], L["lat"], L["lon"])), 0)
        out.append([i, L["portname"], L["locode"], L["arr"], L["dep"], days, dist, L["lat"], L["lon"]])
        prev = L
    return out


def main():
    df = load_archive()
    if df.empty:
        print("No AIS archive; view left unchanged.")
        return
    ports = load_ports()
    calls = derive_calls(df, ports)
    window_start = datetime.fromtimestamp(int(df["timestamp"].min()), timezone.utc).strftime("%Y-%m-%d")
    as_of = datetime.fromtimestamp(int(df["timestamp"].max()), timezone.utc).strftime("%Y-%m-%d")

    vessels = {}
    for imo in calls:
        legs = to_rows(calls[imo], ports)
        if legs:
            vessels[imo] = finalize(legs)

    payload = {
        "as_of": as_of,
        "cols": COLS,
        "method": ("AIS port calls: Moored/At Anchor or <=0.5 kn within "
                   f"{MAX_PORT_NM:g} nm of a PortWatch port; arrival/departure = first/last fix at port"),
        "archive_window": [window_start, as_of],
        "vessels": vessels,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8", newline="\n")
    n_new = sum(len(v) for v in vessels.values())
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(vessels)} vessels, "
          f"{sum(len(v) for v in vessels.values())} legs ({n_new} AIS calls in {window_start}..{as_of}), "
          f"{OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
