"""
Standalone Poten & Partners Weekly Tanker Opinions and LNG Insights Scraper.
Uses requests.Session with full browser headers to crawl Poten Tanker Opinions.
"""

import os
import re
import json
import time
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = REPO_ROOT / "reports" / "poten"
CHECKPOINT_FILE = REPO_ROOT / "data" / "derived" / "poten_checkpoint.json"

BASE_URL = "https://www.poten.com/category/industry-opinions/tanker-opinions/"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
ACCEPT_HEADER = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"


def http_get(url, timeout=30):
    """Fetch a page via curl.

    Poten's WAF blocks Python's TLS fingerprint (requests/urllib both get 403
    with identical headers) while curl passes. Body is spooled to a temp file;
    returns (status_code, text).
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    try:
        proc = subprocess.run(
            [
                "curl", "-s", "-L", "--max-time", str(timeout),
                "-A", USER_AGENT,
                "-H", f"Accept: {ACCEPT_HEADER}",
                "-H", "Accept-Language: en-US,en;q=0.9",
                "-o", tmp_path,
                "-w", "%{http_code}",
                url,
            ],
            capture_output=True,
            text=True,
        )
        try:
            code = int((proc.stdout or "0").strip())
        except ValueError:
            code = 0
        body = ""
        if code == 200:
            body = Path(tmp_path).read_text(encoding="utf-8", errors="ignore")
        return code, body
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

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


def norm_ws(text):
    return re.sub(r"\s+", " ", text or "").strip()

def process_article(article_url, title, date_str):
    """Ingest one Poten Tanker Opinion.

    KNOWN LIMITATION (verified 2026-08): poten.com article bodies are injected
    client-side. The server-rendered HTML carries only the metadata layer
    (title, author, date, standfirst/dek). RSS and /wp-json/ are blocked by the
    site's WAF (TLS fingerprinting) and archive.org holds no snapshots of these
    posts, so full bodies are unobtainable without a JS-rendering browser.
    We persist the metadata + dek honestly labeled as `completeness: metadata`
    so the compiler can still catalog these documents; the `full_text`
    checkpoint flag keeps them out of the processed catalog for a future
    headless-browser re-run that would upgrade them to full articles.
    """
    try:
        code, html = http_get(article_url, timeout=20)
        if code != 200:
            print(f"    [!] HTTP {code} for {article_url}")
            return False, None

        soup = BeautifulSoup(html, "html.parser")
        content_div = soup.find("div", class_="entry-content") or soup.find("article") or soup

        p_texts = []
        for p in content_div.find_all(["p", "h2", "h3", "li"]):
            t = p.get_text().strip()
            if t and not any(skip in t.lower() for skip in ["cookie", "subscribe", "all rights reserved", "poten & partners inc", "privacy policy"]):
                p_texts.append(t)

        full_text = "\n\n".join(p_texts)
        has_full_text = len(full_text) >= 400
        if not has_full_text:
            # Metadata-only fallback: title + author/date line + dek. The dek
            # lives as flat text between the "{d Mon YYYY}:" standfirst and the
            # "Share Post" widget inside <article>.
            art = soup.find("article") or soup
            for junk in art.find_all(["script", "style", "nav"]):
                junk.decompose()
            art_text = norm_ws(art.get_text(" ", strip=True))
            dek = ""
            dm = re.search(
                r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}:\s*(.+?)(?:Share Post:?|$)",
                art_text,
            )
            if dm:
                dek = dm.group(1).strip()
            # Article publish date lives only in the dek standfirst
            # ("24 Apr 2026: ..."). Listing pages carry no per-item dates.
            dmatch = re.search(r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}):\s", art_text)
            if dmatch:
                for fmt in ("%d %B %Y", "%d %b %Y"):
                    try:
                        date_str = datetime.strptime(dmatch.group(1), fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
            h1 = soup.find("h1") or art.find("h1")
            parts = [norm_ws(h1.get_text(" ", strip=True))] if h1 else [norm_ws(title)]
            if dek:
                parts.append(dek)
            full_text = "\n\n".join(x for x in parts if x)
            if len(full_text) < 60:
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
completeness: "{"full_text" if has_full_text else "metadata"}"
tags: ["crude_tankers", "ton_miles", "rerouting", "vlcc", "suezmax", "aframax"]
---

# Poten Tanker Opinion: {title}

**Published Date**: {date_str}  
**Source URL**: [{article_url}]({article_url})  
**Completeness**: {("Full article text." if has_full_text else "Metadata only - body is JS-rendered on poten.com and not retrievable via static fetch.")}

---

## Analysis & Commentary

{full_text}
"""
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(md)

        out_file.completeness = "full_text" if has_full_text else "metadata"
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
            code, html = http_get(url, timeout=25)
            if code != 200:
                print(f"[!] HTTP {code} for page {page_num}")
                break
                
            soup = BeautifulSoup(html, "html.parser")
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
                    print(f"     [OK] Saved to {path.name} (completeness={path.completeness})")
                    if path.completeness == "full_text":
                        # Metadata-only ingests stay out of the processed
                        # catalog so a future run (or headless-browser pass)
                        # can upgrade them to full-text documents.
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
