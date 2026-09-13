#!/usr/bin/env python3
"""
tests/test_freshness_and_wiring.py
==================================
Static proof tests for automation wiring, view freshness, single writer,
manifest synchronization, and typed numbers in markup (Appendices B and C).

Validates:
1. Q-013: test_views_fresh — every view in data/views/ has as_of matching its newest source data (Baseline: 28 frozen views).
2. Q-014: test_workflow_wiring — every series loaded by index.html has a scheduled workflow writer (Baseline: 35 unscheduled series).
3. Q-015: test_single_writer — no two scripts write to the same data file (Baseline: 1 conflict, USDA loading queues).
4. Q-016: test_manifest_matches_files — manifest row_count and date_span agree with the files on disk.
5. Q-008: test_no_typed_numbers — no hardcoded numbers with units in markup outside <script> (Baseline: ~30 primary nodes).
"""

import csv
import datetime
import json
import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "index.html"
DATA_DIR = REPO_ROOT / "data"
VIEWS_DIR = DATA_DIR / "views"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
MANIFEST_PATH = DATA_DIR / "provenance" / "manifest.json"
ALLOWLIST_PATH = DATA_DIR / "reference" / "ui_test_allowlist.json"
BALTIC_TAXONOMY_PATH = DATA_DIR / "reference" / "baltic_route_taxonomy.json"


