"""
Hellenic Demolition Intelligence Extraction Pipeline.

Extracts weekly reports across three premier global cash buyers & brokers:
1. Athenian Shipbrokers S.A. (286 reports)
2. Best Oasis Limited (58 reports)
3. GMS Inc. (265 reports)

Produces:
- Markdown files with YAML frontmatter under data/extracted/md/hellenic/demolition/<publisher>/<year>/
- Structured table JSON sidecars (.tables.json) with issue_date stamped
- Five master stacked time series in data/extracted/series/:
  1. hellenic_athenian_demolition_series.csv
  2. hellenic_best_oasis_demolition_series.csv
  3. hellenic_best_oasis_deals_series.csv
  4. hellenic_gms_demolition_series.csv
  5. hellenic_gms_port_positions_series.csv
"""

import hashlib
import os
import re
import json
import logging
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd
import pymupdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("HellenicDemolition")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEMO_DIR = REPO_ROOT / "corpus" / "02-hellenic" / "demolition"
MD_BASE_DIR = REPO_ROOT / "data" / "extracted" / "md" / "hellenic" / "demolition"
SERIES_DIR = REPO_ROOT / "data" / "extracted" / "series"

SERIES_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# 1. Athenian Shipbrokers Extraction
# ------------------------------------------------------------------------------
def extract_athenian(pdf_path, issue_date):
    doc = pymupdf.open(pdf_path)
    text = doc[0].get_text()
    
    # Extract week number
    m_week = re.search(r"Week\s+(\d+)", text, re.IGNORECASE)
    report_week = int(m_week.group(1)) if m_week else None
    
    # Extract prices
    # Standard format: India, Bangladesh, Pakistan, Turkey for Bulkers, Tankers, Containers
    # Let's extract words with coordinates
    words = doc[0].get_text("words")
    
    # Athenian tables list:
    # Tankers / Dry / Containers across India, Bangladesh, Pakistan, Turkey
    # Usually has ~12 prices starting with $
    prices = [w[4] for w in words if w[4].startswith("$") and re.match(r"^\$\d{3}", w[4])]
    
    records = []
    # If standard 12 prices: 4 countries x 3 sectors
    # Order on sheet: India, Bangladesh, Pakistan, Turkey
    countries = ["India", "Bangladesh", "Pakistan", "Turkey"]
    sectors = ["Tankers", "Dry Bulk", "Containers"]
    
    # Let's map sequentially if 12 prices exist
    if len(prices) >= 12:
        idx = 0
        for sec in sectors:
            for c in countries:
                if idx < len(prices):
                    try:
                        p_val = float(prices[idx].replace("$", "").replace(",", ""))
                        records.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "country": c,
                            "sector": sec,
                            "price_usd_per_ldt": p_val,
                            "source_file": pdf_path.name
                        })
                        idx += 1
                    except Exception:
                        pass

    # Markdown narrative
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    narrative_lines = []
    for l in lines:
        if not any(skip in l for skip in ["Tel:+30", "Email S & P", "PLEASED TO GUIDE YOU"]):
            narrative_lines.append(l)
    narrative = "\n\n".join(narrative_lines[:15])
    
    return report_week, records, narrative

