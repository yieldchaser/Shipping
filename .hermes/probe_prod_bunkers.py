
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width":1720,"height":1000})
        errs = []
        pg.on("console", lambda m: errs.append((m.type, m.text[:150])) if m.type in ("error",) else None)
        pg.on("pageerror", lambda e: errs.append(("pageerror", str(e)[:200])))
        await pg.goto("https://yieldchaser.github.io/Shipping/", wait_until="load")
        await pg.wait_for_timeout(6000)
        # click Bunkers tab
        clicked = await pg.evaluate("""() => {
          const btns = Array.from(document.querySelectorAll('.nav-item, .tab-btn, [data-tab], button, a'));
          const b = btns.find(x => (x.textContent||'').trim().toLowerCase().includes('bunker'));
          if (b) { b.click(); return b.textContent.trim(); }
          return null;
        }""")
        await pg.wait_for_timeout(3500)
        res = await pg.evaluate("""() => {
          const out = {};
          const tb = document.getElementById('tab-bunkers');
          out.tbExists = !!tb;
          if (tb) {
            out.tbChildren = tb.children.length;
            out.hasCanvas = !!tb.querySelector('#bunkerMainChart');
            out.hasDrawer = !!tb.querySelector('.bunkers-chart-drawer');
            out.title = (tb.querySelector('#bunkerChartPortTitle')||{}).textContent || null;
            out.titleNode = null;
            const t = tb.querySelector('#bunkerChartPortTitle');
            if (t) { const r = t.getBoundingClientRect(); out.titleRect = [Math.round(r.width), Math.round(r.height)]; }
            let anc = [], el = tb.parentElement;
            while (el && el !== document.body) { anc.push(el.id || el.className || el.tagName); el = el.parentElement; }
            out.ancestors = anc.slice(0, 4);
          }
          return out;
        }""")
        print("clicked:", clicked)
        print(json.dumps(res, indent=1))
        print("console errors:", errs[:8])
        await b.close()

asyncio.run(main())