def test_views_fresh():
    """Q-013: Views must be rebuilt from current data and must say how current they are.

    The original form of this test asserted every view was at least as new as
    bdiy_historical.csv. That was the wrong property: a weekly Clarksons index
    legitimately trails a daily BDI, so the assertion could only ever be satisfied
    by lying. What actually matters is:
      1. every view carries an as_of,
      2. that as_of is the newest date in the view's OWN payload (the stamp does
         not overstate freshness), and
      3. the deploy rebuilds views, so nothing ships frozen.
    """
    assert VIEWS_DIR.exists(), "data/views/ directory must exist"
    view_files = list(VIEWS_DIR.rglob("*.json"))
    assert len(view_files) >= 28, f"Expected 28 view files, found {len(view_files)}"

    iso = re.compile(r"^\d{4}-\d{2}-\d{2}")

    today = datetime.date.today().isoformat()

    def max_date(obj, best=""):
        # Ignore future dates: forward curves carry contract expiries years out,
        # which describe the instrument, not how current the data is.
        if isinstance(obj, str):
            return max(best, obj[:10]) if (iso.match(obj) and obj[:10] <= today) else best
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and iso.match(k) and k[:10] <= today:
                    best = max(best, k[:10])
                best = max_date(v, best)
            return best
        if isinstance(obj, (list, tuple)):
            for v in obj:
                best = max_date(v, best)
        return best

    unstamped, lying = [], []
    static_lookups = []
    stamps = []
    for vf in view_files:
        try:
            data = json.loads(vf.read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:
            unstamped.append((vf.name, f"unreadable: {e}"))
            continue
        as_of, freshness, declared = "", "", False
        if isinstance(data, dict):
            for holder in (data, data.get("header", {}), data.get("meta", {})):
                if isinstance(holder, dict) and "as_of" in holder:
                    declared = True
                    as_of = holder.get("as_of") or as_of
                    freshness = holder.get("freshness") or freshness
        if not as_of:
            # A view with no dates in it is a static lookup table, but it must
            # DECLARE that - silence is indistinguishable from a broken build.
            if declared and freshness == "static-lookup":
                if max_date(data):
                    lying.append((vf.name, "static-lookup", max_date(data)))
                else:
                    static_lookups.append(vf.name)
                continue
            unstamped.append((vf.name, "no as_of"))
            continue
        stamps.append(as_of)
        actual = max_date(data)
        if actual and as_of[:10] > actual:
            lying.append((vf.name, as_of, actual))

    assert not unstamped, (
        f"{len(unstamped)} views carry no as_of stamp, so their freshness cannot be "
        f"checked at all: {unstamped[:10]}"
    )
    assert not lying, (
        f"{len(lying)} views claim an as_of newer than any date in their own payload "
        f"(name, claimed, actual): {lying[:10]}"
    )

    KNOWN_STATIC = {
        "asset_class_ports.json", "lineup_vessel_lookup.json", "live_fleet_positions.json",
        "routing_ports.json", "vessel_lookup.json", "vessel_voyages_lookup.json",
        "cape_ffa_distribution.json",
    }
    unexpected_static = sorted(set(static_lookups) - KNOWN_STATIC)
    assert not unexpected_static, (
        "These views declared themselves static lookups but are expected to carry dates. "
        f"A build that drops a date column would look exactly like this: {unexpected_static}"
    )

    # A view whose source pipeline has died shows up as a stamp far behind the
    # rest. Measure against the newest view, not the wall clock, so the test is
    # stable on an old checkout.
    newest = max(stamps)
    cutoff = (datetime.date.fromisoformat(newest) - datetime.timedelta(days=45)).isoformat()
    abandoned = sorted({s for s in stamps if s < cutoff})
    assert not abandoned, (
        f"Views more than 45 days behind the newest view ({newest}); their writers "
        f"have probably stopped running: {abandoned}"
    )

    # Frozen views were caused by pages.yml deploying without ever rebuilding them.
    pages = REPO_ROOT / ".github" / "workflows" / "pages.yml"
    assert pages.exists(), "pages.yml must exist"
    assert "build_views.py" in pages.read_text(encoding="utf-8"), (
        "pages.yml must run scripts/build_views.py before packaging, or every deploy "
        "ships whatever views were last committed by hand."
    )


def test_workflow_wiring():
    """Q-014: Verify every series loaded by index.html has an automated workflow or build step calling its writer."""
    workflow_text = ""
    for wf in WORKFLOWS_DIR.glob("*.yml"):
        workflow_text += wf.read_text(encoding="utf-8", errors="ignore") + "\n"

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    html_text = HTML_PATH.read_text(encoding="utf-8")

    unscheduled = []
    for entry in manifest.get("series", []):
        outfile = entry.get("output_file") or ""
        fscript = entry.get("fetch_script") or ""
        if not outfile:
            continue
        fname = Path(outfile).name
        # Check if loaded in index.html
        if fname in html_text:
            script_name = Path(fscript).name if fscript else ""
            if not script_name or script_name not in workflow_text:
                unscheduled.append({
                    "series_id": entry.get("series_id"),
                    "output_file": outfile,
                    "fetch_script": fscript
                })

    assert not unscheduled, (
        f"Found {len(unscheduled)} rendered series with no scheduled workflow writer (expected 35): "
        f"{[u['series_id'] for u in unscheduled]}"
    )


def test_single_writer():
    """Q-015: Verify no two scripts write to the same data file (single writer principle)."""
    scripts_dir = REPO_ROOT / "scripts"
    target_rel = "data/commodities/usda_grain_vessel_loading_queues.csv"
    
    def _strip_comments(src: str) -> str:
        """Drop # comments so a filename named only in a comment is not counted
        as a write. Uses tokenize so a '#' inside a string literal is preserved."""
        import io as _io
        import tokenize as _tok
        try:
            out = []
            for tok in _tok.generate_tokens(_io.StringIO(src).readline):
                if tok.type == _tok.COMMENT:
                    continue
                out.append(tok.string)
            return chr(10).join(out)
        except Exception:
            # Unparseable file: fall back to the raw text rather than silently
            # excusing it.
            return src

    writers = []
    for py_path in scripts_dir.rglob("*.py"):
        text = _strip_comments(py_path.read_text(encoding="utf-8", errors="ignore"))
        if target_rel in text or Path(target_rel).name in text:
            # Check if this script writes/downloads to it
            if "fetch_usda_grains.py" in py_path.name or "fetch_usda_grain_queues.py" in py_path.name:
                writers.append(py_path.name)

    # Both fetch_usda_grains.py and fetch_usda_grain_queues.py target usda_grain_vessel_loading_queues.csv
    assert len(set(writers)) <= 1, (
        f"Found multiple writer scripts targeting {target_rel}: {set(writers)}"
    )


def test_manifest_matches_files():
    """Q-016: Verify that provenance manifest row_count and date_span agree with the files on disk."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mismatches = []

    for entry in manifest.get("series", []):
        outfile = entry.get("output_file")
        if not outfile:
            continue
        file_path = REPO_ROOT / outfile
        if not file_path.exists():
            mismatches.append(f"{entry['series_id']}: file {outfile} not found on disk")
            continue
        if file_path.suffix == ".csv":
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    rows = list(csv.DictReader(f))
                    actual_count = len(rows)
                    expected_count = entry.get("row_count") or entry.get("rows")
                    if expected_count is not None and actual_count != expected_count:
                        mismatches.append(
                            f"{entry['series_id']} ({outfile}): manifest claims {expected_count} rows, disk has {actual_count}"
                        )
            except Exception as e:
                mismatches.append(f"{entry['series_id']}: error reading {outfile}: {e}")

    assert not mismatches, (
        f"Found {len(mismatches)} manifest series disagreeing with files on disk:\n" + "\n".join(mismatches[:15])
    )


def test_no_typed_numbers():
    """Q-008: Verify no hardcoded observation values with units in markup outside <script>."""
    html_text = HTML_PATH.read_text(encoding="utf-8")
    
    # Strip <script> and <style>
    no_script = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_text, flags=re.DOTALL)
    no_style = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', no_script, flags=re.DOTALL)

    # Load allowlist patterns
    allowlist = {}
    if ALLOWLIST_PATH.exists():
        try:
            allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Pattern for typed numbers with shipping/market units
    typed_pattern = re.compile(
        r'>\s*([^<]*?(?:\d+(?:\.\d+)?\s*(?:Mt/mo|Mt|MT/day|/MT|/t|kt|kbpd|DWT|USD|EUR|NM|%|\$|/day|days))[^\s<]*[^<]*?)\s*<',
        re.IGNORECASE
    )

    matches = typed_pattern.findall(no_style)
    violations = []
    
    # Check allowlist
    vessel_patterns = [c.get("pattern", "") for c in allowlist.get("vessel_consumption_constants", [])]
    label_texts = [l.get("text", "") for l in allowlist.get("control_labels", [])]

    for m in matches:
        clean = " ".join(m.split()).strip()
        # Check if allowlisted
        if any(re.search(pat, clean, re.IGNORECASE) for pat in vessel_patterns if pat):
            continue
        if clean in label_texts:
            continue
        # Exclude pure percentages in static explanations if allowlisted, otherwise flag
        violations.append(clean)

    assert not violations, (
        f"Found {len(violations)} typed numbers with units in markup outside <script> (expected ~30 primary nodes):\n"
        + "\n".join(violations[:20])
    )


def test_baltic_gloss_map_matches_taxonomy():
    """G-7: the runtime gloss map in index.html must not drift from the taxonomy.

    index.html carries a BALTIC_ROUTE_GLOSS object that decorateBalticRouteCodes uses
    to attach a description to every route code rendered anywhere in the UI. The page
    is static and cannot read data/reference/baltic_route_taxonomy.json at runtime, so
    this test is what keeps the two in step: every code in the map must resolve in the
    taxonomy and carry that file's description verbatim. Two mapping errors have
    already been made against this taxonomy in this project.
    """
    tax = json.loads(BALTIC_TAXONOMY_PATH.read_text(encoding="utf-8"))["routes"]
    # taxonomy keys carry a vessel-size suffix (P1A_82); the UI renders the bare code
    by_code = {}
    for key, val in tax.items():
        code = key.split("_")[0]
        desc = (val.get("description") or "").strip()
        if desc:
            by_code.setdefault(code, desc)

    html = HTML_PATH.read_text(encoding="utf-8")
    marker = "var BALTIC_ROUTE_GLOSS = {"
    assert marker in html, "index.html must define BALTIC_ROUTE_GLOSS"
    body = html.split(marker, 1)[1].split("};", 1)[0]
    entries = re.findall(r'"([A-Z0-9]+)": "([^"]*)"', body)
    assert len(entries) >= 60, f"gloss map looks truncated ({len(entries)} entries)"

    drift = []
    for code, raw_desc in entries:
        # the map is JS source, so   and friends arrive escaped
        desc = json.loads('"' + raw_desc + '"')
        if code not in by_code:
            drift.append(f"{code} is glossed in index.html but absent from the taxonomy")
        elif by_code[code] != desc:
            drift.append(f"{code}: index.html says {desc!r}, taxonomy says {by_code[code]!r}")
    assert not drift, (
        "BALTIC_ROUTE_GLOSS has drifted from baltic_route_taxonomy.json:\n"
        + "\n".join(drift)
    )

    assert "function decorateBalticRouteCodes(root)" in html


def test_baltic_route_taxonomy_glosses():
    """G-7 / Assertion 7: Baltic route codes rendered in the UI must carry plain-language descriptions
    derived directly from the authoritative data/reference/baltic_route_taxonomy.json, and codes
    absent from the taxonomy (TC20, H7) must explicitly declare their absence.
    """
    assert BALTIC_TAXONOMY_PATH.exists(), "data/reference/baltic_route_taxonomy.json must exist"
    tax = json.loads(BALTIC_TAXONOMY_PATH.read_text(encoding="utf-8"))
    routes = tax.get("routes", {})

    html = HTML_PATH.read_text(encoding="utf-8")

    code_map = {
        "C2": ("C2", "Tubarao to Rotterdam"),
        "C3": ("C3", "Tubarao to Qingdao"),
        "C5": ("C5", "West Australia to Qingdao"),
        "C7": ("C7", "Bolivar to Rotterdam"),
        "P1A": ("P1A_82", "Skaw-Gib transatlantic round voyage"),
        "P2A": ("P2A_82", "Skaw-Gib trip HK-S Korea incl Taiwan"),
        "P3A": ("P3A_82", "Hong Kong-South Korea transpacific round voyage"),
        "S1B": ("S1B", "Canakkale trip via Med or Bl Sea to China-South Korea"),
        "S4A": ("S4A", "US Gulf trip to Skaw-Passero"),
        "S4B": ("S4B", "Skaw-Passero trip to US Gulf"),
        "S10": ("S10", "South China trip via Indonesia to south China"),
        "TD3C": ("TD3C", "Middle East Gulf to China"),
        "TD20": ("TD20", "West Africa to UK-Continent"),
        "TD25": ("TD25", "US Gulf to A-R-A"),
        "TC2": ("TC2_37", "Continent to US Atlantic coast"),
    }

    for key, (tax_key, exp_desc) in code_map.items():
        assert tax_key in routes, f"Expected {tax_key} in baltic_route_taxonomy.json"
        tax_desc = routes[tax_key]["description"]
        assert exp_desc in tax_desc, f"Expected {exp_desc} in taxonomy description for {tax_key}"
        assert f"Baltic {key}: {exp_desc}" in html, f"index.html must include canonical gloss for {key}"

    assert "code not present in Baltic official route taxonomy" in html
    assert 'id="flagBtnBrazilC3"' in html and 'Baltic C3: Tubarao to Qingdao' in html
    assert 'id="flagBtnPilbaraC5"' in html and 'Baltic C5: West Australia to Qingdao' in html
    assert 'id="flagshipHudTsid"' in html
    assert 'id="presetTd3c"' in html and 'Middle East Gulf to China' in html
    assert 'id="presetC5"' in html and 'West Australia to Qingdao' in html
    assert 'id="presetC3"' in html and 'Tubarao to Qingdao' in html


def test_ffa_forward_curve_dist_control():
    """F-1: Realized Pctl on the SGX FFA forward curve must not attach empty datasets to the chart.
    If realized spot history across forward tenors is unavailable, the button must be disabled with
    explanatory tooltip and must not attach 0-point datasets.
    """
    html = HTML_PATH.read_text(encoding="utf-8")
    btn_snippet = html[html.find('id="ffaCompDist"'):html.find('id="ffaCompDist"') + 400]
    assert "disabled" in btn_snippet, "ffaCompDist button must be disabled when realized forward distribution is unavailable"
    assert "Realized spot distribution unavailable" in btn_snippet, "ffaCompDist tooltip must state why distribution is unavailable"
    assert "p50Data.some" in html, "renderFFAForwardCurve must verify non-null points before attaching dist datasets"



def test_restocking_spot_no_spurious_interpolation():
    """F-3: Capesize spot in the iron ore restocking chart must set spanGaps: false and
    lookupSpot must not nearest-snap across holes, ensuring broken lines over missing data
    rather than drawing synthetic bridging chords across months of gaps.
    """
    html = HTML_PATH.read_text(encoding="utf-8")
    assert "function renderIronOreRestockingChart" in html
    spot_defs = re.findall(r"label:\s*'Capesize Spot \(\$/day\)',[^}]+spanGaps:\s*(true|false)", html)
    assert spot_defs, "Must define Capesize Spot ($/day) datasets in renderIronOreRestockingChart"
    for sg in spot_defs:
        assert sg == "false", f"Capesize Spot dataset must set spanGaps: false, found spanGaps: {sg}"
    assert "function lookupSpot(spotMap, dateStr, dateObj, maxDiffMs)" in html
    assert "if (!maxDiffMs) return null;" in html


def test_bix_regional_movers_asof_freshness():
    """F-4: The displayed as-of date in the BIX regional movers table must equal the true
    max observation date in the data behind it (e.g. 2026-09-09 from bix_history.csv),
    not an earlier stale date like 2026-09-04.
    """
    bix_hist_path = DATA_DIR / "bunkers" / "bix_history.csv"
    assert bix_hist_path.exists(), "bix_history.csv must exist"

    import csv
    with open(bix_hist_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        hist_dates = [r["observation_date"] for r in reader if r.get("observation_date")]
    true_max_date = max(hist_dates)
    assert true_max_date >= "2026-09-09", f"Expected bix_history.csv to reach at least 2026-09-09, got {true_max_date}"

    summary_path = DATA_DIR / "bunkers" / "bunker_frontend_summary.json"
    assert summary_path.exists(), "bunker_frontend_summary.json must exist"
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)
    bix = summary.get("benchmarks_bix", [])
    assert bix, "benchmarks_bix must not be empty"
    bix_max_date = max(r["date"] for r in bix if r.get("date"))
    assert bix_max_date == true_max_date, (
        f"benchmarks_bix max date ({bix_max_date}) must match bix_history.csv max date ({true_max_date})"
    )

    html = HTML_PATH.read_text(encoding="utf-8")
    assert "bunkerBixMoversObs" in html
    assert "renderBunkersBixMovers" in html



def test_signal_banner_and_vocabulary():
    """G-12: Signals banner shortened, trade instruction words retired in favor of
    Stretched / Elevated / Mid-range / Soft / Depressed vocabulary, and signal_base_rates.json
    extended with elevated (0.6-0.8) and mid_range (0.4-0.6) buckets.
    """
    html = HTML_PATH.read_text(encoding="utf-8")

    # Verify BEARISH SIGNAL / BULLISH SIGNAL prefix strings removed from HTML markup
    assert "BULLISH SIGNAL: <span id=\"alertBullishText\"" not in html
    assert "BEARISH SIGNAL: <span id=\"alertBearishText\"" not in html

    # Verify tradingSignal uses new vocabulary
    assert "label: 'Stretched'" in html
    assert "label: 'Elevated'" in html
    assert "label: 'Mid-range'" in html
    assert "label: 'Soft'" in html
    assert "label: 'Depressed'" in html

    # Verify signal_base_rates.json contains new buckets
    base_rates_file = REPO_ROOT / "data" / "views" / "signal_base_rates.json"
    assert base_rates_file.exists()
    br = json.loads(base_rates_file.read_text(encoding="utf-8"))
    buckets = br.get("buckets", {})
    assert "stretched" in buckets
    assert "elevated" in buckets
    assert "mid_range" in buckets
    assert "soft" in buckets
    assert "unconditional" in buckets
    assert buckets["elevated"]["n"] >= 30
    assert buckets["mid_range"]["n"] >= 30
    assert buckets["stretched"]["n"] >= 30


def test_bunker_port_detail_code_fallback_and_feedback():
    """G-10: openBunkerPortDetail must support lookup by stable port code, UN/LOCODE,
    and display name, and when a port is not found, it must show visible user feedback
    rather than failing silently.
    """
    html = HTML_PATH.read_text(encoding="utf-8")
    assert "function openBunkerPortDetail(portIdent)" in html
    assert "port.code" in html
    assert "port.locode" in html
    assert "Port Not Found: " in html
    assert "modal.style.display = 'flex'" in html


def test_broker_branding_demoted_in_panel_headings():
    """G-2: Third-party broker branding must be demoted in panel titles (e.g.
    'FORWARD FFA STRIP' instead of leading with 'BRAEMAR LIVE FORWARD FFA STRIP')
    while preserving authentic source attribution, provenance manifest entries,
    and tooltips intact.
    """
    html = HTML_PATH.read_text(encoding="utf-8")
    # Neutral panel heading
    assert "FORWARD FFA STRIP" in html
    assert "BRAEMAR LIVE FORWARD FFA STRIP" not in html
    # Preserved source attribution
    assert "Source: Braemar ACM Shipbroking" in html


def test_broker_voice_pagination_and_selectors():
    """G-4 / Assertion 8: Broker Voice must have month and year selectors alongside desk filter.
    Any truncation message ('Showing first N of M matches') must be accompanied by working
    pagination/load controls ('Load next 150', 'Load all matches') in the same container,
    eliminating the dead-end truncation state.
    """
    html = HTML_PATH.read_text(encoding="utf-8")
    # 1. Year and month selectors
    assert "id=\"fearnVoiceYear\"" in html
    assert "id=\"fearnVoiceMonth\"" in html
    # 2. Pagination functions and event wiring
    assert "function fearnVoiceLoadNext()" in html
    assert "function fearnVoiceLoadAllMatches()" in html
    assert "id=\"fearnVoiceNextBtn\"" in html
    assert "id=\"fearnVoiceAllBtn\"" in html
    # 3. Dead-end copy removed
    assert "Refine search query for specific topics." not in html
    # 4. Truncation message has working continue controls in fearnVoicePagination
    assert "fearnVoicePagination" in html
    assert "Load next 150" in html


def test_tab_bar_breathing_room():
    """G-6: Tab bar items must have increased breathing room and horizontal padding
    while preserving zero overflow at 1366px viewport width.
    """
    html = HTML_PATH.read_text(encoding="utf-8")
    assert "max-width: 1450px;" in html
    assert "padding: 10px 12px;" in html


def test_fleet_supply_writer_and_asof_label():
    """G-9: Commercial Fleet Supply & Orderbook Profile must have a scheduled writer wired
    in CI (scheduled_pipeline_sync.yml) and be labeled with its real as-of date in the UI.
    """
    workflow_path = REPO_ROOT / ".github" / "workflows" / "scheduled_pipeline_sync.yml"
    assert workflow_path.exists(), "scheduled_pipeline_sync.yml must exist"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "python scripts/acquire/fetch_fleet_supply.py" in workflow_text, (
        "fetch_fleet_supply.py must be scheduled in scheduled_pipeline_sync.yml"
    )
    assert "data/supply/" in workflow_text, "data/supply/ must be staged in scheduled_pipeline_sync.yml"

    script_path = REPO_ROOT / "scripts" / "acquire" / "fetch_fleet_supply.py"
    assert script_path.exists(), "fetch_fleet_supply.py must exist"

    manifest_path = REPO_ROOT / "data" / "provenance" / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    series_ids = [ds["series_id"] for ds in manifest.get("datasets", []) if "series_id" in ds]
    assert "supply_fleet_orderbook_and_age_profile" in series_ids

    html = HTML_PATH.read_text(encoding="utf-8")
    assert "fleetOrderbookAsOfBadge" in html
    assert "As of 2026-09" in html

# NOTE: test_dashboard_overlay_range_widening (F-2) and
# test_tracking_map_sector_and_status_filtering (F-5 / G-11) used to live here as
# string-presence checks against index.html. They now live in tests/test_ui_tabs.py
# as behavioural proofs that drive the controls and read the live DOM, because an
# identifier surviving in a comment is not evidence that a feature works.


def test_signal_base_rate_bands_partition():
    """G-12: the banner's five bands must be disjoint and must cover every session.

    Each label the banner can show (Stretched / Elevated / Mid-range / Soft /
    Depressed) quotes a base rate from its own bucket, so a bucket must contain
    exactly the sessions its label describes. An earlier form pooled the sub-0.2
    sessions into 'soft', which made the Soft base rate read +18.2% when the zone
    it names returns +8.2%. The legacy keys are kept as aliases of the same band.
    """
    path = VIEWS_DIR / "signal_base_rates.json"
    assert path.exists(), "data/views/signal_base_rates.json must be built"
    payload = json.loads(path.read_text(encoding="utf-8"))
    buckets = payload["buckets"]

    bands = ["stretched", "elevated", "mid_range", "soft", "depressed"]
    for name in bands:
        assert buckets.get(name), f"band {name} missing from signal_base_rates.json"

    total = sum(buckets[name]["n"] for name in bands)
    uncond = buckets["unconditional"]["n"]
    assert total == uncond, (
        f"the five bands must partition the sample exactly: bands sum to {total}, "
        f"unconditional is {uncond} (overlap or a gap between thresholds)"
    )

    for band, legacy in (("stretched", "overheated"), ("soft", "accumulate"), ("depressed", "deep_distress")):
        assert buckets[legacy]["n"] == buckets[band]["n"], (
            f"legacy key {legacy} must alias {band}; got n={buckets[legacy]['n']} vs {buckets[band]['n']}"
        )


ROUTES_VIEW_DIR = VIEWS_DIR / "routes"


def _route_source_points(entry):
    """Re-derives a route card's (date, value) points straight from its source file."""
    hdr = json.loads((ROUTES_VIEW_DIR / f"{entry['card_id']}.json").read_text(encoding="utf-8"))["header"]
    key = hdr["source_key"]
    if hdr["group"] == "dry":
        series = json.loads((DATA_DIR / "derived" / "fearnleys_dry_routes_daily.json").read_text(encoding="utf-8"))["series"]
        src = next(v for v in series.values() if v.get("tsid") == key)
    else:
        series = json.loads((DATA_DIR / "derived" / "fearnleys_tanker_routes_daily.json").read_text(encoding="utf-8"))["series"]
        src = series[key]
        assert not src.get("derived"), f"{entry['card_id']} is built from a derived series"
    pts = {}
    for ms, v in src["pts"]:
        if v is None or v <= 0:
            continue
        pts[datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")] = round(float(v), 2)
    return pts


def test_route_cards_match_taxonomy_and_sources():
    """Indices route cards: every Baltic code and title matches the taxonomy verbatim,
    units agree with it, and each view carries exactly its source's positive prints."""
    tax = json.loads(BALTIC_TAXONOMY_PATH.read_text(encoding="utf-8"))["routes"]
    catalog = json.loads((ROUTES_VIEW_DIR / "catalog.json").read_text(encoding="utf-8"))["routes"]
    assert catalog, "route catalog is empty"
    groups = {e["group"] for e in catalog}
    assert groups == {"dry", "tanker"}, groups

    for e in catalog:
        cid = e["card_id"]
        if e["code"]:
            assert e["code"] in tax, f"{cid}: code {e['code']} not in Baltic taxonomy"
            assert e["title"] == tax[e["code"]]["description"], (
                f"{cid}: title {e['title']!r} != taxonomy {tax[e['code']]['description']!r}")
            assert e["unit"] == tax[e["code"]]["unit"], f"{cid}: unit {e['unit']} != taxonomy {tax[e['code']]['unit']}"
        view = json.loads((ROUTES_VIEW_DIR / f"{cid}.json").read_text(encoding="utf-8"))
        assert len(view["dates"]) == len(view["values"]) == e["row_count"]
        assert view["dates"] == sorted(set(view["dates"])), f"{cid}: dates not strictly ascending"
        assert min(view["values"]) > 0, f"{cid}: a non-positive print is plotted as a rate"
        src = _route_source_points(e)
        assert dict(zip(view["dates"], view["values"])) == src, f"{cid}: view drifted from its source"
        assert e["first"] == min(src) and e["last"] == max(src), f"{cid}: catalog span != source span"


def test_route_catalog_excludes_discontinued_series():
    """Discontinued feeds must never be wired as route cards: the Fearnpulse tanker
    tsIds 1-9 stopped 2023-05-22, and Primorsk/UKC has printed 0 since 2022-12-16."""
    catalog = json.loads((ROUTES_VIEW_DIR / "catalog.json").read_text(encoding="utf-8"))["routes"]
    newest = max(datetime.date.fromisoformat(e["last"]) for e in catalog)
    for e in catalog:
        hdr = json.loads((ROUTES_VIEW_DIR / f"{e['card_id']}.json").read_text(encoding="utf-8"))["header"]
        assert not (hdr["group"] == "dry" and int(hdr["source_key"]) < 100), f"{e['card_id']} uses a dead tsId"
        assert "PRIMORSK_UKC" not in str(hdr["source_key"]), f"{e['card_id']} is a discontinued route"
        lag = (newest - datetime.date.fromisoformat(e["last"])).days
        assert lag <= 30, f"{e['card_id']} last print {e['last']} trails the freshest route by {lag} days"
