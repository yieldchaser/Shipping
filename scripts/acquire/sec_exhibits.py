#!/usr/bin/env python3
"""
scripts/acquire/sec_exhibits.py

Fetch the EX-99.x exhibits (press releases, quarterly results, fleet updates,
presentation text) of SEC 6-K and 8-K filings and append them, converted to
Markdown, to the filing's corpus file.

A 6-K / 8-K main document is usually only a cover page; the content lives in its
EX-99.x exhibits. Exhibits are discovered from the filing index page
(https://www.sec.gov/Archives/edgar/data/{cik}/{accession-no-dashes}/{accession}-index.htm),
selected by exhibit type, downloaded as raw HTML into a gitignored cache and
converted with the same converter as the main document.

SEC fair-access policy: the declared SEC_IDENTITY user agent, at most ~8
requests per second, retry with exponential backoff on 429 / 503 (and other
transient failures). Raw downloads are cached under data/raw/sec_exhibits_cache/
(gitignored) so reruns issue no network requests.
"""

import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

SEC_IDENTITY = "Antigravity Research research@shippinganalytics.com"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXHIBIT_CACHE_DIR = REPO_ROOT / "data" / "raw" / "sec_exhibits_cache"  # data/raw/ is gitignored

SEC_ARCHIVES = "https://www.sec.gov"
MAX_REQUESTS_PER_SECOND = 8.0
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 6

# Only these exhibit types carry readable disclosure; everything else (EX-101 XBRL,
# EX-104 cover page, EX-23 consents, EX-24, graphics, ...) is skipped.
EXHIBIT_TYPE_RE = re.compile(r"^EX-99(\.\d+)?$", re.IGNORECASE)
TEXT_EXTENSIONS = (".htm", ".html", ".txt")
FORMS_WITH_EXHIBITS = ("6-K", "8-K")


@dataclass(frozen=True)
class ExhibitRef:
    """One document row of a filing index page."""
    seq: str
    description: str
    filename: str
    url: str
    doc_type: str


