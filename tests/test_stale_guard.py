#!/usr/bin/env python3
"""PHASE STALE self-heal gates (index.html).

A session-persistent tab that survives many deploys showed two failure classes:
old JS rendering against NEW data files, and canvases painted at zero size in a
hidden tab that then displayed garbled. Pins the self-heal mechanisms so they
cannot silently regress:

  - the build ETag watch (boot HEAD capture + 10-minute poll + non-blocking
    toast with a Reload button, and NEVER an auto-reload);
  - the canvas resilience path (visibilitychange repaint of the active tab,
    window.refreshVisibleCharts() helper the renderers funnel through, and a
    broken-canvas doctor that re-renders on detection);
  - fetch coherence (cache:'no-cache' on small meta/summary JSONs only; the big
    CSVs keep default caching);
  - the class-mix runtime guard (any raw 20+ char all-binary digit text node in
    the universe Class Mix column is rebuilt into the same mix-bar markup).
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(ROOT, "index.html")

with open(HTML_PATH, "r", encoding="utf-8") as f:
    C = f.read()


# ---------------------------------------------------------------- build ETag watch
def test_etag_boot_capture_and_10min_poll():
    assert "function initStaleGuard(" in C
    # boot-time HEAD of the document captures the served ETag
    assert "method: 'HEAD'" in C
    assert "window.__staleGuardBootEtag = bootEtag;" in C
    # 10-minute poll interval (not 1m, not 1h)
    m = re.search(r"POLL_MS = (\d+)", C)
    assert m, "ETag poll interval must be a named constant"
    assert int(m.group(1)) == 600000


def test_stale_toast_copy_and_reload_button():
    # non-blocking toast markup with the exact copy + Reload button
    assert 'id="staleBuildToast"' in C
    assert "Site updated: reload for the latest build" in C
    assert 'id="staleBuildReloadBtn"' in C
    assert "showStaleBuildToast()" in C
    # ETag change -> toast (never a silent reload)
    seg = C[C.index("var pollOnce = function () {"):C.index("window.__staleGuardPollOnce = pollOnce;")]
    assert "showStaleBuildToast();" in seg
    assert "location.reload()" not in seg


def test_stale_toast_never_auto_reloads():
    # the ONLY reload trigger is the user clicking the toast's Reload button
    seg = C[C.index("var btn = document.getElementById('staleBuildReloadBtn');"):C.index("--- 2. Canvas resilience")]
    assert "location.reload()" in seg
    # and nothing else in the stale-guard module reloads the page
    mod = C[C.index("PHASE STALE: SELF-HEAL SURFACES"):C.index("function initTrackingMap()")]
    assert mod.count("location.reload()") == 1


# ---------------------------------------------------------------- canvas resilience
def test_visibilitychange_re_render_helper_present():
    assert "window.refreshVisibleCharts = window.refreshVisibleCharts || function refreshVisibleCharts(" in C
    # armed on the visible transition, never while hidden
    assert "document.addEventListener('visibilitychange'" in C
    assert "if (!document.hidden && DATA.loaded)" in C
    # guard is armed from the boot completion path (and the watchdog fallback)
    i = C.index("idleStart();")
    assert "initStaleGuard();" in C[i:i + 400]
    assert "try { initStaleGuard(); } catch (err) {}" in C


def test_refresh_helper_covers_maps_and_chart_registry():
    seg = C[C.index("window.refreshVisibleCharts = "):C.index("function canvasIsBroken(")]
    # Leaflet maps invalidateSize on the two map tabs
    assert "window.trackingMap.invalidateSize" in seg
    assert "window.bunkerGeoMap.invalidateSize" in seg
    # Chart.js canvases resize + redraw via the global registry
    assert "Chart.getChart(cv)" in seg
    assert "window.chartRegistry[cv.id]" in seg
    # active-tab renderer dispatch (window-mirror fallback for later blocks)
    assert "renderTrackingTab" in seg and "renderBunkersTab" in seg
    assert "window.currentProduct" in seg


def test_existing_renderers_funnel_through_helper():
    # switchTab resize pass and the tracking resize listener route through it
    i = C.index("if (tabId === 'offshore') {")
    tail = C[i:i + 900]
    assert "window.refreshVisibleCharts(300, tabId, true);" in tail
    assert "healUniverseClassMix();" in tail
    j = C.index("// Window resize listener")
    tail2 = C[j:C.index("// PHASE STALE: the doc hidden -> visible transition")]
    assert "window.refreshVisibleCharts(0, 'tracking', true);" in tail2


def test_broken_canvas_doctor_triggers_redraw():
    assert "function canvasIsBroken(" in C
    assert "function canvasIsBlank(" in C
    assert "function canvasDoctorPass(" in C
    seg_broken = C[C.index("function canvasIsBroken("):C.index("function canvasIsBlank(")]
    # the zero-size-paint signature: CSS box sized while the backing store is not
    assert "var bw = cv.width, bh = cv.height;" in seg_broken
    seg = C[C.index("function canvasDoctorPass("):C.index("function healUniverseClassMix(")]
    assert "refreshVisibleCharts(0, active)" in seg
    # doctor runs on an interval when the tab is visible
    k = C.index("setInterval(function () {\n    if (!document.hidden && DATA.loaded) canvasDoctorPass();")
    assert k > 0


# ---------------------------------------------------------------- fetch coherence
def test_meta_summary_jsons_fetch_no_cache():
    for path in [
        "data/etf/live_quotes.json",
        "data/derived/alibra_tce_matrix.json",
        "data/derived/fearnleys_summary.json",
        "data/derived/fearnleys_series_monthly.json",
        "data/derived/fearnleys_tanker_routes_daily.json",
        "data/derived/fearnleys_dry_routes_daily.json",
        "data/derived/fearnleys_comments_' + d + '.json",
        "data/bunkers/bunker_frontend_summary.json",
        "data/derived/offshore_summary.json",
        "data/derived/port_stress_summary.json",
        "data/congestion/chokepoint_geo_summary.json",
    ]:
        needle = "fetch('" + path + "', { cache: 'no-cache' })"
        assert needle in C, needle


def test_big_csvs_keep_default_caching():
    # the two multi-MB CSVs must NOT be forced no-cache (session-bandwidth guard)
    assert "fetchCSVChunked('data/congestion/portwatch_port_congestion.csv', { cache: 'no-cache' })" not in C
    assert "fetchCSVChunked('data/congestion/port_calls_daily_expanded.csv', { cache: 'no-cache' })" not in C
    assert "safeFetch('data/etf/BDRY_Daily.csv', 'BDRY P/D', [], r => { DATA.bdryPD = parsePDCsv(r || []); }, { cache: 'no-cache' })" not in C


# ---------------------------------------------------------------- class-mix self-heal
def test_class_mix_runtime_guard_present():
    assert "function healUniverseClassMix(" in C
    # exactly the reported defect: a long run of only 0/1 digits
    assert "/^[01]{20,}$/" in C
    # guard runs after every universe table render
    i = C.index("function renderUniverseTable() {")
    seg = C[i:C.index("function prevUniversePage()")]
    assert seg.count("healUniverseClassMix();") == 1
    # and after every tab switch
    assert "healUniverseClassMix();" in C[C.index("if (tabId === 'offshore') {"):C.index("// Tooltip coverage engine")]


def test_class_mix_guard_reuses_the_universe_bar_builder():
    seg = C[C.index("function healUniverseClassMix("):C.index("window.healUniverseClassMix = healUniverseClassMix;")]
    # same palette/labels/90px bar as renderUniverseTable
    assert "UNIVERSE_COLORS[k]" in seg
    assert "UNIVERSE_LABELS[k] + ': ' + mix[k] + ' calls YTD'" in seg
    assert "pd-mixbar" in seg
    assert "window.__trackingSectorPortStats" in seg
    # honest empty state when no measured calls
    assert "var(--text-muted)" in seg


def test_stale_guard_ids_not_leaked_into_visible_copy():
    # standing convention: internal identifiers stay inside <script>
    body = re.sub(r"<script(?![^>]*\bsrc=)[^>]*>.*?</script>", "", C, flags=re.S)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.S)
    for banned in ["refreshVisibleCharts", "healUniverseClassMix", "initStaleGuard",
                   "canvasDoctorPass", "staleGuard"]:
        assert banned not in body, f"code-speak in visible copy: {banned}"