# ------------------------------------------------------------------------------
# 2. Best Oasis Extraction
# ------------------------------------------------------------------------------
def extract_best_oasis(pdf_path, issue_date):
    doc = pymupdf.open(pdf_path)
    pno = len(doc) - 1 # Page 4 has tables
    text = doc[pno].get_text()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    
    # Week number from page 1
    p1_text = doc[0].get_text()
    m_week = re.search(r"WEEK\s+(\d+)", p1_text, re.IGNORECASE)
    report_week = int(m_week.group(1)) if m_week else None
    
    # 1. Indicative Demolition Prices
    # Pattern: LOCATION, STATUS, CONTAINER, TANKER, BULKER, WOW_CHG
    price_records = []
    countries = ["INDIA", "BANGLADESH", "PAKISTAN", "TURKIYE", "TURKEY"]
    for i, l in enumerate(lines):
        if l.upper() in countries:
            # Look ahead for status and numbers
            sub = lines[i:i+8]
            # sub items might be: ['INDIA', 'FIRM', '485', '455', '440', '(0)']
            country = l.capitalize()
            status = "N/A"
            c_val, t_val, b_val, chg = None, None, None, None
            nums = []
            for item in sub[1:]:
                if item.upper() in ["FIRM", "MODERATE", "STEADY", "WEAK"]:
                    status = item.capitalize()
                elif re.match(r"^\d{3}$", item):
                    nums.append(float(item))
                elif "%" in item or re.match(r"^\([+-]?\s*[\d.]+\)$", item):
                    chg = item
            if len(nums) >= 3:
                price_records.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "location": country,
                    "market_status": status,
                    "container_usd_ldt": nums[0],
                    "tanker_usd_ldt": nums[1],
                    "bulker_usd_ldt": nums[2],
                    "wow_change_pct": chg or "0",
                    "source_file": pdf_path.name
                })
                
    # 2. Demolition Deals
    deal_records = []
    # Lines after 'LIST OF VESSELS SOLD' or 'VESSEL NAME'
    deal_start = False
    for i, l in enumerate(lines):
        if "LIST OF VESSELS SOLD" in l.upper() or "VESSEL NAME" in l.upper():
            deal_start = True
            continue
        if deal_start:
            if "DISCLAIMER" in l.upper():
                break
            # Check if this line looks like a vessel name
            # Deal pattern: NAME, TYPE, LDT, TERM, LOCATION, PRICE
            # Often followed by numbers
            m_num = re.search(r"^[\d,]+$", l)
            if m_num and i > 0:
                vessel_name = lines[i-2] if i >= 2 and not re.search(r"^[\d,]+$", lines[i-2]) else lines[i-1]
                vessel_type = lines[i-1] if i >= 2 and not re.search(r"^[\d,]+$", lines[i-2]) else "N/A"
                ldt_val = l.replace(",", "")
                # next lines: term, location, price
                sale_terms = lines[i+1] if i+1 < len(lines) else "N/A"
                loc = lines[i+2] if i+2 < len(lines) else "N/A"
                price_str = lines[i+3] if i+3 < len(lines) else "N/A"
                deal_records.append({
                    "issue_date": issue_date,
                    "vessel_name": vessel_name,
                    "vessel_type": vessel_type,
                    "ldt": ldt_val,
                    "sale_terms": sale_terms,
                    "delivery_location": loc,
                    "price_usd_per_ldt": price_str,
                    "source_file": pdf_path.name
                })
                
    # Full commentary from pages 2 and 3
    narrative_parts = []
    for p in range(1, min(3, len(doc))):
        narrative_parts.append(doc[p].get_text().strip())
    narrative = "\n\n".join(narrative_parts)
    
    return report_week, price_records, deal_records, narrative

# ------------------------------------------------------------------------------
# 3. GMS Extraction
# ------------------------------------------------------------------------------
def extract_gms(pdf_path, issue_date):
    doc = pymupdf.open(pdf_path)
    
    # Week number
    p1_text = doc[0].get_text()
    m_week = re.search(r"Week\s+(\d+)", p1_text, re.IGNORECASE)
    report_week = int(m_week.group(1)) if m_week else None
    
    # 1. Market Rankings (usually page 5)
    rankings_records = []
    for pno in range(len(doc)):
        text = doc[pno].get_text()
        if "MARKET RANKINGS" in text.upper():
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for i, l in enumerate(lines):
                if l in ["1", "2", "3", "4"] and i + 5 < len(lines):
                    rank = int(l)
                    loc = lines[i+1]
                    sent = lines[i+2]
                    dry = lines[i+3]
                    tanker = lines[i+4]
                    cont = lines[i+5]
                    if any(c in loc for c in ["Pakistan", "Bangladesh", "India", "Turkey"]):
                        rankings_records.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "rank": rank,
                            "location": loc,
                            "sentiment": sent,
                            "dry_bulk_usd_ldt": dry,
                            "tankers_usd_ldt": tanker,
                            "containers_usd_ldt": cont,
                            "source_file": pdf_path.name
                        })
                        
    # 2. Port Positions (usually page 7)
    port_records = []
    current_port = "Alang"
    for pno in range(len(doc)):
        text = doc[pno].get_text()
        if "PORT POSITION AS OF" in text.upper():
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for i, l in enumerate(lines):
                if "ALANG" in l.upper():
                    current_port = "Alang"
                elif "CHATTOGRAM" in l.upper():
                    current_port = "Chattogram"
                elif "GADANI" in l.upper():
                    current_port = "Gadani"
                elif "ALIAGA" in l.upper():
                    current_port = "Aliaga"
                elif re.match(r"^\d+$", l) and i + 4 < len(lines):
                    v_name = lines[i+1]
                    ldt = lines[i+2]
                    v_type = lines[i+3]
                    status = lines[i+4]
                    if re.match(r"^[\d,]+$", ldt):
                        port_records.append({
                            "issue_date": issue_date,
                            "port": current_port,
                            "vessel_name": v_name,
                            "ldt": ldt,
                            "vessel_type": v_type,
                            "status": status,
                            "source_file": pdf_path.name
                        })
                        
    # Commentary
    narrative_parts = []
    for pno in range(min(5, len(doc))):
        narrative_parts.append(doc[pno].get_text().strip())
    narrative = "\n\n".join(narrative_parts)
    
    return report_week, rankings_records, port_records, narrative

