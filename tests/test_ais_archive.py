#!/usr/bin/env python3
"""
tests/test_ais_archive.py
=========================
Validates the append-only AIS telemetry historical archive:
1. Schema verification on monthly Parquet files.
2. Idempotent deduplication on (imo, timestamp).
3. Coordinate sanitization and rejection of Null Island (0,0) noise.
4. Trajectory reconstruction across multiple observation timestamps.
5. Generation and structure of vessel_trajectories_active.json.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
import pytest
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.geospatial.archive_ais_history import (
    append_live_positions_to_archive,
    build_active_trajectories_view,
    is_valid_coordinate,
    parse_observation_timestamp,
    HISTORY_DIR,
    VIEWS_DIR,
)


@pytest.fixture
def temp_archive_env(tmp_path):
    hist_dir = tmp_path / "history"
    views_dir = tmp_path / "views"
    hist_dir.mkdir(parents=True)
    views_dir.mkdir(parents=True)
    return hist_dir, views_dir


def test_valid_coordinate_filters():
    # Valid coordinates
    assert is_valid_coordinate(1.28, 103.85) is True  # Singapore
    assert is_valid_coordinate(-20.31, 118.57) is True  # Port Hedland

    # Invalid coordinates
    assert is_valid_coordinate(None, 100.0) is False
    assert is_valid_coordinate(50.0, None) is False
    assert is_valid_coordinate(95.0, 10.0) is False  # Out of latitude range
    assert is_valid_coordinate(10.0, 195.0) is False  # Out of longitude range
    assert is_valid_coordinate(0.0, 0.0) is False  # Null Island noise
    assert is_valid_coordinate(0.005, -0.002) is False  # Null Island near-zero noise


def test_parse_observation_timestamp():
    rec = {"movementDateTime": "2026-09-20T05:56:40Z"}
    ts, dt_utc = parse_observation_timestamp(rec)
    assert dt_utc == "2026-09-20T05:56:40Z"
    assert ts > 1700000000

    # Fallback to current time if missing
    rec_empty = {}
    ts_now, dt_now = parse_observation_timestamp(rec_empty)
    assert ts_now > 1700000000
    assert "T" in dt_now


def test_append_and_idempotency(temp_archive_env):
    hist_dir, views_dir = temp_archive_env

    sample_positions = [
        {
            "imo": 9418468,
            "vesselName": "Test Capesize",
            "lat": -20.31,
            "lon": 118.57,
            "speed": 12.5,
            "heading": 45.0,
            "destination": "QINGDAO",
            "movementDateTime": "2026-09-18T10:00:00Z",
            "aisReportedStatus": "Underway",
        },
        {
            "imo": 9418468,
            "vesselName": "Test Capesize",
            "lat": -18.50,
            "lon": 119.20,
            "speed": 13.0,
            "heading": 40.0,
            "destination": "QINGDAO",
            "movementDateTime": "2026-09-20T10:00:00Z",
            "aisReportedStatus": "Underway",
        },
        {
            "imo": 9500001,
            "vesselName": "Test VLCC",
            "lat": 1.25,
            "lon": 103.80,
            "speed": 0.1,
            "heading": 120.0,
            "destination": "SINGAPORE",
            "movementDateTime": "2026-09-20T12:00:00Z",
            "aisReportedStatus": "At Anchor",
        },
        # Invalid coordinate record (should be ignored)
        {
            "imo": 9999999,
            "lat": 0.0,
            "lon": 0.0,
            "movementDateTime": "2026-09-20T12:00:00Z",
        },
    ]

    # First append
    res1 = append_live_positions_to_archive(sample_positions, history_dir=hist_dir)
    assert "ais_positions_2026_09.parquet" in res1
    assert res1["ais_positions_2026_09.parquet"] == 3

    parquet_file = hist_dir / "ais_positions_2026_09.parquet"
    assert parquet_file.exists()

    table1 = pq.read_table(parquet_file)
    assert table1.num_rows == 3

    # Re-append same records -> must be completely idempotent (0 new)
    res2 = append_live_positions_to_archive(sample_positions, history_dir=hist_dir)
    assert res2["ais_positions_2026_09.parquet"] == 0

    table2 = pq.read_table(parquet_file)
    assert table2.num_rows == 3  # Count has not grown

    # Append fresh ping for existing vessel
    fresh_positions = [
        {
            "imo": 9418468,
            "vesselName": "Test Capesize",
            "lat": -15.20,
            "lon": 120.10,
            "speed": 13.2,
            "heading": 35.0,
            "destination": "QINGDAO",
            "movementDateTime": "2026-09-22T10:00:00Z",
            "aisReportedStatus": "Underway",
        }
    ]
    res3 = append_live_positions_to_archive(fresh_positions, history_dir=hist_dir)
    assert res3["ais_positions_2026_09.parquet"] == 1

    table3 = pq.read_table(parquet_file)
    assert table3.num_rows == 4

    # Build active trajectories view
    view_file = build_active_trajectories_view(days=90, history_dir=hist_dir, views_dir=views_dir)
    assert view_file.exists()

    view_data = json.loads(view_file.read_text(encoding="utf-8"))
    assert view_data["total_vessels"] == 2
    assert view_data["total_points"] == 4

    # Verify chronological ordering of Capesize trajectory
    capesize_pts = view_data["trajectories"]["9418468"]
    assert len(capesize_pts) == 3
    # Check ascending timestamp order
    assert capesize_pts[0][0] < capesize_pts[1][0] < capesize_pts[2][0]
    # Check coordinates
    assert capesize_pts[0][1] == -20.31
    assert capesize_pts[1][1] == -18.50
    assert capesize_pts[2][1] == -15.20


def test_production_archive_exists_and_populated():
    """Verify that Day-1 seeding succeeded in the real repository directory."""
    parquet_files = list(HISTORY_DIR.glob("ais_positions_*.parquet"))
    assert len(parquet_files) >= 1, "At least one monthly Parquet partition must exist in data/geospatial/history/"

    view_file = VIEWS_DIR / "ais_history_active.json"
    assert view_file.exists(), "ais_history_active.json must exist in data/views/signal/"

    view_data = json.loads(view_file.read_text(encoding="utf-8"))
    assert view_data["total_vessels"] > 1000
    assert view_data["total_points"] > 1000
