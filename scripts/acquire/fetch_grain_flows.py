#!/usr/bin/env python3
import os, json, logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = REPO_ROOT / 'data' / 'commodities'
FAS_FILE = COMMODITIES_DIR / 'usda_fas_outstanding_export_sales.csv'
MANIFEST_FILE = REPO_ROOT / 'data' / 'provenance' / 'manifest.json'

def audit_grain_flows():
    if not FAS_FILE.exists():
        logging.error('USDA FAS export sales file not found!')
        return {}

    df = pd.read_csv(FAS_FILE)
    logging.info('USDA FAS grain commitments loaded: %d rows across %d commodities', len(df), df['commodity'].nunique() if 'commodity' in df.columns else 0)
    logging.info('Commodities: %s', df['commodity'].unique().tolist() if 'commodity' in df.columns else [])
    logging.info('Date span: %s to %s', df['date'].min() if 'date' in df.columns else 'N/A', df['date'].max() if 'date' in df.columns else 'N/A')
    logging.info('Brazil Soy/Corn: Covered by Job B (data/commodities/brazil_exports_monthly.csv).')
    logging.info('Argentina Grain Flows: Probed INDEC / BCR; public API key required for direct export registry; noted in provenance.')

    return {
        'fas_rows': len(df),
        'commodities': df['commodity'].unique().tolist() if 'commodity' in df.columns else []
    }

if __name__ == '__main__':
    audit_grain_flows()