# ------------------------------------------------------------------------------
# 4. Pipeline Execution Across All HTML Articles in Demolition
# ------------------------------------------------------------------------------
def publisher_branch(pdf_name: str, title: str) -> str:
    """Which publisher branch a document is routed to.

    Same predicates and same order as the dispatch in main(), so the dedup key
    below cannot suppress a copy that produces rows for a DIFFERENT series.
    """
    n, t = pdf_name.lower(), title.lower()
    if "athenian" in n or "athenian" in t:
        return "athenian"
    if "best-oasis" in n or "best oasis" in t:
        return "best_oasis"
    if "gms" in n or "gms" in t:
        return "gms"
    return ""


def main():
    html_files = sorted(list(DEMO_DIR.glob("**/*.html")))
    logger.info(f"Total HTML articles in demolition: {len(html_files)}")
    
    athenian_series = []
    best_oasis_series = []
    best_oasis_deals = []
    gms_series = []
    gms_port_positions = []
    
    processed_count = 0
    seen_names = set()
    seen_content = set()
    
    for h in html_files:
        soup = BeautifulSoup(h.read_bytes(), "html.parser")
        title_tag = soup.find("title")
        title = title_tag.text.strip() if title_tag else h.stem
        
        # Extract ISO date from filename (e.g. 2024-01-03_...)
        m_date = re.match(r"^(\d{4}-\d{2}-\d{2})", h.name)
        issue_date = m_date.group(1) if m_date else "unknown"
        year = issue_date[:4] if issue_date != "unknown" else "unknown"
        
        # Find companion PDF
        pdf_path = None
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if ".pdf" in href.lower():
                cand = (h.parent / href).resolve()
                if cand.exists():
                    pdf_path = cand
                    break
                cand_matches = list(DEMO_DIR.rglob(cand.name))
                if cand_matches:
                    pdf_path = cand_matches[0]
                    break
        
        if not pdf_path:
            continue
            
        # Deduplicate identical PDFs. TWO rules, both required.
        #
        #  1. By FILENAME, as this always did. Not redundant: a collection-route
        #     alias (a 2025 archive page whose "latest report" link still points at
        #     2022's PDF) must not be re-read under a new issue_date. Dropping this
        #     rule was measured to ADD 4 spurious dates - 2024-12-23, 2025-09-09,
        #     2025-12-16, 2025-12-23 - each carrying a 2022/2024 report's prices.
        #  2. By CONTENT + issue_date + publisher branch. New: the filename rule
        #     cannot see the two collection routes that fetch the SAME issue under
        #     different names (a filename is not an identity). Measured 2026-10-01,
        #     the Athenian twins put 384 duplicate rows into
        #     hellenic_athenian_demolition_series.csv: 32 issue dates carry 24 rows
        #     where the issue has 12. Deduped, that file is 3,300 -> 2,916 rows with
        #     the same 242 issue dates and every other row byte-identical.
        #
        # issue_date and the branch are part of the content key on purpose: a
        # content-only key was measured to be destructive, suppressing 2026-06-13
        # (one file collected under three publisher names) and the 2022-05-03
        # re-collection of the week-16 GMS file, which DELETED 4 rows and 1 date from
        # hellenic_gms_demolition_series.csv and 33 rows and 2 dates from
        # hellenic_gms_port_positions_series.csv.
        try:
            digest = hashlib.md5(pdf_path.read_bytes()).hexdigest()
        except OSError:
            digest = pdf_path.name
        content_key = (digest, issue_date, publisher_branch(pdf_path.name, title))
        if pdf_path.name in seen_names or content_key in seen_content:
            continue
        seen_names.add(pdf_path.name)
        seen_content.add(content_key)
        
        name_l = pdf_path.name.lower()
        title_l = title.lower()
        
        # 1. Athenian
        if "athenian" in name_l or "athenian" in title_l:
            try:
                week, recs, narr = extract_athenian(pdf_path, issue_date)
                athenian_series.extend(recs)
                # Save markdown
                md_dir = MD_BASE_DIR / "athenian" / year
                md_dir.mkdir(parents=True, exist_ok=True)
                md_file = md_dir / f"athenian_{issue_date}_{pdf_path.stem}.md"
                json_file = md_file.with_suffix(".tables.json")
                
                md_content = f"""---
title: "{title}"
issue_date: "{issue_date}"
year: {year}
publisher: "Athenian Shipbrokers S.A."
source: "hellenic_demolition"
category: "demolition"
report_week: {week}
source_file: "corpus/02-hellenic/demolition/pdfs/{pdf_path.name}"
tables_count: 1
---

# {title}

## Athenian Shipbrokers Scrap Price Assessment

| Country | Tankers ($/LDT) | Dry Bulk ($/LDT) | Containers ($/LDT) |
|:---|:---|:---|:---|
"""
                # Group records by country
                c_map = {}
                for r in recs:
                    c = r["country"]
                    if c not in c_map:
                        c_map[c] = {}
                    c_map[c][r["sector"]] = r["price_usd_per_ldt"]
                for c, s_dict in c_map.items():
                    md_content += f"| {c} | ${s_dict.get('Tankers', '-')} | ${s_dict.get('Dry Bulk', '-')} | ${s_dict.get('Containers', '-')} |\n"
                
                md_content += f"\n## Market Commentary\n\n{narr}\n"
                md_file.write_text(md_content, encoding="utf-8")
                
                # Sidecar JSON
                sidecar = {
                    "title": title,
                    "issue_date": issue_date,
                    "year": year,
                    "publisher": "Athenian Shipbrokers S.A.",
                    "tables_count": 1,
                    "tables": [{
                        "title": "Athenian Shipbrokers Scrap Price Assessment",
                        "columns": ["country", "sector", "price_usd_per_ldt"],
                        "row_count": len(recs),
                        "rows": recs
                    }]
                }
                json_file.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                processed_count += 1
            except Exception as e:
                logger.error(f"Error Athenian {pdf_path.name}: {e}")

        # 2. Best Oasis
        elif "best-oasis" in name_l or "best oasis" in title_l:
            try:
                week, p_recs, d_recs, narr = extract_best_oasis(pdf_path, issue_date)
                best_oasis_series.extend(p_recs)
                best_oasis_deals.extend(d_recs)
                
                md_dir = MD_BASE_DIR / "best_oasis" / year
                md_dir.mkdir(parents=True, exist_ok=True)
                md_file = md_dir / f"best_oasis_{issue_date}_{pdf_path.stem}.md"
                json_file = md_file.with_suffix(".tables.json")
                
                md_content = f"""---
title: "{title}"
issue_date: "{issue_date}"
year: {year}
publisher: "Best Oasis Limited"
source: "hellenic_demolition"
category: "demolition"
report_week: {week}
source_file: "corpus/02-hellenic/demolition/pdfs/{pdf_path.name}"
tables_count: 2
---

# {title}

## Best Oasis Indicative Demolition Prices ($/LDT)

| Location | Market Status | Container ($/LDT) | Tanker ($/LDT) | Bulker ($/LDT) | W-o-W Change |
|:---|:---|:---|:---|:---|:---|
"""
                for r in p_recs:
                    md_content += f"| {r['location']} | {r['market_status']} | ${r['container_usd_ldt']} | ${r['tanker_usd_ldt']} | ${r['bulker_usd_ldt']} | {r['wow_change_pct']} |\n"
                
                md_content += "\n## Reported Demolition Deals\n\n| Vessel Name | Type | LDT | Terms | Location | Price ($/LDT) |\n|:---|:---|:---|:---|:---|:---|\n"
                for d in d_recs:
                    md_content += f"| {d['vessel_name']} | {d['vessel_type']} | {d['ldt']} | {d['sale_terms']} | {d['delivery_location']} | {d['price_usd_per_ldt']} |\n"
                
                md_content += f"\n## Market Overview\n\n{narr}\n"
                md_file.write_text(md_content, encoding="utf-8")
                
                sidecar = {
                    "title": title,
                    "issue_date": issue_date,
                    "year": year,
                    "publisher": "Best Oasis Limited",
                    "tables_count": 2,
                    "tables": [
                        {
                            "title": "Best Oasis Indicative Demolition Prices",
                            "columns": ["location", "market_status", "container_usd_ldt", "tanker_usd_ldt", "bulker_usd_ldt", "wow_change_pct"],
                            "row_count": len(p_recs),
                            "rows": p_recs
                        },
                        {
                            "title": "Reported Demolition Deals",
                            "columns": ["vessel_name", "vessel_type", "ldt", "sale_terms", "delivery_location", "price_usd_per_ldt"],
                            "row_count": len(d_recs),
                            "rows": d_recs
                        }
                    ]
                }
                json_file.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                processed_count += 1
            except Exception as e:
                logger.error(f"Error Best Oasis {pdf_path.name}: {e}")

        # 3. GMS
        elif "gms" in name_l or "gms" in title_l:
            try:
                week, r_recs, p_recs, narr = extract_gms(pdf_path, issue_date)
                gms_series.extend(r_recs)
                gms_port_positions.extend(p_recs)
                
                md_dir = MD_BASE_DIR / "gms" / year
                md_dir.mkdir(parents=True, exist_ok=True)
                md_file = md_dir / f"gms_{issue_date}_{pdf_path.stem}.md"
                json_file = md_file.with_suffix(".tables.json")
                
                md_content = f"""---
title: "{title}"
issue_date: "{issue_date}"
year: {year}
publisher: "GMS Inc."
source: "hellenic_demolition"
category: "demolition"
report_week: {week}
source_file: "corpus/02-hellenic/demolition/pdfs/{pdf_path.name}"
tables_count: 2
---

# {title}

## GMS Market Rankings & Price Indications ($/LDT)

| Rank | Location | Sentiment | Dry Bulk ($/LDT) | Tankers ($/LDT) | Containers ($/LDT) |
|:---|:---|:---|:---|:---|:---|
"""
                for r in r_recs:
                    md_content += f"| {r['rank']} | {r['location']} | {r['sentiment']} | {r['dry_bulk_usd_ldt']} | {r['tankers_usd_ldt']} | {r['containers_usd_ldt']} |\n"
                
                md_content += "\n## Beaching Port Positions\n\n| Port | Vessel Name | LDT | Type | Status |\n|:---|:---|:---|:---|:---|\n"
                for p in p_recs:
                    md_content += f"| {p['port']} | {p['vessel_name']} | {p['ldt']} | {p['vessel_type']} | {p['status']} |\n"
                
                md_content += f"\n## Editorial Commentary\n\n{narr}\n"
                md_file.write_text(md_content, encoding="utf-8")
                
                sidecar = {
                    "title": title,
                    "issue_date": issue_date,
                    "year": year,
                    "publisher": "GMS Inc.",
                    "tables_count": 2,
                    "tables": [
                        {
                            "title": "GMS Market Rankings",
                            "columns": ["rank", "location", "sentiment", "dry_bulk_usd_ldt", "tankers_usd_ldt", "containers_usd_ldt"],
                            "row_count": len(r_recs),
                            "rows": r_recs
                        },
                        {
                            "title": "Beaching Port Positions",
                            "columns": ["port", "vessel_name", "ldt", "vessel_type", "status"],
                            "row_count": len(p_recs),
                            "rows": p_recs
                        }
                    ]
                }
                json_file.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                processed_count += 1
            except Exception as e:
                logger.error(f"Error GMS {pdf_path.name}: {e}")

    # Stack Master CSV Series
    if athenian_series:
        df_ath = pd.DataFrame(athenian_series).sort_values("issue_date")
        ath_csv = SERIES_DIR / "hellenic_athenian_demolition_series.csv"
        df_ath.to_csv(ath_csv, index=False)
        logger.info(f"Saved {len(df_ath)} Athenian records to {ath_csv.name}")

    if best_oasis_series:
        df_bo = pd.DataFrame(best_oasis_series).sort_values("issue_date")
        bo_csv = SERIES_DIR / "hellenic_best_oasis_demolition_series.csv"
        df_bo.to_csv(bo_csv, index=False)
        logger.info(f"Saved {len(df_bo)} Best Oasis prices to {bo_csv.name}")

    if best_oasis_deals:
        df_bo_deals = pd.DataFrame(best_oasis_deals).sort_values("issue_date")
        bo_d_csv = SERIES_DIR / "hellenic_best_oasis_deals_series.csv"
        df_bo_deals.to_csv(bo_d_csv, index=False)
        logger.info(f"Saved {len(df_bo_deals)} Best Oasis deals to {bo_d_csv.name}")

    if gms_series:
        df_gms = pd.DataFrame(gms_series).sort_values("issue_date")
        gms_csv = SERIES_DIR / "hellenic_gms_demolition_series.csv"
        df_gms.to_csv(gms_csv, index=False)
        logger.info(f"Saved {len(df_gms)} GMS rankings to {gms_csv.name}")

    if gms_port_positions:
        df_gms_p = pd.DataFrame(gms_port_positions).sort_values("issue_date")
        gms_p_csv = SERIES_DIR / "hellenic_gms_port_positions_series.csv"
        df_gms_p.to_csv(gms_p_csv, index=False)
        logger.info(f"Saved {len(df_gms_p)} GMS port position records to {gms_p_csv.name}")

    logger.info(f"Successfully processed {processed_count} demolition reports.")

if __name__ == "__main__":
    main()
