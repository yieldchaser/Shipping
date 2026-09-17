#!/usr/bin/env python3
"""
Pilbara Ports Authority (Port Hedland + Port of Dampier) monthly iron-ore scraper.

Imperva/Incapsula Bot Wall Bypass:
  * pilbaraports.com.au sits behind an Imperva/Incapsula bot wall: plain urllib/requests
    get a 212-byte JS challenge page with HTTP 200.
  * PDF file names are not predictable (…_1.pdf, …_15.pdf, …-(1).pdf, 2023 files stored
    under /2022/). URL templating or regex-on-filename misses months.

Production Pipeline:
  1. Drives headless Chromium (Playwright) to clear the bot-wall challenge.
  2. Dynamically crawls the two "port statistics and reports" pages and collects every PDF link.
  3. Downloads through the authenticated browser context.
  4. Dates each PDF from the text inside it (never from the file name).
  5. Supports pdftotext (poppler-utils) with automatic fallback to pymupdf / pdfplumber.
  6. Hedland: sums the "Iron Ore" column of the "Cargo Stats by Destination" page.
     Dampier: reads the financial-year table (IRON ORE, TOTAL CARGO).
  7. Updates data/commodities/australia_ppa_iron_ore.csv and data/provenance/manifest.json.
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "commodities" / "australia_ppa_iron_ore.csv"
CACHE = ROOT / "scratch" / "ppa_pdf"
MANIFEST_FILE = ROOT / "data" / "provenance" / "manifest.json"

BASE = "https://www.pilbaraports.com.au"
PAGES = {
    "Port Hedland": BASE + "/ports/port-of-port-hedland/about-port-of-hedland/port-statistics-and-reports",
    "Port of Dampier": BASE + "/ports/port-of-dampier/about-port-of-dampier/port-statistics-and-reports",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
MON = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
NUM = re.compile(r"\d[\d,]*\.\d+|\d{1,3}(?:,\d{3})+|\b\d+\b")


async def download_all():
    CACHE.mkdir(parents=True, exist_ok=True)
    files = {}
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(user_agent=UA)
        pg = await ctx.new_page()
        logging.info("Connecting to %s to establish browser session...", BASE)
        try:
            await pg.goto(BASE + "/", timeout=60000)
            await pg.wait_for_timeout(5000)  # let Incapsula challenge settle
        except Exception as exc:
            logging.warning("Initial base navigation notice: %s", exc)

        for port, url in PAGES.items():
            logging.info("Crawling statistics page for %s: %s", port, url)
            try:
                await pg.goto(url, timeout=60000)
                await pg.wait_for_timeout(3000)
                links = await pg.eval_on_selector_all("a[href*='.pdf']", "els => els.map(e => e.href)")
            except Exception as exc:
                logging.error("Failed to load %s page: %s", port, exc)
                continue

            for u in sorted(set(links)):
                if "shipping_schedule" in u:
                    continue
                fn = CACHE / (hashlib.md5(u.encode()).hexdigest()[:12] + ".pdf")
                if not fn.exists():
                    try:
                        r = await ctx.request.get(u, timeout=60000)
                        body = await r.body()
                        if body[:4] != b"%PDF":
                            logging.debug("[ppa] skip non-pdf %d %s", r.status, u[-60:])
                            continue
                        fn.write_bytes(body)
                    except Exception as exc:
                        logging.warning("Failed downloading PDF %s: %s", u, exc)
                        continue
                files[str(fn)] = (port, u)
        await b.close()
    return files


def pdftext(fn):
    """Extract text preserving layout via pdftotext or pymupdf/pdfplumber."""
    if shutil.which("pdftotext"):
        try:
            res = subprocess.run(["pdftotext", "-layout", fn, "-"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass

    try:
        import pymupdf
        doc = pymupdf.open(str(fn))
        t = "\n".join(page.get_text() for page in doc)
        doc.close()
        if t.strip():
            return t
    except Exception:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(str(fn)) as pdf:
            return "\n".join(page.extract_text(layout=True) or "" for page in pdf.pages)
    except Exception:
        pass

    return ""


def parse_hedland_destination(fn, text):
    """Parse Port Hedland Cargo Stats by Destination."""
    # First attempt pymupdf coordinate extraction if available
    try:
        import pymupdf
        doc = pymupdf.open(str(fn))
        month, iron_load, dest_split = None, None, {}
        for page in doc:
            flat = page.get_text().replace("\r\n", " ").replace("\r", "").replace("\n", " ")
            if month is None:
                m = re.search(r"Cargo Complete [Dd]ate:\s*([\d/]+)\s*to\s*([\d/]+)", flat)
                if not m:
                    m = re.search(r"Departure Date:\s*([\d/]+)\s*to\s*([\d/]+)", flat)
                if m:
                    parts = m.group(1).split("/")
                    month = datetime(int(parts[2]), int(parts[1]), 1)
            if "LOAD" not in flat.upper():
                continue
            words = page.get_text("words")
            iron_x = None
            header_y = None
            for w in words:
                if w[4] == "Iron":
                    iron_x = (w[0] + w[2]) / 2
                    header_y = w[1]
                    break
            if iron_x is None or header_y is None:
                continue

            raw_rows = {}
            for w in words:
                if w[1] <= header_y + 2:
                    continue
                raw_rows.setdefault(round(w[1] / 6), []).append(w)
            keys = sorted(raw_rows)
            merged = []
            for k in keys:
                if merged:
                    prev = merged[-1]
                    py = sum(w[1] for w in prev) / len(prev)
                    cy = sum(w[1] for w in raw_rows[k]) / len(raw_rows[k])
                    if abs(cy - py) <= 5.0:
                        prev.extend(raw_rows[k])
                        continue
                merged.append(list(raw_rows[k]))

            for line_w in merged:
                line = sorted(line_w, key=lambda w: w[0])
                label_tokens = [w[4] for w in line if w[0] < 150]
                if not label_tokens:
                    continue
                label = " ".join(label_tokens).strip()
                vals = [float(w[4].replace(",", "")) for w in line
                        if abs((w[0] + w[2]) / 2 - iron_x) <= 55
                        and re.fullmatch(r"[\d,]+(\.\d+)?", w[4])]
                if not vals:
                    continue
                v = max(vals)
                if label.lower().startswith("total"):
                    iron_load = v if iron_load is None else iron_load
                elif label:
                    dest_split[label] = v
        doc.close()
        if month and iron_load:
            return dict(date=month.strftime("%Y-%m-%d"), iron=iron_load, dest=dest_split)
    except Exception:
        pass

    # Fallback to layout regex
    i = text.find("by Destination")
    if i < 0:
        return None
    s = text[i:]
    m = re.search(r"(?:Departure|Cargo Complete) Date:\s*(\d+)/(\d+)/(\d{4})", s)
    if not m:
        return None
    a, b, y = int(m[1]), int(m[2]), int(m[3])
    month = a if b == 1 else b
    lines = s.split("\n")
    hdr = [k for k, l in enumerate(lines[:30]) if "Iron" in l and "Ore" in l]
    if not hdr:
        return None
    hl = lines[hdr[0]]
    cols = [(mm.end(), mm.group().strip()) for mm in re.finditer(r"[A-Za-z][A-Za-z ]*?(?=\s{2,}|$)", hl)]
    ends = [e for e, _ in cols]
    try:
        iron_end = next(e for e, n in cols if "Iron Ore" in n)
    except StopIteration:
        return None
    dest = {}
    for l in lines[hdr[0] + 1:]:
        if l.startswith("\f") or "Printed:" in l:
            break
        mm = re.match(r"^(\S.*?)\s{2,}", l)
        if not mm or mm.group(1).strip().lower() == "total":
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
    m = re.search(r"(\d{4})\s*[-\u2013/]\s*(\d{2,4})\s+FINANCIAL YEAR", text)
    if not m:
        return []
    y0, rows = int(m[1]), []
    for l in text.split("\n"):
        mm = re.match(r"\s*(?:\d+\s+)?([A-Z]+)\s+(.*)$", l)
        if not mm or mm[1] not in MON:
            continue
        vals = re.findall(r"-|[\d,]+", mm[2])
        if len(vals) < 10:
            continue
        v = [0.0 if x == "-" else float(x.replace(",", "")) for x in vals]
        if len(v) > 9 and v[9] == 0:
            continue
        iron = v[0]
        total = max(v) if len(v) > 1 else iron
        if iron < 100_000:
            continue
        mon = MON.index(mm[1]) + 1
        year = y0 if mon >= 7 else y0 + 1
        rows.append(dict(date=f"{year}-{mon:02d}-01", iron=iron, total=total))
    return rows


def update_manifest(df: pd.DataFrame):
    if not MANIFEST_FILE.exists():
        return
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    now_iso = datetime.now(timezone.utc).isoformat()
    for sec in ["series", "datasets"]:
        if sec in manifest:
            for item in manifest[sec]:
                s_id = item.get("series_id")
                if s_id in ("commodities_australia_ppa_iron_ore", "commodities_australia_ppa_dampier_throughput"):
                    item["row_count"] = len(df)
                    item["date_span"] = [df["date"].min(), df["date"].max()]
                    item["last_fetched_utc"] = now_iso

    with open(MANIFEST_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2)
    logging.info("Updated manifest.json (%d rows, %s -> %s)", len(df), df["date"].min(), df["date"].max())


def main():
    files = asyncio.run(download_all())
    recs = []
    for fn, (port, url) in files.items():
        t = pdftext(fn)
        if port == "Port Hedland" and "destination" in url.lower():
            r = parse_hedland_destination(fn, t)
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

    if not recs:
        logging.warning("No new PPA rows discovered from live crawl.")
        return

    new = pd.DataFrame(recs)
    new = new.sort_values(["port", "date", "n_months_in_file"]).groupby(["port", "date"]).tail(1).drop(columns="n_months_in_file")

    old = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame(columns=new.columns)
    # Merging: keep previous clean data, upsert newly scraped rows
    merged = pd.concat([old[~old.set_index(["port", "date"]).index.isin(new.set_index(["port", "date"]).index)], new])
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.sort_values(["port", "date"]).reset_index(drop=True)

    for port, g in merged.groupby("port"):
        s = g.set_index("date")["iron_ore_exports_mt"].asfreq("MS")
        idx = merged["port"] == port
        merged.loc[idx, "mom_pct"] = merged.loc[idx, "date"].map(((s / s.shift(1) - 1) * 100).round(2))
        merged.loc[idx, "yoy_pct"] = merged.loc[idx, "date"].map(((s / s.shift(12) - 1) * 100).round(2))

    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    cols = ["date", "port", "total_throughput_mt", "iron_ore_exports_mt", "destinations_t", "mom_pct", "yoy_pct", "provenance"]
    merged[cols].to_csv(OUT, index=False, lineterminator="\n")
    logging.info("[ppa] wrote %d rows -> %s", len(merged), OUT)
    update_manifest(merged)


if __name__ == "__main__":
    sys.exit(main())
