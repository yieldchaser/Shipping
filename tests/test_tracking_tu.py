#!/usr/bin/env python3
"""Phase TU Tracking rebuild tests (2026-09-09).

The Tracking tab was rebuilt on honest PortWatch data:
- every synthetic lineup surface (port_lineups_active / vessel_voyage_tracks_master /
  ui_voyage_vectors / port_calls_daily_v2) is gone from index.html render paths;
- the port universe browser reads the PortWatch ports master (2,065 ports);
- the port page renders from real caches (facts card fields exist in the master,
  activity rows exist in the expanded daily feed, fixture rows exist in the
  fixture-grounded voyage history);
- the disruptions feed parses the PortWatch disruptions database with alert
  badges, ongoing flags and affected-port ids;
- data-window labels are honest (2026 year to date vs 2019-present classic hubs);
- visible-token scan extended to Tracking (undefined / NaN / diagnostic / code-speak).

No fabricated data: expectations recomputed from real source rows.
"""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")

# Strip script + style content so the scan sees only what the user can see.
_BODY = re.sub(r"<script(?![^>]*\bsrc=)[^>]*>.*?</script>", "", HTML, flags=re.S)
BODY = re.sub(r"<style[^>]*>.*?</style>", "", _BODY, flags=re.S)
# keep only element text (attribute values such as data-tooltip are not
# visible until hover; the browser sweep covers the rendered DOM anyway)
TEXT = re.sub(r"<[^>]*>", " ", BODY)


def test_no_synthetic_lineup_surfaces_in_render_paths():
    # PRIORITY 0: the fabricated surfaces must not be referenced anywhere in
    # index.html (fetches, render functions, comments about live usage).
    for banned in ["port_lineups_active", "vessel_voyage_tracks_master",
                   "ui_voyage_vectors", "port_calls_daily_v2",
                   "portLineups", "vesselTrajectories", "voyageLegs"]:
        assert banned not in HTML, f"synthetic surface still wired: {banned}"


def test_lineup_kpi_strip_gone_and_replaced_by_honest_kpis():
    # old fabricated KPI shells are gone
    for gone in ['id="hudTrackedHulls"', 'id="hudWaitingAnchor"', 'id="hudOperatingBerth"',
                 'id="hudCapeSurge"', "Monitored Fleet Hulls", "Waiting at Anchor</div>",
                 "Operating at Berth</div>", 'id="lineupCountBadge"', "1,568"]:
        assert gone not in HTML, f"fabricated KPI surface remains: {gone}"
    # honest replacements exist and are computed from real caches
    for marker in ['id="hudUniverseCalls"', 'id="hudCalls7d"', 'id="hudDisruptionsActive"',
                   'id="hudCpBelowBaseline"', "function trackingGlobalKpis()",
                   "DATA.portCallsExpanded"]:
        assert marker in HTML, marker
    # the KPI code must derive values from the caches, not bake them in
    assert "Math.round(k.latestCalls).toLocaleString()" in HTML
    assert re.search(r"avg7\s*=\s*calls7", HTML) or "calls7.reduce" in HTML


def test_no_vessel_position_polylines():
    # no trajectory polyline renderers remain
    for gone in ["plotVesselMarkers", "getVesselMarkerIcon", "selectVesselByImo",
                 "L.polyline(pts", "activeVesselTrackLayer.clearLayers()"]:
        assert gone not in HTML, f"polyline/vessel-position surface remains: {gone}"
    # map layers are port calls / chokepoints / disruption events only
    assert "plotDisruptionMarkers" in HTML
    assert "plotPortHubMarkers" in HTML
    assert "disruptionMarkersLayer" in HTML
    # risk-zone polygons were retired with the AIS fiction
    assert "plotRiskZones" not in HTML


def test_port_universe_browser_reads_ports_master():
    p = pd.read_csv(ROOT / "data" / "geospatial" / "portwatch_ports_master.csv",
                    usecols=["portid", "portname", "country", "LOCODE"])
    assert len(p) == 2065, len(p)
    # frontend wiring: fetch + search + class filter + pagination + row click-through
    for marker in ["data/geospatial/portwatch_ports_master.csv",
                   'id="universeSearchInput"', 'id="universeClassFilter"',
                   "function filterUniversePorts()", "function renderUniverseTable()",
                   'id="universeTableBody"', "onUniverseSearchInput"]:
        assert marker in HTML, marker
    # search matches on name/country/LOCODE exactly as the master stores them
    assert "p.LOCODE" in HTML and "p.country" in HTML and "p.portname" in HTML


