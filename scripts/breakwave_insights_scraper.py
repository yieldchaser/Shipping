"""
Breakwave Advisors Insights Scraper
=====================================
Scrapes all articles from https://www.breakwaveadvisors.com/insights
including full text, images, and embedded charts.

Structure:
  C:/Users/Dell/Github/Shipping/reports/breakwave/
    {year}/
      {date}_{slug}.html       ← clean article HTML
    images/
      {slug}_{filename}.{ext}  ← downloaded images

Usage:
    python breakwave_scraper.py               # full run
    python breakwave_scraper.py --dry-run     # list URLs only
    python breakwave_scraper.py --year 2026   # single year

Install:
    pip install requests beautifulsoup4 lxml
"""

import re
import time
import argparse
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlencode, parse_qs
from datetime import datetime
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL    = "https://www.breakwaveadvisors.com"
START_URL   = "https://www.breakwaveadvisors.com/insights"
OUTPUT_ROOT = Path(r"C:\Users\Dell\Github\Shipping\reports\breakwave")
IMAGES_DIR  = OUTPUT_ROOT / "images"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.breakwaveadvisors.com/",
}

PAGE_DELAY     = 1.5   # between listing pages
ARTICLE_DELAY  = 1.2   # between article downloads
IMAGE_DELAY    = 0.5

# ── HTTP session ──────────────────────────────────────────────────────────────

session = requests.Session()
session.headers.update(HEADERS)


def get(url: str, retries: int = 3, stream: bool = False):
    for i in range(retries):
        try:
            r = session.get(url, timeout=30, stream=stream)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"    ⚠  [{i+1}/{retries}] {url[-60:]}  {e}")
            if i < retries - 1:
                time.sleep(3)
    return None


def soup(url: str) -> "BeautifulSoup | None":
    r = get(url)
    return BeautifulSoup(r.content, "lxml") if r else None


# ── Listing page: collect article URLs ───────────────────────────────────────

ARTICLE_PATTERN = re.compile(
    r"https://www\.breakwaveadvisors\.com/insights/\S+", re.IGNORECASE
)

def is_article_url(href: str) -> bool:
    """True if href looks like an individual article, not a filter/tag/author page."""
    if not href:
        return False
    parsed = urlparse(href)
    path = parsed.path.rstrip("/")
    # Exclude: /insights itself, /insights?author=..., /insights/tag/..., /insights?offset=...
    if path == "/insights":
        return False
    if parsed.query:   # any ?param= is a filter page, not an article
        return False
    if "/insights/tag/" in path:
        return False
    if path.count("/") < 2:   # must be at least /insights/something
        return False
    return True


def extract_article_links(page_soup: BeautifulSoup) -> list:
    links = set()
    for a in page_soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            href = urljoin(BASE_URL, href)
        if "breakwaveadvisors.com/insights/" in href and is_article_url(href):
            # Strip fragments
            links.add(href.split("#")[0])
    return list(links)


def get_older_posts_url(page_soup: BeautifulSoup) -> "str | None":
    """Find the 'Older Posts' pagination link."""
    for a in page_soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if "older" in text:
            href = a["href"]
            if not href.startswith("http"):
                href = urljoin(BASE_URL, href)
            return href
    return None


def collect_all_article_urls(year_filter: "int | None" = None) -> list:
    """Walk all listing pages via 'Older Posts', collecting unique article URLs."""
    all_links = set()
    page_url  = START_URL
    page_num  = 1

    while page_url:
        print(f"  📄 Listing page {page_num}: {page_url[-80:]}")
        pg = soup(page_url)
        if pg is None:
            print(f"  ✗ Failed to fetch listing page — stopping")
            break

        links = extract_article_links(pg)
        before = len(all_links)
        all_links.update(links)
        print(f"     +{len(all_links) - before} new links  (total {len(all_links)})")

        older = get_older_posts_url(pg)
        if older and older != page_url:
            page_url = older
            page_num += 1
            time.sleep(PAGE_DELAY)
        else:
            print(f"  ✓ No more 'Older Posts' — reached the end")
            break

    # Apply year filter if requested
    if year_filter:
        filtered = []
        for url in all_links:
            # Try to extract year from URL path e.g. /insights/2024/3/11/...
            m = re.search(r"/insights/(\d{4})/", url)
            if m and int(m.group(1)) == year_filter:
                filtered.append(url)
            elif not m:
                # URLs like /insights/tanker4726 — keep always (no year in path)
                filtered.append(url)
        return sorted(filtered, reverse=True)

    return sorted(all_links, reverse=True)


# ── Article page: extract content ────────────────────────────────────────────

