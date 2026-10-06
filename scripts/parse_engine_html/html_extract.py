"""Isolate the article body of a Hellenic VV issue and split it into sectors.

Observed container formats (see the `survey` CLI command):
  chrome_div   archive page, body in <section><div><p>...
  chrome_flat  archive page, body in <section><p>... (no inner div)
  wp_fragment  raw WordPress fragment (no <html>/<section>), title in a leading HTML comment
Sector headers come in four spellings (header_style):
  strong_colon_outside  <strong>Bulkers</strong>: commentary
  strong_colon_inside   <strong>Bulkers:</strong>commentary
  strong_alone          <strong>Bulkers</strong> then the commentary in the next <p>
  plain_colon           "Tankers:commentary" with no <strong>
"""
from __future__ import annotations

import codecs
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup, Comment

from scripts.parse_engine_html.deals import Deal, is_deal_candidate, parse_deal_line

SECTOR_CANON = {
    "bulker": "Bulkers", "bulkers": "Bulkers",
    "tanker": "Tankers", "tankers": "Tankers",
    "container": "Containers", "containers": "Containers",
}
SECTOR_WORD = r"(?:Bulkers?|Tankers?|Containers?|Gas|LNG|LPG|Offshore|Others?)"
PLAIN_HEADER_RE = re.compile(rf"^({SECTOR_WORD})\s*:\s*(.*)$", re.I | re.S)
STRONG_HEADER_RE = re.compile(rf"^\s*({SECTOR_WORD})\s*(:?)\s*$", re.I)
NO_SALES_RE = re.compile(r"^no\b.{0,80}\b(?:sales?|transactions?|deals?)\b", re.I)
TITLE_DATE_RE = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})")
FNAME_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_")
IMG_HREF_RE = re.compile(r"\.(?:jpe?g|png|gif)(?:$|\?)", re.I)
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


_CP1252_STRAY = {0x91: "‘", 0x92: "’", 0x93: "“", 0x94: "”", 0x96: "–", 0x97: "—"}


def _cp1252_stray_bytes(exc: UnicodeDecodeError):
    """A lone cp1252 punctuation byte inside an otherwise UTF-8 page (the 'mojibake dash'): map it, else U+FFFD."""
    out = "".join(_CP1252_STRAY.get(b, "�") for b in exc.object[exc.start:exc.end])
    return out, exc.end


codecs.register_error("vv_cp1252", _cp1252_stray_bytes)


def decode_html(raw: bytes) -> str:
    """Decode robustly: UTF-8 (replacement on failure), then undo cp1252 mojibake of common punctuation."""
    text = raw.decode("utf-8", errors="vv_cp1252")
    for bad, good in (("â€“", "–"), ("â€”", "—"),
                      ("â€™", "’"), ("â€œ", "“"),
                      ("â€\u009d", "”")):
        text = text.replace(bad, good)
    return text.replace("\x96", "–")


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def parse_title_date(title: str | None) -> date | None:
    if not title:
        return None
    m = TITLE_DATE_RE.search(title)
    if not m:
        return None
    mon = MONTHS.get(m.group(1)[:3].lower())
    if not mon:
        return None
    try:
        return date(int(m.group(3)), mon, int(m.group(2)))
    except ValueError:
        return None


@dataclass
class Sector:
    header: str
    name: str
    header_style: str
    commentary: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    deals: list[Deal] = field(default_factory=list)
    unparsed: list[tuple[str, str]] = field(default_factory=list)  # (verbatim line, reason)


@dataclass
class Article:
    source_file: str
    sha256: str
    title: str | None
    issue_date: date | None
    archive_date: str | None
    filename_date: date | None
    container: str
    preamble: list[str] = field(default_factory=list)
    sectors: list[Sector] = field(default_factory=list)
    image_refs: list[str] = field(default_factory=list)
    is_vv_report: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def n_deals(self) -> int:
        return sum(len(s.deals) for s in self.sectors)

    @property
    def n_unparsed(self) -> int:
        return sum(len(s.unparsed) for s in self.sectors)

    @property
    def header_styles(self) -> set[str]:
        return {s.header_style for s in self.sectors}


def _paragraph_text(p) -> str:
    for ins in p.find_all("ins"):
        ins.decompose()
    for c in p.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in p.find_all(["em", "i"]):
        tag.insert_before(" ")
        tag.insert_after(" ")
    for br in p.find_all("br"):
        br.replace_with(" ")
    return norm_text(p.get_text(""))


