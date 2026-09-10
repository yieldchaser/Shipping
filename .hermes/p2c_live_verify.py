import asyncio, json, os
from playwright.async_api import async_playwright

OUT = r"C:\Users\Dell\Github\Shipping\scratch\audit"
os.makedirs(OUT, exist_ok=True)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1720, "height": 1100})
        console = []
        pg.on("console", lambda m: console.append(m.text[:200]) if m.type == "error" else None)
        pg.on("pageerror", lambda e: console.append("PAGEERROR: " + str(e)[:200]))
        await pg.goto("https://yieldchaser.github.io/Shipping/", wait_until="load")
        await pg.wait_for_timeout(7000)
        await pg.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('.nav-item, .tab-btn, [data-tab], button, a'))
            .find(x => (x.textContent || '').trim().toLowerCase().includes('broker'));
          if (b) b.click();
        }""")
        await pg.wait_for_timeout(2000)
        await pg.evaluate("() => switchFearnSection(3)")
        await pg.wait_for_timeout(6000)
        tt = await pg.evaluate("""() => new Promise((resolve) => {
          const tile = Array.from(document.querySelectorAll('#fearnTankGrid .tracking-kpi-card'))
            .find(el => (el.getAttribute('data-tt-code') || '').includes('MEG_FEAST') && !(el.getAttribute('data-tt-code') || '').includes('TCE'));
          if (!tile) { resolve('NO_TILE'); return; }
          tile.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, relatedTarget: document.body}));
          setTimeout(() => resolve(document.getElementById('global-tooltip').innerText), 500);
        })""")
        shot1 = OUT + r"\p2c_live_tanker.png"
        await pg.screenshot(path=shot1)
        ok = ("What it is" in tt and "harvest" not in tt.lower() and "marketapi" not in tt.lower()
              and "cache" not in tt.lower() and chr(0x2014) not in tt)
        await pg.mouse.move(10, 900); await pg.wait_for_timeout(400)
        await pg.evaluate("() => switchFearnSection(4)")
        await pg.wait_for_timeout(3000)
        tt2 = await pg.evaluate("""() => new Promise((resolve) => {
          const tile = document.querySelector('#fearnDryGrid .tracking-kpi-card[data-tt-code="CAPESIZE_PACIFIC_RV"]');
          if (!tile) { resolve('NO_TILE'); return; }
          tile.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, relatedTarget: document.body}));
          setTimeout(() => resolve(document.getElementById('global-tooltip').innerText), 500);
        })""")
        shot2 = OUT + r"\p2c_live_dry.png"
        await pg.screenshot(path=shot2)
        ok2 = ("What it is" in tt2 and "harvest" not in tt2.lower() and "cache" not in tt2.lower()
               and chr(0x2014) not in tt2)
        print(json.dumps({
            "prod_sha_hint": "see curl hash step",
            "live_tanker_ok": ok, "live_dry_ok": ok2,
            "live_tanker_emdash": chr(0x2014) in tt,
            "console_errors": console[:5], "console_count": len(console),
            "tt_first_200": tt[:200], "tt2_first_200": tt2[:200],
            "shots": [shot1, shot2]
        }, indent=1))
        await b.close()

asyncio.run(main())
