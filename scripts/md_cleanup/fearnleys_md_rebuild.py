"""Rebuild the bodies of the Fearnleys research-library MDs (fearnleys-md) from the API content blocks.

Fearnleys publishes these reports through its Hasura API (`custom_report`); each report is a list of
typed content blocks, and data/reports/fearnleys_reports_catalog.json keeps them verbatim. The earlier
renderers knew only heading1/2, fullWidthParagraph, half/full-width charts and page breaks, so they
silently dropped:
  - halfWidthParagraph / thirdWidthParagraph (the FSRU "key developments" columns, regional notes),
  - sourceText (the source line under each chart),
  - fullWidthTable / halfWidthTable (exact data tables, e.g. fleet deliveries/scrapping),
  - thirdWidthChartFromFile (the tanker wrap-up production charts).
They also wrote `file:///C:/Users/...` links into the corpus copies and a generic "Indicator Chart"
caption where the block has no title.

This renders every block type in order. Frontmatter and the title/date header are kept byte-identical;
only the body after the header rule is replaced.

    python scripts/md_cleanup/fearnleys_md_rebuild.py [--apply] [stems...]
"""
from __future__ import annotations

import glob
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "reports" / "fearnleys_reports_catalog.json"
CORPUS = ROOT / "corpus" / "01-brokers" / "fearnleys-md"
EXTRACTED = ROOT / "data" / "extracted" / "md" / "fearnleys-md"
BLOB = re.compile(r"pbrkapp\.blob\.core\.windows\.net/report/([^/]+)/(.+)")


def clean(text):
    text = "".join(ch for ch in (text or "") if not (0xF000 <= ord(ch) <= 0xF8FF))
    text = text.replace("\xa0", " ").replace("\u200b", "")
    return text.strip()


def paragraph(text):
    """API paragraphs separate lines with single newlines; each line is its own paragraph in the PDF."""
    lines = [l.strip() for l in clean(text).split("\n")]
    out, prev_blank = [], True
    for l in lines:
        if not l:
            if not prev_blank:
                out.append("")
            prev_blank = True
            continue
        if not prev_blank and not re.match(r"^([-*•]|\d+[.)])\s", l):
            out.append("")                      # break between two text lines
        out.append(l)
        prev_blank = False
    return out + [""]


def table(text):
    text = (text or "").replace("\xa0", " ").replace("​", "").strip("\n")   # keep the header's leading tab
    rows = [[c.strip().replace("|", "/") for c in r.split("\t")] for r in text.split("\n")]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    w = max(len(r) for r in rows)
    rows = [r + [""] * (w - len(r)) for r in rows]
    return (["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w]
            + ["| " + " | ".join(r) + " |" for r in rows[1:]] + [""])


def chart(block, image_prefix):
    url = (block.get("content") or "").strip()
    title = clean(block.get("title"))
    m = BLOB.search(url)
    if not m:
        return [f"*Chart: {title}*" if title else "*Chart*", ""]
    guid, fname = m.group(1), urllib.parse.unquote(m.group(2).split("?")[0].strip())
    name = title or Path(fname).stem.strip()   # untitled blocks: the file name is the only label
    rel = f"{image_prefix}/{guid}/{urllib.parse.quote(fname)}"
    out = [f"![{name}]({rel})", f"*Chart: {name}*", ""]
    printed = image_tables().get(f"{guid}/{fname}")
    if printed:                                   # an image of a printed table, transcribed exactly
        out += ["Table as printed in the image:", "", printed.strip(), ""]
    return out


_IMAGE_TABLES = None


def image_tables():
    """Transcriptions of table images, keyed '<guid>/<file name>' (see fearnleys_md_image_tables.md)."""
    global _IMAGE_TABLES
    if _IMAGE_TABLES is None:
        text = (Path(__file__).with_name("fearnleys_md_image_tables.md")).read_text(encoding="utf-8")
        _IMAGE_TABLES = {}
        for blk in text.split("\n=== ")[1:]:
            key, body = blk.split("\n", 1)
            _IMAGE_TABLES[key.strip()] = body
    return _IMAGE_TABLES


def render(report, image_prefix):
    blocks = report.get("content") or []
    if isinstance(blocks, str):
        blocks = json.loads(blocks)
    out = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t, c = b.get("type", ""), b.get("content", "")
        if t == "heading1":
            out += [f"## {clean(c)}", ""]
        elif t == "heading2":
            out += [f"### {clean(c)}", ""]
        elif t.endswith("Paragraph") or t == "paragraph":
            if clean(c):
                out += paragraph(c)
        elif t == "sourceText":
            if clean(c):
                out += [f"*{clean(c)}*", ""]
        elif t.endswith("Table"):
            out += table(c)
        elif t.endswith("ChartFromFile") or t == "chart":
            out += chart(b, image_prefix)
        elif t in ("pageBreak", "fullWidthApiChart"):
            continue                              # layout only / an empty API test widget
        else:
            raise ValueError(f"unknown block type {t!r} in {report.get('date')} {report.get('title')}")
    body = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"


def split_header(raw):
    """Frontmatter + '# title' + date/PDF lines + the '---' rule; the body follows."""
    m = re.search(r"^\*\*Date:?\*\*.*?\n---[ \t]*\n", raw, re.M | re.S)
    if not m:
        return None, None
    return raw[:m.end()], raw[m.end():]


def stem_of(rep):
    return f"{rep.get('date')}_{rep.get('slug')}"


def main():
    apply = "--apply" in sys.argv
    only = {a for a in sys.argv[1:] if not a.startswith("--")}
    catalog = json.load(open(CATALOG, encoding="utf-8"))
    changed = skipped = 0
    for rep in catalog:
        stem = stem_of(rep)
        if only and stem not in only:
            continue
        year = str(rep.get("date"))[:4]
        for base, prefix in ((CORPUS, "../images"), (EXTRACTED, "../../../../../corpus/01-brokers/fearnleys-md/images")):
            f = base / year / f"{stem}.md"
            if not f.exists():
                continue
            raw = f.read_text(encoding="utf-8")
            head, body = split_header(raw)
            if head is None:
                print(f"skip (no API header, needs full regeneration): {f.relative_to(ROOT)}")
                skipped += 1
                continue
            new = render(rep, prefix)
            if body.lstrip("\n") != new:
                changed += 1
                if apply:
                    for attempt in range(5):          # Windows: a file watcher can hold the file briefly
                        try:
                            with open(f, "w", encoding="utf-8", newline="\n") as fh:
                                fh.write(head + "\n" + new)
                            break
                        except OSError:
                            if attempt == 4:
                                raise
                            time.sleep(1)
    print(f"{changed} files {'rewritten' if apply else 'would change'}, {skipped} skipped")


if __name__ == "__main__":
    main()
