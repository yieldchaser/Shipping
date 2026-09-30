import glob, json, os, re
from pathlib import Path
from bs4 import BeautifulSoup
import datetime as dt
import pandas as pd

ROOT = Path(".")
MD_DIR = ROOT / "data" / "extracted" / "llamaparse_banchero"
SERIES_DIR = ROOT / "data" / "extracted" / "series"
SIDECAR_DIR = ROOT / "data" / "extracted" / "md" / "banchero_costa"

SERIES_DIR.mkdir(parents=True, exist_ok=True)
SIDECAR_DIR.mkdir(parents=True, exist_ok=True)

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
    m = re.search(r"[Ww]eek[_-]?(\d{1,2})[_-]?((?:19|20)\d\d)", stem)
    if m:
        wk, y = int(m.group(1)), int(m.group(2))
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
    # Check 180.242 -> 180242
    if re.fullmatch(r"\d{1,3}\.\d{3}", s):
        return int(s.replace(".", ""))
    if re.fullmatch(r"\d{1,3},\d{3}", s):
        return int(s.replace(",", ""))
    m = re.search(r"(\d+(?:[.,]\d+)?)", s)
    if not m: return None
    num_str = m.group(1).replace(",", "")
    try:
        n = float(num_str)
        if n < 500: # e.g. 28.2 -> 28200
            return int(n * 1000)
        return int(round(n))
    except Exception:
        return None

def parse_price_usd_m(val):
    if not val: return None, None
    s = str(val).strip()
    if s.lower() in ["undisclosed", "/", "-", "na", "n/a", ""]:
        return None, None
    # match number like 27.5, excess 27.5, low 15, 73,50
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
        imo_str = m.group(1)
        # Check digit validation
        check = sum(int(d) * w for d, w in zip(imo_str[:6], range(7, 1, -1))) % 10
        if check == int(imo_str[6]):
            return imo_str
        return imo_str # return even if check digit fails, but valid format
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

def clean_num(val):
    if not val: return None
    s = str(val).strip().replace(',', '').replace('$', '').replace('€', '').replace('', '')
    m = re.search(r'([+-]?\d+(?:\.\d+)?)', s)
    return float(m.group(1)) if m else None

def clean_int(val):
    v = clean_num(val)
    return int(round(v)) if v is not None else None

def extract_prose_sales(text, stem, issue_date, report_week, pdf_path):
    m_sec = re.search(r"#+\s*SECONDHAND SALES(.*?)(?:#+\s*BALTIC|#+\s*DEMOLITION|#+\s*DERIVATIVES|\Z)", text, re.S | re.I)
    if not m_sec:
        return []
    sec_text = m_sec.group(1)
    deals = []
    paras = [p.strip() for p in sec_text.split('\n\n') if p.strip()]
    for p in paras:
        if not any(k in p.lower() for k in ['sold', 'committed', 'changed hands', 'acquired', 'reported', 'disposal']):
            continue
        m_name = re.search(r"\*\*([A-Z0-9\s/.-]{3,35})\*\*", p)
        if not m_name:
            m_name = re.search(r"\b(?:mv|mt)\s+([A-Z0-9\s/.-]{3,30})\b", p)
        if not m_name:
            continue
        vname = m_name.group(1).strip()
        if any(skip in vname.upper() for skip in ['SECONDHAND', 'BALTIC', 'REPORTED', 'ASSESSMENT', 'USD', 'MARKET', 'INDEX']):
            continue
            
        m_dwt = re.search(r"(\d{1,3}(?:[.,]\d{3})*|\d{2,6})\s*(?:dwt|tdw|k\b|teu)", p, re.I)
        dwt_val = parse_dwt(m_dwt.group(1)) if m_dwt else None
        
        m_built = re.search(r"\b(19\d\d|20\d\d)\b", p)
        built_val = int(m_built.group(1)) if m_built else None
        
        m_price = re.search(r"(?:[$]|usd\s*)(\d+(?:\.\d+)?)\s*(?:m|mln|million)?", p, re.I)
        if not m_price:
            m_price = re.search(r"(\d+(?:\.\d+)?)\s*(?:mln|million)?\s*(?:usd|[$])", p, re.I)
        price_val = float(m_price.group(1)) if m_price else None
        
        m_buyer = re.search(r"(?:to|by)\s+([A-Za-z0-9\s.-]+?)(?:\s+for|\s+at|\s+basis|\s+last|\.|\Z)", p, re.I)
        buyer_val = m_buyer.group(1).strip() if m_buyer else None
        if buyer_val and any(k in buyer_val.lower() for k in ['usd', 'mln', 'region', 'around', 'price']):
            buyer_val = None
            
        vtype = "Bulk"
        if any(k in p.lower() for k in ['tanker', 'vlcc', 'suezmax', 'aframax', 'mr', 'lr1', 'lr2']):
            vtype = "Tank"
        elif any(k in p.lower() for k in ['container', 'teu', 'feeder']):
            vtype = "Container"
        elif any(k in p.lower() for k in ['gas', 'lpg', 'lng']):
            vtype = "Gas"
            
        deals.append({
            'issue_date': issue_date,
            'report_week': report_week,
            'vessel_type': vtype,
            'vessel': vname,
            'imo': None,
            'dwt': dwt_val,
            'built': built_val,
            'yard': None,
            'buyer': buyer_val,
            'seller': None,
            'price_usd_m': price_val,
            'ss_due': None,
            'dd_due': None,
            'delivery': None,
            'comments': p[:200],
            'source_file': pdf_path,
            'stem': stem
        })
    return deals


