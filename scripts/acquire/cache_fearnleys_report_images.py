#!/usr/bin/env python3
"""
cache_fearnleys_report_images.py
Polite, resumeable caching utility for all embedded charts, diagrams,
and compiled PDFs referenced in Fearnleys bespoke research publications.

Downloads images from Azure Blob Storage:
  https://pbrkapp.blob.core.windows.net/report/{guid}/{quote(filename)}
into:
  corpus/01-brokers/fearnleys-md/images/{guid}/{filename}

Downloads compiled PDFs into:
  corpus/01-brokers/fearnleys-md/pdfs/{year}/{filename}.pdf

Features:
  - 100% Idempotent: Skips files that already exist on disk.
  - Polite Harvesting: Throttles requests (configurable delay, default 0.08s).
  - Resilient: URL-encodes filenames with spaces, recovers from 404s/transient errors.
  - Auto-normalizing: When downloads complete, runs run_fearnleys_md_normalized.py
    to update the Markdown files in corpus/01-brokers/fearnleys-md/ to link to local images.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from urllib.parse import quote, unquote

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_PATH = ROOT / "data" / "reports" / "fearnleys_reports_catalog.json"
FMD_DIR = ROOT / "corpus" / "01-brokers" / "fearnleys-md"
IMG_BASE_DIR = FMD_DIR / "images"
PDF_BASE_DIR = FMD_DIR / "pdfs"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
}


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text or "").strip("_")
    return s.lower() or "report"


def gather_image_targets(catalog_path: Path) -> list[dict]:
    targets = []
    seen = set()

    if not catalog_path.exists():
        print(f"[ERROR] Catalog file not found: {catalog_path}")
        return []

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    for rep in catalog:
        rep_id = rep.get("id") or ""
        rep_date = rep.get("date") or "undated"
        rep_title = rep.get("title") or "Untitled"

        cb = rep.get("content") or []
        if isinstance(cb, str):
            try:
                cb = json.loads(cb)
            except Exception:
                cb = []

        for block in cb:
            if not isinstance(block, dict):
                continue
            c = str(block.get("content") or "").strip()
            btitle = str(block.get("title") or "")
            m = re.search(r"https?://pbrkapp\.blob\.core\.windows\.net/report/([0-9a-fA-F-]+)/(.+)", c)
            if m:
                guid, raw_fn = m.groups()
                raw_fn = raw_fn.rstrip(')"\'> \r\n\t')
                filename = unquote(raw_fn)
                if not filename:
                    continue
                encoded_url = f"https://pbrkapp.blob.core.windows.net/report/{guid}/{quote(filename)}"
                key = (guid, filename)
                if key not in seen:
                    seen.add(key)
                    targets.append({
                        "url": encoded_url,
                        "guid": guid,
                        "filename": filename,
                        "local_path": IMG_BASE_DIR / guid / filename,
                        "report_id": rep_id,
                        "report_date": rep_date,
                        "report_title": rep_title,
                        "chart_title": btitle or filename,
                    })

    return targets


def gather_pdf_targets(catalog_path: Path) -> list[dict]:
    targets = []
    if not catalog_path.exists():
        return []
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    for rep in catalog:
        pdf_url = rep.get("pdf_url")
        if not pdf_url:
            continue
        rep_date = rep.get("date") or "undated"
        rep_slug = rep.get("slug") or slugify(rep.get("title") or rep.get("id"))
        year = str(rep_date[:4]) if len(rep_date) >= 4 and rep_date[:4].isdigit() else "other"
        filename = f"{rep_date}_{rep_slug}.pdf"
        local_path = PDF_BASE_DIR / year / filename
        targets.append({
            "url": pdf_url,
            "filename": filename,
            "local_path": local_path,
            "report_date": rep_date,
            "year": year,
            "report_title": rep.get("title") or filename,
        })
    return targets


def download_images(
    targets: list[dict],
    delay: float = 0.08,
    limit: int | None = None,
) -> tuple[int, int, int]:
    IMG_BASE_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    lock = Lock()
    downloaded = 0
    skipped = 0
    failed = 0

    to_process = targets[:limit] if limit else targets
    pending = []
    for item in to_process:
        target_path: Path = item["local_path"]
        if target_path.exists() and target_path.stat().st_size > 0:
            skipped += 1
        else:
            pending.append(item)

    print(f"Total images: {len(targets)} | Already cached: {skipped} | To fetch: {len(pending)}")

    def fetch_one(item: dict) -> bool:
        nonlocal downloaded, failed
        target_path: Path = item["local_path"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        url = item["url"]

        for attempt in range(2):
            try:
                resp = session.get(url, timeout=15)
                if resp.status_code == 200:
                    with open(target_path, "wb") as f:
                        f.write(resp.content)
                    with lock:
                        downloaded += 1
                        if downloaded % 50 == 0 or downloaded == 1:
                            print(f"  [{downloaded}/{len(pending)}] Downloaded '{item['filename']}' ({len(resp.content):,} bytes)", flush=True)
                    time.sleep(delay)
                    return True
                elif resp.status_code == 404:
                    with lock:
                        failed += 1
                    return False
                else:
                    time.sleep(1.0)
            except Exception:
                if attempt == 1:
                    with lock:
                        failed += 1
                time.sleep(1.0)
        return False

    if pending:
        max_workers = 4
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_one, item) for item in pending]
            for f in as_completed(futures):
                pass

    return downloaded, skipped, failed


def download_pdfs(
    targets: list[dict],
    delay: float = 0.15,
    limit: int | None = None,
) -> tuple[int, int, int]:
    PDF_BASE_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    lock = Lock()
    downloaded = 0
    skipped = 0
    failed = 0

    to_process = targets[:limit] if limit else targets
    pending = []
    for item in to_process:
        target_path: Path = item["local_path"]
        if target_path.exists() and target_path.stat().st_size > 0:
            skipped += 1
        else:
            pending.append(item)

    print(f"Total PDFs: {len(targets)} | Already cached: {skipped} | To fetch: {len(pending)}")

    def fetch_pdf(item: dict) -> bool:
        nonlocal downloaded, failed
        target_path: Path = item["local_path"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        url = item["url"]

        for attempt in range(2):
            try:
                resp = session.get(url, timeout=30)
                if resp.status_code == 200:
                    with open(target_path, "wb") as f:
                        f.write(resp.content)
                    with lock:
                        downloaded += 1
                        if downloaded % 10 == 0 or downloaded == 1:
                            print(f"  [{downloaded}/{len(pending)}] Saved PDF '{item['filename']}' ({len(resp.content):,} bytes)", flush=True)
                    time.sleep(delay)
                    return True
                elif resp.status_code == 404:
                    with lock:
                        failed += 1
                    return False
                else:
                    time.sleep(1.0)
            except Exception:
                if attempt == 1:
                    with lock:
                        failed += 1
                time.sleep(1.0)
        return False

    if pending:
        max_workers = 4
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_pdf, item) for item in pending]
            for f in as_completed(futures):
                pass

    return downloaded, skipped, failed


def main():
    parser = argparse.ArgumentParser(description="Cache Fearnleys report chart images and PDFs locally.")
    parser.add_argument("--delay", type=float, default=0.08, help="Polite delay between requests in seconds")
    parser.add_argument("--limit", type=int, default=None, help="Max items to attempt in this run")
    parser.add_argument("--dry-run", action="store_true", help="Print targets without downloading")
    parser.add_argument("--download-pdfs", action="store_true", help="Also download and cache compiled PDF reports")
    args = parser.parse_args()

    print("=================================================================")
    print("  FEARNLEYS REPORT ASSETS LOCAL CACHING PIPELINE                 ")
    print("=================================================================")

    # 1. Images
    targets = gather_image_targets(CATALOG_PATH)
    if not targets:
        print("No image targets found.")
        return

    already_cached = sum(1 for t in targets if t["local_path"].exists() and t["local_path"].stat().st_size > 0)
    print(f"Discovered {len(targets)} total unique chart images across reports.")
    print(f"Already cached locally: {already_cached}")
    print(f"Pending download: {len(targets) - already_cached}")

    if args.dry_run:
        print("\n[DRY RUN] First 3 sample image targets:")
        for t in targets[:3]:
            print(f"  - {t['report_date']} | {t['filename']} -> {t['local_path']}")
        pdf_targets = gather_pdf_targets(CATALOG_PATH)
        print(f"\n[DRY RUN] Discovered {len(pdf_targets)} compiled report PDFs:")
        for pt in pdf_targets[:3]:
            print(f"  - {pt['report_date']} | {pt['filename']} -> {pt['local_path']}")
        return

    downloaded, skipped, failed = download_images(
        targets,
        delay=args.delay,
        limit=args.limit,
    )
    print(f"\nImages session: {downloaded} downloaded, {skipped} skipped, {failed} failed.")

    # 2. PDFs (if requested)
    if args.download_pdfs:
        print("\n-----------------------------------------------------------------")
        print("  DOWNLOADING COMPILED PDF REPORTS                               ")
        print("-----------------------------------------------------------------")
        pdf_targets = gather_pdf_targets(CATALOG_PATH)
        pdf_dl, pdf_skip, pdf_fail = download_pdfs(pdf_targets, delay=args.delay, limit=args.limit)
        print(f"PDF session: {pdf_dl} downloaded, {pdf_skip} skipped, {pdf_fail} failed.")

    if downloaded > 0:
        print("\nRe-running Markdown normalizer to link newly cached local images...")
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            from extract.publishers.run_fearnleys_md_normalized import normalize_all
            normalize_all()
        except Exception as e:
            print(f"Note: re-normalizer run encountered: {e}")

    print("=================================================================\n")


if __name__ == "__main__":
    main()
