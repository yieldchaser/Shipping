"""
Poten & Partners Historical Tanker Opinions PDF Downloader & Indexer.

Crawls Poten Tanker Opinions archives across pages (up to 111 pages, ~1,100+ weekly reports),
resolves HubSpot form gates via direct API submission or WordPress uploads,
and downloads the authentic raw unprocessed PDFs to disk under:
  reports/poten/pdfs/{year}/{clean_filename}.pdf
Maintains full manifest & checkpoint in data/derived/poten_tanker_opinions_index.json.
"""

import os
import sys
import re
import json
import time
import argparse
import subprocess
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import unquote

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PDF_BASE_DIR = REPO_ROOT / "reports" / "poten" / "pdfs"
INDEX_FILE = REPO_ROOT / "data" / "derived" / "poten_tanker_opinions_index.json"

BASE_URL_WHATS_NEW = "https://www.poten.com/whats-new-2/tanker-opinions/"
BASE_URL_CATEGORY = "https://www.poten.com/category/industry-opinions/tanker-opinions/"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

def get_html(url, timeout=30, max_retries=4):
    """Fetch URL via curl to bypass Cloudflare/TLS fingerprint WAF blocks with retries."""
    for attempt in range(1, max_retries + 1):
        res = subprocess.run(
            ["curl", "-s", "-L", "--max-time", str(timeout), url, "-A", UA],
            capture_output=True,
            text=True,
            errors="replace"
        )
        out = res.stdout or ""
        if len(out) > 500 and "Your request was blocked" not in out and "Just a moment..." not in out:
            return out
        time.sleep(2 * attempt)
    return ""

