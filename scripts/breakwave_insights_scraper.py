"""
Breakwave Advisors Insights Scraper
==================================
Scrapes article pages from https://www.breakwaveadvisors.com/insights,
stores clean self-contained HTML by year, and downloads article images
plus linked assets into repo-local archive folders.

Output:
  reports/breakwave/{year}/{date}_{slug}.html
  reports/breakwave/{year}/assets/{asset}.{ext}
  reports/breakwave/pdfs/{asset}.pdf
"""

from __future__ import annotations

import argparse
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from source_archive_utils_v2 import (
    REPORTS_ROOT,
    asset_kind,
    clean_node_text,
    configure_utf8_stdio,
    deterministic_asset_filename,
    humanize_slug,
    infer_asset_extension,
    is_mirrorable_asset,
    make_soup,
    minimum_asset_size,
    normalize_asset_url,
    remove_empty_tags,
    repair_text,
    relative_asset_href,
    sanitize_filename,
    slugify,
    standard_archive_html,
    strip_attrs,
    unwrap_redundant_containers,
)


BASE_URL = "https://www.breakwaveadvisors.com"
START_URL = f"{BASE_URL}/insights"
OUTPUT_ROOT = REPORTS_ROOT / "breakwave"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": BASE_URL + "/",
}

PAGE_DELAY = 1.5
ARTICLE_DELAY = 1.2
IMAGE_DELAY = 0.5

session = requests.Session()
session.headers.update(HEADERS)
configure_utf8_stdio()


def get(url: str, retries: int = 3, *, stream: bool = False):
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=30, stream=stream)
            response.raise_for_status()
            return response
        except Exception as exc:
            print(f"    ! [{attempt + 1}/{retries}] {url[-80:]}  {exc}")
            if attempt < retries - 1:
                time.sleep(3)
    return None


def soup(url: str) -> BeautifulSoup | None:
    response = get(url)
    return make_soup(response.text) if response else None


