#!/usr/bin/env python3
"""
scripts/acquire/sync_hellenic_live.py
High-speed incremental harvester for Hellenic Shipping News intelligence.
Uses the WordPress REST API to detect, catalog, and download new reports:
- Category 123: Weekly Shipbrokers Reports (SSY, Xclusiv, Clarksons, Carriers, ISM, Star Asia, Affinity, etc.)
- Category 126: Weekly Demolition Reports (GMS, Best Oasis, Athenian)
- Category 119: Chinese Iron Ore & Steelmaking Reports (MMi Daily Reports)
- Categories 162 & 164: Weekly Time Charter Estimates (Alibra Dry & Tankers)
- Category 129: Weekly Vessel Valuations (VesselsValue)
"""

import os
import re
import sys
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

BROKER_MANIFEST_CSV = ROOT / "corpus" / "01-brokers" / "shipbrokers_manifest.csv"

BROKER_SLUG_MAP = {
    "affinity": "affinity",
    "banchero": "banchero_costa",
    "bancosta": "banchero_costa",
    "advanced": "advanced_shipping",
    "allied": "allied",
    "intermodal": "intermodal",
    "xclusiv": "xclusiv",
    "gibson": "gibson",
    "clarksons": "clarksons",
    "clarkson": "clarksons",
    "lion": "lion",
    "agora": "agora",
    "carriers": "carriers",
    "optima": "optima",
    "intership": "intership",
    "star asia": "star_asia",
    "asiasis": "star_asia",
    "cotzias": "cotzias",
    "weber": "weberseas",
    "golden destiny": "golden_destiny",
    "anchor": "anchor",
    "alibra": "alibra",
    "fearnleys": "fearnleys",
    "ssy": "ssy",
    "simpson": "ssy",
    "ism": "ism",
}

def detect_broker_slug(title, content):
    t_lower = (title + " " + content[:400]).lower()
    for k, v in BROKER_SLUG_MAP.items():
        if k in t_lower:
            return v
    return "other"

def detect_demolition_slug(title, content):
    t_lower = (title + " " + content[:400]).lower()
    if "gms" in t_lower:
        return "gms"
    elif "best oasis" in t_lower:
        return "best_oasis"
    elif "athenian" in t_lower:
        return "athenian"
    return "other"

def extract_week(title):
    m = re.search(r'(?:week|wk|w)\s*(\d{1,2})', title, re.I)
    return f"W{int(m.group(1)):02d}" if m else "N/A"

def fetch_api_posts(category_id, pages=2, per_page=50):
    posts = []
    for p in range(1, pages + 1):
        url = f"https://www.hellenicshippingnews.com/wp-json/wp/v2/posts?categories={category_id}&per_page={per_page}&page={p}"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                batch = json.loads(resp.read().decode("utf-8"))
                if not batch:
                    break
                posts.extend(batch)
                time.sleep(0.5)
        except Exception as e:
            print(f"    Notice fetching category {category_id} page {p}: {e}")
            break
    return posts

def _load_untracked_inventory() -> set:
    inv_path = ROOT / "corpus" / "_inventory_untracked.json"
    if not inv_path.exists():
        return set()
    try:
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        items = data.get("entries") or data.get("files") or []
        return {
            str(f.get("path", "")).replace("\\", "/")
            for f in items
            if (f.get("bytes") or f.get("size_bytes") or 0) > 500
        }
    except Exception:
        return set()

UNTRACKED_INVENTORY = _load_untracked_inventory()

def _is_in_inventory(target_path: Path) -> bool:
    try:
        rel = str(target_path.relative_to(ROOT)).replace("\\", "/")
        return rel in UNTRACKED_INVENTORY
    except Exception:
        return False

def download_file(url, target_path):
    if (target_path.exists() and target_path.stat().st_size > 1024) or _is_in_inventory(target_path):
        return False, "cached"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if len(data) > 500:
                    with open(target_path, "wb") as f:
                        f.write(data)
                    # Dual-save mirror if under corpus/02-hellenic
                    try:
                        rel = target_path.relative_to(ROOT / "corpus" / "02-hellenic")
                        legacy_dest = ROOT / "reports" / "hellenic" / rel
                        legacy_dest.parent.mkdir(parents=True, exist_ok=True)
                        if not legacy_dest.exists():
                            with open(legacy_dest, "wb") as lf:
                                lf.write(data)
                    except Exception:
                        pass
                    return True, "downloaded"
        except Exception as e:
            time.sleep(1.0)
    return False, "failed"

