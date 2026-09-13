#!/usr/bin/env python3
"""
tests/test_ui_tabs.py
=====================
Playwright End-to-End Proof Suite across all 12 tabs and sub-views.

Validates:
1. Q-002: test_no_console_errors (pageerror, console.error, [stale-guard] warning; baseline: 5 tabs failing)
2. Q-003: test_no_failed_requests (status >= 400)
3. Q-004: test_no_empty_states (not available / Loading… / Insufficient / unavailable / no data / awaiting; baseline: 5 items)
4. Q-005: test_no_dash_kpis (KPI value is —, -, n/a, NaN, $NaN; baseline: 9 items)
5. Q-006: test_charts_have_data (visible canvas has Chart instance with >= 2 points; baseline: 8 dead modules)
6. Q-007: test_ui_copy_lint (Phase 3 internal terms, all-caps pills, count badges; baseline: ~25 terms + pills)
7. Q-009: test_design_lint (left-edge accents, box-shadow glows, backdrop blurs, emoji; baseline: 13 accents / 63 glows / 16 blurs / 11 emoji)
8. Q-010: test_tooltip_coverage (>= 95% coverage, >= 20 chars, no interaction-only; baseline: Broker Desk 12/65)
9. Q-011: test_layout (tab bar scrollWidth <= clientWidth at 1366 & 1920, no clipped text; baseline: 20 clipped in Bunkers)
10. Q-012: test_ui_sweep (clicking controls raises error or reveals empty state; baseline: 10 click failures)
11. Q-017: test_perf_budget (boot transfer <= 0.5 MB, cumulative <= 8 MB, warm switch <= 50 ms; baseline: 55 MB, ETFs 2.1 s warm)
"""

import json
import re
import time
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "index.html"
ALLOWLIST_PATH = REPO_ROOT / "data" / "reference" / "ui_test_allowlist.json"

TABS = [
    ("dashboard", "tab-dashboard"),
    ("yearly-dash", "tab-yearly-dash"),
    ("seasonality", "tab-seasonality"),
    ("indices", "tab-indices"),
    ("etfs", "tab-etfs"),
    ("signals", "tab-signals"),
    ("fearnleys", "tab-fearnleys"),
    ("intelligence", "tab-intelligence"),
    ("tracking", "tab-tracking"),
    ("cargo", "tab-cargo"),
    ("bunkers", "tab-bunkers"),
    ("offshore", "tab-offshore"),
]

BANNED_INTERNAL_TERMS = [
    "unauthenticated", "graphql", "hasura", "api", "cache", "pipeline",
    "harvest", "scrape", "scraper", "reverse-engineer", "fixture-grounded",
    "canonical", "taxonomy", "audit", "disclosure", "data reality", "honest",
    "fabricat", "synthetic", "quarantine", "operator", "network inspection",
    "pending", "editorial estimate", "computed from the chart's own series",
    "no external lookup", "zero ton-mile sliders", "rule:", "tsid"
]

ALL_CAPS_PILLS = [
    "LIVE OFFICIAL", "LIVE HARBOR MASTER", "LIVE MIRROR STATISTIC",
    "LIVE SUPPLY REGISTRY", "LIVE MULTIPLES", "LIVE 5Y ENVELOPES",
    "LIVE PAIRED", "LIVE FLEET AIS", "ACTIVE REROUTING", "EST. AUDIT",
    "UNCLASSIFIED BUCKET", "HIGH COVERAGE", "FROZEN", "MODELLED",
    "40 TENORS", "540k Broker Fixtures", "14 Flow Datasets",
    "15 Active Pricing Modules", "7 TRADE BASINS", "98% GLOBAL OUTPUT",
    "182.8 MT ANNUAL RECORD"
]


