"""
Standalone Poten & Partners Weekly Tanker Opinions and LNG Insights Scraper.
Uses requests.Session with full browser headers to crawl Poten Tanker Opinions.
"""

import os
import re
import json
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = REPO_ROOT / "reports" / "poten"
CHECKPOINT_FILE = REPO_ROOT / "data" / "derived" / "poten_checkpoint.json"

BASE_URL = "https://www.poten.com/category/industry-opinions/tanker-opinions/"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.poten.com/category/industry-opinions/tanker-opinions/",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
})

def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"processed_urls": [], "last_page": 1}
    return {"processed_urls": [], "last_page": 1}

def save_checkpoint(cp):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(cp, f, indent=2)

def process_article(article_url, title, date_str):
    try:
        resp = SESSION.get(article_url, timeout=20)
        if resp.status_code != 200:
            print(f"    [!] HTTP {resp.status_code} for {article_url}")
            return False, None
            
        soup = BeautifulSoup(resp.text, "html.parser")
        content_div = soup.find("div", class_="entry-content") or soup.find("article") or soup
        
        p_texts = []
        for p in content_div.find_all(["p", "h2", "h3", "li"]):
            t = p.get_text().strip()
            if t and not any(skip in t.lower() for skip in ["cookie", "subscribe", "all rights reserved", "poten & partners inc", "privacy policy"]):
                p_texts.append(t)
        
        full_text = "\n\n".join(p_texts)
        if len(full_text) < 100:
            return False, None
            
        year_match = re.search(r'\b(202[0-6])\b', date_str + " " + title)
        year = year_match.group(1) if year_match else "2026"
        
        slug = re.sub(r'[^a-zA-Z0-9_\-]+', '_', f"poten_{date_str}_{title}"[:80]).strip('_').lower()
        
        out_year_dir = OUTPUT_DIR / year
        out_year_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_year_dir / f"{slug}.md"
        
        md = f"""---
title: "Poten Tanker Opinion: {title.replace('"', '')}"
date: "{date_str}"
source: "poten"
category: "tankers"
source_url: "{article_url}"
tags: ["crude_tankers", "ton_miles", "rerouting", "vlcc", "suezmax", "aframax"]
---

# Poten Tanker Opinion: {title}

**Published Date**: {date_str}  
**Source URL**: [{article_url}]({article_url})  

---

## Analysis & Commentary

{full_text}
"""
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(md)
            
        return True, out_file
    except Exception as e:
        print(f"    [!] Error parsing {article_url}: {e}")
        return False, None

def crawl_poten(max_pages=2, delay_sec=1.5):
    checkpoint = load_checkpoint()
    processed_set = set(checkpoint.get("processed_urls", []))
    
    print(f"Starting Poten & Partners crawl. Known URLs: {len(processed_set)}")
    
    for page_num in range(1, max_pages + 1):
        url = BASE_URL if page_num == 1 else f"{BASE_URL}page/{page_num}/"
        print(f"\n--- Scraping Page {page_num}: {url} ---")
        
        try:
            resp = SESSION.get(url, timeout=25)
            if resp.status_code != 200:
                print(f"[!] HTTP {resp.status_code} for page {page_num}")
                break
                
            soup = BeautifulSoup(resp.text, "html.parser")
            articles = []
            for h2 in soup.find_all(["h2", "h3"], class_=re.compile(r"entry-title|title|post-title")):
                a = h2.find("a", href=True)
                if a:
                    title = a.get_text().strip()
                    href = a["href"]
                    date_str = "2026-08-24"
                    parent = h2.find_parent(["article", "div"])
                    if parent:
                        d_elem = parent.find(["time", "span"], class_=re.compile(r"date|published"))
                        if d_elem:
                            date_str = d_elem.get_text().strip()
                    articles.append((href, title, date_str))
                    
            print(f"Found {len(articles)} articles on page {page_num}")
            for href, title, date_str in articles:
                if href in processed_set:
                    continue
                print(f"  -> Fetching: {title[:60]}...")
                ok, path = process_article(href, title, date_str)
                if ok:
                    print(f"     [OK] Saved to {path.name}")
                    processed_set.add(href)
                    checkpoint["processed_urls"] = list(processed_set)
                    checkpoint["last_page"] = page_num
                    save_checkpoint(checkpoint)
                time.sleep(delay_sec)
                
        except Exception as e:
            print(f"[!] Error on page {page_num}: {e}")
            break
            
    print(f"\nPoten crawl finished. Total in catalog: {len(processed_set)}")

if __name__ == "__main__":
    import sys
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    crawl_poten(max_pages=pages)
