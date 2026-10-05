"""Process Banchero Costa 2026 W36, W37, W38 cover-to-cover via LlamaParse,
save markdown and JSON sidecars, and upsert series CSVs.
"""
import glob, json, os, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import datetime as dt
import pandas as pd
from llama_parse import LlamaParse

API_KEY = "llx-p1IAIhBMQdXo21E9Wz2jgW6hoTPJ8Xs2VvxJMd7S7b8aXYUR"
os.environ["LLAMA_CLOUD_API_KEY"] = API_KEY

ROOT = Path(__file__).resolve().parents[3]
LP_DIR = ROOT / "data" / "extracted" / "llamaparse_banchero"
MD_DIR = ROOT / "data" / "extracted" / "md" / "banchero_costa"
MD_2026_DIR = MD_DIR / "2026"
SERIES_DIR = ROOT / "data" / "extracted" / "series"

LP_DIR.mkdir(parents=True, exist_ok=True)
MD_DIR.mkdir(parents=True, exist_ok=True)
MD_2026_DIR.mkdir(parents=True, exist_ok=True)
SERIES_DIR.mkdir(parents=True, exist_ok=True)

TARGET_PDFS = [
    ROOT / "corpus/01-brokers/banchero_costa/2026/banchero_costa_2026_W36_Bancosta-Weekly-2026-36.pdf",
    ROOT / "corpus/01-brokers/banchero_costa/2026/banchero_costa_2026_W37_Bancosta-Weekly-2026-37.pdf",
    ROOT / "corpus/01-brokers/banchero_costa/2026/banchero_costa_2026_W38_Bancosta-Weekly-2026-38.pdf",
]

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

def report_date_from_stem(stem):
    m = re.search(r"((?:19|20)\d\d)[_-]?[Ww](\d{1,2})(?![0-9])", stem)
    if m:
        y, wk = int(m.group(1)), int(m.group(2))
        if 1 <= wk <= 53:
            try:
                d = dt.date.fromisocalendar(y, wk, 1).isoformat()
                return d, wk
            except ValueError:
                pass
    return None, None

def norm_date(val):
    if not val: return None
    s = str(val).strip()
    m = re.match(r"^([A-Za-z]{3,9})[-/ ](\d{2,4})$", s)
    if m:
        mon_str, yr_str = m.group(1).lower()[:3], m.group(2)
        if mon_str in MONTHS:
            mon = MONTHS[mon_str]
            yr = int(yr_str)
            if yr < 100: yr = 2000 + yr if yr < 50 else 1900 + yr
            return f"{yr:04d}-{mon:02d}"
    m = re.match(r"^(\d{1,2})[/-](\d{2,4})$", s)
    if m:
        mon, yr = int(m.group(1)), int(m.group(2))
        if yr < 100: yr = 2000 + yr if yr < 50 else 1900 + yr
        if 1 <= mon <= 12:
            return f"{yr:04d}-{mon:02d}"
    return None

def parse_dwt(val):
    if not val: return None
    s = str(val).strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}\.\d{3}", s):
        return int(s.replace(".", ""))
    if re.fullmatch(r"\d{1,3},\d{3}", s):
        return int(s.replace(",", ""))
    m = re.search(r"(\d+(?:[.,]\d+)?)", s)
    if not m: return None
    num_str = m.group(1).replace(",", "")
    try:
        n = float(num_str)
        if n < 500: return int(n * 1000)
        return int(round(n))
    except Exception:
        return None

def parse_price_usd_m(val):
    if not val: return None, None
    s = str(val).strip()
    if s.lower() in ["undisclosed", "/", "-", "na", "n/a", ""]:
        return None, None
    m = re.search(r"(\d+)[.,](\d+)", s)
    if m:
        f = float(f"{m.group(1)}.{m.group(2)}")
        if 0.1 <= f <= 2500:
            return f, s
    m = re.search(r"(\d+)", s)
    if m:
        f = float(m.group(1))
        if 0.1 <= f <= 2500:
            return f, s
    return None, s