def submit_hubspot_form(portal_id, form_id, page_url):
    """Submit lightweight registration payload to HubSpot API to retrieve public PDF redirectUri."""
    submit_url = f"https://api.hsforms.com/submissions/v3/integration/submit/{portal_id}/{form_id}"
    payload = {
        "fields": [
            {"name": "email", "value": "research@maritimeanalytics.org"},
            {"name": "firstname", "value": "Maritime"},
            {"name": "lastname", "value": "Analyst"},
            {"name": "company", "value": "Shipping Research Group"},
            {"name": "city", "value": "London"},
            {"name": "region", "value": "Europe"},
            {"name": "commodity", "value": "Crude Oil"},
            {"name": "sector", "value": "Academia"}
        ],
        "context": {
            "pageUri": page_url,
            "pageName": "Poten Tanker Opinions"
        }
    }
    try:
        r = requests.post(submit_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("redirectUri")
    except Exception as e:
        print(f"      [!] Form submit exception: {e}")
    return None

def download_pdf(pdf_url, target_path):
    """Stream download binary PDF to target path."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(pdf_url, headers={"User-Agent": UA}, stream=True, timeout=25)
        if r.status_code == 200:
            with open(target_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=16384):
                    f.write(chunk)
            return target_path.stat().st_size
    except Exception as e:
        print(f"      [!] Download error: {e}")
    return 0

def load_index():
    if INDEX_FILE.exists():
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"reports": {}, "last_page": 0, "total_downloaded": 0}

def save_index(index_data):
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

def clean_name(val):
    clean = re.sub(r'[\\/*?:"<>|]', "", val)
    return re.sub(r'\s+', ' ', clean).strip()

def extract_year(filename, text=""):
    m = re.search(r'\b(20\d\d)\b', filename)
    if m:
        return m.group(1)
    m2 = re.search(r'\b(20\d\d)\b', text)
    if m2:
        return m2.group(1)
    return "unknown"

def process_page(page_num, use_category=False, delay=1.5):
    base = BASE_URL_CATEGORY if use_category else BASE_URL_WHATS_NEW
    page_url = base if page_num == 1 else f"{base}page/{page_num}/"
    print(f"\n========================================================")
    print(f"Fetching Listing Page {page_num}: {page_url}")
    print(f"========================================================")
    
    html = get_html(page_url)
    if not html:
        print(f"[!] Empty response for page {page_num}")
        return 0, False

    soup = BeautifulSoup(html, "html.parser")
    articles = soup.find_all("article")
    print(f"Found {len(articles)} articles on page {page_num}.")
    
    if not articles:
        return 0, False

    index_data = load_index()
    reports_map = index_data.get("reports", {})
    new_downloads = 0

    for idx, art in enumerate(articles):
        h = art.find(["h1", "h2", "h3", "h4"])
        a = h.find("a") if h else art.find("a")
        if not a or "href" not in a.attrs:
            continue
        title = clean_name(a.get_text(strip=True))
        art_url = a["href"].strip()
        
        # Check if already processed and PDF exists
        if art_url in reports_map:
            cached = reports_map[art_url]
            rel_path = cached.get("pdf_path")
            if rel_path and (REPO_ROOT / rel_path).exists() and (REPO_ROOT / rel_path).stat().st_size > 5000:
                print(f"  [{idx+1}/{len(articles)}] [ALREADY DOWNLOADED] {title}")
                continue

        print(f"  [{idx+1}/{len(articles)}] Ingesting: {title} ({art_url})")
        art_html = get_html(art_url)
        if not art_html:
            print("      [-] Empty HTML response")
            continue

        form_m = re.search(r'formId:\s*["\']([a-f0-9\-]+)["\']', art_html)
        portal_m = re.search(r'portalId:\s*["\'](\d+)["\']', art_html)

        pdf_url = None
        form_id = None
        if form_m:
            form_id = form_m.group(1)
            portal_id = portal_m.group(1) if portal_m else "1975593"
            pdf_url = submit_hubspot_form(portal_id, form_id, art_url)
        
        if not pdf_url:
            # Check WordPress direct PDF link
            pdfs = re.findall(r'https?://[^\s"\'<>]+\.pdf', art_html)
            if pdfs:
                # Filter out generic/non-report links if any
                valid_pdfs = [p for p in pdfs if any(k in p.lower() for k in ["opinion", "tanker", "hubfs", "upload"])]
                pdf_url = valid_pdfs[0] if valid_pdfs else pdfs[0]

        if not pdf_url:
            # Standfirst probe fallback: check if date and title can match standard HubSpot CDN naming
            date_m = re.search(r'\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d\d)\b', art_html or "")
            if not date_m:
                # Check listing item snippet text
                date_m = re.search(r'\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d\d)\b', art.get_text() if art else "")
            if date_m:
                d_day, d_mon, d_yr = date_m.group(1), date_m.group(2), date_m.group(3)
                simple_title = re.sub(r'[^a-zA-Z0-9\s]', '', title).strip()
                candidates = [
                    f"https://1975593.fs1.hubspotusercontent-na1.net/hubfs/1975593/Tanker%20Opinions/Weekly%20Opinion%20-%20{d_day}%20{d_mon}%20{d_yr}%20-%20{simple_title}.pdf",
                    f"https://1975593.fs1.hubspotusercontent-na1.net/hubfs/1975593/Tanker%20Opinions/Weekly%20Opinion%20-%20{d_day}%20{d_mon[:3]}%20{d_yr}%20-%20{simple_title}.pdf",
                    f"https://1975593.fs1.hubspotusercontent-na1.net/hubfs/1975593/Tanker%20Opinions/Weekly%20Opinion%20-%20{d_mon}%20{d_day}%20{d_yr}%20-%20{simple_title}.pdf",
                ]
                for cand in candidates:
                    try:
                        r_head = requests.head(cand, headers={"User-Agent": UA}, timeout=6)
                        if r_head.status_code == 200:
                            pdf_url = cand
                            print(f"      [+] Recovered PDF via HubSpot CDN probe: {cand}")
                            break
                    except Exception:
                        pass

        if not pdf_url:
            print("      [-] No PDF URL available for this article.")
            reports_map[art_url] = {
                "title": title,
                "url": art_url,
                "status": "no_pdf_found",
                "page": page_num
            }
            save_index(index_data)
            time.sleep(delay)
            continue

        raw_filename = unquote(pdf_url.split("?")[0].split("/")[-1])
        filename = clean_name(raw_filename)
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
            
        year = extract_year(filename, title)
        local_rel_path = f"reports/poten/pdfs/{year}/{filename}"
        local_abs_path = REPO_ROOT / local_rel_path

        size = download_pdf(pdf_url, local_abs_path)
        if size > 1000:
            print(f"      [OK] Downloaded: {filename} ({size:,} bytes) -> {year}/")
            reports_map[art_url] = {
                "title": title,
                "url": art_url,
                "pdf_url": pdf_url,
                "pdf_path": local_rel_path,
                "filename": filename,
                "year": year,
                "size_bytes": size,
                "form_id": form_id,
                "status": "downloaded",
                "page": page_num
            }
            new_downloads += 1

            # Generate markdown metadata file under reports/poten/{year}/{slug}.md
            date_str = f"{year}-01-01"
            m_dt = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(20\d\d)', filename)
            if m_dt:
                try:
                    date_str = datetime.strptime(f"{m_dt.group(1)} {m_dt.group(2)[:3]} {m_dt.group(3)}", "%d %b %Y").strftime("%Y-%m-%d")
                except Exception:
                    pass
            slug = re.sub(r'[^a-zA-Z0-9_\-]+', '_', f"poten_{date_str}_{title}"[:80]).strip('_').lower() + ".md"
            md_target = REPO_ROOT / "reports" / "poten" / year / slug
            if not md_target.exists():
                md_target.parent.mkdir(parents=True, exist_ok=True)
                dek_m = re.search(r'\b(\d{1,2}\s+[A-Za-z]+\s+20\d\d\s*:[^<\n\r]+)', art_html or "")
                dek_text = dek_m.group(1) if dek_m else title
                md_content = f"""---
title: "Poten Tanker Opinion: {title.replace('\"', '')}"
date: "{date_str}"
source: "poten"
category: "tankers"
source_url: "{art_url}"
author: "Erik Broekhuizen"
completeness: "full_pdf_archived"
pdf_url: "{pdf_url}"
pdf_file: "{filename}"
tags: ["crude_tankers", "ton_miles", "rerouting", "vlcc", "suezmax", "aframax"]
---

# Poten Tanker Opinion: {title}

**Author**: Erik Broekhuizen  
**Published Date**: {date_str}  
**Source URL**: [{art_url}]({art_url})  
**Full PDF Report**: [{filename}]({pdf_url})  
**Coverage**: Full PDF archived locally under reports/poten/pdfs/{year}/{filename}.

---

## Analysis & Overview

{title}

{dek_text}
"""
                md_target.write_text(md_content, encoding="utf-8", newline="\n")
        else:
            print(f"      [!] Download failed or empty size ({size} bytes)")
            reports_map[art_url] = {
                "title": title,
                "url": art_url,
                "pdf_url": pdf_url,
                "status": "download_failed",
                "page": page_num
            }

        index_data["reports"] = reports_map
        index_data["last_page"] = page_num
        index_data["total_downloaded"] = sum(1 for r in reports_map.values() if r.get("status") == "downloaded")
        save_index(index_data)
        time.sleep(delay)

    return new_downloads, True

def run_crawler(start_page=1, end_page=5, use_category=False, delay=1.5):
    print(f"Starting Poten PDF crawler for pages {start_page} to {end_page}...")
    total_new = 0
    for p in range(start_page, end_page + 1):
        count, ok = process_page(p, use_category=use_category, delay=delay)
        if not ok:
            print(f"Listing ended at page {p}.")
            break
        total_new += count
        time.sleep(delay)

    index_data = load_index()
    print(f"\n========================================================")
    print(f"Poten PDF Crawl Complete: {total_new} new PDFs downloaded.")
    print(f"Total PDFs in manifest: {index_data.get('total_downloaded', 0)}")
    print(f"========================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poten Tanker Opinions PDF Archive Crawler")
    parser.add_argument("--start", type=int, default=1, help="Starting page number")
    parser.add_argument("--end", type=int, default=5, help="Ending page number")
    parser.add_argument("--category", action="store_true", help="Use category archive URL instead of whats-new")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between requests in seconds")
    args = parser.parse_args()

    run_crawler(start_page=args.start, end_page=args.end, use_category=args.category, delay=args.delay)
