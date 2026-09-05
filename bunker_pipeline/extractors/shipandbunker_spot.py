#!/usr/bin/env python3
"""
Ship & Bunker Historical Spot Engine Extractor
Queries the internal JSON-RPC endpoint to harvest up to 10+ years of daily spot price history
across all 221 valid ports and macro benchmarks.
"""

import logging
import datetime
from bunker_pipeline.utils.http_client import CLIENT
from bunker_pipeline.utils.normalizer import normalize_grade, validate_price

logger = logging.getLogger("ShipAndBunkerSpot")

RPC_URL = "https://shipandbunker.com/a/.json"

RPC_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://shipandbunker.com",
    "Referer": "https://shipandbunker.com/prices",
}

def fetch_markets_batch(markets_list: list) -> list:
    """
    Fetches historical spot series for a batch of markets (up to 10 at a time)
    via a single POST to /a/.json using mc0, mc1, ... parameters.
    """
    if not markets_list:
        return []
        
    payload = {
        "api-method": "pricesForAllSeriesGet",
        "resource": "MarketPriceGraph_Block",
    }
    
    code_to_name = {}
    for i, m in enumerate(markets_list):
        c = m.get("code") if isinstance(m, dict) else m
        n = m.get("name", c) if isinstance(m, dict) else c
        payload[f"mc{i}"] = c
        code_to_name[c] = n
        
    extracted_rows = []
    try:
        response = CLIENT.post(RPC_URL, data=payload, headers=RPC_HEADERS, timeout=20)
        if response.status_code != 200:
            logger.error(f"Batch fetch failed: HTTP {response.status_code}")
            return []
            
        data_json = response.json()
        api_data = data_json.get("api", {})
        
        for m_code, market_data in api_data.items():
            if not isinstance(market_data, dict):
                continue
            inner_data = market_data.get("data", {})
            resolved_name = code_to_name.get(m_code) or inner_data.get("market_name", m_code)
            prices_dict = inner_data.get("prices", {})
            day_list_dict = inner_data.get("day_list", {})
            
            for raw_grade, grade_data in prices_dict.items():
                std_grade = normalize_grade(raw_grade)
                dayprice_list = grade_data.get("dayprice", [])
                grade_days = day_list_dict.get(raw_grade, {})
                
                for item in dayprice_list:
                    if not isinstance(item, list) or len(item) < 2:
                        continue
                    day_idx = str(item[0])
                    price_val = item[1]
                    
                    if not validate_price(price_val):
                        continue
                        
                    timestamp_ms = grade_days.get(day_idx)
                    if not timestamp_ms:
                        continue
                        
                    obs_date = datetime.datetime.fromtimestamp(
                        timestamp_ms / 1000.0, tz=datetime.timezone.utc
                    ).strftime("%Y-%m-%d")
                    
                    extracted_rows.append({
                        "observation_date": obs_date,
                        "port_code": m_code,
                        "port_name": resolved_name,
                        "grade": std_grade,
                        "delivery_term": "Prompt",
                        "price_usd": float(price_val),
                        "change_usd": None,
                        "high_usd": None,
                        "low_usd": None,
                        "spread_usd": None,
                        "unit": "USD/MT",
                        "source": "ShipAndBunker_RPC"
                    })
                    
        logger.info(f"Batch of {len(markets_list)} markets yielded {len(extracted_rows)} total price records.")
    except Exception as e:
        logger.error(f"Error in batch fetch for {list(code_to_name.keys())}: {e}")
        
    return extracted_rows

def fetch_market(market_code: str, market_name: str = None) -> list:
    """Fetches the full historical spot series for a single market code."""
    return fetch_markets_batch([{"code": market_code, "name": market_name or market_code}])

if __name__ == "__main__":
    test_res = fetch_market("SG SIN", "Singapore")
    print(f"Retrieved {len(test_res)} records for Singapore.")
    if test_res:
        print("First record:", test_res[0])
        print("Last record:", test_res[-1])
