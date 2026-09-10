
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width":1720,"height":1000})
        errs = []
        pg.on("console", lambda m: errs.append((m.type, m.text[:150])) if m.type in ("error","warning") else None)
        pg.on("pageerror", lambda e: errs.append(("pageerror", str(e)[:200])))
        await pg.goto("http://127.0.0.1:4173/index.html", wait_until="load")
        await pg.wait_for_timeout(5000)
        res = await pg.evaluate("""() => {
          const out = {errs: []};
          const tb = document.getElementById('tab-bunkers');
          out.tbExists = !!tb;
          if (tb) {
            out.tbChildren = tb.children.length;
            out.hasDrawer = !!tb.querySelector('.bunkers-chart-drawer');
            out.hasCanvas = !!tb.querySelector('#bunkerMainChart');
            const c = tb.querySelector('#bunkerMainChart');
            out.canvas = c ? c.getBoundingClientRect().width : null;
            out.title = (tb.querySelector('#bunkerChartPortTitle')||{}).textContent || null;
            let anc = [], el = tb.parentElement;
            while (el && el !== document.body) { anc.push(el.id || el.className || el.tagName); el = el.parentElement; }
            out.ancestors = anc.slice(0, 5);
          }
          const panels = Array.from(document.querySelectorAll('.tab-panel'));
          out.panelIds = panels.map(p => p.id);
          return out;
        }""")
        print(json.dumps(res, indent=1))
        print("console:", errs[:8])
        await b.close()

asyncio.run(main())
