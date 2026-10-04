"""
Gibson Shipbrokers Weekly HTML Intelligence Harvester & Extractor (2023-2026).

Downloads and processes native interactive HTML reports from gibsons.co.uk:
1. Archives raw HTML files under corpus/01-brokers/gibson/html/<year>/<date>_<slug>.html.
2. Extracts narrative commentary structured cleanly by section and sub-heading:
   - Feature Story (Lead editorial)
   - Crude Oil: East/Middle East, West Africa, Mediterranean, US Gulf/Latin America, North Sea
   - Clean Products: East, UK Continent, Med/Mediterranean
   - Dirty Products: Handy, MR, Panamax
3. Extracts tabular market assessments:
   - Clean & Dirty Tanker Spot Market Developments (WS and $/day TCE)
   - Bunker Prices ($/tonne)
4. Extracts embedded Chart.js (wpDataCharts) numerical time series vectors:
   - Feature Topic / Hi5 / Orderbook series
   - Crude Tanker Spot Rates (Mid East/China 270kt, WA/UKC 130kt, USG/UKC 70kt)
   - Clean Tanker Spot Rates (USG/Brazil 38kt, Spore/Aus 35kt, Mid East/Japan 75kt, Mid East/Japan 55kt)
   - Dirty Product Tanker Spot Rates (UKC/UKC 30kt, Med/Med 30kt)
5. Emits:
   - data/extracted/md/gibson/<year>/<date>_<slug>.md
   - data/extracted/md/gibson/<year>/<date>_<slug>.tables.json
   - data/extracted/md/gibson/<year>/<date>_<slug>.charts.json
   - Appends to data/extracted/series/gibson_tanker_spot_series.csv
   - Appends to data/extracted/series/gibson_bunker_prices_series.csv
   - Refreshes data/extracted/series/gibson_master_tanker_series.xlsx
"""

import os
import re
import json
import gzip
import subprocess
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CORPUS_HTML_DIR = REPO_ROOT / "corpus" / "01-brokers" / "gibson" / "html"
OUTPUT_MD_DIR = REPO_ROOT / "data" / "extracted" / "md" / "gibson"
SERIES_DIR = REPO_ROOT / "data" / "extracted" / "series"
CATALOG_PATH = REPO_ROOT / "data" / "clarksons" / "gibson_all_reports_catalog.json"

