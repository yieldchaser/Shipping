"""
download_signal_images.py
Downloads all 1,423 unique embedded images from The Signal Group reports into corpus/07-signal/images/
and localizes image references across all markdown files in corpus/07-signal/monitors/ and corpus/07-signal/newsroom/.
"""

import os
import re
import urllib.request
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = "corpus/07-signal"
IMG_DIR = os.path.join(BASE_DIR, "images")
os.makedirs(IMG_DIR, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_clean_filename(url):
    path = urlparse(url).path
    filename = path.split("/")[-1]
    # Remove URL encoding like %20
    filename = urllib.parse.unquote(filename)
    # Sanitize invalid Windows characters
    filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
    if not any(filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.avif', '.gif', '.svg']):
        filename += '.png'
    return filename

def harvest_and_localize():
    import glob
    import shutil
    md_files = []
    for sub in ["monitors", "newsroom", "newsletters"]:
        sub_path = os.path.join(BASE_DIR, sub)
        if os.path.exists(sub_path):
            md_files.extend(glob.glob(os.path.join(sub_path, "**", "*.md"), recursive=True))
                    
    print(f"[*] Found {len(md_files)} Markdown files across monitors, newsroom, and newsletters.")
    
    url_to_local = {}
    
    # 1. Collect all unique image URLs
    for md_path in md_files:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        matches = re.findall(r'!\[.*?\]\((https?://cdn\.prod\.website-files\.com/[^\)]+)\)', content)
        for u in matches:
            if u not in url_to_local:
                local_name = get_clean_filename(u)
                url_to_local[u] = local_name
                
    print(f"[*] Found {len(url_to_local)} unique embedded images to download.")
    
    ext_img_dir = os.path.join("data", "extracted", "md", "signal", "images")
    os.makedirs(ext_img_dir, exist_ok=True)

    # 2. Download images with thread pool
    def download_img(url, local_name):
        dest = os.path.join(IMG_DIR, local_name)
        ext_dest = os.path.join(ext_img_dir, local_name)
        if os.path.exists(dest) and os.path.getsize(dest) > 100:
            if not os.path.exists(ext_dest):
                try:
                    shutil.copy2(dest, ext_dest)
                except Exception:
                    pass
            return local_name, "cached", os.path.getsize(dest)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            with open(dest, "wb") as f:
                f.write(data)
            try:
                shutil.copy2(dest, ext_dest)
            except Exception:
                pass
            return local_name, "downloaded", len(data)
        except Exception as e:
            return local_name, f"error: {e}", 0

    downloaded = 0
    cached = 0
    errors = 0
    total_bytes = 0
    
    print("[*] Starting multi-threaded image download...")
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(download_img, u, name) for u, name in url_to_local.items()]
        for idx, fut in enumerate(as_completed(futures)):
            name, status, sz = fut.result()
            total_bytes += sz
            if status == "downloaded":
                downloaded += 1
            elif status == "cached":
                cached += 1
            else:
                errors += 1
            if (idx + 1) % 100 == 0 or (idx + 1) == len(futures):
                print(f"  [{idx+1}/{len(futures)}] Processed ({downloaded} new, {cached} cached, {errors} errors)")
                
    print(f"[+] All images downloaded: {downloaded} new, {cached} cached, {errors} errors.")
    print(f"[+] Total Image Disk Space: {round(total_bytes / (1024 * 1024), 2)} MB in {IMG_DIR}")
    
    # 3. Localize image references in markdown files
    print("[*] Localizing markdown image paths...")
    for md_path in md_files:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        modified = False
        parent_name = os.path.basename(os.path.dirname(md_path))
        rel_prefix = "../../images" if parent_name.isdigit() and len(parent_name) == 4 else "../images"
        for u, local_name in url_to_local.items():
            if u in content:
                content = content.replace(u, f"{rel_prefix}/{local_name}")
                modified = True
                
        if modified:
            with open(md_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
                
    print("[+] Successfully localized all markdown files!")

if __name__ == "__main__":
    harvest_and_localize()
