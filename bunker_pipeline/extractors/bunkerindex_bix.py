#!/usr/bin/env python3
"""
Bunker Index BIX Macro Benchmark Suites Extractor
Extracts global and regional composite indices across 5 key geographic basins:
- World Composite (BIX World)
- World 3 (Major bunkering hubs composite)
- Americas Composite
- Asia-Pacific Composite (APAC)
- Europe, Middle East & Africa Composite (EMEA)
"""

import logging
from bs4 import BeautifulSoup
import pandas as pd
from bunker_pipeline.utils.http_client import CLIENT
from bunker_pipeline.utils.normalizer import normalize_date_str, validate_price

logger = logging.getLogger("BunkerIndexBIX")

BIX_ENDPOINTS = {
    "BIX_World": "https://www.bunkerindex.com/indices/world.php",
    "BIX_World3": "https://www.bunkerindex.com/indices/world-3.php",
    "BIX_Americas": "https://www.bunkerindex.com/indices/region.php?r=21&n=americas",
    "BIX_APAC": "https://www.bunkerindex.com/indices/region.php?r=7&n=apac",
    "BIX_EMEA": "https://www.bunkerindex.com/indices/region.php?r=11&n=emea",
}

def parse_bix_table(table_elem, index_name: str, grade: str) -> list:
    """Parses daily observations from a BIX HTML table."""
    records = []
    rows = table_elem.find_all("tr")
    if len(rows) < 2:
        return records
        
    for r in rows[1:]:
        cells = [td.get_text(strip=True) for td in r.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
            
        date_raw = cells[0]
        price_raw = cells[1].replace(",", "")
        
        try:
            price_val = float(price_raw)
        except ValueError:
            continue
            
        if not validate_price(price_val):
            continue
            
        obs_date = normalize_date_str(date_raw)
        
        change_val = None
        change_pct = None
        low_val = None
        high_val = None
        
        if len(cells) >= 3:
            try: change_val = float(cells[2].replace("+", "").replace(",", ""))
            except ValueError: pass
        if len(cells) >= 4:
            try: change_pct = float(cells[3].replace("+", "").replace("%", "").replace(",", ""))
            except ValueError: pass
        if len(cells) >= 5:
            try: low_val = float(cells[4].replace(",", ""))
            except ValueError: pass
        if len(cells) >= 6:
            try: high_val = float(cells[5].replace(",", ""))
            except ValueError: pass
            
        records.append({
            "observation_date": obs_date,
            "index_code": index_name,
            "grade": grade,
            "price_usd": price_val,
            "change_usd": change_val,
            "change_pct": change_pct,
            "low_usd": low_val,
            "high_usd": high_val,
            "unit": "USD/MT",
            "source": "BunkerIndex_BIX"
        })
        
    return records

def fetch_bix_suite(index_name: str, url: str) -> pd.DataFrame:
    """Fetches all 3 tables (IFO 380, VLSFO, MGO) for a BIX index."""
    records = []
    try:
        resp = CLIENT.get(url, timeout=12)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch {index_name}: HTTP {resp.status_code}")
            return pd.DataFrame()
            
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")
        
        # In Bunker Index, Table 0 is IFO 380, Table 1 is VLSFO, Table 2 is MGO
        grades = ["IFO380", "VLSFO", "MGO"]
        for i, grade in enumerate(grades):
            if i < len(tables):
                extracted = parse_bix_table(tables[i], index_name, grade)
                records.extend(extracted)
                
        logger.info(f"Retrieved {len(records)} daily records for {index_name}")
    except Exception as e:
        logger.error(f"Error fetching {index_name}: {e}")
        
    return pd.DataFrame(records)

def fetch_all_bix_benchmarks() -> pd.DataFrame:
    """Fetches all 5 regional and global composite BIX benchmarks."""
    frames = []
    for name, url in BIX_ENDPOINTS.items():
        df = fetch_bix_suite(name, url)
        if not df.empty:
            frames.append(df)
            
    if not frames:
        return pd.DataFrame()
        
    return pd.concat(frames, ignore_index=True)

if __name__ == "__main__":
    df = fetch_bix_suite("BIX_World", BIX_ENDPOINTS["BIX_World"])
    print("BIX World Sample:")
    print(df.head(10))