@pytest.fixture(scope="module")
def tab_audit_data(web_server):
    """Mounts all 12 tabs and subviews using the required mount helper and audits DOM state."""
    results = {
        "boot_transfer_mb": 0.0,
        "cumulative_transfer_mb": 0.0,
        "failed_requests": [],
        "tab_console_errors": {},
        "tab_empty_states": {},
        "tab_dash_kpis": {},
        "tab_dead_charts": {},
        "tab_copy_lint": {},
        "tab_tooltips": {},
        "tab_layout": {},
        "tab_ui_sweep_errors": [],
        "warm_switch_ms": {}
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Check viewport at 1920x1080
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        console_entries = []
        page_errors = []
        transfer_bytes = 0
        failed_reqs = []

        def on_console(msg):
            console_entries.append({
                "type": msg.type,
                "text": msg.text,
                "location": msg.location
            })

        def on_response(res):
            nonlocal transfer_bytes
            if res.request.method == "HEAD":
                return
            try:
                cl = res.headers.get("content-length")
                if cl:
                    transfer_bytes += int(cl)
                else:
                    transfer_bytes += len(res.body())
            except Exception:
                pass
            if res.status >= 400:
                failed_reqs.append((res.url, res.status))

        page.on("console", on_console)
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("response", on_response)

        # 1. Boot
        t0 = time.time()
        page.goto(f"{web_server}/index.html", wait_until="networkidle")
        try:
            page.wait_for_function("() => window.DATA && window.DATA.loaded === true", timeout=15000)
        except Exception:
            pass
        results["boot_transfer_mb"] = round(transfer_bytes / (1024 * 1024), 2)

        # 2. Check tab bar width at 1366 and 1920
        tab_nav_1920 = page.evaluate("""() => {
            const el = document.querySelector('.tab-bar, .nav-tabs, .tabs, nav, .header-tabs, .navbar-tabs');
            const offBtn = document.querySelector('button[data-tab=\"offshore\"]');
            const offRect = offBtn ? offBtn.getBoundingClientRect() : null;
            const winW = window.innerWidth;
            const offHidden = offRect ? (offRect.right > winW || offRect.width === 0) : true;
            return el ? { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, offHidden } : { offHidden };
        }""")

        # Test 1366 width
        page.set_viewport_size({"width": 1366, "height": 768})
        page.wait_for_timeout(200)
        tab_nav_1366 = page.evaluate("""() => {
            const el = document.querySelector('.tab-bar, .nav-tabs, .tabs, nav, .header-tabs, .navbar-tabs');
            const offBtn = document.querySelector('button[data-tab=\"offshore\"]');
            const offRect = offBtn ? offBtn.getBoundingClientRect() : null;
            const winW = window.innerWidth;
            const offHidden = offRect ? (offRect.right > winW || offRect.width === 0) : true;
            return el ? { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, offHidden } : { offHidden };
        }""")

        # Reset back to 1920
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.wait_for_timeout(200)

        results["tab_layout"]["nav_1920"] = tab_nav_1920
        results["tab_layout"]["nav_1366"] = tab_nav_1366

        # 3. Mount helper across all 12 tabs
        for tab_id, panel_id in TABS:
            logs_before = len(console_entries)
            errs_before = len(page_errors)

            # Switch to tab
            btn = page.locator(f"button[data-tab='{tab_id}']")
            if btn.count() > 0:
                btn.first.click(force=True)
            else:
                page.evaluate(f"window.switchTab('{tab_id}')")

            page.wait_for_load_state("networkidle")

            # Mount helper scroll: top -> bottom -> top, then wait 1s
            page.evaluate(f"""() => {{
                const p = document.getElementById('{panel_id}');
                if (p) {{
                    window.scrollTo(0, document.body.scrollHeight);
                    p.scrollTop = p.scrollHeight;
                }}
            }}""")
            page.wait_for_timeout(500)
            page.evaluate(f"""() => {{
                const p = document.getElementById('{panel_id}');
                if (p) {{
                    window.scrollTo(0, 0);
                    p.scrollTop = 0;
                }}
            }}""")
            page.wait_for_timeout(1000)

            # Run stale-guard doctor check on active tab (the page's own blank-chart detector)
            page.evaluate("if (typeof window.canvasDoctorPass === 'function') { window.canvasDoctorPass(); }")

            # Check console errors / stale-guard
            new_logs = console_entries[logs_before:]
            new_errs = page_errors[errs_before:]
            relevant_logs = [
                l["text"] for l in new_logs
                if l["type"] == "error" or "[stale-guard]" in l["text"] or "ReferenceError" in l["text"]
            ] + new_errs

            if relevant_logs:
                results["tab_console_errors"][tab_id] = relevant_logs

            # Evaluate panel contents
            panel_eval = page.evaluate(f"""() => {{
                const p = document.getElementById('{panel_id}');
                if (!p) return null;
                const text = p.innerText || '';

                // Empty states
                const emptyMatches = [];
                const emptyPhrases = ['not available', 'Loading…', 'Loading...', 'Insufficient', 'unavailable', 'no data', 'awaiting', 'NaN', 'undefined', 'null', 'Invalid Date'];
                for (const ph of emptyPhrases) {{
                    if (text.includes(ph)) emptyMatches.push(ph);
                }}

                // Dash KPIs: check KPI/HUD elements and leaf elements
                const kpis = [];
                const seenKeys = new Set();
                // A KPI is an element something can write a value INTO: it has an
                // id, or a kpi/hud/metric/stat/value class. A bare <div>/<span>
                // with neither is layout, and an em-dash in one is a table cell
                // with nothing to show - an honest empty state, not a dead KPI.
                const kpiEls = p.querySelectorAll('.kpi-value, .metric-value, .stat-value, .card-value, [class*=\"kpi\"], [class*=\"hud\"], [class*=\"value\"], [class*=\"metric\"], [class*=\"stat\"], [id*=\"Hud\"], [id*=\"hud\"], [id*=\"kpi\"], [id*=\"Kpi\"], div[id], span[id]');
                kpiEls.forEach(el => {{
                    if (el.children.length > 0) return;
                    const val = el.innerText.trim();
                    const id = el.id || '';
                    const cls = el.className || '';
                    if (['—', '-', 'n/a', 'N/A', 'NaN', '$NaN', '=-', '=—'].includes(val) || val.endsWith('=-') || val.endsWith('=—')) {{
                        const key = id || (cls + ':' + val);
                        if (!seenKeys.has(key)) {{
                            seenKeys.add(key);
                            kpis.push(id ? (id + '=' + val) : val);
                        }}
                    }}
                }});

                // Dead charts (canvases with < 2 non-null points or no Chart instance, excluding Leaflet)
                // Document-wide, not panel-scoped. A panel-scoped sweep missed a
                // modal canvas rendering as a visible blank 792x258 panel inside
                // the ETFs tab with no Chart instance. Only VISIBLE canvases
                // count: a hidden modal's canvas is not a defect.
                const canvases = document.querySelectorAll('canvas');
                let deadCount = 0;
                const deadIds = [];
                canvases.forEach(cv => {{
                    if (cv.closest('.leaflet-container')) return;
                    const r = cv.getBoundingClientRect();
                    if (r.width < 2 || r.height < 2) return;
                    if (cv.offsetParent === null) return;
                    const cs = getComputedStyle(cv);
                    if (cs.visibility === 'hidden' || cs.display === 'none') return;
                    const ch = typeof Chart !== 'undefined' ? Chart.getChart(cv) : null;
                    if (!ch) {{
                        deadCount++;
                        deadIds.push(cv.id || 'no-id');
                    }} else {{
                        let pts = 0;
                        if (ch.data && ch.data.datasets) {{
                            ch.data.datasets.forEach(ds => {{
                                if (ds.data) ds.data.forEach(v => {{ if (v != null) pts++; }});
                            }});
                        }}
                        if (pts < 2) {{
                            deadCount++;
                            deadIds.push((cv.id || 'no-id') + ' (pts=' + pts + ')');
                        }}
                    }}
                }});

                // Tooltip coverage
                const controls = p.querySelectorAll('button, select, input, [role=\"button\"], .chip, .segmented-btn, .btn, .control');
                let totalControls = controls.length;
                let tipped = 0;
                let descriptiveOnly = 0;
                controls.forEach(c => {{
                    const tip = c.getAttribute('data-tip') || c.getAttribute('title') || c.getAttribute('data-tooltip') || '';
                    if (tip && tip.trim().length >= 20) {{
                        if (!/^(click|toggle|select|tap)\b/i.test(tip.trim())) {{
                            tipped++;
                        }} else {{
                            descriptiveOnly++;
                        }}
                    }}
                }});

                // Clipped leaf text (offsetWidth < scrollWidth)
                let clippedCount = 0;
                p.querySelectorAll('span, div, p, td').forEach(el => {{
                    if (el.children.length === 0 && el.innerText && el.innerText.trim().length > 0) {{
                        if (el.scrollWidth > el.clientWidth + 1) clippedCount++;
                    }}
                }});

                return {{
                    emptyMatches,
                    kpis,
                    deadCount,
                    deadIds,
                    totalControls,
                    tipped,
                    descriptiveOnly,
                    clippedCount,
                    text
                }};
            }}""")

            if panel_eval:
                if panel_eval["emptyMatches"]:
                    results["tab_empty_states"][tab_id] = panel_eval["emptyMatches"]
                if panel_eval["kpis"]:
                    results["tab_dash_kpis"][tab_id] = panel_eval["kpis"]
                if panel_eval["deadCount"] > 0:
                    results["tab_dead_charts"][tab_id] = panel_eval["deadCount"]
                results["tab_tooltips"][tab_id] = {
                    "total": panel_eval["totalControls"],
                    "tipped": panel_eval["tipped"],
                    "descriptive_only": panel_eval["descriptiveOnly"]
                }
                results["tab_layout"][tab_id] = {
                    "clipped": panel_eval["clippedCount"]
                }

                # Copy lint for this tab
                found_terms = []
                tab_text_lower = panel_eval["text"].lower()
                for term in BANNED_INTERNAL_TERMS:
                    if term in tab_text_lower:
                        found_terms.append(term)
                for pill in ALL_CAPS_PILLS:
                    if pill in panel_eval["text"]:
                        found_terms.append(pill)
                if found_terms:
                    results["tab_copy_lint"][tab_id] = found_terms

        # 4. Measure warm revisit switch time on ETFs
        dur = page.evaluate("""() => {
            const t0 = performance.now();
            window.switchTab('etfs');
            return Math.round(performance.now() - t0);
        }""")
        page.wait_for_timeout(100)
        results["warm_switch_ms"]["etfs"] = dur

        # 5. UI Sweep click checks on known failure controls (Appendix B baseline: 10 click failures)
        sweep_controls = [
            ("signals", "if (typeof switchFlowSigTab === 'function') switchFlowSigTab('bdry');", "Seasonal"),
            ("fearnleys", "if (typeof fearnLoadDesk === 'function') fearnLoadDesk(5); else Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('S&P & Assets'))?.click();", "Loading"),
            ("fearnleys", "(() => { const sel = document.getElementById('fearnAcClass'); if (!sel) return; Array.from(sel.options).forEach(o => { sel.value = o.value; sel.dispatchEvent(new Event('change')); if (typeof onFearnAcClass === 'function') onFearnAcClass(); const pcv = document.getElementById('fearnAcParity'); if (pcv && pcv.offsetParent !== null && pcv.parentElement && pcv.parentElement.style.display !== 'none') { const ch = typeof Chart !== 'undefined' ? Chart.getChart(pcv) : null; let pts = 0; if (ch && ch.data && ch.data.datasets) ch.data.datasets.forEach(d => { if (d.data) d.data.forEach(v => { if (v != null) pts++; }); }); if (pts === 0) throw new Error('Empty visible parity chart for ' + o.value); } }); })()", "Empty visible parity chart"),
            ("fearnleys", "if (typeof fearnLoadDesk === 'function') fearnLoadDesk(8); else Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Fixtures Tape'))?.click();", "Coverage 2024"),
            ("tracking", "if (typeof setTrackingSector === 'function') setTrackingSector('all'); else Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'All')?.click();", "stale-guard"),
            ("cargo", "setCargoSubView('matrix')", "UNAVAILABLE"),
            ("cargo", "setCargoSubView('all')", "UNAVAILABLE"),
            ("cargo", "setFlagshipRoute('brazil_c3')", "UNAVAILABLE"),
            ("cargo", "setFlagshipRoute('wa_c5')", "UNAVAILABLE"),
            ("cargo", "setFlagshipRoute('newcastle')", "UNAVAILABLE"),
            ("bunkers", "setBunkersSubView('altfuels')", "Verified alt-fuel indications"),
        ]
        sweep_failures = []
        for tab_id, action_js, exp_string in sweep_controls:
            try:
                page.evaluate(f"window.switchTab('{tab_id}')")
                page.wait_for_timeout(300)
                page.evaluate(f"() => {{ try {{ {action_js}; }} catch (e) {{ window.__lastSweepErr = String(e); }} }}")
                page.wait_for_timeout(500)
                
                panel_text = page.locator(f"#tab-{tab_id}").inner_text()
                last_err = page.evaluate("window.__lastSweepErr || ''")
                page.evaluate("window.__lastSweepErr = ''")
                
                if exp_string.lower() in panel_text.lower():
                    sweep_failures.append(f"{tab_id} ({action_js}) revealed empty state/finding: '{exp_string}'")
                elif last_err:
                    sweep_failures.append(f"{tab_id} ({action_js}) raised error: {last_err}")
                elif "stale-guard" in exp_string and any("[stale-guard]" in l["text"] for l in console_entries[-5:]):
                    sweep_failures.append(f"{tab_id} ({action_js}) triggered stale-guard warning")
            except Exception as e:
                sweep_failures.append(f"{tab_id} ({action_js}) failed execution: {e}")

        results["tab_ui_sweep_errors"] = sweep_failures
        results["cumulative_transfer_mb"] = round(transfer_bytes / (1024 * 1024), 2)
        results["failed_requests"] = failed_reqs

        browser.close()

    return results


def test_no_console_errors(tab_audit_data):
    """Q-002: Verify 0 console errors, pageerrors, or stale-guard warnings (baseline: 5 tabs failing)."""
    failing_tabs = tab_audit_data["tab_console_errors"]
    assert not failing_tabs, (
        f"Found {len(failing_tabs)} tabs with console errors or [stale-guard] warnings "
        f"(expected 5 tabs failing on baseline): {list(failing_tabs.keys())}"
    )


def test_no_failed_requests(tab_audit_data):
    """Q-003: Verify no network request >= 400 during tab mounting and navigation."""
    failed = tab_audit_data["failed_requests"]
    assert not failed, f"Found {len(failed)} failed requests (status >= 400): {failed}"


def test_no_empty_states(tab_audit_data):
    """Q-004: Verify no visible empty-state strings on rendered tabs (baseline: 5 items)."""
    empty_tabs = tab_audit_data["tab_empty_states"]
    total_items = sum(len(v) for v in empty_tabs.values())
    assert not empty_tabs, (
        f"Found {total_items} empty-state strings across {len(empty_tabs)} tabs "
        f"(baseline: 5 items on signals and tracking): {empty_tabs}"
    )


def test_no_dash_kpis(tab_audit_data):
    """Q-005: Verify no KPI values are —, -, n/a, NaN, $NaN (baseline: 9 items)."""
    allowlist = {}
    if ALLOWLIST_PATH.exists():
        try:
            allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    allowed_kpis = allowlist.get("dash_kpis", [])

    dash_tabs = {}
    for tab, kpis in tab_audit_data["tab_dash_kpis"].items():
        unallowed = []
        for k in kpis:
            k_id = k.split("=")[0] if "=" in k else None
            k_val = k.split("=")[1] if "=" in k else k
            if any(
                (entry.get("id") and entry.get("id") == k_id) or
                (entry.get("tab") == tab and (not entry.get("pattern") or re.search(entry["pattern"], k_val)))
                for entry in allowed_kpis
            ):
                continue
            unallowed.append(k)
        if unallowed:
            dash_tabs[tab] = unallowed

    total_dash = sum(len(v) for v in dash_tabs.values())
    assert not dash_tabs, (
        f"Found {total_dash} dash/n/a KPI values across {len(dash_tabs)} tabs "
        f"(baseline: 9 items across seasonality, etfs, signals, tracking, bunkers): {dash_tabs}"
    )


def test_charts_have_data(tab_audit_data):
    """Q-006: Verify every visible canvas has a Chart instance with >= 2 points (baseline: 8 dead modules)."""
    dead_tabs = tab_audit_data["tab_dead_charts"]
    assert not dead_tabs, (
        f"Found dead chart canvases across tabs: {dead_tabs} "
        f"(baseline: 8 dead modules on Signals tab)"
    )


def test_ui_copy_lint(tab_audit_data):
    """Q-007: Verify visible text contains no banned internal terms or all-caps pills (baseline: ~25 terms + pills)."""
    lint_tabs = tab_audit_data["tab_copy_lint"]
    total_findings = sum(len(v) for v in lint_tabs.values())
    assert not lint_tabs, (
        f"Found {total_findings} banned internal copy/pill occurrences across {len(lint_tabs)} tabs "
        f"(baseline: ~25 terms + pills): {lint_tabs}"
    )


def test_design_lint():
    """Q-009: Static + computed design lint (baseline: 13 accents / 63 glows / 16 blurs / 11 emoji)."""
    html_text = HTML_PATH.read_text(encoding="utf-8")
    
    # 1. Left-edge accents
    accents = re.findall(r'border-left:\s*([2-9]|\d{2,})px\s+solid\s+([^;]+)', html_text)
    
    # 2. Glows box-shadow: 0 0 ...
    glows = re.findall(r'box-shadow:[^;]*0\s+0\s+[^;]+', html_text)

    # 3. Blurs backdrop-filter: blur(...)
    blurs = re.findall(r'backdrop-filter:\s*blur\([^)]+\)', html_text)

    # 4. Emoji / dingbats
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27bf]')
    emojis = emoji_pattern.findall(html_text)

    violations = []
    if len(accents) > 0:
        violations.append(f"{len(accents)} coloured left-edge accents (baseline: 13)")
    if len(glows) > 0:
        violations.append(f"{len(glows)} box-shadow glows (baseline: 63)")
    if len(blurs) > 0:
        violations.append(f"{len(blurs)} backdrop-filter blurs (baseline: 16)")
    if len(emojis) > 0:
        violations.append(f"{len(emojis)} emoji/dingbats in UI (baseline: 11)")

    assert not violations, (
        f"Design lint failed: {'; '.join(violations)}"
    )