HTML_CSS = """
*, *::before, *::after { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Georgia, serif;
    font-size: 15px; line-height: 1.75; color: #1a1a1a;
    max-width: 860px; margin: 0 auto; padding: 32px 24px; background: #fff;
}
h1 { font-size: 1.7em; color: #1a1a1a; margin: 0 0 8px; line-height: 1.3; }
h2 { font-size: 1.25em; color: #222; margin: 24px 0 8px; }
h3 { font-size: 1.05em; color: #222; margin: 16px 0 6px; }
p  { margin: 0 0 14px; }
a  { color: #1a6b3c; }
img { max-width: 100%; height: auto; margin: 16px 0; border-radius: 4px; }
.meta {
    font-size: 0.82em; color: #555; margin: 6px 0 20px;
    padding: 6px 12px; background: #f4f6f4;
    border-left: 3px solid #1a6b3c; border-radius: 2px;
}
.source-tag { font-weight: 600; color: #1a6b3c; }
.tags { font-size: 0.8em; color: #888; margin-top: 24px; }
.chart-embed { background: #f8f8f8; border: 1px solid #ddd;
               padding: 10px; margin: 16px 0; border-radius: 4px;
               font-size: 0.85em; color: #555; }
hr { border: none; border-top: 1px solid #e0e0e0; margin: 20px 0; }
blockquote { border-left: 3px solid #ccc; margin: 16px 0;
             padding: 4px 16px; color: #444; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; }
th { background: #1a6b3c; color: #fff; padding: 8px 12px; text-align: left; }
td { padding: 7px 12px; border-bottom: 1px solid #e0e6ed; }
tr:nth-child(even) td { background: #f5f9f5; }
"""


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].strip("-")


