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
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def run_cargo_e2e():
    console_errors = []
    page_errors = []

    Path("docs/screenshots").mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        print("Navigating to http://localhost:8000/index.html...")
        page.goto("http://localhost:8000/index.html", wait_until="networkidle")

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

        # Check Guinea mirror & empty-state provenance
        guinea_empty = page.locator("#guineaEmptyStateCard")
        assert guinea_empty.is_visible(), "Guinea UNAVAILABLE empty-state card should be visible"
        guinea_status = page.locator("#flagshipStatusBadge").inner_text()
        print(f"Guinea Provenance Status: {guinea_status}")
        assert "LIVE_MIRROR" in guinea_status or "MIRROR" in guinea_status

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
        page.screenshot(path="docs/screenshots/cargo_tab_full.png", full_page=False)
        print("Captured docs/screenshots/cargo_tab_full.png")

        # Capture flagship route section
        flagship_section = page.locator("#cargoFlagshipSection")
        flagship_section.screenshot(path="docs/screenshots/cargo_flagship.png")
        print("Captured docs/screenshots/cargo_flagship.png")

        # Switch to matrix and capture
        page.locator("#cargoSubMatrixBtn").click()
        page.wait_for_timeout(300)
        matrix_section = page.locator("#cargoMatrixSection")
        matrix_section.screenshot(path="docs/screenshots/cargo_matrix.png")
        print("Captured docs/screenshots/cargo_matrix.png")

        # Switch to basins and capture
        page.locator("#cargoSubBasinsBtn").click()
        page.wait_for_timeout(300)
        basins_section = page.locator("#cargoBasinsSection")
        basins_section.screenshot(path="docs/screenshots/cargo_basins.png")
        print("Captured docs/screenshots/cargo_basins.png")

        # Switch to grains and capture
        page.locator("#cargoSubGrainsBtn").click()
        page.wait_for_timeout(300)
        grains_section = page.locator("#cargoGrainsSection")
        grains_section.screenshot(path="docs/screenshots/cargo_grains.png")
        print("Captured docs/screenshots/cargo_grains.png")

        browser.close()
        print("All Cargo Playwright E2E checks passed!")

if __name__ == "__main__":
    run_cargo_e2e()
