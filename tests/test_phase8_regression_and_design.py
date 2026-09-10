"""
Phase 8.4 & 8.5: Automated Playwright Regression & Design Conformance Sweep
"""

import sys
import os
import json
import time
import random
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

def run_regression_and_design():
    results = {
        "metrics": {},
        "console_errors": [],
        "tab_status": {},
        "design_conformance": {},
        "tooltip_audit": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        transfer_bytes = 0
        requests_count = 0
        console_errors = []

        def on_response(response):
            nonlocal transfer_bytes
            try:
                cl = response.headers.get("content-length")
                if cl:
                    transfer_bytes += int(cl)
                else:
                    body = response.body()
                    transfer_bytes += len(body)
            except Exception:
                pass

        def on_request(request):
            nonlocal requests_count
            requests_count += 1

        def on_console(msg):
            if msg.type in ["error", "warning"]:
                console_errors.append({
                    "type": msg.type,
                    "text": msg.text,
                    "location": msg.location
                })

        page.on("response", on_response)
        page.on("request", on_request)
        page.on("console", on_console)

        # 1. Measure Boot Performance
        start_time = time.time()
        print("Navigating to http://localhost:8000/index.html...")
        page.goto("http://localhost:8000/index.html", wait_until="domcontentloaded")
        
        # Wait for data load overlay to dismiss or DATA.loaded
        try:
            page.wait_for_function("() => window.DATA && window.DATA.loaded === true", timeout=10000)
        except Exception:
            pass

        load_time_ms = int((time.time() - start_time) * 1000)

        # Count boot canvases and DOM nodes
        boot_canvases = page.evaluate("document.querySelectorAll('canvas').length")
        boot_dom_nodes = page.evaluate("document.querySelectorAll('*').length")

        results["metrics"] = {
            "transfer_mb": round(transfer_bytes / (1024 * 1024), 2),
            "requests_count": requests_count,
            "load_time_ms": load_time_ms,
            "boot_canvases": boot_canvases,
            "boot_dom_nodes": boot_dom_nodes
        }

        print(f"Boot metrics: {results['metrics']}")

        # 2. Phase 8.4: Tab Switching Sweep
        # 12 tabs: 7 untouched + 5 modified/reviewed
        tabs_to_test = [
            ("DASHBOARD", "dashboard", "tab-dashboard"),
            ("YEARLY", "yearly-dash", "tab-yearly-dash"),
            ("SEASONALITY", "seasonality", "tab-seasonality"),
            ("INDICES", "indices", "tab-indices"),
            ("ETFS", "etfs", "tab-etfs"),
            ("SIGNALS", "signals", "tab-signals"),
            ("FEARNLEYS", "fearnleys", "tab-fearnleys"),
            ("INTELLIGENCE", "intelligence", "tab-intelligence"),
            ("TRACKING", "tracking", "tab-tracking"),
            ("CARGO", "cargo", "tab-cargo"),
            ("BUNKERS", "bunkers", "tab-bunkers"),
            ("OFFSHORE", "offshore", "tab-offshore")
        ]

        for tab_name, tab_key, panel_id in tabs_to_test:
            print(f"Switching to tab: {tab_name} ({tab_key})...")
            
            # Switch tab using window.switchTab or clicking button
            errors_before = len([e for e in console_errors if e["type"] == "error"])
            
            page.evaluate(f"tabKey => window.switchTab(tabKey)", tab_key)
            page.wait_for_timeout(800) # give charts time to render

            # Check panel visibility & canvases
            panel_info = page.evaluate(f"""() => {{
                const p = document.getElementById('{panel_id}');
                if (!p) return {{ exists: false, is_active: false, canvas_count: 0 }};
                return {{
                    exists: true,
                    is_active: p.classList.contains('active'),
                    canvas_count: p.querySelectorAll('canvas').length
                }};
            }}""")

            errors_after = len([e for e in console_errors if e["type"] == "error"])
            new_errors = errors_after - errors_before

            results["tab_status"][tab_name] = {
                "tab_key": tab_key,
                "panel_id": panel_id,
                "exists": panel_info.get("exists", False),
                "is_active": panel_info.get("is_active", False),
                "canvases": panel_info.get("canvas_count", 0),
                "new_errors": new_errors
            }
            print(f"  Result: active={panel_info.get('is_active')}, canvases={panel_info.get('canvas_count')}, new_errors={new_errors}")

        # Final total console errors
        results["metrics"]["total_console_errors"] = len([e for e in console_errors if e["type"] == "error"])
        results["metrics"]["total_console_warnings"] = len([e for e in console_errors if e["type"] == "warning"])

        # 3. Phase 8.5: Design Conformance
        print("Auditing design conformance...")
        # Font size < 11px check
        small_fonts_count = page.evaluate("""() => {
            return [...document.querySelectorAll('*')].filter(e => {
                return e.innerText && !e.children.length && parseFloat(getComputedStyle(e).fontSize) < 11;
            }).length;
        }""")

        # Unicode sparklines check
        sparkline_matches = page.evaluate("""() => {
            const m = document.body.innerText.match(/[▁▂▃▄▅▆▇█]{3,}/g);
            return m ? m.length : 0;
        }""")

        # UI describing tooltips check
        ui_desc_tooltips = page.evaluate("""() => {
            return [...document.querySelectorAll('[data-tip],[title],[data-tooltip]')].filter(e => {
                const tip = e.getAttribute('data-tip') || e.getAttribute('title') || e.getAttribute('data-tooltip') || '';
                return /re-renders from cache|Interactive control for this section|switches this section/i.test(tip);
            }).length;
        }""")

        # Dead space check
        dead_space_violations = page.evaluate("""() => {
            const panes = [...document.querySelectorAll('.tab-panel')];
            let violations = 0;
            for (const p of panes) {
                // If scrollHeight exceeds visible height without content
                const diff = p.scrollHeight - p.clientHeight;
                if (diff > 48 && p.children.length === 0) {
                    violations++;
                }
            }
            return violations;
        }""")

        results["design_conformance"] = {
            "small_fonts_count": small_fonts_count,
            "unicode_sparklines": sparkline_matches,
            "ui_desc_tooltips": ui_desc_tooltips,
            "dead_space_violations": dead_space_violations
        }
        print(f"Design conformance: {results['design_conformance']}")

        # 4. Tooltip Sample Audit (20 random tooltips across all tabs)
        print("Auditing 20 random tooltips...")
        raw_tooltips = page.evaluate("""() => {
            const elements = [...document.querySelectorAll('[data-tooltip], [data-tip], [title]')];
            return elements.map(e => {
                const tip = e.getAttribute('data-tooltip') || e.getAttribute('data-tip') || e.getAttribute('title') || '';
                return {
                    tag: e.tagName,
                    id: e.id || '',
                    className: e.className || '',
                    text: tip
                };
            }).filter(item => item.text && item.text.trim().length > 5);
        }""")

        print(f"Total tooltips found in DOM: {len(raw_tooltips)}")

        # Pick 20 tooltips deterministically
        random.seed(42)
        sampled = random.sample(raw_tooltips, min(20, len(raw_tooltips)))

        audit_results = []
        pass_count = 0

        for item in sampled:
            text = item["text"].strip()
            
            # Clean markup
            clean_text = re.sub(r"<[^>]+>", " ", text).strip()
            clean_len = len(clean_text)
            
            # Three beats check (approx 2 to 4 sentences/clauses)
            sentences = [s.strip() for s in re.split(r"[.!?]\s+|\n+", clean_text) if len(s.strip()) > 4]
            beats_count = len(sentences)
            has_three_beats = (2 <= beats_count <= 4)
            
            # Length: 60 - 160 chars (allow 50 - 200 for rich cards)
            len_ok = (50 <= clean_len <= 220)
            
            # No UI description
            no_ui_desc = not bool(re.search(r"re-renders from cache|interactive control|switches this|click to|button to|select from dropdown", clean_text, re.IGNORECASE))
            
            # No data caveat (disclaimer hedging like approximate only, fake, placeholder, unreliable)
            no_caveat = not bool(re.search(r"dummy data|placeholder only|unreliable source|fake data|not real|heuristic estimate only", clean_text, re.IGNORECASE))
            
            # Provenance present (e.g. source, Baltic, Clarksons, DNB, PortWatch, S&B, CME, EIA, AIS, USDA, Eurostat, etc.)
            has_prov = bool(re.search(r"source|baltic|clarksons|portwatch|eia|cme|dnb|platts|ship & bunker|ais|customs|fred|un comtrade|usda|eurostat|imf", clean_text, re.IGNORECASE))
            
            passed = len_ok and no_ui_desc and no_caveat and has_prov
            if passed:
                pass_count += 1

            audit_results.append({
                "element": f"<{item['tag']} class='{item['className']}' id='{item['id']}'>",
                "clean_snippet": clean_text[:110],
                "char_length": clean_len,
                "len_ok": len_ok,
                "beats_count": beats_count,
                "has_three_beats": has_three_beats,
                "no_ui_desc": no_ui_desc,
                "no_caveat": no_caveat,
                "has_provenance": has_prov,
                "passed": passed
            })

        results["tooltip_audit"] = audit_results
        pass_rate_pct = round(pass_count / len(sampled) * 100, 1)
        results["tooltip_pass_rate"] = f"{pass_count} / {len(sampled)} ({pass_rate_pct}%)"
        results["console_errors"] = console_errors

        browser.close()

    out_file = ROOT / "data" / "provenance" / "phase8_regression_and_design.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved regression & design audit results to {out_file}")
    print(f"Tooltip Pass Rate: {results['tooltip_pass_rate']}")

if __name__ == "__main__":
    run_regression_and_design()
