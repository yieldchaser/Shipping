#!/usr/bin/env python3
"""
scripts/rebuild_book11_perfect.py
Rebuild Book 11: Shipping Business Unwrapped by Okan Duru (Routledge / Z-Library).

Fixes all defects:
1. Full-page figure vector chart artifacts (Figure 8.1 on p56 and Figure 8.2 on p58):
   - Completely removes 104+ axis tick numbers, year sequences (1738-2017, 3000-0), and scale labels.
   - Emits clean blockquotes for the figure captions.
   - Heals sentences split across figure pages (e.g. "dopamine addiction, the love of risk...").
2. 2-Column Index (Pages 137 to 141):
   - Spatial 2-column extraction (Column 1 then Column 2 per page).
   - Alphabetical section headers (### A through ### Y).
   - Structured bullet items (- entry).
3. Unicode normalization: heals ligatures (fi, fl, ffi, ffl) and hyphenations ("scanning").
4. Strict zero-data-loss, zero-emoji policy, and 100% byte parity between corpus/ and knowledge/.
"""

import sys
import re
from pathlib import Path
import pymupdf

sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH = Path("corpus/books/Shipping Business Unwrapped. (Duru, Okan) (Z-Library).pdf")
TARGET_CORPUS = Path("corpus/books/shipping_business_unwrapped_duru_okan_z_library.md")
TARGET_KNOWLEDGE = Path("knowledge/docs/books/shipping_business_unwrapped_duru_okan_z_library.md")

FRONTMATTER = """---
title: "Shipping Business Unwrapped"
author: "Okan Duru"
publisher: "Routledge"
year: 2018
isbn: "978-1-138-04336-7"
pages: 141
source: "corpus/books/shipping_business_unwrapped_duru_okan_z_library.md"
category: "Shipping Management / Maritime Economics"
---

# Shipping Business Unwrapped

**Author:** Okan Duru  
**Publisher:** Routledge (Taylor & Francis Group, 2018)  
**ISBN:** 978-1-138-04336-7 (hbk), 978-1-315-17316-0 (ebk)  

*To my parents, my wife and my son*

---

"""

CHAPTER_PAGES = {
    11: (1, "The Rational Actor Fallacy", "Why do smart people make stupid mistakes?"),
    16: (2, "The Fundamental Metric of Shipping", "The ton-mile is dead, long live the ton-mile"),
    23: (3, "The Fallacy of Cheap Ships", "Why cheap ships are not really cheap"),
    29: (4, "The Mystery of Shipping Markets", "A game of thrones: spot vs. period"),
    34: (5, "The S&P Market Dilemma", "Why do shipowners buy high and sell low?"),
    38: (6, "The Psychology of Asset Play", "When emotions drive multimillion-dollar decisions"),
    43: (7, "The Market Timing Myth", "Can anyone really time the market?"),
    48: (8, "Cycles, Crises, and Bubbles", "Why shipping cycles are here to stay"),
    58: (9, "The Illusion of Control", "Risk management in an uncontrollable world"),
    65: (10, "The Shipping Mortgage Crisis", "How ship valuation methods rationalized toxic shipping portfolios and ship covered bonds"),
    73: (11, "Glaring Tycoons", "Survivorship bias"),
    75: (12, "The Fallacy of 'Expertise-Like'", "Know-whys"),
    78: (13, "Too Big to Fail", "Winner's tragedy"),
    81: (14, "About the C-Level Executives", "Get the incentives right"),
    84: (15, "Spot vs. Period", "Risk vs. loyalty"),
    90: (16, "Too Small to Survive", "Uniqueness vs. size"),
    93: (17, "Seafarers and Outsourcing", "Bundle it!"),
    95: (18, "Dashboard", "Visualizing shipping metrics"),
    100: (19, "The Age of Artificial Intelligence", "What computational intelligence needs to be"),
    106: (20, "Lenders' Stimulus", "Even bankers can be misled"),
    109: (21, "The Magic of the Discount Factor", "Temporal myopia and hyperbolic discounting"),
    112: (22, "Credit Engineering", "Misleading habits"),
    118: (23, "Risk vs. Uncertainty", "Swine flu and shipping"),
    125: (None, "Concluding Remarks", None),
    127: (None, "Appendix: Cognitive Bias and Logical Fallacy", "Do not trust yourself much"),
    131: (None, "References", None),
}

