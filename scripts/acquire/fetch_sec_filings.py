#!/usr/bin/env python3
"""
scripts/acquire/fetch_sec_filings.py

Download SEC EDGAR filings for target shipping and dry bulk companies,
converting them to clean, artifact-free Markdown using edgartools and sec2md.

Target companies (in exact order):
VALE, RIO, BHP, FSUGY, SBLK, GOGL, GNK, SB, DSX, SHIP, CTRM, GLBS, EDRY,
FRO, INSW, STNG, DHT, TNK, TRMD, ECO, NAT, TNP, ASC, SFL, NVGS, LPG

Storage structure:
corpus/10-companies/
    └── {TICKER}/
        ├── 10-K/
        ├── 20-F/
        ├── 10-Q/
        ├── 6-K/
        └── 8-K/

File naming:
{TICKER}_{FORM}_{YYYY-MM-DD}_{accession}.md
"""

import os
import sys
import time
import argparse
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set

from edgar import Company, set_identity
from sec2md.parser import Parser

# SEC identity
SEC_IDENTITY = "Antigravity Research research@shippinganalytics.com"
CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus" / "10-companies"

# Target companies in exact order
TARGET_COMPANIES = [
    "VALE", "RIO", "BHP", "FSUGY", "SBLK", "GOGL", "GNK", "SB", "DSX", "SHIP",
    "CTRM", "GLBS", "EDRY", "FRO", "INSW", "STNG", "DHT", "TNK", "TRMD", "ECO",
    "NAT", "TNP", "ASC", "SFL", "NVGS", "LPG"
]

# Tickers that map to explicit CIKs in SEC EDGAR
CIK_OVERRIDES = {
    "GOGL": "0001029145",   # Golden Ocean Group Ltd
    "TNP": "0001166663",    # Tsakos Energy Navigation Ltd (SEC ticker TEN)
    "FSUGY": "0001444325",  # Fortescue Metals Group Ltd
}

# Standard form directories
FORM_DIRS = ["10-K", "20-F", "10-Q", "6-K", "8-K"]

# Material 8-K items (Item numbers in EDGAR header/items)
MATERIAL_8K_ITEMS = {
    "Item 1.01",  # Entry into a Material Definitive Agreement (acquisitions, financing, debt facilities)
    "Item 2.01",  # Acquisition or Disposition of Assets (vessel sales/purchases)
    "Item 2.02",  # Results of Operations and Financial Condition (earnings releases)
    "Item 2.06",  # Material Impairments
    "Item 7.01",  # Regulation FD Disclosure (investor presentations, fleet updates)
    "Item 8.01",  # Other Events (material contracts, dividend declarations, fleet developments)
    "1.01", "2.01", "2.02", "2.06", "7.01", "8.01"
}

# Material keywords for 8-K detection fallback
MATERIAL_KEYWORDS = [
    "earnings", "financial results", "quarterly results", "annual results",
    "fleet update", "vessel acquisition", "vessel sale", "vessel purchase",
    "impairment", "dividend", "credit facility", "term loan", "charter",
    "newbuilding", "delivery", "guidance"
]
MATERIAL_KW_REGEX = re.compile(r'\b(' + '|'.join(MATERIAL_KEYWORDS) + r')\b', re.IGNORECASE)

# Composition / SGML artifact regex pattern
ARTIFACT_LINE_PATTERN = re.compile(
    r'^\s*(COMMAND=|ZEQ=|Field:\s*|end of user-specified|User-specified TAGGED|PARA=JUSTIFY|TOC_END)',
    re.IGNORECASE
)


def ensure_company_directories(ticker: str) -> Dict[str, Path]:
    """Create directory structure for a company and return paths."""
    ticker_dir = CORPUS_DIR / ticker
    dir_map = {}
    for form in FORM_DIRS:
        sub_dir = ticker_dir / form
        sub_dir.mkdir(parents=True, exist_ok=True)
        dir_map[form] = sub_dir
    return dir_map


def sanitize_form_name(form: str) -> str:
    """Sanitize form name for filesystem (e.g. 20-F/A -> 20-F-A)."""
    return form.replace("/", "-").strip()


