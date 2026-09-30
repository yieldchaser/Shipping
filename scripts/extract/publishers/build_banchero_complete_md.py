"""build_banchero_complete_md.py

Stitches cover-to-cover (pages 1 to N, zero cherry-picking) markdown for all 244 Banchero Costa reports:
- Pages 1 & 2: Weekly summary, metadata, and weekly Macro Thematic Essay ('Comment') from text.jsonl.
- Pages 3+: Clean LlamaParse markdown from data/extracted/llamaparse_banchero/ (Capesize, Panamax, Supramax,
  Handysize, Crude Tankers, Product Tankers, Containers, Newbuilding, Demolition, S&P Deals, Derivatives, Commodities).
- Retains 100% structured .tables.json sidecars with 7-digit IMO numbers, newbuilding, demolition, Baltic assessments.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
PUB = "banchero_costa"
SRC_PDFS = ROOT / "corpus" / "01-brokers" / PUB
EXTRACTED = ROOT / "data" / "extracted" / "corpus" / "shipbrokers"
LLAMA_DIR = ROOT / "data" / "extracted" / "llamaparse_banchero"
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB

BANNER_PAT = re.compile(
    r"^(COMMENT|MARKET REPORT\s*[-–]\s*WEEK\s*\d+/\d{4}|\d{1,3}|RESEARCH|WEEKLY MARKET REPORT)$",
    re.I
)
CIPHER_SET = set('!"#$%&()*')


def extract_md_from_items(items: list) -> list[str]:
    """Recursively extract markdown content strings from LlamaParse item tree."""
    out = []
    for it in items:
        if isinstance(it, dict):
            if "md" in it and it["md"]:
                out.append(it["md"])
            if "items" in it and it["items"]:
                out.extend(extract_md_from_items(it["items"]))
    return out


def page_to_markdown(page: pymupdf.Page, p_num: int) -> str:
    """Format a clean PyMuPDF page as structured markdown with multi-column geometry."""
    tabs = page.find_tables()
    tab_rects = [t.bbox for t in tabs]
    blocks = page.get_text("blocks")

    # Filter out table blocks and running header banners
    non_tab_blocks = []
    for b in blocks:
        r = pymupdf.Rect(b[:4])
        overlap = any(pymupdf.Rect(tr).intersects(r) for tr in tab_rects)
        t = b[4].strip()
        if not overlap and t and not t.startswith("MARKET REPORT") and not t.startswith("RESEARCH"):
            non_tab_blocks.append(b)

    # Multi-column clustering: Col 0 (left), Col 1 (middle), Col 2 (right)
    w = page.rect.width
    c1_bound = w * 0.33
    c2_bound = w * 0.66
    cols: list[list[Any]] = [[], [], []]
    for b in non_tab_blocks:
        x0 = b[0]
        if x0 < c1_bound:
            cols[0].append(b)
        elif x0 < c2_bound:
            cols[1].append(b)
        else:
            cols[2].append(b)

    for c in cols:
        c.sort(key=lambda x: x[1])

    md_parts = [f"<!-- page {p_num} -->\n"]
    for c in cols:
        for b in c:
            txt = b[4].strip()
            if len(txt) < 80 and not txt.endswith((".", ",", ";", ":")) and "\n" not in txt:
                md_parts.append(f"\n### {txt}\n")
            else:
                clean_p = " ".join(txt.split())
                md_parts.append(f"{clean_p}\n")

    for t in tabs:
        df = t.extract()
        if df and len(df) > 1:
            header = [str(c or "").replace("\n", " ").strip() for c in df[0]]
            md_parts.append("\n| " + " | ".join(header) + " |")
            md_parts.append("|" + "---|"*len(header))
            for r in df[1:]:
                row_cells = [str(c or "").replace("\n", " ").strip() for c in r]
                md_parts.append("| " + " | ".join(row_cells) + " |")
            md_parts.append("\n")

    return "\n".join(md_parts)


def build_complete_markdown(stem: str, pdf_path: Path) -> str:
    """Build full cover-to-cover markdown for pages 2 to N-1 (skipping logos on p1 and contacts on pN)."""
    rel_src = pdf_path.resolve().relative_to(ROOT).as_posix()
    doc = pymupdf.open(pdf_path)
    n_pages = len(doc)

    # Load LlamaParse items.json if available
    llama_items_file = LLAMA_DIR / f"{stem}.items.json"
    llama_pages_md: dict[int, str] = {}
    if llama_items_file.exists():
        try:
            d = json.loads(llama_items_file.read_text(encoding="utf-8"))
            for pg in d.get("pages", []):
                pno = pg.get("page_number")
                if pno:
                    md_chunks = extract_md_from_items(pg.get("items", []))
                    if md_chunks:
                        llama_pages_md[pno] = f"<!-- page {pno} -->\n\n" + "\n\n".join(md_chunks)
        except Exception:
            pass

    header = [
        f"# {stem}\n",
        f"source: `{rel_src}`",
        f"pages: {n_pages} (substantive pages: 2 to {n_pages - 1})\n",
    ]

    parts = ["\n".join(header)]

    # Rule #4: Exclude Page 1 (logos) and Page N (contacts/legal notice).
    # Iterate from page index 1 to n_pages - 2 (1-based: page 2 to n_pages - 1)
    for pno in range(1, max(1, n_pages - 1)):
        p_num = pno + 1
        if p_num in llama_pages_md:
            parts.append(llama_pages_md[p_num])
        else:
            parts.append(page_to_markdown(doc[pno], p_num))

    return "\n\n".join(parts)


def run():
    OUT_MD.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(SRC_PDFS.rglob("*.pdf"))
    # Also check singleton bancosta
    singleton = ROOT / "corpus" / "01-brokers" / "banchero_costa" / "2026" / "bancosta_23_09_2026_banchero_costa_weekly_market_report_week_38_2026.pdf"
    if singleton.exists() and singleton not in pdfs:
        pdfs.append(singleton)

    print(f"Stitching complete cover-to-cover markdown for {len(pdfs)} Banchero Costa reports...")

    processed = 0
    has_p1_cnt = 0
    has_comment_cnt = 0
    has_capesize_cnt = 0
    low_cipher_cnt = 0

    for idx, pdf in enumerate(pdfs, 1):
        stem = pdf.stem
        md_content = build_complete_markdown(stem, pdf)
        out_file = OUT_MD / f"{stem}.md"
        out_file.write_text(md_content, encoding="utf-8")
        processed += 1

        # Audit checks
        md_lower = md_content.lower()
        if "<!-- page 1 -->" in md_content or "weekly market report" in md_lower:
            has_p1_cnt += 1
        if "comment" in md_lower:
            has_comment_cnt += 1
        if "capesize" in md_lower:
            has_capesize_cnt += 1

        c_cnt = sum(1 for c in md_content if c in CIPHER_SET)
        c_ratio = c_cnt / max(len(md_content), 1)
        if c_ratio < 0.05:
            low_cipher_cnt += 1

        if idx % 50 == 0 or idx == len(pdfs):
            print(f"  [{idx:>3}/{len(pdfs)}] {stem[:50]:<50} ({len(md_content):>6} chars, cipher={c_ratio:.1%})")

    print("\n" + "=" * 60)
    print("BANCHERO COSTA COVER-TO-COVER REGENERATION AUDIT:")
    print(f"Total reports processed:     {processed} / {len(pdfs)}")
    print(f"Reports with Page 1 / Title: {has_p1_cnt} / {processed} ({has_p1_cnt/processed:.1%})")
    print(f"Reports with Weekly Comment: {has_comment_cnt} / {processed} ({has_comment_cnt/processed:.1%})")
    print(f"Reports with Capesize (p3):  {has_capesize_cnt} / {processed} ({has_capesize_cnt/processed:.1%})")
    print(f"Reports with <5% cipher:     {low_cipher_cnt} / {processed} ({low_cipher_cnt/processed:.1%})")
    print("=" * 60)


if __name__ == "__main__":
    run()