def sync_shipbrokers():
    print("\n--- Synchronizing Category 123 (Weekly Shipbrokers) ---")
    posts = fetch_api_posts(123, pages=2, per_page=50)
    print(f"  Fetched {len(posts)} recent shipbroker posts from API")
    
    # Load manifest
    manifest_rows = []
    existing_pids = set()
    if BROKER_MANIFEST_CSV.exists():
        df_man = pd.read_csv(BROKER_MANIFEST_CSV)
        existing_pids = set(df_man["post_id"].astype(str).tolist())
    
    new_downloads = 0
    new_manifest_records = []
    
    for p in posts:
        pid = str(p["id"])
        title = p["title"]["rendered"]
        date_iso = p["date"][:10]
        year = date_iso[:4]
        content = p.get("content", {}).get("rendered", "")
        broker_slug = detect_broker_slug(title, content)
        week = extract_week(title)
        
        pdfs = re.findall(r'https?://[^\s"\'<>]+\.pdf', content, re.I)
        pdf_url = pdfs[0].strip() if pdfs else ""
        
        local_path = ""
        status = "no_pdf"
        file_size = 0
        
        if pdf_url:
            raw_fn = urllib.parse.unquote(pdf_url.split("/")[-1])
            sanitized_fn = re.sub(r'[\\/*?:"<>| ]', '_', raw_fn)
            if not sanitized_fn.lower().endswith(".pdf"):
                sanitized_fn += ".pdf"
            wk_str = f"_{week}" if week != "N/A" else ""
            final_name = f"{broker_slug}_{year}{wk_str}_{sanitized_fn}"
            dest = ROOT / "corpus" / "01-brokers" / broker_slug / year / final_name
            
            dl_ok, dl_status = download_file(pdf_url, dest)
            if dl_ok:
                new_downloads += 1
                print(f"  [+] Downloaded: {dest.name} ({dest.stat().st_size // 1024} KB)")
            local_path = str(dest.relative_to(ROOT)).replace("\\", "/") if dest.exists() else ""
            status = "downloaded" if dl_ok else ("cached" if dest.exists() else "failed")
            file_size = dest.stat().st_size if dest.exists() else 0
            
        if pid not in existing_pids:
            new_manifest_records.append({
                "post_id": pid,
                "title": title,
                "date": date_iso,
                "year": int(year),
                "week": week,
                "broker": broker_slug,
                "post_url": p.get("link", ""),
                "pdf_url": pdf_url,
                "has_pdf": bool(pdf_url),
                "local_path": local_path,
                "file_size_bytes": file_size,
                "download_status": status,
            })
            existing_pids.add(pid)
            
    if new_manifest_records:
        df_new = pd.DataFrame(new_manifest_records)
        if BROKER_MANIFEST_CSV.exists():
            df_combined = pd.concat([df_new, df_man], ignore_index=True).drop_duplicates(subset=["post_id"])
            df_combined.sort_values(by="date", ascending=False, inplace=True)
            df_combined.to_csv(BROKER_MANIFEST_CSV, index=False, lineterminator="\n")
        else:
            df_new.to_csv(BROKER_MANIFEST_CSV, index=False, lineterminator="\n")
        print(f"  Appended {len(new_manifest_records)} new records to shipbrokers_manifest.csv")
    else:
        print("  Shipbrokers manifest is fully up to date.")
        
    print(f"  New PDFs downloaded: {new_downloads}")
    return new_downloads

def sync_demolition():
    print("\n--- Synchronizing Category 126 (Weekly Demolition) ---")
    posts = fetch_api_posts(126, pages=1, per_page=30)
    print(f"  Fetched {len(posts)} recent demolition posts from API")
    new_dl = 0
    
    for p in posts:
        pid = str(p["id"])
        title = p["title"]["rendered"]
        date_iso = p["date"][:10]
        year = date_iso[:4]
        content = p.get("content", {}).get("rendered", "")
        slug = detect_demolition_slug(title, content)
        if slug == "other":
            continue
            
        pdfs = re.findall(r'https?://[^\s"\'<>]+\.pdf', content, re.I)
        if not pdfs:
            continue
            
        pdf_url = pdfs[0].strip()
        raw_fn = urllib.parse.unquote(pdf_url.split("/")[-1])
        sanitized_fn = re.sub(r'[\\/*?:"<>| ]', '_', raw_fn)
        clean_title_slug = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-').lower()[:40]
        dest_name = f"{date_iso}_{clean_title_slug}_{sanitized_fn}"
        dest = ROOT / "corpus" / "02-hellenic" / "demolition" / "pdfs" / slug / dest_name
        
        ok, st = download_file(pdf_url, dest)
        if ok:
            new_dl += 1
            print(f"  [+] Downloaded: {slug}/{dest.name} ({dest.stat().st_size // 1024} KB)")
            
    print(f"  New demolition PDFs downloaded: {new_dl}")
    return new_dl