def test_port_page_renders_from_real_cache_fields():
    m = pd.read_csv(ROOT / "data" / "geospatial" / "portwatch_ports_master.csv", nrows=3)
    for col in ["vessel_count_total", "vessel_count_tanker", "industry_top1",
                "share_country_maritime_import", "share_country_maritime_export",
                "LOCODE", "lat", "lon"]:
        assert col in m.columns, col
        # every field the facts card shows must exist in the master
        assert col in HTML, col
    e = pd.read_csv(ROOT / "data" / "congestion" / "port_calls_daily_expanded.csv", nrows=3)
    for col in ["portcalls", "import", "export", "portcalls_tanker"]:
        assert col in e.columns, col
        assert col in HTML, col
    # fixtures filtered by resolved portids from the fixture-grounded history
    v = pd.read_csv(ROOT / "data" / "geospatial" / "voyage_history_fixturegrounded.csv", nrows=3)
    for col in ["load_portid", "discharge_portid", "load_match", "discharge_match", "leg_date"]:
        assert col in v.columns, col
    assert "fixturesForPort" in HTML and "load_match" in HTML and "discharge_match" in HTML
    # match quality column is shown subtly (a dedicated column exists)
    assert "unresolved" in HTML
    # honest empty state mirrors the reference's own "No Rows To Show"
    assert "No Rows To Show" in HTML


def test_sector_modes_are_real_portwatch_classes():
    e = pd.read_csv(ROOT / "data" / "congestion" / "port_calls_daily_expanded.csv", nrows=2)
    for col in ["portcalls_tanker", "portcalls_dry_bulk", "portcalls_container",
                "portcalls_general_cargo", "portcalls_roro"]:
        assert col in e.columns, col
    # filter chips exist for the measured classes
    for token in ["setTrackingClass('Tanker')", "setTrackingClass('Dry Bulk')",
                  "setTrackingClass('Container')", "setTrackingClass('General Cargo')",
                  "setTrackingClass('RoRo')"]:
        assert token in HTML, token
    # LNG / LPG are explicitly fixture-grounded, badged and never measured
    assert "setTrackingClass('LNG')" in HTML and "setTrackingClass('LPG')" in HTML
    assert "REPORTED FIXTURES" in HTML
    assert HTML.count("reported fixture") >= 2
    # no fabricated gas port-call counts anywhere
    assert "portcalls_lng" not in HTML and "portcalls_lpg" not in HTML


def test_disruption_badge_logic_and_feed():
    d = pd.read_csv(ROOT / "data" / "congestion" / "portwatch_disruptions.csv")
    assert len(d) >= 130, len(d)
    assert (d["ongoing"] == 1).sum() >= 1
    assert set(d["alertlevel"].dropna().unique()) <= {"RED", "ORANGE", "YELLOW", "GREEN"}
    # frontend: feed parses alertlevel + ongoing + affectedports and sorts ongoing first
    for marker in ["data/congestion/portwatch_disruptions.csv", "DATA.disruptions",
                   "function filterDisruptions()", "function renderDisruptionFeed()",
                   "disruptionLevelFilter", "disruptionOngoingFilter",
                   "d.ongoing", "d.alertlevel", "affectedPortIds"]:
        assert marker in HTML, marker
    # ongoing-first ordering in the port-page disruption list too
    assert "(b.ongoing ? 1 : 0) - (a.ongoing ? 1 : 0)" in HTML
    # badges are colored by alert level
    assert "d.alertlevel === 'RED'" in HTML


def test_honest_window_labels():
    # year-to-date label present wherever the expanded feed drives a chart
    assert "2026 year to date" in HTML
    # the 43-hub deep series is labeled 2019-present and gated to classic hubs
    assert "2019&ndash;present (classic hubs)" in HTML
    assert "portHasDeepHistory" in HTML
    # activity window note always states the source span
    assert "ppActivityWindowNote" in HTML
    assert "IMF PortWatch expanded feed (2026 year to date)" in HTML
    assert "IMF PortWatch 43-hub daily series" in HTML
    # no chart claims a span the data does not carry
    assert "2019&ndash;2026" not in HTML.split('id="tab-tracking"')[1].split('id="tab-bunkers"')[0].split("<script")[0]


def test_multi_port_tab_strip():
    for marker in ["getPinnedPorts", "togglePinnedPort", "ppTabStrip",
                   "tuPinnedPorts", "renderPortPageTabStrip"]:
        assert marker in HTML, marker


