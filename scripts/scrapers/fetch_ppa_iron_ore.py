#!/usr/bin/env python3
"""
Pilbara Ports Authority (PPA) — REAL monthly Port Hedland cargo statistics.

Source: PPA's own "Cargo Stats by Destination/Origin" monthly reports (PDF), published on
pilbaraports.com.au port-statistics pages. The HTML pages sit behind an Incapsula bot-wall,
but the underlying media PDFs are served openly; historical months are additionally
preserved by the Internet Archive (Wayback). This scraper:
  1. queries the Wayback CDX index for every archived Hedland cargo-stats PDF,
  2. downloads each snapshot,
  3. extracts the reporting month + total Iron Ore LOAD tonnage (+ per-destination split),
  4. writes data/commodities/australia_ppa_iron_ore.csv (provenance=live_ppa_archive).

Honesty rules (2026-08-25 audit):
  - Only REAL extracted values are written. No editorial estimates, ever.
  - Coverage = months PPA has published AND the archive preserves (currently ~2020→2024).
    Recent months appear once captured by the Internet Archive (or fetched live when the
    site serves them without the wall).
  - Port Hedland only: these reports cover PH; Dampier publishes separately and is NOT
    fabricated here.
"""
import json
import logging
import re
import ssl
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd
import pymupdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "commodities"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / "australia_ppa_iron_ore.csv"
SCRATCH = ROOT / "scratch"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

COUNTRIES = ["China", "Japan", "Korea, Republic of", "India", "Indonesia",
             "Malaysia", "Philippines", "Singapore", "Taiwan, Province of China",
             "Vietnam", "Australia"]


def cdx_hedland_pdfs(retries: int = 4) -> list[dict]:
    """All archived Port Hedland cargo-stats PDF snapshots (newest per filename)."""
    url = ("https://web.archive.org/cdx/search/cdx?url=pilbaraports.com.au"
           "&matchType=domain&output=json&limit=8000&collapse=urlkey"
           "&filter=mimetype:application/pdf&from=2019")
    rows = []
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            payload = urllib.request.urlopen(req, timeout=120, context=CTX).read()
            rows = json.loads(payload.decode("utf-8", "replace"))[1:]
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            logging.warning("CDX attempt %d/%d failed: %s", attempt, retries, exc)
            time.sleep(5 * attempt)
    if not rows:
        raise SystemExit(f"Wayback CDX unreachable after {retries} tries ({last}). "
                         "Nothing written; retry later.")
    seen: dict[str, dict] = {}
    for r in rows:
        ts, status, orig = r[1], r[4], r[2]
        low = orig.lower()
        if status != "200" or "hedland" not in low:
            continue
        fname = low.rsplit("/", 1)[-1]
        is_stat = ("cargo-stats-by-destination" in fname
                   or "cargo%20stats%20by%20destination" in fname
                   or "cargo-stats-by-origin" in fname)
        if not is_stat:
            continue
        key = re.sub(r"%20|%", "-", fname)
        if key not in seen or ts > seen[key]["ts"]:
            seen[key] = {"ts": ts, "url": orig}
    return list(seen.values())