def parse_built(val):
    if not val: return None
    s = str(val).strip()
    m = re.search(r"\b(19\d\d|20\d\d)\b", s)
    if m: return int(m.group(1))
    m = re.search(r"\b(\d{2})\b", s)
    if m:
        y = int(m.group(1))
        return 2000 + y if y < 50 else 1900 + y
    return None

def parse_imo(val):
    if not val: return None
    s = str(val).strip()
    m = re.search(r"\b(\d{7})\b", s)
    if m:
        return m.group(1)
    return None

def normalize_vtype(vtype):
    if not vtype: return "Unknown"
    v = vtype.strip().lower()
    for k, target in [('bulk', 'Bulk'), ('tank', 'Tank'), ('cont', 'Container'),
                      ('lpg', 'LPG'), ('lng', 'LNG'), ('gas', 'Gas'),
                      ('chemical', 'Chemical'), ('roro', 'RoRo'), ('reefer', 'Reefer'),
                      ('pax', 'Passenger'), ('car', 'Car carrier'), ('general', 'General cargo')]:
        if k in v:
            return target
    return vtype.strip().title()

def parse_single_pdf(pdf_path):
    stem = pdf_path.stem
    lp_md_path = LP_DIR / f"{stem}.md"
    if lp_md_path.exists() and len(lp_md_path.read_text(encoding="utf-8")) > 5000:
        print(f"Reading cached LlamaParse output for {stem}...")
        md_text = lp_md_path.read_text(encoding="utf-8")
        (MD_2026_DIR / f"{stem}.md").write_text(md_text, encoding="utf-8")
        return stem, pdf_path, md_text

    print(f"Starting LlamaParse cover-to-cover for {stem}...")
    t0 = time.time()
    parser = LlamaParse(
        api_key=API_KEY,
        result_type="markdown",
        tier="cost_effective",
        version="latest",
        output_tables_as_HTML=True,
        verbose=False
    )
    json_res = parser.get_json_result(str(pdf_path))
    pages = json_res[0].get('pages', []) if json_res else []
    md_text = "\n\n".join(p.get('md', '') for p in pages)
    
    # Save md in LP_DIR and MD_2026_DIR
    (LP_DIR / f"{stem}.md").write_text(md_text, encoding="utf-8")
    (MD_2026_DIR / f"{stem}.md").write_text(md_text, encoding="utf-8")
    
    # Save .items.json
    (LP_DIR / f"{stem}.items.json").write_text(json.dumps(json_res, indent=2), encoding="utf-8")
    
    secs = round(time.time() - t0, 1)
    print(f"DONE: {stem} -> {len(pages)} pages, {len(md_text)} chars in {secs}s")
    return stem, pdf_path, md_text