SPOT_CSV_PATH = SERIES_DIR / "gibson_tanker_spot_series.csv"
BUNKER_CSV_PATH = SERIES_DIR / "gibson_bunker_prices_series.csv"
EXCEL_PATH = SERIES_DIR / "gibson_master_tanker_series.xlsx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '--')
    text = text.replace('\xa0', ' ').replace('\ufffd', "'")
    text = re.sub(r'[\x80-\x9f]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def http_fetch_html(url: str, target_file: Path) -> str:
    if target_file.exists() and target_file.stat().st_size > 2000:
        return target_file.read_text(encoding="utf-8", errors="ignore")
    try:
        res = subprocess.run(
            ["curl.exe", "-s", "-L", "--compressed", "-A", HEADERS["User-Agent"], url],
            capture_output=True,
            timeout=25
        )
        raw = res.stdout
        if raw.startswith(b"\x1f\x8b"):
            html = gzip.decompress(raw).decode("utf-8", errors="ignore")
        else:
            html = raw.decode("utf-8", errors="ignore")
            
        if len(html) > 2000:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(html, encoding="utf-8")
            return html
    except Exception as e:
        print(f"Fetch failed for {url}: {e}")
    return ""

def parse_html_report(html: str, iso_date: str, slug: str, url: str):
    soup = BeautifulSoup(html, "html.parser")
    year = iso_date[:4]
    
    # 1. Title
    title_tag = soup.find("h1") or soup.find("title")
    title = clean_text(title_tag.get_text()) if title_tag else slug.replace('-', ' ').title()
    title = re.sub(r'\s*-\s*Gibson.*$', '', title, flags=re.IGNORECASE).strip()
    
    # 2. Week Number
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        report_week = dt.isocalendar()[1]
    except Exception:
        report_week = 1
        
    main_container = soup.find("main") or soup.find("article") or soup
    
    # 3. Structure narrative content
    editorial_paragraphs = []
    sections = {
        'Crude Oil': {},
        'Clean Products': {},
        'Dirty Products': {}
    }
    
    current_major = None
    current_sub = None
    
    # Standard sub-heading aliases
    sub_alias = {
        'east': 'East',
        'middle east': 'Middle East',
        'west africa': 'West Africa',
        'mediterranean': 'Mediterranean',
        'med': 'Mediterranean',
        'us gulf/latin america': 'US Gulf/Latin America',
        'north sea': 'North Sea',
        'uk continent': 'UK Continent',
        'handy': 'Handy',
        'mr': 'MR',
        'panamax': 'Panamax'
    }
    
    elements = main_container.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'table'])
    
    for el in elements:
        t = clean_text(el.get_text())
        if not t:
            continue
            
        if el.name in ['h1', 'h2']:
            t_lower = t.lower()
            if 'crude oil' in t_lower:
                current_major = 'Crude Oil'
                current_sub = None
            elif 'clean products' in t_lower:
                current_major = 'Clean Products'
                current_sub = None
            elif 'dirty products' in t_lower:
                current_major = 'Dirty Products'
                current_sub = None
            elif 'rates & bunkers' in t_lower or 'rates and bunkers' in t_lower:
                current_major = 'Rates & Bunkers'
                current_sub = None
            elif current_major is None and t_lower not in ['table of contents', 'contents', 'menu']:
                # Lead title or chart header
                pass
            continue
            
        elif el.name in ['h3', 'h4']:
            t_lower = t.lower()
            if t_lower in sub_alias and current_major in sections:
                current_sub = sub_alias[t_lower]
                sections[current_major].setdefault(current_sub, [])
            elif 'print the report' in t_lower or 'get your weekly update' in t_lower or 'our locations' in t_lower:
                current_major = None
                current_sub = None
            continue
            
        elif el.name == 'p':
            if not t or len(t) < 25 or 'wpDataCharts' in t or t.startswith('Note:') or 'Print the report' in t:
                continue
            if current_major is None:
                editorial_paragraphs.append(t)
            elif current_major in sections and current_sub:
                sections[current_major][current_sub].append(t)
                
    # 4. Extract Structured Tables
    tables = main_container.find_all('table')
    spot_rows = []
    bunker_rows = []
    
    for tab in tables:
        rows = tab.find_all('tr')
        if not rows:
            continue
        hdr = [clean_text(c.get_text()) for c in rows[0].find_all(['th', 'td'])]
        
        # Determine FFA column
        ffa_period = "FFA"
        for h in hdr:
            m_q = re.search(r'\b(Q[1-4])\b', h)
            if m_q:
                ffa_period = m_q.group(1)
                break
                
        is_spot_table = any('TD3C' in clean_text(r.get_text()) or 'Suezmax' in clean_text(r.get_text()) for r in rows)
        is_bunker_table = any('VLSFO' in clean_text(r.get_text()) or 'LSMGO' in clean_text(r.get_text()) for r in rows)
        
        if is_spot_table:
            for r in rows[1:]:
                cells = [clean_text(c.get_text()) for c in r.find_all(['th', 'td'])]
                if not cells or len(cells) < 4:
                    continue
                row_label = cells[0]
                chg = cells[1] if len(cells) > 1 else ""
                curr = cells[2] if len(cells) > 2 else ""
                prev = cells[3] if len(cells) > 3 else ""
                mth = cells[4] if len(cells) > 4 else ""
                ffa = cells[5] if len(cells) > 5 else ""
                
                # Determine Route Code, Category, Market Type, Vessel Class, Description
                category = "Dirty Tanker Spot"
                market_type = "Spot Worldscale"
                r_code = ""
                vessel_class = ""
                route_desc = ""
                
                m_code = re.match(r'^(TD\d+[A-Za-z]?|TC\d+[A-Za-z]?)', row_label)
                if m_code:
                    r_code = m_code.group(1)
                else:
                    if 'VLCC' in row_label: r_code = 'TD3C'
                    elif 'Suezmax' in row_label: r_code = 'TD20'
                    elif 'Aframax' in row_label: r_code = 'TD25'
                    elif 'LR2' in row_label: r_code = 'TC1'
                    elif 'MR' in row_label and 'west' in row_label.lower(): r_code = 'TC2'
                    elif 'LR1' in row_label: r_code = 'TC5'
                    elif 'MR' in row_label and 'east' in row_label.lower(): r_code = 'TC7'
                    
                if r_code.startswith('TC'):
                    category = "Clean Tanker Spot"
                else:
                    category = "Dirty Tanker Spot"
                    
                if 'tce' in row_label.lower() or '$/day' in row_label.lower():
                    market_type = "$/day TCE"
                else:
                    market_type = "Spot Worldscale"
                    
                if 'VLCC' in row_label: vessel_class = 'VLCC'
                elif 'Suezmax' in row_label: vessel_class = 'Suezmax'
                elif 'Aframax' in row_label: vessel_class = 'Aframax'
                elif 'LR2' in row_label: vessel_class = 'LR2'
                elif 'LR1' in row_label: vessel_class = 'LR1'
                elif 'MR' in row_label: vessel_class = 'MR'
                
                route_desc = re.sub(r'^(TD\d+[A-Za-z]?|TC\d+[A-Za-z]?)\s*', '', row_label)
                route_desc = re.sub(r'\s*(WS|TCE\s*\$/day|\$/day)\s*$', '', route_desc, flags=re.IGNORECASE).strip()
                
                def parse_val(v):
                    if not v: return None
                    c = v.replace(',', '').replace('+', '').strip()
                    try: return float(c)
                    except ValueError: return None
                    
                spot_rows.append({
                    'issue_date': iso_date,
                    'report_week': report_week,
                    'category': category,
                    'market_type': market_type,
                    'route_code': r_code or row_label[:10],
                    'vessel_class': vessel_class,
                    'route_description': route_desc,
                    'change_wow': parse_val(chg),
                    'rate_current': parse_val(curr),
                    'rate_prev': parse_val(prev),
                    'rate_last_month': parse_val(mth),
                    'ffa_value': parse_val(ffa),
                    'ffa_period': ffa_period if parse_val(ffa) is not None else "",
                    'source_file': f"corpus/01-brokers/gibson/html/{year}/{iso_date}_{slug}.html"
                })
                
        elif is_bunker_table:
            for r in rows[1:]:
                cells = [clean_text(c.get_text()) for c in r.find_all(['th', 'td'])]
                if not cells or len(cells) < 4:
                    continue
                port_grade = cells[0]
                chg = cells[1] if len(cells) > 1 else ""
                curr = cells[2] if len(cells) > 2 else ""
                prev = cells[3] if len(cells) > 3 else ""
                mth = cells[4] if len(cells) > 4 else ""
                
                port = "Rotterdam"
                grade = "VLSFO"
                if 'Fujairah' in port_grade: port = 'Fujairah'
                elif 'Singapore' in port_grade: port = 'Singapore'
                elif 'Rotterdam' in port_grade: port = 'Rotterdam'
                
                if 'LSMGO' in port_grade or 'MGO' in port_grade: grade = 'LSMGO'
                elif 'VLSFO' in port_grade: grade = 'VLSFO'
                elif 'HSFO' in port_grade: grade = 'HSFO'
                
                def parse_val(v):
                    if not v: return None
                    c = v.replace(',', '').replace('+', '').strip()
                    try: return float(c)
                    except ValueError: return None
                    
                bunker_rows.append({
                    'issue_date': iso_date,
                    'report_week': report_week,
                    'port': port,
                    'grade': grade,
                    'change_wow': parse_val(chg),
                    'price_current': parse_val(curr),
                    'price_prev': parse_val(prev),
                    'price_last_month': parse_val(mth),
                    'source_file': f"corpus/01-brokers/gibson/html/{year}/{iso_date}_{slug}.html"
                })

    # 5. Extract wpDataCharts
    chart_matches = re.finditer(r'wpDataCharts\[(\d+)\]\s*=\s*\{\s*render_data:\s*(\{.+?\})\s*,\s*(?:engine|container|chart_id)', html, re.DOTALL)
    charts_extracted = []
    for cm in chart_matches:
        cid = cm.group(1)
        try:
            cdata = json.loads(cm.group(2))
            opts = cdata.get('options', {})
            d = opts.get('data', {})
            lbls = d.get('labels', [])
            dsets = d.get('datasets', [])
            series_list = []
            for ds in dsets:
                series_list.append({
                    'name': ds.get('label'),
                    'points_count': len(ds.get('data', [])),
                    'values': ds.get('data', [])
                })
            charts_extracted.append({
                'chart_id': cid,
                'dates_count': len(lbls),
                'dates': lbls,
                'series': series_list
            })
        except Exception:
            pass
            
    # Format Prose Markdown
    md_lines = [
        "---",
        f'title: "{title}"',
        'subtitle: "Weekly Tanker Market Report"',
        f'issue_date: "{iso_date}"',
        f'year: {int(year)}',
        f'report_week: {report_week}',
        'broker: "gibson"',
        'category: "tankers"',
        'format: "html"',
        f'source_url: "{url}"',
        f'source_file: "corpus/01-brokers/gibson/html/{year}/{iso_date}_{slug}.html"',
        f'tables_count: {len(spot_rows) + len(bunker_rows)}',
        f'charts_count: {len(charts_extracted)}',
        "---",
        "",
        f"# {title}",
        f"**Weekly Tanker Market Report | Week {report_week} ({iso_date})**",
        "",
        "## Feature Story",
        ""
    ]
    
    for p in editorial_paragraphs:
        md_lines.append(p)
        md_lines.append("")
        
    for maj in ['Crude Oil', 'Clean Products', 'Dirty Products']:
        if maj in sections and sections[maj]:
            md_lines.append(f"## {maj}")
            md_lines.append("")
            for sub, paras in sections[maj].items():
                md_lines.append(f"### {sub}")
                md_lines.append("")
                for p in paras:
                    md_lines.append(p)
                    md_lines.append("")
                    
    md_lines.append("## Rates & Bunkers")
    md_lines.append("")
    
    d_ws = [r for r in spot_rows if r['market_type'] == 'Spot Worldscale']
    if d_ws:
        md_lines.append("### Clean & Dirty Tanker Spot Market Developments - Spot Worldscale")
        md_lines.append("")
        md_lines.append("| Route | Category | Vessel | Description | WoW Change | Current | Previous | Last Month | FFA |")
        md_lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in d_ws:
            md_lines.append(f"| {r['route_code']} | {r['category']} | {r['vessel_class']} | {r['route_description']} | {r['change_wow'] or '-'} | {r['rate_current'] or '-'} | {r['rate_prev'] or '-'} | {r['rate_last_month'] or '-'} | {r['ffa_value'] or '-'} |")
        md_lines.append("")
        
    d_tce = [r for r in spot_rows if r['market_type'] == '$/day TCE']
    if d_tce:
        md_lines.append("### Clean & Dirty Tanker Spot Market Developments - $/day TCE")
        md_lines.append("")
        md_lines.append("| Route | Category | Vessel | Description | WoW Change ($) | Current ($/day) | Previous ($/day) | Last Month ($/day) | FFA ($/day) |")
        md_lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in d_tce:
            md_lines.append(f"| {r['route_code']} | {r['category']} | {r['vessel_class']} | {r['route_description']} | {r['change_wow'] or '-'} | {r['rate_current'] or '-'} | {r['rate_prev'] or '-'} | {r['rate_last_month'] or '-'} | {r['ffa_value'] or '-'} |")
        md_lines.append("")
        
    if bunker_rows:
        md_lines.append("### Bunker Prices ($/tonne)")
        md_lines.append("")
        md_lines.append("| Port | Grade | WoW Change ($) | Current ($/t) | Previous ($/t) | Last Month ($/t) |")
        md_lines.append("|---|---|---|---|---|---|")
        for r in bunker_rows:
            md_lines.append(f"| {r['port']} | {r['grade']} | {r['change_wow'] or '-'} | {r['price_current'] or '-'} | {r['price_prev'] or '-'} | {r['price_last_month'] or '-'} |")
        md_lines.append("")
        
    md_content = "\n".join(md_lines)
    
    tables_sidecar = {
        'issue_date': iso_date,
        'report_week': report_week,
        'title': title,
        'source_url': url,
        'spot_rates': spot_rows,
        'bunker_prices': bunker_rows
    }
    
    charts_sidecar = {
        'issue_date': iso_date,
        'report_week': report_week,
        'title': title,
        'charts': charts_extracted
    }
    
    return md_content, tables_sidecar, charts_sidecar, spot_rows, bunker_rows

