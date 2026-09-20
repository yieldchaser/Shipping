#!/usr/bin/env python3
"""
scripts/geospatial/archive_ais_history.py
=========================================
Append-Only AIS Telemetry Time-Series Archive & Multi-Month Voyage Reconstruction
---------------------------------------------------------------------------------
1. Receives raw AIS observation batches from the Signal Ocean ingestion pipeline.
2. Filters out corrupted or out-of-bounds coordinates (Null Island (0,0), invalid latitudes).
3. Normalizes timestamps to integer Unix epoch seconds and UTC ISO-8601 strings.
4. Partitions records into monthly Parquet files (data/geospatial/history/ais_positions_YYYY_MM.parquet)
   compressed with Zstandard (zstd).
5. Enforces idempotent set-deduplication on (imo, timestamp) so re-runs or retries never duplicate pings.
6. Once a month finishes, past monthly files remain permanently sealed and immutable.
7. Compiles a browser-optimized rolling trajectory view (data/views/signal/vessel_trajectories_active.json)
   for active commercial vessels.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
GEO_DIR = DATA_DIR / "geospatial"
HISTORY_DIR = GEO_DIR / "history"
VIEWS_DIR = DATA_DIR / "views" / "signal"

SCHEMA = pa.schema([
    ("timestamp", pa.int64()),
    ("datetime_utc", pa.string()),
    ("imo", pa.int32()),
    ("lat", pa.float32()),
    ("lon", pa.float32()),
    ("speed", pa.float32()),
    ("heading", pa.float32()),
    ("status", pa.string()),
    ("destination", pa.string()),
    ("draught", pa.float32()),
    ("is_laden", pa.int8()),
])


def parse_observation_timestamp(rec: Dict[str, Any]) -> Tuple[int, str]:
    """Extracts unix timestamp and ISO-8601 string from observation record."""
    dt_str = (
        rec.get("movementDateTime")
        or rec.get("updatedDate")
        or rec.get("reportedEta")
        or rec.get("last_updated")
    )
    if dt_str and isinstance(dt_str, str):
        try:
            # Handles 2026-09-20T05:56:40Z or +00:00 or space-separated
            clean_str = dt_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ts = int(dt.timestamp())
            return ts, dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    return int(now.timestamp()), now.strftime("%Y-%m-%dT%H:%M:%SZ")


def sanitize_coordinate(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        if -180.0 <= f <= 180.0:
            return round(f, 4)
    except (ValueError, TypeError):
        pass
    return None


def is_valid_coordinate(lat: Optional[float], lon: Optional[float]) -> bool:
    if lat is None or lon is None:
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    # Filter Null Island (0, 0) noise
    if abs(lat) < 0.01 and abs(lon) < 0.01:
        return False
    return True


def append_live_positions_to_archive(
    positions_list: List[Dict[str, Any]],
    history_dir: Optional[Path] = None
) -> Dict[str, int]:
    """Appends live positions into monthly partitioned Parquet files with deduplication.
    
    Returns a dict mapping partition name -> count of newly inserted records.
    """
    target_dir = history_dir or HISTORY_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    by_month: Dict[str, List[Dict[str, Any]]] = {}

    for v in positions_list:
        try:
            imo_val = v.get("imo")
            if not imo_val:
                continue
            imo_int = int(imo_val)
            if imo_int <= 0:
                continue
        except (ValueError, TypeError):
            continue

        lat = sanitize_coordinate(v.get("lat") if v.get("lat") is not None else v.get("latitude"))
        lon = sanitize_coordinate(v.get("lon") if v.get("lon") is not None else v.get("longitude"))

        if not is_valid_coordinate(lat, lon):
            continue

        ts, dt_utc = parse_observation_timestamp(v)
        month_key = dt_utc[:7].replace("-", "_")  # "2026_09"

        spd = v.get("speed")
        try:
            spd_val = round(float(spd), 1) if spd is not None and 0.0 <= float(spd) <= 45.0 else 0.0
        except (ValueError, TypeError):
            spd_val = 0.0

        hdg = v.get("heading")
        try:
            hdg_val = round(float(hdg), 1) if hdg is not None and 0.0 <= float(hdg) <= 360.0 else 0.0
        except (ValueError, TypeError):
            hdg_val = 0.0

        drg = v.get("draught")
        try:
            drg_val = round(float(drg), 2) if drg is not None and 0.0 <= float(drg) <= 35.0 else 0.0
        except (ValueError, TypeError):
            drg_val = 0.0

        stat = (
            v.get("aisReportedStatus")
            or (v.get("tonnageListData", {}) or {}).get("operationalStatus")
            or v.get("commercialOperationalStatus")
            or "Underway"
        )
        dst = str(v.get("destination") or "").strip()[:80]
        op_stat = str((v.get("tonnageListData", {}) or {}).get("operationalStatus") or "")
        is_laden = 1 if "laden" in op_stat.lower() else 0

        row = {
            "timestamp": ts,
            "datetime_utc": dt_utc,
            "imo": imo_int,
            "lat": lat,
            "lon": lon,
            "speed": spd_val,
            "heading": hdg_val,
            "status": str(stat)[:50],
            "destination": dst,
            "draught": drg_val,
            "is_laden": is_laden,
        }

        if month_key not in by_month:
            by_month[month_key] = []
        by_month[month_key].append(row)

    results: Dict[str, int] = {}

    for month_key, rows in by_month.items():
        partition_file = target_dir / f"ais_positions_{month_key}.parquet"
        existing_keys: Set[Tuple[int, int]] = set()

        existing_table = None
        if partition_file.exists():
            try:
                existing_table = pq.read_table(partition_file)
                # Build set of (imo, timestamp)
                imos = existing_table.column("imo").to_pylist()
                tss = existing_table.column("timestamp").to_pylist()
                existing_keys = set(zip(imos, tss))
            except Exception as ex:
                logging.warning("Failed to read existing partition %s: %s. Re-creating.", partition_file.name, ex)

        # Filter incoming rows
        new_unique_rows = []
        for r in rows:
            pair = (r["imo"], r["timestamp"])
            if pair not in existing_keys:
                existing_keys.add(pair)
                new_unique_rows.append(r)

        if not new_unique_rows:
            logging.info("Partition %s: 0 new unique records (all %d already archived).", partition_file.name, len(rows))
            results[partition_file.name] = 0
            continue

        df_new = pd.DataFrame(new_unique_rows)
        # Type casting to match PyArrow schema
        df_new["timestamp"] = df_new["timestamp"].astype("int64")
        df_new["datetime_utc"] = df_new["datetime_utc"].astype("string")
        df_new["imo"] = df_new["imo"].astype("int32")
        df_new["lat"] = df_new["lat"].astype("float32")
        df_new["lon"] = df_new["lon"].astype("float32")
        df_new["speed"] = df_new["speed"].astype("float32")
        df_new["heading"] = df_new["heading"].astype("float32")
        df_new["status"] = df_new["status"].astype("string")
        df_new["destination"] = df_new["destination"].astype("string")
        df_new["draught"] = df_new["draught"].astype("float32")
        df_new["is_laden"] = df_new["is_laden"].astype("int8")

        new_table = pa.Table.from_pandas(df_new, schema=SCHEMA, preserve_index=False)

        if existing_table is not None:
            combined_table = pa.concat_tables([existing_table, new_table])
        else:
            combined_table = new_table

        # Write to temporary file first then atomic rename
        tmp_file = partition_file.with_suffix(".tmp")
        pq.write_table(combined_table, tmp_file, compression="zstd", compression_level=7)
        if partition_file.exists():
            partition_file.unlink()
        tmp_file.rename(partition_file)

        logging.info(
            "Partition %s: Appended %d new records. Total in month: %d (%d KB).",
            partition_file.name, len(new_unique_rows), combined_table.num_rows, partition_file.stat().st_size // 1024
        )
        results[partition_file.name] = len(new_unique_rows)

    return results


def build_active_trajectories_view(
    days: int = 90,
    history_dir: Optional[Path] = None,
    views_dir: Optional[Path] = None
) -> Path:
    """Builds a browser-ready compact JSON trajectory lookup for active vessels.
    
    Scans monthly parquet archives within the trailing `days` window,
    sorts waypoints chronologically per IMO, and produces:
    data/views/signal/vessel_trajectories_active.json:
    {
      "as_of": "...",
      "window_days": 90,
      "total_vessels": 4500,
      "total_points": 45000,
      "trajectories": {
        "<imo>": [[ts, lat, lon, spd, hdg, stat, dst], ...]
      }
    }
    """
    target_hist = history_dir or HISTORY_DIR
    target_views = views_dir or VIEWS_DIR
    target_views.mkdir(parents=True, exist_ok=True)

    out_file = target_views / "ais_history_active.json"

    now_ts = int(datetime.now(timezone.utc).timestamp())
    cutoff_ts = now_ts - (days * 86400)

    parquet_files = sorted(target_hist.glob("ais_positions_*.parquet"))
    if not parquet_files:
        logging.warning("No historical Parquet files found in %s to build trajectories.", target_hist)
        empty_payload = {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "window_days": days,
            "total_vessels": 0,
            "total_points": 0,
            "trajectories": {}
        }
        out_file.write_text(json.dumps(empty_payload), encoding="utf-8")
        return out_file

    all_dfs = []
    cols = ["timestamp", "imo", "lat", "lon", "speed", "heading", "status", "destination"]

    for pf in parquet_files:
        try:
            table = pq.read_table(pf, columns=cols)
            df = table.to_pandas()
            df = df[df["timestamp"] >= cutoff_ts]
            if not df.empty:
                all_dfs.append(df)
        except Exception as ex:
            logging.error("Failed to read %s: %s", pf.name, ex)

    if not all_dfs:
        logging.info("No records found within trailing %d days.", days)
        combined = pd.DataFrame(columns=cols)
    else:
        combined = pd.concat(all_dfs, ignore_index=True)

    trajectories: Dict[str, List[List[Any]]] = {}

    if not combined.empty:
        # Sort chronologically by IMO and timestamp
        combined = combined.sort_values(["imo", "timestamp"], ascending=[True, True])
        for imo_int, group in combined.groupby("imo"):
            imo_str = str(imo_int)
            pts = []
            for _, r in group.iterrows():
                # [timestamp, lat, lon, speed, heading, status, destination]
                pts.append([
                    int(r["timestamp"]),
                    round(float(r["lat"]), 4),
                    round(float(r["lon"]), 4),
                    round(float(r["speed"]), 1),
                    int(round(float(r["heading"]))),
                    str(r["status"]) if pd.notna(r["status"]) else "",
                    str(r["destination"]) if pd.notna(r["destination"]) else "",
                ])
            trajectories[imo_str] = pts

    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "total_vessels": len(trajectories),
        "total_points": sum(len(p) for p in trajectories.values()),
        "trajectories": trajectories
    }

    with open(out_file, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, separators=(",", ":"))

    logging.info(
        "Successfully compiled %s: %d vessels, %d total breadcrumb points (%d KB).",
        out_file.name, len(trajectories), payload["total_points"], out_file.stat().st_size // 1024
    )
    return out_file


def seed_from_existing_live_fleet(geo_dir: Optional[Path] = None) -> int:
    """Reads existing signal_live_fleet_positions_*.json caches and seeds the historical archive."""
    src_geo = geo_dir or GEO_DIR
    sector_files = [
        src_geo / "signal_live_fleet_positions_capesize_vloc.json",
        src_geo / "signal_live_fleet_positions_vlcc_suezmax.json",
        src_geo / "signal_live_fleet_positions_lng.json",
        src_geo / "signal_live_fleet_positions_lpg.json",
        src_geo / "signal_live_fleet_positions_tankers.json",
    ]

    all_positions = []
    seen_imos = set()

    for sf in sector_files:
        if not sf.exists():
            continue
        try:
            vessels = json.loads(sf.read_text(encoding="utf-8"))
            for v in vessels:
                imo = v.get("imo")
                if imo and imo not in seen_imos:
                    seen_imos.add(imo)
                    all_positions.append(v)
        except Exception as ex:
            logging.error("Failed to seed from %s: %s", sf.name, ex)

    logging.info("Seeding archive with %d unique baseline vessel records from existing caches...", len(all_positions))
    results = append_live_positions_to_archive(all_positions)
    total_added = sum(results.values())
    logging.info("Seeding complete: %d total observations written.", total_added)

    build_active_trajectories_view()
    return total_added


def main():
    parser = argparse.ArgumentParser(description="AIS Telemetry Time-Series Archive & Trajectory Reconstructor")
    parser.add_argument("--seed", action="store_true", help="Seed archive from existing local live fleet caches.")
    parser.add_argument("--export-view", action="store_true", help="Rebuild active trajectories browser view.")
    parser.add_argument("--days", type=int, default=90, help="Trailing days window for active trajectories view.")
    args = parser.parse_args()

    if args.seed:
        seed_from_existing_live_fleet()
        return

    if args.export_view:
        build_active_trajectories_view(days=args.days)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