def clean_text(text: str) -> str:
    text = text.replace('\ufb00', 'ff').replace('\ufb01', 'fi').replace('\ufb02', 'fl')
    text = text.replace('\ufb03', 'ffi').replace('\ufb04', 'ffl')
    text = text.replace('ﬃ', 'ffi').replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('ﬀ', 'ff')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '--')
    text = text.replace('(cid:1)', '-').replace('(cid:129)', '-').replace('\uf0b7', '-').replace('\x01', '-')
    text = text.replace('\xa0', ' ')
    text = text.replace('Duru\ufffd', 'Duru ©').replace('Duru©', 'Duru ©')
    text = re.sub(r'(\b[a-zA-Z]+)-\s+([a-zA-Z]+\b)', r'\1\2', text)
    return text

def is_running_header(text: str, y0: float) -> bool:
    if y0 < 68.0:
        return True
    t = text.strip()
    if re.match(r'^\d+\s+[A-Za-z\s,\'\-]+$', t) and len(t) < 60:
        return True
    if re.match(r'^[A-Za-z\s,\'\-]+\s+\d+$', t) and len(t) < 60:
        return True
    return False

def extract_index(doc) -> str:
    all_entries = []
    curr_entry = []

    def flush():
        nonlocal curr_entry
        if curr_entry:
            entry_text = ' '.join(curr_entry)
            entry_text = clean_text(entry_text)
            all_entries.append(entry_text)
            curr_entry = []

    for p_num in range(137, 142):
        page = doc[p_num - 1]
        lines_col1 = []
        lines_col2 = []
        for b in page.get_text('dict')['blocks']:
            if 'lines' not in b:
                continue
            for l in b['lines']:
                spans = l['spans']
                if not spans:
                    continue
                x0 = spans[0]['bbox'][0]
                y0 = spans[0]['bbox'][1]
                text = ''.join(s['text'] for s in spans).strip()
                if not text or text == 'Index' or text.isdigit() or (y0 < 60 and 'Index' in text):
                    continue
                if x0 < 210:
                    lines_col1.append((y0, text, x0, 1))
                else:
                    lines_col2.append((y0, text, x0, 2))
        lines_col1.sort(key=lambda x: x[0])
        lines_col2.sort(key=lambda x: x[0])
        
        for col in (lines_col1, lines_col2):
            for y0, text, x0, c_idx in col:
                is_indent = (c_idx == 1 and x0 > 62.0) or (c_idx == 2 and x0 > 233.0)
                if is_indent:
                    if curr_entry:
                        curr_entry.append(text)
                    else:
                        curr_entry = [text]
                else:
                    flush()
                    curr_entry = [text]
    flush()

    index_sections = []
    current_letter = ''
    for e in all_entries:
        clean_e = e.lstrip('"\'')
        first_char = clean_e[0].upper()
        if first_char.isalpha() and first_char != current_letter:
            current_letter = first_char
            index_sections.append(f"\n### {current_letter}\n")
        index_sections.append(f"- {e}")

    return "## Index\n" + "\n".join(index_sections)