def parse_breakwave_date(raw: str) -> datetime | None:
    raw = repair_text(raw)
    for fmt in (
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def first_meaningful_text(body: BeautifulSoup | None) -> str:
    if body is None:
        return ""
    for tag in body.find_all(["h1", "h2", "h3", "strong", "p", "li"], limit=40):
        text = repair_text(tag.get_text(" ", strip=True))
        if len(text) >= 16:
            return text[:180]
    return ""


def find_title(page_soup: BeautifulSoup, body: BeautifulSoup | None, url: str) -> str:
    bad_titles = {"", "breakwave advisors", "signal ocean", "insights"}
    selectors = [
        "article h1",
        ".entry-title",
        "main h1",
        "meta[property='og:title']",
        "meta[name='twitter:title']",
        "title",
        "h1",
    ]
    for selector in selectors:
        element = page_soup.select_one(selector)
        if element is None:
            continue
        if element.name == "meta":
            text = repair_text(element.get("content"))
        else:
            text = repair_text(element.get_text(" ", strip=True))
            if element.name == "title":
                text = text.replace(" - Breakwave Advisors", "").replace(" \u2014 Breakwave Advisors", "").strip()
        if text and text.lower() not in bad_titles:
            return text

    fallback = first_meaningful_text(body)
    if fallback:
        return fallback
    return humanize_slug(url.rstrip("/").split("/")[-1]) or "Breakwave Insights Article"


def is_article_url(href: str) -> bool:
    if not href:
        return False
    parsed = urlparse(href)
    path = parsed.path.rstrip("/")
    if path == "/insights":
        return False
    if parsed.query:
        return False
    if "/insights/tag/" in path:
        return False
    return path.count("/") >= 2


def extract_article_links(page_soup: BeautifulSoup) -> list[str]:
    links: set[str] = set()
    for anchor in page_soup.find_all("a", href=True):
        href = anchor["href"]
        if not href.startswith("http"):
            href = urljoin(BASE_URL, href)
        if "breakwaveadvisors.com/insights/" in href and is_article_url(href):
            links.add(href.split("#")[0])
    return sorted(links)


def get_older_posts_url(page_soup: BeautifulSoup) -> str | None:
    for anchor in page_soup.find_all("a", href=True):
        if "older" in anchor.get_text(strip=True).lower():
            href = anchor["href"]
            return urljoin(BASE_URL, href) if not href.startswith("http") else href
    return None


def collect_all_article_urls(year_filter: int | None = None) -> list[str]:
    all_links: set[str] = set()
    page_url = START_URL
    page_num = 1

    while page_url:
        print(f"  Listing page {page_num}: {page_url[-80:]}")
        page_soup = soup(page_url)
        if page_soup is None:
            print("  x Failed to fetch listing page; stopping")
            break

        links = extract_article_links(page_soup)
        before = len(all_links)
        all_links.update(links)
        print(f"    +{len(all_links) - before} new links  (total {len(all_links)})")

        if year_filter:
            page_years = []
            has_yearless = False
            for link in links:
                match = re.search(r"/insights/(\d{4})/", link)
                if match:
                    page_years.append(int(match.group(1)))
                else:
                    has_yearless = True
            if page_years and max(page_years) < year_filter and not has_yearless:
                print(f"  Reached pages older than {year_filter}; stopping pagination early")
                break

        older = get_older_posts_url(page_soup)
        if not older or older == page_url:
            print("  No more listing pages")
            break
        page_url = older
        page_num += 1
        time.sleep(PAGE_DELAY)

    if year_filter:
        filtered = []
        for url in all_links:
            match = re.search(r"/insights/(\d{4})/", url)
            if match and int(match.group(1)) == year_filter:
                filtered.append(url)
            elif not match:
                filtered.append(url)
        return sorted(filtered, reverse=True)
    return sorted(all_links, reverse=True)


def mirror_asset(
    *,
    page_url: str,
    raw_url: str,
    base_name: str,
    html_path: Path,
    assets_dir: Path,
    link_text: str = "",
) -> tuple[str, str] | None:
    absolute = normalize_asset_url(page_url, raw_url)
    if not absolute or not is_mirrorable_asset(absolute, link_text):
        return None

    extension = infer_asset_extension(absolute, link_text)
    if not extension:
        return None
    kind_name = asset_kind(extension)
    minimum_size = minimum_asset_size(kind_name)

    response = get(absolute, stream=True)
    if response is None:
        return None

    payload = response.content
    if len(payload) <= minimum_size:
        return None

    assets_dir.mkdir(parents=True, exist_ok=True)
    filename = deterministic_asset_filename(base_name, absolute, payload, extension)
    destination = assets_dir / filename
    if not destination.exists():
        destination.write_bytes(payload)
    time.sleep(IMAGE_DELAY)
    return relative_asset_href(html_path, destination), absolute


def clean_breakwave_body(
    body: BeautifulSoup,
    page_url: str,
    base_name: str,
    html_path: Path,
    assets_dir: Path,
    pdf_dir: Path,
) -> tuple[str, list[str]]:
    fragment = make_soup(f"<section>{str(body)}</section>").section
    if fragment is None:
        return "<p><em>No content extracted - visit the original URL.</em></p>", []

    for tag in fragment.select(
        "script, style, noscript, nav, header, footer, form, button, aside, svg"
    ):
        tag.decompose()

    iframe_notes: list[str] = []
    seen_images: set[str] = set()

    for iframe in list(fragment.find_all("iframe")):
        src = repair_text(iframe.get("src") or "")
        note = fragment.new_tag("div")
        note["class"] = "archive-note"
        mirrored = mirror_asset(
            page_url=page_url,
            raw_url=src,
            base_name=f"{base_name}_embed",
            html_path=html_path,
            assets_dir=assets_dir,
        ) if src else None
        if mirrored:
            local_href, original = mirrored
            link = fragment.new_tag("a", href=local_href)
            link.string = f"Embedded asset: {Path(urlparse(original).path).name or 'download'}"
            note.string = ""
            note.append(link)
            iframe_notes.append(local_href)
        else:
            note.string = f"Embedded chart: {src}" if src else "Embedded chart removed during archiving"
            if src:
                iframe_notes.append(src)
        iframe.replace_with(note)

    for anchor in list(fragment.find_all("a", href=True)):
        href = anchor.get("href", "")
        link_text = repair_text(anchor.get_text(" ", strip=True))
        absolute = normalize_asset_url(page_url, href)
        if not absolute:
            anchor.decompose()
            continue

        extension = infer_asset_extension(absolute, link_text)
        target_dir = pdf_dir if extension == ".pdf" else assets_dir
        mirrored = mirror_asset(
            page_url=page_url,
            raw_url=href,
            base_name=base_name,
            html_path=html_path,
            assets_dir=target_dir,
            link_text=link_text,
        )
        if mirrored:
            local_href, mirrored_url = mirrored
            anchor["href"] = local_href
            if not link_text:
                anchor.string = f"Linked asset: {Path(urlparse(mirrored_url).path).name or 'download'}"
            continue

        anchor["href"] = absolute

    for img in list(fragment.find_all("img")):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            img.decompose()
            continue
        src = normalize_asset_url(page_url, src)
        if not src:
            img.decompose()
            continue
        if src in seen_images:
            img.decompose()
            continue
        seen_images.add(src)
        result = mirror_asset(
            page_url=page_url,
            raw_url=src,
            base_name=f"{base_name}_img",
            html_path=html_path,
            assets_dir=assets_dir,
        )
        if result is None:
            note = fragment.new_tag("div")
            note["class"] = "archive-note"
            note.string = f"Missing image: {src}"
            img.replace_with(note)
            continue
        local_path, _ = result
        img["src"] = local_path
        img["loading"] = "lazy"
        img.attrs.pop("data-src", None)

    clean_node_text(fragment)
    strip_attrs(fragment)
    unwrap_redundant_containers(fragment)
    remove_empty_tags(fragment)
    return str(fragment), iframe_notes


def extract_article(page_soup: BeautifulSoup, url: str) -> dict:
    date_str = ""
    date_obj = None
    for selector in [
        "meta[property='article:published_time']",
        "meta[name='article:published_time']",
        "time[datetime]",
        "time",
        ".entry-dateline",
        "[class*='date']",
        "[class*='Date']",
    ]:
        element = page_soup.select_one(selector)
        if element:
            raw = element.get("content") or element.get("datetime") or element.get_text(strip=True)
            date_obj = parse_breakwave_date(raw)
            if date_obj:
                date_str = date_obj.strftime("%B %d, %Y")
                break

    if not date_obj:
        match = re.search(r"/insights/(\d{4})/(\d{1,2})/(\d{1,2})/", url)
        if match:
            try:
                date_obj = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                date_str = date_obj.strftime("%B %d, %Y")
            except ValueError:
                pass

    source = ""
    for selector in [
        ".entry-header .entry-dateline a",
        ".author-name",
        ".entry-author",
        "meta[name='author']",
        "[class*='author']",
        "[itemprop='author']",
    ]:
        element = page_soup.select_one(selector)
        if element:
            text = repair_text(element.get("content") or element.get_text(strip=True))
            if text and len(text) < 80:
                source = text
                break

    tags = []
    for anchor in page_soup.find_all("a", href=True):
        if "/insights/tag/" in anchor["href"]:
            tag_text = repair_text(anchor.get_text(strip=True))
            if tag_text:
                tags.append(tag_text)

    body = None
    for selector in [
        "article .entry-content",
        ".entry-content",
        ".blog-item-content",
        ".post-content",
        "[class*='entry-content']",
        "[class*='blog-item-content']",
        "article",
        ".sqs-block-content",
        "main",
    ]:
        element = page_soup.select_one(selector)
        if element and len(element.get_text(strip=True)) > 150:
            body = element
            break

    if body is None:
        best = None
        best_len = 0
        for div in page_soup.find_all(["div", "section"]):
            text_len = len(div.get_text(strip=True))
            if best_len < text_len < 50000:
                best = div
                best_len = text_len
        body = best

    return {
        "title": find_title(page_soup, body, url),
        "url": url,
        "date_str": date_str,
        "date_obj": date_obj,
        "source": source or "Breakwave Advisors",
        "tags": tags,
        "body": body,
    }


def build_html(info: dict, dest_html: Path) -> str:
    title = repair_text(info["title"])
    url = info["url"]
    date_str = info["date_str"] or "unknown"
    source = repair_text(info["source"]) or "Breakwave Advisors"
    tags = info["tags"]
    body = info["body"]
    base_name = sanitize_filename(dest_html.stem)
    assets_dir = dest_html.parent / "assets"
    pdf_dir = OUTPUT_ROOT / "pdfs"

    if body:
        body_html, iframe_notes = clean_breakwave_body(
            body,
            url,
            base_name,
            dest_html,
            assets_dir,
            pdf_dir,
        )
    else:
        body_html = "<p><em>No content extracted - visit the original URL.</em></p>"
        iframe_notes = []

    extra_parts = []
    if iframe_notes:
        links = " | ".join(f'<a href="{src}">{repair_text(src)[:60]}</a>' for src in iframe_notes)
        extra_parts.append(f'<div class="archive-note">Embedded charts: {links}</div>')

    return standard_archive_html(
        title=title,
        archive_source="breakwave_insights",
        source_url=url,
        published_date=date_str,
        category="insights",
        body_html=body_html,
        source_label=source,
        tags=tags,
        extra_html="\n".join(extra_parts),
        accent_color="#1a6b3c",
    )


def make_dest(info: dict, slug: str) -> Path:
    year = info["date_obj"].year if info["date_obj"] else "unknown"
    date_stamp = info["date_obj"].strftime("%Y-%m-%d") if info["date_obj"] else "0000-00-00"
    return OUTPUT_ROOT / str(year) / sanitize_filename(f"{date_stamp}_{slug}.html")


def process_article(url: str, dry_run: bool, overwrite: bool) -> bool:
    slug = slugify(url.rstrip("/").split("/")[-1])
    time.sleep(ARTICLE_DELAY)

    page_soup = soup(url)
    if page_soup is None:
        print("    x Failed to fetch article")
        return False

    info = extract_article(page_soup, url)
    dest = make_dest(info, slug)

    if not overwrite and dest.exists() and dest.stat().st_size > 1000:
        print(f"    skip: {dest.name}")
        return True

    if dry_run:
        print(f"    [DRY RUN] {info['date_str'] or 'unknown date'}  {info['title'][:70]} -> {dest.name}")
        return True

    html_doc = build_html(info, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html_doc, encoding="utf-8")
    print(f"    saved: {dest.name}  ({dest.stat().st_size // 1024} KB)")
    return True


def run(dry_run: bool, year_filter: int | None, overwrite: bool) -> None:
    print("\n" + "=" * 64)
    print("  Breakwave Advisors Insights Scraper")
    print(f"  Mode  : {'DRY RUN' if dry_run else 'DOWNLOAD'}")
    if year_filter:
        print(f"  Year  : {year_filter}")
    print("=" * 64 + "\n")

    print("  Collecting article URLs...\n")
    urls = collect_all_article_urls(year_filter)
    print(f"\n  {len(urls)} articles to process\n")
    print("-" * 64)

    ok = fail = 0
    for index, url in enumerate(urls, 1):
        print(f"\n  [{index}/{len(urls)}] {url.split('/')[-1][:70]}")
        if process_article(url, dry_run, overwrite):
            ok += 1
        else:
            fail += 1

    print("\n" + "=" * 64)
    print(f"  DONE  ok={ok}  failed={fail}")
    print("=" * 64 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Breakwave Advisors Insights Scraper")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run(args.dry_run, args.year, args.overwrite)


if __name__ == "__main__":
    main()
