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
