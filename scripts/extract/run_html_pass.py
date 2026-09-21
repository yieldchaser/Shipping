"""HTML corpus pass: article text + tables + image inventory.

Handles the article-HTML sources (Hellenic sectors, Signal monitors/newsroom/
newsletters, Breakwave insights, Baltic roundups) with per-source junk rules
derived from the continuity audit:

  * Baltic `*/assets/*` files are bot-wall placeholders, not content
  * Breakwave insights include Yahoo Finance / CNN / Blogspot dumps that must
    be filtered by boilerplate + size, or they pollute the corpus
  * Signal pages carry fixed site chrome (identical headings on every page);
    the article body sits between the title and the footer

Output per document (same shape as the PDF path so downstream is uniform):
  <out>/<source>/<stem>/text.jsonl     headings + paragraphs, reading order
  <out>/<source>/<stem>/tables.jsonl   <table> rows as cells
  <out>/<source>/<stem>/images.jsonl   <img> src/alt for later harvesting
  <out>/<source>/<stem>/meta.json      title, junk verdict, counts

Usage:
  python scripts/extract/run_html_pass.py --root reports/hellenic --out data/extracted/html
  python scripts/extract/run_html_pass.py --all --out data/extracted/html
"""
import argparse
import glob
import json
import os
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOTS = {
    "hellenic": ["reports/hellenic"],
    "signal": ["reports/signal/html"],
    "breakwave": ["reports/breakwave"],
    "baltic": ["reports/baltic"],
}

# Junk rules per audit: (substring, reason)
JUNK_PATTERNS = [
    ("/assets/", "bot-wall asset placeholder"),
    ("yahoo.com", "third-party aggregation dump"),
    ("cnn.com", "third-party aggregation dump"),
    ("blogspot.", "reposted third-party content"),
    ("challenge validation", "bot-wall interstitial"),
]

BOILERPLATE = [
    "cookie", "subscribe to our newsletter", "all rights reserved",
    "download the cnn app", "yahoo finance", "recommended stories",
]


def strip_tags(html):
    html = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html,
                  flags=re.S | re.I)
    return html


def junk_verdict(path, html):
    low_path, low = path.lower().replace("\\", "/"), html[:4000].lower()
    for pat, reason in JUNK_PATTERNS:
        if pat in low_path or pat in low:
            return True, reason
    return False, None


def extract(html):
    """Return (title, blocks, tables, images) using a stdlib parser."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.title = ""
            self.blocks = []
            self.tables = []
            self.images = []
            self._cap = None
            self._buf = []
            self._intable = False
            self._row = None
            self._cell = None
            self._skip = 0

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag in ("script", "style", "noscript"):
                self._skip += 1
            elif tag in ("h1", "h2", "h3", "h4", "p", "li"):
                self._cap = tag
                self._buf = []
            elif tag == "title":
                self._cap = "title"
                self._buf = []
            elif tag == "table":
                self._intable = True
                self.tables.append([])
            elif tag == "tr" and self._intable:
                self._row = []
            elif tag in ("td", "th") and self._intable:
                self._cell = []
            elif tag == "img":
                self.images.append({"src": a.get("src", ""), "alt": a.get("alt", "")})

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript"):
                self._skip = max(0, self._skip - 1)
            elif tag in ("h1", "h2", "h3", "h4", "p", "li") and self._cap == tag:
                txt = re.sub(r"\s+", " ", "".join(self._buf)).strip()
                if txt and len(txt) > 2:
                    self.blocks.append({"kind": tag, "text": txt})
                self._cap = None
            elif tag == "title" and self._cap == "title":
                self.title = re.sub(r"\s+", " ", "".join(self._buf)).strip()
                self._cap = None
            elif tag in ("td", "th") and self._cell is not None:
                self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
                self._cell = None
            elif tag == "tr" and self._row is not None:
                if any(self._row):
                    self.tables[-1].append(self._row)
                self._row = None
            elif tag == "table":
                self._intable = False

        def handle_data(self, data):
            if self._skip:
                return
            if self._cell is not None:
                self._cell.append(data)
            elif self._cap:
                self._buf.append(data)

    p = P()
    p.feed(strip_tags(html))
    return p.title, p.blocks, p.tables, p.images


def source_for(path):
    for name, prefixes in ROOTS.items():
        for pre in prefixes:
            if path.replace("\\", "/").startswith(pre):
                return name
    return "html"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default=os.path.join(REPO, "data", "extracted", "html"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    roots = []
    if a.all or not a.root:
        for v in ROOTS.values():
            roots += v
    else:
        roots = a.root
    files = []
    for r in roots:
        files += glob.glob(os.path.join(REPO, r, "**", "*.html"), recursive=True)
        files += glob.glob(os.path.join(REPO, r, "**", "*.htm"), recursive=True)
    files = sorted(set(files))
    if a.limit:
        files = files[:a.limit]
    print(f"html files: {len(files)}", flush=True)

    stats = {"docs": 0, "junk": 0, "blocks": 0, "tables": 0, "images": 0}
    reasons = {}
    for i, fp in enumerate(files, 1):
        rel = os.path.relpath(fp, REPO)
        try:
            html = open(fp, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        junk, reason = junk_verdict(rel, html)
        src = source_for(rel)
        stem = os.path.splitext(os.path.basename(fp))[0]
        ddir = os.path.join(a.out, src, stem)
        os.makedirs(ddir, exist_ok=True)
        if junk:
            stats["junk"] += 1
            reasons[reason] = reasons.get(reason, 0) + 1
            with open(os.path.join(ddir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"file": rel, "junk": True, "reason": reason}, f)
            continue
        title, blocks, tables, images = extract(html)
        # drop site boilerplate blocks (Signal chrome repeats on every page)
        blocks = [b for b in blocks
                  if not any(bp in b["text"].lower() for bp in BOILERPLATE)]
        with open(os.path.join(ddir, "text.jsonl"), "w", encoding="utf-8") as f:
            for bi, b in enumerate(blocks):
                f.write(json.dumps({"idx": bi, **b}) + "\n")
        with open(os.path.join(ddir, "tables.jsonl"), "w", encoding="utf-8") as f:
            for ti, rows in enumerate(tables):
                if rows:
                    f.write(json.dumps({"page": 0, "table_idx": ti,
                                        "engine": "html-table", "rows": rows}) + "\n")
        with open(os.path.join(ddir, "images.jsonl"), "w", encoding="utf-8") as f:
            for im in images:
                f.write(json.dumps(im) + "\n")
        with open(os.path.join(ddir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"file": rel, "title": title, "blocks": len(blocks),
                       "tables": len(tables), "images": len(images),
                       "junk": False,
                       "extraction_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                      time.gmtime())}, f, indent=1)
        stats["docs"] += 1
        stats["blocks"] += len(blocks)
        stats["tables"] += len(tables)
        stats["images"] += len(images)
        if i % 250 == 0:
            print(f"[{i}/{len(files)}] {stats}", flush=True)

    print(f"\ndone: {stats}")
    if reasons:
        print(f"junk reasons: {reasons}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
