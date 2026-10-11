"""Re-insert text that the HTML -> Markdown conversion dropped (Breakwave insights, Signal articles).

Measured 2026-10-11: 99.4% of HTML paragraphs are in the MDs; the misses are nested sub-bullets (the converter kept
only the outer list) and chart captions printed as their own paragraph. This tool walks the article's HTML elements
in order, finds each one in the MD, and inserts any missing element's text right after the MD line that holds the
previous matched element. Additive only: no existing MD text is changed or removed. Bare URLs, share/subscribe
boilerplate and newsletter layout tables are skipped.

    python scripts/md_cleanup/restore_html_paragraphs.py data/extracted/md/breakwave/insights            # dry run
    python scripts/md_cleanup/restore_html_paragraphs.py data/extracted/md/breakwave/insights --apply
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT.parents[2] if ROOT.parent.name == "worktrees" else ROOT
LINK = re.compile(r"!?\[([^\]]*)\]\((?:[^()\s]|\([^()\s]*\))+\)")
TAGS = ["p", "li", "h2", "h3", "h4", "figcaption", "blockquote"]
SKIP = re.compile(r"^\s*(?:https?://\S+|Data Source:.*https?://\S+|Follow us on|Click here to|For the latest updates|"
                  r"Book a walkthrough|Thank you for catching up|Subscribe|Share)\b", re.I)


def norm_map(text: str) -> tuple[str, list[int]]:
    """Lowercase alphanumerics of text, plus each kept char's index in text."""
    keep, idx = [], []
    for i, ch in enumerate(text):
        c = ch.lower()
        if c.isascii() and c.isalnum():
            keep.append(c)
            idx.append(i)
    return "".join(keep), idx


def norm(s: str) -> str:
    return norm_map(s)[0]


def depth(el) -> int:
    return sum(1 for p in el.parents if p.name in ("ul", "ol")) - 1


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    stat = Counter()
    files = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", *args], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8").stdout.splitlines()
    for rel in files:
        if not rel.endswith(".md") or "/newsletters/" in rel:
            continue
        path = ROOT / rel
        if not path.exists():
            continue
        raw = path.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        md = raw.replace("\r\n", "\n")
        m = re.search(r'^source_file:\s*"?([^"\n]+\.html?)', md, re.M)
        html = next((b / m.group(1) for b in (ROOT, MAIN) if m and (b / m.group(1)).exists()), None)
        if html is None:
            continue
        soup = BeautifulSoup(html.read_text(encoding="utf-8", errors="replace"), "html.parser")
        bodies = [b for b in soup.select(".w-richtext") if "hide" not in (b.get("class") or [])] or [soup.body]
        els = [e for b in bodies for e in b.find_all(TAGS)
               if not e.find(TAGS)]                                   # innermost blocks only: no double counting
        stripped = LINK.sub(lambda x: x.group(1), md)
        inserts = []                                                  # (position in md, text)
        cursor = 0
        nm_full, idx_full = norm_map(md)
        nm_strip = norm(stripped)
        for e in els:
            text = re.sub(r"\s+", " ", e.get_text(" ", strip=True)).replace("‍", "").strip()
            key = norm(text)
            if len(key) < 25 or SKIP.match(text):
                continue
            pos = nm_full.find(key[:60])
            if pos >= 0:
                cursor = max(cursor, md.find("\n", idx_full[min(pos + len(key) - 1, len(idx_full) - 1)]))
                if cursor < 0:
                    cursor = len(md)
                continue
            if key[:60] in nm_strip:                                  # present, split by a markdown link
                continue
            chunks = [key[i:i + 40] for i in range(0, max(len(key) - 40, 1), 20)]
            if any(c in nm_strip for c in chunks):                    # partly present: a word or label was lost
                stat["partial losses (reported, not inserted)"] += 1
                if "--show" in sys.argv:
                    print(f"   PARTIAL {rel.split('/')[-1][:50]} | {text[:110]}")
                continue
            line_start = md.rfind("\n", 0, max(cursor, 0)) + 1
            prev_line = md[line_start:cursor] if cursor > 0 else ""
            in_list = re.match(r"\s*(?:[-*+]|\d+[.)]|[ivx]+\.)\s", prev_line) is not None
            nested_li = e.name == "li" or (e.find_parent("li") is not None)
            if in_list and nested_li:                                 # a dropped sub-item: nest it under the item above
                indent = len(prev_line) - len(prev_line.lstrip()) + 3
                block = ("\n", " " * indent + "- " + text)
            elif e.name == "li":
                block = ("\n\n", "- " + text)
            elif e.name in ("h2", "h3", "h4"):
                block = ("\n\n", "### " + text)
            else:
                block = ("\n\n", text + ("\n" if in_list else ""))
            inserts.append((cursor, block))
        if not inserts:
            continue
        stat["files"] += 1
        stat["blocks restored"] += len(inserts)
        new = md
        for pos in sorted({p for p, _ in inserts}, reverse=True):   # blocks sharing an anchor keep their order
            new = new[:pos] + "".join(sep + b for p, (sep, b) in inserts if p == pos) + new[pos:]
        if "--show" in sys.argv:
            print(f"== {rel}")
            for _, (_, b) in inserts:
                print("   +", b[:150])
        if apply:
            path.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
    for k, v in sorted(stat.items()):
        print(f"{v:6}  {k}")
    print("APPLIED" if apply else "dry run (use --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
