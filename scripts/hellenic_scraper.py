"""
Hellenic Shipping News — Multi-Category Scraper
=================================================
Scrapes 6 report categories from hellenicshippingnews.com.
Uses Selenium (headless Chrome) to bypass 403 blocks.

For each article saves:
  - Clean HTML  (text + inline images)
  - Downloaded images (JPGs of tables etc.)
  - Downloaded PDFs  (if "Download PDF" link present)

Output:
  C:/Users/Dell/Github/Shipping/reports/hellenic/
    {category}/
      {year}/
        {date}_{slug}.html
        {date}_{slug}_img1.jpg  ...
      pdfs/
        {date}_{slug}.pdf  ...

Usage:
    python hellenic_scraper.py                          # all 6 categories
    python hellenic_scraper.py --category dry_charter   # one category
    python hellenic_scraper.py --dry-run                # list URLs only
    python hellenic_scraper.py --year 2026              # single year

Install (already have these):
    pip install selenium requests beautifulsoup4 lxml
"""

import re
import sys
import time
import argparse
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL    = "https://www.hellenicshippingnews.com"
OUTPUT_ROOT = Path(r"C:\Users\Dell\Github\Shipping\reports\hellenic")

CATEGORIES = {
    "dry_charter": (
        "https://www.hellenicshippingnews.com/category/report-analysis/"
        "weekly-dry-time-charter-estimates/"
    ),
    "tanker_charter": (
        "https://www.hellenicshippingnews.com/category/report-analysis/"
        "weekly-tanker-time-charter-estimates/"
    ),
    "iron_ore": (
        "https://www.hellenicshippingnews.com/category/commodities/"
        "chinese-iron-ore-and-steelmaking-prices/"
    ),
    "vessel_valuations": (
        "https://www.hellenicshippingnews.com/category/report-analysis/"
        "weekly-vessel-valuations-report/"
    ),
    "demolition": (
        "https://www.hellenicshippingnews.com/category/report-analysis/"
        "weekly-demolition-reports/"
    ),
    "shipbuilding": (
        "https://www.hellenicshippingnews.com/category/report-analysis/"
        "weekly-shipbuilding-reports/"
    ),
}

PAGE_DELAY    = 1.5
ARTICLE_DELAY = 1.5
ASSET_DELAY   = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.hellenicshippingnews.com/",
}

dl_session = requests.Session()
dl_session.headers.update(HEADERS)

# ── Selenium driver ───────────────────────────────────────────────────────────

def get_driver(headed: bool = False):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if not headed:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    opts.add_argument("--log-level=3")
    opts.page_load_strategy = "eager"   # don't wait for ads/trackers to load
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        print(f"  ✗ Chrome failed: {e}")
        sys.exit(1)
    driver.set_page_load_timeout(60)
    return driver


def fetch_soup(driver, url: str, wait: float = 2.5) -> "BeautifulSoup | None":
    for attempt in range(3):
        try:
            driver.get(url)
            time.sleep(wait)
            return BeautifulSoup(driver.page_source, "lxml")
        except Exception as e:
            # Suppress the massive stacktrace — just show first line
            first_line = str(e).split("\n")[0][:120]
            print(f"    ⚠  [{attempt+1}/3] {first_line}")
            try:
                # Page may have partially loaded — try to get what we have
                src = driver.page_source
                if src and len(src) > 500:
                    print(f"    ↺  Partial page recovered")
                    return BeautifulSoup(src, "lxml")
            except Exception:
                pass
            time.sleep(3)
    return None


# ── Listing page: collect article URLs ───────────────────────────────────────

