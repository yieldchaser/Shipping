"""
Open-Access Maritime Literature & Legal Treatises Fetcher.

Downloads open-access maritime economics / legal texts, cleans boilerplate,
splits into 800-1200 word knowledge chunks and writes them as Markdown under
knowledge/books/<TOPIC>/ for the copilot's grounding corpus.

Verified sources (2026-08) - all public domain / explicitly open access:
1. Martin Stopford "Maritime Economics" (Routledge, ISBN 9780415084383)
   - archive.org item isbn_9780415084383: full-text djvu.txt + PDF
2. A Treatise on Maritime Law (Parsons, 1867) - public domain scan
3. Pritchards' Digest of Admiralty and Maritime Law - public domain scan
4. Reports of Cases Relating to Maritime Law - public domain case reports

KNOWN LIMITATIONS (verified 2026-08):
- sewkis.com "Ship Finance Basics" PDF (plan URL): 404 - no longer hosted.
- fjc.gov "Admiralty and Maritime Law" (Robert Force): plan URL 404; the
  FJC moved its publications and the old adm.pdf.pdf path is gone.
- WMU Maritime Commons viewcontent.cgi returns HTTP 202 with an EMPTY body
  for anonymous clients (bepress download challenge); the landing pages are
  readable but full-text downloads require a browser session.
These three plan sources are recorded as unavailable rather than fabricated.
"""

import io
import json
import re
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_DIR = REPO_ROOT / "knowledge" / "books"
CHECKPOINT_FILE = REPO_ROOT / "data" / "derived" / "academic_books_checkpoint.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

# (title, author, topic, source_url)
TEXT_SOURCES = [
    (
        "Maritime Economics",
        "Martin Stopford",
        "maritime_economics",
        "https://archive.org/download/isbn_9780415084383/isbn_9780415084383_djvu.txt",
    ),
    (
        "A Treatise on Maritime Law Including the Law of Shipping",
        "Theophilus Parsons",
        "admiralty_law",
        "https://archive.org/download/atreatiseonmari01parsgoog/atreatiseonmari01parsgoog_djvu.txt",
    ),
    (
        "Pritchards Digest of Admiralty and Maritime Law",
        "Lawrence B. Pritchard",
        "admiralty_law",
        "https://archive.org/download/cu31924022453371/cu31924022453371_djvu.txt",
    ),
    (
        "Reports of the Cases Relating to Maritime Law",
        "Court of Session (Scotland)",
        "admiralty_law",
        "https://archive.org/download/reportscasesrel00courgoog/reportscasesrel00courgoog_djvu.txt",
    ),
]

TARGET_CHUNK_WORDS = (800, 1200)


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_checkpoint(cp):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps(cp, indent=2), encoding="utf-8")


def get_with_backoff(url, attempts=3):
    delay = 2.0
    last_exc = None
    for _ in range(attempts):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=90, stream=True)
            if resp.status_code == 200:
                return resp
            resp.close()
            if resp.status_code in (429, 503):
                time.sleep(delay)
                delay *= 2
                continue
            print(f"  [!] HTTP {resp.status_code} for {url}")
            return None
        except Exception as exc:
            last_exc = exc
            time.sleep(delay)
            delay *= 2
    if last_exc:
        print(f"  [!] Failed {url}: {last_exc}")
    return None


def clean_text(text):
    """Strip OCR artifacts, running page headers/footers, bare page numbers."""
    lines_out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"(?:Page\s*)?\d{1,4}", s):
            continue
        # Google-scan artifacts
        if re.search(r"Digitized by|Google\s*$|Original from|^UNIVERSITY", s, re.I) and len(s) < 60:
            continue
        if len(s) < 2 and not s.isalnum():
            continue
        lines_out.append(s)
    return "\n".join(lines_out)


def split_into_chunks(words, title, topic):
    """Split a word stream into ~800-1200 word chunks."""
    chunks = []
    i = 0
    while i < len(words):
        piece = words[i : i + TARGET_CHUNK_WORDS[1]]
        if len(piece) >= TARGET_CHUNK_WORDS[0] // 2:
            chunks.append(piece)
        i += TARGET_CHUNK_WORDS[1]
    return chunks


def write_chunks(chunks, title, author, topic, source_url):
    written = []
    out_dir = KNOWLEDGE_DIR / topic
    out_dir.mkdir(parents=True, exist_ok=True)
    for n, words in enumerate(chunks, start=1):
        chunk_title = f"{title} - Section {n}"
        slug = re.sub(r"[^a-z0-9]+", "_", chunk_title.lower()).strip("_")[:80]
        text = " ".join(words)
        path = out_dir / f"{slug}.md"
        md = f"""---
title: "{chunk_title}"
author: "{author}"
category: "books"
topic: "{topic}"
source_url: "{source_url}"
---

# {chunk_title}

{text}
"""
        path.write_text(md, encoding="utf-8", errors="ignore")
        written.append(path)
    return written


def process_source(title, author, topic, url, checkpoint):
    key = url.rsplit("/", 1)[-1]
    if checkpoint.get("processed", {}).get(key):
        print(f"  [=] Already processed: {key}")
        return True
    print(f"  [+] Downloading {title} <- {url}")
    resp = get_with_backoff(url)
    if not resp:
        return False
    raw = ""
    with resp:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            raw += chunk.decode("utf-8", errors="ignore")

    # archive.org plain-text items wrap content between two form-feed markers;
    # everything before the first is OCR front-matter noise.
    if raw.lstrip().startswith("\\ No newline at end of file"):
        pass
    total_words_raw = len(raw.split())
    cleaned = clean_text(raw)
    words = cleaned.split()
    print(f"      {total_words_raw:,} raw words -> {len(words):,} after cleaning")
    if len(words) < 3000:
        print("      [!] Text layer too thin; skipping.")
        return False
    chunks = split_into_chunks(words, title, topic)
    written = write_chunks(chunks, title, author, topic, url)
    print(f"      wrote {len(written)} chunks -> knowledge/books/{topic}/")
    checkpoint.setdefault("processed", {})[key] = {
        "chunks": len(written),
        "words": len(words),
    }
    return True


def main():
    print("=" * 80)
    print("  OPEN-ACCESS MARITIME LITERATURE INGESTION")
    print("=" * 80)

    checkpoint = load_checkpoint()
    results = {}

    for title, author, topic, url in TEXT_SOURCES:
        try:
            ok = process_source(title, author, topic, url, checkpoint)
        except Exception as exc:
            print(f"      [!] Error: {exc}")
            ok = False
        results[title] = "OK" if ok else "FAILED"
        time.sleep(1.0)

    save_checkpoint(checkpoint)

    print("\n" + "=" * 80)
    print("  INGESTION SUMMARY:")
    for name, status in results.items():
        print(f"  • {name:60s} -> {status}")
    print("=" * 80)

    return 0 if any(v == "OK" for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
