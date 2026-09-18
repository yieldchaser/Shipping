#!/usr/bin/env python3
"""
Test Suite: Predictive Freight Upgrade & Live Port Sentinel
===========================================================
Validates the implementation of Work Packages 1–4:
  - WP1: Live Port Sentinel (scripts/acquire/stream_sentinel.py & data/derived/live_anchorage_events.json)
  - WP2: Cryogenic Gas Sector Matrix Interceptor (scripts/derived/compute_gas_metrics.py & gas_port_arrivals.json)
  - WP3: Ultra-Fast Data Correlation Pipeline (scripts/congestion/build_predictive_signals.py & predictive_freight_signals.json)
  - WP4: Frontend UI Workstation Wiring in index.html
"""

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def test_wp1_sentinel_script_and_geofences():
    """Verify stream_sentinel.py exists and defines targeted geofences."""
    sentinel_path = ROOT / "scripts" / "acquire" / "stream_sentinel.py"
    assert sentinel_path.exists(), "stream_sentinel.py missing"
    
    src = sentinel_path.read_text(encoding="utf-8")
    for locode in ["AUHPT", "AUNCL", "BRTUB", "ZARCB", "IDSMR", "IDBDJ"]:
        assert locode in src, f"Target locode {locode} missing from sentinel"
    assert "wss://stream.aisstream.io/v0/stream" in src
    assert "AISSTREAM_API_KEY" in src

    # Verify output JSON cache
    events_file = ROOT / "data" / "derived" / "live_anchorage_events.json"
    assert events_file.exists(), "live_anchorage_events.json missing"
    data = json.loads(events_file.read_text(encoding="utf-8"))
    assert "events" in data
    assert "as_of" in data
    assert len(data["events"]) > 0
    sample = data["events"][0]
    for key in ["locode", "port_name", "vessel_name", "vessel_class", "speed_knots", "status"]:
        assert key in sample, f"Key {key} missing from live anchorage event"


def test_wp2_gas_sector_interceptor_and_summary_sync():
    """Verify compute_gas_metrics.py processes gas hulls and syncs into port_stress_summary.json."""
    gas_script = ROOT / "scripts" / "derived" / "compute_gas_metrics.py"
    assert gas_script.exists(), "compute_gas_metrics.py missing"

    gas_arrivals_file = ROOT / "data" / "derived" / "gas_port_arrivals.json"
    assert gas_arrivals_file.exists(), "gas_port_arrivals.json missing"
    data = json.loads(gas_arrivals_file.read_text(encoding="utf-8"))
    assert "total_gas_arrivals" in data
    assert data["total_gas_arrivals"] > 0
    assert len(data["ports"]) > 0

    # Verify port_stress_summary.json holds updated gas hubs
    stress_file = ROOT / "data" / "derived" / "port_stress_summary.json"
    assert stress_file.exists(), "port_stress_summary.json missing"
    stress_data = json.loads(stress_file.read_text(encoding="utf-8"))
    gas_hubs = [h for h in stress_data["hubs"] if h.get("asset_class") in ["LNG", "LPG"]]
    assert len(gas_hubs) == 23, f"Expected 23 Gas hubs, got {len(gas_hubs)}"
    for h in gas_hubs:
        assert "weekly_calls" in h
        assert "zscore" in h
        assert h["stress_flag"] in ["SURGE", "COLLAPSE", "NORMAL"]
        assert isinstance(h["zscore"], (int, float))


def test_wp3_predictive_signals_compiler_and_indices_correlation():
    """Verify build_predictive_signals.py produces valid predictive freight signals."""
    pred_script = ROOT / "scripts" / "congestion" / "build_predictive_signals.py"
    assert pred_script.exists(), "build_predictive_signals.py missing"

    pred_file = ROOT / "data" / "derived" / "predictive_freight_signals.json"
    assert pred_file.exists(), "predictive_freight_signals.json missing"
    pred_data = json.loads(pred_file.read_text(encoding="utf-8"))
    assert "metadata" in pred_data
    assert "summary" in pred_data
    assert "alerts" in pred_data
    assert "impacted_tickers" in pred_data["summary"]

    if pred_data["alerts"]:
        alert = pred_data["alerts"][0]
        for k in ["port_name", "locode", "asset_class", "zscore", "correlated_ticker", "signal_state", "projected_impact"]:
            assert k in alert, f"Key {k} missing from predictive alert"


def test_wp4_frontend_ui_wiring():
    """Verify index.html contains the predictive HUD badges, data loader, and Chart.js dual-axis."""
    # HUD badges and indicators
    assert 'id="hudPredictiveAlerts"' in HTML
    assert 'id="hudPredictiveAlertsSub"' in HTML
    assert 'id="hudPredictiveStrip"' in HTML
    assert 'id="hudPredictiveStripVal"' in HTML

    # Data fetcher in loadTrackingData
    assert "predictive_freight_signals.json" in HTML
    assert "DATA.predictiveSignals" in HTML

    # Subview 7 Chart.js dual-axis extension
    assert "yAxisID: 'y1'" in HTML
    assert "Correlated Baltic" in HTML
    assert "Baltic" in HTML and "Spot Index" in HTML
