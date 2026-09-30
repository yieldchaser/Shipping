"""
World-Class Polishing Engine for Star Asia Weekly Market Reports.

Refines Markdown to publication-grade quality:
1. Removes artificial '## Page N' breaks in favor of natural semantic sections.
2. Strips broker boilerplate, repeated running footers ('Shipbroking www.star-asia.com.sg'),
   telephones, emails, and legal disclaimers.
3. Pulls table footnotes out of table body rows into clean italicized notes below tables.
4. Formats large integer tonnages and rates (>= 10,000) with commas while preserving 4-digit years intact.
5. Standardizes typography (ASCII hyphens for en/em dashes) to prevent terminal replacement chars.
6. Emits structured .tables.json sidecars and updates stacked series CSVs.
"""

import os
import re
import json
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW_LLAMA = ROOT / "data" / "extracted" / "test_star_asia_w05_llamaparse.md"
OUT_MD = ROOT / "data" / "extracted" / "md" / "star_asia" / "star_asia_2026_W05_Market-report-Week-5.md"
OUT_JSON = ROOT / "data" / "extracted" / "md" / "star_asia" / "star_asia_2026_W05_Market-report-Week-5.tables.json"
SERIES_DIR = ROOT / "data" / "extracted" / "series"

def format_number_commas(val_str: str) -> str:
    """Format pure integer strings >= 10,000 with commas. Preserves 4-digit years intact."""
    val = val_str.strip()
    if re.fullmatch(r'\d{5,}', val):
        return f"{int(val):,}"
    return val

def html_table_to_md(html_str: str) -> str:
    headers = []
    th_matches = re.findall(r'<th[^>]*>(.*?)</th>', html_str, re.IGNORECASE | re.DOTALL)
    if th_matches:
        headers = [re.sub(r'<[^>]+>', '', h).strip() for h in th_matches]
    
    rows = []
    tr_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', html_str, re.IGNORECASE | re.DOTALL)
    for tr in tr_matches:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.IGNORECASE | re.DOTALL)
        if tds:
            row = [format_number_commas(re.sub(r'<[^>]+>', ' ', td).strip()) for td in tds]
            rows.append(row)
            
    if not headers and rows:
        headers = [f"Col {i+1}" for i in range(len(rows[0]))]
        
    if not headers:
        return html_str
        
    md = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        while len(r) < len(headers):
            r.append("")
        md.append("| " + " | ".join(r[:len(headers)]) + " |")
    return "\n".join(md)

def clean_markdown_table(table_str: str) -> str:
    lines = [ln.strip() for ln in table_str.strip().split("\n") if ln.strip()]
    if len(lines) < 3:
        return table_str
    
    header_line = lines[0]
    sep_line = lines[1]
    data_lines = []
    footnotes = []

    for ln in lines[2:]:
        # Check if row is actually a footnote masquerading as a row
        lower_ln = ln.lower()
        if "amount in usd" in lower_ln or "eco units" in lower_ln or "all prices are usd" in lower_ln:
            clean_fn = re.sub(r'^[\|\s\*\\]+', '', ln)
            clean_fn = re.sub(r'[\|\s\*\\]+$', '', clean_fn).strip()
            # Standardize footnote wording
            clean_fn = clean_fn.replace('\\*', '').replace('*', '').strip()
            if clean_fn:
                footnotes.append(f"*{clean_fn}*")
            continue
        
        # Format numbers >= 10000 with commas
        cols = [c.strip() for c in ln.strip("|").split("|")]
        formatted_cols = [format_number_commas(c) for c in cols]
        data_lines.append("| " + " | ".join(formatted_cols) + " |")

    res = [header_line, sep_line] + data_lines
    res_str = "\n".join(res)
    if footnotes:
        res_str += "\n\n" + "\n\n".join(footnotes)
    return res_str

def parse_md_table_to_dict(table_str: str):
    lines = [ln.strip() for ln in table_str.strip().split("\n") if ln.strip()]
    if len(lines) < 3:
        return None
    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    data_rows = []
    for line in lines[2:]:
        if line.startswith("*") and not line.startswith("* |"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) == len(headers):
            row_dict = {headers[i]: cols[i] for i in range(len(headers))}
            data_rows.append(row_dict)
    return {"headers": headers, "rows": data_rows}

