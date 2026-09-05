#!/usr/bin/env python3
"""
Data Normalization & Cleaning Utilities for Bunker Ingestion Pipeline
"""

import re
from datetime import datetime, timezone, date

GRADE_ALIASES = {
    "VLSFO": "VLSFO",
    "0.5%": "VLSFO",
    "VLSFO (0.5%)": "VLSFO",
    "IFO 380": "IFO380",
    "IFO380": "IFO380",
    "380 CST": "IFO380",
    "HSFO": "IFO380",
    "IFO 180": "IFO180",
    "IFO180": "IFO180",
    "180 CST": "IFO180",
    "MGO": "MGO",
    "MGO (0.1%)": "MGO",
    "LSMGO": "LSMGO",
    "DMA": "MGO",
    "BIO": "BIO",
    "B24": "BIO",
    "B30": "BIO",
    "SS": "SS",
    "MEOH": "MEOH",
    "METHANOL": "MEOH",
    "LNG": "LNG",
}

def normalize_grade(raw_grade: str) -> str:
    clean = raw_grade.strip().upper()
    clean = re.sub(r'[^A-Z0-9\.\%\s]', '', clean)
    for alias, standardized in GRADE_ALIASES.items():
        if alias.upper() == clean:
            return standardized
    if "VLSFO" in clean or "0.5" in clean:
        return "VLSFO"
    if "380" in clean:
        return "IFO380"
    if "180" in clean:
        return "IFO180"
    if "LSMGO" in clean:
        return "LSMGO"
    if "MGO" in clean:
        return "MGO"
    if "BIO" in clean:
        return "BIO"
    if "MEOH" in clean:
        return "MEOH"
    return clean

def normalize_timestamp_ms(timestamp_ms: int) -> str:
    """Converts unix timestamp in milliseconds to YYYY-MM-DD in UTC."""
    dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")

def normalize_date_str(date_str: str, default_year: int = None) -> str:
    """Standardizes string dates like '2026-09-04', '04 Sep', 'FSep 4' to YYYY-MM-DD."""
    if not date_str:
        return date.today().strftime("%Y-%m-%d")
    date_str = date_str.strip()
    # If already YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    # If YYYYMMDD
    if re.match(r'^\d{8}$', date_str):
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    
    current_year = default_year or date.today().year
    
    # Strip day of week prefixes like 'F', 'T', 'W', 'M', 'S'
    clean = re.sub(r'^[A-Za-z]{1,3}\s*', '', date_str)
    
    # Try formats like '04 Sep', 'Sep 04', 'Sep 4'
    month_names = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    match = re.search(r'([0-9]{1,2})\s*([A-Za-z]{3})', date_str)
    if match:
        day = int(match.group(1))
        mon_str = match.group(2).lower()
        if mon_str in month_names:
            return f"{current_year:04d}-{month_names[mon_str]:02d}-{day:02d}"
            
    match2 = re.search(r'([A-Za-z]{3})\s*([0-9]{1,2})', date_str)
    if match2:
        mon_str = match2.group(1).lower()
        day = int(match2.group(2))
        if mon_str in month_names:
            return f"{current_year:04d}-{month_names[mon_str]:02d}-{day:02d}"
            
    return date_str

def validate_price(price: float, min_val: float = 50.0, max_val: float = 3000.0) -> bool:
    """Validates that price is a positive finite float within realistic maritime limits."""
    if price is None:
        return False
    try:
        val = float(price)
        return min_val <= val <= max_val
    except (ValueError, TypeError):
        return False