def run_gibson_html_pipeline(limit=None):
    print("=" * 80)
    print("GIBSON SHIPBROKERS HTML HARVESTER & EXTRACTION PIPELINE")
    print("=" * 80)
    
    with open(CATALOG_PATH, encoding="utf-8") as f:
        cat = json.load(f)
        
    reports = cat.get("online_reports", [])
    print(f"Total online reports in catalog: {len(reports)}")
    if limit:
        reports = reports[:limit]
        print(f"Processing limited batch of {limit} reports...")
        
    all_new_spot = []
    all_new_bunker = []
    processed = 0
    
    for r in reports:
        raw_date = r.get("date", "")
        iso_date = raw_date[:10] if len(raw_date) >= 10 else "2024-01-01"
        year = iso_date[:4]
        slug = r.get("slug", "")
        link = r.get("link", "")
        
        target_html = CORPUS_HTML_DIR / year / f"{iso_date}_{slug}.html"
        html = http_fetch_html(link, target_html)
        if not html:
            continue
            
        md_content, tables_sidecar, charts_sidecar, spot_rows, bunker_rows = parse_html_report(html, iso_date, slug, link)
        
        out_year_dir = OUTPUT_MD_DIR / year
        out_year_dir.mkdir(parents=True, exist_ok=True)
        
        stem = f"gibson_{iso_date}_{slug}"
        md_file = out_year_dir / f"{stem}.md"
        tables_file = out_year_dir / f"{stem}.tables.json"
        charts_file = out_year_dir / f"{stem}.charts.json"
        
        md_file.write_text(md_content, encoding="utf-8")
        tables_file.write_text(json.dumps(tables_sidecar, indent=2), encoding="utf-8")
        charts_file.write_text(json.dumps(charts_sidecar, indent=2), encoding="utf-8")
        
        all_new_spot.extend(spot_rows)
        all_new_bunker.extend(bunker_rows)
        processed += 1
        if processed % 20 == 0 or processed == len(reports):
            print(f"Processed {processed}/{len(reports)} HTML reports...")
            
    print(f"\nHarvested and processed {processed} Gibson HTML reports.")
    print(f"Extracted {len(all_new_spot)} new spot rate records, {len(all_new_bunker)} new bunker records.")
    
    # Append & deduplicate series CSVs
    if all_new_spot and SPOT_CSV_PATH.exists():
        df_old = pd.read_csv(SPOT_CSV_PATH)
        df_new = pd.DataFrame(all_new_spot)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
        df_all = df_all.drop_duplicates(subset=['issue_date', 'category', 'market_type', 'route_code'])
        df_all = df_all.sort_values(by=['issue_date', 'category', 'market_type', 'route_code'])
        df_all.to_csv(SPOT_CSV_PATH, index=False, encoding="utf-8")
        print(f"Updated: {SPOT_CSV_PATH} (Now {len(df_all)} total rows)")
        
    if all_new_bunker and BUNKER_CSV_PATH.exists():
        df_old_b = pd.read_csv(BUNKER_CSV_PATH)
        df_new_b = pd.DataFrame(all_new_bunker)
        df_all_b = pd.concat([df_old_b, df_new_b], ignore_index=True)
        df_all_b = df_all_b.drop_duplicates(subset=['issue_date', 'port', 'grade'])
        df_all_b = df_all_b.sort_values(by=['issue_date', 'port', 'grade'])
        df_all_b.to_csv(BUNKER_CSV_PATH, index=False, encoding="utf-8")
        print(f"Updated: {BUNKER_CSV_PATH} (Now {len(df_all_b)} total rows)")
        
    # Re-generate Master Excel Workbook
    if SPOT_CSV_PATH.exists() and BUNKER_CSV_PATH.exists():
        df_s = pd.read_csv(SPOT_CSV_PATH)
        df_b = pd.read_csv(BUNKER_CSV_PATH)
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
            df_s[df_s["category"] == "Dirty Tanker Spot"].to_excel(writer, sheet_name="Dirty Spot WS & TCE", index=False)
            df_s[df_s["category"] == "Clean Tanker Spot"].to_excel(writer, sheet_name="Clean Spot WS & TCE", index=False)
            df_b.to_excel(writer, sheet_name="Bunker Prices", index=False)
            pivot_rates = df_s.pivot_table(
                index=["issue_date", "report_week"],
                columns=["market_type", "route_code"],
                values="rate_current"
            ).reset_index()
            pivot_rates.columns = [f"{col[0]}_{col[1]}" if col[1] else col[0] for col in pivot_rates.columns]
            pivot_rates.to_excel(writer, sheet_name="Continuous Rate Matrix", index=False)
        print(f"Regenerated Master Multi-Tab Excel: {EXCEL_PATH}")

if __name__ == "__main__":
    run_gibson_html_pipeline()