def extract_tables_from_md(stem, pdf_path, md_text):
    issue_date, report_week = report_date_from_stem(stem)
    rel_source = str(pdf_path.relative_to(ROOT)).replace('\\', '/')
    soup = BeautifulSoup(md_text, "html.parser")
    tables = soup.find_all("table")
    
    sales_recs = []
    nb_recs = []
    demo_recs = []
    
    for table in tables:
        rows = table.find_all("tr")
        if not rows: continue
        headers = [th.get_text().strip().upper() for th in rows[0].find_all(["th", "td"])]
        h_str = " ".join(headers)
        body_text = " ".join(r.get_text().strip().upper() for r in rows[1:])
        
        # 1. Newbuilding table
        if ("CAPESIZE" in body_text and ("KAMSARMAX" in body_text or "SUEZMAX" in body_text) and
            ("USD MLN" in body_text or "USD" in h_str or "UNIT" in h_str or "M-O-M" in h_str or "M-O-M" in body_text)):
            for r in rows[1:]:
                cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
                if len(cells) >= 2:
                    vtype = cells[0].strip(" *#")
                    m_v = re.match(r"^([A-Za-z0-9 /-]+)", vtype)
                    clean_vtype = m_v.group(1).strip() if m_v else vtype
                    if any(clean_vtype.lower().startswith(t.lower()) for t in ['capesize', 'newcastlemax', 'kamsarmax', 'panamax', 'ultramax', 'supramax', 'handysize', 'vlcc', 'suezmax', 'aframax', 'lr2', 'lr1', 'mr']):
                        for c in cells[1:]:
                            if 'usd' in c.lower() or 'mln' in c.lower(): continue
                            m_num = re.search(r"(\d+(?:\.\d+)?)", c.replace(",", ""))
                            if m_num:
                                val = float(m_num.group(1))
                                if 15.0 <= val <= 250.0:
                                    rec = {
                                        'issue_date': issue_date,
                                        'report_week': report_week,
                                        'vessel_type': clean_vtype,
                                        'price_usd_m': val,
                                        'source_file': rel_source
                                    }
                                    nb_recs.append(rec)
                                    break
                                    
        # 2. Demolition table
        if (("PAKISTAN" in body_text or "BANGLADESH" in body_text or "INDIA" in body_text) and
            ("USD/LDT" in body_text or "USD/LDT" in h_str or "USD LDT" in body_text or "W-O-W" in h_str or "W-O-W" in body_text)):
            for r in rows[1:]:
                cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
                if len(cells) >= 2:
                    cat = cells[0].strip(" *#")
                    m_country = None
                    segment = "Dry"
                    if "tank" in cat.lower() or "tnk" in cat.lower():
                        segment = "Tanker"
                    elif "dry" in cat.lower() or "bulk" in cat.lower():
                        segment = "Dry"
                        
                    for loc in ["Pakistan", "India", "Bangladesh", "Turkey"]:
                        if loc.lower() in cat.lower():
                            m_country = loc
                            break
                    if m_country:
                        for c in cells[1:]:
                            if 'usd' in c.lower() or 'ldt' in c.lower(): continue
                            m_num = re.search(r"(\d+(?:\.\d+)?)", c.replace(",", ""))
                            if m_num:
                                val = float(m_num.group(1))
                                if 150.0 <= val <= 1000.0:
                                    rec = {
                                        'issue_date': issue_date,
                                        'report_week': report_week,
                                        'segment': segment,
                                        'country': m_country,
                                        'price_usd_per_ldt': val,
                                        'source_file': rel_source
                                    }
                                    demo_recs.append(rec)
                                    break
                                    
        # 3. Sales table
        is_sales = False
        if any(k in h_str for k in ['VESSEL NAME', 'VESSEL']) and any(k in h_str for k in ['DWT', 'BLT', 'BUYER', 'PRICE']):
            is_sales = True
        elif len(headers) >= 6 and headers[0] in ['TYPE', 'VESSEL', 'CATEGORY'] and any('DWT' in h for h in headers):
            is_sales = True
            
        if is_sales:
            col_map = {}
            for idx, h in enumerate(headers):
                if 'TYPE' in h or 'CATEGORY' in h: col_map.setdefault('vtype', idx)
                elif 'VESSEL' in h or 'NAME' in h: col_map.setdefault('vessel', idx)
                elif 'IMO' in h: col_map.setdefault('imo', idx)
                elif 'DWT' in h: col_map.setdefault('dwt', idx)
                elif 'BLT' in h or 'YEAR' in h or 'BUILT' in h: col_map.setdefault('built', idx)
                elif 'YARD' in h or 'BUILDER' in h: col_map.setdefault('yard', idx)
                elif 'BUYER' in h: col_map.setdefault('buyer', idx)
                elif 'PRICE' in h: col_map.setdefault('price', idx)
                elif 'SS' in h: col_map.setdefault('ss', idx)
                elif 'NOTE' in h or 'COMMENT' in h or 'NOTES' in h: col_map.setdefault('note', idx)
                
            for r in rows[1:]:
                cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
                if len(cells) < 4: continue
                
                vtype = cells[col_map['vtype']] if 'vtype' in col_map and col_map['vtype'] < len(cells) else None
                vessel = cells[col_map['vessel']] if 'vessel' in col_map and col_map['vessel'] < len(cells) else None
                imo_raw = cells[col_map['imo']] if 'imo' in col_map and col_map['imo'] < len(cells) else None
                dwt_raw = cells[col_map['dwt']] if 'dwt' in col_map and col_map['dwt'] < len(cells) else None
                built_raw = cells[col_map['built']] if 'built' in col_map and col_map['built'] < len(cells) else None
                yard = cells[col_map['yard']] if 'yard' in col_map and col_map['yard'] < len(cells) else None
                buyer = cells[col_map['buyer']] if 'buyer' in col_map and col_map['buyer'] < len(cells) else None
                price_raw = cells[col_map['price']] if 'price' in col_map and col_map['price'] < len(cells) else None
                ss_raw = cells[col_map['ss']] if 'ss' in col_map and col_map['ss'] < len(cells) else None
                note_raw = cells[col_map['note']] if 'note' in col_map and col_map['note'] < len(cells) else None
                
                imo = parse_imo(imo_raw)
                dwt = parse_dwt(dwt_raw)
                built = parse_built(built_raw)
                price, price_text = parse_price_usd_m(price_raw)
                ss_due = norm_date(ss_raw)
                
                delivery = None
                dd_due = None
                comments = note_raw
                if note_raw:
                    m_del = re.search(r"(?:dely|delivery)\b[ :]*([A-Za-z0-9/\- ]{2,20})", note_raw, re.I)
                    if m_del: delivery = m_del.group(1).strip()
                    m_dd = re.search(r"\bDD[ :]*\(?(\d{1,2}[/-]\d{2,4})", note_raw, re.I)
                    if m_dd: dd_due = norm_date(m_dd.group(1))
                    
                if price_text and price_text != str(price):
                    comments = f"PRICE: {price_text} | {comments}" if comments else f"PRICE: {price_text}"
                    
                if buyer and any(k in buyer.upper() for k in ['BWTS', 'SCRUBBER', 'EN BLOC', 'AUCTION']):
                    comments = f"{buyer} | {comments}" if comments else buyer
                    buyer = None
                    
                if not vessel or len(vessel.strip()) < 2:
                    continue
                    
                rec = {
                    'issue_date': issue_date,
                    'report_week': report_week,
                    'vessel_type': normalize_vtype(vtype),
                    'vessel': vessel,
                    'imo': imo,
                    'dwt': dwt,
                    'built': built,
                    'yard': yard,
                    'buyer': buyer,
                    'seller': None,
                    'price_usd_m': price,
                    'ss_due': ss_due,
                    'dd_due': dd_due,
                    'delivery': delivery,
                    'comments': comments,
                    'source_file': rel_source
                }
                sales_recs.append(rec)
                
    # Deduplicate NB and Demo
    nb_df = pd.DataFrame(nb_recs).drop_duplicates(subset=['vessel_type']).to_dict(orient='records') if nb_recs else []
    demo_df = pd.DataFrame(demo_recs).drop_duplicates(subset=['segment', 'country']).to_dict(orient='records') if demo_recs else []
    
    # Save tables.json sidecars
    sidecar_data = {
        'source_file': rel_source,
        'stem': stem,
        'issue_date': issue_date,
        'report_week': report_week,
        'tables': {
            'sales': sales_recs,
            'newbuilding': nb_df,
            'demolition': demo_df
        },
        'row_counts': {
            'sales': len(sales_recs),
            'newbuilding': len(nb_df),
            'demolition': len(demo_df)
        }
    }
    (MD_2026_DIR / f"{stem}.tables.json").write_text(json.dumps(sidecar_data, indent=2), encoding="utf-8")
    
    return sales_recs, nb_df, demo_df