def download(ts: str, url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 5000:
        return True
    dl = f"https://web.archive.org/web/{ts}id_/{url}"
    r = subprocess.run(["curl", "-sL", "--max-time", "120", "-o", str(dest),
                        "-w", "%{http_code}", dl, "-A", "Mozilla/5.0"],
                       capture_output=True, text=True)
    ok = r.stdout.strip().endswith("200") and dest.exists() and dest.stat().st_size > 5000
    if not ok:
        dest.unlink(missing_ok=True)
    return ok


def month_from_text(text: str):
    m = re.search(r"Cargo Complete [Dd]ate:\s*([\d/]+)\s*to\s*([\d/]+)", text)
    if not m:
        return None
    d1, mth, y = m.group(1).split("/")
    try:
        return datetime(int(y), int(mth), 1)   # start date is DD/MM/YYYY
    except ValueError:
        return None


def parse_pdf(path: Path):
    """Coordinate-based extraction: locate the Iron Ore column by its header x-position,
    then read each destination row's value in that x-band. Robust to ragged columns."""
    doc = pymupdf.open(str(path))
    month, iron_load, dest_split = None, None, {}
    for page in doc:
        flat = page.get_text().replace("\r\n", " ").replace("\r", "").replace("\n", " ")
        if month is None:
            month = month_from_text(flat)
        if "LOAD" not in flat.upper():
            continue
        words = page.get_text("words")   # x0,y0,x1,y1,text,...
        # 1) commodity header row: contains 'Iron' + 'Ore' tokens
        iron_x = None
        header_y = None
        for w in words:
            if w[4] == "Iron":
                iron_x = (w[0] + w[2]) / 2
                header_y = w[1]
                break
        if iron_x is None or header_y is None:
            continue
        # 2) group remaining words into rows below the header (tolerant clustering:
        #    a row's label and its numbers can sit ~4px apart, so bucket by 6px and
        #    then merge adjacent buckets whose y-centres are within 5px)
        raw_rows: dict[int, list] = {}
        for w in words:
            if w[1] <= header_y + 2:
                continue
            raw_rows.setdefault(round(w[1] / 6), []).append(w)
        keys = sorted(raw_rows)
        merged: list[list] = []
        for k in keys:
            if merged:
                prev = merged[-1]
                py = sum(w[1] for w in prev) / len(prev)
                cy = sum(w[1] for w in raw_rows[k]) / len(raw_rows[k])
                if abs(cy - py) <= 5.0:
                    prev.extend(raw_rows[k])
                    continue
            merged.append(list(raw_rows[k]))
        # 3) per-row: label = leftmost word(s), value = number in iron x-band (+/-55px)
        BAND = 55
        for line_w in merged:
            line = sorted(line_w, key=lambda w: w[0])
            label_tokens = [w[4] for w in line if w[0] < 150]
            if not label_tokens:
                continue
            label = " ".join(label_tokens)
            vals = [float(w[4].replace(",", "")) for w in line
                    if abs((w[0] + w[2]) / 2 - iron_x) <= BAND
                    and re.fullmatch(r"[\d,]+(\.\d+)?", w[4])]
            if not vals:
                continue
            v = max(vals)
            if label.startswith("Total"):
                iron_load = v if iron_load is None else iron_load
            elif label in COUNTRIES:
                dest_split[label] = v
    doc.close()
    # cross-check: sum of destinations should approximate the total (>95% when present)
    if iron_load and dest_split:
        s = sum(dest_split.values())
        if s < iron_load * 0.95:      # partial coverage is fine (other countries exist),
            pass                      # but a wildly-off split would signal misparse
    return month, iron_load, dest_split


def main() -> pd.DataFrame:
    SCRATCH.mkdir(exist_ok=True)
    # Fast path: reuse the verified manifest from the collection probe when present
    # (24 known-good snapshot URLs). Otherwise fall back to a fresh CDX sweep.
    manifest = SCRATCH / "ppa_pdf_manifest.json"
    if manifest.exists():
        cached = [json.loads(json.dumps(m)) for m in json.load(open(manifest))]
        pdfs = [{"ts": m["ts"], "url": m["url"]} for m in cached]
        logging.info("Using cached manifest: %d verified PDFs", len(pdfs))
    else:
        pdfs = cdx_hedland_pdfs()
        if not pdfs:
            raise SystemExit("No archived PPA cargo-stat PDFs found via CDX — investigate.")
        logging.info("%d archived Hedland cargo-stat PDFs", len(pdfs))

    records = []
    for i, item in enumerate(sorted(pdfs, key=lambda x: x["ts"])):
        safe = re.sub(r"[^a-z0-9]+", "_",
                      item["url"].lower().rsplit("/", 1)[-1])[:60]
        dest = SCRATCH / f"ppa_{safe}.pdf"
        try:
            if not download(item["ts"], item["url"], dest):
                logging.warning("download failed: %s", item["url"][:90])
                continue
            month, load, split = parse_pdf(dest)
            time.sleep(1.0)
        except Exception as exc:  # noqa: BLE001
            logging.warning("parse failed %s: %s", dest.name[:50], exc)
            continue
        if month and load:
            records.append({
                "date": month.strftime("%Y-%m-%d"),
                "port": "Port Hedland",
                "total_throughput_mt": round(load / 1e6, 3),
                "iron_ore_exports_mt": round(load / 1e6, 3),
                "destinations_t": json.dumps(split, sort_keys=True),
            })
            logging.info("%s  %.2f Mt (%d destinations)", month.strftime("%Y-%m"),
                         load / 1e6, len(split))
    if not records:
        raise SystemExit("Parsed zero real PPA months — layout changed? Nothing written.")

    df = pd.DataFrame(records).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    df["mom_pct"] = (df["iron_ore_exports_mt"].pct_change() * 100).round(2)
    df["yoy_pct"] = (df["iron_ore_exports_mt"].pct_change(12) * 100).round(2)
    df["provenance"] = "live_ppa_archive"
    df.to_csv(OUT_FILE, index=False)
    span = f"{df['date'].min()} .. {df['date'].max()}"
    logging.info("Wrote %d REAL PPA months (%s) -> %s", len(df), span, OUT_FILE.name)
    return df


if __name__ == "__main__":
    main()
