#!/usr/bin/env python3
"""
Data Health & Freshness Monitor
Audits all CSV datasets in data/ relative to current date (or specified target date).
Referenced in docs/DATASETS.md.
"""

import csv
import glob
import os
import sys
import datetime

TARGET_DATE = datetime.date.today()

def parse_date_str(d_str):
    if not d_str:
        return None
    d_str = str(d_str).strip()
    try:
        if '-' in d_str:
            parts = d_str.split('-')
            if len(parts) == 3:
                if len(parts[0]) == 4:
                    return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                elif len(parts[2]) == 4:
                    return datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
        if '/' in d_str:
            parts = d_str.split('/')
            if len(parts) == 3:
                if len(parts[0]) == 4:
                    return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                elif len(parts[2]) == 4:
                    return datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
    except Exception:
        pass
    return None

def audit_data_health(target_date=TARGET_DATE):
    categories = ['indices', 'derived', 'etf', 'futures']
    all_results = []

    for cat in categories:
        files = sorted(glob.glob(f'data/{cat}/*.csv'))
        for filepath in files:
            fname = os.path.basename(filepath)
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                rows = list(reader)

            if not rows:
                all_results.append({
                    'category': cat,
                    'file': fname,
                    'rows': 0,
                    'columns': len(fieldnames),
                    'first_date': 'N/A',
                    'latest_date': 'N/A',
                    'days_lag': 9999,
                    'status': 'EMPTY'
                })
                continue

            date_col = None
            for col in fieldnames:
                if col.lower() in ('date', 'datestr', 'asofdate', 'timestamp'):
                    date_col = col
                    break
            if not date_col:
                date_col = fieldnames[0]

            valid_dates = []
            for r in rows:
                dt = parse_date_str(r.get(date_col, ''))
                if dt:
                    valid_dates.append(dt)

            if not valid_dates:
                all_results.append({
                    'category': cat,
                    'file': fname,
                    'rows': len(rows),
                    'columns': len(fieldnames),
                    'first_date': 'Static Metadata',
                    'latest_date': 'Static Metadata',
                    'days_lag': 0,
                    'status': 'STATIC'
                })
                continue

            valid_dates.sort()
            first_dt = valid_dates[0]
            latest_dt = valid_dates[-1]
            lag_days = (target_date - latest_dt).days

            # Ignore known legacy/discontinued datasets
            is_legacy = fname in ('blpg_fearnleys_historical.csv', 'BDRY_Daily.csv', 'BWET_Daily.csv')

            if lag_days <= 7:
                status = 'ACTIVE'
            elif lag_days <= 30:
                status = 'LAGGED'
            elif is_legacy:
                status = 'LEGACY (Superseded)'
            else:
                status = 'STALE'

            all_results.append({
                'category': cat,
                'file': fname,
                'rows': len(rows),
                'columns': len(fieldnames),
                'first_date': first_dt.strftime('%Y-%m-%d'),
                'latest_date': latest_dt.strftime('%Y-%m-%d'),
                'days_lag': lag_days,
                'status': status
            })

    return all_results

if __name__ == '__main__':
    results = audit_data_health()
    print('=== DATA HEALTH & FRESHNESS MONITOR ===\n')
    print(f'Target Date: {TARGET_DATE.strftime("%Y-%m-%d")}\n')
    print(f'{"Category":<10} | {"File Name":<35} | {"Rows":<6} | {"Start Date":<10} | {"Latest Date":<10} | {"Lag (Days)":<10} | {"Status"}')
    print('-' * 110)

    stale_count = 0
    for r in results:
        print(f'{r["category"]:<10} | {r["file"]:<35} | {r["rows"]:<6} | {r["first_date"]:<10} | {r["latest_date"]:<10} | {r["days_lag"]:<10} | {r["status"]}')
        if r['status'] == 'STALE':
            stale_count += 1

    print('-' * 110)
    if stale_count > 0:
        print(f'\n[WARNING] {stale_count} unhandled stale dataset(s) detected!')
        sys.exit(1)
    else:
        print('\n[SUCCESS] All datasets are healthy and up to date!')
        sys.exit(0)
