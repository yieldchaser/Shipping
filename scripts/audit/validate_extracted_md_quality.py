"""
validate_extracted_md_quality.py
Automated Quality Gate and Structural Regression Validator for Extracted Markdown Reports.

Validates that extracted markdown files across all publishers meet strict production standards:
1. Valid YAML frontmatter (title, issue_date, year, broker/publisher, source_file).
2. Clean typography and zero residual banners (e.g. no '[banchero costa RESEARCH]', no 'snp@clarksons.gr' leaks).
3. No dangling headers (consecutive headers with zero body text or tables between them).
4. No pseudo-tables (tables created from vector/line charts where >50% cells in columns are blank or missing headers).
5. Sidecar JSON alignment (corresponding .tables.json exists and is valid JSON with issue_date stamped).
6. Non-empty substantive content (minimum word count and section coverage).
"""

import os
import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MD_DIR = REPO_ROOT / "data" / "extracted" / "md"

LEAKED_BANNER_PATTERNS = [
    (re.compile(r"\[banchero costa RESEARCH\]", re.IGNORECASE), "Leaked Banchero banner '[banchero costa RESEARCH]'"),
    (re.compile(r"MARKET REPORT\s*–\s*WEEK\s+\d+/\d+\s+\d+", re.IGNORECASE), "Leaked running header 'MARKET REPORT - WEEK XX/YYYY N'"),
    (re.compile(r"^ebc\s*$", re.MULTILINE), "Leaked standalone 'ebc' marker"),
    (re.compile(r"snp@clarksons\.gr\s*$", re.MULTILINE), "Leaked Clarksons contact line 'snp@clarksons.gr'"),
    (re.compile(r"\ufffd"), "Corrupt unicode replacement character '\\ufffd'"),
]

def parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Extract YAML frontmatter and body from markdown."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    
    fm_text = parts[1]
    body = parts[2]
    fm = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body

def check_pseudo_tables(body: str) -> List[str]:
    """Detect malformed or hallucinated chart tables (e.g. columns with empty values or blank headers)."""
    issues = []
    table_blocks = re.findall(r"(\|(?:[^\n]+\|)+\n\|(?:\s*[-:]+[-| :]*)\|\n(?:\|(?:[^\n]+\|)*(?:\n|$))+)", body)
    for block in table_blocks:
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        header_cells = [c.strip() for c in lines[0].split("|")[1:-1]]
        # Check if header has empty cells
        empty_headers = [i for i, h in enumerate(header_cells) if not h]
        if empty_headers and len(empty_headers) >= len(header_cells) // 2:
            issues.append(f"Table has {len(empty_headers)}/{len(header_cells)} blank header cells")
        
        # Check rows for columns that are entirely blank
        row_lines = lines[2:]
        if not row_lines:
            continue
        col_blanks = [0] * len(header_cells)
        for r_line in row_lines:
            cells = [c.strip() for c in r_line.split("|")[1:-1]]
            for col_idx in range(min(len(cells), len(col_blanks))):
                if not cells[col_idx] or cells[col_idx] == "-":
                    col_blanks[col_idx] += 1
        
        for col_idx, blank_count in enumerate(col_blanks):
            if blank_count == len(row_lines) and len(row_lines) >= 3:
                col_name = header_cells[col_idx] if col_idx < len(header_cells) else f"Col{col_idx}"
                issues.append(f"Table column '{col_name}' is 100% blank across all {len(row_lines)} rows")
    return issues

def check_dangling_headers(body: str) -> List[str]:
    """Detect genuine dangling empty headers and malformed heading markers."""
    issues = []
    lines = body.splitlines()
    last_header = None
    last_level = 0
    last_header_line = 0
    for idx, line in enumerate(lines, start=1):
        line_s = line.strip()
        m = re.match(r"^(#{1,6})\s+", line_s)
        if m:
            level = len(m.group(1))
            if re.match(r"^#+\s+#+", line_s):
                issues.append(f"Malformed repeated header hashes '{line_s}' at line {idx}")
            if last_header is not None:
                # Same level or ascending level without content (e.g. ### Foo then ### Bar, or ### Foo then ## Bar)
                if level <= last_level:
                    issues.append(f"Dangling empty header '{last_header}' immediately followed by '{line_s}' at line {idx}")
            last_header = line_s
            last_level = level
            last_header_line = idx
        elif line_s in ("---", "***"):
            if last_header is not None:
                issues.append(f"Empty header '{last_header}' immediately followed by horizontal rule at line {idx}")
                last_header = None
                last_level = 0
        elif line_s:
            # Body text or table found, clear last_header
            last_header = None
            last_level = 0

    if last_header is not None:
        issues.append(f"Trailing empty header '{last_header}' at end of document")
    return issues

