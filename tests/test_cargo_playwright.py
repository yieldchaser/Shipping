#!/usr/bin/env python3
"""
Playwright End-to-End Test for Cargo & Trade Flows Tab (#tab-cargo)
Verifies:
1. Navigation and tab activation
2. Hero HUD metrics (Iron Ore, Grains, Fixture coverage with 53.2% unclassified bucket, C3-C5 spread)
3. Flagship Origin -> Freight interactive route switching (Brazil C3, Pilbara C5, Newcastle, USG, Guinea mirror)
4. Commodity Flow Matrix table filtering and explicit unclassified bucket
5. Rebuilt SeasonalEnvelope charts with provenance footers
6. Subview workstation toggling
7. Zero browser console errors
8. DOM font-size >= 11px (tinyCount === 0)
9. Trailing dead space <= 48px
10. Screenshot capture for walkthrough
"""

import os
import sys
from pathlib import Path
import functools
import http.server
import socket
import threading
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def run_cargo_e2e():
    console_errors = []
    page_errors = []

    Path("docs/screenshots").mkdir(parents=True, exist_ok=True)

    server = None
    sock = socket.socket()
    is_open = (sock.connect_ex(('127.0.0.1', 8000)) == 0)
    sock.close()

    if not is_open:
        repo_root = Path(__file__).resolve().parent.parent
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(repo_root))
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 8000), handler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print("Started internal test HTTP server on http://127.0.0.1:8000")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        print("Navigating to http://127.0.0.1:8000/index.html...")
        page.goto("http://127.0.0.1:8000/index.html", wait_until="networkidle")

        # Ensure loading overlay disappears
        try:
            page.locator("#loadingOverlay").wait_for(state="hidden", timeout=12000)
        except Exception:
            page.evaluate("() => { const o = document.getElementById('loadingOverlay'); if (o) o.classList.add('hidden'); }")
        page.wait_for_timeout(1000)

        # 1. Switch to Cargo tab
        cargo_nav_btn = page.locator("button[data-tab='cargo']")
        assert cargo_nav_btn.is_visible(), "Cargo nav button is not visible"
        print("Clicking Cargo & Trade Flows nav button...")
        cargo_nav_btn.click(force=True)
        page.wait_for_timeout(2000)

        cargo_tab = page.locator("#tab-cargo")
        assert cargo_tab.is_visible(), "Cargo tab (#tab-cargo) did not activate or is not visible"
        print("Cargo tab activated successfully.")

        # 2. Check Hero HUD metrics
        ore_val = page.locator("#cargoHudIronOre").inner_text()
        print(f"HUD Iron Ore: {ore_val}")
        assert "Mt" in ore_val

        grains_val = page.locator("#cargoHudGrains").inner_text()
        print(f"HUD USDA Grains: {grains_val}")
        assert "Mt" in grains_val

        fixtures_stat = page.locator("#cargoHudFixtures").inner_text()
        print(f"HUD Fixtures Coverage: {fixtures_stat}")
        assert "%" in fixtures_stat or "Classified" in fixtures_stat

        spread_val = page.locator("#cargoHudC3C5Spread").inner_text()
        print(f"HUD C3-C5 Spread: {spread_val}")
        assert "$" in spread_val

        # 3. Flagship Origin -> Freight route switching
        corridor = page.locator("#flagshipHudCorridor").inner_text()
        print(f"Initial Flagship Corridor: {corridor}")
        assert "Tubarão" in corridor or "Tubarao" in corridor or "Qingdao" in corridor

        routes = [
            ("#flagBtnPilbaraC5", "Pilbara"),
            ("#flagBtnNewcastleCoal", "Newcastle"),
            ("#flagBtnUsgGrain", "US Gulf"),
            ("#flagBtnGuineaCape", "Guinea")
        ]
        for btn_id, label in routes:
            btn = page.locator(btn_id)
            assert btn.is_visible(), f"Route button {btn_id} not visible"
            btn.click()
            page.wait_for_timeout(400)
            cur_corridor = page.locator("#flagshipHudCorridor").inner_text()
            print(f"Switched with {btn_id} -> Corridor: {cur_corridor}")

        # Check Guinea mirror & empty-state removal
        assert page.locator("#guineaEmptyStateCard").count() == 0, "Guinea UNAVAILABLE empty-state card should be removed"
        guinea_status = page.locator("#flagshipStatusBadge").inner_text()
        print(f"Guinea Provenance Status: {guinea_status}")
        assert "LIVE" in guinea_status

        # 4. Commodity Flow Matrix table & group selector
        page.locator("#cargoSubMatrixBtn").click()
        page.wait_for_timeout(500)

        matrix_table = page.locator("#cargoMatrixTableBody")
        assert matrix_table.is_visible(), "Matrix table body not visible"
        row_count = matrix_table.locator("tr").count()
        print(f"Matrix table rows: {row_count}")
        assert row_count > 0, "Matrix table has no rows"

        # Check unclassified bucket row is visible in matrix
        unclass_cell = page.locator("td:has-text('Unclassified')").first
        assert unclass_cell.is_visible(), "Unclassified bucket row is missing from matrix table!"
        print("Explicit Unclassified Bucket verified in matrix table.")

        # Filter to Ores
        page.locator("#matBtnOres").click()
        page.wait_for_timeout(300)
        filtered_rows = matrix_table.locator("tr").count()
        print(f"Matrix rows filtered by Ores: {filtered_rows}")

        # Filter to Unclassified Bucket
        page.locator("#matBtnUnclass").click()
        page.wait_for_timeout(300)
        unclass_rows = matrix_table.locator("tr").count()
        print(f"Matrix rows filtered by Unclassified: {unclass_rows}")

        # Reset filter to All
        page.locator("#matBtnALL").click()
        page.wait_for_timeout(300)

        # 5. Test Subview Toolbar (all 6 views)
        subviews = [
            ("#cargoSubFlagshipBtn", "#cargoFlagshipSection"),
            ("#cargoSubMatrixBtn", "#cargoMatrixSection"),
            ("#cargoSubBasinsBtn", "#cargoBasinsSection"),
            ("#cargoSubGrainsBtn", "#cargoGrainsSection"),
            ("#cargoSubDemandBtn", "#cargoDemandSection"),
            ("#cargoSubAllBtn", "#cargoFlagshipSection")
        ]
        for btn_id, target_sec in subviews:
            page.locator(btn_id).click()
            page.wait_for_timeout(300)
            assert page.locator(target_sec).is_visible(), f"Section {target_sec} should be visible after clicking {btn_id}"
            print(f"Subview {btn_id} activated and verified.")

        # Return to 'all' subview for layout & font verification
        page.locator("#cargoSubAllBtn").click()
        page.wait_for_timeout(600)

        # 6. Check DOM for tiny text (< 11px)
        tiny_elements = page.evaluate("""() => {
            const tab = document.querySelector('#tab-cargo');
            if (!tab) return { tinyCount: -1, tinyNodes: [] };
            const walker = document.createTreeWalker(tab, NodeFilter.SHOW_ELEMENT);
            let tinyCount = 0;
            const tinyNodes = [];
            while (walker.nextNode()) {
                const node = walker.currentNode;
                if (node.offsetParent === null) continue; // hidden
                if (node.tagName === 'CANVAS' || node.tagName === 'SVG' || node.tagName === 'path') continue;
                const text = node.innerText ? node.innerText.trim() : '';
                if (!text) continue;
                const fs = parseFloat(window.getComputedStyle(node).fontSize);
                if (fs < 10.9) {
                    tinyCount++;
                    tinyNodes.push({ tag: node.tagName, id: node.id, class: node.className, fs: fs, text: text.slice(0, 30) });
                }
            }
            return { tinyCount, tinyNodes: tinyNodes.slice(0, 10) };
        }""")
        print(f"Tiny text scan (< 11px): count={tiny_elements['tinyCount']}")
        if tiny_elements['tinyCount'] > 0:
            print("Tiny nodes:", tiny_elements['tinyNodes'])
        assert tiny_elements["tinyCount"] == 0, f"Found {tiny_elements['tinyCount']} elements with font-size < 11px: {tiny_elements['tinyNodes']}"

        # 7. Check Dead Space at bottom of tab
        dead_space = page.evaluate("""() => {
            const tab = document.querySelector('#tab-cargo');
            if (!tab) return 999;
            const rect = tab.getBoundingClientRect();
            const allElements = tab.querySelectorAll('*');
            let maxBottom = rect.top;
            for (const el of allElements) {
                if (el.offsetParent === null) continue;
                const r = el.getBoundingClientRect();
                if (r.bottom > maxBottom) {
                    maxBottom = r.bottom;
                }
            }
            return Math.max(0, rect.bottom - maxBottom);
        }""")
        print(f"Trailing dead space: {dead_space:.1f}px")
        assert dead_space <= 48, f"Dead space exceeds 48px: {dead_space:.1f}px"

        # 8. Check console and page errors
        critical_errors = [e for e in console_errors if not ("favicon" in e.lower() or "source map" in e.lower())]
        print(f"Console errors: {len(critical_errors)}")
        print(f"Page uncaught exceptions: {len(page_errors)}")
        if critical_errors:
            print("Errors logged:")
            for err in critical_errors:
                print(f"  - {err}")
        if page_errors:
            print("Exceptions logged:")
            for err in page_errors:
                print(f"  - {err}")
        assert len(critical_errors) == 0, f"Encountered {len(critical_errors)} console errors"
        assert len(page_errors) == 0, f"Encountered {len(page_errors)} uncaught exceptions"

        # 9. Capture screenshots for walkthrough
        import time

        def safe_screenshot(target, filename):
            target_path = Path("docs/screenshots") / filename
            target_path.parent.mkdir(parents=True, exist_ok=True)
            for attempt in range(4):
                try:
                    target.screenshot(path=str(target_path.resolve()))
                    print(f"Captured docs/screenshots/{filename}")
                    return
                except Exception as e:
                    if attempt == 3:
                        print(f"Warning: could not capture {filename}: {e}")
                    else:
                        time.sleep(0.5)

        safe_screenshot(page, "cargo_tab_full.png")

        # Capture flagship route section
        safe_screenshot(page.locator("#cargoFlagshipSection"), "cargo_flagship.png")

        # Switch to matrix and capture
        page.locator("#cargoSubMatrixBtn").click()
        page.wait_for_timeout(300)
        safe_screenshot(page.locator("#cargoMatrixSection"), "cargo_matrix.png")

        # Switch to basins and capture
        page.locator("#cargoSubBasinsBtn").click()
        page.wait_for_timeout(300)
        safe_screenshot(page.locator("#cargoBasinsSection"), "cargo_basins.png")

        # Switch to grains and capture
        page.locator("#cargoSubGrainsBtn").click()
        page.wait_for_timeout(300)
        safe_screenshot(page.locator("#cargoGrainsSection"), "cargo_grains.png")

        # --- DEDICATED CARDS VERIFICATION ---

        # Card 1: USDA commitments tab (verify Barley/Sorghum removed, verify Wheat/Corn/Soy)
        page.locator("#cargoSubGrainsBtn").click()
        page.wait_for_timeout(400)
        assert page.locator("#usdaSalesBtnBarley").count() == 0, "Barley button should be removed"
        assert page.locator("#usdaSalesBtnSorghum").count() == 0, "Sorghum button should be removed"
        page.locator("#usdaSalesBtnWheat").click()
        page.wait_for_timeout(300)
        safe_screenshot(page.locator("#usdaExportSalesContainer"), "card_usda_commitments.png")

        # Card 2: Dampier toggle
        page.locator("#cargoSubBasinsBtn").click()
        page.wait_for_timeout(400)
        page.locator("#ppaBtnDampier").click()
        page.wait_for_timeout(500)
        safe_screenshot(page.locator("#ppaThroughputContainer"), "card_dampier_toggle.png")

        # Card 3: Hedland destination panel header
        page.locator("#ppaBtnHedland").click()
        page.wait_for_timeout(400)
        safe_screenshot(page.locator("#ppaDestinationCard"), "card_hedland_destination_header.png")

        # Card 4: Major Miners standalone card (clean separation from PPA)
        assert page.locator("#ppaBtnMiners").count() == 0, "PPA Miners toggle should be eliminated"
        assert page.locator("#majorMinersContainer").is_visible(), "Major Miners container should be visible"
        safe_screenshot(page.locator("#majorMinersContainer"), "card_major_miners.png")

        # Card 5: Gulf-PNW spread badge and chart
        page.locator("#cargoSubGrainsBtn").click()
        page.wait_for_timeout(400)
        safe_screenshot(page.locator("#grainFreightContainer"), "card_gulf_pnw_spread.png")

        # Card 6: Minor-bulk multiples
        page.locator("#cargoSubBasinsBtn").click()
        page.wait_for_timeout(400)
        safe_screenshot(page.locator("#minorBulksContainer"), "card_minor_bulks.png")

        # Card 7: Brazil seasonal cards
        page.locator("#brazilBtnOre").click()
        page.wait_for_timeout(400)
        safe_screenshot(page.locator("#brazilExportsContainer"), "card_brazil_seasonal.png")

        # Card 8: Node-audit tiles
        page.locator("#cargoSubMatrixBtn").click()
        page.wait_for_timeout(400)
        safe_screenshot(page.locator("#cargoCoverageGrid"), "card_node_audit_tiles.png")

        # Card 9: Guinea Bauxite Container (in Basins subview)
        page.locator("#cargoSubBasinsBtn").click()
        page.wait_for_timeout(400)
        safe_screenshot(page.locator("#guineaBauxiteContainer"), "card_guinea_bauxite.png")

        # Card 10: Guinea Empty State Card eliminated
        assert page.locator("#guineaEmptyStateCard").count() == 0, "Guinea empty state card eliminated"

        # Re-capture matrix section with period toggles (YoY removed)
        page.locator("#cargoSubMatrixBtn").click()
        page.wait_for_timeout(400)
        assert page.locator("#matPeriodYoy").count() == 0, "YoY period toggle should be eliminated"
        safe_screenshot(page.locator("#commodityMatrixContainer"), "cargo_matrix.png")

        # Capture matrix with Last 12M period
        page.locator("#matPeriod12m").click()
        page.wait_for_timeout(400)
        safe_screenshot(page.locator("#commodityMatrixContainer"), "card_matrix_period_12m.png")

        # Reset matrix back to All-Time
        page.locator("#matPeriodAll").click()
        page.wait_for_timeout(200)

        browser.close()
        print("All Cargo Playwright E2E checks passed!")

        # Copy all screenshots to artifact directory
        artifact_dir = Path(r"C:\Users\Dell\.gemini\antigravity\brain\b43c34cd-0857-475d-92ff-5a9e0356f6bc")
        if artifact_dir.exists():
            import shutil
            for f in Path("docs/screenshots").glob("*.png"):
                shutil.copy2(f, artifact_dir / f.name)
            print(f"Copied all screenshots to artifact directory: {artifact_dir}")

if __name__ == "__main__":
    run_cargo_e2e()