def is_material_8k(filing) -> bool:
    """
    Determine if an 8-K filing is material.
    Includes earnings releases (2.02), fleet updates/presentations (7.01),
    vessel sales/purchases (2.01), material contracts (1.01), impairments (2.06),
    and other material events (8.01).
    Skips routine filings (e.g. voting results Item 5.07 or officer notices 5.02).
    """
    try:
        items = getattr(filing, "items", None)
        if items:
            if isinstance(items, str):
                items_list = [i.strip() for i in items.split(",") if i.strip()]
            elif isinstance(items, (list, tuple, set)):
                items_list = [str(i).strip() for i in items if str(i).strip()]
            else:
                items_list = [str(items).strip()]

            for item_str in items_list:
                for mat in MATERIAL_8K_ITEMS:
                    if mat == item_str or mat in item_str:
                        return True
            return False
    except Exception:
        pass

    try:
        desc = getattr(filing, "description", "") or ""
        if MATERIAL_KW_REGEX.search(desc):
            return True

        html = filing.html()
        if html:
            snippet = html[:5000]
            if MATERIAL_KW_REGEX.search(snippet):
                return True
    except Exception:
        pass

    return False


def clean_markdown_content(md_text: str) -> str:
    """
    Post-process markdown content to eliminate SGML/typesetting artifacts,
    corrupted characters, empty table rows, and malformed whitespace.
    """
    if not md_text:
        return ""

    # 1. Unicode character normalization
    md_text = md_text.replace('\u200b', '')   # zero-width space
    md_text = md_text.replace('\ufeff', '')   # byte-order mark
    md_text = md_text.replace('\u00a0', ' ')   # non-breaking space
    md_text = md_text.replace('\u041f', '\u2014')   # Cyrillic Pe used by old SGML printers for em-dash

    # 2. Line-by-line filtering of composition commands & SGML printer noise
    cleaned_lines = []
    for line in md_text.splitlines():
        line_strip = line.strip()
        if not line_strip:
            cleaned_lines.append("")
            continue

        if ARTIFACT_LINE_PATTERN.match(line_strip):
            continue
        if "THIS IS THE END OF A COMPOSITION COMPONENT" in line_strip:
            continue
        if re.match(r'^\s*<!--.*?-->\s*$', line_strip):
            continue

        # Check if line is purely empty table row: e.g. "| | | | | |"
        if line_strip.startswith("|") and line_strip.endswith("|"):
            cells = [c.strip() for c in line_strip.split("|")[1:-1]]
            if all(c == "" for c in cells):
                continue

        # Clean spaced parentheses inside table numbers: (3,105 ) -> (3,105)
        line = re.sub(r'\(\s*([0-9,]+(?:\.[0-9]+)?)\s+\)', r'(\1)', line)

        cleaned_lines.append(line)

    # 3. Collapse multiple blank lines
    result = re.sub(r'\n{3,}', '\n\n', "\n".join(cleaned_lines)).strip()
    return result


def convert_filing_to_markdown(filing) -> Tuple[str, str]:
    """
    Convert filing to clean Markdown.
    Primary: sec2md Parser on comment-stripped HTML, followed by artifact filtering.
    Fallback 1: edgartools native filing.markdown().
    Fallback 2: filing.text().

    Returns:
        (markdown_content, method_used)
    """
    # 1. Try sec2md with comment stripping
    try:
        raw_html = filing.html()
        if raw_html and len(raw_html.strip()) > 100:
            # Strip comments and XML headers before parsing
            clean_html = re.sub(r'<!--.*?-->', '', raw_html, flags=re.DOTALL)
            clean_html = re.sub(r'<\?xml.*?\?>', '', clean_html)
            clean_html = re.sub(r'<!DOCTYPE.*?>', '', clean_html, flags=re.IGNORECASE)

            parser = Parser(clean_html)
            pages = parser.get_pages(include_elements=False)
            raw_md = "\n\n".join(page.content for page in pages if page.content)
            clean_md = clean_markdown_content(raw_md)
            if clean_md and len(clean_md) > 100:
                return clean_md, "sec2md"
    except Exception:
        pass

    # 2. Try edgartools native markdown
    try:
        md = filing.markdown()
        if md and len(md.strip()) > 100:
            clean_md = clean_markdown_content(md)
            if clean_md and len(clean_md) > 100:
                return clean_md, "edgartools_markdown"
    except Exception:
        pass

    # 3. Fallback to text
    try:
        txt = filing.text()
        if txt and len(txt.strip()) > 100:
            clean_txt = clean_markdown_content(txt)
            if clean_txt and len(clean_txt) > 100:
                return clean_txt, "edgartools_text"
    except Exception:
        pass

    return "", "failed"


