#!/usr/bin/env python3
"""
scripts/tools/normalize_banchero_costa_md.py
============================================
Normalizes formatting across Banchero Costa weekly market reports:
1. Strips running header banners from PDF pages:
   - '# COMMENT'
   - '# MARKET REPORT – WEEK XX/YYYY N'
   - '# CHARTERING MARKET REPORT – WEEK XX/YYYY N'
   - 'RESEARCH I', 'RESEARCH 2'
   - '<!-- page N -->'
2. Standardizes document header hierarchy:
   - '# Banchero Costa Weekly Market Report - Week {wk}, {yr}'
   - '## Weekly Macro Insight: {Essay Title}'
3. Reassembles choppy, single-sentence lines into flowing, publication-grade prose paragraphs
   without altering any data or table rows.
4. Corrects inverted sentences resulting from PDF column breaks.
5. Cleans typographical spacing and OCR join errors ('mln tin' -> 'mln t in', 'laycan18' -> 'laycan 18', 'y- o-y' -> 'y-o-y').
6. Preserves 100% of tables, IMO numbers, prices, and time series data intact.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MD_DIR = ROOT / "data" / "extracted" / "md" / "banchero_costa"
LLAMA_V2_DIR = ROOT / "data" / "extracted" / "llamaparse_banchero_v2"


def is_structural_line(s: str) -> bool:
    """Check if line is structural (headers, tables, lists, code fences, blockquotes, dividers)."""
    if not s:
        return False
    if s.startswith(('#', '|', '>', '```', '---')):
        return True
    if s.startswith(('- ', '* ', '+ ')):
        return True
    if re.match(r'^\d+\.\s', s):
        return True
    return False


def normalize_banchero_content(text: str, stem: str = "") -> str:
    # 1. Parse YAML frontmatter if present
    frontmatter = ""
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = "---" + parts[1] + "---\n\n"
            body = parts[2]

    # Extract week and year from frontmatter or filename
    m_wk = re.search(r'report_week:\s*(\d+)', frontmatter)
    m_yr = re.search(r'year:\s*(\d+)', frontmatter)
    wk_str = m_wk.group(1) if m_wk else ""
    yr_str = m_yr.group(1) if m_yr else ""

    if not wk_str or not yr_str:
        m_stem = re.search(r'banchero_costa_(\d{4})_W?(\d{1,2})', stem)
        if m_stem:
            yr_str = yr_str or m_stem.group(1)
            wk_str = wk_str or m_stem.group(2)

    # 2. Fix typos/spacing in body
    body = re.sub(r'\bmln tin\b', 'mln t in', body)
    body = re.sub(r'\blaycan(\d+)', r'laycan \1', body)
    body = re.sub(r'y-\s*o-y', 'y-o-y', body)
    body = re.sub(r'(\b\d{1,3}(?:\.\d+)?%)\s+((?:In|On|At|The|This|However|Moreover|Meanwhile)\b)', r'\1. \2', body)

    # 3. Strip running headers and footer artifacts
    body = re.sub(r'(?m)^[ \t]*#\s+COMMENT\s*\n+', '', body)
    body = re.sub(r'(?m)^[ \t]*#\s+(?:CHARTERING\s+)?MARKET REPORT\s*[-–]\s*WEEK\s*\d+/\d{4}(?:\s+\d+)?\s*\n+', '', body)
    body = re.sub(r'(?m)^[ \t]*RESEARCH\s*[IVX\d]*\s*\n+', '', body)
    body = re.sub(r'(?m)^[ \t]*<!--\s*page\s*\d+\s*-->\s*\n+', '', body)

    # 4. If top starts with an article title like "# EUROPEAN UNION COAL IMPORTS", structure it
    top_header = ""
    m_art = re.search(r'^\s*#\s+([A-Z0-9\s,\-\'\/\&]+)\n', body)
    if m_art:
        art_title = m_art.group(1).strip()
        body = body[m_art.end():]
        if wk_str and yr_str:
            top_header = f"# Banchero Costa Weekly Market Report - Week {wk_str}, {yr_str}\n\n## Weekly Macro Insight: {art_title.title()}\n\n"
        else:
            top_header = f"## Weekly Macro Insight: {art_title.title()}\n\n"

    # 5. Process sections and group prose sentences into flowing paragraphs
    lines = body.splitlines()
    out_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Structural lines pass through directly
        if is_structural_line(stripped):
            out_lines.append(line)
            i += 1
            continue

        if not stripped:
            out_lines.append('')
            i += 1
            continue

        # Collect consecutive prose paragraphs
        prose_blocks = []
        while i < len(lines):
            l = lines[i]
            s = l.strip()
            if not s:
                i += 1
                continue
            if is_structural_line(s):
                break
            # Collapse internal newline wraps within this block
            clean_s = " ".join(s.split())
            prose_blocks.append(clean_s)
            i += 1

        if not prose_blocks:
            continue

        # Group prose_blocks into natural paragraphs
        grouped_paras = []
        curr_para = []
        curr_words = 0

        for b in prose_blocks:
            words = len(b.split())

            is_transition = any(b.startswith(marker) for marker in [
                'In terms of', 'The most important', 'In 1Q', 'In Jan-Mar',
                'In the Atlantic', 'Quite some activity', 'Nothing to report',
                'Early on the week', 'Later, for a cargo', 'On P1A', 'On P2A',
                'Activity in the Black', 'Declining rates', 'Given the disappoint',
                'Despite the holidays', 'An Ultramax was', 'The market was active',
                'A shallow', 'A 56,000', 'Despite limited activity', 'Russian business',
                'A cargo of', '**The European Union**', 'The European Union'
            ])

            is_sentence_boundary = False
            if curr_para:
                prev_text = curr_para[-1].rstrip()
                if prev_text and prev_text[-1] in ('.', '!', '?', '"', "'", '”', '’', ':'):
                    is_sentence_boundary = True

            if curr_para and is_sentence_boundary and (not b or not b[0].islower()) and curr_words >= 60 and (curr_words >= 160 or (curr_words >= 80 and is_transition)):
                grouped_paras.append(" ".join(curr_para))
                curr_para = [b]
                curr_words = words
            else:
                curr_para.append(b)
                curr_words += words

        if curr_para:
            grouped_paras.append(" ".join(curr_para))

        for gp in grouped_paras:
            # Fix any inverted sentences from column wraps
            if "in ballast towards Spore/ECSAm; that could help clear up the tonnage list in Pacific. Given the disappoint returns many owners decided to send their vessels" in gp:
                gp = gp.replace(
                    "in ballast towards Spore/ECSAm; that could help clear up the tonnage list in Pacific. Given the disappoint returns many owners decided to send their vessels",
                    "Given the disappointed returns many owners decided to send their vessels in ballast towards Spore/ECSAm; that could help clear up the tonnage list in Pacific."
                )
            out_lines.append(gp)
            out_lines.append('')

    # Clean redundant blank line runs
    res = frontmatter + top_header + "\n".join(out_lines)
    res = re.sub(r'\n{3,}', '\n\n', res)
    return res.strip() + '\n'


def run_sweep():
    print("================================================================================")
    print("STARTING BANCHERO COSTA MARKDOWN NORMALIZATION")
    print("================================================================================")

    targets = []
    if MD_DIR.exists():
        targets.extend(list(MD_DIR.rglob("*.md")))
    if LLAMA_V2_DIR.exists():
        targets.extend(list(LLAMA_V2_DIR.rglob("*.md")))

    print(f"Discovered {len(targets)} markdown files to normalize across Banchero Costa.")

    modified = 0
    hdr_cleared = 0
    choppy_cleared = 0

    hdr_pat = re.compile(r'(?m)^[ \t]*#{1,3}\s+(?:COMMENT|MARKET REPORT\s*[-–]\s*WEEK\s*\d+/\d{4}\s*\d*|RESEARCH\s*[IVX\d]*|CHARTERING MARKET REPORT\s*[-–]\s*WEEK\s*\d+/\d{4}\s*\d*)')

    for p in targets:
        orig = p.read_text(encoding="utf-8", errors="ignore")
        had_hdr = bool(hdr_pat.search(orig))
        
        normalized = normalize_banchero_content(orig, p.stem)
        
        if normalized != orig:
            p.write_text(normalized, encoding="utf-8")
            modified += 1
            if had_hdr:
                hdr_cleared += 1

    print(f"Successfully processed {len(targets)} files.")
    print(f"Files modified: {modified}")
    print(f"Running header artifacts cleared: {hdr_cleared}")
    print("================================================================================")


if __name__ == "__main__":
    run_sweep()