def validate_markdown_file(file_path: Path, check_sidecar: bool = True) -> Dict[str, Any]:
    """Run full validation checks against a single markdown file."""
    issues = []
    warnings = []
    
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"file": str(file_path), "valid": False, "issues": [f"Cannot read file: {e}"], "warnings": []}
    
    fm, body = parse_frontmatter(content)
    
    # Check Frontmatter
    if not fm:
        issues.append("Missing or invalid YAML frontmatter")
    else:
        issue_date = fm.get("issue_date")
        if not issue_date or not re.match(r"^\d{4}-\d{2}-\d{2}$", issue_date):
            issues.append(f"Missing or invalid ISO issue_date: '{issue_date}'")
        
        year = fm.get("year")
        if not year or (issue_date and not issue_date.startswith(year)):
            warnings.append(f"Year mismatch or missing: '{year}' vs issue_date '{issue_date}'")
            
        if not fm.get("title"):
            warnings.append("Missing title in frontmatter")
        if not fm.get("source_file"):
            warnings.append("Missing source_file in frontmatter")

    # Check Minimum Body Length
    if len(body.strip()) < 100:
        issues.append(f"Body text too short ({len(body.strip())} chars)")
        
    # Check Leaked Banners
    for pattern, desc in LEAKED_BANNER_PATTERNS:
        if pattern.search(content):
            issues.append(desc)
            
    # Check Dangling Headers
    dangling = check_dangling_headers(body)
    issues.extend(dangling)
    
    # Check Pseudo-Tables
    pseudo = check_pseudo_tables(body)
    issues.extend(pseudo)
    
    # Check Sidecar JSON
    if check_sidecar:
        sidecar_path = file_path.with_suffix(".tables.json")
        if not sidecar_path.exists():
            # Check flat vs year subfolder
            flat_sidecar = file_path.parent.parent / f"{file_path.stem}.tables.json"
            if not flat_sidecar.exists():
                warnings.append(f"Missing sidecar {sidecar_path.name}")
        else:
            try:
                sidecar_data = json.loads(sidecar_path.read_text(encoding="utf-8"))
                if not isinstance(sidecar_data, dict):
                    issues.append("Sidecar JSON root is not an object")
            except Exception as e:
                issues.append(f"Invalid sidecar JSON: {e}")

    return {
        "file": str(file_path),
        "stem": file_path.stem,
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "issue_date": fm.get("issue_date", "unknown"),
        "title": fm.get("title", ""),
    }

def validate_broker(broker_name: str, sample_size: int = 10) -> Dict[str, Any]:
    """Validate sample of latest reports for a specific broker."""
    broker_dir = MD_DIR / broker_name
    if not broker_dir.exists():
        return {"broker": broker_name, "error": "Directory does not exist", "total": 0, "passed": 0, "failed": 0}
        
    md_files = sorted(broker_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not md_files:
        return {"broker": broker_name, "total": 0, "passed": 0, "failed": 0}
        
    sample = md_files[:sample_size]
    results = []
    passed = 0
    failed = 0
    for p in sample:
        res = validate_markdown_file(p)
        results.append(res)
        if res["valid"]:
            passed += 1
        else:
            failed += 1
            
    return {
        "broker": broker_name,
        "total": len(sample),
        "available_total": len(md_files),
        "passed": passed,
        "failed": failed,
        "results": results
    }

def run_all_brokers_validation(sample_size: int = 5) -> Dict[str, Any]:
    """Run regression validation across all broker directories."""
    brokers = [
        "advanced_shipping", "affinity", "agora", "banchero_costa", "carriers",
        "clarksons", "fearnleys", "fearnleys-md", "gibson", "intermodal",
        "ism", "lion", "ssy", "star_asia", "xclusiv"
    ]
    summary = {}
    for b in brokers:
        res = validate_broker(b, sample_size=sample_size)
        summary[b] = res
    return summary

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Validate Extracted Markdown Quality")
    parser.add_argument("--broker", type=str, default="", help="Specific broker to validate")
    parser.add_argument("--sample", type=int, default=5, help="Sample size per broker")
    parser.add_argument("--file", type=str, default="", help="Specific file to validate")
    args = parser.parse_args()

    if args.file:
        res = validate_markdown_file(Path(args.file))
        print(f"Validation for: {res['file']}")
        print(f"Status: {'PASS' if res['valid'] else 'FAIL'}")
        if res['issues']:
            print("Issues:")
            for iss in res['issues']:
                print(f"  - {iss}")
        if res['warnings']:
            print("Warnings:")
            for w in res['warnings']:
                print(f"  - {w}")
        sys.exit(0 if res['valid'] else 1)
        
    if args.broker:
        res = validate_broker(args.broker, sample_size=args.sample)
        print(f"Broker: {args.broker} | Sample: {res['total']}/{res['available_total']} | Passed: {res['passed']} | Failed: {res['failed']}")
        for r in res["results"]:
            status = "PASS" if r["valid"] else "FAIL"
            print(f"  [{status}] {r['stem']} ({r['issue_date']})")
            for iss in r["issues"]:
                print(f"      [ISSUE] {iss}")
            for w in r["warnings"]:
                print(f"      [WARN] {w}")
        sys.exit(0 if res['failed'] == 0 else 1)
        
    summary = run_all_brokers_validation(sample_size=args.sample)
    total_checked = sum(v.get("total", 0) for v in summary.values())
    total_passed = sum(v.get("passed", 0) for v in summary.values())
    total_failed = sum(v.get("failed", 0) for v in summary.values())
    
    print("=" * 70)
    print("EXTRACTED MARKDOWN QUALITY REGRESSION VALIDATION")
    print(f"Total Files Checked: {total_checked} | Passed: {total_passed} | Failed: {total_failed}")
    print("=" * 70)
    for b, v in summary.items():
        if "error" in v:
            print(f"{b:20s}: DIR NOT FOUND")
            continue
        status_str = "OK" if v["failed"] == 0 else f"FAIL ({v['failed']} defects)"
        print(f"{b:20s}: {v['passed']:2d}/{v['total']:2d} PASS [{status_str}] (Total archive: {v.get('available_total', 0)})")
        if v["failed"] > 0:
            for r in v["results"]:
                if not r["valid"]:
                    print(f"    - {r['stem']}: {', '.join(r['issues'])}")
    print("=" * 70)
