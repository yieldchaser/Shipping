#!/usr/bin/env python3
import os, json, logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = REPO_ROOT / 'data' / 'bunkers' / 'bunker_forward_curves_12m.csv'

def audit_curve_slopes():
    if not CSV_PATH.exists():
        logging.error('bunker_forward_curves_12m.csv not found!')
        return {}

    df = pd.read_csv(CSV_PATH)
    hub_slopes = {}
    for hub in df['port'].unique():
        hdf = df[df['port'] == hub].sort_values('month_offset')
        vals = hdf['vlsfo_usd'].values
        ratios = [vals[i]/vals[i-1] for i in range(1, len(vals))]
        hub_slopes[hub] = [round(r, 5) for r in ratios]

    first_slopes = list(hub_slopes.values())[0]
    all_identical = all(slopes == first_slopes for slopes in hub_slopes.values())
    logging.info('All 6 unmasked hubs share identical slope to 5 decimal places: %s', all_identical)
    logging.info('Sample slope decay (m2/m1): %s, (m12/m11): %s', first_slopes[0], first_slopes[-1])
    return {
        'all_identical': all_identical,
        'decay_ratios': first_slopes
    }

if __name__ == '__main__':
    audit_curve_slopes()
