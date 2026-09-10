import os, sys, json, logging, urllib.request, urllib.error, ssl
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = REPO_ROOT / 'data' / 'commodities'
COMMODITIES_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = COMMODITIES_DIR / 'guinea_bauxite_exports.csv'
MANIFEST_FILE = REPO_ROOT / 'data' / 'provenance' / 'manifest.json'

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def test_source_1_comtrade_direct():
    url = 'https://comtradeapi.un.org/data/v1/get/C/M/HS?reporterCode=324&cmdCode=260600&period=202401'
    logging.info('Testing Source 1: UN Comtrade Guinea direct (%s)', url)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=CTX, timeout=8) as resp:
            return resp.status, resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return 0, str(e)

def test_source_2_comtrade_china_mirror():
    url = 'https://comtradeapi.un.org/public/v1/preview/C/M/HS?reporterCode=156&partnerCode=324&cmdCode=260600&flowCode=M&period=202401'
    logging.info('Testing Source 2: UN Comtrade China mirror (%s)', url)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=CTX, timeout=8) as resp:
            return resp.status, resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return 0, str(e)

def test_source_4_guinea_eiti():
    url = 'https://opendataitie-guinee.org/'
    logging.info('Testing Source 4: Guinea EITI portal (%s)', url)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=CTX, timeout=8) as resp:
            return resp.status, 'Portal reachable'
    except Exception as e:
        return 0, str(e)

def run_job_a():
    logging.info('Starting Job A: Guinea Bauxite Re-acquisition audit...')
    results = {}
    
    # 1. UN Comtrade Direct
    s1_code, s1_resp = test_source_1_comtrade_direct()
    results['UN_Comtrade_Direct'] = {'status_code': s1_code, 'summary': s1_resp[:120]}
    logging.info('Source 1 Result: HTTP %s -> %s', s1_code, s1_resp[:80])
    
    # 2. UN Comtrade China Mirror
    s2_code, s2_resp = test_source_2_comtrade_china_mirror()
    results['UN_Comtrade_China_Mirror'] = {'status_code': s2_code, 'summary': s2_resp[:120]}
    logging.info('Source 2 Result: HTTP %s -> %s', s2_code, s2_resp[:80])
    
    # 4. Guinea EITI
    s4_code, s4_resp = test_source_4_guinea_eiti()
    results['Guinea_EITI'] = {'status_code': s4_code, 'summary': s4_resp[:120]}
    logging.info('Source 4 Result: HTTP %s -> %s', s4_code, s4_resp[:80])

    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        entry = {
            'series_id': 'commodities_guinea_bauxite_exports',
            'display_name': 'Commodities — Guinea Bauxite Exports',
            'status': 'UNAVAILABLE',
            'source_name': 'UN Comtrade / China GACC (Pending Key)',
            'source_url': 'https://comtradeapi.un.org/data/v1/get/C/M/HS',
            'fetch_method': 'REST API',
            'fetch_script': 'scripts/acquire/fetch_guinea_bauxite.py',
            'output_file': 'data/commodities/guinea_bauxite_exports.csv',
            'row_count': 0,
            'date_span': None,
            'last_fetched_utc': datetime.now(timezone.utc).isoformat(),
            'unit': 'kt',
            'is_derived': False,
            'derivation': None,
            'notes': 'UN Comtrade v1 requires COMTRADE_API_KEY (HTTP 401); public preview endpoints intermittent/timed out. Tagged UNAVAILABLE pending scraping key.'
        }
        
        found = False
        for i, s in enumerate(manifest['series']):
            if s['series_id'] == entry['series_id']:
                manifest['series'][i] = entry
                found = True
                break
        if not found:
            manifest['series'].append(entry)
            
        with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        logging.info('Updated provenance manifest: commodities_guinea_bauxite_exports marked UNAVAILABLE.')

    return results

if __name__ == '__main__':
    run_job_a()
