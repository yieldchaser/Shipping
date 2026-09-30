"""
Star Asia Ferrous Scrap Intelligence Extraction Pipeline.

Extracts weekly ferrous scrap and steel market intelligence from Star Asia reports (2022-2026):
- Explicit $/t pricing for steel scrap, busheling, shredded, HMS 80:20, turning, PNS, billet, rebar.
- Local domestic steel and scrap prices across India, Pakistan, Bangladesh, Turkey.
- Detailed origins, terms (CFR, Ex-Works, Domestic), price types (Offer, Bid, Deal Concluded, Indication),
  and foreign exchange rates.

Outputs:
  - data/extracted/series/star_asia_ferrous_scrap_series.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
PUB = "star_asia"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"
FERROUS_SERIES_CSV = OUT_SERIES / "star_asia_ferrous_scrap_series.csv"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

ORIGIN_RULES = [
    ("Mozambique", "Mozambique"),
    ("Malaysia", "Malaysia"),
    ("Malaysian", "Malaysia"),
    ("Australia", "Australia"),
    ("Australian", "Australia"),
    ("New Zealand", "New Zealand"),
    ("UK/EU", "UK/EU"),
    ("UK", "UK"),
    ("British", "UK"),
    ("EU", "EU"),
    ("European", "EU"),
    ("US", "US"),
    ("USA", "US"),
    ("American", "US"),
    ("UAE", "UAE"),
    ("Bahrain", "Bahrain"),
    ("Israel", "Israel"),
    ("Latin American", "Latin American"),
    ("South American", "South American"),
    ("Southeast Asian", "Southeast Asian"),
    ("Baltic", "Baltic"),
    ("African", "African"),
    ("Middle East", "Middle East"),
    ("Japanese", "Japan"),
    ("Japan", "Japan"),
]

GRADE_RULES = [
    ("HMS 80:20", "HMS 80:20"),
    ("HMS 90:10", "HMS 90:10"),
    ("HMS 1/2", "HMS 1/2"),
    ("HMS (80:20)", "HMS 80:20"),
    ("shredded and busheling", "Shredded and Busheling"),
    ("busheling and shredded", "Shredded and Busheling"),
    ("busheling", "Busheling"),
    ("turning scrap", "Turning"),
    ("turning", "Turning"),
    ("shredded scrap", "Shredded"),
    ("shredded", "Shredded"),
    ("pns scrap", "PNS"),
    ("pns", "PNS"),
    ("tangshan billet", "Billet"),
    ("square billet", "Billet"),
    ("billet", "Billet"),
    ("rebar", "Rebar"),
    ("hms scrap", "HMS"),
    ("hms", "HMS"),
    ("ship plates", "Domestic Scrap"),
    ("domestic ship scrap", "Domestic Scrap"),
    ("local scrap", "Domestic Scrap"),
    ("domestic scrap", "Domestic Scrap"),
    ("melting scrap", "Melting Scrap"),
]

PORT_RULES = [
    ("Chattogram", "Chattogram"),
    ("Chittagong", "Chattogram"),
    ("Qasim", "Qasim"),
    ("Karachi", "Karachi"),
    ("Mundra", "Mundra"),
    ("Chennai", "Chennai"),
    ("Mandi", "Mandi"),
    ("Ludhiana", "Ludhiana"),
    ("Aliaga", "Aliaga"),
    ("Turkey", "Turkey"),
    ("Nhava Sheva", "Nhava Sheva"),
    ("Kandla", "Kandla"),
    ("Mumbai", "Mumbai"),
]


def clean_ord(s: str) -> str:
    return re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s, flags=re.I)


def extract_meta(doc: pymupdf.Document, pdf_path: Path) -> Tuple[int, str]:
    p1 = doc[0].get_text()
    m_wk = re.search(r"WEEK\s*(\d{1,2})", p1, re.I)
    week = int(m_wk.group(1)) if m_wk else None
    if week is None:
        m_fn_wk = re.search(r"week[_\-\s]*(\d{1,2})", pdf_path.name, re.I) or re.search(r"W(\d{1,2})", pdf_path.name, re.I)
        if m_fn_wk:
            week = int(m_fn_wk.group(1))

    dt = None
    for line in p1.splitlines()[:25]:
        cleaned = clean_ord(line)
        m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(202\d)", cleaned)
        if m and m.group(1).lower() in MONTHS:
            mo = MONTHS[m.group(1).lower()]
            da = int(m.group(2))
            yr = int(m.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break
        m2 = re.search(r"(\d{1,2})\s+([A-Za-z]+),?\s+(202\d)", cleaned)
        if m2 and m2.group(2).lower() in MONTHS:
            da = int(m2.group(1))
            mo = MONTHS[m2.group(2).lower()]
            yr = int(m2.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break
        m3 = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](202\d)", cleaned)
        if m3:
            da, mo, yr = int(m3.group(1)), int(m3.group(2)), int(m3.group(3))
            if 1 <= mo <= 12 and 1 <= da <= 31:
                dt = f"{yr:04d}-{mo:02d}-{da:02d}"
                break

    if dt is None:
        m_fn_dt = re.search(r"(\d{2})_(\d{2})_(202\d)", pdf_path.name)
        if m_fn_dt:
            da, mo, yr = int(m_fn_dt.group(1)), int(m_fn_dt.group(2)), int(m_fn_dt.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"

    if dt is None and "2024_W05_ISM" in pdf_path.name:
        dt, week = "2024-02-02", 5
    elif dt is None and "2024_W10_ISM" in pdf_path.name:
        dt, week = "2024-03-08", 10

    return week or 0, dt or "2026-00-00"


def clean_num(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    try:
        return float(s.replace(",", "").strip())
    except Exception:
        return None


def extract_table_fx_rates(doc: pymupdf.Document) -> Dict[str, float]:
    fx_rates = {}
    for pg in doc:
        txt = pg.get_text()
        if "EXCHANGE RATES" in txt.upper():
            for tab in pg.find_tables():
                ext = tab.extract()
                for r in ext:
                    if not r: continue
                    r_str = " ".join(str(c or "") for c in r).upper()
                    val = None
                    for c in r[1:]:
                        v = clean_num(str(c or ""))
                        if v and 1.0 < v < 1000.0:
                            val = v
                            break
                    if val is not None:
                        if "INR" in r_str or "INDIA" in r_str: fx_rates["India"] = val
                        elif "BDT" in r_str or "BANGLADESH" in r_str: fx_rates["Bangladesh"] = val
                        elif "PKR" in r_str or "PAKISTAN" in r_str: fx_rates["Pakistan"] = val
                        elif "TRY" in r_str or "TURKEY" in r_str: fx_rates["Turkey"] = val
    return fx_rates


def extract_ferrous_intel_from_text(
    full_text: str, issue_date: str, report_week: int, pdf_name: str, doc_fx: Dict[str, float]
) -> List[Dict[str, Any]]:
    records = []

    # Find the target section(s)
    # 1. Primary: Sub-Continent and Turkey ferrous scrap markets insights
    # 2. Secondary: Country insight blocks mentioning scrap prices
    sections = []
    
    m_sec = re.search(r"(?:Sub-Continent\s*(?:and|&)\s*Turkey\s*(?:ferrous\s*)?scrap\s*markets?\s*insights?|SUB-CONTINENT\s*&\s*TURKEY\s*SCRAP\s*MARKETS)(.*?)(?:HMS\s*1/2|BUNKER\s*PRICES|COMMODITIES|EXCHANGE\s*RATES|TIDE\s*DATES|\Z)", full_text, flags=re.I | re.S)
    if m_sec:
        sections.append(("dedicated", m_sec.group(1)))
    else:
        # Fallback to general insights text
        m_ins = re.search(r"(?:Market\s*Insights?|Insights?)(.*?)(?:Anchorage\s*&\s*Beaching|BUNKER\s*PRICES|COMMODITIES|\Z)", full_text, flags=re.I | re.S)
        if m_ins:
            sections.append(("insights", m_ins.group(1)))

    for sec_kind, sec_text in sections:
        # Split by country headers
        country_splits = re.split(r"(?:^|\n|\b)(India|Pakistan|Bangladesh|Turkiye|Turkey|Alang|Chattogram|Gadani|Gaddani|Aliaga)(?::|\s+[A-Z]|\s*\n)", sec_text, flags=re.I)
        
        i = 1
        while i < len(country_splits):
            cty_raw = country_splits[i].strip()
            chunk = country_splits[i+1] if i+1 < len(country_splits) else ""
            i += 2

            cu = cty_raw.upper()
            country = "India"
            if "PAKISTAN" in cu or "GADANI" in cu or "GADDANI" in cu: country = "Pakistan"
            elif "BANGLADESH" in cu or "CHATTOGRAM" in cu: country = "Bangladesh"
            elif "TURKEY" in cu or "TURKIYE" in cu or "ALIAGA" in cu: country = "Turkey"
            elif "INDIA" in cu or "ALANG" in cu: country = "India"

            # Check FX rate in prose, fallback to table FX
            fx_val = doc_fx.get(country)
            m_fx = re.search(r"\b(?:INR|BDT|PKR|TRY)\s*(\d+(?:\.\d+)?)\s*(?:/\s*USD|\bto\s+the\s+(?:dollar|USD))", chunk, re.I)
            if m_fx:
                fx_val = float(m_fx.group(1))

            # Process sentence by sentence
            sentences = re.split(r"\.\s+", chunk)
            for sent in sentences:
                sent = sent.strip().replace("\n", " ")
                if not sent: continue

                # A. Domestic scrap price in local currency
                # e.g. BDT 56,000/t (US$456/t) or INR 39,800 to INR 40,500 per ton
                m_dom = re.search(r"(?:holding\s+at|prices?\s+at|around|standing\s+at|between|holding\s+between)\s*(BDT|INR|PKR|Rs\.?)\s*([\d,]+)(?:\s*[-~–—to]+\s*(?:BDT|INR|PKR|Rs\.?)?\s*([\d,]+))?\s*(?:/t|/ton|per\s+ton)?(?:\s*\(\s*(?:US\$|USD|\$)\s*([\d,]+)\s*(?:/t|/ton)?\s*\))?", sent, re.I)
                if m_dom:
                    d_cur = m_dom.group(1).upper().replace("RS.", "INR").replace("RS", "INR")
                    d_low = clean_num(m_dom.group(2))
                    d_high = clean_num(m_dom.group(3)) or d_low
                    d_usd = clean_num(m_dom.group(4))
                    if not d_usd and fx_val and d_low and d_low > 1000:
                        d_usd = round(d_low / fx_val, 2)
                    
                    if d_low and d_low > 1000:
                        records.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "country": country,
                            "grade": "Domestic Scrap",
                            "origin": "",
                            "price_usd_per_t": d_usd if d_usd else "",
                            "price_range_low": d_usd if d_usd else "",
                            "price_range_high": d_usd if d_usd else "",
                            "price_type": "Indication",
                            "terms": "Domestic",
                            "destination_port": "",
                            "domestic_price_local_cur": d_low,
                            "domestic_currency": d_cur,
                            "fx_rate": fx_val if fx_val else "",
                            "source_file": pdf_name,
                        })

                # B. Respectively pattern: e.g. 'offers for HMS and shredded material hovered near US$395~420/t, respectively'
                m_resp = re.search(r"offers?\s+for\s+([A-Za-z0-9/:\s]+)\s+and\s+([A-Za-z0-9/:\s]+)\s+(?:material|scrap|cargo)?\s*hovered\s+near\s*(?:US\$|USD|\$)\s*([\d,]+)\s*[-~–—to]+\s*([\d,]+)\s*(?:/t|/ton)", sent, re.I)
                if m_resp:
                    g1_raw, g2_raw = m_resp.group(1).strip(), m_resp.group(2).strip()
                    p1 = clean_num(m_resp.group(3))
                    p2 = clean_num(m_resp.group(4))
                    g1 = "HMS" if "HMS" in g1_raw.upper() else g1_raw.title()
                    g2 = "Shredded" if "SHREDDED" in g2_raw.upper() else g2_raw.title()
                    
                    orig = ""
                    for op, on in ORIGIN_RULES:
                        if re.search(r"\b" + re.escape(op) + r"\b", sent, re.I):
                            orig = on
                            break
                    port = "Chattogram" if country == "Bangladesh" else ("Turkey" if country == "Turkey" else "")
                    
                    records.append({
                        "issue_date": issue_date, "report_week": report_week, "country": country,
                        "grade": g1, "origin": orig, "price_usd_per_t": p1,
                        "price_range_low": p1, "price_range_high": p1, "price_type": "Offer",
                        "terms": "CFR", "destination_port": port, "domestic_price_local_cur": "",
                        "domestic_currency": "", "fx_rate": fx_val if fx_val else "", "source_file": pdf_name
                    })
                    records.append({
                        "issue_date": issue_date, "report_week": report_week, "country": country,
                        "grade": g2, "origin": orig, "price_usd_per_t": p2,
                        "price_range_low": p2, "price_range_high": p2, "price_type": "Offer",
                        "terms": "CFR", "destination_port": port, "domestic_price_local_cur": "",
                        "domestic_currency": "", "fx_rate": fx_val if fx_val else "", "source_file": pdf_name
                    })
                    continue

                # C. Split sentence into discrete deal/offer/bid clauses
                clause_delims = re.compile(
                    r"(?:,\s*while\s+|\s+while\s+|\s+against\s+|,\s*whereas\s+|\s+whereas\s+|;\s*|\s+and\s+(?=[a-zA-Z\s]*(?:shredded|turning|busheling|hms|scrap|deal|cargo|origin|material|new zealand|australian|bids|offers)))",
                    re.I
                )
                clauses = clause_delims.split(sent)

                last_grade = ""
                last_origin = ""
                last_port = ""

                for clause in clauses:
                    p_matches = list(re.finditer(r"(?:US\$|USD|\$)\s*([\d,]+)(?:\s*(?:[-~–—]|to)\s*(?:US\$|USD|\$)?\s*([\d,]+))?\s*(?:/(?:t|ton|MT)|per\s+(?:ton|MT))?", clause, re.I))
                    if not p_matches:
                        continue

                    for pm in p_matches:
                        # Skip if part of local currency parenthesis already parsed
                        if m_dom and abs(pm.start() - m_dom.start()) < 60:
                            continue

                        p_low = clean_num(pm.group(1))
                        p_high = clean_num(pm.group(2)) if pm.group(2) else p_low
                        # Validate realistic scrap/steel price range: $150 to $950/t
                        if not p_low or not (150 <= p_low <= 950):
                            continue
                        p_mid = round((p_low + p_high) / 2.0, 2)

                        # Detect grade in clause
                        grade = ""
                        for gp, gn in GRADE_RULES:
                            if re.search(r"\b" + re.escape(gp) + r"\b", clause, re.I):
                                grade = gn
                                break
                        if not grade and last_grade:
                            grade = last_grade
                        elif grade:
                            last_grade = grade

                        # Detect origin in clause (stripping currency symbols first so 'US$' != 'US')
                        clean_clause = re.sub(r"(?:US\$|USD|\$)\s*[\d,]+", "", clause)
                        origin = ""
                        for op, on in ORIGIN_RULES:
                            if re.search(r"\b" + re.escape(op) + r"\b", clean_clause, re.I):
                                origin = on
                                break
                        if not origin and last_origin and ("bid" in clause.lower() or "conservative" in clause.lower()):
                            origin = last_origin
                        elif origin:
                            last_origin = origin

                        # Detect port
                        port = ""
                        for pp, pn in PORT_RULES:
                            if re.search(r"\b" + re.escape(pp) + r"\b", clause, re.I):
                                port = pn
                                break
                        if not port and last_port:
                            port = last_port
                        elif port:
                            last_port = port
                        elif not port:
                            if country == "Turkey": port = "Turkey"
                            elif country == "Bangladesh" and "CHATTOGRAM" in chunk.upper(): port = "Chattogram"

                        # Price Type
                        cl_low = clause.lower()
                        p_type = "Indication"
                        if any(w in cl_low for w in ["bid", "bids", "bidding", "buyer target", "targets"]):
                            p_type = "Bid"
                        elif any(w in cl_low for w in ["offer", "offered", "asking", "seller offer"]):
                            p_type = "Offer"
                        elif any(w in cl_low for w in ["sale of", "concluded", "finalised", "sold", "transacted", "deal", "agreement was reached"]):
                            p_type = "Deal Concluded"
                        elif any(w in cl_low for w in ["heard", "indicated", "quoted", "assessed", "hovered", "priced"]):
                            p_type = "Indication"

                        # Terms
                        terms = "CFR"
                        if "fob" in cl_low: terms = "FOB"
                        elif "ex-works" in cl_low or "ex-mill" in cl_low: terms = "Ex-Works"
                        elif "delivered" in cl_low: terms = "Delivered"

                        records.append({
                            "issue_date": issue_date,
                            "report_week": report_week,
                            "country": country,
                            "grade": grade or "Steel Scrap",
                            "origin": origin,
                            "price_usd_per_t": p_mid,
                            "price_range_low": p_low,
                            "price_range_high": p_high,
                            "price_type": p_type,
                            "terms": terms,
                            "destination_port": port,
                            "domestic_price_local_cur": "",
                            "domestic_currency": "",
                            "fx_rate": fx_val if fx_val else "",
                            "source_file": pdf_name,
                        })

    return records


def process_star_asia_ferrous_scrap() -> Dict[str, Any]:
    OUT_SERIES.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    print(f"Extracting ferrous scrap intelligence from {len(pdfs)} Star Asia PDFs...")

    all_records: List[Dict[str, Any]] = []
    reports_with_scrap_intel = 0

    for idx, pdf in enumerate(pdfs, 1):
        if "ISM_" in pdf.name:
            continue

        with pymupdf.open(pdf) as doc:
            report_week, issue_date = extract_meta(doc, pdf)
            doc_fx = extract_table_fx_rates(doc)
            
            # Combine text of all pages
            full_text = "\n".join(pg.get_text() for pg in doc)

            doc_records = extract_ferrous_intel_from_text(full_text, issue_date, report_week, pdf.name, doc_fx)
            if doc_records:
                reports_with_scrap_intel += 1
                all_records.extend(doc_records)

        if idx % 25 == 0 or idx == len(pdfs):
            print(f"Processed {idx:>3}/{len(pdfs)} documents... (extracted {len(all_records)} records so far)")

    # Write Ferrous Scrap Series CSV
    headers = [
        "issue_date", "report_week", "country", "grade", "origin",
        "price_usd_per_t", "price_range_low", "price_range_high",
        "price_type", "terms", "destination_port",
        "domestic_price_local_cur", "domestic_currency", "fx_rate", "source_file"
    ]
    with open(FERROUS_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(all_records)

    summary = {
        "total_documents": len(pdfs),
        "reports_with_scrap_intel": reports_with_scrap_intel,
        "ferrous_scrap_series_rows": len(all_records),
    }

    print("=" * 60)
    print("STAR ASIA FERROUS SCRAP EXTRACTION COMPLETE")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:<30}: {v}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Extract Star Asia ferrous scrap market intelligence.")
    args = parser.parse_args()
    process_star_asia_ferrous_scrap()


if __name__ == "__main__":
    main()