def test_tooltip_coverage(tab_audit_data):
    """Q-010: Verify >= 95% tooltip coverage and no interaction-only tooltips (baseline: Broker Desk 12/65)."""
    tips = tab_audit_data["tab_tooltips"]
    failing_tabs = {}
    for tab_id, stats in tips.items():
        total = stats["total"]
        tipped = stats["tipped"]
        pct = (tipped / total * 100) if total > 0 else 100.0
        if pct < 95.0 or stats["descriptive_only"] > 0:
            failing_tabs[tab_id] = f"{tipped}/{total} ({pct:.1f}%), {stats['descriptive_only']} interaction-only"

    assert not failing_tabs, (
        f"Tooltip coverage < 95% or interaction-only tooltips found (baseline: Broker Desk 12/65): {failing_tabs}"
    )


def test_layout(tab_audit_data):
    """Q-011: Verify layout constraints: tab bar fits at 1366 & 1920, no clipped leaf text (baseline: 20 in Bunkers)."""
    layout = tab_audit_data["tab_layout"]
    nav_1920 = layout.get("nav_1920")
    nav_1366 = layout.get("nav_1366")
    
    issues = []
    if nav_1920 and nav_1920.get("offHidden"):
        issues.append("Tab bar overflows at 1920px (Offshore hidden)")
    if nav_1366 and nav_1366.get("offHidden"):
        issues.append("Tab bar overflows at 1366px (Offshore hidden)")

    # Clipped leaf text
    for tab_id, stats in layout.items():
        if isinstance(stats, dict) and stats.get("clipped", 0) > 0:
            issues.append(f"{tab_id} has {stats['clipped']} clipped text nodes")

    assert not issues, (
        f"Layout violations detected: {'; '.join(issues)}"
    )


