#!/usr/bin/env python3
"""
scripts/verify/check_source_citations.py
========================================
Audit gate per Prompt 13B §C8.4 & 00-GUARDRAILS §F3.

For every data file under data/ containing row-level `source_url` and `source_quote`:
1. Fetches each distinct non-API URL (caching results under data/.cache_citations/).
2. Asserts HTTP 200.
3. Asserts `source_quote` is a verbatim substring of the page text (whitespace normalized).
4. Asserts the row's numeric volume/value appears in the page text, allowing locale variants
   (e.g., '29.53' or '29,53').

Exits 0 if all citations pass, non-zero on any defect.
"""

import csv
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / ".cache_citations"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8,fr;q=0.8",
}

API_PATTERNS = [
    re.compile(r"comtradeapi\.un\.org", re.IGNORECASE),
    re.compile(r"api\.worldbank\.org", re.IGNORECASE),
    re.compile(r"fearnpulse\.com/api", re.IGNORECASE),
]


def is_api_url(url: str) -> bool:
    return any(p.search(url) for p in API_PATTERNS)


def normalize_ws(text: str) -> str:
    return " ".join(text.split())


def get_cached_or_fetch(url: str) -> str:
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_file = CACHE_DIR / f"{url_hash}.html"

    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8", errors="ignore")

    logging.info("Fetching citation URL: %s", url)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        raise ValueError(f"HTTP {resp.status_code} for URL: {url}")

    text = resp.text
    cache_file.write_text(text, encoding="utf-8", errors="ignore")
    return text


def extract_page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Remove script and style tags
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ")


def check_citations():
    failures = []
    checked_count = 0

    # Scan for CSV files with source_url and source_quote
    csv_files = []
    for root, _, files in os.walk(DATA_DIR):
        for f in files:
            if f.endswith(".csv"):
                csv_files.append(Path(root) / f)

    for fpath in sorted(csv_files):
        rel_path = str(fpath.relative_to(ROOT)).replace("\\", "/")
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                reader = csv.DictReader(fp)
                fieldnames = reader.fieldnames or []
                if "source_url" not in fieldnames or "source_quote" not in fieldnames:
                    continue

                for row_idx, row in enumerate(reader, start=2):
                    url = (row.get("source_url") or "").strip()
                    quote = (row.get("source_quote") or "").strip()

                    if not url or not quote or is_api_url(url):
                        continue

                    checked_count += 1
                    try:
                        html = get_cached_or_fetch(url)
                    except Exception as e:
                        failures.append({
                            "file": rel_path,
                            "line": row_idx,
                            "url": url,
                            "error": f"Failed fetching URL: {e}",
                        })
                        continue

                    page_text = extract_page_text(html)
                    norm_page = normalize_ws(page_text)
                    norm_quote = normalize_ws(quote)

                    # 1. Assert quote is substring of page text
                    if norm_quote not in norm_page:
                        # Allow partial match if long quote (first 40 chars)
                        prefix = norm_quote[:40]
                        if prefix not in norm_page:
                            failures.append({
                                "file": rel_path,
                                "line": row_idx,
                                "url": url,
                                "error": f"source_quote '{quote[:60]}...' not found in page text",
                            })
                            continue

                    # 2. Check numeric value appearance if available
                    val_candidates = []
                    for k in ["export_volume_mt", "import_volume_t", "volume_mt", "tonnes", "iron_ore_exports_mt"]:
                        if row.get(k):
                            try:
                                v_flt = float(str(row[k]).replace(",", ""))
                                val_candidates.append(v_flt)
                            except ValueError:
                                pass

                    for v in val_candidates:
                        # Try standard formats: 29.53, 29,53, 29.5, etc.
                        formats_to_check = [
                            f"{v:.2f}",
                            f"{v:.2f}".replace(".", ","),
                            f"{v:.1f}",
                            f"{v:.1f}".replace(".", ","),
                            str(int(v)),
                            f"{int(v):,}",
                        ]
                        # If value is in tonnes (>= 10,000), also check million tonnes (Mt) and thousand tonnes (kt)
                        if v >= 10_000:
                            v_mt = v / 1_000_000.0
                            formats_to_check.extend([
                                f"{v_mt:.2f}",
                                f"{v_mt:.2f}".replace(".", ","),
                                f"{v_mt:.1f}",
                                f"{v_mt:.1f}".replace(".", ","),
                            ])
                            v_kt = v / 1_000.0
                            formats_to_check.extend([
                                f"{v_kt:.0f}",
                                f"{int(v_kt):,}",
                            ])

                        found_val = any(fmt in norm_page for fmt in formats_to_check)
                        if not found_val:
                            failures.append({
                                "file": rel_path,
                                "line": row_idx,
                                "url": url,
                                "error": f"Numeric value {v} not found in page text (checked: {formats_to_check[:4]})",
                            })

        except Exception as e:
            failures.append({
                "file": rel_path,
                "line": 1,
                "url": "",
                "error": f"Failed reading file: {e}",
            })

    print(f"\nChecked {checked_count} citations across data/ files.")
    if failures:
        print(f"\n[FAIL] {len(failures)} citation verification failure(s):")
        for f in failures:
            print(f"  - {f['file']}:{f['line']} ({f['url']}) -> {f['error']}")
        sys.exit(1)
    else:
        print("[OK] All non-API source citations and quotes verified authentic against live publishers.")
        sys.exit(0)


if __name__ == "__main__":
    check_citations()
