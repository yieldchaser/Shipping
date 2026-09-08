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

import bisect
import logging
import re
from datetime import datetime, timezone
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

# Chart-block grade labels in publication order (IFO 380 -> VLSFO -> MGO),
# mapped to the canonical grade tokens used across the BUX/BIX datasets.
_CHART_GRADE_ORDER = ("IFO 380", "VLSFO", "MGO")
_GRADE_TOKEN = {"IFO 380": "IFO380", "VLSFO": "VLSFO", "MGO": "MGO"}

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


# --------------------------------------------------------------------------
# Full-history parsing (chart arrays). The tables only carry the latest 10
# observation days; the Highcharts config on each page embeds the FULL
# published series (a rolling ~1y of daily points) in inline JS:
#   var data = [{"date":"YYYY-MM-DD","price":"664.82"},...];
#   var newArray = data.map(function(obj){ return [Date.parse(obj.date), parseFloat(obj.price)];});
# One such block per grade (IFO 380 -> VLSFO -> MGO, publication order), each
# immediately followed by "let productName = '<grade label>';". The chart
# series carries date+price ONLY - +/-, +/-%, Low, High exist exclusively in
# the latest-10-day tables, so historical rows are emitted with those fields
# empty (never fabricated) and the table rows (which do carry them) win the
# dedupe merge in scripts/bunkers/build_bix_history.py.
# --------------------------------------------------------------------------

# {"date":"2025-09-09","price":"474.63"} - no nested braces, no newlines.
_PAIR_RE = re.compile(r'\{"date":"(\d{4}-\d{2}-\d{2})","price":"([\d.,]+)"\}')


_DECL_RE = re.compile(r'(?:var|let|const)\s+(\w+)\s*=\s*\[')


def _decl_positions(html: str) -> list:
    """All `(bracket_pos, var_name)` declaration positions, ascending."""
    return [(m.end() - 1, m.group(1)) for m in _DECL_RE.finditer(html)]


def _find_array_start(decls, pair_pos: int):
    """Rightmost `var|let|const <name> = [` bracket at or before pair_pos."""
    i = bisect.bisect_right([d[0] for d in decls], pair_pos) - 1
    return decls[i] if i >= 0 else None


def _extract_chart_grade_blocks(html: str) -> list:
    """Extracts every inline chart-data array as a block dict in publication
    order: {'var': <var name>, 'label': <product label or ''>,
    'points': [(date, price), ...]}.

    Verified source layout (one block per grade on every BIX page):
        var data = [{"date":"YYYY-MM-DD","price":"664.82"},...];
        let productName = 'IFO 380';            <- label follows the block
    """
    blocks = []
    decls = _decl_positions(html)
    opened = {}  # array bracket position -> parsed block (one array per grade)
    for m in _PAIR_RE.finditer(html):
        hit = _find_array_start(decls, m.start())
        if hit is None:
            continue
        start, name = hit
        end = html.find('];', start)
        if end == -1 or end < m.start():
            continue
        if start not in opened:
            pairs = [(mm.group(1), mm.group(2).replace(',', ''))
                     for mm in _PAIR_RE.finditer(html, start, end)]
            label = ''
            lm = re.search(r"productName\s*=\s*'([^']+)'", html[end:end + 400])
            if lm:
                label = lm.group(1).strip()
            opened[start] = {'var': name, 'label': label, 'points': pairs}
    # dict preserves insertion order = publication order
    return list(opened.values())


def parse_bix_history(html: str, index_name: str) -> list:
    """Parses the FULL published daily series (chart arrays + latest-10 tables)
    for one BIX index page into long-schema observation rows.

    Returns one row per (grade, observation_date):
    - chart arrays supply every published day (date, price only);
    - the trailing tables supply date/price/change_usd/change_pct/low/high for
      the latest ~10 days and WIN the downstream dedupe merge (build_bix_history.py
      seeds the archive with history rows first, then merges table/seed rows).
    Rows with no parseable price or an out-of-range price are skipped.
    """
    rows = {}
    grade_pub_order = []
    for block in _extract_chart_grade_blocks(html):
        label = block['label']
        grade = _GRADE_TOKEN.get(label)
        if grade is None:
            # Fall back to publication order for unlabelled/renamed blocks.
            label = ''
            for cand in _CHART_GRADE_ORDER:
                tok = _GRADE_TOKEN[cand]
                if tok not in grade_pub_order:
                    grade = tok
                    break
            if grade is None:
                continue
        if grade in grade_pub_order:
            continue  # duplicate chart block for an already-mapped grade
        grade_pub_order.append(grade)
        for obs_date, price_raw in block['points']:
            try:
                price = float(price_raw)
            except (TypeError, ValueError):
                continue
            if not validate_price(price):
                continue
            rows[(grade, obs_date)] = {
                'observation_date': obs_date,
                'index_code': index_name,
                'grade': grade,
                'price_usd': price,
                'change_usd': None,
                'change_pct': None,
                'low_usd': None,
                'high_usd': None,
                'unit': 'USD/MT',
                'source': 'BunkerIndex_BIX',
            }

    # Latest-10 tables: richer rows (change / low / high) for the trailing days.
    soup = BeautifulSoup(html, 'html.parser')
    for i, table in enumerate(soup.find_all('table')):
        if i >= len(grade_pub_order):
            break
        grade = grade_pub_order[i]
        for rec in parse_bix_table(table, index_name, grade):
            rows[(grade, rec['observation_date'])] = rec
    return list(rows.values())


def fetch_bix_history(index_name: str, url: str) -> list:
    """Fetches one BIX page and parses the full published history."""
    try:
        resp = CLIENT.get(url, timeout=15)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch {index_name} history: HTTP {resp.status_code}")
            return []
        return parse_bix_history(resp.text, index_name)
    except Exception as e:
        logger.error(f"Error fetching {index_name} history: {e}")
        return []


def fetch_all_bix_history() -> list:
    """Full published history for every BIX index page x 3 grades."""
    all_rows = []
    for name, url in BIX_ENDPOINTS.items():
        recs = fetch_bix_history(name, url)
        grades = sorted({r['grade'] for r in recs})
        days = {r['observation_date'] for r in recs}
        logger.info(f"BIX history {name}: {len(recs)} rows, "
                    f"{len(days)} obs days ({min(days) if days else '-'} .. {max(days) if days else '-'}) "
                    f"grades={grades}")
        all_rows.extend(recs)
    return all_rows


if __name__ == "__main__":
    df = fetch_bix_suite("BIX_World", BIX_ENDPOINTS["BIX_World"])
    print("BIX World Sample:")
    print(df.head(10))