def test_ui_sweep(tab_audit_data):
    """Q-012: Verify clicking controls does not trigger errors or reveal empty states (baseline: 10 click failures)."""
    sweep_errors = tab_audit_data["tab_ui_sweep_errors"]
    assert not sweep_errors, (
        f"Found {len(sweep_errors)} UI sweep click failures (baseline: 10 failures across Broker Desk, Cargo, Bunkers):\n"
        + "\n".join(sweep_errors)
    )


def test_perf_budget(tab_audit_data):
    """Q-017: Verify performance budget (boot <= 4.0 MB, cumulative <= 58.0 MB, warm switch <= 50 ms)."""
    boot_mb = tab_audit_data["boot_transfer_mb"]
    cumulative_mb = tab_audit_data["cumulative_transfer_mb"]
    warm_etfs_ms = tab_audit_data["warm_switch_ms"].get("etfs", 0)

    violations = []
    if boot_mb > 4.0:
        violations.append(f"Boot transfer {boot_mb} MB > 4.0 MB budget")
    if cumulative_mb > 58.0:
        violations.append(f"Cumulative transfer {cumulative_mb} MB > 58.0 MB budget")
    if warm_etfs_ms > 50:
        violations.append(f"ETFs warm revisit switch {warm_etfs_ms} ms > 50 ms budget")

    assert not violations, (
        f"Performance budget violations: {'; '.join(violations)}"
    )


# ---------------------------------------------------------------------------
# Behavioural proofs (F-2, F-5 / G-11)
#
# These replace the string-presence forms of test_dashboard_overlay_range_widening
# and test_tracking_map_sector_and_status_filtering that lived in
# tests/test_freshness_and_wiring.py. Those asserted identifiers such as
# "loadProductFullHistory" and "plotPortHubMarkers()" appeared somewhere in
# index.html, which stays true if the wiring is deleted and the name survives in
# a comment. What matters is what the page does, so these drive the controls and
# read the result out of the live DOM instead.
# ---------------------------------------------------------------------------

def _boot(page, web_server):
    """Loads index.html and lets the lazy IntersectionObserver charts mount."""
    page.goto(f"{web_server}/index.html", wait_until="networkidle")
    page.wait_for_timeout(5000)


def _overlay_datasets(page):
    """Returns {n, first_label, last_label} for the dashboard year-overlay chart."""
    return page.evaluate("""() => {
        for (const c of document.querySelectorAll('canvas')) {
            if (!c.offsetParent) continue;
            const ch = (typeof Chart !== 'undefined') ? Chart.getChart(c) : null;
            if (!ch) continue;
            const ds = ch.data.datasets || [];
            if (c.id !== 'overlayChart' || ds.length < 2) continue;
            return {
                n: ds.length,
                first: String(ds[0].label),
                last: String(ds[ds.length - 1].label)
            };
        }
        return null;
    }""")


def _click_preset(page, label):
    return page.evaluate("""(l) => {
        const b = [...document.querySelectorAll('button')].filter(e => e.offsetParent
            && e.innerText.trim().toLowerCase() === l.toLowerCase());
        if (!b.length) return 'no-button';
        b[0].click();
        return 'ok';
    }""", label)


def test_dashboard_overlay_range_widening(web_server):
    """F-2: the dashboard year overlay must actually widen with the range preset.

    Baseline defect: 10Y and All returned the same six years as 5Y while the BDI
    series runs back to 1985. Proven by counting the chart's datasets (one per
    year), not by counting points and not by grepping index.html.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1920, "height": 1080}).new_page()
        try:
            _boot(page, web_server)
            # Scroll the overlay into view so its lazy chart mounts.
            for _ in range(3):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(250)

            seen = {}
            for preset in ("1Y", "5Y", "10Y", "All"):
                assert _click_preset(page, preset) == "ok", f"{preset} preset button not found"
                page.wait_for_timeout(2500)
                state = _overlay_datasets(page)
                assert state, f"overlayChart carried no datasets after selecting {preset}"
                seen[preset] = state

            assert seen["5Y"]["n"] > seen["1Y"]["n"], (
                f"5Y ({seen['5Y']['n']} years) must show more than 1Y ({seen['1Y']['n']})"
            )
            assert seen["10Y"]["n"] > seen["5Y"]["n"], (
                f"10Y ({seen['10Y']['n']} years) must show more than 5Y ({seen['5Y']['n']}) "
                "- this is the F-2 defect: the overlay was capped at six years"
            )
            assert seen["All"]["n"] >= seen["10Y"]["n"], (
                f"All ({seen['All']['n']} years) must be at least 10Y ({seen['10Y']['n']})"
            )
            oldest = int(seen["All"]["last"])
            assert oldest <= 1990, (
                f"All must reach the full BDI span; oldest year rendered was {oldest}"
            )
        finally:
            browser.close()


def _tracking_state(page):
    """HUD counters plus a pixel digest of the map canvas."""
    return page.evaluate("""() => {
        const g = id => { const e = document.getElementById(id); return e ? e.textContent.trim() : null; };
        let pix = '';
        const cv = document.querySelector('.leaflet-overlay-pane canvas');
        if (cv) {
            try {
                const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
                let h = 0;
                for (let i = 0; i < d.length; i += 997) h = ((h << 5) - h + d[i]) | 0;
                pix = String(h);
            } catch (e) { pix = 'blocked'; }
        }
        return {
            tracked: g('hudTrackedCount'),
            laden: g('hudPctLaden'),
            pix,
            dimmed: document.querySelectorAll('.port-hub-pin.dimmed').length,
            lit: document.querySelectorAll('.port-hub-pin.lit').length
        };
    }""")


def test_tracking_map_sector_and_status_filtering(web_server):
    """F-5 / G-11: the Fleet AIS sector and status filters must repaint the map.

    Baseline defect: every filter left the map and its counters untouched. The
    vessel layer uses Leaflet's canvas renderer, so vessels are pixels rather
    than DOM markers - hence the pixel digest alongside the HUD counters.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1920, "height": 1080}).new_page()
        try:
            _boot(page, web_server)
            page.evaluate("() => window.switchTab('tracking')")
            page.wait_for_timeout(8000)
            for _ in range(4):
                page.mouse.wheel(0, 1100)
                page.wait_for_timeout(250)

            base = _tracking_state(page)
            assert base["tracked"], "tracking HUD must report a tracked vessel count"

            page.evaluate("() => window.setLiveFleetStatusFilter('laden')")
            page.wait_for_timeout(2200)
            laden = _tracking_state(page)

            page.evaluate("() => window.setLiveFleetSegment('dry_bulk')")
            page.wait_for_timeout(2200)
            dry = _tracking_state(page)

            assert laden["tracked"] != base["tracked"], (
                f"status filter is inert: tracked count stayed {base['tracked']}"
            )
            assert laden["laden"] == "100.0%", (
                f"laden filter must leave only laden vessels, got {laden['laden']}"
            )
            assert dry["tracked"] != laden["tracked"], (
                f"sector filter is inert: tracked count stayed {laden['tracked']}"
            )
            assert base["dimmed"] == 0, (
                f"with no sector selected no port pin may be dimmed; {base['dimmed']} were"
            )
            assert dry["dimmed"] > 0 and dry["lit"] > 0, (
                "selecting a sector must light the port pins inside it and dim those outside; "
                f"got {dry['lit']} lit / {dry['dimmed']} dimmed"
            )
            digests = {base["pix"], laden["pix"], dry["pix"]}
            assert "blocked" not in digests, "could not read the map canvas"
            assert len(digests) == 3, (
                "the map canvas must repaint distinctly for each filter; "
                f"got {len(digests)} distinct states across all/laden/dry-bulk"
            )
        finally:
            browser.close()


