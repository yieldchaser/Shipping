"""
Post-processor and sidecar generator for Star Asia W05.
Takes LlamaParse 19-page extraction, polishes markdown, creates structured .tables.json sidecar,
and updates master series files.
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

def html_table_to_md(html_str):
    headers = []
    th_matches = re.findall(r'<th[^>]*>(.*?)</th>', html_str, re.IGNORECASE | re.DOTALL)
    if th_matches:
        headers = [re.sub(r'<[^>]+>', '', h).strip() for h in th_matches]
    
    rows = []
    tr_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', html_str, re.IGNORECASE | re.DOTALL)
    for tr in tr_matches:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.IGNORECASE | re.DOTALL)
        if tds:
            rows.append([re.sub(r'<[^>]+>', ' ', td).strip() for td in tds])
            
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

def parse_md_table_to_dict(table_str):
    lines = [ln.strip() for ln in table_str.strip().split("\n") if ln.strip()]
    if len(lines) < 3:
        return None
    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    data_rows = []
    for line in lines[2:]:
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) == len(headers):
            row_dict = {headers[i]: cols[i] for i in range(len(headers))}
            data_rows.append(row_dict)
    return {"headers": headers, "rows": data_rows}

def main():
    with open(RAW_LLAMA, "r", encoding="utf-8") as f:
        raw = f.read()

    pages = raw.split("\n\n---\n\n")
    print(f"Total raw pages: {len(pages)}")

    cleaned_pages = []
    for i, p in enumerate(pages):
        p_clean = re.sub(r'<table[^>]*>.*?</table>', lambda m: html_table_to_md(m.group(0)), p, flags=re.IGNORECASE | re.DOTALL)
        p_clean = re.sub(r'~~+', '', p_clean)
        p_clean = re.sub(r'!\[.*?\]\(.*?\)', '', p_clean)
        p_clean = p_clean.replace(r'\~', '~')
        p_clean = p_clean.replace('\ufffd', '-')
        
        # Clean specific page titles / headers
        if i == 0:
            p_clean = re.sub(r'#+\s*WEEK\s*5\s*-\s*January\s*30th,\s*2026', '### WEEK 5 - January 30th, 2026', p_clean, flags=re.IGNORECASE)
        elif i == 13:  # Page 14 - Alang & Chattogram beaching
            # First table is Alang beaching (continuing Alang commentary from Page 13)
            # Second table is Chattogram beaching (under Chattogram narrative)
            parts = p_clean.split("Anchorage & Beaching Position (JANUARY 2026)")
            if len(parts) == 3:
                p_clean = (
                    parts[0]
                    + "### Anchorage & Beaching Position (JANUARY 2026) - Alang, India\n"
                    + parts[1]
                    + "### Anchorage & Beaching Position (JANUARY 2026) - Chattogram, Bangladesh\n"
                    + parts[2]
                )
        elif i == 14:  # Page 15 - Gadani beaching
            p_clean = re.sub(
                r'#*\s*Anchorage & Beaching Position\s*\(JANUARY 2026\)',
                '### Anchorage & Beaching Position (JANUARY 2026) - Gadani, Pakistan',
                p_clean,
                count=1
            )
        elif i == 9:   # Page 10 - Recycling snapshot cleanup
            p_clean = re.sub(r'IMPROVING\s*/\s*~*', 'IMPROVING', p_clean)
            p_clean = re.sub(r'STABLE\s*/\s*~*', 'STABLE', p_clean)

        p_clean = re.sub(r'__+', '', p_clean)
        p_clean = re.sub(r'#+\s*###\s*', '### ', p_clean)
        
        # Remove repetitive website footer lines
        lines = [line for line in p_clean.split("\n") if not (line.strip().startswith("STAR ASIA") and "star-asia.com.sg" in line.lower())]
        p_clean = "\n".join(lines).strip()
        cleaned_pages.append(f"## Page {i+1}\n\n" + p_clean)

    frontmatter = """---
title: "Star Asia Weekly Market Report - Week 05, 2026"
issue_date: "2026-01-30"
report_week: 5
year: 2026
publisher: "star_asia"
source_file: "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"
pages: 19
---