def get_article_links(pg: BeautifulSoup, cat_url: str) -> list:
    """
    Extract article URLs from a category listing page.
    Only picks up links from the MAIN article listing — not sidebar/footer/nav.
    Strategy: find article title links (h2.entry-title a) or Read More links
    that are inside the main content area.
    """
    links = []
    seen  = set()
    domain = urlparse(cat_url).netloc
    cat_path = urlparse(cat_url).path.rstrip("/")

    def add(href):
        if not href:
            return
        if not href.startswith("http"):
            href = urljoin(BASE_URL, href)
        href = href.split("#")[0].rstrip("/")
        parsed = urlparse(href)
        if parsed.netloc != domain:
            return
        if parsed.query:
            return
        path = parsed.path.strip("/")
        # Must not be a category/tag/page/author/feed/wp- URL
        if any(x in path for x in [
            "category/", "tag/", "/page/", "author/",
            "feed", "wp-content", "wp-includes", "wp-json",
            "cdn-cgi", "mailto", "#"
        ]):
            return
        # Must not be the category page itself
        if parsed.path.rstrip("/") == cat_path:
            return
        # Must look like an article slug (single path segment, no subdirectory)
        segments = [s for s in path.split("/") if s]
        if len(segments) != 1:
            return
        if href not in seen:
            seen.add(href)
            links.append(href)

    # ── Strategy 1: article title links (most reliable) ──────────────────────
    # WordPress uses h2.entry-title > a for article titles in listings
    for sel in ["h2.entry-title a", "h1.entry-title a",
                ".entry-title a", ".post-title a",
                "h2 > a[rel='bookmark']", "a[rel='bookmark']"]:
        for a in pg.select(sel):
            add(a.get("href", ""))

    # ── Strategy 2: "Read More" links ─────────────────────────────────────────
    for a in pg.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if text in ("read more »", "read more", "read more»", "continue reading"):
            add(a["href"])

    # If nothing found via targeted selectors, warn rather than fall back broadly
    if not links:
        print(f"    ⚠  No entry-title links found on this page — check page structure")

    return links


def get_next_page_url(pg: BeautifulSoup, current_url: str) -> "str | None":
    """
    Find next page URL from WordPress numbered pagination.
    Hellenic uses numbered pages like: « First ... 13 14 15 16 17
    Strategy: find 'Page X of Y' text, if X < Y construct /page/X+1/ URL.
    """
    # Method 1: rel="next" (most reliable if present)
    next_link = pg.find("a", rel="next")
    if next_link:
        href = next_link.get("href", "")
        if href:
            return urljoin(BASE_URL, href) if not href.startswith("http") else href

    # Method 2: detect "Page X of Y" and build next URL
    page_text = pg.get_text()
    m = re.search(r"Page\s+(\d+)\s+of\s+(\d+)", page_text)
    if m:
        cur_page = int(m.group(1))
        total    = int(m.group(2))
        if cur_page < total:
            # Build next page URL from current
            # Strip existing /page/N/ if present, add /page/N+1/
            base = re.sub(r"/page/\d+/?$", "", current_url.rstrip("/"))
            return f"{base}/page/{cur_page + 1}/"

    # Method 3: find the highest linked page number and see if there's one higher
    current_page_num = None
    m2 = re.search(r"/page/(\d+)/?$", current_url)
    if m2:
        current_page_num = int(m2.group(1))
    else:
        current_page_num = 1  # first page has no /page/N/

    # Find all page number links
    page_nums = []
    for a in pg.find_all("a", href=True):
        pm = re.search(r"/page/(\d+)/?$", a["href"])
        if pm:
            page_nums.append(int(pm.group(1)))

    if page_nums:
        max_linked = max(page_nums)
        if current_page_num < max_linked:
            base = re.sub(r"/page/\d+/?$", "", current_url.rstrip("/"))
            return f"{base}/page/{current_page_num + 1}/"

    return None


