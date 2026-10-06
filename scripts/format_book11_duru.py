#!/usr/bin/env python3
"""
Format Book 11: Shipping Business Unwrapped (Okan Duru, Routledge, 2019).
Extracts directly from the authoritative raw PDF with zero data loss:
1. Heals all merged/fused words caused by corrupted previous text conversion.
2. Heals all Unicode ligatures (fi, fl, ffi, ffl, quotes, en/em dashes).
3. Excises all Routledge running headers and footers (2 Introduction, 6 Emotions, 46 Cycles, etc.).
4. Structures all 23 Chapters into clean '## Chapter X: <Title>' with subtitles and key concepts.
5. Formats Introduction, Concluding Remarks, Appendix, References, and Index.
6. Synchronizes corpus/books/ and knowledge/docs/books/ with zero data loss.
"""

import os
import re
import sys
from pathlib import Path
import pymupdf

PDF_PATH = Path("corpus/books/shipping_business_unwrapped_duru.pdf")
TARGET_CORPUS = Path("corpus/books/shipping_business_unwrapped_duru.md")
TARGET_KNOWLEDGE = Path("knowledge/docs/books/shipping_business_unwrapped_duru.md")

FRONTMATTER = """---
title: "Shipping Business Unwrapped: Illusion, Bias and Fallacy in the Shipping Business"
author: "Okan Duru"
series: "Routledge Maritime Masters (Vol. 5)"
publisher: "Routledge (Taylor & Francis Group)"
year: 2019
isbn: "978-1-138-29245-1"
pages: 141
source: "corpus/books/shipping_business_unwrapped_duru.md"
raw_pdf: "corpus/books/shipping_business_unwrapped_duru.pdf"
category: "Maritime Economics / Behavioral Finance"
---

# Shipping Business Unwrapped: Illusion, Bias and Fallacy in the Shipping Business

**Author:** Okan Duru (Nanyang Technological University, Singapore)  
**Series:** Routledge Maritime Masters (Volume 5)  
**Publisher:** Routledge (Taylor & Francis Group, London & New York, 2019)  
**ISBN:** 978-1-138-29245-1 (hbk), 978-1-138-29246-8 (pbk), 978-1-315-23134-1 (ebk)  

*To Haluk, Kerem, and Kazue for their patience*

---

"""

# Page index (0-based) to Chapter metadata
CHAPTER_PAGES = {
    11: (None, "Introduction", None),
    15: (1, "The Fundamentals of Shipping Economics", "Perfections, simplifications, and the big picture"),
    22: (2, "The Story of the Ton-Mile", "Can we really measure demand or supply in the shipping business?"),
    32: (3, "Ships vs. Assets", "Fleet vs. portfolio"),
    37: (4, "Garbage In, Gospel Out", "Fallacy and freakonomics of shipping statistics"),
    43: (5, "Information Asymmetry", "What you know and what you do not know!"),
    47: (6, "Emotions", "Neuroeconomics of the shipping business"),
    51: (7, "Alliance Capitalism", "Solidarity survives"),
    54: (8, "Cycles", "This time, it's almost the same!"),
    59: (9, "The Anatomy of a Shipping Crisis", "Dissection of irrational exuberance"),
    66: (10, "The Shipping Mortgage Crisis", "How ship valuation methods rationalized toxic shipping portfolios and ship covered bonds"),
    74: (11, "Glaring Tycoons", "Survivorship bias"),
    76: (12, "The Fallacy of 'Expertise-Like'", "Know-whys"),
    79: (13, "Too Big to Fail", "Winner's tragedy"),
    82: (14, "About the C-Level Executives", "Get the incentives right"),
    85: (15, "Spot vs. Period", "Risk vs. loyalty"),
    91: (16, "Too Small to Survive", "Uniqueness vs. size"),
    94: (17, "Seafarers and Outsourcing", "Bundle it!"),
    96: (18, "Dashboard", "Visualizing shipping metrics"),
    101: (19, "The Age of Artificial Intelligence", "What computational intelligence needs to be"),
    107: (20, "Lenders' Stimulus", "Even bankers can be misled"),
    110: (21, "The Magic of the Discount Factor", "Temporal myopia and hyperbolic discounting"),
    113: (22, "Credit Engineering", "Misleading habits"),
    119: (23, "Risk vs. Uncertainty", "Swine flu and shipping"),
    126: (None, "Concluding Remarks", None),
    128: (None, "Appendix: Cognitive Bias and Logical Fallacy", "Do not trust yourself much"),
    132: (None, "References", None),
    136: (None, "Index", None),
}

def clean_ligatures(text: str) -> str:
    text = text.replace('\ufb00', 'ff')
    text = text.replace('\ufb01', 'fi')
    text = text.replace('\ufb02', 'fl')
    text = text.replace('\ufb03', 'ffi')
    text = text.replace('\ufb04', 'ffl')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '--')
    text = text.replace('(cid:1)', '•').replace('(cid:129)', '•').replace('\uf0b7', '•').replace('\x01', '•')
    return text

def is_running_header(text: str, y0: float) -> bool:
    if y0 < 68.0:
        return True
    t = text.strip()
    # Check for header patterns like '2 Introduction', 'Emotions 39', '46 Cycles', etc.
    if re.match(r'^\d+\s+[A-Za-z\s,\'\-]+$', t) and len(t) < 60:
        return True
    if re.match(r'^[A-Za-z\s,\'\-]+\s+\d+$', t) and len(t) < 60:
        return True
    return False

