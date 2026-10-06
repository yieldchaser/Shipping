#!/usr/bin/env python3
"""
Audit all 12 books for page-by-page text coverage against their source PDFs.
"""
import sys
import re
from pathlib import Path
import pymupdf

BOOKS = [
    ("Book 1", "secondhand_bulker_predictability_duru.pdf", "secondhand_bulker_predictability_duru.md"),
    ("Book 2", "freight_rate_modelling_review_2022.pdf", "freight_rate_modelling_review_2022.md"),
    ("Book 3", "worlds_key_industry_harlaftis_tenold_valdaliso.pdf", "worlds_key_industry_harlaftis_tenold_valdaliso.md"),
    ("Book 4", "maritime_economics_macro_karakitsos_varnavides.pdf", "maritime_economics_macro_karakitsos_varnavides.md"),
    ("Book 5", "lloyds_maritime_atlas_24e.pdf", "lloyds_maritime_atlas_24e.md"),
    ("Book 6", "maritime_economics_stopford_3e.pdf", "maritime_economics_stopford_3e.md"),
    ("Book 7", "business_of_shipping_kendall.pdf", "business_of_shipping_kendall.md"),
    ("Book 8", "shipping_finance_handbook_kavussanos_visvikis.pdf", "shipping_finance_handbook_kavussanos_visvikis.md"),
    ("Book 9", "sea_and_civilization_paine.pdf", "sea_and_civilization_paine.md"),
    ("Book 10", "shipping_man_mccleery.pdf", "shipping_man_mccleery.md"),
    ("Book 11", "shipping_business_unwrapped_duru.pdf", "shipping_business_unwrapped_duru.md"),
    ("Book 12", "types_of_ships_lesson2.pdf", "types_of_ships_lesson2.md"),
]

CORPUS_DIR = Path("corpus/books")

def clean_for_search(text):
    # remove punctuation and normalize spaces
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', text)).lower()

def audit_book(tag, pdf_name, md_name):
    pdf_path = CORPUS_DIR / pdf_name
    if not pdf_path.exists():
        # Match using keywords
        words = [w for w in re.findall(r'[A-Za-z0-9]+', pdf_name) if len(w) > 4 and w.lower() not in ('world', 'shipping', 'edition')]
        if words:
            matches = list(CORPUS_DIR.glob(f"*{words[0]}*.pdf"))
            if matches:
                pdf_path = matches[0]
    md_path = CORPUS_DIR / md_name
    
    if not pdf_path.exists() or not md_path.exists():
        print(f"{tag}: Missing file(s) - pdf={pdf_path.exists()}, md={md_path.exists()}")
        return
        
    doc = pymupdf.open(pdf_path)
    md_raw = md_path.read_text(encoding='utf-8')
    md_clean = clean_for_search(md_raw)
    
    total_pages = len(doc)
    tested_pages = 0
    missing_pages = []
    
    for p_num in range(total_pages):
        page = doc[p_num]
        p_text = page.get_text()
        words = p_text.split()
        if len(words) < 25: # skip nearly empty / title pages
            continue
            
        tested_pages += 1
        
        # Take 3 distinct 5-word phrases across the page
        w_len = len(words)
        phrases = []
        for offset in [w_len // 4, w_len // 2, 3 * w_len // 4]:
            phrase = clean_for_search(" ".join(words[offset:offset+5]))
            if len(phrase.strip()) > 10:
                phrases.append(phrase.strip())
                
        # Check if at least one phrase is in md_clean
        found = any(p in md_clean for p in phrases)
        if not found:
            # try 2 more phrases at 1/8 and 7/8
            extra = [
                clean_for_search(" ".join(words[w_len // 8: w_len // 8 + 5])),
                clean_for_search(" ".join(words[7 * w_len // 8: 7 * w_len // 8 + 5]))
            ]
            if any(p in md_clean for p in extra if len(p.strip()) > 10):
                found = True
                
        if not found:
            missing_pages.append(p_num + 1)
            
    doc.close()
    pct = (tested_pages - len(missing_pages)) / tested_pages * 100 if tested_pages else 100
    print(f"{tag:<8} | PDF: {total_pages:4d} pp | Tested: {tested_pages:4d} pp | Missing: {len(missing_pages):4d} pp | Coverage: {pct:5.1f}% | {md_name[:35]}")
    if missing_pages:
        print(f"   Missing sample: {missing_pages[:15]}")

def main():
    print("=" * 100)
    print("PAGE COVERAGE AUDIT ACROSS ALL 12 BOOKS")
    print("=" * 100)
    for tag, pdf_name, md_name in BOOKS:
        audit_book(tag, pdf_name, md_name)

if __name__ == "__main__":
    main()