def sanitize_filename(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", s)


def download_image(img_url: str, slug: str) -> "tuple[str, str] | None":
    """
    Download an image. Returns (local_rel_path, img_url) or None on failure.
    local_rel_path is relative to the article HTML file.
    """
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(img_url)
    ext = Path(parsed.path).suffix or ".jpg"
    if len(ext) > 5:
        ext = ".jpg"
    # Build filename from slug + url hash
    img_slug = slugify(Path(parsed.path).stem or "img")
    fname = sanitize_filename(f"{slug[:30]}_{img_slug[:40]}{ext}")
    dest = IMAGES_DIR / fname

    if dest.exists() and dest.stat().st_size > 500:
        return (f"../../images/{fname}", img_url)

    r = get(img_url, stream=True)
    if r is None:
        return None
    dest.write_bytes(r.content)
    time.sleep(IMAGE_DELAY)
    return (f"../../images/{fname}", img_url)


def extract_article(pg: BeautifulSoup, url: str) -> "dict | None":
    """Extract all fields from an article page."""
    # Title
    h1 = pg.find("h1")
    title = h1.get_text(strip=True) if h1 else url.split("/")[-1]

    # Date — look for time tag or date-looking text near top of page
    date_str = ""
    date_obj = None
    for sel in ["time", ".entry-dateline", "[class*='date']", "[class*='Date']"]:
        el = pg.select_one(sel)
        if el:
            raw = el.get_text(strip=True)
            # Try to parse
            for fmt in ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d %B %Y"]:
                try:
                    date_obj = datetime.strptime(raw, fmt)
                    date_str = raw
                    break
                except ValueError:
                    pass
            if date_obj:
                break

    # Fallback: extract from URL path /insights/2026/4/8/...
    if not date_obj:
        m = re.search(r"/insights/(\d{4})/(\d{1,2})/(\d{1,2})/", url)
        if m:
            try:
                date_obj = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                date_str = date_obj.strftime("%B %d, %Y")
            except ValueError:
                pass

    # Source / author
    source = ""
    for sel in [".author-name", ".entry-author", "[class*='author']",
                "[itemprop='author']"]:
        el = pg.select_one(sel)
        if el:
            t = el.get_text(strip=True)
            if t and len(t) < 80:
                source = t
                break

    # Tags
    tags = []
    for a in pg.find_all("a", href=True):
        if "/insights/tag/" in a["href"]:
            tags.append(a.get_text(strip=True))

    # Main content body — try multiple selectors
    body = None
    for sel in [".entry-content", ".blog-item-content", ".post-content",
                "[class*='entry-content']", "[class*='blog-item-content']",
                "article", ".sqs-block-content", "main"]:
        el = pg.select_one(sel)
        if el and len(el.get_text(strip=True)) > 150:
            body = el
            break

    if body is None:
        # Fallback: take the largest text div
        best, best_len = None, 0
        for div in pg.find_all(["div", "section"]):
            t = div.get_text(strip=True)
            if len(t) > best_len and len(t) < 50000:
                best, best_len = div, len(t)
        body = best

    return {
        "title":    title,
        "url":      url,
        "date_str": date_str,
        "date_obj": date_obj,
        "source":   source,
        "tags":     tags,
        "body":     body,
    }


def build_html(info: dict, slug: str) -> str:
    """Build clean self-contained HTML from extracted article info."""
    title    = info["title"]
    url      = info["url"]
    date_str = info["date_str"]
    source   = info["source"]
    tags     = info["tags"]
    body     = info["body"]

    # Process body: download images, note iframes
    img_notes = []
    iframe_notes = []

    if body:
        # Remove nav/header/footer/scripts
        for tag in body.find_all(["nav", "header", "footer", "script",
                                   "style", "noscript"]):
            tag.decompose()

        # Handle images — download and repoint src
        for img in body.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if not src:
                continue
            if not src.startswith("http"):
                src = urljoin(BASE_URL, src)
            result = download_image(src, slug)
            if result:
                local_path, orig = result
                img["src"] = local_path
                img["loading"] = "lazy"
                img.attrs.pop("data-src", None)
            else:
                img_notes.append(src)

        # Handle iframes (Signal Ocean charts, etc.) — replace with note
        for iframe in body.find_all("iframe"):
            src = iframe.get("src", "")
            note = body.new_tag("div")
            note["class"] = "chart-embed"
            note.string = f"[Embedded chart: {src}]"
            iframe.replace_with(note)
            iframe_notes.append(src)

        # Strip class/id/style from all tags for cleaner LLM processing
        for tag in body.find_all(True):
            for attr in ["class", "id", "style", "onclick", "onload"]:
                tag.attrs.pop(attr, None)

        body_html = str(body)
    else:
        body_html = "<p><em>No content extracted — visit the original URL.</em></p>"

    tags_html = ""
    if tags:
        tag_list = " · ".join(tags)
        tags_html = f'<p class="tags">Tags: {tag_list}</p>'

    iframe_html = ""
    if iframe_notes:
        links = " | ".join(f'<a href="{s}">{s[:60]}</a>' for s in iframe_notes)
        iframe_html = f'<p class="tags">📊 Embedded charts: {links}</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>{HTML_CSS}</style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">
    <span class="source-tag">{source}</span>
    &nbsp;|&nbsp; {date_str}
    &nbsp;|&nbsp; <a href="{url}">{url}</a>
  </div>
  <hr>
  {body_html}
  {tags_html}
  {iframe_html}
</body>
</html>"""


def make_dest(info: dict, slug: str) -> Path:
    year = info["date_obj"].year if info["date_obj"] else "unknown"
    ds   = info["date_obj"].strftime("%Y-%m-%d") if info["date_obj"] else "0000-00-00"
    fname = sanitize_filename(f"{ds}_{slug}.html")
    return OUTPUT_ROOT / str(year) / fname


def process_article(url: str, dry_run: bool) -> bool:
    slug = slugify(url.rstrip("/").split("/")[-1])
    time.sleep(ARTICLE_DELAY)

    pg = soup(url)
    if pg is None:
        print(f"    ✗ Failed to fetch")
        return False

    info = extract_article(pg, url)
    if info is None:
        return False

    dest = make_dest(info, slug)

    # Skip if already saved with reasonable size
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"    ✓ skip: {dest.name}")
        return True

    if dry_run:
        ds = info["date_str"] or "unknown date"
        print(f"    [DRY RUN] {ds}  {info['title'][:60]}  → {dest.name}")
        return True

    html = build_html(info, slug)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    kb = dest.stat().st_size // 1024
    print(f"    ↓ {dest.name}  ({kb} KB)")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def run(dry_run: bool, year_filter: "int | None"):
    print(f"\n{'═'*64}")
    print(f"  Breakwave Advisors Insights Scraper")
    print(f"  Mode  : {'DRY RUN' if dry_run else 'DOWNLOAD'}")
    if year_filter:
        print(f"  Year  : {year_filter}")
    print(f"{'═'*64}\n")

    print(f"  🔍 Collecting article URLs from all listing pages...\n")
    urls = collect_all_article_urls(year_filter)
    print(f"\n  ✅ {len(urls)} articles to process\n")
    print(f"{'─'*64}")

    ok = fail = 0
    for i, url in enumerate(urls, 1):
        print(f"\n  [{i}/{len(urls)}] {url.split('/')[-1][:60]}")
        if process_article(url, dry_run):
            ok += 1
        else:
            fail += 1

    print(f"\n{'═'*64}")
    print(f"  DONE  ✓ {ok} saved   ✗ {fail} failed")
    print(f"{'═'*64}\n")


def main():
    p = argparse.ArgumentParser(description="Breakwave Advisors Insights Scraper")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--year",    type=int, default=None)
    args = p.parse_args()
    run(args.dry_run, args.year)


if __name__ == "__main__":
    main()