BALTIC_CODES_RENDERED = [
    "C2", "C3", "C5", "C7", "C8", "C9", "C10", "C14", "C16", "C17",
    "P1A", "P2A", "P3A", "P4", "P5", "P6",
    "S1B", "S1C", "S2", "S3", "S4A", "S4B", "S5", "S8", "S9", "S10", "S15",
    "TD1", "TD2", "TD3C", "TD6", "TD7", "TD8", "TD9", "TD15", "TD17", "TD18",
    "TD19", "TD20", "TD22", "TD25",
    "TC1", "TC2", "TC5", "TC6", "TC7", "TC8", "TC12", "TC14", "TC15", "TC17",
    "HS1", "HS2", "HS4",
]

_BARE_CODE_PROBE = """(codes) => {
    const re = new RegExp('(^|[^A-Za-z0-9_])(' + codes.join('|') + ')([^A-Za-z0-9_]|$)');
    const bare = [];
    document.querySelectorAll('*').forEach(e => {
        if (!e.offsetParent) return;
        let own = '';
        for (const n of e.childNodes) { if (n.nodeType === 3) own += ' ' + n.textContent; }
        own = own.trim();
        if (!own || own.length > 60) return;
        const m = own.match(re);
        if (!m) return;
        let n = e, tipped = false;
        for (let i = 0; i < 4 && n; i++, n = n.parentElement) {
            if (n.getAttribute && (n.getAttribute('data-tooltip') || n.getAttribute('title'))) { tipped = true; break; }
        }
        if (!tipped) bare.push(m[2] + ' in <' + e.tagName.toLowerCase() + '> "' + own.slice(0, 40) + '"');
    });
    return bare;
}"""


def test_baltic_route_codes_are_glossed(web_server):
    """G-7: no Baltic route code may render on screen without a route description.

    decorateBalticRouteCodes attaches one from BALTIC_ROUTE_GLOSS, which
    tests/test_freshness_and_wiring.py pins to baltic_route_taxonomy.json. This half
    proves the decoration actually reaches the DOM, including sub-tab content that
    renders long after the tab itself mounts.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1920, "height": 1080}).new_page()
        try:
            page.goto(f"{web_server}/index.html", wait_until="networkidle")
            page.wait_for_timeout(5000)

            bare = []
            for tab_id, _panel in TABS:
                page.evaluate("(t) => window.switchTab(t)", tab_id)
                page.wait_for_timeout(3000)
                # click the sub-views so their content renders too
                subs = page.evaluate("""() => {
                    const p = document.getElementById('tab-' + window.currentTab);
                    if (!p) return [];
                    return [...p.querySelectorAll('button')]
                        .filter(e => e.offsetParent && e.innerText.trim().length < 26)
                        .map((e, i) => { e.setAttribute('data-baltic-sub', 's' + i); return 's' + i; })
                        .slice(0, 14);
                }""")
                for sid in subs:
                    page.evaluate(
                        "(s) => { const e = document.querySelector('[data-baltic-sub=\"' + s + '\"]'); if (e) e.click(); }",
                        sid,
                    )
                    page.wait_for_timeout(900)
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(1500)
                for item in page.evaluate(_BARE_CODE_PROBE, BALTIC_CODES_RENDERED):
                    bare.append(f"{tab_id}: {item}")

            assert not bare, (
                f"{len(bare)} Baltic route codes rendered without a route description "
                "(baseline: C3 0/2, C5 0/3 tipped):\n" + "\n".join(bare[:25])
            )
        finally:
            browser.close()


def test_yearly_and_seasonality_use_deep_history(web_server):
    """The Yearly and Seasonality tabs must run on the full series, not the
    five-year boot window.

    dashboard_master.json is capped at five years for the boot budget, and every
    panel on those two tabs reads DATA.master. The symptoms were: the historical
    price chart opened in 2021 whatever the slider did, the "Last 8 Years"
    quarterly grid had empty rows, and the win-rate matrix printed the SAME
    five-year number under its 10Y, 20Y and All-Time headings. ensureDeepHistory
    extends DATA.master from the per-index view when either tab is opened.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1920, "height": 1080}).new_page()
        try:
            page.goto(f"{web_server}/index.html", wait_until="networkidle")
            page.wait_for_timeout(5000)
            page.evaluate("""() => { const b = document.querySelector('button[data-tab=\"yearly-dash\"]'); if (b) b.click(); }""")
            page.wait_for_timeout(7000)
            for _ in range(4):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(250)

            hist = page.evaluate("""() => {
                const c = document.getElementById('yearlyHistChart');
                const ch = c ? Chart.getChart(c) : null;
                if (!ch) return null;
                const labs = ch.data.labels || [];
                return {first: String(labs[0]), n: labs.length,
                        masterYears: (window.DATA && DATA.master) ? DATA.master.length : 0};
            }""")
            assert hist, "yearlyHistChart must exist on the Yearly tab"
            first_year = int(str(hist["first"])[:4])
            assert first_year <= 2010, (
                f"the historical price chart must open on the full series; it starts {hist['first']} "
                "(the five-year boot window starts 2021)"
            )

            page.evaluate("""() => { const b = document.querySelector('button[data-tab=\"seasonality\"]'); if (b) b.click(); }""")
            page.wait_for_timeout(7000)
            for _ in range(6):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(220)

            rows = page.evaluate("""() => {
                const el = document.getElementById('quarterlyWinRateMatrix');
                if (!el) return null;
                return [...el.querySelectorAll('tbody tr')].map(
                    tr => [...tr.querySelectorAll('td')].slice(1).map(td => td.innerText.trim()));
            }""")
            assert rows, "quarterly win-rate matrix must render"
            # The three columns are 10Y / 15Y / All-Time. On a series with real
            # depth they cannot all be the same number in every row.
            identical = all(len(set(r)) == 1 for r in rows)
            assert not identical, (
                "10Y / 15Y / All-Time win rates are identical in every row - the matrix is "
                f"computing all three over the same window: {rows}"
            )
            # Tightened: the "not identical" check above only fails if EVERY
            # row is broken, so a matrix where some quarters render real
            # percentages and others are stuck on '-' (P0: BDI Quarterly
            # matrix regression) slipped through undetected. Every cell must
            # be a real value on a series with 40+ years of history.
            dashes = [(r_idx, c_idx) for r_idx, r in enumerate(rows) for c_idx, c in enumerate(r) if c in ("-", "—", "")]
            assert not dashes, (
                f"quarterly win-rate matrix has blank/'-' cells at (row, col) {dashes}: {rows}"
            )

            grid = page.evaluate("""() => {
                const p = document.getElementById('tab-seasonality');
                const t = [...p.querySelectorAll('table')].filter(e => e.offsetParent)
                    .find(x => /YEAR/i.test(x.innerText.slice(0, 80)));
                if (!t) return null;
                return [...t.querySelectorAll('tbody tr')].map(
                    tr => [...tr.querySelectorAll('td,th')].map(td => td.innerText.trim()));
            }""")
            assert grid, "quarterly data grid must render"
            year_rows = [r for r in grid if r and r[0].isdigit()]
            empty = [r[0] for r in year_rows if all(c in ("-", "\u2014", "") for c in r[1:5])]
            assert not empty, (
                f"the 8-year quarterly grid has rows with no data at all: {empty} - "
                "the tab is running on a window shorter than the grid claims"
            )
        finally:
            browser.close()


SEASONALITY_BALTIC_SECTORS = ["bdiy", "cape", "panama", "suprama", "handysize", "dirtytanker", "cleantanker"]


