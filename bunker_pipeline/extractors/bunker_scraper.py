#!/usr/bin/env python3
"""
HTML Matrix Bunker Scraper
Extracts daily tabular price matrices, sulfur grades, delivery terms, daily changes,
highs, lows, and spreads from public bunker port pages.
Captures rolling 10-day sliding window observations.
"""

import re
import logging
from bs4 import BeautifulSoup
from bunker_pipeline.utils.http_client import CLIENT
from bunker_pipeline.utils.normalizer import normalize_grade, normalize_date_str, validate_price

logger = logging.getLogger("BunkerScraper")

# Common port page mappings
POPULAR_PORT_URLS = {
    "SG SIN": "https://shipandbunker.com/prices/apac/sea/sg-sin-singapore",
    "NL RTM": "https://shipandbunker.com/prices/emea/nwe/nl-rtm-rotterdam",
    "US HOU": "https://shipandbunker.com/prices/am/usgac/us-hou-houston",
    "AE FJR": "https://shipandbunker.com/prices/emea/me/ae-fjr-fujairah",
    "US LAX": "https://shipandbunker.com/prices/am/nampac/us-lax-la-long-beach",
    "CN HOK": "https://shipandbunker.com/prices/apac/ea/cn-hok-hong-kong",
    "US NYC": "https://shipandbunker.com/prices/am/namatl/us-nyc-new-york",
    "BR SSZ": "https://shipandbunker.com/prices/am/samatl/br-ssz-santos",
    "GI GIB": "https://shipandbunker.com/prices/emea/med/gi-gib-gibraltar",
    "PA BLB": "https://shipandbunker.com/prices/am/usgac/pa-blb-balboa-panama",
    "PA CTB": "https://shipandbunker.com/prices/am/usgac/pa-ctb-cristobal-panama",
    "KR PUS": "https://shipandbunker.com/prices/apac/ea/kr-pus-busan",
    "CN ZOS": "https://shipandbunker.com/prices/apac/ea/cn-zos-zhoushan",
    "JP TYO": "https://shipandbunker.com/prices/apac/ea/jp-tyo-tokyo",
    "ZA DUR": "https://shipandbunker.com/prices/emea/afr/za-dur-durban",
    "GR PIR": "https://shipandbunker.com/prices/emea/med/gr-pir-piraeus",
}

def parse_price_table(table_elem, port_code: str, port_name: str, grade_code: str) -> list:
    """Parses a single HTML price table for a given fuel grade."""
    records = []
    rows = table_elem.find_all("tr")
    if not rows or len(rows) < 2:
        return records
        
    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
            
        date_raw = cells[0]
        price_raw = cells[1].replace("$", "").replace(",", "")
        
        try:
            price_val = float(price_raw)
        except ValueError:
            continue
            
        if not validate_price(price_val):
            continue
            
        obs_date = normalize_date_str(date_raw)
        
        change_val = None
        high_val = None
        low_val = None
        spread_val = None
        
        if len(cells) >= 3:
            try:
                change_val = float(cells[2].replace("+", "").replace(",", ""))
            except ValueError:
                pass
        if len(cells) >= 4:
            try:
                high_val = float(cells[3].replace(",", ""))
            except ValueError:
                pass
        if len(cells) >= 5:
            try:
                low_val = float(cells[4].replace(",", ""))
            except ValueError:
                pass
        if len(cells) >= 6:
            try:
                spread_val = float(cells[5].replace(",", ""))
            except ValueError:
                pass
                
        records.append({
            "observation_date": obs_date,
            "port_code": port_code,
            "port_name": port_name,
            "grade": normalize_grade(grade_code),
            "delivery_term": "Prompt",
            "price_usd": price_val,
            "change_usd": change_val,
            "high_usd": high_val,
            "low_usd": low_val,
            "spread_usd": spread_val,
            "unit": "USD/MT",
            "source": "ShipAndBunker_HTML"
        })
        
    return records

def scrape_port_page(url: str, port_code: str, port_name: str) -> list:
    """Scrapes all grade tables from a specific port's page."""
    try:
        resp = CLIENT.get(url)
        if resp.status_code != 200:
            logger.error(f"Failed to scrape {url}: HTTP {resp.status_code}")
            return []
            
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table", class_=re.compile(r'price-table'))
        
        all_records = []
        for t in tables:
            cls_list = t.get("class", [])
            caption = t.get("caption", "")
            grade_candidate = None
            
            for c in cls_list:
                if c in ["VLSFO", "IFO380", "MGO", "LSMGO", "BIO", "SS", "MEOH", "IFO180"]:
                    grade_candidate = c
                    break
                    
            if not grade_candidate and caption:
                for possible in ["VLSFO", "IFO380", "MGO", "LSMGO", "BIO", "SS", "MEOH", "IFO180"]:
                    if possible in caption:
                        grade_candidate = possible
                        break
                        
            if grade_candidate:
                extracted = parse_price_table(t, port_code, port_name, grade_candidate)
                all_records.extend(extracted)
                
        logger.info(f"HTML scraper extracted {len(all_records)} sliding-window observations from {port_name}")
        return all_records
        
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return []

def scrape_all_popular_ports() -> list:
    """Scrapes all configured popular port pages for sliding-window data."""
    results = []
    for code, url in POPULAR_PORT_URLS.items():
        port_name = code.split()[-1]
        records = scrape_port_page(url, code, port_name)
        results.extend(records)
    return results

if __name__ == "__main__":
    records = scrape_port_page(POPULAR_PORT_URLS["SG SIN"], "SG SIN", "Singapore")
    print(f"Scraped {len(records)} records from Singapore HTML page.")
    if records:
        print("Sample record:", records[0])