def _classify_header(p, text: str):
    """Return (header_raw, style, inline_commentary) when the paragraph opens a sector, else None."""
    first = next((c for c in p.children if getattr(c, "name", None) or str(c).strip()), None)
    if first is not None and getattr(first, "name", None) in ("strong", "b"):
        m = STRONG_HEADER_RE.match(norm_text(first.get_text("")))
        if m:
            rest = norm_text("".join(x.get_text("") if hasattr(x, "get_text") else str(x)
                                     for x in first.next_siblings))
            if m.group(2):
                style, inline = "strong_colon_inside", rest
            elif rest.startswith(":"):
                style, inline = "strong_colon_outside", rest[1:].strip()
            elif rest:
                style, inline = "strong_colon_outside", rest
            else:
                style, inline = "strong_alone", ""
            return m.group(1), style, inline
    m = PLAIN_HEADER_RE.match(text)
    if m and not is_deal_candidate(text):
        return m.group(1), "plain_colon", m.group(2).strip()
    return None


def extract_article(path: Path) -> Article:
    raw = path.read_bytes()
    soup = BeautifulSoup(decode_html(raw), "lxml")
    sha = hashlib.sha256(raw).hexdigest()

    title = None
    comment_date = None
    if soup.title and soup.title.string:
        title = norm_text(soup.title.string)
    h1 = soup.find("h1")
    if h1:
        title = norm_text(h1.get_text(" "))
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        m = re.match(r"\s*Title:\s*(.*?)\s*\|\s*Date:\s*(\d{4}-\d{2}-\d{2})", str(c))
        if m:
            title = title or m.group(1)
            comment_date = m.group(2)
            break
    meta = soup.find("meta", attrs={"name": "archive-date"})
    archive_date = meta["content"] if meta is not None and meta.has_attr("content") else comment_date

    section = soup.find("section")
    if section is not None:
        container = "chrome_div" if section.find("div", recursive=False) else "chrome_flat"
        root = section
    else:
        container = "wp_fragment"
        root = soup.body or soup
    m = FNAME_DATE_RE.match(path.name)
    fdate = date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    art = Article(source_file=path.name, sha256=sha, title=title, issue_date=parse_title_date(title),
                  archive_date=archive_date, filename_date=fdate, container=container)
    if art.issue_date is None and comment_date:
        art.issue_date = datetime.strptime(comment_date, "%Y-%m-%d").date()
        art.warnings.append("issue_date taken from fragment comment (title had no parseable date)")
    if not (title or "").lower().startswith("weekly vessel valuations report"):
        art.is_vv_report = False
        return art

    current: Sector | None = None
    for p in root.find_all("p"):
        for img in p.find_all("img"):
            if img.get("src"):
                art.image_refs.append(img["src"])
        for a in p.find_all("a"):
            if a.get("href") and IMG_HREF_RE.search(a["href"]):
                art.image_refs.append(a["href"])
        if p.find_parent("p") is not None:
            continue
        ptxt = _paragraph_text(p)
        if not ptxt or ptxt.startswith("Linked asset:"):
            continue
        hdr = _classify_header(p, ptxt)
        if hdr:
            raw_name, style, inline = hdr
            current = Sector(header=raw_name, name=SECTOR_CANON.get(raw_name.lower(), raw_name.title()),
                             header_style=style)
            art.sectors.append(current)
            if inline:
                _add_text(current, inline)
            continue
        if current is None:
            if is_deal_candidate(ptxt):
                current = Sector(header="", name="(no sector header)", header_style="none")
                art.sectors.append(current)
                art.warnings.append("deal line(s) before any sector header")
                _add_deal(current, ptxt)
            else:
                art.preamble.append(ptxt)
            continue
        _add_text(current, ptxt)
    return art


def _add_deal(sector: Sector, text: str) -> None:
    res = parse_deal_line(text, sector.name)
    if res.deal is not None:
        res.deal.sector = sector.name
        sector.deals.append(res.deal)
    else:
        sector.unparsed.append((text, res.reason))


def _add_text(sector: Sector, text: str) -> None:
    if is_deal_candidate(text):
        _add_deal(sector, text)
    elif NO_SALES_RE.match(text):
        sector.notes.append(text)
    elif not sector.deals and not sector.notes:
        sector.commentary.append(text)
    else:
        sector.notes.append(text)