def extract_all():
    pdfs = sorted(glob.glob("corpus/01-brokers/banchero_costa/*/*.pdf"))
    pdf_map = {Path(p).stem: p for p in pdfs}
    
    sales_rows = []
    nb_rows = []
    demo_rows = []
    sh_matrix_rows = []
    fixtures_rows = []
    vhss_rows = []
    fx_rows = []
    
    # Load banchero_deals.parquet for clean historical base
    pq_path = ROOT / "data" / "extracted" / "banchero_deals.parquet"
    existing_deals = []
    if pq_path.exists():
        df_pq = pd.read_parquet(pq_path)
        def clean_val(v):
            return None if pd.isna(v) else v

        for _, r in df_pq.iterrows():
            stem = Path(r['source_file']).stem
            idate = r['report_date'].strftime('%Y-%m-%d') if pd.notna(r['report_date']) else None
            _, wk = report_date_from_stem(stem)
            existing_deals.append({
                'issue_date': idate,
                'report_week': wk,
                'vessel_type': clean_val(r.get('vessel_type')),
                'vessel': clean_val(r.get('vessel')),
                'imo': str(r['imo']) if pd.notna(r.get('imo')) else None,
                'dwt': int(r['dwt']) if pd.notna(r.get('dwt')) else None,
                'built': int(r['built']) if pd.notna(r.get('built')) else None,
                'yard': clean_val(r.get('yard')),
                'buyer': clean_val(r.get('buyer')),
                'seller': clean_val(r.get('seller')),
                'price_usd_m': float(r['price_usd_m']) if pd.notna(r.get('price_usd_m')) else None,
                'ss_due': clean_val(r.get('ss_due')),
                'dd_due': clean_val(r.get('dd_due')),
                'delivery': clean_val(r.get('delivery')),
                'comments': clean_val(r.get('comments')),
                'source_file': str(pdf_map.get(stem, r.get('source_file'))).replace('\\', '/'),
                'stem': stem
            })
            
    print(f"Loaded {len(existing_deals)} existing deals from parquet.")
    
    # Track existing deals by (stem, vessel, built, dwt)
    existing_keys = set()
    for d in existing_deals:
        k = (d['stem'], str(d['vessel']).lower() if d['vessel'] else '', d['built'], d['dwt'])
        existing_keys.add(k)
        sales_rows.append(d)
        
    # Extract from all 243 markdown files across MD_DIR and SIDECAR_DIR
    # md tier is organised by YEAR subdirectory; non-recursive globs find 0 files (verified 2026-09-30).
    all_stems = sorted(list(set(list(pdf_map.keys()) + [p.stem for p in MD_DIR.rglob("*.md")] + [p.stem for p in SIDECAR_DIR.rglob("*.md")])))
    for stem in all_stems:
        p = MD_DIR / f"{stem}.md"
        if not p.exists():
            p = SIDECAR_DIR / f"{stem}.md"
        if not p.exists():
            continue
        pdf_path = str(pdf_map.get(stem, f"corpus/01-brokers/banchero_costa/{stem}.pdf")).replace('\\', '/')
        issue_date, report_week = report_date_from_stem(stem)
        text = p.read_text(encoding="utf-8")
        soup = BeautifulSoup(text, "html.parser")
        tables = soup.find_all("table")
        
        doc_sales = []
        doc_nb = []
        doc_demo = []
        doc_sh_matrix = []
        doc_fixtures = []
        doc_vhss = []
        doc_fx = []
        
        for table in tables:
            rows = table.find_all("tr")
            if not rows: continue
            headers = [th.get_text().strip().upper() for th in rows[0].find_all(["th", "td"])]
            h_str = " ".join(headers)
            body_text = " ".join(r.get_text().strip().upper() for r in rows[1:])
            
            # --- 1. NEWBUILDING TABLE (M-o-M) ---
            if ("CAPESIZE" in body_text and ("KAMSARMAX" in body_text or "SUEZMAX" in body_text) and
                ("M-O-M" in h_str or "M-O-M" in body_text or "NEWBUILDING" in h_str or "NEWBUILDING" in body_text) and
                "W-O-W" not in h_str and "W-O-W" not in body_text):
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
                                            'source_file': pdf_path
                                        }
                                        doc_nb.append(rec)
                                        break
                                        
            # --- 1b. BALTIC SECONDHAND ASSESSMENTS TABLE (W-o-W) ---
            elif ("CAPESIZE" in body_text and ("KAMSARMAX" in body_text or "AFRAMAX" in body_text) and
                  ("W-O-W" in h_str or "W-O-W" in body_text) and
                  not any(k in h_str for k in ['DWT', 'BLT', 'BUYER'])):
                for r in rows[1:]:
                    cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
                    if len(cells) >= 3:
                        vtype = cells[0].strip(" *#")
                        m_v = re.match(r"^([A-Za-z0-9 /-]+)", vtype)
                        clean_vtype = m_v.group(1).strip() if m_v else vtype
                        if any(clean_vtype.lower().startswith(t.lower()) for t in ['capesize', 'newcastlemax', 'kamsarmax', 'panamax', 'ultramax', 'supramax', 'handysize', 'vlcc', 'suezmax', 'aframax', 'lr2', 'lr1', 'mr']):
                            val_curr = clean_num(cells[2]) if len(cells) > 2 else None
                            val_prev = clean_num(cells[3]) if len(cells) > 3 else None
                            pct_wow = cells[4].strip() if len(cells) > 4 else ""
                            pct_yoy = cells[5].strip() if len(cells) > 5 else ""
                            if val_curr and 10.0 <= val_curr <= 250.0:
                                rec = {
                                    'issue_date': issue_date,
                                    'report_week': report_week,
                                    'vessel_type': clean_vtype,
                                    'unit': 'usd mln',
                                    'price_current_usd_m': val_curr,
                                    'price_previous_usd_m': val_prev,
                                    'pct_change_wow': pct_wow,
                                    'pct_change_yoy': pct_yoy,
                                    'source_file': pdf_path
                                }
                                doc_sh_matrix.append(rec)

            # --- 2. DEMOLITION TABLE ---
            elif (("PAKISTAN" in body_text or "BANGLADESH" in body_text or "INDIA" in body_text) and
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
                                            'source_file': pdf_path
                                        }
                                        doc_demo.append(rec)
                                        break

            # --- 4. CONTAINERSHIP FIXTURES TABLE ---
            elif (('TEU' in h_str and any(k in h_str for k in ['RATES', 'RATE', 'ACCOUNT', 'FIXTURE', 'PERIOD'])) or
                  ('VESSEL' in h_str and 'GEAR' in h_str and 'PERIOD' in h_str)):
                col_map = {}
                for idx, h in enumerate(headers):
                    if 'VESSEL' in h or 'NAME' in h: col_map.setdefault('vessel', idx)
                    elif 'BUILT' in h or 'BLT' in h: col_map.setdefault('built', idx)
                    elif 'TEU@14' in h or '14TS' in h: col_map.setdefault('teu_14', idx)
                    elif 'TEU' in h: col_map.setdefault('teu', idx)
                    elif 'GEAR' in h: col_map.setdefault('gear', idx)
                    elif 'ACCOUNT' in h or 'FIXTURE' in h: col_map.setdefault('account', idx)
                    elif 'PERIOD' in h: col_map.setdefault('period', idx)
                    elif 'RATE' in h: col_map.setdefault('rate', idx)

                for r in rows[1:]:
                    cells = [td.get_text().strip() for td in r.find_all(["td", "th"])]
                    if len(cells) < 3: continue
                    v_name = cells[col_map['vessel']] if 'vessel' in col_map and col_map['vessel'] < len(cells) else cells[0]
                    if not v_name or len(v_name) < 2 or v_name.upper() in ['VESSEL', 'NAME', 'TOTAL']:
                        continue
                    b_yr = parse_built(cells[col_map['built']]) if 'built' in col_map and col_map['built'] < len(cells) else parse_built(cells[1])
                    teu_val = clean_int(cells[col_map['teu']]) if 'teu' in col_map and col_map['teu'] < len(cells) else clean_int(cells[2] if len(cells)>2 else "")
                    teu14_val = clean_int(cells[col_map['teu_14']]) if 'teu_14' in col_map and col_map['teu_14'] < len(cells) else (clean_int(cells[3]) if len(cells)>3 else None)
                    gear_val = cells[col_map['gear']] if 'gear' in col_map and col_map['gear'] < len(cells) else (cells[4] if len(cells)>4 else "")
                    acc_val = cells[col_map['account']] if 'account' in col_map and col_map['account'] < len(cells) else (cells[5] if len(cells)>5 else "")
                    per_val = cells[col_map['period']] if 'period' in col_map and col_map['period'] < len(cells) else (cells[6] if len(cells)>6 else "")
                    rate_val = clean_num(cells[col_map['rate']]) if 'rate' in col_map and col_map['rate'] < len(cells) else (clean_num(cells[7]) if len(cells)>7 else None)

                    rec = {
                        'issue_date': issue_date,
                        'report_week': report_week,
                        'vessel_name': v_name,
                        'built': b_yr,
                        'teu': teu_val,
                        'teu_14': teu14_val,
                        'gear': gear_val,
                        'account': acc_val,
                        'period_mos': per_val,
                        'rate_usd_day': rate_val,
                        'source_file': pdf_path
                    }
                    doc_fixtures.append(rec)

            # --- 5. VHSS CONTAINERSHIP TIMECHARTER TABLE ---
            elif ('VHSS' in h_str or 'CONTEX' in body_text) and ('UNIT' in h_str or 'W-O-W' in h_str):
                for r in rows[1:]:
                    cells = [td.get_text().strip() for td in r.find_all(['td', 'th'])]
                    if len(cells) >= 3:
                        seg = cells[0].strip(" *#")
                        unit = cells[1].strip() if len(cells) > 1 else ""
                        val_curr = clean_num(cells[2]) if len(cells) > 2 else None
                        val_prev = clean_num(cells[3]) if len(cells) > 3 else None
                        pct_wow = cells[4].strip() if len(cells) > 4 else ""
                        pct_yoy = cells[5].strip() if len(cells) > 5 else ""
                        if seg and val_curr and seg.upper() not in ['VHSS', 'UNIT', 'INDEX']:
                            rec = {
                                'issue_date': issue_date,
                                'report_week': report_week,
                                'segment': seg,
                                'unit': unit,
                                'value_current': val_curr,
                                'value_previous': val_prev,
                                'pct_change_wow': pct_wow,
                                'pct_change_yoy': pct_yoy,
                                'source_file': pdf_path
                            }
                            doc_vhss.append(rec)

            # --- 6. EXCHANGE RATES TABLE ---
            elif ('CURRENCIES' in h_str or ('USD/EUR' in body_text and 'JPY/USD' in body_text)) and not any(k in h_str for k in ['VESSEL', 'DWT']):
                for r in rows[1:]:
                    cells = [td.get_text().strip() for td in r.find_all(['td', 'th'])]
                    if len(cells) >= 2:
                        pair = cells[0].strip(" *#")
                        if any(pair.upper().startswith(p) for p in ['USD/EUR', 'JPY/USD', 'KRW/USD', 'CNY/USD', 'EUR/USD', 'GBP/USD']):
                            rate_curr = clean_num(cells[1]) if len(cells) > 1 else None
                            rate_prev = clean_num(cells[2]) if len(cells) > 2 else None
                            pct_wow = cells[3].strip() if len(cells) > 3 else ""
                            pct_yoy = cells[4].strip() if len(cells) > 4 else ""
                            rec = {
                                'issue_date': issue_date,
                                'report_week': report_week,
                                'currency_pair': pair,
                                'rate_current': rate_curr,
                                'rate_previous': rate_prev,
                                'pct_change_wow': pct_wow,
                                'pct_change_yoy': pct_yoy,
                                'source_file': pdf_path
                            }
                            doc_fx.append(rec)
                                        
            # --- 3. SALES TABLE ---
            r0 = [c.get_text().strip().upper() for c in rows[0].find_all(['th', 'td'])]
            r1 = [c.get_text().strip().upper() for c in rows[1].find_all(['th', 'td'])] if len(rows) > 1 else []
            
            hdr_row = None
            start_row = 1
            is_sales = False
            
            if any('VESSEL' in h for h in r0) and any(k in ' '.join(r0) for k in ['DWT', 'BLT', 'BUYER', 'PRICE']):
                hdr_row = r0
                start_row = 1
                is_sales = True
            elif any('VESSEL' in h for h in r1) and any(k in ' '.join(r1) for k in ['DWT', 'BLT', 'BUYER', 'PRICE']):
                hdr_row = r1
                start_row = 2
                is_sales = True
            elif 'REPORTED SALES' in ' '.join(r0):
                if any('VESSEL' in h for h in r1):
                    hdr_row = r1
                    start_row = 2
                    is_sales = True
                else:
                    hdr_row = None
                    start_row = 1
                    is_sales = True
            elif len(headers) >= 6 and headers[0] in ['TYPE', 'VESSEL', 'CATEGORY'] and any('DWT' in h for h in headers):
                hdr_row = headers
                start_row = 1
                is_sales = True
            else:
                for test_idx in range(min(3, len(rows))):
                    test_cells = [c.get_text().strip() for c in rows[test_idx].find_all(['th', 'td'])]
                    if len(test_cells) >= 6:
                        first = test_cells[0].lower()
                        if any(first.startswith(t) for t in ['bulk', 'tank', 'cont', 'gas', 'lpg', 'lng', 'chem', 'carrier', 'mpp', 'reefer']):
                            start_row = test_idx
                            is_sales = True
                            has_imo = bool(re.match(r'^\d{7}$', test_cells[2].replace(' ', '')))
                            if has_imo:
                                col_map = {'vtype': 0, 'vessel': 1, 'imo': 2, 'dwt': 3, 'built': 4, 'yard': 5, 'buyer': 6, 'price': 7, 'ss': 8, 'note': 9}
                            else:
                                col_map = {'vtype': 0, 'vessel': 1, 'dwt': 2, 'built': 3, 'yard': 4, 'buyer': 5, 'price': 6, 'ss': 7, 'note': 8}
                            break
                
            if is_sales:
                # Map columns by header
                if hdr_row:
                    col_map = {}
                    for idx, h in enumerate(hdr_row):
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
                    
                for r in rows[start_row:]:
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
                    
                    # Parse fields
                    imo = parse_imo(imo_raw)
                    dwt = parse_dwt(dwt_raw)
                    built = parse_built(built_raw)
                    price, price_text = parse_price_usd_m(price_raw)
                    ss_due = norm_date(ss_raw)
                    
                    # Extract delivery or dd from note
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
                        
                    # Clean buyer if it's a technical note
                    if buyer and any(k in buyer.upper() for k in ['BWTS', 'SCRUBBER', 'EN BLOC', 'AUCTION']):
                        comments = f"{buyer} | {comments}" if comments else buyer
                        buyer = None

                    if not vessel or len(vessel.strip()) < 2:
                        continue

                    v_clean = re.sub(r'[^a-z0-9]', '', vessel.lower())
                    match_ex = None
                    for ex in sales_rows:
                        if ex['stem'] == stem and re.sub(r'[^a-z0-9]', '', str(ex['vessel']).lower()) == v_clean:
                            match_ex = ex
                            break
                            
                    if match_ex:
                        if imo and not match_ex.get('imo'):
                            match_ex['imo'] = imo
                        if built and not match_ex.get('built'):
                            match_ex['built'] = built
                        if dwt and not match_ex.get('dwt'):
                            match_ex['dwt'] = dwt
                        if yard and not match_ex.get('yard'):
                            match_ex['yard'] = yard
                        if buyer and (not match_ex.get('buyer') or match_ex.get('buyer') == 'Undisclosed') and buyer != 'Undisclosed':
                            match_ex['buyer'] = buyer
                        if price is not None and match_ex.get('price_usd_m') is None:
                            match_ex['price_usd_m'] = price
                        if ss_due and not match_ex.get('ss_due'):
                            match_ex['ss_due'] = ss_due
                        if dd_due and not match_ex.get('dd_due'):
                            match_ex['dd_due'] = dd_due
                        if delivery and not match_ex.get('delivery'):
                            match_ex['delivery'] = delivery
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
                        'source_file': pdf_path,
                        'stem': stem
                    }
                    doc_sales.append(rec)
                    sales_rows.append(rec)
                    
        nb_rows.extend(doc_nb)
        demo_rows.extend(doc_demo)
        sh_matrix_rows.extend(doc_sh_matrix)
        fixtures_rows.extend(doc_fixtures)
        vhss_rows.extend(doc_vhss)
        fx_rows.extend(doc_fx)
        
        # Fallback to prose sales if no sales deals extracted for this issue
        if len([r for r in sales_rows if r['stem'] == stem]) == 0:
            p_deals = extract_prose_sales(text, stem, issue_date, report_week, pdf_path)
            for pd_rec in p_deals:
                doc_sales.append(pd_rec)
                sales_rows.append(pd_rec)
        
        # Write sidecar JSON
        sidecar_data = {
            'source_file': pdf_path,
            'stem': stem,
            'issue_date': issue_date,
            'report_week': report_week,
            'tables': {
                'sales': [r for r in sales_rows if r['stem'] == stem],
                'newbuilding': doc_nb,
                'demolition': doc_demo,
                'baltic_secondhand_assessments': doc_sh_matrix,
                'container_fixtures': doc_fixtures,
                'vhss_containership': doc_vhss,
                'exchange_rates': doc_fx
            },
            'row_counts': {
                'sales': len([r for r in sales_rows if r['stem'] == stem]),
                'newbuilding': len(doc_nb),
                'demolition': len(doc_demo),
                'baltic_secondhand_assessments': len(doc_sh_matrix),
                'container_fixtures': len(doc_fixtures),
                'vhss_containership': len(doc_vhss),
                'exchange_rates': len(doc_fx)
            }
        }
        (SIDECAR_DIR / f"{stem}.tables.json").write_text(json.dumps(sidecar_data, indent=2, default=lambda o: None if pd.isna(o) else str(o)), encoding="utf-8")
        
    print(f"Extraction completed!")
    print(f"  Total sales records: {len(sales_rows)}")
    print(f"  Total newbuilding records: {len(nb_rows)}")
    print(f"  Total demolition records: {len(demo_rows)}")
    print(f"  Total Baltic secondhand records: {len(sh_matrix_rows)}")
    print(f"  Total containership fixtures: {len(fixtures_rows)}")
    print(f"  Total VHSS records: {len(vhss_rows)}")
    print(f"  Total FX records: {len(fx_rows)}")
    
    # Save CSV series
    # 1. Sales series
    sales_cols = ['issue_date', 'report_week', 'vessel_type', 'vessel', 'imo', 'dwt',
                  'built', 'yard', 'buyer', 'seller', 'price_usd_m', 'ss_due', 'dd_due',
                  'delivery', 'comments', 'source_file']
    df_sales = pd.DataFrame(sales_rows)[sales_cols]
    df_sales['source_file'] = df_sales['source_file'].astype(str).str.replace('\\', '/')
    for c in ['imo', 'dwt', 'built']:
        df_sales[c] = pd.to_numeric(df_sales[c], errors='coerce').astype('Int64')
    df_sales.sort_values(by=['issue_date', 'report_week', 'vessel'], inplace=True, na_position='last')
    sales_csv = SERIES_DIR / "bancosta_sales_series.csv"
    df_sales.to_csv(sales_csv, index=False)
    print(f"Wrote {len(df_sales)} rows to {sales_csv}")
    
    # 2. Newbuilding series
    nb_cols = ['issue_date', 'report_week', 'vessel_type', 'price_usd_m', 'source_file']
    df_nb = pd.DataFrame(nb_rows)[nb_cols]
    df_nb['source_file'] = df_nb['source_file'].astype(str).str.replace('\\', '/')
    df_nb.drop_duplicates(subset=['issue_date', 'vessel_type'], inplace=True)
    df_nb.sort_values(by=['issue_date', 'report_week', 'vessel_type'], inplace=True, na_position='last')
    nb_csv = SERIES_DIR / "bancosta_newbuilding_series.csv"
    df_nb.to_csv(nb_csv, index=False)
    print(f"Wrote {len(df_nb)} rows to {nb_csv}")
    
    # 3. Demolition series
    demo_cols = ['issue_date', 'report_week', 'segment', 'country', 'price_usd_per_ldt', 'source_file']
    df_demo = pd.DataFrame(demo_rows)[demo_cols]
    df_demo['source_file'] = df_demo['source_file'].astype(str).str.replace('\\', '/')
    df_demo.drop_duplicates(subset=['issue_date', 'segment', 'country'], inplace=True)
    df_demo.sort_values(by=['issue_date', 'report_week', 'segment', 'country'], inplace=True, na_position='last')
    demo_csv = SERIES_DIR / "bancosta_demolition_series.csv"
    df_demo.to_csv(demo_csv, index=False)
    print(f"Wrote {len(df_demo)} rows to {demo_csv}")

    # 4. Baltic Secondhand Matrix series
    sh_cols = ['issue_date', 'report_week', 'vessel_type', 'unit', 'price_current_usd_m', 'price_previous_usd_m', 'pct_change_wow', 'pct_change_yoy', 'source_file']
    df_sh = pd.DataFrame(sh_matrix_rows)[sh_cols]
    df_sh['source_file'] = df_sh['source_file'].astype(str).str.replace('\\', '/')
    df_sh.drop_duplicates(subset=['issue_date', 'vessel_type'], inplace=True)
    df_sh.sort_values(by=['issue_date', 'report_week', 'vessel_type'], inplace=True, na_position='last')
    sh_csv = SERIES_DIR / "bancosta_secondhand_matrix_series.csv"
    df_sh.to_csv(sh_csv, index=False)
    print(f"Wrote {len(df_sh)} rows to {sh_csv}")

    # 5. Containership Fixtures series
    fix_cols = ['issue_date', 'report_week', 'vessel_name', 'built', 'teu', 'teu_14', 'gear', 'account', 'period_mos', 'rate_usd_day', 'source_file']
    df_fix = pd.DataFrame(fixtures_rows)[fix_cols]
    df_fix['source_file'] = df_fix['source_file'].astype(str).str.replace('\\', '/')
    for c in ['built', 'teu', 'teu_14']:
        df_fix[c] = pd.to_numeric(df_fix[c], errors='coerce').astype('Int64')
    df_fix.sort_values(by=['issue_date', 'report_week', 'vessel_name'], inplace=True, na_position='last')
    fix_csv = SERIES_DIR / "bancosta_container_fixtures_series.csv"
    df_fix.to_csv(fix_csv, index=False)
    print(f"Wrote {len(df_fix)} rows to {fix_csv}")

    # 6. VHSS Containership series
    vhss_cols = ['issue_date', 'report_week', 'segment', 'unit', 'value_current', 'value_previous', 'pct_change_wow', 'pct_change_yoy', 'source_file']
    df_vhss = pd.DataFrame(vhss_rows)[vhss_cols]
    df_vhss['source_file'] = df_vhss['source_file'].astype(str).str.replace('\\', '/')
    df_vhss.drop_duplicates(subset=['issue_date', 'segment'], inplace=True)
    df_vhss.sort_values(by=['issue_date', 'report_week', 'segment'], inplace=True, na_position='last')
    vhss_csv = SERIES_DIR / "bancosta_vhss_series.csv"
    df_vhss.to_csv(vhss_csv, index=False)
    print(f"Wrote {len(df_vhss)} rows to {vhss_csv}")

    # 7. FX series
    fx_cols = ['issue_date', 'report_week', 'currency_pair', 'rate_current', 'rate_previous', 'pct_change_wow', 'pct_change_yoy', 'source_file']
    df_fx = pd.DataFrame(fx_rows)[fx_cols]
    df_fx['source_file'] = df_fx['source_file'].astype(str).str.replace('\\', '/')
    df_fx.drop_duplicates(subset=['issue_date', 'currency_pair'], inplace=True)
    df_fx.sort_values(by=['issue_date', 'report_week', 'currency_pair'], inplace=True, na_position='last')
    fx_csv = SERIES_DIR / "bancosta_fx_series.csv"
    df_fx.to_csv(fx_csv, index=False)
    print(f"Wrote {len(df_fx)} rows to {fx_csv}")

if __name__ == "__main__":
    extract_all()
