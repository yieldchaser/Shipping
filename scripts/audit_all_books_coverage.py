#!/usr/bin/env python3
"""
Audit all 12 books for page-by-page text coverage against their source PDFs.
"""
import sys
import re
from pathlib import Path
import pymupdf

BOOKS = [
    ("Book 1", "Predictability of second-hand bulk carriers with a novel hybrid.pdf", "predictability_of_second_hand_bulk_carriers_with_a_novel_hybrid.md"),
    ("Book 2", "2022-Quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.pdf", "2022_quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.md"),
    ("Book 3", "The World's Key Industry History and Economics of International Shipping (G. Harlaftis, S. Tenold, J. Valdaliso) (z-lib.org).pdf", "the_world_s_key_industry_history_and_economics_of_international_shipping_g_harlaftis_s_tenold_j_valdaliso_z_lib_org.md"),
    ("Book 4", "Maritime Economics A Macroeconomic Approach (Elias Karakitsos, Lambros Varnavides (auth.)) (z-lib.org).pdf", "maritime_economics_a_macroeconomic_approach_elias_karakitsos_lambros_varnavides_auth_z_lib_org.md"),
    ("Book 5", "Lloyds_Maritime_Atlas_24th_Edition.pdf", "lloyds_maritime_atlas_24th_edition.md"),
    ("Book 6", "Maritime economics 3rd edition.pdf", "maritime_economics_3rd_edition.md"),
    ("Book 7", "The Business of Shipping (Lane C. Kendall (auth.)) (Z-Library).pdf", "the_business_of_shipping_lane_c_kendall_auth_z_library.md"),
    ("Book 8", "The International Handbook of Shipping Finance Theory and Practice (Manolis G. Kavussanos, Ilias D. Visvikis (eds.)) (z-lib.org).pdf", "the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md"),
    ("Book 9", "The Sea and Civilization A Maritime History of the World (Lincoln Paine) (z-lib.org).pdf", "the_sea_and_civilization_a_maritime_history_of_the_world_lincoln_paine_z_lib_org.md"),
    ("Book 10", "The Shipping Man (Matthew McCleery) (z-lib.org).pdf", "the_shipping_man_matthew_mccleery_z_lib_org.md"),
    ("Book 11", "Shipping Business Unwrapped. (Duru, Okan) (Z-Library).pdf", "shipping_business_unwrapped_duru_okan_z_library.md"),
    ("Book 12", "Lesson-2-Types-of-Ships.pdf", "lesson_2_types_of_ships.md"),
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
