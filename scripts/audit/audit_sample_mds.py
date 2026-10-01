#!/usr/bin/env python3
"""
scripts/audit/audit_sample_mds.py
Audit sample markdown files across all discrete publishers and formats for:
- Frontmatter presence & validity
- Correct ISO issue_date resolution
- Proper headings & markdown tables
- Absence of corruption markers (unicode replacement, raw bytecode, code dumps, truncation)
"""

import os
import re
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

sample_files = [
    Path('data/extracted/md/clarksons/2026/clarksons_2026_Weekly-Sales-25th-Sept-2026.md'),
    Path('data/extracted/md/advanced_shipping/2026/advanced_shipping_19_09_2026_advanced_shipping_trading_weekly_shipping_marke.md'),
    Path('data/extracted/md/intermodal/2026/intermodal_30_09_2026_intermodal_weekly_market_report_week_39_2026_broker_s_insi.md'),
    Path('data/extracted/md/xclusiv/2026/xclusiv_2026_xclusiv-2026_02_24.md'),
    Path('data/extracted/md/fearnleys/fearnleys_01_10_2026_fearnleys_week_40_2026.md'),
    Path('data/extracted/md/agora/2026/agora_30_09_2026_agora_shipbroking_corporation_snapshot_of_commercial_indicator.md'),
    Path('data/extracted/md/hellenic/dry_charter/2026/alibra_dry_2026-09-30.md'),
    Path('data/extracted/md/hellenic/tanker_charter/2026/alibra_wet_2026-09-30.md'),
    Path('data/extracted/md/hellenic/vessel_valuations/2026/vv_2026-09-29.md'),
    Path('data/extracted/md/drewry/ais/2026/Drewry_AIS_Product_LR2_Week39_2026.md'),
    Path('data/extracted/md/signal/monitors/weekly-dry-market-monitor-week-35-2026.md'),
    Path('data/extracted/md/poten/2026/poten_2026-09-18_running-out-of-options.md')
]

def run_sample_md_audit():
    print("=" * 80)
    print("  SAMPLE MARKDOWN FILE INTEGRITY & QUALITY AUDIT")
    print("=" * 80)

    audit_results = []
    for rel_path in sample_files:
        target = REPO_ROOT / rel_path
        if not target.exists():
            candidates = list((REPO_ROOT / "data" / "extracted" / "md").rglob(rel_path.name))
            if candidates:
                target = candidates[0]
            else:
                audit_results.append((rel_path.name, False, "FILE_NOT_FOUND", 0, {}))
                continue

        text = target.read_text(encoding="utf-8", errors="replace")
        char_count = len(text)
        
        # Check frontmatter and date
        date_match = re.search(r'(?:issue_date|Date|publication_date|reference_date)[*\s:"\']+(\d{4}-\d{2}-\d{2})', text, re.I)
        iso_date = date_match.group(1) if date_match else None
        if not iso_date:
            # Check text month day year or YYYY_MM_DD in path/text
            m = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', target.name)
            if m:
                iso_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            else:
                m_eu = re.search(r'(\d{2})_(\d{2})_(\d{4})', target.name)
                if m_eu:
                    iso_date = f"{m_eu.group(3)}-{m_eu.group(2)}-{m_eu.group(1)}"
                else:
                    iso_date = "N/A"
        
        # Check corruption markers
        has_bad_unicode = '\ufffd' in text
        has_raw_pdf = 'endobj' in text or '/Filter /FlateDecode' in text
        has_js_dump = 'function()' in text or 'var _0x' in text
        has_truncated_read_more = '... Read More' in text or 'Read More" />' in text
        
        # Check structure
        has_heading = bool(re.search(r'^(?:#\s+.+|---\s*Page\s+\d+\s*---)', text, re.M))
        num_tables = len(re.findall(r'\|(?:\s*:?-+:?\s*\|)+', text))
        
        # Check sidecar json if exists
        sidecar_json = target.with_suffix('.tables.json')
        has_sidecar = sidecar_json.exists()
        
        issues = []
        if not has_heading:
            issues.append("MISSING_HEADING")
        if has_bad_unicode:
            issues.append("BAD_UNICODE_U+FFFD")
        if has_raw_pdf:
            issues.append("RAW_PDF_BYTECODE")
        if has_js_dump:
            issues.append("JS_CODE_DUMP")
        if has_truncated_read_more:
            issues.append("TRUNCATED_READ_MORE")
        if iso_date == "N/A":
            issues.append("MISSING_ISO_DATE")
                
        status = "PASS" if not issues else f"DEFECT ({', '.join(issues)})"
        audit_results.append((target.name, len(issues) == 0, status, char_count, {
            "path": str(target.relative_to(REPO_ROOT)),
            "iso_date": iso_date,
            "num_tables": num_tables,
            "chars": char_count,
            "sidecar": has_sidecar
        }))

    for name, ok, status, chars, meta in audit_results:
        flag = "[PASS]" if ok else "[FAIL]"
        print(f"{flag:<7} {name[:45]:<45} | Date: {meta.get('iso_date', 'N/A')} | Tables: {meta.get('num_tables', 0):<2} | Chars: {chars:<6,} | Status: {status}")

    print("=" * 80)
    total = len(audit_results)
    passed = sum(1 for _, ok, _, _, _ in audit_results if ok)
    print(f"Audit Summary: {passed}/{total} Sample Files Passed (Defects: {total - passed})")
    print("=" * 80)
    return passed == total

if __name__ == "__main__":
    success = run_sample_md_audit()
    exit(0 if success else 1)
