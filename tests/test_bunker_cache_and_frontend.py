#!/usr/bin/env python3
"""
Unit and Integration Tests for Bunker Frontend Cache and Dashboard Integration
"""

import json
import os
import subprocess
import pytest

def test_bunker_frontend_summary_json_exists():
    path = "data/bunkers/bunker_frontend_summary.json"
    assert os.path.exists(path), f"Missing cache file: {path}"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "kpis" in data
    assert "ports" in data
    assert "forward_curves_12m" in data
    assert "physical_volumes" in data
    assert "scrubber_economics" in data
    assert "monthly_series" in data
    assert "daily_series" in data

    # Verify benchmark daily series
    daily_series = data["daily_series"]
    assert "Singapore" in daily_series
    assert "Rotterdam" in daily_series
    assert len(daily_series["Singapore"]) > 200
    assert "d" in daily_series["Singapore"][0]
    assert "vlsfo" in daily_series["Singapore"][0]

    # Verify 213 true physical ports + 6 composites + 2 macro benchmarks = 221 markets
    ports = data["ports"]
    assert len(ports) == 213, f"Expected 213 ports, got {len(ports)}"
    assert len(data.get("composites", [])) == 6, f"Expected 6 composites, got {len(data.get('composites', []))}"
    assert len(ports) + len(data.get("composites", [])) + len(data.get("macro_benchmarks", [])) == 221

    # Check key global hubs
    port_names = set(p["name"] for p in ports)
    assert "Singapore" in port_names
    assert "Rotterdam" in port_names
    assert "Houston" in port_names
    assert "Fujairah" in port_names

    # Verify coordinates exist on all ports
    for p in ports:
        assert "lat" in p and "lon" in p
        assert isinstance(p["lat"], (int, float))
        assert isinstance(p["lon"], (int, float))
        assert -90 <= p["lat"] <= 90
        assert -180 <= p["lon"] <= 180

    # Verify KPIs
    kpis = data["kpis"]
    assert kpis["global_vlsfo"] > 0
    assert kpis["global_hsfo"] > 0
    assert kpis["global_mgo"] > 0
    assert kpis["singapore_hi5"] > 0
    assert kpis["eu_ets_carbon_eur"] > 0
    assert kpis["singapore_monthly_vol_mt"] > 1000000

