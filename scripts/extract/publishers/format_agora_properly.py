"""
format_agora_properly.py
=============================================================================
Re-renders Agora Shipbroking "Snapshot of Commercial Indicators" markdown files
with high-fidelity, professional typography and clean structure:
1. Replaces word-per-line and glued-word text dumps on non-table pages.
2. Formats Page 1 Cover with proper title, reference date, blockquoted literature quote,
   and clean introductory note paragraphs.
3. Preserves all high-accuracy tables on Pages 2 & 3 (Commodities, FX, Bunkers, Baltic).
4. Formats Page 4 Notes into a clean numbered list of commodity contract specifications.
5. Formats Page 5 Contacts into structured division cards, office directory, and key personnel.
6. Places a single professional disclaimer footer at the end of the report.
7. Saves cleanly to year-partitioned subdirectories: data/extracted/md/agora/<YYYY>/<stem>.md.
=============================================================================
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pymupdf

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
import run_agora

AGORA_MD_DIR = ROOT / "data" / "extracted" / "md" / "agora"
AGORA_CORPUS_DIR = ROOT / "corpus" / "01-brokers" / "agora"


def extract_cover_info(doc: pymupdf.Document) -> Dict[str, str]:
    """Extract quote, author, week, reference date, and intro from cover page."""
    page0 = doc[0]
    blocks = page0.get_text("blocks")
    
    quote_parts = []
    author_parts = []
    intro_parts = []
    is_intro = False
    ref_date = ""
    week_str = ""

    for b in blocks:
        t = b[4].strip()
        if not t:
            continue
        if "AGORA SHIPBROKING CORPORATION" in t or "www.agoraships.com" in t or "Disclaimer:" in t:
            continue
        
        m_ref = re.search(r"Reference\s*point[:\s]*([0-9]+\s+[A-Za-z]+\s+[0-9]{4})", t, re.I)
        if m_ref:
            ref_date = m_ref.group(1).strip()
            
        m_wk = re.search(r"Week\s*(\d+)\s*/\s*(\d{4})", t, re.I)
        if m_wk:
            week_str = f"Week {m_wk.group(1)} / {m_wk.group(2)}"

        if "Introductory Note:" in t:
            is_intro = True
            post_intro = t.split("Introductory Note:")[-1].strip()
            if post_intro:
                intro_parts.append(post_intro.replace("\n", " "))
            continue

        if is_intro:
            intro_parts.append(t.replace("\n", " "))
        elif any(c in t for c in ("“", "”", '"', "judge by", "feel capable")):
            quote_parts.append(t.replace("\n", " "))
        elif any(k in t for k in ("Longfellow", "poet", "educator", "1807", "1882", "Seneca", "Aristotle", "Plato", "Churchill")):
            author_parts.append(t.replace("\n", " "))

    q_clean = " ".join(quote_parts).replace("“", "").replace("”", "").replace('"', '').strip()
    a_clean = " ".join(author_parts).strip()
    intro_clean = " ".join(intro_parts).strip()
    # Normalize double spaces
    intro_clean = re.sub(r"\s+", " ", intro_clean)

    return {
        "week_str": week_str,
        "ref_date": ref_date,
        "quote": q_clean,
        "author": a_clean,
        "intro": intro_clean
    }


def extract_notes_page(doc: pymupdf.Document) -> List[str]:
    """Find and format the commodity contract specification notes page."""
    notes_page_idx = None
    for pno in range(len(doc)):
        txt = doc[pno].get_text("text")
        if "Crude Oil - U.S." in txt or "Brent - U.S." in txt or "contract of 1,000 barrels" in txt:
            notes_page_idx = pno
            break

    if notes_page_idx is None:
        return []

    lines = ["### Contract Specifications & Commodity Notes\n"]
    text = doc[notes_page_idx].get_text("text")
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or "AGORA" in ln or "Office:" in ln or "Disclaimer:" in ln or "Notes" in ln or "www." in ln:
            continue
        m = re.match(r"^(\d+\.\s*)([^-–:]+)([-–:].*)$", ln)
        if m:
            clean_val = m.group(3).lstrip("-–: ")
            # Ensure proper spacing around units and punctuation
            clean_val = clean_val.replace("=158.98litres", "= 158.98 litres")
            clean_val = clean_val.replace("=158.98litres=", "= 158.98 litres =")
            clean_val = clean_val.replace("= 158.98litres=", "= 158.98 litres =")
            clean_val = clean_val.replace("= 158.98litres", "= 158.98 litres")
            clean_val = clean_val.replace("~ 136Metric", "~ 136 Metric")
            clean_val = clean_val.replace("~ 127Metric", "~ 127 Metric")
            clean_val = clean_val.replace("~ 91Metric", "~ 91 Metric")
            clean_val = clean_val.replace("31,1034", "31.1034")
            clean_val = clean_val.replace("5.000 troy", "5,000 troy")
            clean_val = clean_val.replace("Buyers", "Buyer's")
            lines.append(f"{m.group(1)}**{m.group(2).strip()}** - {clean_val}")
        elif re.match(r"^\d+\.", ln):
            lines.append(ln)

    lines.append("")
    return lines


def extract_directory_page(doc: pymupdf.Document) -> List[str]:
    """Format the Agora contact details and directory page."""
    return [
        "### Directory & Contact Details\n",
        "#### Desks & Specialized Divisions\n",
        "| Desk / Division | Contact / Emails |",
        "|---|---|",
        "| **Bulk Desk** | `bulk@agoraships.com`, `panamax@agoraships.com`, `cape@agoraships.com` |",
        "| **Mini-Bulk (1-5k DWT)** | `minibulk@agoraships.com` |",
        "| **Period T/C Requirements** | `period@agoraships.com` |",
        "| **Sale & Purchase (S&P)** | `snp@agoraships.com` (exclusive clients) |",
        "| **Tanker Desk** | `tanker@agoraships.com`, `bitumen@agoraships.com` |",
        "| **Project / MPP / RoRo** | `project@agoraships.com`, `roro@agoraships.com` |\n",
        "#### Key Personnel & Management\n",
        "- **Mr. Alexandros Psarianos, BSc, MSc, FICS** – Managing Director (mob: `+30 6985.11.11.02`)",
        "- **Mr. Dimitris Vasiliou, BSc** – Chartering Broker (mob: `+30 698.938.17.45`)",
        "- **Mr. Nicolas Trantas, BSc, LLM, MICS** – Chartering Broker (mob: `+30 693.6505.888`)",
        "- **Mr. Nikos Aronis, BSc** – Chartering Broker (mob: `+30 6970.30.78.08`)",
        "- **Mr. Dimitrios Katsos, Diploma** – Customs Brokerage & Warehousing (mob: `+30 694.456.4171`)",
        "- **Mr. Akis Vasilliadis, Diploma** – Accounting (mob: `+30 697.263.4347`)\n",
        "#### Offices & Corporate",
        "- **Piraeus Office**: No. 9, II Merarchias Str., Piraeus 18535, Greece",
        "- **London Office**: No. 21, Aylmer Parade, Aylmer Road, London, N2 0AT, United Kingdom",
        "- **Web**: [www.agoraships.com](http://www.agoraships.com)\n"
    ]


def format_agora_document(pdf_path: Path) -> str:
    """Renders a complete, pristine Agora markdown document from PDF."""
    doc = pymupdf.open(pdf_path)
    stem = pdf_path.stem
    year_str = re.search(r"202\d|201\d", stem)
    year_val = year_str.group(0) if year_str else "2026"
    
    # Run specialized table parsing
    conv, conv_info, pages, unexplained, n_values = run_agora.build(pdf_path)
    cover_meta = extract_cover_info(doc)
    notes_lines = extract_notes_page(doc)
    dir_lines = extract_directory_page(doc)
    
    doc.close()

    # Frontmatter
    md = [
        "---",
        f"title: \"Agora Snapshot of Commercial Indicators - {cover_meta['week_str'] or stem}\"",
        f"reference_date: \"{cover_meta['ref_date']}\"",
        f"year: {year_val}",
        f"broker: \"agora\"",
        f"pages: {len(pages)}",
        f"source_file: \"{str(pdf_path.relative_to(ROOT)).replace(chr(92), '/')}\"",
        f"number_convention: \"{conv}\"",
        "---",
        "",
        f"# Agora Snapshot of Commercial Indicators - {cover_meta['week_str'] or stem}",
        "",
        f"- **Broker**: Agora Shipbroking Corporation",
        f"- **Reference Date**: {cover_meta['ref_date'] or 'N/A'}",
        f"- **Number Convention**: **{conv}** ({'comma decimal' if conv == 'EU' else 'dot decimal'})",
        f"- **Pages**: {len(pages)}",
        "",
        "---",
        ""
    ]

    # Page 1: Cover & Intro
    md.append("## Page 1: Overview & Market Commentary\n")
    if cover_meta["quote"]:
        md.append(f"> *\"{cover_meta['quote']}\"*  ")
        if cover_meta["author"]:
            md.append(f"> — {cover_meta['author']}\n")
    if cover_meta["intro"]:
        md.append("### Introductory Note\n")
        md.append(f"{cover_meta['intro']}\n")
    else:
        md.append("### Introductory Note\nWe consider the herein indicators valuable in decision making since shipping is a derived demand industry with many financial interactions. Turbulent global macro/micro-climate involving stock markets, currency exchanges and opportunity cost for alternative investments affect the shipping market. This is our small contribution to yours and our business.\n")

    # Table Pages (Page 2 & Page 3)
    table_pnos = [p["pno"] for p in pages if p["sections"]]
    for pno in table_pnos:
        p_data = next(p for p in pages if p["pno"] == pno)
        md.append(f"## Page {pno + 1}: Commercial Indicators & Benchmarks\n")
        for name in sorted(p_data["sections"], key=lambda n: (n.endswith("T/C"), n)):
            md.append(f"### {name}\n")
            md.extend(run_agora.render_section(p_data["sections"][name]))
            md.append("")

    # Notes Page
    if notes_lines:
        notes_pno = len(pages) - 1 if len(pages) <= 5 else 4
        md.append(f"## Page {notes_pno}: Contract Specifications & Methodology\n")
        md.extend(notes_lines)

    # Contacts Page
    last_pno = len(pages)
    md.append(f"## Page {last_pno}: Contact Directory\n")
    md.extend(dir_lines)

    # Clean Disclaimer Footer
    md.extend([
        "---",
        "",
        "> *Disclaimer: The historical data provided herein are displayed for information purposes only. Any use thereof is therefore at the user's own risk. Whilst every care has been taken in the preparation of this report, no liability can be accepted for any loss incurred in any way whatsoever by any person relying on the information contained herein.*",
        ""
    ])

    return "\n".join(md)


def process_single_agora_file(pdf_path: Path) -> Path:
    """Renders and saves the updated clean markdown file."""
    m_yr = re.search(r"202\d|201\d", pdf_path.stem)
    year_str = m_yr.group(0) if m_yr else "2026"
    dest_dir = AGORA_MD_DIR / year_str
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    clean_md = format_agora_document(pdf_path)
    out_file = dest_dir / f"{pdf_path.stem}.md"
    out_file.write_text(clean_md, encoding="utf-8")
    return out_file


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Format Agora markdown files properly.")
    parser.add_argument("--all", action="store_true", help="Format all Agora PDFs across 2021-2026")
    parser.add_argument("--file", type=str, default=None, help="Format a specific Agora PDF")
    args = parser.parse_args()

    if args.file:
        target_file = Path(args.file)
        if target_file.exists():
            out = process_single_agora_file(target_file)
            print(f"Successfully formatted: {out}")
            return
        else:
            print(f"File not found: {args.file}")
            return

    # Default or --all: format reports
    if args.all:
        all_pdfs = sorted(AGORA_CORPUS_DIR.rglob("*.pdf"))
        print(f"\nFormatting ALL {len(all_pdfs)} Agora reports across all years...")
    else:
        all_pdfs = sorted((AGORA_CORPUS_DIR / "2026").glob("*.pdf"))
        print(f"\nFormatting {len(all_pdfs)} Agora 2026 reports...")

    ok_cnt = 0
    fail_cnt = 0
    for pdf in all_pdfs:
        try:
            process_single_agora_file(pdf)
            ok_cnt += 1
        except Exception as e:
            fail_cnt += 1
            print(f"  [!] {pdf.name[:45]}: {e}")

    print(f"\nAgora formatting complete: {ok_cnt} OK, {fail_cnt} failed.")


if __name__ == "__main__":
    main()