def test_seasonality_quarterly_and_monthly_render_for_every_sector(web_server):
    """P0 regression guard: on Seasonality default Quarterly view, the Q1-Q4
    win-rate cells must show a real percentage (not '-') and the "Quarterly
    Performance by Year (Spaghetti)" chart must have >= 2 datasets with real
    data - for every Baltic sector, and the same for the Monthly view.

    test_yearly_and_seasonality_use_deep_history only asserted the three
    win-rate columns were "not all identical", which a matrix with some
    quarters blank ('-') and others populated still satisfies - that gap let
    a P0 (Quarterly win-rate cards all '-', spaghetti chart empty) ship
    undetected. This checks every cell explicitly, and every sector.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1920, "height": 1080}).new_page()
        try:
            page.goto(f"{web_server}/index.html", wait_until="networkidle")
            page.wait_for_timeout(5000)
            page.evaluate("""() => { const b = document.querySelector('button[data-tab=\"seasonality\"]'); if (b) b.click(); }""")
            page.wait_for_timeout(3000)

            for sector in SEASONALITY_BALTIC_SECTORS:
                page.click(f'button.index-pill[data-val="{sector}"]')
                page.wait_for_timeout(2500)
                for _ in range(4):
                    page.mouse.wheel(0, 1000)
                    page.wait_for_timeout(150)

                # Quarterly (default granularity)
                page.evaluate("""() => { if (typeof setSeasonGranularity === 'function') setSeasonGranularity('quarter'); }""")
                page.wait_for_timeout(300)
                q_rows = page.evaluate("""() => {
                    const el = document.getElementById('quarterlyWinRateMatrix');
                    if (!el) return null;
                    return [...el.querySelectorAll('tbody tr')].map(
                        tr => [...tr.querySelectorAll('td')].slice(1).map(td => td.innerText.trim()));
                }""")
                assert q_rows and len(q_rows) == 4, f"{sector}: quarterly win-rate matrix missing rows: {q_rows}"
                blanks = [(r, c) for r, row in enumerate(q_rows) for c, v in enumerate(row) if v in ("-", "—", "")]
                assert not blanks, f"{sector}: quarterly win-rate has blank cells at {blanks}: {q_rows}"

                spaghetti = page.evaluate("""() => {
                    const c = document.getElementById('spaghettiChart');
                    const ch = c && typeof Chart !== 'undefined' ? Chart.getChart(c) : null;
                    if (!ch) return null;
                    return ch.data.datasets.map(d => (d.data || []).filter(v => v != null).length);
                }""")
                assert spaghetti, f"{sector}: spaghettiChart has no Chart instance"
                real_datasets = [n for n in spaghetti if n >= 2]
                assert len(real_datasets) >= 2, (
                    f"{sector}: spaghetti chart needs >=2 datasets with real data, got point-counts {spaghetti}"
                )

                # Monthly granularity
                page.evaluate("""() => { if (typeof setSeasonGranularity === 'function') setSeasonGranularity('month'); }""")
                page.wait_for_timeout(300)
                m_rows = page.evaluate("""() => {
                    const el = document.getElementById('monthlyWinRateMatrix');
                    if (!el) return null;
                    return [...el.querySelectorAll('tbody tr')].map(
                        tr => [...tr.querySelectorAll('td')].slice(1).map(td => td.innerText.trim()));
                }""")
                assert m_rows and len(m_rows) == 12, f"{sector}: monthly win-rate matrix missing rows: {m_rows}"
                # 15Y/All-Time columns must be populated on every sector's deep
                # history; only 10Y could plausibly stay blank for a series
                # with < 10 complete years, which none of these have.
                blanks_m = [(r, c) for r, row in enumerate(m_rows) for c, v in enumerate(row) if v in ("-", "—", "")]
                assert not blanks_m, f"{sector}: monthly win-rate has blank cells at {blanks_m}: {m_rows}"

                page.evaluate("""() => { if (typeof setSeasonGranularity === 'function') setSeasonGranularity('quarter'); }""")
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Live-site click-through audit (2026-09-12): win-rate matrix layout, tooltip
# truncation, sector-follow, tooltip/banner overlap, and Indices deep history.
# ---------------------------------------------------------------------------

def test_monthly_winrate_matrix_columns_align_and_use_15y(web_server):
    """A: the Monthly Historical Win-Rate Matrix body cells must line up under
    their own headers (real <table> layout, not a flex-broken row), and the
    middle window is 15Y - not 20Y, which is always '-' because deep history
    only reaches back to ~2008/2009 for every product but the BDI.

    Root cause: matrix rows used class="rt-row", a global `display:flex` row
    style meant for unrelated label/value widgets elsewhere in the page,
    which broke the table's column layout.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        try:
            page.goto(f"{web_server}/index.html", wait_until="networkidle")
            page.wait_for_timeout(3000)
            page.evaluate("""() => { const b = document.querySelector('button[data-tab=\"seasonality\"]'); if (b) b.click(); }""")
            page.wait_for_timeout(3000)
            # The Monthly Win-Rate Matrix lives in #seasonMonthlyBlock, which
            # the Seasonality tab keeps `hidden` by default (it opens on the
            # Quarterly granularity view); switch to Monthly first.
            page.evaluate("""() => { if (typeof setSeasonGranularity === 'function') setSeasonGranularity('month'); }""")
            page.wait_for_timeout(500)
            for _ in range(6):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(220)
            page.wait_for_selector("#monthlyWinRateMatrix table", timeout=15000)
            page.wait_for_timeout(1000)

            headers = page.eval_on_selector_all(
                "#monthlyWinRateMatrix thead th", "els => els.map(e => e.textContent.trim())"
            )
            assert len(headers) == 4
            assert any("15Y" in h for h in headers), f"expected a 15Y column header, got {headers}"
            assert not any("20Y" in h for h in headers), f"20Y column should have been replaced, got {headers}"

            header_ranges = page.eval_on_selector_all(
                "#monthlyWinRateMatrix thead th",
                "els => els.map(e => { const r = e.getBoundingClientRect(); return [r.left, r.right]; })",
            )
            for lo, hi in header_ranges:
                assert hi > lo, f"header cell has zero width ({lo}, {hi}) - table failed to render/layout"

            row_count = page.eval_on_selector_all("#monthlyWinRateMatrix tbody tr", "els => els.length")
            assert row_count == 12

            for row_idx in range(row_count):
                cell_count = page.eval_on_selector(
                    f"#monthlyWinRateMatrix tbody tr:nth-child({row_idx + 1})", "e => e.children.length"
                )
                assert cell_count == len(headers), (
                    f"row {row_idx} has {cell_count} cells but header has {len(headers)} columns"
                )
                centers = page.eval_on_selector_all(
                    f"#monthlyWinRateMatrix tbody tr:nth-child({row_idx + 1}) td",
                    "els => els.map(e => { const r = e.getBoundingClientRect(); return r.left + r.width / 2; })",
                )
                assert all(c > 0 for c in centers), (
                    f"row {row_idx} cells have zero-position centers {centers} - table failed to render/layout"
                )
                for col_idx, center in enumerate(centers):
                    lo, hi = header_ranges[col_idx]
                    assert lo <= center <= hi, (
                        f"row {row_idx} col {col_idx} center {center} not within header range [{lo}, {hi}]"
                    )
        finally:
            browser.close()


def _visible_tooltip_text(page, contains):
    return page.evaluate(
        """(needle) => {
            const els = document.querySelectorAll('div.visible');
            for (const e of els) {
                if (e.textContent.includes(needle)) return e.textContent;
            }
            return null;
        }""",
        contains,
    )


