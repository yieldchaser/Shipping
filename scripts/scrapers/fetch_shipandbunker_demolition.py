#!/usr/bin/env python3
import os
import sys
import re
import logging
import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath('.'))
from bunker_pipeline.utils.http_client import CLIENT

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('SBDemolition')

OUT_DIR = 'data/demolition'
os.makedirs(OUT_DIR, exist_ok=True)

def crawl_demolition_reports(max_pages: int = 10):
    all_fixtures = []
    all_rates = []
    seen_urls = set()

    for p in range(1, max_pages + 1):
        url = f'https://shipandbunker.com/news/features/risk-management/?page={p}'
        logger.info(f'Fetching index page {p}: {url}')
        resp = CLIENT.get(url)
        if resp.status_code != 200:
            logger.warning(f'Failed to fetch page {p}')
            break
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        report_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'weekly-vessel-scrapping-report' in href:
                full_url = href if href.startswith('http') else 'https://shipandbunker.com' + href
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    report_links.append(full_url)
                    
        logger.info(f'Discovered {len(report_links)} reports on page {p}')
        for rep_url in report_links:
            try:
                r_resp = CLIENT.get(rep_url)
                if r_resp.status_code != 200:
                    continue
                r_soup = BeautifulSoup(r_resp.text, 'html.parser')
                
                m_yw = re.search(r'(\d{4})-week-(\d{1,2})', rep_url)
                year = int(m_yw.group(1)) if m_yw else None
                week = int(m_yw.group(2)) if m_yw else None
                
                # Extract date from text
                m_dt = re.search(r'([A-Za-z]+day,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4})', r_soup.text)
                pub_date = m_dt.group(1) if m_dt else None

                tables = r_soup.find_all('table')
                for t in tables:
                    rows = t.find_all('tr')
                    for row in rows:
                        cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                        if len(cells) >= 5 and cells[0] not in ['Sale Date', '']:
                            all_fixtures.append({
                                'year': year,
                                'week': week,
                                'published_date': pub_date,
                                'sale_date': cells[0],
                                'vessel_name': cells[1],
                                'vessel_type': cells[2],
                                'build_date': cells[3],
                                'seller': cells[4],
                                'source': 'ShipAndBunker_VesselsValue'
                            })
            except Exception as e:
                logger.error(f'Error processing {rep_url}: {e}')

    if all_fixtures:
        df_fix = pd.DataFrame(all_fixtures).drop_duplicates(subset=['sale_date', 'vessel_name', 'vessel_type'])
        out_csv = os.path.join(OUT_DIR, 'shipandbunker_demolition_fixtures.csv')
        df_fix.to_csv(out_csv, index=False)
        logger.info(f'Saved {len(df_fix)} unique demolition fixtures to {out_csv}')
    return len(all_fixtures)

if __name__ == '__main__':
    crawl_demolition_reports(max_pages=5)
