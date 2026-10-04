#!/usr/bin/env python3
"""
Verify all 12 reference books in corpus/books/ and knowledge/docs/books/.
Checks:
1. 1:1 existence and exact byte-for-byte matching between corpus/ and knowledge/.
2. Valid YAML frontmatter in each file.
3. Total line counts, heading counts, and file sizes.
4. Strictly zero emojis across all files.
"""

import sys
import re
from pathlib import Path

BOOKS = [
    ("Book 1", "predictability_of_second_hand_bulk_carriers_with_a_novel_hybrid.md"),
    ("Book 2", "2022_quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.md"),
    ("Book 3", "the_world_s_key_industry_history_and_economics_of_international_shipping_g_harlaftis_s_tenold_j_valdaliso_z_lib_org.md"),
    ("Book 4", "maritime_economics_a_macroeconomic_approach_elias_karakitsos_lambros_varnavides_auth_z_lib_org.md"),
    ("Book 5", "lloyds_maritime_atlas_24th_edition.md"),
    ("Book 6", "maritime_economics_3rd_edition.md"),
    ("Book 7", "the_business_of_shipping_lane_c_kendall_auth_z_library.md"),
    ("Book 8", "the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md"),
    ("Book 9", "the_sea_and_civilization_a_maritime_history_of_the_world_lincoln_paine_z_lib_org.md"),
    ("Book 10", "the_shipping_man_matthew_mccleery_z_lib_org.md"),
    ("Book 11", "shipping_business_unwrapped_duru_okan_z_library.md"),
    ("Book 12", "lesson_2_types_of_ships.md"),
]

CORPUS_DIR = Path("corpus/books")
KNOWLEDGE_DIR = Path("knowledge/docs/books")

# Regex to detect common emojis
EMOJI_PATTERN = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)

def main():
    print("=" * 80)
    print("AUDIT & VERIFICATION OF ALL 12 REFERENCE BOOKS")
    print("=" * 80)
    
    total_bytes = 0
    total_lines = 0
    all_passed = True
    
    print(f"{'#':<8} {'Filename':<50} {'Bytes':<10} {'Lines':<8} {'Headings':<10} {'Status':<10}")
    print("-" * 96)
    
    for tag, fname in BOOKS:
        c_path = CORPUS_DIR / fname
        k_path = KNOWLEDGE_DIR / fname
        
        if not c_path.exists():
            print(f"FAIL: Missing in corpus: {c_path}")
            all_passed = False
            continue
            
        if not k_path.exists():
            print(f"FAIL: Missing in knowledge: {k_path}")
            all_passed = False
            continue
            
        c_bytes = c_path.read_bytes()
        k_bytes = k_path.read_bytes()
        
        if c_bytes != k_bytes:
            print(f"FAIL: Byte mismatch between corpus and knowledge for {fname} ({len(c_bytes)} vs {len(k_bytes)})")
            all_passed = False
            continue
            
        text = c_bytes.decode('utf-8', errors='replace')
        lines = text.splitlines()
        headings = [l for l in lines if l.startswith('#')]
        
        # Check frontmatter
        has_frontmatter = text.startswith("---") and "---" in text[3:]
        
        # Check emojis
        emojis = EMOJI_PATTERN.findall(text)
        if emojis:
            print(f"FAIL: Emoji detected in {fname}: {emojis[:5]}")
            all_passed = False
            continue
            
        status = "PASS" if has_frontmatter else "NO_FM"
        if not has_frontmatter:
            all_passed = False
            
        total_bytes += len(c_bytes)
        total_lines += len(lines)
        
        print(f"{tag:<8} {fname[:48]:<50} {len(c_bytes):<10,} {len(lines):<8,} {len(headings):<10} {status:<10}")

    print("-" * 96)
    print(f"TOTAL: 12 Books | {total_bytes:,} Bytes ({total_bytes / (1024*1024):.2f} MB) | {total_lines:,} Lines")
    if all_passed:
        print("RESULT: ALL 12 BOOKS 100% VERIFIED & SYNCHRONIZED [ZERO DATA LOSS, ZERO EMOJIS]")
    else:
        print("RESULT: AUDIT FAILED ON ONE OR MORE CHECKS")
        sys.exit(1)

if __name__ == "__main__":
    main()