def write_series_rows(csv_path: Path, headers: list, new_rows: list, key_fields: list):
    existing_rows = []
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)
    
    existing_keys = set()
    for r in existing_rows:
        k = tuple(r.get(kf, "") for kf in key_fields)
        existing_keys.add(k)
        
    added = 0
    for r in new_rows:
        k = tuple(r.get(kf, "") for kf in key_fields)
        if k not in existing_keys:
            existing_rows.append(r)
            existing_keys.add(k)
            added += 1
            
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(existing_rows)
    print(f"Updated {csv_path.name}: {len(existing_rows)} total rows (+{added} new)")

def polish_w05():
    with open(RAW_LLAMA, "r", encoding="utf-8") as f:
        raw = f.read()

    raw_pages = raw.split('\n\n---\n\n')
    print(f"Loaded {len(raw_pages)} raw pages from LlamaParse.")

    def clean_page(p_text: str) -> str:
        # Convert HTML tables to Markdown
        t = re.sub(r'<table[^>]*>.*?</table>', lambda m: html_table_to_md(m.group(0)), p_text, flags=re.IGNORECASE | re.DOTALL)
        # Strip image tags
        t = re.sub(r'!\[.*?\]\(.*?\)', '', t)
        # Strip running footers
        t = re.sub(r'(?i)^\s*(?:\*\*)?STAR\s*ASIA(?:\*\*)?\s*(?:<u>)?Shipbroking\s*\([^\)]*\)(?:</u>)?\s*$', '', t, flags=re.MULTILINE)
        t = re.sub(r'(?i)^\s*(?:<u>)?Shipbroking\s*\([^\)]*\)(?:</u>)?\s*$', '', t, flags=re.MULTILINE)
        t = re.sub(r'(?i)^\s*\*(?:STAR\s*ASIA\s*)?Shipbroking\s*\([^\)]*\)\*\s*$', '', t, flags=re.MULTILINE)
        t = re.sub(r'(?i)^\s*(?:\*\*)?STAR\s*ASIA(?:\*\*)?\s*$', '', t, flags=re.MULTILINE)
        # Clean OCR artifacts & typography
        t = re.sub(r'~~+', '', t)
        t = t.replace('\u2013', '-').replace('\u2014', '-').replace('\u2018', "'").replace('\u2019', "'")
        t = t.replace('\ufffd', '-')
        t = t.replace(r'\~', '~')
        t = re.sub(r'__+', '', t)
        t = re.sub(r'IMPROVING\s*/\s*~*', 'IMPROVING', t)
        t = re.sub(r'STABLE\s*/\s*~*', 'STABLE', t)
        # Clean tables
        t = re.sub(r'(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)', lambda m: clean_markdown_table(m.group(0)), t)
        # Clean leftover horizontal rules
        t = re.sub(r'^-{3,}$', '', t, flags=re.MULTILINE)
        return t.strip()

    pages = [clean_page(p) for p in raw_pages]
    print(f"Cleaned {len(pages)} pages.")

    doc_sections = []

    # Frontmatter
    doc_sections.append("""---
title: "Star Asia Weekly Market Report - Week 05, 2026"
issue_date: "2026-01-30"
report_week: 5
year: 2026
publisher: "star_asia"
source_file: "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"
pages: 19
---

# STAR ASIA WEEKLY REPORT
**WEEK 5 - January 30th, 2026**
""")

    # Section 1: Executive Lead Editorial (Page 1)
    p1 = pages[0]
    p1 = re.sub(r'(?i)#+\s*STAR\s*ASIA\s*WEEKLY\s*REPORT', '', p1)
    p1 = re.sub(r'(?i)#+\s*WEEK\s*\d+\s*-\s*[^\n]+', '', p1)
    p1 = re.sub(r'(?i)^\s*WEEK\s*\d+\s*-\s*[^\n]+$', '', p1, flags=re.MULTILINE)
    doc_sections.append("## 1. Executive Lead Editorial\n\n" + p1.strip())

    # Section 2: Dry Bulk Market (Pages 2-4)
    dry_bulk_content = []
    p2 = re.sub(r'(?im)^#+\s*Dry\s*Bulk\s*$', '', pages[1]).strip()
    dry_bulk_content.append(p2)

    p3 = pages[2].strip()
    p3 = re.sub(r'(?im)^#*\s*Handysize:\s*$', '**Handysize:**', p3)
    p3 = re.sub(r'#+\s*Baltic Exchange Dry Bulk Indices', '### Baltic Exchange Dry Bulk Indices', p3)
    p3 = re.sub(r'#+\s*Dry Bulk Values(?:\s*\(Weekly\))?', '### Dry Bulk Values (Weekly)', p3)
    p3 = re.sub(r'(?m)^\s*\*\s*\(Weekly\)\s*\*\s*$', '', p3)
    dry_bulk_content.append(p3)

    p4 = pages[3].strip()
    p4 = re.sub(r'#+\s*Dry\s*Bulk\s*-\s*S&P\s*Report', '### Dry Bulk - S&P Report', p4, flags=re.IGNORECASE)
    p4 = re.sub(r'#+\s*Dry Bulk 1 year T/C rates', '### Dry Bulk 1-Year T/C Rates (Quarterly Historical)', p4)
    dry_bulk_content.append(p4)
    doc_sections.append("## 2. Dry Bulk Market\n\n" + "\n\n".join(dry_bulk_content))

    # Section 3: Tanker Market (Pages 5-7)
    tanker_content = []
    p5 = re.sub(r'(?im)^#+\s*Tankers\s*$', '', pages[4]).strip()
    p5 = re.sub(r'<\/?u>', '', p5)
    tanker_content.append(p5)

    p6 = pages[5].strip()
    p6 = re.sub(r'#+\s*Baltic Exchange Tanker Indices', '### Baltic Exchange Tanker Indices', p6)
    p6 = re.sub(r'#+\s*Tankers Values(?:\s*\(Weekly\))?', '### Tankers Values (Weekly)', p6)
    p6 = re.sub(r'(?m)^\s*\*\s*\(Weekly\)\s*\*\s*$', '', p6)
    tanker_content.append(p6)

    p7 = pages[6].strip()
    p7 = re.sub(r'#+\s*Tankers S&P Report', '### Tankers S&P Report', p7)
    p7 = re.sub(r'#+\s*Tanker 1 year T/C rates', '### Tanker 1-Year T/C Rates (Quarterly Historical)', p7)
    tanker_content.append(p7)
    doc_sections.append("## 3. Tanker Market\n\n" + "\n\n".join(tanker_content))

    # Section 4: Container Market (Pages 8-9)
    container_content = []
    p8 = re.sub(r'(?im)^#+\s*Containers\s*$', '', pages[7]).strip()
    p8 = re.sub(r'#+\s*Containers Values(?:\s*\(Weekly\))?', '### Containers Values (Weekly)', p8)
    p8 = re.sub(r'(?m)^\s*\*\s*\(Weekly\)\s*\*\s*$', '', p8)
    p8 = re.sub(r'\*\s*\(amount in USD million\)\s*/\s*=\s*Eco units\*', '*(amount in USD million) | (E) - eco units*', p8)
    p8 = re.sub(r'#+\s*S&P Containers Report', '### S&P Containers Report', p8)
    container_content.append(p8)

    p9 = pages[8].strip()
    p9 = re.sub(r'#+\s*Container 6-12 months T/C rates', '### Container 6-12 Months T/C Rates (Quarterly Historical)', p9)
    container_content.append(p9)
    doc_sections.append("## 4. Container Market\n\n" + "\n\n".join(container_content))

    # Section 5: Ship Recycling Market Intelligence (Pages 10-15)
    recycling_content = []
    p10 = pages[9].strip()
    p10 = re.sub(r'#+\s*Ship Recycling Market Snapshot', '### Ship Recycling Market Snapshot', p10)
    p10 = re.sub(r'##\s*5-Year Ship Recycling Average Historical Prices', '### 5-Year Ship Recycling Average Historical Prices', p10)
    # Clean Turkey cell footnote in Ship Recycling Market Snapshot
    p10 = re.sub(
        r'\*\*TURKEY\*\*\s*<br\/>\*?[^\n\|]*?(?=\s*\|)',
        r'**TURKEY**',
        p10,
        flags=re.IGNORECASE
    )
    # Ensure footnote is included in notes below table
    if 'For non-EU ships' not in p10 and 'USD 20-30/ton less' not in p10:
        p10 = re.sub(
            r'(- Prices quoted are basis simple Japanese[^\n]+)',
            r'\1\n- *Turkey prices quoted are for non-EU ships. For E.U. ships, prices are about USD 20-30/ton less.*',
            p10
        )
    recycling_content.append(p10)

    p11 = pages[10].strip()
    p11 = re.sub(r'#+\s*Ships Sold for Recycling', '### Ships Sold for Recycling (Fixtures)', p11)
    p11 = re.sub(r'#+\s*Recycling Ships Price Trend', '### Recycling Ships Price Trend (Quarterly Historical)', p11)
    recycling_content.append(p11)

    p12 = pages[11].strip()
    p12 = re.sub(r'#+\s*Total number of Vessel sold per month', '### Total Number of Vessels Sold Per Month', p12)
    p12 = re.sub(r'#+\s*Sub-continent total Light Displacement Tonnage in metric tons', '### Sub-Continent Total Light Displacement Tonnage (Metric Tons)', p12)
    recycling_content.append(p12)

    p13 = pages[12].strip()
    p13 = re.sub(r'#+\s*COMPARISON OF TOTAL LIGHT DISPLACEMENT TONNAGE \(LDT\) SOLD 5 YEARS.*', '### Comparison of Total Light Displacement Tonnage (LDT) Sold 5 Years (January 2021 - December 2025)', p13)
    p13 = re.sub(r'##\s*Insights', '### Waterfront Insights & Beaching Positions', p13)
    p13 = re.sub(r'##\s*\*+Alang\*+', '#### Alang (India) Waterfront Insights & Beaching Position of the Mud', p13)
    recycling_content.append(p13)

    p14 = pages[13].strip()
    p14 = re.sub(r'Anchorage & Beaching Position \(JANUARY 2026\)', '##### Anchorage & Beaching Position (January 2026) - Alang, India', p14, count=1)
    p14 = re.sub(r'##\s*Chattogram', '#### Chattogram (Bangladesh) Waterfront Insights & Beaching Position of the Mud', p14)
    p14 = re.sub(r'Anchorage & Beaching Position \(JANUARY 2026\)', '##### Anchorage & Beaching Position (January 2026) - Chattogram, Bangladesh', p14, count=1)
    recycling_content.append(p14)

    p15 = pages[14].strip()
    p15 = re.sub(r'(?im)^#+\s*Gadani\s*$', '#### Gadani (Pakistan) Waterfront Insights & Beaching Position of the Mud', p15)
    p15 = re.sub(r'#+\s*Anchorage & Beaching Position \(JANUARY 2026\)', '##### Anchorage & Beaching Position (January 2026) - Gadani, Pakistan', p15, count=1)
    p15 = re.sub(r'#+\s*Aliaga,\s*Turkiye', '#### Aliaga (Turkiye) Waterfront Insights', p15)
    
    # Clean Beaching Tide Dates & Bunker Prices on Page 15
    beaching_tide_clean = """### Beaching Tide Dates 2026

| LOCATION | FIRST SPRING TIDE PERIOD | SECOND SPRING TIDE PERIOD |
| -------- | ------------------------ | ------------------------- |
| Chattogram, Bangladesh | 3 ~ 6 February | 19 ~ 22 February |
| Alang, India | 30 January ~ 6 February | 16 ~ 23 February |"""

    bunker_prices_clean = """### Bunker Prices (USD/ton)

| PORTS | VLSFO (0.5%) | HSFO (3.5%) | MGO (0.1%) |
| ----- | ------------ | ----------- | ---------- |
| SINGAPORE | 465 | 425 | 656 |
| HONG KONG | 483 | 449 | 685 |
| FUJAIRAH | 461 | 397 | 752 |
| ROTTERDAM | 433 | 390 | 683 |
| HOUSTON | 462 | 362 | 702 |"""

    # Replace Beaching Tide Dates and Bunker Prices tables
    p15 = re.sub(r'\|?\s*#*BEACHING TIDE DATES 2026[\s\S]*?(?=\n\n\|?\s*#*BUNKER PRICES|\Z)', beaching_tide_clean + '\n\n', p15, flags=re.IGNORECASE)
    p15 = re.sub(r'\|?\s*#*BUNKER PRICES \(USD/ton\)[\s\S]*?(?=\n\n|\Z)', bunker_prices_clean, p15, flags=re.IGNORECASE)
    recycling_content.append(p15)
    doc_sections.append("## 5. Ship Recycling Market Intelligence\n\n" + "\n\n".join(recycling_content))

    # Section 6: Ferrous Scrap Market & Foreign Exchange (Pages 16-17)
    scrap_content = []
    p16 = pages[15].strip()
    
    # Extract Exchange Rates table from page 16
    fx_clean = """### Foreign Exchange Rates

| CURRENCY | CURRENT (JAN 30) | PREVIOUS (JAN 23) | W-O-W % CHANGE |
| -------- | ---------------- | ----------------- | -------------- |
| USD / CNY (CHINA) | 6.94 | 6.96 | +0.29% |
| USD / BDT (BANGLADESH) | 122.20 | 122.32 | +0.10% |
| USD / INR (INDIA) | 91.87 | 91.63 | -0.26% |
| USD / PKR (PAKISTAN) | 279.69 | 279.88 | +0.07% |
| USD / TRY (TURKEY) | 43.42 | 43.39 | -0.07% |"""

    # Remove raw exchange table from p16 text
    p16_no_fx = re.sub(r'\|?\s*EXCHANGE RATES[\s\S]*?(?=\n\n|\Z)', '', p16, flags=re.IGNORECASE).strip()
    p16_no_fx = re.sub(r'#+\s*Sub-Continent and Turkey ferrous scrap markets insights', '', p16_no_fx, flags=re.IGNORECASE).strip()
    p16_no_fx = re.sub(r'^Sub-Continent and Turkey ferrous scrap markets insights\s*', '', p16_no_fx, flags=re.IGNORECASE).strip()
    
    scrap_content.append("### Sub-Continent and Turkey Ferrous Scrap Market Insights\n\n" + p16_no_fx)

    p17 = pages[16].strip()
    p17 = re.sub(r'#+\s*\*+Turkiye\*+', '#### Turkiye Ferrous Scrap Insights', p17)
    p17 = re.sub(r'##\s*HMS 1/2 & Tangshan', '### Sub-Continent & China Benchmark Scrap Trends', p17)
    p17 = re.sub(r'###\s*HMS 1/2 TURKEY CFR \(USD/T\)', '#### HMS 1/2 Turkey CFR (USD/T)', p17)
    p17 = re.sub(r'###\s*TANGSHAN BILLET EX-WORKS \(CNY/T\)', '#### Tangshan Billet Ex-Works (CNY/T)', p17)
    
    comm_split = p17.find('## **Commodities')
    if comm_split != -1:
        scrap_part = p17[:comm_split].strip()
        comm_p17 = p17[comm_split:].strip()
    else:
        scrap_part = p17
        comm_p17 = ""
    
    # Split scrap_part into Turkiye insights and benchmark trends
    bench_split = scrap_part.find('### Sub-Continent & China Benchmark Scrap Trends')
    if bench_split != -1:
        turk_insights = scrap_part[:bench_split].strip()
        bench_trends = scrap_part[bench_split:].strip()
        scrap_content.append(turk_insights)
        scrap_content.append(fx_clean)
        scrap_content.append(bench_trends)
    else:
        scrap_content.append(scrap_part)
        scrap_content.append(fx_clean)

    doc_sections.append("## 6. Ferrous Scrap Market & Foreign Exchange Rates\n\n" + "\n\n".join(scrap_content))

    # Section 7: Commodities (Week in Focus) (Pages 17-19)
    comm_content = []
    if comm_p17:
        comm_p17 = re.sub(r'##\s*\*+Commodities\s*\(\*+Week in focus\*+\)\*+', '### Industrial Metals & Commodities Macro Commentary', comm_p17)
        comm_content.append(comm_p17)

    p18 = pages[17].strip()
    # Fix split sentence across pages 17 and 18
    if comm_content:
        # Check if previous ended with 'as'
        if comm_content[-1].rstrip().endswith(' as'):
            p18 = p18.lstrip()
            # Merge directly
            comm_content[-1] = comm_content[-1].rstrip() + ' ' + p18
            p18 = ""

    if p18:
        p18 = re.sub(r'(?m)^#*\s*~*Iron Ore~*\s*$', '### Iron Ore Spot Prices (China CNF/CFR)', p18)
        comm_content.append(p18)
    else:
        # Re-attach iron ore header if it was in p18
        if 'Iron Ore' in comm_content[-1]:
            comm_content[-1] = re.sub(r'(?m)^#*\s*~*Iron Ore~*\s*$', '\n\n### Iron Ore Spot Prices (China CNF/CFR)\n', comm_content[-1])

    p19 = pages[18].strip()
    p19 = re.sub(r'#+\s*Industrial Metal Rates', '### Industrial Metal Rates', p19)
    p19 = re.sub(r'#+\s*Crude Oil & Natural Gas Rates', '### Crude Oil & Natural Gas Rates', p19)
    p19 = re.sub(r'<\/?sup>', '', p19)
    note_idx = p19.find('*Note: All rates')
    if note_idx != -1:
        note_end = p19.find('\n', note_idx)
        if note_end != -1:
            p19 = p19[:note_end].strip()
        else:
            p19 = p19.strip()
    comm_content.append(p19)
    doc_sections.append("## 7. Commodities (Week in Focus)\n\n" + "\n\n".join(comm_content))

    # Final document assembly
    final_md = "\n\n---\n\n".join(doc_sections).strip() + "\n"

    # Remove any leftover stray broker lines

    final_md = re.sub(r'(?im)^\s*STAR\s*ASIA\s*<u>.*$', '', final_md)
    final_md = re.sub(r'(?im)^\s*\*\*STAR\s*ASIA\*\*.*$', '', final_md)
    final_md = re.sub(r'(?im)^\s*STAR\s*ASIA\s*\*+.*$', '', final_md)
    final_md = re.sub(r'\n{3,}', '\n\n', final_md)

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(final_md)
    print(f"Wrote publication-grade markdown: {OUT_MD} ({len(final_md)} bytes, {len(final_md.splitlines())} lines)")

    # Build sidecar .tables.json
    tables_sidecar = {
        "metadata": {
            "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf",
            "publisher": "star_asia",
            "issue_date": "2026-01-30",
            "report_week": 5,
            "year": 2026,
            "pages": 19
        },
        "tables": []
    }

    table_blocks = re.findall(r'(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)', final_md)
    print(f"Total markdown tables in polished document: {len(table_blocks)}")

    for idx, tb in enumerate(table_blocks):
        tdict = parse_md_table_to_dict(tb)
        if tdict:
            tdict["table_id"] = f"table_{idx+1:02d}"
            tables_sidecar["tables"].append(tdict)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tables_sidecar, f, indent=2, ensure_ascii=False)
    print(f"Wrote structured tables JSON: {OUT_JSON} ({len(tables_sidecar['tables'])} tables)")

    # Update series files
    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    hist_csv = SERIES_DIR / "star_asia_5y_history_series.csv"
    hist_headers = ["issue_date", "report_week", "destination", "year_2021", "year_2022", "year_2023", "year_2024", "year_2025", "source_file"]
    hist_rows = [
        {"issue_date": "2026-01-30", "report_week": "5", "destination": "Alang, India", "year_2021": "405", "year_2022": "575", "year_2023": "550", "year_2024": "490", "year_2025": "460", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "destination": "Chattogram, Bangladesh", "year_2021": "430", "year_2022": "605", "year_2023": "520", "year_2024": "520", "year_2025": "470", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "destination": "Gaddani, Pakistan", "year_2021": "415", "year_2022": "600", "year_2023": "540", "year_2024": "520", "year_2025": "430", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "destination": "Aliaga, Turkey", "year_2021": "240", "year_2022": "330", "year_2023": "310", "year_2024": "320", "year_2025": "360", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
    ]
    write_series_rows(hist_csv, hist_headers, hist_rows, key_fields=["issue_date", "destination"])

    iron_csv = SERIES_DIR / "star_asia_iron_ore_series.csv"
    iron_headers = ["issue_date", "report_week", "commodity", "grade_origin", "price_usd_mt", "change_wow_pct", "change_yoy_pct", "last_week_usd_mt", "last_year_usd_mt", "source_file"]
    iron_rows = [
        {"issue_date": "2026-01-30", "report_week": "5", "commodity": "Iron Ore Fines, CNF Rizhao, China", "grade_origin": "Fines, Fe 62% (Aust. Origin)", "price_usd_mt": "103", "change_wow_pct": "-0.96%", "change_yoy_pct": "-2.83%", "last_week_usd_mt": "104", "last_year_usd_mt": "106", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "commodity": "Iron Ore Fines, CNF Qingdao, China", "grade_origin": "Fines, Fe 62.5% (Brazil Origin)", "price_usd_mt": "103", "change_wow_pct": "-0.96%", "change_yoy_pct": "-3.73%", "last_week_usd_mt": "104", "last_year_usd_mt": "107", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
    ]
    write_series_rows(iron_csv, iron_headers, iron_rows, key_fields=["issue_date", "commodity"])

    me_csv = SERIES_DIR / "star_asia_metals_energy_series.csv"
    me_headers = ["issue_date", "report_week", "category", "index_name", "units", "price", "change", "pct_change", "contract", "source_file"]
    me_rows = [
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "Copper (Comex)", "units": "USD / lb.", "price": "593.20", "change": "-27.15", "pct_change": "-4.42%", "contract": "Mar 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "3Mo Copper (L.M.E.)", "units": "USD / MT", "price": "13,618.00", "change": "+531.50", "pct_change": "+4.06%", "contract": "N/A", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "3Mo Aluminum (L.M.E.)", "units": "USD / MT", "price": "3,218.50", "change": "-38.50", "pct_change": "-1.18%", "contract": "N/A", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "3Mo Zinc (L.M.E.)", "units": "USD / MT", "price": "3,412.00", "change": "+48.00", "pct_change": "+1.43%", "contract": "N/A", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "3Mo Tin (L.M.E.)", "units": "USD / MT", "price": "55,084.00", "change": "-869.00", "pct_change": "-1.55%", "contract": "N/A", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Energy", "index_name": "WTI Crude Oil (Nymex)", "units": "USD / bbl.", "price": "65.06", "change": "-0.36", "pct_change": "-0.43%", "contract": "Mar 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Energy", "index_name": "Brent Crude (ICE.)", "units": "USD / bbl.", "price": "70.71", "change": "0.00", "pct_change": "-0.06%", "contract": "Mar 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Energy", "index_name": "Crude Oil (Tokyo)", "units": "JPY / kl", "price": "65,140.00", "change": "+1,090.00", "pct_change": "+1.70%", "contract": "Jan 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Energy", "index_name": "Natural Gas (Nymex)", "units": "USD / MMBtu", "price": "4.27", "change": "+0.35", "pct_change": "+9.01%", "contract": "Mar 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
    ]
    write_series_rows(me_csv, me_headers, me_rows, key_fields=["issue_date", "index_name"])

if __name__ == "__main__":
    polish_w05()
