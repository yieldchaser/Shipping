import asyncio, json, os, re
from playwright.async_api import async_playwright

OUT = r"C:\Users\Dell\Github\Shipping\scratch\audit"
os.makedirs(OUT, exist_ok=True)

TAB_IDS = ["tab-dashboard", "tab-yearly-dash", "tab-seasonality", "tab-indices", "tab-etfs",
           "tab-signals", "tab-fearnleys", "tab-intelligence", "tab-tracking", "tab-bunkers", "tab-offshore"]
NON_FEARN = [t for t in TAB_IDS if t != "tab-fearnleys"]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1720, "height": 1100})
        console = []
        pg.on("console", lambda m: console.append(m.text[:200]) if m.type == "error" else None)
        pg.on("pageerror", lambda e: console.append("PAGEERROR: " + str(e)[:200]))
        await pg.goto("http://127.0.0.1:4173/index.html", wait_until="load")
        await pg.wait_for_timeout(6000)

        # switch to Broker Desk tab
        await pg.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('.nav-item, .tab-btn, [data-tab], button, a'))
            .find(x => (x.textContent || '').trim().toLowerCase().includes('broker'));
          if (b) b.click();
        }""")
        await pg.wait_for_timeout(1500)
        # open the Tanker Routes sub-section (id 3) then Dry Routes (id 4)
        await pg.evaluate("() => switchFearnSection(3)")
        await pg.wait_for_timeout(5000)  # caches fetch
        await pg.evaluate("() => renderFearnTank()")
        await pg.wait_for_timeout(2500)

        report = {"console_errors": console[:6], "console_count": len(console)}

        # ---- hover VLCC MEG/FEAST tile
        n_tiles = await pg.evaluate("() => document.querySelectorAll('#fearnTankGrid .tracking-kpi-card').length")
        report["tank_tiles"] = n_tiles
        tt_text = await pg.evaluate("""() => new Promise((resolve) => {
          const tile = Array.from(document.querySelectorAll('#fearnTankGrid .tracking-kpi-card'))
            .find(el => (el.getAttribute('data-tt-code') || '').includes('MEG_FEAST') && !(el.getAttribute('data-tt-code') || '').includes('TCE'));
          if (!tile) { resolve('NO_TILE'); return; }
          tile.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, relatedTarget: null}));
          setTimeout(() => resolve(document.getElementById('global-tooltip').innerText), 400);
        })""")
        report["tt_tanker"] = tt_text
        shot1 = OUT + r"\p2c_tt_tanker.png"
        await pg.screenshot(path=shot1)
        # move mouse away to clear, then switch to dry section
        await pg.mouse.move(10, 900)
        await pg.wait_for_timeout(400)
        await pg.evaluate("() => switchFearnSection(4)")
        await pg.wait_for_timeout(2500)

        # ---- hover Capesize Pacific RV tile
        tt_text2 = await pg.evaluate("""() => new Promise((resolve) => {
          const tile = document.querySelector('#fearnDryGrid .tracking-kpi-card[data-tt-code="CAPESIZE_PACIFIC_RV"]');
          if (!tile) { resolve('NO_TILE'); return; }
          tile.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, relatedTarget: null}));
          setTimeout(() => resolve(document.getElementById('global-tooltip').innerText), 400);
        })""")
        report["tt_dry"] = tt_text2
        shot2 = OUT + r"\p2c_tt_dry.png"
        await pg.screenshot(path=shot2)
        await pg.mouse.move(10, 900)
        await pg.wait_for_timeout(300)

        # assertions
        report["tt_tanker_ok"] = ("What it is" in tt_text and "harvest" not in tt_text.lower()
                                  and "marketapi" not in tt_text.lower() and "cache" not in tt_text.lower()
                                  and "Fearnleys daily assessments" in tt_text)
        report["tt_dry_ok"] = ("What it is" in tt_text2 and "harvest" not in tt_text2.lower()
                               and "marketapi" not in tt_text2.lower() and "cache" not in tt_text2.lower()
                               and "Fearnleys daily assessments" in tt_text2)
        report["tt_tanker_emdash"] = chr(0x2014) in tt_text
        report["tt_dry_emdash"] = chr(0x2014) in tt_text2

        # ---- 9-tab leak sweep: no element leaks outside its panel
        leaks = await pg.evaluate("""(tabIds) => {
          const out = [];
          const main = document.querySelector('main') || document.body;
          tabIds.forEach((id) => {
            const panel = document.getElementById(id);
            if (!panel) { out.push(id + ':PANEL_MISSING'); return; }
            // any panel whose DOM position is inside a DIFFERENT panel = leak
            tabIds.forEach((other) => {
              if (other === id) return;
              const o = document.getElementById(other);
              if (o && o.contains(panel)) out.push(id + ' inside ' + other);
            });
          });
          return out;
        }""", TAB_IDS)
        report["leaks"] = leaks

        # ---- bunkers SG-history card intact (parent-steer verification)
        await pg.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('.nav-item, .tab-btn, [data-tab], button, a'))
            .find(x => (x.textContent || '').trim().toLowerCase().includes('bunker'));
          if (b) b.click();
        }""")
        await pg.wait_for_timeout(4000)
        bk = await pg.evaluate("""() => {
          const tb = document.getElementById('tab-bunkers');
          const t = tb && tb.querySelector('#bunkerChartPortTitle');
          const c = tb && tb.querySelector('#bunkerMainChart');
          const r = t ? t.getBoundingClientRect() : null;
          return { title: t ? t.textContent : null, titleVisible: !!(r && r.width > 0),
                   canvas: !!c, canvasW: c ? c.getBoundingClientRect().width : null };
        }""")
        report["bunkers_sg_card"] = bk

        print(json.dumps(report, indent=1))
        await b.close()

asyncio.run(main())
