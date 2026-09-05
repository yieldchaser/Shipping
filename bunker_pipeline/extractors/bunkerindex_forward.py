#!/usr/bin/env python3
"""
Bunker Index 12-Month Forward Curves Extractor
Harvests the forward delivery matrix across 12 rolling forward contract months
for 6 key global bunker hubs: Busan, Fujairah, Hong Kong, Kaohsiung, Rotterdam, Singapore.
"""

import re
import logging
from datetime import date
from bs4 import BeautifulSoup
import pandas as pd
from bunker_pipeline.utils.http_client import CLIENT
from bunker_pipeline.utils.normalizer import validate_price

logger = logging.getLogger("BunkerIndexForward")

TARGET_HUBS = ["Busan", "Fujairah", "Hong Kong", "Kaohsiung", "Rotterdam", "Singapore"]

def get_contract_month_label(month_offset: int, as_of: date = None) -> str:
    """Computes YYYY-MM label for a forward month offset (1 = prompt next month)."""
    base = as_of or date.today()
    target_year = base.year
    target_month = base.month + month_offset
    while target_month > 12:
        target_month -= 12
        target_year += 1
    return f"{target_year:04d}-{target_month:02d}"

def fetch_forward_month(month_offset: int, as_of_date_str: str = None) -> pd.DataFrame:
    """
    Fetches the forward prices table for month M (1 to 12).
    Returns a pandas DataFrame of parsed prices.
    """
    url = f"https://www.bunkerindex.com/center_table_forward_prices_month_{month_offset}_home.php"
    as_of = date.today().strftime("%Y-%m-%d") if not as_of_date_str else as_of_date_str
    contract_month = get_contract_month_label(month_offset)
    
    records = []
    try:
        resp = CLIENT.get(url, timeout=12)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch forward month {month_offset}: HTTP {resp.status_code}")
            return pd.DataFrame()
            
        soup = BeautifulSoup(resp.text, "html.parser")
        for tr in soup.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if not cells or len(cells) < 7:
                continue
                
            cell0 = cells[0]
            matched_hub = None
            for hub in TARGET_HUBS:
                if cell0.startswith(hub) or hub in cell0:
                    matched_hub = hub
                    break
                    
            if not matched_hub:
                continue
                
            # Discard paywalled rows
            if "Subscribe" in cells[2] or "Subscribe" in cells[4] or "Subscribe" in cells[6]:
                continue
                
            try:
                ifo380 = float(cells[2].replace(",", ""))
                vlsfo = float(cells[4].replace(",", ""))
                mgo = float(cells[6].replace(",", ""))
            except (ValueError, IndexError):
                continue
                
            if not (validate_price(ifo380) and validate_price(vlsfo) and validate_price(mgo)):
                continue
                
            records.append({
                "as_of_date": as_of,
                "port": matched_hub,
                "month_offset": month_offset,
                "contract_month": contract_month,
                "ifo380_usd": ifo380,
                "vlsfo_usd": vlsfo,
                "mgo_usd": mgo,
                "source": "BunkerIndex_Forward"
            })
            
    except Exception as e:
        logger.error(f"Error fetching forward month {month_offset}: {e}")
        
    return pd.DataFrame(records)

def fetch_all_forward_curves() -> pd.DataFrame:
    """Fetches all 12 forward months across all hubs."""
    frames = []
    for m in range(1, 13):
        df_m = fetch_forward_month(m)
        if not df_m.empty:
            frames.append(df_m)
            
    if not frames:
        return pd.DataFrame()
        
    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"Retrieved {len(combined)} forward curve points across {len(combined['port'].unique())} hubs and 12 contract months.")
    return combined

if __name__ == "__main__":
    df = fetch_forward_month(1)
    print("Month 1 Forward Prices:")
    print(df)
