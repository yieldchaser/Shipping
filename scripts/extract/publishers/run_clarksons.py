"""Clarksons Platou Hellas S&P and Demolition Extraction Runner.

Extracts weekly Sale & Purchase and Demolition market reports for Clarksons Hellas:
- Multi-era coverage spanning 2021 through 2026 (171 unique editions)
- Ingests both corpus/01-brokers/clarksons/2026 and corpus/02-hellenic/shipbuilding/pdfs
- Extracts narrative commentary (Desk Talk, Recycling, Newbuilding)
- Extracts S&P transaction tables (Bulker Sales and Tanker Sales)
- Extracts Demolition / Recycling transaction tables
- Produces:
  data/extracted/md/clarksons/<stem>.md
  data/extracted/md/clarksons/<stem>.tables.json (with issue_date stamped in each record)
  data/extracted/series/clarksons_sales_series.csv
  data/extracted/series/clarksons_demolition_series.csv
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
PUB = "clarksons"
BROKER_DIR = ROOT / "corpus" / "01-brokers" / PUB / "2026"
HELLENIC_DIR = ROOT / "corpus" / "02-hellenic" / "shipbuilding" / "pdfs"
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"
STATE_FILE = OUT_MD / "_run_state.json"

DATE_PATTERNS = [
    # Sept 18, 2026 or Aug 7th, 2026 or Aug 14, 2026
    re.compile(r"([A-Za-z]{3,9})\s*(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})", re.I),
    # 2 July 2021 or 07 January 2022 or 05 Jan 2024
    re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\s+(\d{4})", re.I),
    # 18_09_2026
    re.compile(r"(\d{1,2})_(\d{1,2})_(\d{4})"),
    # 04th-Sept-2026 or 7th-August-2026
    re.compile(r"(\d{1,2})(?:st|nd|rd|th)?-([A-Za-z]{3,9})-(\d{4})", re.I),
    # 2021-07-02
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),
    # REPORT-02-07-2021
    re.compile(r"REPORT-(\d{1,2})-(\d{2})-(\d{4})", re.I),
]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}


def clean_text(s: str) -> str:
    """Normalize whitespace and fix unicode font mojibake."""
    if not s:
        return ""
    s = s.replace("\ufffd", "'")
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("`", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_issue_date(pdf_path: Path, doc: pymupdf.Document) -> Tuple[str, str]:
    """Extract standard ISO date (YYYY-MM-DD) and printed date string."""
    fname = pdf_path.name

    # 1. Check filename for YYYY-MM-DD
    m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", fname)
    if m_iso:
        yyyy, mm, dd = m_iso.group(1), int(m_iso.group(2)), int(m_iso.group(3))
        return f"{yyyy}-{mm:02d}-{dd:02d}", f"{dd:02d}/{mm:02d}/{yyyy}"

    # 2. Check filename for DD_MM_YYYY or DD-MM-YYYY
    m1 = re.search(r"(\d{1,2})_(\d{1,2})_(\d{4})", fname)
    if m1:
        dd, mm, yyyy = int(m1.group(1)), int(m1.group(2)), m1.group(3)
        return f"{yyyy}-{mm:02d}-{dd:02d}", f"{dd:02d}/{mm:02d}/{yyyy}"

    m_rep = re.search(r"REPORT-(\d{1,2})-(\d{2})-(\d{4})", fname, re.I)
    if m_rep:
        dd, mm, yyyy = int(m_rep.group(1)), int(m_rep.group(2)), m_rep.group(3)
        return f"{yyyy}-{mm:02d}-{dd:02d}", f"{dd:02d}/{mm:02d}/{yyyy}"

    # 3. Check filename for DD-Mon-YYYY
    m2 = re.search(r"(\d{1,2})(?:st|nd|rd|th)?-([A-Za-z]{3,9})-(\d{4})", fname, re.I)
    if m2:
        day_str, mon_str, yyyy = m2.group(1), m2.group(2)[:3].lower(), m2.group(3)
        if mon_str in MONTH_MAP:
            mm = MONTH_MAP[mon_str]
            dd = int(day_str)
            return f"{yyyy}-{mm:02d}-{dd:02d}", f"{dd} {m2.group(2)} {yyyy}"

    # 4. Look in top banner on page 1 / page 2
    for pno in range(min(2, len(doc))):
        page = doc[pno]
        for b in page.get_text("blocks"):
            if b[1] < 160:
                txt = b[4].strip()
                # Try Month DD, YYYY
                m_m = DATE_PATTERNS[0].search(txt)
                if m_m:
                    mon_str, day_str, yr_str = m_m.group(1)[:3].lower(), m_m.group(2), m_m.group(3)
                    if mon_str in MONTH_MAP:
                        mm = MONTH_MAP[mon_str]
                        dd = int(day_str)
                        return f"{yr_str}-{mm:02d}-{dd:02d}", m_m.group(0)

                # Try DD Month YYYY
                m_d = DATE_PATTERNS[1].search(txt)
                if m_d:
                    day_str, mon_str, yr_str = m_d.group(1), m_d.group(2)[:3].lower(), m_d.group(3)
                    if mon_str in MONTH_MAP:
                        mm = MONTH_MAP[mon_str]
                        dd = int(day_str)
                        return f"{yr_str}-{mm:02d}-{dd:02d}", m_d.group(0)

    return "2026-00-00", fname


def infer_vessel_type(name: str, dwt_str: str, section: str, commentary: str) -> str:
    """Infer standardized vessel subtype using commentary and DWT."""
    dwt_num = None
    if dwt_str:
        num_match = re.search(r"[\d,]+", dwt_str)
        if num_match:
            try:
                dwt_num = int(num_match.group(0).replace(",", ""))
            except ValueError:
                pass

    comm_lower = commentary.lower()
    name_lower = name.lower()

    # Check commentary context for explicit vessel class mentions at sentence level
    for para in commentary.split("\n\n"):
        if name_lower in para.lower():
            sentences = re.split(r"[.!?]\s+", para)
            for s in sentences:
                if name_lower in s.lower():
                    slow = s.lower()
                    if "handysize" in slow or "handy" in slow:
                        return "Handysize"
                    if "kamsarmax" in slow:
                        return "Kamsarmax"
                    if "ultramax" in slow:
                        return "Ultramax"
                    if "supramax" in slow:
                        return "Supramax"
                    if "panamax" in slow:
                        return "Panamax"
                    if "capesize" in slow or "cape" in slow or "newcastlemax" in slow:
                        return "Capesize"
                    if "vlcc" in slow:
                        return "VLCC"
                    if "suezmax" in slow:
                        return "Suezmax"
                    if "aframax" in slow or "lr2" in slow:
                        return "LR2" if "lr2" in slow else "Aframax"
                    if "mr" in slow or "product" in slow:
                        return "MR"

    # Default to standard DWT boundaries
    if "bulk" in section.lower() or (dwt_num and dwt_num < 45000 and "tank" not in name_lower):
        if dwt_num:
            if dwt_num >= 120000:
                return "Capesize"
            if dwt_num >= 80000:
                return "Kamsarmax"
            if dwt_num >= 70000:
                return "Panamax"
            if dwt_num >= 60000:
                return "Ultramax"
            if dwt_num >= 45000:
                return "Supramax"
            return "Handysize"
        return "Bulker"

    if "tanker" in section.lower():
        if dwt_num:
            if dwt_num >= 200000:
                return "VLCC"
            if dwt_num >= 120000:
                return "Suezmax"
            if dwt_num >= 80000:
                return "Aframax"
            if dwt_num >= 60000:
                return "Panamax"
            if dwt_num <= 40000 and "bulk" in commentary.lower():
                return "Handysize"
            return "MR"
        return "Tanker"

    return "Vessel"


def extract_desk_commentary(doc: pymupdf.Document) -> str:
    """Extract narrative commentary across all pages with proper section association and labeling."""
    sections = []
    current_sec = "Desk Talk"

    for pno in range(min(2, len(doc))):
        page = doc[pno]
        blocks = page.get_text("blocks")

        # 1. Find table cutoff y
        table_y = 9999.0
        for b in blocks:
            u = b[4].strip().upper()
            if ("VESSEL" in u and "DWT" in u) or "BULKER SALES" in u or "TANKER SALES" in u or "DEMOLITION" in u:
                if b[1] < table_y:
                    table_y = b[1]

        # 2. Extract banners and narrative blocks
        banners = []
        narratives = []

        for b in blocks:
            txt = b[4].strip()
            if not txt or b[1] >= table_y - 5:
                continue
            if b[1] < 120 and ("Clarkson" in txt or "Weekly Bulletin" in txt or "Sale and Purchase" in txt):
                continue
            if b[1] > 800 or "Page " in txt or "The material and the information" in txt or "Direct  +" in txt or "Kifissias Avenue" in txt or "clarksons.gr" in txt.lower():
                continue
            if "BALTIC INDEX" in txt or "EXCHANGE RATE" in txt or "BUNKER PRICES" in txt:
                continue
            u = txt.upper()
            if "VESSEL" in u and "DWT" in u and ("BLT" in u or "BUILT" in u):
                continue
            if u in ("BULK CARRIERS", "TANKERS - CHEMICALS - LPG/LNGS", "BULKER SALES", "TANKER SALES", "DEMOLITION"):
                continue

            clean_name = txt.strip()
            if b[0] < 120 and clean_name in ("Desk Talk", "Dry Cargo", "Tanker", "NEW BUILDING", "RECYCLING", "Mixed Messages!"):
                banners.append((b[1], clean_name))
            else:
                lines = [l.strip() for l in txt.split("\n") if l.strip()]
                if len(lines) >= 2 or len(txt) > 80:
                    cleaned = clean_text(txt.replace("\n", " "))
                    if cleaned:
                        narratives.append((b[1], cleaned, txt))

        banners.sort(key=lambda x: x[0])
        narratives.sort(key=lambda x: x[0])

        for n_y, n_clean, raw_txt in narratives:
            # Match to banner
            for b_y, b_name in reversed(banners):
                if b_y <= n_y + 35:
                    current_sec = b_name
                    break

            if current_sec == "Desk Talk":
                raw_paras = [clean_text(p) for p in re.split(r"\n\s*\n", raw_txt) if clean_text(p)]
                tanker_paras = []
                dry_paras = []
                general_paras = []
                for p in raw_paras:
                    low = p.lower()
                    if low.startswith("on dry") or "bdi " in low or "dry bulk" in low or "dry space" in low:
                        dry_paras.append(p)
                    elif "tanker" in low or "vlcc" in low or "suezmax" in low or "clean earnings" in low or "crude carriers" in low:
                        tanker_paras.append(p)
                    else:
                        general_paras.append(p)

                sections.append(("Desk Talk", general_paras, tanker_paras, dry_paras))
            else:
                sections.append((current_sec, [n_clean], [], []))

    # Format into markdown
    md_lines = []
    desk_talk_emitted = False
    for sec_name, gen_p, tkr_p, dry_p in sections:
        if sec_name == "Desk Talk" and not desk_talk_emitted:
            desk_talk_emitted = True
            md_lines.append("### Desk Talk\n")
            if tkr_p:
                md_lines.append("#### Tankers\n")
                for p in tkr_p:
                    md_lines.append(f"{p}\n")
            if dry_p:
                md_lines.append("#### Dry Cargo\n")
                for p in dry_p:
                    md_lines.append(f"{p}\n")
            if gen_p:
                for p in gen_p:
                    md_lines.append(f"{p}\n")
        elif sec_name == "Dry Cargo":
            md_lines.append("### Dry Cargo S&P\n")
            for p in gen_p:
                md_lines.append(f"{p}\n")
        elif sec_name == "Tanker":
            md_lines.append("### Tanker S&P\n")
            for p in gen_p:
                md_lines.append(f"{p}\n")
        elif sec_name not in ("Desk Talk",):
            md_lines.append(f"### {sec_name}\n")
            for p in gen_p:
                md_lines.append(f"{p}\n")

    return "\n".join(md_lines).strip()


BANNER_KEYWORDS = [
    "TANKERS", "BULK CARRIERS", "BULKER SALES", "TANKER SALES",
    "DEMOLITION", "RECYCLING", "NEW BUILDING", "BALTIC INDEX",
    "EXCHANGE RATE", "BUNKER PRICES", "CONTACTS", "DIRECT  +", "THE MATERIAL"
]


def get_table_y_end(page: pymupdf.Page, y_start: float, next_hdr_y: Optional[float]) -> float:
    """Find bottom bound of a table before the next header or section banner."""
    blocks = page.get_text("blocks")
    y_end = next_hdr_y if next_hdr_y else 780.0
    for b in blocks:
        if b[1] > y_start + 10:
            txt = b[4].strip().upper()
            if any(k in txt for k in BANNER_KEYWORDS):
                if b[1] < y_end:
                    y_end = b[1]
    return y_end


def extract_all_transactions(doc: pymupdf.Document, pdf_path: Path, issue_date: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract both S&P sales records and Demolition records."""
    sales_extracted = []
    demo_extracted = []
    fname = pdf_path.name
    full_commentary = extract_desk_commentary(doc)

    bounds = [30.0, 118.0, 168.0, 275.0, 375.0, 430.0, 520.0, 585.0]

    for pno in range(len(doc)):
        page = doc[pno]
        words = page.get_text("words")
        blocks = page.get_text("blocks")

        # Skip disclaimer / contact page
        if any("The material and the information" in b[4] for b in blocks):
            continue

        v_hdrs = []
        for w in words:
            if w[4].strip().upper() == "VESSEL" and w[1] > 100:
                line_words = [lw for lw in words if abs(lw[1] - w[1]) < 6]
                line_str = " ".join(lw[4].upper() for lw in line_words)
                if "DWT" in line_str and ("BLT" in line_str or "BUILT" in line_str):
                    v_hdrs.append(w)

        if not v_hdrs:
            continue

        v_hdrs.sort(key=lambda w: w[1])

        for i, vh in enumerate(v_hdrs):
            line_words = [lw for lw in words if abs(lw[1] - vh[1]) < 6]
            line_str = " ".join(lw[4].upper() for lw in line_words)
            is_demo = ("DELIVERY" in line_str or "RECYCLING" in line_str or "DEMOLITION" in line_str)

            y_start = vh[3] + 4
            next_vh = v_hdrs[i + 1][1] - 5 if i + 1 < len(v_hdrs) else None
            y_end = get_table_y_end(page, y_start, next_vh)

            # Determine section
            by_cand = []
            for b in blocks:
                if b[1] < vh[1]:
                    btxt = b[4].strip().upper()
                    if "BULK" in btxt:
                        by_cand.append((b[1], "Bulker Sales"))
                    elif "TANK" in btxt:
                        by_cand.append((b[1], "Tanker Sales"))
                    elif "DEMO" in btxt or "RECYC" in btxt:
                        by_cand.append((b[1], "Demolition Sales"))
            by_cand.sort(key=lambda x: x[0])
            sec = by_cand[-1][1] if by_cand else ("Demolition Sales" if is_demo else "Bulker Sales")

            # Extract vessel candidate words
            vw = [
                w for w in words
                if w[0] < bounds[1]
                and y_start <= (w[1] + w[3]) / 2 < y_end
                and w[4].strip() not in ("VESSEL", "-", "Bulker", "Tanker", "Sales", "Vessel")
            ]

            clustered = []
            for w in sorted(vw, key=lambda x: (x[1], x[0])):
                if not clustered or abs(w[1] - clustered[-1][-1][1]) > 14.0:
                    clustered.append([w])
                else:
                    clustered[-1].append(w)

            for c in clustered:
                v_name = clean_text(" ".join(x[4] for x in c))
                u_name = v_name.upper()
                if not v_name or v_name in ("-", "None", "Vessel", "VESSEL"):
                    continue
                if u_name.startswith("TANKERS") or u_name.startswith("BULK CARRIERS") or u_name.startswith("BALTIC INDEX"):
                    continue
                if u_name in ("DEMOLITION", "RECYCLING", "NEW BUILDING", "BUNKERS"):
                    continue

                min_y = min(x[1] for x in c) - 8
                max_y = max(x[3] for x in c) + 16
                rw = [w for w in words if min_y <= (w[1] + w[3]) / 2 <= max_y]
                row_cols = [""] * 7
                for w in sorted(rw, key=lambda x: (x[1], x[0])):
                    cx = (w[0] + w[2]) / 2
                    for ci in range(7):
                        if bounds[ci] <= cx < bounds[ci + 1]:
                            row_cols[ci] = (row_cols[ci] + " " + w[4]).strip()
                            break

                raw_built = clean_text(row_cols[2])
                m_yr = re.match(r"^(\d{4})\s*(.*)$", raw_built)
                built_yr = m_yr.group(1) if m_yr else ""
                yard = m_yr.group(2) if m_yr else raw_built

                dwt_clean = clean_text(row_cols[1])
                price_clean = clean_text(row_cols[5])
                details_clean = clean_text(row_cols[3])
                buyer_or_deliv = clean_text(row_cols[6])
                ss_dd_clean = clean_text(row_cols[4])

                # Reject phantom rows with no ship data
                has_dwt = bool(re.search(r"\d", dwt_clean))
                has_yr = bool(re.search(r"\d{4}", built_yr))
                has_price = bool(re.search(r"[\d\$]|usd|eur", price_clean.lower()))
                if not (has_dwt or has_yr or has_price):
                    continue

                # Infer vessel sub-type
                v_type = infer_vessel_type(v_name, dwt_clean, sec, full_commentary)

                record = {
                    "issue_date": issue_date,
                    "stem": pdf_path.stem,
                    "source_file": fname,
                    "section": sec,
                    "page": pno + 1,
                    "NAME": v_name,
                    "TYPE": v_type,
                    "DWT": dwt_clean,
                    "BUILT": built_yr,
                    "YARD": yard,
                    "PRICE": price_clean,
                    "BUYERS": buyer_or_deliv,
                    "SS_DD": ss_dd_clean,
                    "COMMENTS": details_clean,
                    "raw_built": raw_built,
                    "raw_details": details_clean,
                }

                if "DEMO" in sec.upper() or is_demo:
                    demo_record = {
                        "issue_date": issue_date,
                        "stem": pdf_path.stem,
                        "source_file": fname,
                        "section": sec,
                        "page": pno + 1,
                        "NAME": v_name,
                        "TYPE": v_type,
                        "DWT": dwt_clean,
                        "BUILT": built_yr,
                        "YARD": yard,
                        "PRICE": price_clean,
                        "DELIVERY": buyer_or_deliv,
                        "COMMENTS": details_clean,
                        "raw_built": raw_built,
                    }
                    demo_extracted.append(demo_record)
                else:
                    sales_extracted.append(record)

    return sales_extracted, demo_extracted