class SecClient:
    """Rate-limited, retrying, disk-caching HTTP client for sec.gov."""

    def __init__(
        self,
        cache_dir: Path = EXHIBIT_CACHE_DIR,
        user_agent: str = SEC_IDENTITY,
        max_per_second: float = MAX_REQUESTS_PER_SECOND,
        session: Optional[requests.Session] = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.cache_dir = Path(cache_dir)
        self.min_interval = 1.0 / max_per_second
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_request = 0.0
        self.network_requests = 0

    def _cache_path(self, url: str) -> Path:
        rel = url.split("/Archives/edgar/data/", 1)[-1]
        return self.cache_dir / rel

    def _throttle(self) -> None:
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                self._sleep(wait)
            self._last_request = time.monotonic()

    def get_bytes(self, url: str) -> bytes:
        """Return the body of `url`, from the cache when present."""
        cache_path = self._cache_path(url)
        if cache_path.exists():
            return cache_path.read_bytes()

        last_error = "no attempt made"
        for attempt in range(MAX_ATTEMPTS):
            self._throttle()
            self.network_requests += 1
            try:
                resp = self.session.get(url, timeout=60)
            except requests.RequestException as e:
                last_error = f"{type(e).__name__}: {e}"
                self._sleep(min(2 ** attempt, 60))
                continue
            if resp.status_code == 200:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
                tmp.write_bytes(resp.content)
                try:
                    tmp.replace(cache_path)
                except OSError:
                    # another process cached the same document first (Windows refuses to replace an open file)
                    tmp.unlink(missing_ok=True)
                    if not cache_path.exists():
                        raise
                return resp.content
            if resp.status_code in RETRY_STATUSES:
                retry_after = resp.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 2 ** attempt
                last_error = f"HTTP {resp.status_code}"
                self._sleep(min(delay, 120))
                continue
            raise SecFetchError(f"HTTP {resp.status_code} for {url}")
        raise SecFetchError(f"giving up on {url} after {MAX_ATTEMPTS} attempts ({last_error})")

    def get_text(self, url: str) -> str:
        return decode_html_bytes(self.get_bytes(url))


class SecFetchError(Exception):
    """Raised when a SEC URL cannot be retrieved."""


def decode_html_bytes(raw: bytes) -> str:
    """Decode filing HTML: UTF-8 (with BOM) first, then cp1252, never failing."""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


SGML_WRAPPER_RE = re.compile(r"^\s*<DOCUMENT>.*?<TEXT>", re.IGNORECASE | re.DOTALL)
SGML_TRAILER_RE = re.compile(r"</TEXT>\s*(</DOCUMENT>\s*)?$", re.IGNORECASE)


def strip_sgml_wrapper(html: str) -> str:
    """Remove the <DOCUMENT><TYPE>..<TEXT> envelope EDGAR keeps around exhibit documents."""
    html = SGML_WRAPPER_RE.sub("", html, count=1)
    return SGML_TRAILER_RE.sub("", html)


def accession_nodash(accession: str) -> str:
    return accession.replace("-", "")


def index_url(cik: str, accession: str) -> str:
    return f"{SEC_ARCHIVES}/Archives/edgar/data/{int(cik)}/{accession_nodash(accession)}/{accession}-index.htm"


def parse_index_html(html: str) -> List[ExhibitRef]:
    """Parse the 'Document Format Files' table of a filing index page."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="tableFile", summary="Document Format Files")
    refs: List[ExhibitRef] = []
    if table is None:
        return refs
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue
        link = cells[2].find("a")
        if link is None or not link.get("href"):
            continue
        href = link["href"]
        if "/ix?doc=" in href:  # inline-XBRL viewer link -> the underlying document
            href = href.split("/ix?doc=", 1)[1]
        description = " ".join(cells[1].get_text(" ", strip=True).split())
        # Some filer agents put the description in the Type cell too ("EX-99.1 CHARTER")
        type_parts = " ".join(cells[3].get_text(" ", strip=True).split()).split(" ", 1)
        doc_type = type_parts[0]
        if not description and len(type_parts) > 1:
            description = type_parts[1]
        refs.append(ExhibitRef(
            seq=cells[0].get_text(strip=True),
            description=description,
            filename=link.get_text(strip=True),
            url=href if href.startswith("http") else SEC_ARCHIVES + href,
            doc_type=doc_type,
        ))
    return refs


def select_exhibits(refs: List[ExhibitRef]) -> List[ExhibitRef]:
    """Keep EX-99.x documents that are HTML/text, in index order."""
    return [
        r for r in refs
        if EXHIBIT_TYPE_RE.match(r.doc_type) and r.filename.lower().endswith(TEXT_EXTENSIONS)
    ]


def exhibit_number(doc_type: str) -> str:
    """'EX-99.1' -> '99.1'."""
    return doc_type.upper().replace("EX-", "", 1)


def exhibit_heading(ref: ExhibitRef) -> str:
    number = exhibit_number(ref.doc_type)
    desc = ref.description.strip()
    if desc and desc.upper() != ref.doc_type.upper():
        return f"## Exhibit {number} — {desc}"
    return f"## Exhibit {number}"


def default_converter(raw_html: str) -> str:
    """The same HTML -> Markdown converter used for the main document."""
    try:
        from scripts.acquire.fetch_sec_filings import convert_html_to_markdown
    except ImportError:
        from fetch_sec_filings import convert_html_to_markdown
    md, _method = convert_html_to_markdown(raw_html)
    return md or plain_text_fallback(raw_html)


def plain_text_fallback(raw_html: str) -> str:
    """Plain text of very short exhibits that fall under the converter's 100-character floor."""
    soup = BeautifulSoup(raw_html, "html.parser")
    lines = [" ".join(line.split()) for line in soup.get_text("\n").splitlines()]
    return "\n\n".join(line for line in lines if line)


def build_exhibit_sections(
    client: SecClient,
    cik: str,
    accession: str,
    converter: Optional[Callable[[str], str]] = None,
) -> List[Tuple[str, str]]:
    """
    Download and convert every EX-99.x exhibit of a filing.
    Returns [(doc_type, section_markdown)] where section_markdown starts with the
    "## Exhibit 99.x" heading. Exhibits that convert to nothing are skipped.
    Raises SecFetchError if the index or an exhibit cannot be retrieved.
    """
    converter = converter or default_converter
    refs = select_exhibits(parse_index_html(client.get_text(index_url(cik, accession))))
    sections: List[Tuple[str, str]] = []
    for ref in refs:
        body = converter(strip_sgml_wrapper(client.get_text(ref.url))).strip()
        if not body:
            continue
        sections.append((ref.doc_type.upper(), f"{exhibit_heading(ref)}\n\n{body}"))
    return sections


FRONTMATTER_END = "\n---\n"


def has_exhibits(md_text: str) -> bool:
    """True if the frontmatter already carries an exhibits key."""
    if not md_text.startswith("---\n") and not md_text.startswith("---\r\n"):
        return False
    end = md_text.find("\n---", 3)
    header = md_text[: end if end != -1 else 0]
    return re.search(r"^exhibits:", header, re.MULTILINE) is not None


def append_exhibits(md_text: str, sections: List[Tuple[str, str]]) -> str:
    """
    Return md_text with the exhibit sections appended after the main document and an
    `exhibits: [EX-99.1, ...]` key added as the last frontmatter key. The existing
    frontmatter and body are otherwise unchanged. A no-op if sections is empty or the
    file already has an exhibits key.
    """
    if not sections or has_exhibits(md_text):
        return md_text
    crlf = "\r\n" in md_text
    text = md_text.replace("\r\n", "\n") if crlf else md_text
    if not text.startswith("---\n"):
        raise ValueError("markdown has no YAML frontmatter")
    end = text.find(FRONTMATTER_END, 3)
    if end == -1:
        raise ValueError("unterminated YAML frontmatter")
    types = ", ".join(t for t, _ in sections)
    head = text[:end + 1] + f"exhibits: [{types}]\n"
    body = text[end + 1:]  # starts at the closing '---'
    body = body.rstrip("\n") + "\n\n" + "\n\n".join(s for _, s in sections) + "\n"
    out = head + body
    return out.replace("\n", "\r\n") if crlf else out