"""
    full_md = frontmatter + "\n\n---\n\n".join(cleaned_pages)

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(full_md)
    print(f"Wrote polished markdown to: {OUT_MD} ({len(full_md)} bytes)")

    # Extract structured tables for sidecar .tables.json
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

    table_blocks = re.findall(r'(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)', full_md)
    print(f"Total markdown tables detected: {len(table_blocks)}")

    for idx, tb in enumerate(table_blocks):
        tdict = parse_md_table_to_dict(tb)
        if tdict:
            tdict["table_id"] = f"table_{idx+1:02d}"
            tables_sidecar["tables"].append(tdict)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tables_sidecar, f, indent=2, ensure_ascii=False)
    print(f"Wrote structured tables JSON to: {OUT_JSON} ({len(tables_sidecar['tables'])} tables)")

    # Stack new series
    SERIES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 5-Year History Series
    hist_csv = SERIES_DIR / "star_asia_5y_history_series.csv"
    hist_headers = ["issue_date", "report_week", "destination", "year_2021", "year_2022", "year_2023", "year_2024", "year_2025", "source_file"]
    hist_rows = [
        {"issue_date": "2026-01-30", "report_week": "5", "destination": "Alang, India", "year_2021": "405", "year_2022": "575", "year_2023": "550", "year_2024": "490", "year_2025": "460", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "destination": "Chattogram, Bangladesh", "year_2021": "430", "year_2022": "605", "year_2023": "520", "year_2024": "520", "year_2025": "470", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "destination": "Gaddani, Pakistan", "year_2021": "415", "year_2022": "600", "year_2023": "540", "year_2024": "520", "year_2025": "430", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "destination": "Aliaga, Turkey", "year_2021": "240", "year_2022": "330", "year_2023": "310", "year_2024": "320", "year_2025": "360", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
    ]
    write_series_rows(hist_csv, hist_headers, hist_rows, key_fields=["issue_date", "destination"])

    # 2. Iron Ore Series
    iron_csv = SERIES_DIR / "star_asia_iron_ore_series.csv"
    iron_headers = ["issue_date", "report_week", "commodity", "grade_origin", "price_usd_mt", "change_wow_pct", "change_yoy_pct", "last_week_usd_mt", "last_year_usd_mt", "source_file"]
    iron_rows = [
        {"issue_date": "2026-01-30", "report_week": "5", "commodity": "Iron Ore Fines, CNF Rizhao, China", "grade_origin": "Fines, Fe 62% (Aust. Origin)", "price_usd_mt": "103", "change_wow_pct": "-0.96%", "change_yoy_pct": "-2.83%", "last_week_usd_mt": "104", "last_year_usd_mt": "106", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "commodity": "Iron Ore Fines, CNF Qingdao, China", "grade_origin": "Fines, Fe 62.5% (Brazil Origin)", "price_usd_mt": "103", "change_wow_pct": "-0.96%", "change_yoy_pct": "-3.73%", "last_week_usd_mt": "104", "last_year_usd_mt": "107", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
    ]
    write_series_rows(iron_csv, iron_headers, iron_rows, key_fields=["issue_date", "commodity"])

    # 3. Metals & Energy Series
    me_csv = SERIES_DIR / "star_asia_metals_energy_series.csv"
    me_headers = ["issue_date", "report_week", "category", "index_name", "units", "price", "change", "pct_change", "contract", "source_file"]
    me_rows = [
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "Copper (Comex)", "units": "USD / lb.", "price": "593.20", "change": "-27.15", "pct_change": "-4.42%", "contract": "Mar 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "3Mo Copper (L.M.E.)", "units": "USD / MT", "price": "13618.00", "change": "+531.50", "pct_change": "+4.06%", "contract": "N/A", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "3Mo Aluminum (L.M.E.)", "units": "USD / MT", "price": "3218.50", "change": "-38.50", "pct_change": "-1.18%", "contract": "N/A", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "3Mo Zinc (L.M.E.)", "units": "USD / MT", "price": "3412.00", "change": "+48.00", "pct_change": "+1.43%", "contract": "N/A", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Industrial Metals", "index_name": "3Mo Tin (L.M.E.)", "units": "USD / MT", "price": "55084.00", "change": "-869.00", "pct_change": "-1.55%", "contract": "N/A", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Energy", "index_name": "WTI Crude Oil (Nymex)", "units": "USD / bbl.", "price": "65.06", "change": "-0.36", "pct_change": "-0.43%", "contract": "Mar 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Energy", "index_name": "Brent Crude (ICE.)", "units": "USD / bbl.", "price": "70.71", "change": "0.00", "pct_change": "-0.06%", "contract": "Mar 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Energy", "index_name": "Crude Oil (Tokyo)", "units": "JPY / kl", "price": "65140.00", "change": "+1090.00", "pct_change": "+1.70%", "contract": "Jan 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
        {"issue_date": "2026-01-30", "report_week": "5", "category": "Energy", "index_name": "Natural Gas (Nymex)", "units": "USD / MMBtu", "price": "4.27", "change": "+0.35", "pct_change": "+9.01%", "contract": "Mar 2026", "source_file": "corpus/01-brokers/star_asia/2026/star_asia_2026_W05_Market-report-Week-5.pdf"},
    ]
    write_series_rows(me_csv, me_headers, me_rows, key_fields=["issue_date", "index_name"])

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

if __name__ == "__main__":
    main()