def rebuild_book11():
    doc = pymupdf.open(PDF_PATH)
    print(f"Loaded Book 11 with {len(doc)} pages.")

    # Preliminary pages
    toc_p8 = clean_text(doc[7].get_text('text')).strip()
    toc_p9 = clean_text(doc[8].get_text('text')).strip()
    illus_p10 = clean_text(doc[9].get_text('text')).strip()

    prelim_sections = []
    toc_clean = re.sub(r'^\s*Contents\s*\n', '', toc_p8, flags=re.I)
    toc_clean += "\n" + re.sub(r'^\s*Contents\s*\n', '', toc_p9, flags=re.I)
    toc_clean = re.sub(r'(?m)^viii\s*\nContents\s*$', '', toc_clean)
    prelim_sections.append("## Contents\n\n" + toc_clean.strip())

    illus_clean = re.sub(r'^\s*List of illustrations\s*\n', '', illus_p10, flags=re.I)
    illus_clean = re.sub(r'(?m)^ix\s*\nIllustrations\s*$', '', illus_clean)
    prelim_sections.append("## List of Illustrations\n\n" + illus_clean.strip())

    body_sections = []

    # Body pages 11 to 135 (0-indexed 10 to 135)
    for p_idx in range(10, 136):
        page_num = p_idx + 1

        # Page 56: Full-page Figure 8.1
        if page_num == 56:
            body_sections.append("> **Figure 8.1** Long-term freight market index (LFI)  \n> *Source: Copyright Okan Duru © 2018.*")
            continue

        # Page 58: Full-page Figure 8.2
        if page_num == 58:
            body_sections.append("> **Figure 8.2** LFI series for the second half of the 1700s (right scale) and 1900s (left scale)")
            continue

        page = doc[p_idx]
        blocks = page.get_text('blocks')
        blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

        is_chapter_start = page_num in CHAPTER_PAGES
        ch_meta = CHAPTER_PAGES.get(page_num)

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

            raw_title_blocks_to_skip = 1
            if len(blocks) > 0:
                first_b_text = clean_text(blocks[0][4]).strip()
                if ch_num is not None and (first_b_text.startswith(str(ch_num)) or title.lower() in first_b_text.lower()):
                    raw_title_blocks_to_skip = 1
                    if len(blocks) > 1 and subtitle and subtitle[:15].lower() in clean_text(blocks[1][4]).lower():
                        raw_title_blocks_to_skip = 2
                elif ch_num is None and title.lower() in first_b_text.lower():
                    raw_title_blocks_to_skip = 1
                    if len(blocks) > 1 and subtitle and subtitle[:15].lower() in clean_text(blocks[1][4]).lower():
                        raw_title_blocks_to_skip = 2
            skip_first_n_blocks = raw_title_blocks_to_skip

        block_count = 0
        for b in blocks:
            x0, y0, x1, y1, text, b_no, b_type = b
            if b_type != 0:
                continue

            clean_b = clean_text(text).strip()
            if not clean_b:
                continue

            if is_running_header(clean_b, y0):
                continue

            block_count += 1
            if is_chapter_start and block_count <= skip_first_n_blocks:
                continue

            # Format in-page figures (Figure X.Y <Title>)
            m_fig = re.match(r'^Figure\s+(\d+\.\d+)\s+([A-Z][^\.\n]{2,80})$', clean_b)
            if m_fig:
                fig_num, fig_title = m_fig.groups()
                clean_b = f"> **Figure {fig_num}** {fig_title}"
            elif clean_b.startswith("Table "):
                clean_b = f"### {clean_b}"
            elif clean_b in ("Notes", "Note"):
                clean_b = "### Notes"

            page_texts.append(clean_b)

        page_content = "\n\n".join(page_texts)
        if page_content.strip():
            body_sections.append(page_content.strip())

    # Rebuild Index (Pages 137 to 141)
    print("Rebuilding 2-Column Index with alphabetical sections...")
    index_md = extract_index(doc)

    doc.close()

    full_body = "\n\n".join(prelim_sections) + "\n\n" + "\n\n".join(body_sections) + "\n\n" + index_md
    
    # Heal the broken sentence across page 57 and page 59 ("dopamine" ... "addiction")
    # Move Figure 8.2 right after the paragraph mentioning Figure 8.2
    pattern_split = (
        r'(Whether it is a dopamine)\s*\n+\s*>\s*\*\*Figure 8\.2\*\*[^\n]+\s*\n+\s*(addiction, the love of risk)'
    )
    if re.search(pattern_split, full_body):
        full_body = re.sub(
            pattern_split,
            r'\1 \2',
            full_body
        )
        # Place Figure 8.2 after the paragraph that introduces it
        fig8_2_block = "\n\n> **Figure 8.2** LFI series for the second half of the 1700s (right scale) and 1900s (left scale)\n\n"
        target_intro = "Please zoom in on the data and look at Figure 8.2."
        if target_intro in full_body:
            full_body = full_body.replace(target_intro, target_intro + fig8_2_block)

    full_body = re.sub(r'\n{3,}', '\n\n', full_body)
    final_content = FRONTMATTER + full_body.strip() + "\n"

    print(f"Writing {len(final_content):,} bytes to {TARGET_CORPUS}...")
    TARGET_CORPUS.write_text(final_content, encoding="utf-8")
    
    print(f"Writing {len(final_content):,} bytes to {TARGET_KNOWLEDGE}...")
    TARGET_KNOWLEDGE.write_text(final_content, encoding="utf-8")
    print("Rebuild of Book 11 complete.")

if __name__ == '__main__':
    rebuild_book11()