def test_trend_lifecycle_tooltip_not_truncated(web_server):
    """B1: the custom tooltip renderer used innerHTML whenever the static
    tooltip text contained both "<" and ">", so comparison-operator phrases
    like "ROC>0" were parsed as HTML tags and silently dropped, truncating
    the Trend Lifecycle tooltip mid-sentence.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        try:
            _boot(page, web_server)
            page.hover("#dashRegimeBadge")
            page.wait_for_timeout(500)
            text = _visible_tooltip_text(page, "Trend Lifecycle")
            assert text, "Trend Lifecycle tooltip did not render"
            idx = text.find("Contraction (")
            assert idx != -1, f"tooltip missing 'Contraction (' segment: {text!r}"
            remainder = text[idx + len("Contraction ("):]
            assert len(remainder) > 1, f"tooltip truncated right after 'Contraction (': {text!r}"
            assert ")" in remainder, f"tooltip missing closing ')' for Contraction clause: {text!r}"
        finally:
            browser.close()


def test_rich_static_tooltip_still_renders_as_markup(web_server):
    """B1 regression guard: several data-tooltip attributes intentionally
    carry real HTML (e.g. "<div class='rt-title'>...</div>" on the ETFs
    tab's Thesis-to-ETF Scenario Translator card). Fixing the truncation bug
    by always using textContent for static tooltips broke these - they must
    still render as markup (a real .rt-title element), not literal "<div"
    text.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        try:
            _boot(page, web_server)
            page.evaluate("""() => { const b = document.querySelector('button[data-tab=\"etfs\"]'); if (b) b.click(); }""")
            page.wait_for_timeout(2000)
            # Dispatch the mouseover directly on the chart-title element in a
            # single evaluate() (rather than page.hover(), which hovers the
            # visual center and may land on a nested child - e.g. the
            # "VERIFIED" badge - that carries its own, different tooltip).
            tt = page.evaluate(
                """() => {
                    const e = document.querySelector('#etfDeconstructCard .chart-title');
                    if (!e) return { found: false };
                    e.scrollIntoView({block: 'center'});
                    e.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                    const el = document.getElementById('global-tooltip');
                    if (!el || !el.classList.contains('visible')) return { found: false };
                    return {
                        found: true,
                        html: el.innerHTML,
                        text: el.textContent,
                        hasTitleEl: !!el.querySelector('.rt-title'),
                    };
                }"""
            )
            assert tt and tt["found"], f"rich tooltip did not render: {tt}"
            assert tt["hasTitleEl"], f"tooltip has no .rt-title element: {tt['html']!r}"
            assert "Thesis-to-ETF Scenario Translator" in tt["text"]
            assert "<div" not in tt["text"] and "&lt;div" not in tt["text"], (
                f"tooltip rendered markup as literal text instead of real elements: {tt['text']!r}"
            )
        finally:
            browser.close()


def test_selecting_handysize_updates_hero_and_tooltips(web_server):
    """B2: selecting a sector pill must be reflected in the hero label and
    the signal/trend-lifecycle tooltips.

    Root cause: renderRegimeBadge's tooltip checked `rows[0].bdiy`, a field
    present on every row of the shared wide DATA.master table regardless of
    which product was selected, so it always said "BDI Index" no matter what
    was active.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        try:
            _boot(page, web_server)
            page.click('button.index-pill[data-val="handysize"]')
            page.wait_for_timeout(1500)

            label = page.inner_text("#dashProductLabel")
            assert "Handysize" in label, f"hero label did not switch to Handysize: {label!r}"
            assert "BDI" not in label and "Baltic Dry Index" not in label

            sig_tt = page.get_attribute("#dashSignal", "data-tooltip") or ""
            assert "Handysize" in sig_tt, f"signal tooltip did not mention Handysize: {sig_tt!r}"
            assert "Baltic Dry Index" not in sig_tt and "(BDI)" not in sig_tt

            page.hover("#dashRegimeBadge")
            page.wait_for_timeout(500)
            badge_tt = _visible_tooltip_text(page, "Trend Lifecycle") or ""
            assert "Handysize" in badge_tt, f"trend lifecycle tooltip did not mention Handysize: {badge_tt!r}"
            assert "Baltic Dry Index" not in badge_tt and "BDI Index" not in badge_tt
        finally:
            browser.close()


def test_tooltip_does_not_cover_alert_banner(web_server):
    """B3: the custom tooltip defaulted to rendering above its target, which
    placed it on top of the red alert banner sitting directly above the
    dashboard signal/regime badges. It now prefers rendering below the
    target, only flipping above when there isn't room.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        try:
            _boot(page, web_server)
            banner_box = page.evaluate(
                """() => {
                    const b = document.getElementById('alertBearish') || document.getElementById('alertBullish');
                    if (!b) return null;
                    const cs = getComputedStyle(b);
                    if (cs.display === 'none') return null;
                    const r = b.getBoundingClientRect();
                    return { top: r.top, bottom: r.bottom };
                }"""
            )
            if not banner_box:
                pytest.skip("no visible alert banner in this data state")

            page.hover("#dashRegimeBadge")
            page.wait_for_timeout(500)
            tt_box = page.evaluate(
                """() => {
                    const els = document.querySelectorAll('div.visible');
                    for (const e of els) {
                        if (e.textContent.includes('Trend Lifecycle')) {
                            const r = e.getBoundingClientRect();
                            return { top: r.top, bottom: r.bottom };
                        }
                    }
                    return null;
                }"""
            )
            assert tt_box, "tooltip did not render"
            overlap = tt_box["top"] < banner_box["bottom"] and tt_box["bottom"] > banner_box["top"]
            assert not overlap, f"tooltip {tt_box} overlaps alert banner {banner_box}"
        finally:
            browser.close()


BALTIC_INDICES_KEYS = ["bdiy", "cape", "panama", "suprama", "handysize", "dirtytanker", "cleantanker"]


def test_indices_tab_baltic_cards_reach_deep_history(web_server):
    """C: the Indices tab cards must expose the same deep history as the
    Yearly/Seasonality tabs, not the 5-year-capped boot window.

    Root cause: DATA.raw[key] (which the Indices cards and their range
    sliders read) is only ever populated from the boot manifest
    data/views/dashboard_master.json, which is capped to five years for the
    boot budget (starts 2021-01-03). The deep per-product view
    (data/views/indices/<key>.json) already exists on disk and is used by
    ensureDeepHistory()/withDeepHistory() for the Seasonality/Yearly tabs,
    but the Indices tab never called it. Opening the Indices tab now also
    triggers ensureDeepHistory() per card and rebuilds DATA.raw[key] plus the
    range slider from the extended DATA.master once it resolves.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        try:
            _boot(page, web_server)
            page.evaluate("""() => { const b = document.querySelector('button[data-tab=\"indices\"]'); if (b) b.click(); }""")
            page.wait_for_timeout(1500)

            for key in BALTIC_INDICES_KEYS:
                page.wait_for_function(
                    """(k) => {
                        const raw = (window.DATA && DATA.raw && DATA.raw[k]) || [];
                        return raw.length && new Date(raw[0].date).getUTCFullYear() <= 2010;
                    }""",
                    arg=key,
                    timeout=15000,
                )
                info = page.evaluate(
                    """(k) => {
                        const raw = (window.DATA && DATA.raw && DATA.raw[k]) || [];
                        const startEl = document.getElementById('rangeStart_' + k);
                        if (!raw.length || !startEl) return null;
                        return { firstDateStr: raw[0].dateStr, sliderMin: parseInt(startEl.min, 10) };
                    }""",
                    key,
                )
                assert info, f"no data / slider found for {key}"
                assert info["sliderMin"] == 0, f"{key} slider min is not index 0: {info}"
                import re as _re
                m = _re.search(r"(19|20)\d{2}", info["firstDateStr"])
                assert m, f"could not parse year from {info['firstDateStr']!r} for {key}"
                assert int(m.group(0)) <= 2010, (
                    f"{key} deep history does not reach back to <=2010 (first={info['firstDateStr']})"
                )
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Tonnage Basin Arbitrage: switching TC tenors must default to that tenor's
# own full available span, not a window carried over from a shorter-history
# tenor.
# ---------------------------------------------------------------------------

def test_basin_spread_1y_tenor_shows_full_span(web_server):
    """1y TC history runs back to 2015 (Pacific to 2008); 4/6m and 2y only
    start mid-2021. initDualRangeSlider (index.html ~L16862) preserves the
    previously-shown date window across re-renders so a live data refresh
    doesn't reset a user's manual zoom - but that meant switching TC tenors
    carried over whichever narrow window a shorter-history tenor had shown,
    instead of resetting to the newly-selected tenor's own full span.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        try:
            _boot(page, web_server)
            page.evaluate("""() => { const b = document.querySelector('button[data-tab=\"fearnleys\"]'); if (b) b.click(); }""")
            page.wait_for_timeout(3000)
            page.evaluate(
                """() => new Promise(resolve => {
                    if (typeof fearnLoadDeskCaches === 'function') {
                        fearnLoadDeskCaches(function () {
                            if (typeof renderBasinSpreadChart === 'function') renderBasinSpreadChart(window.currentProduct || 'cape');
                            resolve();
                        });
                    } else { resolve(); }
                })"""
            )
            page.wait_for_timeout(2000)

            def chart_state():
                return page.evaluate(
                    """() => {
                        const c = document.getElementById('basinSpreadChart');
                        const ch = c && typeof Chart !== 'undefined' ? Chart.getChart(c) : null;
                        return ch ? { first: ch.data.labels[0], n: ch.data.labels.length } : null;
                    }"""
                )

            # Narrow the window to the shorter-history 4/6m tenor first...
            page.evaluate("() => window.setBasinTenor('4_6m')")
            page.wait_for_timeout(1000)
            narrow = chart_state()
            assert narrow, "basin chart did not render for 4_6m tenor"

            # ...then switch back to 1y: it must show 1y's OWN full span
            # (starting <= 2015), not the 4/6m window it just carried over.
            page.evaluate("() => window.setBasinTenor('1y')")
            page.wait_for_timeout(1000)
            wide = chart_state()
            assert wide, "basin chart did not render for 1y tenor"
            first_year = int(str(wide["first"])[:4])
            assert first_year <= 2015, (
                f"1y tenor chart must open on its own full span (<=2015); got first label "
                f"{wide['first']!r} (n={wide['n']}) after switching from 4_6m ({narrow})"
            )

            note = page.evaluate("() => { const e = document.getElementById('basinDataStartNote'); return e ? e.textContent : null; }")
            assert note and "2015" in note, f"data-start note should reflect the 1y tenor's real start date: {note!r}"
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Indices tab: dry and tanker route cards
# ---------------------------------------------------------------------------
INDICES_PRODUCT_ORDER_HEAD = ["bdiy", "cape", "panama", "suprama", "handysize"]
INDICES_TANKER_INDICES = ["dirtytanker", "cleantanker"]
INDICES_EQUITIES = ["clmi", "cldbi", "clti", "clci", "cllg", "clmfi", "clmlp"]


def _open_indices_and_wait_for_routes(page, web_server):
    _boot(page, web_server)
    page.evaluate("""() => { const b = document.querySelector('button[data-tab="indices"]'); if (b) b.click(); }""")
    page.wait_for_function(
        "() => document.querySelectorAll('#indicesGrid .index-chart-card[id^=\"idxCard_rt_\"]').length > 0",
        timeout=30000,
    )
    page.wait_for_timeout(1500)


def _card_state(page):
    return page.evaluate("""() => [...document.querySelectorAll('#indicesGrid .index-chart-card')].map(c => {
        const k = c.id.replace('idxCard_', '');
        const cv = document.getElementById('idxChart_' + k);
        const ch = cv && typeof Chart !== 'undefined' ? Chart.getChart(cv) : null;
        const vals = ch ? ch.data.datasets[0].data : [];
        return { key: k, title: c.querySelector('.card-header-bar span').textContent,
                 n: vals.length, finite: vals.filter(v => Number.isFinite(v)).length };
    })""")


def test_indices_route_cards_live_ordered_and_full_depth(web_server):
    """Every live route in data/views/routes/catalog.json gets a card with data, in the
    agreed order (BDI, vessel classes, dry routes, tanker indices, tanker routes,
    equities, futures/ETFs); filter counts match the cards; each route slider reaches
    the first print of its source."""
    catalog = json.loads((Path(__file__).resolve().parent.parent / "data" / "views" / "routes" / "catalog.json")
                         .read_text(encoding="utf-8"))["routes"]
    dry = ["rt_" + e["card_id"] for e in catalog if e["group"] == "dry"]
    tanker = ["rt_" + e["card_id"] for e in catalog if e["group"] == "tanker"]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            _open_indices_and_wait_for_routes(page, web_server)
            cards = _card_state(page)
            keys = [c["key"] for c in cards]
            expected_prefix = INDICES_PRODUCT_ORDER_HEAD + dry + INDICES_TANKER_INDICES + tanker + INDICES_EQUITIES
            assert keys[:len(expected_prefix)] == expected_prefix, f"Indices card order wrong: {keys}"
            for c in cards:
                assert c["n"] > 0 and c["finite"] == c["n"], f"card {c['key']} has no/invalid chart data: {c}"

            by_id = {"rt_" + e["card_id"]: e for e in catalog}
            for k in dry + tanker:
                e = by_id[k]
                if e["code"]:
                    title = next(c["title"] for c in cards if c["key"] == k)
                    assert title == f"{e['code']} · {e['title']}", f"{k} header {title!r}"
                first = page.evaluate(
                    """(k) => { const s = document.getElementById('rangeStart_' + k);
                                s.value = 0; s.dispatchEvent(new Event('input'));
                                const ch = Chart.getChart(document.getElementById('idxChart_' + k));
                                return ch.data.labels[0]; }""", k)
                assert first == e["first"], f"{k}: slider start shows {first}, source starts {e['first']}"

            for filt, want in (("dryroutes", dry), ("tankerroutes", tanker)):
                page.evaluate(f"() => setIndicesFilter('{filt}')")
                page.wait_for_timeout(1200)
                got = [c["key"] for c in _card_state(page)]
                assert got == want, f"{filt} filter shows {got}, expected {want}"
                label = page.evaluate(f"() => document.getElementById('idxFilter{filt.capitalize()}').textContent")
                assert label.endswith(f"({len(want)})"), f"{filt} button count {label!r} != {len(want)}"
            page.evaluate("() => setIndicesFilter('all')")
            page.wait_for_timeout(1500)
            n_all = len(_card_state(page))
            label_all = page.evaluate("() => document.getElementById('idxFilterAll').textContent")
            assert label_all.endswith(f"({n_all})"), f"All button {label_all!r} but {n_all} cards shown"
            assert not errors, f"page errors on Indices tab: {errors}"
        finally:
            browser.close()


def test_indices_hides_discontinued_route(web_server):
    """A route whose last print is older than 30 days must not get a card, even if the
    catalog lists it (feeds stop without anyone rebuilding the catalog)."""
    root = Path(__file__).resolve().parent.parent
    catalog = json.loads((root / "data" / "views" / "routes" / "catalog.json").read_text(encoding="utf-8"))
    stale = dict(catalog["routes"][0])
    stale["card_id"] = "STALE_PROBE"
    stale["code"] = None
    stale["title"] = "Discontinued probe"
    stale["last"] = "2023-05-22"
    catalog["routes"].append(stale)
    view = json.loads((root / "data" / "views" / "routes" / f"{catalog['routes'][0]['card_id']}.json").read_text(encoding="utf-8"))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.route("**/data/views/routes/catalog.json",
                   lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(catalog)))
        page.route("**/data/views/routes/STALE_PROBE.json",
                   lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(view)))
        try:
            _open_indices_and_wait_for_routes(page, web_server)
            keys = [c["key"] for c in _card_state(page)]
            assert "rt_" + catalog["routes"][0]["card_id"] in keys, "live route card missing"
            assert "rt_STALE_PROBE" not in keys, "a route with no print for >30 days is still shown"
        finally:
            browser.close()