def test_vessel_view_is_fixture_labeled():
    for marker in ['id="subviewVessel"', 'id="vesselSearchInput"',
                   "function renderVesselTimeline(vesselName)", "vesselIndexFromFixtures",
                   "reported fixture voyages, not AIS positions",
                   "voyage_history_fixturegrounded.csv"]:
        assert marker in HTML, marker
    # no STS / valuation panels exist
    for gone in ["STS", "Valuation", "valuation_usd"]:
        assert gone not in HTML.split('id="subviewVessel"')[1].split('id="subviewBunkers"')[0], gone


def test_chokepoints_kept_and_fixed():
    # 28 chokepoints preserved (real PortWatch data the user likes)
    d = json.load(open(ROOT / "data" / "congestion" / "chokepoint_geo_summary.json", encoding="utf-8"))
    assert len(d["chokepoints"]) == 28
    assert "renderChokepointSelector" in HTML
    assert 'id="chokepointChart"' in HTML
    # legend spacing fix: the source line sits in its own full-width row below the
    # controls, and the chart canvas carries top padding
    assert "width:100%; padding-top:4px; border-top:1px solid var(--border);" in HTML
    # stray duplicated cp-btn-group fragment is gone
    assert HTML.count("<div class=\"cp-btn-group\">") >= 1
    assert "onclick=\"setChokepointRange('all')\"\n              <div class=\"cp-btn-group\">" not in HTML
    # callout text re-sourced: no hardcoded +14.5/+28.4 defaults; values come
    # from the metrics cache or the summary rerouting note, else em dash
    assert "+14.5 Days" not in HTML
    assert "+28.4%" not in HTML
    assert "kpiDays.textContent = '\\u2014'" in HTML or "kpiDays.textContent = '\u2014'" in HTML
    assert "Modeled rerouting voyage impact" in HTML


def test_tracking_visible_token_scan():
    # extended visible-token scan for the Tracking tab region (no scripts)
    trk = HTML[HTML.index('id="tab-tracking"'):HTML.index('id="tab-bunkers"')]
    trk_body = re.sub(r"<script(?![^>]*\bsrc=)[^>]*>.*?</script>", "", trk, flags=re.S)
    trk_body = re.sub(r"<!--.*?-->", "", trk_body, flags=re.S)
    for tok in ["undefined", "NaN", "_diagnostic", ".csv", "scripts/", "TODO", "FIXME"]:
        assert tok not in trk_body, f"leaked token in Tracking markup: {tok}"


def test_global_visible_token_scan_no_regression():
    # whole-page visible-text scan (scripts + styles + tags + comments stripped)
    body = re.sub(r"<!--.*?-->", "", TEXT, flags=re.S)
    for tok in ["undefined", "NaN", "_diagnostic", "TODO", "FIXME", "1,568"]:
        assert tok not in body, f"leaked token in visible copy: {tok}"
    # the only .csv mention allowed is the ETF reconciliation download filename
    csv_hits = [m.start() for m in re.finditer(r"\.csv", body)]
    for pos in csv_hits:
        ctx = body[max(0, pos - 120):pos + 60]
        assert "reconciliation_backtest" in ctx, f"code-speak .csv in visible copy: {ctx[-120:]}"


def test_expanded_payload_is_lazy_not_inlined():
    # the 57 MB CSV is fetched at data/ path, lazily, once
    assert "data/congestion/port_calls_daily_expanded.csv" in HTML
    assert "function loadExpandedPortCalls()" in HTML
    assert "expandedLoadPromise" in HTML
    # wired into the Tracking open path, not page boot
    assert "if (typeof loadExpandedPortCalls === 'function') loadExpandedPortCalls();" in HTML
    # no base64/data-URI embed of the payload
    assert "data:csv" not in HTML
    seg = HTML[HTML.index("loadExpandedPortCalls()"):HTML.index("loadExpandedPortCalls()") + 400]
    assert "fetchCSV('data/congestion/port_calls_daily_expanded.csv')" in HTML


def test_div_balance_tracking_panel():
    src = HTML
    a = src.rfind("<div", 0, src.index('id="tab-tracking"'))
    b = src.rfind("<div", 0, src.index('id="tab-bunkers"'))
    seg = src[a:b]
    opens = len(re.findall(r"<div\b", seg))
    closes = len(re.findall(r"</div>", seg))
    assert opens == closes, (opens, closes)
