#!/usr/bin/env python3
"""
Extract Fearnpulse Official Series Titles from Next.js Client Chunks
===================================================================
Prompt 13C §D2:
Fetches https://fearnpulse.com/fearnleys-weekly-report, discovers the Next.js
client chunk containing `tsId:`, extracts all defined series configurations,
and emits data/reference/fearnpulse_titles.json = {tsId: {title, section, paired_with}}.
"""

import json
import os
import re
import sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = ROOT / "data" / "reference" / "fearnpulse_titles.json"
CACHE_DIR = ROOT / "data" / "raw" / "fearnleys" / "chunks"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_page_and_chunks():
    url = "https://fearnpulse.com/fearnleys-weekly-report"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    chunk_urls = []
    cached_page = CACHE_DIR / "page.html"
    if cached_page.exists():
        html = cached_page.read_text(encoding="utf-8")
        matches = re.findall(r'src=["\'](/_next/static/chunks/[^"\']+)["\']', html)
        chunk_urls = ["https://fearnpulse.com" + m for m in matches]

    if not chunk_urls:
        print(f"Fetching {url}...")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            html = resp.text
            cached_page.write_text(html, encoding="utf-8")
            matches = re.findall(r'src=["\'](/_next/static/chunks/[^"\']+)["\']', html)
            chunk_urls = ["https://fearnpulse.com" + m for m in matches]
        except Exception as e:
            print(f"Warning: Failed to fetch live page: {e}.")

    cached_files = list(CACHE_DIR.glob("*.js"))
    if not chunk_urls and cached_files:
        print(f"Using {len(cached_files)} cached JS chunks in {CACHE_DIR}")
        return [(f.name, f.read_text(encoding="utf-8")) for f in cached_files]

    results = []
    for cur_url in chunk_urls:
        filename = cur_url.split("/")[-1]
        cache_path = CACHE_DIR / filename
        if cache_path.exists():
            content = cache_path.read_text(encoding="utf-8")
        else:
            print(f"Fetching chunk {filename}...")
            r = requests.get(cur_url, headers=HEADERS, timeout=15)
            content = r.text
            cache_path.write_text(content, encoding="utf-8")
        results.append((filename, content))
    return results


def extract_titles(chunks):
    """
    Search JS content for series definitions with title and tsId / tsId1 / tsId2.
    Associates each series with its section heading from the component tree.
    """
    titles = {}

    SECTIONS = [
        "Capesize", "Panamax", "Supramax", "Dry Bulk",
        "Exchange Rates", "Interest Rates", "Commodity Prices",
        "Singapore", "Rotterdam", "Bunker Prices"
    ]

    for filename, js in chunks:
        if "tsId" not in js:
            continue
        print(f"Analyzing chunk {filename} ({len(js):,} bytes) with tsId definitions...")

        # Match object literals containing tsId: { ... }
        for m in re.finditer(r"\{([^{}]*?tsId[12]?\s*:\s*[0-9e]+[^{}]*?)\}", js):
            obj = m.group(1)
            pos = m.start()

            # Find title
            title_m = re.search(r'title\s*:\s*["\']([^"\']+)["\']', obj)
            if not title_m:
                continue
            title = title_m.group(1).strip()

            # Find section from preceding code context
            pre = js[max(0, pos-1200):pos]
            detected_sec = "Unknown"
            best_pos = -1
            for sec in SECTIONS:
                sec_pos = pre.rfind(f'"{sec}"')
                if sec_pos == -1:
                    sec_pos = pre.rfind(f"'{sec}'")
                if sec_pos > best_pos:
                    best_pos = sec_pos
                    detected_sec = sec

            # Check for paired tsIds (tsId1 and tsId2)
            pair_m = re.search(r"tsId1\s*:\s*([0-9e]+).*?tsId2\s*:\s*([0-9e]+)", obj)
            if pair_m:
                raw1, raw2 = pair_m.group(1), pair_m.group(2)
                id1 = str(int(float(raw1)))
                id2 = str(int(float(raw2)))
                if id1 not in titles:
                    titles[id1] = {
                        "title": title,
                        "section": detected_sec,
                        "paired_with": int(id2),
                        "source_chunk": filename,
                    }
                else:
                    titles[id1]["paired_with"] = int(id2)

                if id2 not in titles:
                    titles[id2] = {
                        "title": title,
                        "section": detected_sec,
                        "paired_with": int(id1),
                        "source_chunk": filename,
                    }
                else:
                    titles[id2]["paired_with"] = int(id1)
                continue

            # Single tsId
            single_m = re.search(r"tsId\s*:\s*([0-9e]+)", obj)
            if single_m:
                raw = single_m.group(1)
                num = int(float(raw))
                if num == 0:
                    continue  # template / dummy
                num_str = str(num)
                existing_pair = titles.get(num_str, {}).get("paired_with")
                titles[num_str] = {
                    "title": title,
                    "section": detected_sec,
                    "paired_with": existing_pair,
                    "source_chunk": filename,
                }
                # Also if raw == '5e3', record under '5' with note
                if raw == "5e3":
                    titles["5"] = {
                        "title": title,
                        "section": detected_sec,
                        "paired_with": existing_pair,
                        "source_chunk": filename,
                        "notes": "Wired as 5e3 (5000) in Fearnpulse Next.js bundle for USD/JPY"
                    }

    return titles


def main():
    chunks = fetch_page_and_chunks()
    titles = extract_titles(chunks)
    print(f"Extracted {len(titles)} official Fearnpulse series titles.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(titles, f, indent=2)
    print(f"Saved to {OUTPUT_FILE}")

    for tsid, d in sorted(titles.items(), key=lambda x: int(x[0])):
        paired = f" (paired with {d['paired_with']})" if d.get("paired_with") else ""
        print(f"  tsId {tsid:>6}: {d['title']:<30} [{d['section']}]{paired}")


if __name__ == "__main__":
    main()
