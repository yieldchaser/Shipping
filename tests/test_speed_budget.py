#!/usr/bin/env python3
"""PHASE SPEED-2 budget gates (index.html).

Pins the idle-prefetch + chunked-parse architecture so the deferred-fetch
pileup cannot silently return:

  - the idle scheduler (requestIdleCallback w/ setTimeout fallback) exists and
    is started from the boot completion path;
  - every deferred tab payload (Bunker summary, 43-hub congestion history,
    Fearnleys daily caches, Offshore summary, PortWatch expanded universe) is
    scheduled by id with a monotonic priority (Bunker summary first, the 56 MB
    expanded universe last);
  - the two big CSVs parse through the chunked/idle-slice loader
    (fetchCSVChunked -> chunkedParseCsvText), never one synchronous
    Papa.parse of the whole text;
  - the Bunkers tab renders in split phases (fast shell first, heavy charts in
    idle slices behind a generation guard);
  - Signals re-entrant renders are gated to the active tab;
  - completion refreshes of background payloads never touch DOM of a foreign
    tab (window.currentTab guard), and Tracking's warm revisit rebuilds
    surfaces skipped while backgrounded;
  - the retained lazy-loader contracts the older tests pin (function names,
    data paths, no base64 embedding) still hold;
  - honest debug surfaces only: no fabricated numbers introduced (the exact
    stale numerals banned by the audit phase stay banned).
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(ROOT, "index.html")

with open(HTML_PATH, "r", encoding="utf-8") as f:
    C = f.read()


# ---------------------------------------------------------------- idle scheduler
def test_idle_scheduler_exists():
    assert "function idleSchedule(" in C
    assert "function idleStart(" in C
    assert "function idleDrain(" in C
    # requestIdleCallback with a guaranteed setTimeout fallback
    assert "window.requestIdleCallback" in C
    assert "setTimeout(cb" in C
    # debug surface is intentional and named
    assert "window.__idleScheduler" in C


def test_idle_scheduler_started_from_boot_completion():
    # the scheduler must be armed on the DATA.loaded boot path, not at parse time
    i = C.index("liveDot.classList.add('active')")
    tail = C[i:i + 2500]
    assert "idleStart()" in tail
    assert "idleSchedule('bunker-summary'" in tail


def test_prefetch_priority_order():
    order = [
        C.index("idleSchedule('bunker-summary'"),
        C.index("idleSchedule('congestion-history'"),
        C.index("idleSchedule('fearn-daily'"),
        C.index("idleSchedule('offshore-summary'"),
        C.index("idleSchedule('expanded-portcalls'"),
    ]
    assert order == sorted(order), "prefetch priorities must ascend: bunker summary first, expanded universe last"


# ---------------------------------------------------------------- chunked parsing
def test_big_csvs_use_chunked_loader():
    assert "function fetchCSVChunked(" in C
    assert "function chunkedParseCsvText(" in C
    assert "function csvChunkWorker(" in C
    # the 8 MB congestion history + 56 MB expanded universe go through it
    assert "fetchCSVChunked('data/congestion/portwatch_port_congestion.csv'" in C
    assert "fetchCSVChunked('data/congestion/port_calls_daily_expanded.csv'" in C
    # bounded slice size, not one giant synchronous pass
    m = re.search(r"SLICE_ROWS = (\d+)", C)
    assert m, "csvChunkWorker must declare a bounded SLICE_ROWS"
    assert 10000 <= int(m.group(1)) <= 200000


def test_small_csvs_keep_whole_text_papa_path():
    # fetchCSVChunked threshold keeps the legacy Papa path for small files
    assert "text.length < threshold" in C
    assert "Papa.parse(text" in C


def test_chunked_parser_has_papa_fallback_for_quoted_text():
    # fast split parser must bail to Papa when quotes appear (comma-in-quotes safety)
    seg = C[C.index("function csvChunkWorker("):C.index("function chunkedParseCsvText(")]
    assert "ctx.slowPath = true" in seg
    assert "Papa.parse(remainText" in seg
    assert 'skipEmptyLines: true' in seg


def test_chunked_fetch_timeout_scoped_to_headers_not_body():
    # the 10s wall-clock race must guard the fetch itself only: resp.text() of a
    # healthy 8-56 MB download that overlaps a heavy idle parse must never be a
    # timeout victim (a rejected race poisons the memoized load-promise for the
    # whole session - measured on the congestion-history feed)
    seg = C[C.index("function fetchCSVChunked("):C.index("async function fetchCSV(")]
    assert "Promise.race([headersPromise, timeoutPromise])" in seg
    assert ".then(resp => resp.text())" in seg
    assert seg.index("Promise.race([headersPromise, timeoutPromise])") < seg.index(".then(resp => resp.text())")
    assert "Promise.race([fetchPromise, timeoutPromise])" not in seg
    assert "timeoutPromise.catch" in seg


# ---------------------------------------------------------------- bunkers split render
def test_bunkers_progressive_render_split():
    seg = C[C.index("function renderBunkersTab() {"):C.index("function initBunkerGeoMap() {")]
    # fast shell = map soon + HUD + spot table; heavy art deferred
    assert "initBunkerGeoMapSoon()" in seg
    assert "updateBunkersHUD();" in seg
    assert "renderBunkersSpotTable();" in seg
    assert "renderBunkerMainChart();" in seg
    # heavy pieces must be inside idle slices, not in the synchronous body
    body_end = seg.index("var gen = ++__bunkersProgressiveGen;")
    assert "renderBunkerMainChart();" not in seg[:body_end]
    # generation guard invalidates stale slices
    assert "__bunkersProgressiveGen" in C
    assert "if (gen !== __bunkersProgressiveGen) return;" in seg


def test_bunkers_warm_revisit_skips_rerender():
    # the render-once memoization (speed-1) must survive: warm visits only resize
    assert "if (bunkersTabFullyInitialized) {" in C
    assert "bunkersTabFullyInitialized = true;" in C


def test_bunker_summary_parses_off_open_path():
    # 4.4 MB JSON: fetch -> text -> JSON.parse on idle; cache + guarded refresh
    seg = C[C.index("function loadBunkerSummary() {"):C.index("window.loadBunkerSummary = loadBunkerSummary;")]
    assert "res.text()" in seg
    assert "JSON.parse(text)" in seg
    assert "idleYield" in seg
    # refresh only when the tab is actually on screen
    assert "window.currentTab === 'bunkers'" in seg


# ---------------------------------------------------------------- signals gate
def test_signals_rerender_gated_to_active_tab():
    seg = C[C.index("function renderSignalsTab(productKey) {"):]
    seg = seg[:seg.index("function setHVWindow(")] if "function setHVWindow(" in seg else seg[:6000]
    assert "window.currentTab !== 'signals'" in seg
    # the debounced body must bail when the user left the tab
    assert "if (window.currentTab !== 'signals') { return; }" in seg
    # Broker Desk terminal work is deferred off the first paint
    assert "idleYield" in seg


def test_switch_tab_mirrors_window_currentTab():
    assert "window.currentTab = currentTab;" in C
    # inside switchTab, after the assignment
    i = C.index("currentTab = tabId;")
    assert "window.currentTab = currentTab;" in C[i:i + 120]


# ---------------------------------------------------------------- background refresh discipline
def test_expanded_completion_refresh_never_janks_foreign_tab():
    seg = C[C.index("Slice 4: refresh the surfaces"):C.index("[expanded port calls fetch error]")]
    assert "window.currentTab === 'tracking'" in seg


def test_congestion_completion_refresh_never_janks_foreign_tab():
    seg = C[C.index("function loadPortCongestionHistory() {"):C.index("window.loadPortCongestionHistory = loadPortCongestionHistory;")]
    assert "window.currentTab === 'tracking'" in seg


def test_tracking_warm_revisit_rebuilds_backgrounded_surfaces():
    seg = C[C.index("function renderTrackingTab() {"):C.index("function initTrackingMap() {")]
    assert "portHistoryCache = null;" in seg
    assert "trackingSectorPortStats()" in seg
    assert "renderUniverseTable();" in seg


def test_tracking_warm_revisit_gated_on_stale_flags():
    # a plain revisit (payload already rendered while Tracking was open) must
    # cost ~nothing; rebuilds run exactly once per backgrounded completion
    seg = C[C.index("function renderTrackingTab() {"):C.index("function initTrackingMap() {")]
    assert "DATA.__trackingStaleHistory" in seg
    assert "DATA.__trackingStaleExpanded" in seg
    assert "DATA.__trackingStaleHistory = false;" in seg
    assert "DATA.__trackingStaleExpanded = false;" in seg
    seg_exp = C[C.index("Slice 4: refresh the surfaces"):C.index("[expanded port calls fetch error]")]
    assert "DATA.__trackingStaleExpanded = true;" in seg_exp
    seg_cong = C[C.index("function loadPortCongestionHistory() {"):C.index("window.loadPortCongestionHistory = loadPortCongestionHistory;")]
    assert "DATA.__trackingStaleHistory = true;" in seg_cong


def test_tracking_sector_stats_memoized_by_source_length():
    # 495k-row aggregation is pure w.r.t. the in-session cache; a matching
    # __srcLen serves the memo (prefetch refresh, warm revisit, stray re-calls)
    seg = C[C.index("function trackingSectorPortStats() {"):C.index("function setTrackingMapSector(")]
    assert "__srcLen" in seg
    assert "window.__trackingSectorPortStats.__srcLen === rows.length" in seg
    assert "out.__srcLen = rows.length;" in seg


# ---------------------------------------------------------------- retained contracts (older pins)
def test_lazy_loader_names_and_paths_survive():
    assert "function loadExpandedPortCalls()" in C
    assert "if (typeof loadExpandedPortCalls === 'function') loadExpandedPortCalls();" in C
    assert "expandedLoadPromise" in C
    assert "function loadPortCongestionHistory()" in C
    assert "portCongestionLoadPromise" in C
    assert "function loadBunkerSummary()" in C
    assert "bunkerSummaryLoadPromise" in C
    assert "function loadFearnDailyCaches()" in C
    assert "fearnDailyLoadPromise" in C
    assert "function loadOffshoreSummary()" in C
    assert "offshoreSummaryLoadPromise" in C
    # no data-URI embedding of payloads
    assert "data:csv" not in C


def test_no_base64_payload_embedding():
    assert "data:application/json;base64" not in C
    assert "data:text/csv" not in C


def test_progressive_markers_not_code_speak_in_visible_copy():
    # standing gate mirrors test_no_code_speak_in_visible_copy: the new
    # identifiers must stay inside <script>, never leak into visible HTML copy
    body = re.sub(r"<script(?![^>]*\bsrc=)[^>]*>.*?</script>", "", C, flags=re.S)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.S)
    for banned in ["idleSchedule", "fetchCSVChunked", "csvChunkWorker",
                   "__bunkersProgressiveGen", "idleStart"]:
        assert banned not in body, f"code-speak in visible copy: {banned}"


def test_no_stale_snapshot_numerals_return():
    # audit-phase bans must keep holding after the speed pass
    for lit in ["4.73M MT", "205.5", "'2026-08-14'"]:
        assert lit not in C, f"banned literal returned: {lit}"


def test_html_size_budget():
    # index.html itself stays a code-only artifact: no payload smuggling
    # (27.6 MB ceiling = pre-speed-2 measured 27.5 MB + slack)
    assert len(C.encode("utf-8")) < 29_000_000