def collect_category_urls(driver, cat_name: str, cat_url: str,
                           year_filter: "int | None") -> list:
    """Walk all listing pages for a category, return article URLs."""
    all_links = []
    seen      = set()
    page_url  = cat_url
    page_num  = 1

    while page_url:
        print(f"    📄 Page {page_num}: ...{page_url[-50:]}")
        pg = fetch_soup(driver, page_url)
        if pg is None:
            print(f"    ✗ Failed — stopping")
            break

        links = get_article_links(pg, cat_url)
        added = 0
        for lnk in links:
            if lnk not in seen:
                seen.add(lnk)
                all_links.append(lnk)
                added += 1

        print(f"       +{added} links  (total {len(all_links)})")

        nxt = get_next_page_url(pg, page_url)
        if nxt:
            page_url = nxt
            page_num += 1
            time.sleep(PAGE_DELAY)
        else:
            print(f"    ✓ End of pages")
            break

    # Year filter — only works for URLs containing /YYYY/ or date in slug
    if year_filter:
        filtered = []
        yr_str   = str(year_filter)
        for u in all_links:
            # Try to detect year from URL (e.g. april-08-2026 → 2026)
            if yr_str in u:
                filtered.append(u)
        return filtered

    return all_links


# ── Asset downloading ─────────────────────────────────────────────────────────

def download_file(url: str, dest: Path) -> bool:
    """Download a binary file (image or PDF)."""
    if dest.exists() and dest.stat().st_size > 500:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = dl_session.get(url, timeout=30, stream=True)
        r.raise_for_status()
        dest.write_bytes(r.content)
        time.sleep(ASSET_DELAY)
        return True
    except Exception as e:
        print(f"    ⚠  Asset download failed: {url[-60:]}  {e}")
        return False


# ── Article extraction ────────────────────────────────────────────────────────

HTML_CSS = """
*, *::before, *::after { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Georgia, serif;
    font-size: 15px; line-height: 1.75; color: #1a1a1a;
    max-width: 900px; margin: 0 auto; padding: 28px 20px; background: #fff;
}
h1 { font-size: 1.6em; color: #003366; margin: 0 0 8px; line-height: 1.3; }
h2 { font-size: 1.2em; color: #003366; margin: 20px 0 6px; }
h3 { font-size: 1.05em; color: #003366; margin: 14px 0 4px; }
p  { margin: 0 0 12px; }
a  { color: #003366; }
img { max-width: 100%; height: auto; margin: 12px 0; border: 1px solid #ddd;
      border-radius: 3px; display: block; }
.meta { font-size: 0.82em; color: #555; margin: 6px 0 18px;
        padding: 6px 12px; background: #f0f4f8;
        border-left: 3px solid #003366; border-radius: 2px; }
.pdf-link { display: inline-block; margin: 12px 0; padding: 8px 16px;
            background: #003366; color: #fff !important;
            text-decoration: none; border-radius: 4px; font-size: 0.9em; }
hr { border: none; border-top: 1px solid #dce3ea; margin: 18px 0; }
table { width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 0.88em; }
th { background: #003366; color: #fff; padding: 7px 10px; text-align: left; }
td { padding: 6px 10px; border-bottom: 1px solid #dde3ea; }
tr:nth-child(even) td { background: #f4f7fc; }
blockquote { border-left: 3px solid #ccc; margin: 14px 0;
             padding: 4px 14px; color: #444; }
"""


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:60].strip("-")


