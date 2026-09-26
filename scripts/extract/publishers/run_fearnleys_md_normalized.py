#!/usr/bin/env python3
"""
run_fearnleys_md_normalized.py
Normalizes, enriches, and backfills the entire Fearnleys Bespoke Research Markdown corpus
(corpus/01-brokers/fearnleys-md/) across 2024-2026 from the authoritative catalog.

Performs:
  1. Backfills 100% of reports from data/reports/fearnleys_reports_catalog.json (178 reports).
  2. Injects standardized YAML frontmatter (title, issue_date, year, department, publisher, pdf_url, images_count, local_pdf).
  3. Reconstructs clean Markdown hierarchies:
     - # Title
     - ## Vessel Class / Sector
     - Commentary prose with clear indicators
     - Structured image figures with captions linking to local images
     - Headers linking to local cached PDFs and cloud backups
  4. Generates an enhanced index catalog corpus/01-brokers/fearnleys-md/INDEX.md.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

ROOT = Path(r"c:\Users\Dell\Github\Shipping")
CATALOG_PATH = ROOT / "data" / "reports" / "fearnleys_reports_catalog.json"
FMD_DIR = ROOT / "corpus" / "01-brokers" / "fearnleys-md"
IMG_BASE_DIR = FMD_DIR / "images"
PDF_BASE_DIR = FMD_DIR / "pdfs"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text or "").strip("_")
    return s.lower() or "report"


def clean_encoding(text: str) -> str:
    if not text:
        return ""
    text = "".join(ch for ch in text if not (0xF000 <= ord(ch) <= 0xF8FF))
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\xa0", " ")
    text = text.replace("\ufb00", "ff").replace("\ufb01", "fi").replace("\ufb02", "fl").replace("\ufb03", "ffi").replace("\ufb04", "ffl")
    text = re.sub(r"(\w)\ufffd(\w)", r"\1'\2", text)
    text = text.replace("\ufffd", " ")
    return text.strip()


def parse_blocks_to_markdown(report: dict, rep_slug: Optional[str] = None) -> Tuple[str, int, Optional[str]]:
    """Converts Hasura JSON report blocks to standardized clean Markdown with YAML frontmatter."""
    title = clean_encoding(report.get("title") or "Untitled Report")
    date_str = report.get("date") or "undated"
    dept = (report.get("department") or "General").upper()
    pdf_url = report.get("pdf_url") or ""
    rep_id = report.get("id") or ""
    year = int(date_str[:4]) if len(date_str) >= 4 and date_str[:4].isdigit() else 2024

    content_blocks = report.get("content") or []
    if isinstance(content_blocks, str):
        try:
            content_blocks = json.loads(content_blocks)
        except Exception:
            content_blocks = [{"type": "paragraph", "content": content_blocks}]

    body_lines = []
    images_count = 0

    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "")
        bcontent = clean_encoding(block.get("content", ""))
        btitle = clean_encoding(block.get("title", ""))

        if btype == "heading1":
            body_lines.append(f"\n## {bcontent}\n")
        elif btype == "heading2":
            body_lines.append(f"\n### {bcontent}\n")
        elif btype in ("fullWidthParagraph", "paragraph"):
            if bcontent:
                body_lines.append(f"{bcontent}\n")
        elif btype in ("halfWidthChartFromFile", "fullWidthChartFromFile", "chart"):
            images_count += 1
            chart_title = btitle or "Indicator Chart"
            chart_url = bcontent.strip()

            # Check if image is cached locally
            m_blob = re.search(r"pbrkapp\.blob\.core\.windows\.net/report/([^/]+)/(.+)", chart_url)
            local_rel_path = None
            if m_blob:
                guid, filename = m_blob.groups()
                filename_clean = filename.rstrip(')"\'> \r\n\t')
                expected_local = IMG_BASE_DIR / guid / filename_clean
                if expected_local.exists():
                    local_rel_path = f"../images/{guid}/{filename_clean}"

            target_img_path = local_rel_path if local_rel_path else chart_url
            body_lines.append(f"\n![{chart_title}]({target_img_path})\n*Figure: {chart_title}*\n")
        elif btype == "pageBreak":
            body_lines.append("\n---\n")

    # Local PDF verification
    local_pdf_rel = None
    if rep_slug:
        expected_pdf = PDF_BASE_DIR / str(year) / f"{date_str}_{rep_slug}.pdf"
        if expected_pdf.exists():
            local_pdf_rel = f"../pdfs/{year}/{date_str}_{rep_slug}.pdf"

    # Frontmatter
    fm = [
        "---",
        f'title: "{title}"',
        f'issue_date: "{date_str}"',
        f"year: {year}",
        f'department: "{dept}"',
        'publisher: "Fearnleys"',
        'category: "bespoke_research"',
        f'report_id: "{rep_id}"',
        f"images_count: {images_count}",
    ]
    if local_pdf_rel:
        fm.append(f'local_pdf: "{local_pdf_rel}"')
    if pdf_url:
        fm.append(f'pdf_url: "{pdf_url}"')
    fm.append("---\n")

    # Header
    header = [
        f"# {title}\n",
        f"**Date:** {date_str} | **Department:** {dept} | **Publisher:** Fearnleys AS  ",
    ]
    if local_pdf_rel and pdf_url:
        header.append(f"**Original PDF:** [Local PDF]({local_pdf_rel}) | [Cloud Backup]({pdf_url})  ")
    elif local_pdf_rel:
        header.append(f"**Original PDF:** [Local PDF]({local_pdf_rel})  ")
    elif pdf_url:
        header.append(f"**Original PDF:** [Download PDF]({pdf_url})  ")
    header.append("\n---\n")

    full_md = "\n".join(fm) + "\n".join(header) + "\n".join(body_lines)
    return full_md, images_count, local_pdf_rel


def normalize_all():
    print("=================================================================", flush=True)
    print("  FEARNLEYS-MD RESEARCH CORPUS NORMALIZATION & BACKFILL          ", flush=True)
    print("=================================================================", flush=True)

    if not CATALOG_PATH.exists():
        print(f"Error: Master catalog {CATALOG_PATH} not found.", flush=True)
        return

    catalog = json.load(open(CATALOG_PATH, encoding="utf-8"))
    print(f"Loaded {len(catalog)} reports from master catalog.")

    total_images = 0
    saved_count = 0
    by_year = {}
    by_dept = {}

    index_entries = []

    for rep in catalog:
        rep_date = rep.get("date") or "undated"
        year_str = str(rep_date[:4]) if len(rep_date) >= 4 and rep_date[:4].isdigit() else "2024"
        title = (rep.get("title") or "report").strip()
        dept = (rep.get("department") or "General").upper()
        rep_slug = rep.get("slug") or slugify(title)
        filename = f"{rep_date}_{rep_slug}.md"

        year_dir = FMD_DIR / year_str
        year_dir.mkdir(parents=True, exist_ok=True)

        md_content, img_count, local_pdf = parse_blocks_to_markdown(rep, rep_slug=rep_slug)
        target_path = year_dir / filename
        target_path.write_text(md_content, encoding="utf-8")

        saved_count += 1
        total_images += img_count
        by_year[year_str] = by_year.get(year_str, 0) + 1
        by_dept[dept] = by_dept.get(dept, 0) + 1

        pdf_link = f"[PDF](pdfs/{year_str}/{rep_date}_{rep_slug}.pdf)" if local_pdf else (f"[Cloud]({rep.get('pdf_url')})" if rep.get("pdf_url") else "-")

        index_entries.append({
            "date": rep_date,
            "year": year_str,
            "title": title,
            "dept": dept,
            "images": img_count,
            "file": f"{year_str}/{filename}",
            "pdf_link": pdf_link,
        })

    # Sort index entries by date descending
    index_entries.sort(key=lambda x: x["date"], reverse=True)

    # Write Master Index
    index_md = [
        "# Fearnleys Bespoke Research Library (fearnleys-md)",
        "",
        "This directory contains Fearnleys's proprietary weekly research publications and sector wrap-ups harvested directly from Fearnleys's Hasura API (`custom_report`).",
        "",
        "## Summary Statistics",
        f"- **Total Research Reports:** {saved_count}",
        f"- **Total Indicator & Correlation Charts:** {total_images}",
        f"- **Date Coverage:** {index_entries[-1]['date']} to {index_entries[0]['date']}",
        "",
        "### Reports by Year",
    ]
    for y, count in sorted(by_year.items()):
        index_md.append(f"- **{y}:** {count} reports")

    index_md.extend([
        "",
        "### Reports by Department",
    ])
    for d, count in sorted(by_dept.items()):
        index_md.append(f"- **{d}:** {count} reports")

    index_md.extend([
        "",
        "---",
        "",
        "## Complete Publications Catalog",
        "",
        "| Date | Department | Title | Charts | Markdown | PDF |",
        "| :---: | :---: | :--- | :---: | :--- | :---: |"
    ])

    for entry in index_entries:
        index_md.append(
            f"| {entry['date']} | {entry['dept']} | {entry['title']} | {entry['images']} | [{entry['file']}]({entry['file']}) | {entry['pdf_link']} |"
        )

    (FMD_DIR / "INDEX.md").write_text("\n".join(index_md), encoding="utf-8")

    print(f"\nSuccessfully normalized {saved_count} research reports in {FMD_DIR}")
    print(f"Total charts referenced: {total_images}")
    print(f"Created master index: {FMD_DIR / 'INDEX.md'}")
    print("=================================================================\n", flush=True)


if __name__ == "__main__":
    normalize_all()