def sync_iron_ore():
    print("\n--- Synchronizing Category 119 (Chinese Iron Ore & Steelmaking) ---")
    posts = fetch_api_posts(119, pages=1, per_page=30)
    print(f"  Fetched {len(posts)} recent iron ore posts from API")
    new_dl = 0
    
    for p in posts:
        pid = str(p["id"])
        title = p["title"]["rendered"]
        date_iso = p["date"][:10]
        year = date_iso[:4]
        content = p.get("content", {}).get("rendered", "")
        
        pdfs = re.findall(r'https?://[^\s"\'<>]+\.pdf', content, re.I)
        if not pdfs:
            continue
            
        pdf_url = pdfs[0].strip()
        raw_fn = urllib.parse.unquote(pdf_url.split("/")[-1])
        sanitized_fn = re.sub(r'[\\/*?:"<>| ]', '_', raw_fn)
        clean_title_slug = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-').lower()[:40]
        dest_name = f"{date_iso}_{clean_title_slug}_{sanitized_fn}"
        dest = ROOT / "corpus" / "02-hellenic" / "iron_ore" / "pdfs" / year / dest_name
        
        ok, st = download_file(pdf_url, dest)
        if ok:
            new_dl += 1
            print(f"  [+] Downloaded: iron_ore/{year}/{dest.name} ({dest.stat().st_size // 1024} KB)")
            
    print(f"  New iron ore PDFs downloaded: {new_dl}")
    return new_dl

def sync_html_articles():
    print("\n--- Synchronizing Categories 162, 164, 129 (Alibra & VesselsValue HTML) ---")
    categories = [
        (162, "dry_charter"),
        (164, "tanker_charter"),
        (129, "vessel_valuations")
    ]
    new_articles = 0
    for cat_id, cat_slug in categories:
        posts = fetch_api_posts(cat_id, pages=1, per_page=15)
        for p in posts:
            title = p["title"]["rendered"]
            date_iso = p["date"][:10]
            year = date_iso[:4]
            if not re.match(r"^20\d{2}-\d{2}-\d{2}$", date_iso):
                continue
            slug = p.get("slug") or re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-').lower()
            content = p.get("content", {}).get("rendered", "")
            if len(content.strip()) < 80 or any(err in content for err in ("Error code 520", "Cloudflare Ray ID", "This site can't be reached", "This site can\u2019t be reached")):
                continue
            
            dest = ROOT / "corpus" / "02-hellenic" / cat_slug / year / f"{date_iso}_{slug}.html"
            if not dest.exists() and not _is_in_inventory(dest):
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(f"<!-- Title: {title} | Date: {date_iso} | URL: {p.get('link', '')} -->\n")
                    f.write(content)
                new_articles += 1
                print(f"  [+] Saved HTML: {cat_slug}/{year}/{dest.name}")
    print(f"  New HTML articles saved: {new_articles}")
    return new_articles

def main():
    print("=================================================================")
    print("  HELLENIC SHIPPING NEWS LIVE INCREMENTAL HARVESTER              ")
    print("=================================================================")
    t0 = time.time()
    
    n_sb = sync_shipbrokers()
    n_demo = sync_demolition()
    n_io = sync_iron_ore()
    n_html = sync_html_articles()
    
    elapsed = time.time() - t0
    print("\n=================================================================")
    print(f"  Harvest complete in {elapsed:.1f}s.")
    print(f"  Deltas -> Shipbroker PDFs: +{n_sb} | Demo PDFs: +{n_demo} | Iron Ore PDFs: +{n_io} | HTML Articles: +{n_html}")
    print("=================================================================")

if __name__ == "__main__":
    main()