def main():
    print(f"Target PDFs: {len(TARGET_PDFS)}")
    all_results = {}
    
    with ThreadPoolExecutor(max_workers=3) as pool:
        future_to_pdf = {pool.submit(parse_single_pdf, p): p for p in TARGET_PDFS}
        for future in as_completed(future_to_pdf):
            p = future_to_pdf[future]
            stem, pdf_path, md_text = future.result()
            all_results[stem] = (pdf_path, md_text)
            
    print("\nExtracting structured tables from parsed markdowns...")
    new_sales = []
    new_nb = []
    new_demo = []
    
    for stem, (pdf_path, md_text) in all_results.items():
        s_recs, nb_recs, demo_recs = extract_tables_from_md(stem, pdf_path, md_text)
        print(f"Extracted for {stem}: {len(s_recs)} sales, {len(nb_recs)} NB, {len(demo_recs)} Demo")
        new_sales.extend(s_recs)
        new_nb.extend(nb_recs)
        new_demo.extend(demo_recs)
        
    print(f"\nTotal new records to upsert: {len(new_sales)} sales, {len(new_nb)} NB, {len(new_demo)} Demo")
    
    # 1. Upsert Sales
    sales_csv = SERIES_DIR / "bancosta_sales_series.csv"
    df_sales = pd.read_csv(sales_csv)
    initial_sales_count = len(df_sales)
    # Remove any existing rows for these 3 weeks to avoid dupes
    new_sources = {r['source_file'] for r in new_sales}
    df_sales = df_sales[~df_sales['source_file'].isin(new_sources)]
    df_new_sales = pd.DataFrame(new_sales)
    df_sales = pd.concat([df_sales, df_new_sales], ignore_index=True)
    def _to_int(val):
        if pd.isna(val) or val is None or str(val).strip() in ("", "nan", "None", "<NA>"):
            return pd.NA
        try:
            return int(round(float(val)))
        except Exception:
            return pd.NA

    for c in ['imo', 'dwt', 'built']:
        df_sales[c] = df_sales[c].apply(_to_int).astype('Int64')
    df_sales.sort_values(by=['issue_date', 'report_week', 'vessel'], inplace=True, na_position='last')
    df_sales.to_csv(sales_csv, index=False)
    print(f"Updated {sales_csv}: {initial_sales_count} -> {len(df_sales)} rows (+{len(df_sales)-initial_sales_count})")
    
    # 2. Upsert Newbuilding
    nb_csv = SERIES_DIR / "bancosta_newbuilding_series.csv"
    df_nb = pd.read_csv(nb_csv)
    initial_nb_count = len(df_nb)
    new_nb_sources = {r['source_file'] for r in new_nb}
    df_nb = df_nb[~df_nb['source_file'].isin(new_nb_sources)]
    df_new_nb = pd.DataFrame(new_nb)
    df_nb = pd.concat([df_nb, df_new_nb], ignore_index=True)
    df_nb.drop_duplicates(subset=['issue_date', 'vessel_type'], inplace=True)
    df_nb.sort_values(by=['issue_date', 'report_week', 'vessel_type'], inplace=True, na_position='last')
    df_nb.to_csv(nb_csv, index=False)
    print(f"Updated {nb_csv}: {initial_nb_count} -> {len(df_nb)} rows (+{len(df_nb)-initial_nb_count})")
    
    # 3. Upsert Demolition
    demo_csv = SERIES_DIR / "bancosta_demolition_series.csv"
    df_demo = pd.read_csv(demo_csv)
    initial_demo_count = len(df_demo)
    new_demo_sources = {r['source_file'] for r in new_demo}
    df_demo = df_demo[~df_demo['source_file'].isin(new_demo_sources)]
    df_new_demo = pd.DataFrame(new_demo)
    df_demo = pd.concat([df_demo, df_new_demo], ignore_index=True)
    df_demo.drop_duplicates(subset=['issue_date', 'segment', 'country'], inplace=True)
    df_demo.sort_values(by=['issue_date', 'report_week', 'segment', 'country'], inplace=True, na_position='last')
    df_demo.to_csv(demo_csv, index=False)
    print(f"Updated {demo_csv}: {initial_demo_count} -> {len(df_demo)} rows (+{len(df_demo)-initial_demo_count})")

if __name__ == "__main__":
    main()
