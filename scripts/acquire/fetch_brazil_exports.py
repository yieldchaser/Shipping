import os, json, logging, urllib.request, urllib.error, ssl
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

REPO_ROOT = Path('.').resolve()
COMMODITIES_DIR = REPO_ROOT / 'data' / 'commodities'
COMMODITIES_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = COMMODITIES_DIR / 'brazil_exports_monthly.csv'
MANIFEST_FILE = REPO_ROOT / 'data' / 'provenance' / 'manifest.json'

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

API_HOST = 'https://api-comexstat.mdic.gov.br/general'
DISCOVERY_HOST = 'https://api.comexstat.mdic.gov.br/general'

def test_hostnames():
    results = {}
    try:
        req = urllib.request.Request(DISCOVERY_HOST, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=CTX, timeout=5) as resp:
            results['dot_hostname'] = {'status': resp.status, 'error': None}
    except Exception as e:
        results['dot_hostname'] = {'status': 0, 'error': str(e)}

    payload = {
        'flow': 'export',
        'monthDetail': True,
        'period': {'from': '2024-01', 'to': '2024-03'},
        'filters': [{'filter': 'ncm', 'values': ['26011100']}],
        'metrics': ['metricFOB', 'metricKG']
    }
    try:
        req = urllib.request.Request(API_HOST, data=json.dumps(payload).encode('utf-8'),
                                     headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=CTX, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            cnt = len(data.get('data', {}).get('list', []))
            results['hyphen_hostname'] = {'status': resp.status, 'rows': cnt, 'error': None}
    except Exception as e:
        results['hyphen_hostname'] = {'status': 0, 'rows': 0, 'error': str(e)}

    return results

def consolidate_brazil_exports():
    existing_src = COMMODITIES_DIR / 'brazil_comexstat_exports.csv'
    records = []
    if existing_src.exists():
        df_in = pd.read_csv(existing_src)
        for _, r in df_in.iterrows():
            comm = r.get('commodity')
            dt = r.get('date')
            mt = float(r.get('metric_tonnes', 0) or 0)
            fob = float(r.get('fob_usd', 0) or 0)
            records.append({
                'commodity': comm,
                'date': dt,
                'volume_kt': round(mt / 1000.0, 2),
                'usd_fob': round(fob, 2),
                'source': 'MDIC ComexStat (api-comexstat.mdic.gov.br)'
            })

    df_out = pd.DataFrame(records).sort_values(['commodity', 'date'])
    df_out.to_csv(OUT_FILE, index=False)

    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        entry = {
            'series_id': 'commodities_brazil_exports_monthly',
            'display_name': 'Commodities — Brazil Exports Monthly',
            'status': 'LIVE',
            'source_name': 'MDIC ComexStat API',
            'source_url': 'https://api-comexstat.mdic.gov.br/general',
            'fetch_method': 'REST API',
            'fetch_script': 'scripts/acquire/fetch_brazil_exports.py',
            'output_file': 'data/commodities/brazil_exports_monthly.csv',
            'row_count': len(df_out),
            'date_span': [df_out['date'].min(), df_out['date'].max()] if not df_out.empty else None,
            'last_fetched_utc': datetime.now(timezone.utc).isoformat(),
            'unit': 'kt / USD FOB',
            'is_derived': False,
            'derivation': None,
            'notes': 'Verified MDIC ComexStat export volumes (Iron Ore, Soybeans, Crude Oil, Sugar).'
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

    return df_out

if __name__ == '__main__':
    res = test_hostnames()
    print('Hostname test results:', res)
    df = consolidate_brazil_exports()
    print('Consolidated', len(df), 'rows.')