def sanitize(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", s)


def parse_date(pg: BeautifulSoup, url: str) -> "datetime | None":
    # Try structured date elements
    for sel in ["time[datetime]", ".entry-date", ".post-date",
                "[class*='date']", "[class*='Date']", "time"]:
        el = pg.select_one(sel)
        if el:
            raw = el.get("datetime") or el.get_text(strip=True)
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y",
                        "%d %B %Y", "%d %b %Y", "%Y-%m-%dT%H:%M:%S%z",
                        "%d/%m/%Y %H:%M"]:
                try:
                    return datetime.strptime(raw[:10], fmt[:len(raw[:10])])
                except ValueError:
                    pass
            # Try regex on the text
            m = re.search(r"(\d{2})[/\-](\d{2})[/\-](\d{4})", raw)
            if m:
                try:
                    return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                except ValueError:
                    pass

    # Fallback: look for dd/mm/yyyy anywhere in article header
    header_text = ""
    for sel in ["header", ".entry-header", "h1", ".post-header"]:
        el = pg.select_one(sel)
        if el:
            header_text += el.get_text()
    m = re.search(r"(\d{2})[/\-](\d{2})[/\-](\d{4})", header_text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def extract_and_save(pg: BeautifulSoup, url: str, cat_name: str,
                     dry_run: bool) -> bool:
    # ── Title ────────────────────────────────────────────────────────────────
    h1 = pg.find("h1")
    title = h1.get_text(strip=True) if h1 else url.rstrip("/").split("/")[-1]

    # ── Date ─────────────────────────────────────────────────────────────────
    date_obj = parse_date(pg, url)
    if date_obj:
        date_str = date_obj.strftime("%d %B %Y")
        year     = date_obj.year
        ds       = date_obj.strftime("%Y-%m-%d")
    else:
        year, date_str, ds = "unknown", "", "0000-00-00"

    slug  = slugify(url.rstrip("/").split("/")[-1])
    fname = sanitize(f"{ds}_{slug}")
    dest_html = OUTPUT_ROOT / cat_name / str(year) / f"{fname}.html"
    dest_pdf_dir = OUTPUT_ROOT / cat_name / "pdfs"
    dest_img_dir = OUTPUT_ROOT / cat_name / str(year)

    # Skip check
    if dest_html.exists() and dest_html.stat().st_size > 800:
        print(f"    ✓ skip: {dest_html.name}")
        return True

    if dry_run:
        print(f"    [DRY RUN] {date_str}  {title[:55]}  → {dest_html.name}")
        return True

    # ── Body content ─────────────────────────────────────────────────────────
    body = None
    for sel in [".entry-content", ".post-content", "[class*='entry-content']",
                "article", ".post-body", "main .content", ".article-content"]:
        el = pg.select_one(sel)
        if el and len(el.get_text(strip=True)) > 100:
            body = el
            break

    if body is None:
        # Fallback: largest content block
        best, best_len = None, 0
        for div in pg.find_all(["div", "article"]):
            t = div.get_text(strip=True)
            if 200 < len(t) < 100000 and len(t) > best_len:
                best, best_len = div, len(t)
        body = best

    pdf_links_html = ""
    img_count = 0

    if body:
        # Remove clutter
        for tag in body.find_all(["script", "style", "noscript", "aside",
                                   "nav", ".sharedaddy", ".jp-relatedposts",
                                   ".wpcnt", "[class*='share']",
                                   "[class*='related']", "[class*='ad']"]):
            if hasattr(tag, 'decompose'):
                tag.decompose()

        # ── PDF links: download + mark in HTML ───────────────────────────────
        pdf_links = []
        for a in body.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = urljoin(BASE_URL, href)
            if href.lower().endswith(".pdf") or "download" in href.lower():
                pdf_links.append(href)
                # Replace link tag with a styled anchor
                a["class"] = "pdf-link"
                a["href"]  = href
                a.string   = f"📄 Download PDF: {href.split('/')[-1]}"

        # Download PDFs
        for pdf_url in pdf_links:
            pdf_name = sanitize(f"{ds}_{pdf_url.split('/')[-1]}")
            if not pdf_name.endswith(".pdf"):
                pdf_name += ".pdf"
            pdf_dest = dest_pdf_dir / pdf_name
            if download_file(pdf_url, pdf_dest):
                print(f"    📄 PDF: {pdf_name}")
            pdf_links_html += (
                f'<p><a class="pdf-link" href="../../pdfs/{pdf_name}">'
                f'📄 {pdf_name}</a></p>\n'
            )

        # ── Images: download + repoint src ───────────────────────────────────
        for img in body.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            if not src or "data:image" in src:
                continue
            if not src.startswith("http"):
                src = urljoin(BASE_URL, src)
            # Skip tiny icons/logos (usually <5KB, indicated by known paths)
            if any(x in src for x in ["logo", "icon", "avatar", "sponsor",
                                        "pixel", "tracking", "1x1"]):
                continue

            img_count += 1
            ext  = Path(urlparse(src).path).suffix or ".jpg"
            if len(ext) > 5: ext = ".jpg"
            img_fname = sanitize(f"{fname}_img{img_count}{ext}")
            img_dest  = dest_img_dir / img_fname

            if download_file(src, img_dest):
                img["src"] = img_fname   # relative path
                img.attrs.pop("data-src", None)
                img.attrs.pop("data-lazy-src", None)
                img.attrs.pop("srcset", None)
                img.attrs.pop("sizes", None)

        # Strip class/id/style for cleaner output
        for tag in body.find_all(True):
            for attr in ["class", "id", "style", "onclick", "onload",
                          "data-src", "srcset", "sizes"]:
                tag.attrs.pop(attr, None)

        body_html = str(body)
    else:
        body_html = "<p><em>Content not extracted — visit original URL.</em></p>"

    # ── Build final HTML ──────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
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
    {date_str} &nbsp;|&nbsp; {cat_name.replace('_',' ').title()}
    &nbsp;|&nbsp; <a href="{url}">{url}</a>
  </div>
  <hr>
  {body_html}
  {pdf_links_html}
</body>
</html>"""

    dest_html.parent.mkdir(parents=True, exist_ok=True)
    dest_html.write_text(html, encoding="utf-8")
    kb = dest_html.stat().st_size // 1024
    print(f"    ↓ {dest_html.name}  ({kb} KB)"
          + (f"  [{img_count} imgs]" if img_count else "")
          + (f"  [PDF]" if pdf_links else ""))
    return True


# ── Main runner ───────────────────────────────────────────────────────────────

def run_category(driver, cat_name: str, cat_url: str,
                 dry_run: bool, year_filter: "int | None"):
    print(f"\n  {'─'*60}")
    print(f"  📂 {cat_name.upper()}  →  {cat_url}")
    print(f"  {'─'*60}")

    urls = collect_category_urls(driver, cat_name, cat_url, year_filter)
    print(f"\n  ✅ {len(urls)} articles found for {cat_name}")

    ok = fail = 0
    for i, url in enumerate(urls, 1):
        print(f"\n  [{i}/{len(urls)}] {url.rstrip('/').split('/')[-1][:60]}")
        time.sleep(ARTICLE_DELAY)
        pg = fetch_soup(driver, url, wait=2.5)
        if pg is None:
            print(f"    ✗ Failed to fetch")
            fail += 1
            continue
        if extract_and_save(pg, url, cat_name, dry_run):
            ok += 1
        else:
            fail += 1

    print(f"\n  {cat_name}: ✓ {ok} saved   ✗ {fail} failed")
    return ok, fail


def run(categories: list, dry_run: bool, year_filter: "int | None",
        headed: bool):
    print(f"\n{'═'*64}")
    print(f"  Hellenic Shipping News Scraper")
    print(f"  Categories : {', '.join(categories)}")
    print(f"  Mode       : {'DRY RUN' if dry_run else 'DOWNLOAD'}")
    if year_filter:
        print(f"  Year       : {year_filter}")
    print(f"{'═'*64}")

    total_ok = total_fail = 0
    for cat_name in categories:
        cat_url = CATEGORIES[cat_name]
        driver  = get_driver(headed=headed)
        try:
            ok, fail = run_category(driver, cat_name, cat_url,
                                     dry_run, year_filter)
            total_ok   += ok
            total_fail += fail
        finally:
            driver.quit()

    print(f"\n{'═'*64}")
    print(f"  TOTAL  ✓ {total_ok} saved   ✗ {total_fail} failed")
    print(f"{'═'*64}\n")


def main():
    p = argparse.ArgumentParser(description="Hellenic Shipping News Scraper")
    p.add_argument("--category",
                   choices=list(CATEGORIES.keys()) + ["all"],
                   default="all")
    p.add_argument("--dry-run",  action="store_true")
    p.add_argument("--year",     type=int, default=None)
    p.add_argument("--headed",   action="store_true")
    args = p.parse_args()

    cats = list(CATEGORIES.keys()) if args.category == "all" else [args.category]
    run(cats, args.dry_run, args.year, args.headed)


if __name__ == "__main__":
    main()