def test_bunker_kpis_live_chg_provenance():
    """Wave-1: KPI levels/deltas derived from owned CSVs, never stale hardcodes."""
    import csv
    with open("data/bunkers/bunker_frontend_summary.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    kpis = data["kpis"]
    for field in ["global_vlsfo_chg", "global_hsfo_chg", "global_mgo_chg",
                  "singapore_hi5_chg", "global_obs", "global_prev_obs",
                  "hi5_obs", "hi5_prev_obs", "singapore_vol_period"]:
        assert field in kpis, f"Missing live KPI field: {field}"

    # Cross-check global composite vs bunker_prices_daily.csv latest/prev obs
    rows = list(csv.DictReader(open("data/bunkers/bunker_prices_daily.csv")))
    g = [r for r in rows if r["port"] == "global_average_bunker_price"]
    dates = sorted(set(r["date"] for r in g))
    px = {(r["date"], r["fuel_grade"]): float(r["price_usd_mt"]) for r in g}
    latest, prev = dates[-1], dates[-2]
    assert kpis["global_obs"] == latest
    assert kpis["global_vlsfo"] == px[(latest, "VLSFO")]
    assert kpis["global_mgo"] == px[(latest, "MGO")]
    assert kpis["global_hsfo"] == px[(latest, "IFO380")]
    assert kpis["global_vlsfo_chg"] == round(px[(latest, "VLSFO")] - px[(prev, "VLSFO")], 2)
    assert kpis["global_mgo_chg"] == round(px[(latest, "MGO")] - px[(prev, "MGO")], 2)
    assert kpis["global_hsfo_chg"] == round(px[(latest, "IFO380")] - px[(prev, "IFO380")], 2)

    # Cross-check Singapore monthly volume + YoY vs physical volumes CSV
    vol = list(csv.DictReader(open("data/bunkers/bunker_physical_sales_volumes.csv")))
    sgm = sorted([r for r in vol if r["port"] == "Singapore" and r["metric"] == "Sales_Monthly_MT"],
                 key=lambda r: r["period"])
    assert kpis["singapore_monthly_vol_mt"] == float(sgm[-1]["volume_mt"])
    assert kpis["singapore_vol_period"] == sgm[-1]["period"]

def test_bunker_bix_coverage():
    """Wave-1: BIX strip source — 150 rows, 5 indices x 3 grades, change/high/low present."""
    with open("data/bunkers/bunker_frontend_summary.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    bix = data["benchmarks_bix"]
    assert len(bix) == 150, f"Expected 150 BIX rows, got {len(bix)}"
    assert set(x["index"] for x in bix) == {"BIX_World", "BIX_World3", "BIX_APAC", "BIX_EMEA", "BIX_Americas"}
    assert set(x["grade"] for x in bix) == {"VLSFO", "IFO380", "MGO"}
    for r in bix:
        for field in ["date", "index", "grade", "price", "change", "change_pct", "low", "high"]:
            assert field in r, f"BIX row missing {field}"
        assert r["price"] > 0 and r["low"] > 0 and r["high"] >= r["low"]

def test_bunker_altfuels_no_zerofill():
    """Wave-1 & Prompt 06: LNG/MEOH parsed in ports; EUA in macro benchmarks; nulls are None, never 0-filled."""
    with open("data/bunkers/bunker_frontend_summary.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    ports = data["ports"]
    for key in ["lng", "meoh"]:
        nn = [p for p in ports if p.get(key) is not None]
        assert len(nn) >= 1, f"No verified {key.upper()} indications"
        for p in nn:
            assert p[key] > 0, f"{key} zero-filled at {p['name']}"
    # EUA verified in macro_benchmarks (moved out of port table per Prompt 06 §6.1)
    macros = data.get("macro_benchmarks", [])
    assert any(m["name"] == "EUA" for m in macros), "Missing EUA in macro_benchmarks"
    for p in ports:
        for key in ["lng", "meoh", "eua", "bio"]:
            assert p.get(key) is None or p[key] > 0, f"{key} invalid at {p['name']}: {p.get(key)}"

def test_bunker_coverage_honesty():
    """Coverage-driven daily series: every port with >=120 trailing observations
    earns a daily series (180/221 as of 2026-09); the rest stay monthly-only.
    Floor guards against coverage regressions; volumes SG+RTM only."""
    with open("data/bunkers/bunker_frontend_summary.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    n_ports = len(data["ports"])
    n_daily = len(data["daily_series"])
    assert n_ports == 213
    assert n_daily >= 170, f"Daily-series coverage regressed: {n_daily}/221"
    assert n_daily < n_ports + 6, "monthly-only fallback must remain for sparse ports"
    assert {"Singapore", "Rotterdam"}.issubset(set(data["physical_volumes"].keys()))
    assert len(data["forward_curves_12m"]) == 6

def test_build_bunker_cache_script():
    script_path = "scripts/bunkers/build_bunker_cache.py"
    assert os.path.exists(script_path), f"Missing build script: {script_path}"
    
    # Run script and ensure exit code 0
    res = subprocess.run(["python", script_path], capture_output=True, text=True)
    assert res.returncode == 0, f"Script failed with output: {res.stderr}"
    assert "Successfully generated" in res.stdout

def test_index_html_bunkers_integration():
    with open("index.html", "r", encoding="utf-8") as f:
        c = f.read()

    # Verify tab button and panel
    assert '<button class="tab-btn" data-tab="bunkers">Bunkers</button>' in c
    assert '<div class="tab-panel" id="tab-bunkers">' in c
    assert '<div id="bunkerGeoMap"' in c
    assert '<canvas id="bunkerMainChart"' in c

    # Verify all 4 subviews
    assert 'id="bunkersSubviewSpot"' in c
    assert 'id="bunkersSubviewForward"' in c
    assert 'id="bunkersSubviewVolumes"' in c
    assert 'id="bunkersSubviewScrubber"' in c

    # Verify dynamic tooltip support
    assert "type === 'bunker-kpi'" in c
    assert "type === 'bunker-port-cell'" in c
    assert "type === 'bunker-fwd-cell'" in c
    assert "type === 'bunker-scrubber-cell'" in c
    assert "type === 'tracking-hud'" in c

    # Verify data pipeline wiring
    assert "bunkerSummary: null" in c
    assert "data/bunkers/bunker_frontend_summary.json" in c
    assert "renderBunkersTab()" in c

def test_index_html_bunkers_wave1():
    """Wave-1 rebuild markers: one-truth sync, BIX strip, alt fuels, live deltas,
    MoM fallback, selected-row fix, honesty labels, BNKR idiom."""
    with open("index.html", "r", encoding="utf-8") as f:
        c = f.read()

    # (1) legacy Tracking mini-view synced to one truth
    assert "ONE-TRUTH SYNC" in c
    assert "synced from BUNKERS tab" in c
    # (2) BIX benchmark strip/chart from benchmarks_bix
    assert 'id="bunkerBixStrip"' in c
    assert 'id="bunkerBixChart"' in c
    assert "renderBunkersBixStrip" in c
    assert "benchmarks_bix" in c
    # (3) alt-fuel subview, non-null only, never zero-filled
    assert 'id="bunkersSubviewAltfuels"' in c
    assert 'id="bunkersAltFuelsTableBody"' in c
    assert "renderBunkersAltFuels" in c
    assert "never zero-filled" in c
    # (4) live KPI deltas from kpis chg fields
    assert "bunkerKpiVlsfoSub" in c and "global_vlsfo_chg" in c
    assert "singapore_vol_period" in c
    # (5) spot deltas + sparklines with labeled MoM fallback
    assert "bunkerPortDelta" in c and "bunkerSpark12M" in c
    assert "MoM*" in c
    # (6) selected-row CSS fix (border-left on <tr> is dead under border-collapse)
    assert ".bunkers-port-row.selected td" in c
    assert "box-shadow: inset 3px 0 0 var(--accent)" in c
    # (7) honest coverage labels
    assert "2 PORTS ONLY" in c
    assert "MONTHLY FALLBACK" in c
    assert "monthly-only" in c
    # (8) BNKR HUD idiom distinct from tracking
    assert "bnkr-tag" in c
    assert "BNKR" in c


def test_index_html_bunkers_phase_b():
    """Phase B: provenance debug bar purged, full BIX archive chart with
    region/grade selectors, regional movers table, honest archive badge,
    dynamic tooltips on every Bunkers control, no code-speak in visible UI."""
    with open("index.html", "r", encoding="utf-8") as f:
        c = f.read()

    # (1) PROVENANCE debug bar fully gone (markup + css), EUA disclosure in tooltip
    assert 'class="bunkers-prov"' not in c
    assert "PROVENANCE \u00b7 levels" not in c
    assert "EUA level is a static screening assumption" in c
    # (2) BIX archive chart: full bix_history archive, not the trailing window
    assert "DATA.bunkerSummary.bix_history" in c or "summary.bix_history" in c
    assert "bunkerBixArchBadge" in c
    assert "accumulates with each daily harvest" in c
    assert "no observations in the archive yet" in c
    for fn in ["setBixChartRegion", "setBixChartGrade", "renderBunkerBixChart",
               "renderBunkersBixMovers"]:
        assert fn in c, f"missing {fn}"
    for region in ["World", "World3", "APAC", "EMEA", "Americas", "MidGulf"]:
        assert f'data-bixregion="{region}"' in c
    for grade in ["VLSFO", "IFO380", "MGO"]:
        assert f'data-bixgrade="{grade}"' in c
    # (3) regional movers table populated from cache, latest obs + changes
    assert 'id="bunkerBixMoversBody"' in c
    assert "bix-movers-cell" in c
    # (4) dynamic tooltips on every Bunkers control
    for tt in ["bunker-region-btn", "bunker-grade-btn", "bunker-subtab",
               "bunker-search", "bunker-forward-hub", "bunker-vol-hub",
               "bunker-map-pin", "bix-chip", "bix-region-card", "bix-region-btn",
               "bix-grade-btn", "bix-chart", "bix-archive-badge", "bix-movers",
               "bix-movers-row", "bix-movers-cell"]:
        assert f'"{tt}"' in c, f"missing tooltip branch/type {tt}"
    # (5) code-speak swept from visible UI
    assert "Source: benchmarks_bix[] via" not in c
    assert "\u0394 = change_usd (change_pct)" not in c
    assert "ports[].lng/.meoh/.eua/.bio" not in c


def test_index_html_tab_nesting_regression():
    """9dd8432e5 shipped an unmatched <div class=tracking-workstation> that made
    #tab-bunkers/#tab-offshore children of the hidden tracking panel (zero
    height on render). Guard: each top-level tab panel closes before the next opens."""
    with open("index.html", "r", encoding="utf-8") as f:
        c = f.read()
    assert "</div><!-- /tracking-workstation -->" in c
    import re
    # Bunkers panel must not appear inside the tracking panel span
    trk = c.index('id="tab-tracking"')
    trk_end = c.index("<!-- /tab-tracking -->", trk)
    bix = c.index('id="tab-bunkers"')
    off = c.index('id="tab-offshore"')
    assert not (trk < bix < trk_end), "tab-bunkers nested inside tab-tracking"
    assert not (trk < off < trk_end), "tab-offshore nested inside tab-tracking"
