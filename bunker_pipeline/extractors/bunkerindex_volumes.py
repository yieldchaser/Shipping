#!/usr/bin/env python3
"""
Physical Bunker Demand Indicators Extractor
Collects official physical bunker sales volumes (in Metric Tonnes) for Singapore and Rotterdam.
"""

import re
import json
import logging
from bs4 import BeautifulSoup
import pandas as pd
from bunker_pipeline.utils.http_client import CLIENT

logger = logging.getLogger("BunkerIndexVolumes")

INDICATOR_META = {
    2: {"port": "Singapore", "metric": "Sales_Monthly_MT", "frequency": "Monthly"},
    44: {"port": "Singapore", "metric": "Sales_Trailing_3M_MT", "frequency": "T3M"},
    4: {"port": "Singapore", "metric": "Sales_TTM_MT", "frequency": "TTM"},
    45: {"port": "Singapore", "metric": "Sales_CY_MT", "frequency": "CY"},
    3: {"port": "Rotterdam", "metric": "Sales_Quarterly_MT", "frequency": "Quarterly"},
    5: {"port": "Rotterdam", "metric": "Sales_TTM_MT", "frequency": "TTM"},
    46: {"port": "Rotterdam", "metric": "Sales_CY_MT", "frequency": "CY"},
}

def fetch_indicator(indicator_id: int) -> pd.DataFrame:
    """
    Fetches physical volume time series for an indicator ID.
    Returns DataFrame with columns [period, port, metric, volume_mt, frequency, source].
    """
    url = f"https://www.bunkerindex.com/indicators/indicator.php?i={indicator_id}"
    meta = INDICATOR_META.get(indicator_id, {"port": "Unknown", "metric": f"Indicator_{indicator_id}", "frequency": "Custom"})
    
    records = []
    try:
        resp = CLIENT.get(url, timeout=12)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch indicator {indicator_id}: HTTP {resp.status_code}")
            return pd.DataFrame()
            
        # Method 1: Regex on JSON data array in script: let data = [{"date":"2024-08","datum":4559452}, ...]
        match = re.search(r'let\s+data\s*=\s*(\[\{.*?\}\]);', resp.text, re.DOTALL)
        if match:
            raw_json = match.group(1)
            parsed = json.loads(raw_json)
            for item in parsed:
                p_date = item.get("date")
                v_mt = item.get("datum")
                if p_date and v_mt is not None:
                    records.append({
                        "indicator_id": indicator_id,
                        "period": str(p_date),
                        "port": meta["port"],
                        "metric": meta["metric"],
                        "volume_mt": float(v_mt),
                        "frequency": meta["frequency"],
                        "source": "BunkerIndex_Indicators"
                    })
                    
        # Method 2: Fallback to HTML table parsing
        if not records:
            soup = BeautifulSoup(resp.text, "html.parser")
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                    if len(cells) >= 2:
                        p_str = cells[0]
                        v_str = cells[1].replace(",", "").replace("MT", "").replace("mt", "").strip()
                        try:
                            v_float = float(v_str)
                            if re.match(r'^\d{4}', p_str) and v_float > 100000:
                                records.append({
                                    "indicator_id": indicator_id,
                                    "period": p_str,
                                    "port": meta["port"],
                                    "metric": meta["metric"],
                                    "volume_mt": v_float,
                                    "frequency": meta["frequency"],
                                    "source": "BunkerIndex_Indicators"
                                })
                        except ValueError:
                            pass
                            
    except Exception as e:
        logger.error(f"Error extracting indicator {indicator_id}: {e}")
        
    df = pd.DataFrame(records)
    if not df.empty:
        logger.info(f"Retrieved {len(df)} volume records for Indicator {indicator_id} ({meta['port']} {meta['metric']})")
    return df

def fetch_all_volume_indicators() -> pd.DataFrame:
    """Fetches all 7 official bunker sales volume series."""
    frames = []
    for i_id in INDICATOR_META.keys():
        df = fetch_indicator(i_id)
        if not df.empty:
            frames.append(df)
            
    if not frames:
        return pd.DataFrame()
        
    combined = pd.concat(frames, ignore_index=True)
    return combined

if __name__ == "__main__":
    df = fetch_indicator(2)
    print("Singapore Monthly Bunker Sales Sample:")
    print(df.tail(10))
