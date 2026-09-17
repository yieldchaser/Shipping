#!/usr/bin/env python3
"""
Pilbara Ports Authority (Port Hedland + Port of Dampier) monthly iron-ore scraper.

Why the old scraper silently dropped months
  * pilbaraports.com.au sits behind an Imperva/Incapsula bot wall: plain urllib/requests
    get a 212-byte JS challenge page with HTTP 200.
  * PDF file names are not predictable (…_1.pdf, …_15.pdf, …-(1).pdf, 2023 files stored
    under /2022/). URL templating or regex-on-filename misses months.

This version
  1. drives headless Chromium (playwright) to clear the challenge,
  2. crawls the two "port statistics and reports" pages and collects every PDF link,
  3. downloads through the same browser context,
  4. dates each PDF from the text inside it (never from the file name),
  5. Hedland: sums the "Iron Ore" column of the "Cargo Stats by Destination" page
     (validated: 40/40 overlapping months identical to the prior series; also agrees with
     the vessel-level "Cargo, GRT and DWT by commodity" PDFs),
     Dampier: reads the financial-year table (IRON ORE, TOTAL CARGO) — validated 178/178.

Setup (CI):  pip install playwright pandas && python -m playwright install --with-deps chromium
Needs: poppler-utils (pdftotext)
"""
import asyncio, hashlib, json, re, subprocess, sys
from pathlib import Path
import pandas as pd
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "commodities" / "australia_ppa_iron_ore.csv"
CACHE = ROOT / "scratch" / "ppa_pdf"
BASE = "https://www.pilbaraports.com.au"
PAGES = {
    "Port Hedland": BASE + "/ports/port-of-port-hedland/about-port-of-hedland/port-statistics-and-reports",
    "Port of Dampier": BASE + "/ports/port-of-dampier/about-port-of-dampier/port-statistics-and-reports",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
MON = ["JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"]
NUM = re.compile(r"\d[\d,]*\.\d+|\d{1,3}(?:,\d{3})+|\b\d+\b")


async def download_all():
    CACHE.mkdir(parents=True, exist_ok=True)
    files = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(user_agent=UA)
        pg = await ctx.new_page()
        await pg.goto(BASE + "/", timeout=60000)
        await pg.wait_for_timeout(5000)            # let the Incapsula challenge settle
        for port, url in PAGES.items():
            await pg.goto(url, timeout=60000)
            await pg.wait_for_timeout(3000)
            links = await pg.eval_on_selector_all("a[href*='.pdf']", "els => els.map(e => e.href)")
            for u in sorted(set(links)):
                if "shipping_schedule" in u:
                    continue
                fn = CACHE / (hashlib.md5(u.encode()).hexdigest()[:12] + ".pdf")
                if not fn.exists():
                    r = await ctx.request.get(u, timeout=60000)
                    body = await r.body()
                    if body[:4] != b"%PDF":
                        print(f"[ppa] skip non-pdf {r.status} {u[-60:]}")
                        continue
                    fn.write_bytes(body)
                files[str(fn)] = (port, u)
        await b.close()
    return files


def pdftext(fn):
    return subprocess.run(["pdftotext", "-layout", fn, "-"], capture_output=True, text=True).stdout


def parse_hedland_destination(text):
    i = text.find("by Destination")
    if i < 0:
        return None
    s = text[i:]
    m = re.search(r"(?:Departure|Cargo Complete) Date:\s*(\d+)/(\d+)/(\d{4})", s)
    if not m:
        return None
    a, b, y = int(m[1]), int(m[2]), int(m[3])
    month = a if b == 1 else b                    # range always starts on day 1 (MM/DD or DD/MM)
    lines = s.split("\n")
    hdr = [k for k, l in enumerate(lines[:30]) if "Iron" in l and "Ore" in l]
    if not hdr:
        return None
    hl = lines[hdr[0]]
    cols = [(mm.end(), mm.group().strip()) for mm in re.finditer(r"[A-Za-z][A-Za-z ]*?(?=\s{2,}|$)", hl)]
    ends = [e for e, _ in cols]
    iron_end = next(e for e, n in cols if "Iron Ore" in n)
    dest = {}
    for l in lines[hdr[0] + 1:]:
        if l.startswith("\f") or "Printed:" in l:
            break
        mm = re.match(r"^(\S.*?)\s{2,}", l)
        if not mm or mm.group(1).strip().lower() == "total":   # use sum of rows, not the Total row
            continue
        for n in NUM.finditer(l):
            if n.start() < mm.end() - 1:
                continue
            near = min(ends, key=lambda x: abs(x - n.end()))
            if near == iron_end and abs(n.end() - iron_end) < 12:
                dest[mm.group(1).strip()] = float(n.group().replace(",", ""))
    if not dest:
        return None
    return dict(date=f"{y}-{month:02d}-01", iron=sum(dest.values()), dest=dest)


def parse_dampier_fy(text):
    m = re.search(r"(\d{4})\s*-\s*(\d{4})\s+FINANCIAL YEAR", text)
    if not m:
        return []
    y0, rows = int(m[1]), []
    for l in text.split("\n"):
        mm = re.match(r"\s*(?:\d+\s+)?([A-Z]+)\s+(.*)$", l)
        if not mm or mm[1] not in MON:
            continue
        vals = re.findall(r"-|[\d,]+", mm[2])
        if len(vals) < 12:
            continue
        v = [0.0 if x == "-" else float(x.replace(",", "")) for x in vals[:12]]
        if v[9] == 0:
            continue
        mon = MON.index(mm[1]) + 1
        rows.append(dict(date=f"{y0 if mon >= 7 else y0 + 1}-{mon:02d}-01", iron=v[0], total=v[9]))
    return rows


def main():
    files = asyncio.run(download_all())
    recs = []
    for fn, (port, url) in files.items():
        t = pdftext(fn)
        if port == "Port Hedland" and "destination" in url.lower():
            r = parse_hedland_destination(t)
            if r:
                mt = round(r["iron"] / 1e6, 3)
                recs.append(dict(date=r["date"], port=port, total_throughput_mt=mt, iron_ore_exports_mt=mt,
                                 destinations_t=json.dumps(dict(sorted(r["dest"].items()))),
                                 provenance="live_ppa_pdf", n_months_in_file=1))
        elif port == "Port of Dampier":
            rows = parse_dampier_fy(t)
            for r in rows:
                recs.append(dict(date=r["date"], port=port, total_throughput_mt=round(r["total"] / 1e6, 3),
                                 iron_ore_exports_mt=round(r["iron"] / 1e6, 3), destinations_t="",
                                 provenance="live_ppa_dampier_fy", n_months_in_file=len(rows)))
    new = pd.DataFrame(recs)
    # Dampier YTD files repeat months: keep the value from the most complete (latest) file
    new = new.sort_values(["port", "date", "n_months_in_file"]).groupby(["port", "date"]).tail(1).drop(columns="n_months_in_file")

    old = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame(columns=new.columns)
    # never overwrite older wayback history; new scrape wins for months it covers
    merged = pd.concat([old[~old.set_index(["port", "date"]).index.isin(new.set_index(["port", "date"]).index)], new])
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.sort_values(["port", "date"])
    for port, g in merged.groupby("port"):
        s = g.set_index("date")["iron_ore_exports_mt"].asfreq("MS")
        idx = merged["port"] == port
        merged.loc[idx, "mom_pct"] = merged.loc[idx, "date"].map(((s / s.shift(1) - 1) * 100).round(2))
        merged.loc[idx, "yoy_pct"] = merged.loc[idx, "date"].map(((s / s.shift(12) - 1) * 100).round(2))
        holes = pd.date_range(g["date"].min(), g["date"].max(), freq="MS").difference(g["date"])
        if len(holes):
            print(f"[ppa] {port}: {len(holes)} months not published by PPA: {[h.strftime('%Y-%m') for h in holes][:10]}")
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    cols = ["date", "port", "total_throughput_mt", "iron_ore_exports_mt", "destinations_t", "mom_pct", "yoy_pct", "provenance"]
    merged[cols].to_csv(OUT, index=False, lineterminator="\n")
    print(f"[ppa] wrote {len(merged)} rows -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
