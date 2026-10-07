"""Markdown normalisation (banners, running headers, boilerplate, table spacing) and frontmatter."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import yaml

IMAGE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")
PAGE_BANNER_RE = re.compile(r"(?i)^\s*(#+\s*)?(\*\*)?page\s+\d+(\s+of\s+\d+)?(\*\*)?\s*$")
MD_PREFIX_RE = re.compile(r"^\s*(#+\s+|\*\*|__)+|(\*\*|__)\s*$")


def _plain(line: str) -> str:
    return MD_PREFIX_RE.sub("", line).strip()


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def clean_markdown(md: str, profile: dict[str, Any]) -> str:
    strip_res = [re.compile(p) for p in profile.get("strip_line_patterns", [])]
    boiler_res = [re.compile(p) for p in profile.get("boilerplate_patterns", [])]
    blocks = [b for b in re.split(r"\n\s*\n", md.replace("\r\n", "\n")) if b.strip()]

    # running headers / footers: short non-table blocks that repeat verbatim
    counts = Counter(b.strip() for b in blocks if len(b.strip()) < 90 and not _is_table_line(b))
    repeated = {t for t, n in counts.items() if n >= 2 and not t.startswith("#")}

    out_blocks: list[str] = []
    for block in blocks:
        text = block.strip()
        if text in repeated:
            continue
        if any(r.search(text) for r in boiler_res):
            continue
        kept = []
        for line in text.split("\n"):
            if not _is_table_line(line):
                if IMAGE_RE.match(line) or PAGE_BANNER_RE.match(line):
                    continue
                plain = _plain(line)
                if plain and any(r.search(plain) for r in strip_res):
                    continue
                if not plain or re.fullmatch(r"[-*_]{3,}", plain) or not re.search(r"[A-Za-z0-9]", plain):
                    continue                      # empty, rules, or stray punctuation glyphs (a lone backtick)
            # a heading that starts lower-case is a mis-detected sentence fragment: demote to text
            m = re.match(r"^#+\s+([a-z].*)$", line)
            kept.append(m.group(1).rstrip() if m else line.rstrip())
        if kept:
            out_blocks.append("\n".join(kept))
    return ensure_table_spacing("\n\n".join(out_blocks)) + "\n"


def ensure_table_spacing(md: str) -> str:
    """Exactly one blank line before and after every GFM table; no other blank-line runs."""
    lines = md.split("\n")
    out: list[str] = []
    in_table = False
    for line in lines:
        tbl = _is_table_line(line)
        if tbl and not in_table:
            while out and out[-1] == "":
                out.pop()
            if out:
                out.append("")
        elif in_table and not tbl:
            if line.strip():
                out.append("")
        if not tbl and not line.strip():
            if out and out[-1] == "":
                continue
        out.append(line)
        in_table = tbl
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build_frontmatter(meta: dict[str, Any]) -> str:
    ordered = {k: meta.get(k) for k in (
        "title", "publisher", "source", "issue_date", "document_header_date", "issue_date_conflict", "year", "source_file", "source_sha256",
        "pages_total", "pages_parsed", "parser", "parsed_at")}
    return "---\n" + yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, width=1000) + "---\n\n"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------- HTML tables -> GFM
from html.parser import HTMLParser  # noqa: E402

_EMPTY = {"", "-", "\u2013", "\u2014"}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[dict[str, Any]]] = []
        self._cell: dict[str, Any] | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            if not self.rows:
                self.rows.append([])
            self._cell = {"text": "", "rowspan": int(a.get("rowspan") or 1), "colspan": int(a.get("colspan") or 1)}
        elif tag == "br" and self._cell is not None:
            self._cell["text"] += " "

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._cell["text"] = re.sub(r"\s+", " ", self._cell["text"]).strip()
            self.rows[-1].append(self._cell)
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text"] += data


def _html_table_to_gfm(html: str) -> str:
    parser = _TableParser()
    parser.feed(html)
    grid: list[list[str]] = []
    spans: list[list[bool]] = []   # True where the cell comes from a rowspan (value repeated)
    pending: dict[tuple[int, int], tuple[str, bool]] = {}
    for r, row in enumerate(parser.rows):
        out: list[str] = []
        flag: list[bool] = []
        c = 0
        cells = list(row)
        while cells or any(k[0] == r and k[1] >= c for k in pending):
            if (r, c) in pending:
                text, _ = pending.pop((r, c))
                out.append(text)
                flag.append(True)
                c += 1
                continue
            if not cells:
                c += 1
                out.append("")
                flag.append(False)
                continue
            cell = cells.pop(0)
            for dc in range(cell["colspan"]):
                out.append(cell["text"] if dc == 0 else "")
                flag.append(cell["rowspan"] > 1)  # the originating row of a spanning cell is shared too
                for dr in range(1, cell["rowspan"]):
                    pending[(r + dr, c + dc)] = (cell["text"] if dc == 0 else "", True)
            c += cell["colspan"]
        grid.append(out)
        spans.append(flag)
    if not grid:
        return ""
    width = max(len(r) for r in grid)
    grid = [r + [""] * (width - len(r)) for r in grid]
    spans = [f + [False] * (width - len(f)) for f in spans]
    header, body, body_spans = grid[0], grid[1:], spans[1:]
    # a cell spanning several vessel rows in the Price/Buyer columns is an en-bloc deal
    price = next((i for i, h in enumerate(header) if h.strip().lower() == "price"), None)
    if price is not None:
        for ri, row in enumerate(body):
            shared = any(body_spans[ri][ci] for ci, h in enumerate(header) if h.strip().lower() in ("price", "buyer"))
            if shared and "en bloc" not in row[price].lower():
                row[price] = (row[price] + " (en bloc)").strip()
    if body and all(x.strip() in _EMPTY for r in body for x in r):
        body = [["No reported sales"] + [""] * (width - 1)]
    esc = lambda s: s.replace("|", "\\|")  # noqa: E731
    lines = ["| " + " | ".join(esc(h) for h in header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(esc(x) for x in r) + " |" for r in body]
    return "\n".join(lines)


def html_tables_to_gfm(md: str) -> str:
    """Convert <table> blocks (LlamaParse v2 output) to GFM; rowspans are repeated per row."""
    return re.sub(r"<table\b.*?</table>", lambda m: "\n\n" + _html_table_to_gfm(m.group(0)) + "\n\n", md,
                  flags=re.S | re.I)


def nest_headings_md(md: str) -> str:
    """After cleaning: a heading directly followed by another heading of the same or a shallower level
    (a section title and its first table title, e.g. "Demolition" / "Bulk Carriers - GCs") would leave the
    first one empty, so the second is pushed one level below it. The table titles that follow in the same
    section (headings directly followed by a table, until the next text paragraph) are pushed with it, so
    sibling tables keep one level. Done on the final text so removed letterhead lines cannot matter."""
    blocks = re.split(r"\n\s*\n", md.strip())

    def level_of(b: str) -> int:
        m = re.match(r"(#{1,6}) ", b)
        return len(m.group(1)) if m and "\n" not in b.strip() else 0

    out: list[str] = []
    prev_level = 0
    child_level = 0            # >0 while the tables of a section whose first title was pushed are being nested
    section_level = 0
    for i, b in enumerate(blocks):
        lvl = level_of(b)
        nxt = blocks[i + 1] if i + 1 < len(blocks) else ""
        is_table_title = lvl > 0 and nxt.lstrip().startswith("|")
        if lvl and prev_level and lvl <= prev_level:
            section_level, child_level = prev_level, min(prev_level + 1, 6)
            b = "#" * child_level + b[lvl:]
            lvl = child_level
        elif lvl and is_table_title and child_level and lvl <= section_level:
            b = "#" * child_level + b[lvl:]
            lvl = child_level
        elif child_level and not b.lstrip().startswith(("|", "#")):
            child_level = 0    # a text paragraph ends the section
        elif lvl and not is_table_title and lvl <= section_level:
            child_level = 0    # a new section heading
        prev_level = lvl
        out.append(b)
    return "\n\n".join(out) + "\n"