def build_markdown_document(pdf_path: Path, issue_date: str, printed_date: str,
                            commentary: str, sales: List[Dict[str, Any]],
                            demos: List[Dict[str, Any]]) -> str:
    """Build high-fidelity markdown artifact for knowledge base."""
    stem = pdf_path.stem
    try:
        rel_path = pdf_path.resolve().relative_to(REPO_ROOT).as_posix()
    except Exception:
        rel_path = f"corpus/02-hellenic/shipbuilding/pdfs/{pdf_path.name}"
    year_str = issue_date[:4] if issue_date else "2026"

    lines = [
        "---",
        f'title: "Clarksons Hellas S&P Weekly - {printed_date}"',
        f'issue_date: "{issue_date}"',
        f'year: "{year_str}"',
        'broker: "Clarksons Hellas"',
        'category: "market_report"',
        f'source_file: "{rel_path}"',
        "---",
        "",
        f"# Clarksons Hellas S&P Weekly - {printed_date}",
        "",
        f"- **Date**: {issue_date} ({printed_date})",
        f"- **Source**: `{rel_path}`",
        f"- **Publisher**: Clarksons Hellas Ltd.",
        "",
        "## Desk Commentary",
        "",
        commentary if commentary else "*No editorial commentary.*",
        "",
        "## S&P Transaction Tables",
        "",
    ]

    # Bulker Sales
    bulker_recs = [r for r in sales if "bulk" in r["section"].lower()]
    lines.append("### Bulker Sales")
    lines.append("")
    if bulker_recs:
        lines.append("| Vessel | DWT | Built | Yard | Details | SS/DD | Price | Buyer |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in bulker_recs:
            lines.append(
                f"| {r['NAME']} | {r['DWT']} | {r['BUILT']} | {r['YARD']} | {r['COMMENTS']} | {r['SS_DD']} | {r['PRICE']} | {r['BUYERS']} |"
            )
    else:
        lines.append("*No bulker sales reported for this week.*")
    lines.append("")

    # Tanker Sales
    tanker_recs = [r for r in sales if "tank" in r["section"].lower()]
    lines.append("### Tanker Sales")
    lines.append("")
    if tanker_recs:
        lines.append("| Vessel | DWT | Built | Yard | Details | SS/DD | Price | Buyer |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in tanker_recs:
            lines.append(
                f"| {r['NAME']} | {r['DWT']} | {r['BUILT']} | {r['YARD']} | {r['COMMENTS']} | {r['SS_DD']} | {r['PRICE']} | {r['BUYERS']} |"
            )
    else:
        lines.append("*No tanker sales reported for this week.*")
    lines.append("")

    # Demolition Sales
    if demos:
        lines.append("## Demolition & Recycling Sales")
        lines.append("")
        lines.append("| Vessel | Type | DWT | Built | Details | Price | Delivery |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in demos:
            lines.append(
                f"| {r['NAME']} | {r['TYPE']} | {r['DWT']} | {r['BUILT']} | {r['COMMENTS']} | {r['PRICE']} | {r['DELIVERY']} |"
            )
        lines.append("")

    # Disclaimer / Footer
    lines.extend([
        "## Contact & Legal Disclaimer",
        "",
        "**Clarkson Hellas Ltd.**  ",
        "Direct: +(30) 210 458 6700 | Fax: +(30) 210 458 6799  ",
        "Website: www.clarksons.com  ",
        "",
        "> *The material and information contained herein are provided by Clarkson Hellas Ltd for general information purposes only.*",
        ""
    ])

    return "\n".join(lines)


def process_all(verify: bool = True) -> Dict[str, Any]:
    """Execute full extraction workflow across all discovered Clarksons PDFs."""
    OUT_MD.mkdir(parents=True, exist_ok=True)
    OUT_SERIES.mkdir(parents=True, exist_ok=True)

    # Discover and deduplicate all Clarksons PDFs
    all_pdfs: Dict[str, Path] = {}
    if BROKER_DIR.exists():
        for f in sorted(BROKER_DIR.glob("*.pdf")):
            h = hashlib.md5(f.read_bytes()).hexdigest()
            if h not in all_pdfs:
                all_pdfs[h] = f

    if HELLENIC_DIR.exists():
        for f in sorted(HELLENIC_DIR.rglob("*.pdf")):
            if "breakwave" in f.name.lower():
                continue
            h = hashlib.md5(f.read_bytes()).hexdigest()
            if h not in all_pdfs:
                all_pdfs[h] = f

    pdf_files = sorted(list(all_pdfs.values()), key=lambda x: x.name)
    print(f"Discovered {len(pdf_files)} unique Clarksons PDF files across broker & hellenic sources")

    all_sales_rows: List[Dict[str, Any]] = []
    all_demo_rows: List[Dict[str, Any]] = []
    report_summaries: List[Dict[str, Any]] = []

    for i, pdf_path in enumerate(pdf_files, 1):
        stem = pdf_path.stem
        fname = pdf_path.name
        doc = pymupdf.open(pdf_path)
        issue_date, printed_date = parse_issue_date(pdf_path, doc)
        commentary = extract_desk_commentary(doc)
        sales_recs, demo_recs = extract_all_transactions(doc, pdf_path, issue_date)

        # 1. Write <stem>.tables.json (both flat root and year subfolder)
        payload_json = {
            "issue_date": issue_date,
            "printed_date": printed_date,
            "source_file": fname,
            "sales_count": len(sales_recs),
            "demo_count": len(demo_recs),
            "sales": sales_recs,
            "demolitions": demo_recs
        }
        tab_json_path = OUT_MD / f"{stem}.tables.json"
        with open(tab_json_path, "w", encoding="utf-8") as f:
            json.dump(payload_json, f, indent=2, ensure_ascii=False)

        yr_str = issue_date[:4] if issue_date and issue_date[:4].isdigit() else "2026"
        yr_dir = OUT_MD / yr_str
        yr_dir.mkdir(parents=True, exist_ok=True)
        with open(yr_dir / f"{stem}.tables.json", "w", encoding="utf-8") as f:
            json.dump(payload_json, f, indent=2, ensure_ascii=False)

        # 2. Write <stem>.md (both flat root and year subfolder)
        md_content = build_markdown_document(pdf_path, issue_date, printed_date, commentary, sales_recs, demo_recs)
        md_path = OUT_MD / f"{stem}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        with open(yr_dir / f"{stem}.md", "w", encoding="utf-8") as f:
            f.write(md_content)

        report_summaries.append({
            "stem": stem,
            "filename": fname,
            "issue_date": issue_date,
            "printed_date": printed_date,
            "sales_count": len(sales_recs),
            "demo_count": len(demo_recs),
        })

        for r in sales_recs:
            extra_payload = {
                "stem": stem,
                "source_file": fname,
                "raw_built": r["raw_built"],
                "raw_details": r["raw_details"],
                "printed_date": printed_date,
            }
            csv_row = {
                "issue": r["issue_date"],
                "section": r["section"],
                "page": r["page"],
                "NAME": r["NAME"],
                "TYPE": r["TYPE"],
                "DWT": r["DWT"],
                "BUILT": r["BUILT"],
                "YARD": r["YARD"],
                "PRICE": r["PRICE"],
                "BUYERS": r["BUYERS"],
                "SS_DD": r["SS_DD"],
                "COMMENTS": r["COMMENTS"],
                "extra_json": json.dumps(extra_payload, ensure_ascii=False),
            }
            all_sales_rows.append(csv_row)

        for r in demo_recs:
            extra_payload = {
                "stem": stem,
                "source_file": fname,
                "raw_built": r["raw_built"],
                "printed_date": printed_date,
            }
            csv_row = {
                "issue": r["issue_date"],
                "section": r["section"],
                "page": r["page"],
                "NAME": r["NAME"],
                "TYPE": r["TYPE"],
                "DWT": r["DWT"],
                "BUILT": r["BUILT"],
                "YARD": r["YARD"],
                "PRICE": r["PRICE"],
                "DELIVERY": r["DELIVERY"],
                "COMMENTS": r["COMMENTS"],
                "extra_json": json.dumps(extra_payload, ensure_ascii=False),
            }
            all_demo_rows.append(csv_row)

        if i % 25 == 0 or i == len(pdf_files):
            print(f"[{i}/{len(pdf_files)}] {fname} -> {len(sales_recs)} sales, {len(demo_recs)} demos ({issue_date})")

    # Deduplicate series rows across duplicate issues
    seen_sales = set()
    deduped_sales = []
    for r in all_sales_rows:
        k = (r["issue"], r["NAME"].upper(), str(r["DWT"]), str(r["BUILT"]))
        if k not in seen_sales:
            seen_sales.add(k)
            deduped_sales.append(r)
    all_sales_rows = deduped_sales

    seen_demos = set()
    deduped_demos = []
    for r in all_demo_rows:
        k = (r["issue"], r["NAME"].upper(), str(r["DWT"]))
        if k not in seen_demos:
            seen_demos.add(k)
            deduped_demos.append(r)
    all_demo_rows = deduped_demos

    # 3. Write data/extracted/series/clarksons_sales_series.csv
    sales_cols = [
        "issue_date", "issue", "section", "page", "NAME", "TYPE", "DWT", "BUILT",
        "YARD", "PRICE", "BUYERS", "SS_DD", "COMMENTS", "extra_json"
    ]
    sales_csv_path = OUT_SERIES / "clarksons_sales_series.csv"
    with open(sales_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sales_cols)
        writer.writeheader()
        for row in all_sales_rows:
            dt_val = row.get("issue_date") or row.get("issue", "")
            row["issue_date"] = dt_val
            row["issue"] = dt_val
            writer.writerow(row)

    print(f"\nWritten {len(all_sales_rows)} total S&P sales rows to {sales_csv_path}")

    # 4. Write data/extracted/series/clarksons_demolition_series.csv
    demo_cols = [
        "issue_date", "issue", "section", "page", "NAME", "TYPE", "DWT", "BUILT",
        "YARD", "PRICE", "DELIVERY", "COMMENTS", "extra_json"
    ]
    demo_csv_path = OUT_SERIES / "clarksons_demolition_series.csv"
    with open(demo_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=demo_cols)
        writer.writeheader()
        for row in all_demo_rows:
            dt_val = row.get("issue_date") or row.get("issue", "")
            row["issue_date"] = dt_val
            row["issue"] = dt_val
            writer.writerow(row)

    print(f"Written {len(all_demo_rows)} total demolition rows to {demo_csv_path}")

    # Write run state summary
    state = {
        "reports_processed": len(pdf_files),
        "total_extracted_sales": len(all_sales_rows),
        "total_extracted_demos": len(all_demo_rows),
        "unique_issues": len(set(r["issue_date"] for r in report_summaries)),
        "reports": report_summaries,
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    return state


if __name__ == "__main__":
    state = process_all()
    print("Clarksons Extraction Complete.")