def process_filing(
    ticker: str,
    filing,
    form_dir: Path,
    rate_limit_delay: float = 0.1
) -> Tuple[bool, str]:
    """
    Process a single filing, converting and saving to .md if not already present.

    Returns:
        (success_bool, message_str)
    """
    form_raw = str(getattr(filing, "form", "")).strip()
    filing_date = str(getattr(filing, "filing_date", "")).strip()
    accession = str(getattr(filing, "accession_no", "")).strip()

    if not form_raw or not filing_date or not accession:
        return False, "Missing filing metadata (form, date, or accession)"

    form_clean = sanitize_form_name(form_raw)
    filename = f"{ticker}_{form_clean}_{filing_date}_{accession}.md"
    target_path = form_dir / filename

    # Resumability: check if target file exists and is non-empty (>1KB)
    if target_path.exists() and target_path.stat().st_size > 1024:
        return True, f"SKIPPED (already exists: {filename})"

    # Convert to markdown
    md_content, method = convert_filing_to_markdown(filing)
    if not md_content or len(md_content.strip()) < 50:
        return False, f"FAILED to extract markdown for {filename}"

    # Write final markdown file atomically
    temp_path = target_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        temp_path.replace(target_path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        return False, f"FAILED to write file {filename}: {e}"

    if rate_limit_delay > 0:
        time.sleep(rate_limit_delay)

    return True, f"SAVED ({method}, {len(md_content):,} chars): {filename}"


def download_company_filings(
    ticker: str,
    annual_years: int = 12,
    quarterly_years: int = 7,
    limit_per_form: Optional[int] = None,
    limit_6k: Optional[int] = None,
    rate_limit_delay: float = 0.1
) -> Dict[str, int]:
    """
    Download and convert SEC filings for a single company into corpus/10-companies/{TICKER}/.
    """
    print(f"\n======================================================================")
    print(f"Starting SEC filings acquisition for: {ticker}")
    print(f"======================================================================")

    dir_map = ensure_company_directories(ticker)

    identifier = CIK_OVERRIDES.get(ticker, ticker)
    try:
        company = Company(identifier)
        company_name = getattr(company, "name", ticker)
        cik = getattr(company, "cik", "unknown")
        print(f"Company: {company_name} | CIK: {cik} (query: {identifier})")
    except Exception as e:
        print(f"ERROR: Unable to initialize Company('{identifier}'): {e}")
        return {}

    now = datetime.now()
    annual_cutoff = (now - timedelta(days=int(annual_years * 365.25))).strftime("%Y-%m-%d") if annual_years > 0 else "1990-01-01"
    quarterly_cutoff = (now - timedelta(days=int(quarterly_years * 365.25))).strftime("%Y-%m-%d") if quarterly_years > 0 else "1990-01-01"

    stats = {form: 0 for form in FORM_DIRS}

    # 1. Annual Reports: 10-K and 20-F
    for form_name in ["10-K", "20-F"]:
        target_dir = dir_map[form_name]
        amended_form = f"{form_name}/A"
        try:
            print(f"\n[{ticker}] Fetching {form_name} filings (since {annual_cutoff})...")
            filings = company.get_filings(form=[form_name, amended_form])
            if annual_years > 0:
                filings = filings.filter(filing_date=f"{annual_cutoff}:")

            total_found = len(filings)
            print(f"[{ticker}] Found {total_found} filings for {form_name}")

            if total_found == 0:
                continue

            count_to_process = total_found if limit_per_form is None else min(limit_per_form, total_found)
            saved_count = 0

            for i in range(count_to_process):
                f = filings[i]
                success, msg = process_filing(ticker, f, target_dir, rate_limit_delay)
                progress_idx = i + 1
                if success:
                    saved_count += 1
                    print(f"  [{ticker}] {form_name} [{progress_idx}/{count_to_process}]: {msg}")
                else:
                    print(f"  [{ticker}] {form_name} [{progress_idx}/{count_to_process}]: {msg}")

            stats[form_name] = saved_count
            print(f"[{ticker}] {form_name} complete: {saved_count} filings processed")

        except Exception as e:
            print(f"[{ticker}] Error fetching {form_name}: {e}")

    # 2. Quarterly Reports: 10-Q and 6-K
    for form_name in ["10-Q", "6-K"]:
        target_dir = dir_map[form_name]
        amended_form = f"{form_name}/A"
        try:
            print(f"\n[{ticker}] Fetching {form_name} filings (since {quarterly_cutoff})...")
            filings = company.get_filings(form=[form_name, amended_form])
            if quarterly_years > 0:
                filings = filings.filter(filing_date=f"{quarterly_cutoff}:")

            total_found = len(filings)
            print(f"[{ticker}] Found {total_found} filings for {form_name}")

            if total_found == 0:
                continue

            max_items = limit_per_form
            if form_name == "6-K" and limit_6k is not None:
                max_items = limit_6k

            count_to_process = total_found if max_items is None else min(max_items, total_found)
            saved_count = 0

            for i in range(count_to_process):
                f = filings[i]
                success, msg = process_filing(ticker, f, target_dir, rate_limit_delay)
                progress_idx = i + 1
                if success:
                    saved_count += 1
                    print(f"  [{ticker}] {form_name} [{progress_idx}/{count_to_process}]: {msg}")
                else:
                    print(f"  [{ticker}] {form_name} [{progress_idx}/{count_to_process}]: {msg}")

            stats[form_name] = saved_count
            print(f"[{ticker}] {form_name} complete: {saved_count} filings processed")

        except Exception as e:
            print(f"[{ticker}] Error fetching {form_name}: {e}")

    # 3. Current Reports: Material 8-K only
    target_dir = dir_map["8-K"]
    try:
        print(f"\n[{ticker}] Fetching 8-K filings (since {quarterly_cutoff})...")
        filings = company.get_filings(form=["8-K", "8-K/A"])
        if quarterly_years > 0:
            filings = filings.filter(filing_date=f"{quarterly_cutoff}:")

        total_found = len(filings)
        print(f"[{ticker}] Found {total_found} filings for 8-K")

        if total_found > 0:
            saved_count = 0
            checked_count = 0
            max_to_check = total_found if limit_per_form is None else min(limit_per_form * 4, total_found)

            for i in range(max_to_check):
                f = filings[i]
                checked_count += 1
                if not is_material_8k(f):
                    continue

                success, msg = process_filing(ticker, f, target_dir, rate_limit_delay)
                if success:
                    saved_count += 1
                    print(f"  [{ticker}] 8-K (Material) [{saved_count} saved, {checked_count}/{max_to_check} checked]: {msg}")
                else:
                    print(f"  [{ticker}] 8-K [{checked_count}/{max_to_check}]: {msg}")

                if limit_per_form is not None and saved_count >= limit_per_form:
                    break

            stats["8-K"] = saved_count
            print(f"[{ticker}] 8-K complete: {saved_count} material filings saved (from {checked_count} inspected)")

    except Exception as e:
        print(f"[{ticker}] Error fetching 8-K: {e}")

    print(f"\n[{ticker}] Summary of acquired filings:")
    for form in FORM_DIRS:
        print(f"  {form}: {stats[form]}")
    print(f"======================================================================\n")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Download SEC EDGAR filings to clean Markdown in corpus/10-companies/.")
    parser.add_argument("--ticker", type=str, help="Single company ticker to download (e.g. VALE)")
    parser.add_argument("--companies", type=str, help="Comma-separated list of tickers")
    parser.add_argument("--all", action="store_true", help="Download all 26 target companies in sequence")
    parser.add_argument("--annual-years", type=int, default=12, help="Years back for 10-K and 20-F (default: 12, 0 for all)")
    parser.add_argument("--quarterly-years", type=int, default=6, help="Years back for 10-Q and 6-K (default: 6)")
    parser.add_argument("--limit", type=int, default=None, help="Limit filings per form type (for testing)")
    parser.add_argument("--limit-6k", type=int, default=None, help="Specific limit for 6-K filings")
    parser.add_argument("--rate-limit", type=float, default=0.1, help="Delay between downloads in seconds (default: 0.1)")

    args = parser.parse_args()

    set_identity(SEC_IDENTITY)
    print(f"SEC identity set to: {SEC_IDENTITY}")
    print(f"Destination root: {CORPUS_DIR}")

    if args.ticker:
        tickers = [args.ticker.upper()]
    elif args.companies:
        tickers = [t.strip().upper() for t in args.companies.split(",") if t.strip()]
    elif args.all:
        tickers = TARGET_COMPANIES
    else:
        print("No target specified. Defaulting to all 26 companies.")
        tickers = TARGET_COMPANIES

    overall_results = {}
    for ticker in tickers:
        results = download_company_filings(
            ticker=ticker,
            annual_years=args.annual_years,
            quarterly_years=args.quarterly_years,
            limit_per_form=args.limit,
            limit_6k=args.limit_6k,
            rate_limit_delay=args.rate_limit
        )
        overall_results[ticker] = results

    print("\n======================================================================")
    print("ALL REQUESTED COMPANIES PROCESSED")
    print("======================================================================")
    for ticker, stats in overall_results.items():
        summary_str = ", ".join([f"{k}: {v}" for k, v in stats.items() if v > 0])
        print(f"{ticker}: {summary_str or 'None'}")


if __name__ == "__main__":
    main()