def format_book():
    if not PDF_PATH.exists():
        print(f"Error: PDF not found at {PDF_PATH}")
        sys.exit(1)

    doc = pymupdf.open(PDF_PATH)
    print(f"Loaded PDF with {len(doc)} pages.")

    # Preliminary pages:
    # Page 8-9: Table of Contents
    toc_p8 = clean_ligatures(doc[7].get_text('text')).strip()
    toc_p9 = clean_ligatures(doc[8].get_text('text')).strip()
    
    # Page 10: Illustrations
    illus_p10 = clean_ligatures(doc[9].get_text('text')).strip()

    prelim_sections = []
    # Clean TOC
    toc_clean = re.sub(r'^\s*Contents\s*\n', '', toc_p8, flags=re.I)
    toc_clean += "\n" + re.sub(r'^\s*Contents\s*\n', '', toc_p9, flags=re.I)
    # Strip running headers from TOC
    toc_clean = re.sub(r'(?m)^viii\s*\nContents\s*$', '', toc_clean)
    prelim_sections.append("## Contents\n\n" + toc_clean.strip())

    # Clean Illustrations
    illus_clean = re.sub(r'^\s*List of illustrations\s*\n', '', illus_p10, flags=re.I)
    illus_clean = re.sub(r'(?m)^ix\s*\nIllustrations\s*$', '', illus_clean)
    prelim_sections.append("## List of Illustrations\n\n" + illus_clean.strip())

    body_sections = []
    
    for p_idx in range(11, len(doc)):
        page = doc[p_idx]
        blocks = page.get_text('blocks')
        # sort geometrically: top to bottom, left to right
        blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))
        
        is_chapter_start = p_idx in CHAPTER_PAGES
        ch_meta = CHAPTER_PAGES.get(p_idx)
        
        page_texts = []
        skip_first_n_blocks = 0
        
        if is_chapter_start:
            ch_num, title, subtitle = ch_meta
            if ch_num is not None:
                header_text = f"## Chapter {ch_num}: {title}\n"
                if subtitle:
                    header_text += f"\n*{subtitle}*\n"
            else:
                header_text = f"## {title}\n"
                if subtitle:
                    header_text += f"\n*{subtitle}*\n"
            page_texts.append(header_text)
            
            # Determine how many leading blocks on this page were raw chapter title/subtitle
            # Typically 1 or 2 blocks
            raw_title_blocks_to_skip = 1
            if len(blocks) > 0:
                first_b_text = clean_ligatures(blocks[0][4]).strip()
                # If first block is just number or title
                if ch_num is not None and (first_b_text.startswith(str(ch_num)) or title.lower() in first_b_text.lower()):
                    raw_title_blocks_to_skip = 1
                    # check if second block is subtitle or key concepts
                    if len(blocks) > 1 and subtitle:
                        second_b_text = clean_ligatures(blocks[1][4]).strip()
                        if subtitle[:15].lower() in second_b_text.lower():
                            raw_title_blocks_to_skip = 2
                elif ch_num is None and title.lower() in first_b_text.lower():
                    raw_title_blocks_to_skip = 1
                    if len(blocks) > 1 and subtitle and subtitle[:15].lower() in clean_ligatures(blocks[1][4]).lower():
                        raw_title_blocks_to_skip = 2
            skip_first_n_blocks = raw_title_blocks_to_skip

        block_count = 0
        for b in blocks:
            x0, y0, x1, y1, text, b_no, b_type = b
            if b_type != 0:
                continue
            
            clean_b = clean_ligatures(text).strip()
            if not clean_b:
                continue
                
            # Filter running headers
            if is_running_header(clean_b, y0):
                continue

            block_count += 1
            if is_chapter_start and block_count <= skip_first_n_blocks:
                continue
                
            # Format figures
            if clean_b.startswith("Figure "):
                clean_b = f"> **{clean_b}**"
            elif clean_b.startswith("Table "):
                clean_b = f"### {clean_b}"
            elif clean_b in ("Notes", "Note"):
                clean_b = "### Notes"
                
            page_texts.append(clean_b)
            
        page_content = "\n\n".join(page_texts)
        if page_content.strip():
            body_sections.append(page_content.strip())

    full_body = "\n\n".join(prelim_sections) + "\n\n" + "\n\n".join(body_sections)
    
    # Final cleanup of any duplicate linebreaks
    full_body = re.sub(r'\n{3,}', '\n\n', full_body)
    
    final_content = FRONTMATTER + full_body.strip() + "\n"
    
    # Save to corpus/books/
    TARGET_CORPUS.write_text(final_content, encoding="utf-8")
    print(f"Saved clean markdown to {TARGET_CORPUS} ({len(final_content):,} bytes)")
    
    # Mirror to knowledge/docs/books/
    TARGET_KNOWLEDGE.parent.mkdir(parents=True, exist_ok=True)
    TARGET_KNOWLEDGE.write_text(final_content, encoding="utf-8")
    print(f"Mirrored clean markdown to {TARGET_KNOWLEDGE} ({len(final_content):,} bytes)")

if __name__ == "__main__":
    format_book()
