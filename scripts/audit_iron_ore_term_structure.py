#!/usr/bin/env python3
"""
Deep Forensic Audit of SGX Iron Ore Derivatives (FEF & FEM):
1. Historical Depth Audit: Can we retrieve >100 to >1,000 days of daily settlement history per contract?
2. Expired Contracts Test: Does the API retain full trading history for expired historical contracts (2021-2025)?
3. Forward Curve Term Structure: Maps the complete forward curve across all consecutive monthly tenors out to 2028/2029.
4. Liquidity & Open Interest Concentration: Analyzes where open interest and trading volume reside across the curve.
"""

import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime, date

sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Referer': 'https://www.sgx.com/',
    'Origin': 'https://www.sgx.com',
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

CME_MONTHS = {
    'F': (1, 'Jan'), 'G': (2, 'Feb'), 'H': (3, 'Mar'), 'J': (4, 'Apr'),
    'K': (5, 'May'), 'M': (6, 'Jun'), 'N': (7, 'Jul'), 'Q': (8, 'Aug'),
    'U': (9, 'Sep'), 'V': (10, 'Oct'), 'X': (11, 'Nov'), 'Z': (12, 'Dec')
}

def audit_single_contract_depth():
    print("=" * 90)
    print("PART 1: TESTING HISTORICAL DEPTH (>100 TO 1,000+ DAYS) FOR INDIVIDUAL CONTRACTS")
    print("=" * 90)

    # Test prompt, near, deferred, and far-deferred contracts for FEF (62% Fe)
    test_symbols = [
        ("FEFU26", "FEF Prompt Month (Sep 2026)"),
        ("FEFV26", "FEF Near Month (Oct 2026)"),
        ("FEFZ26", "FEF 3M Forward (Dec 2026)"),
        ("FEFJ27", "FEF 7M Forward (Apr 2027)"),
        ("FEFZ27", "FEF 15M Forward (Dec 2027)"),
        ("FEFZ28", "FEF 27M Far Forward (Dec 2028)"),
    ]

    for ticker, desc in test_symbols:
        url = f"https://api.sgx.com/derivatives/v1.0/history/symbol/{ticker}?days=5y&category=futures&params=base-date,daily-settlement-price-abs,total-volume,open-interest"
        try:
            r = SESSION.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json().get('data', [])
                if data:
                    dates = [d.get('base-date') for d in data if d.get('base-date')]
                    prices = [float(d.get('daily-settlement-price-abs', 0)) for d in data if d.get('daily-settlement-price-abs') is not None]
                    volumes = [float(d.get('total-volume', 0)) for d in data]
                    ois = [float(d.get('open-interest', 0)) for d in data]

                    first_date = dates[0] if dates else 'N/A'
                    last_date = dates[-1] if dates else 'N/A'
                    min_p = min(prices) if prices else 0
                    max_p = max(prices) if prices else 0
                    latest_p = prices[-1] if prices else 0
                    latest_oi = ois[-1] if ois else 0

                    print(f"✔ {ticker:<8} ({desc:<30}) -> {len(data):>4} Daily Bars | {first_date} to {last_date} | Settle: ${latest_p:>6.2f} (Range: ${min_p:.2f}-${max_p:.2f}) | OI: {latest_oi:>8,.0f} lots")
                else:
                    print(f"✖ {ticker:<8} ({desc:<30}) -> 0 records returned")
            else:
                print(f"✖ {ticker:<8} -> HTTP {r.status_code}")
        except Exception as e:
            print(f"Error {ticker}: {e}")
        time.sleep(0.04)

def audit_expired_contracts():
    print("\n" + "=" * 90)
    print("PART 2: TESTING EXPIRED HISTORICAL CONTRACTS RETENTION (2021 TO 2025)")
    print("=" * 90)

    # Test historical contracts that expired in past years
    expired_candidates = [
        ("FEFZ25", "FEF Dec 2025 (Expired)"),
        ("FEFU25", "FEF Sep 2025 (Expired)"),
        ("FEFZ24", "FEF Dec 2024 (Expired)"),
        ("FEFU24", "FEF Sep 2024 (Expired)"),
        ("FEFZ23", "FEF Dec 2023 (Expired)"),
        ("FEFZ22", "FEF Dec 2022 (Expired)"),
        ("FEFZ21", "FEF Dec 2021 (Expired)"),
    ]

    for ticker, desc in expired_candidates:
        url = f"https://api.sgx.com/derivatives/v1.0/history/symbol/{ticker}?days=5y&category=futures&params=base-date,daily-settlement-price-abs,total-volume,open-interest"
        try:
            r = SESSION.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json().get('data', [])
                if data:
                    dates = [d.get('base-date') for d in data if d.get('base-date')]
                    prices = [float(d.get('daily-settlement-price-abs', 0)) for d in data if d.get('daily-settlement-price-abs') is not None]
                    print(f"✔ [EXPIRED RETAINED] {ticker:<8} ({desc:<25}) -> {len(data):>4} Historical Daily Bars | {dates[0]} to {dates[-1]} | Final Settle: ${prices[-1]:.2f}")
                else:
                    print(f"✖ [NO DATA]          {ticker:<8} ({desc:<25}) -> 0 records (purged upon expiry)")
            else:
                print(f"✖ [ERROR]            {ticker:<8} -> HTTP {r.status_code}")
        except Exception as e:
            print(f"Error {ticker}: {e}")
        time.sleep(0.04)

def map_full_iron_ore_curve():
    print("\n" + "=" * 90)
    print("PART 3: MAPPING THE COMPLETE ACTIVE FORWARD CURVE & TERM STRUCTURE (FEF 62% & FEM 65%)")
    print("=" * 90)

    now = datetime.now()
    cur_year = now.year
    cur_month = now.month

    # Generate all candidate delivery months from current month to Dec 2028 (36 months)
    curve_tenors = []
    for y in range(cur_year, cur_year + 3):
        y2 = str(y)[-2:]
        for m_code, (m_num, m_name) in CME_MONTHS.items():
            if y == cur_year and m_num < cur_month:
                continue
            curve_tenors.append((m_code, y2, y, m_num, m_name))

    print(f"Scanning {len(curve_tenors)} forward monthly contracts across 62% Fe (FEF) and 65% Fe (FEM)...")
    
    fef_curve = []
    fem_curve = []

    for m_code, y2, y, m_num, m_name in curve_tenors:
        tenor_label = f"{m_name}-{y}"
        # 1. FEF (62% Fe)
        ticker_fef = f"FEF{m_code}{y2}"
        url_fef = f"https://api.sgx.com/derivatives/v1.0/history/symbol/{ticker_fef}?days=5d&category=futures&params=base-date,daily-settlement-price-abs,total-volume,open-interest"
        try:
            r = SESSION.get(url_fef, timeout=5)
            if r.status_code == 200:
                data = r.json().get('data', [])
                if data:
                    valid_rows = [row for row in data if row.get('daily-settlement-price-abs', 0) > 0 or row.get('open-interest', 0) > 0]
                    if valid_rows:
                        last = valid_rows[-1]
                        fef_curve.append({
                            "ticker": ticker_fef,
                            "tenor": tenor_label,
                            "year": y,
                            "month": m_num,
                            "settlement": last.get('daily-settlement-price-abs', 0),
                            "volume": last.get('total-volume', 0),
                            "open_interest": last.get('open-interest', 0),
                            "date": last.get('base-date')
                        })
        except Exception:
            pass

        # 2. FEM (65% Fe)
        ticker_fem = f"FEM{m_code}{y2}"
        url_fem = f"https://api.sgx.com/derivatives/v1.0/history/symbol/{ticker_fem}?days=5d&category=futures&params=base-date,daily-settlement-price-abs,total-volume,open-interest"
        try:
            r = SESSION.get(url_fem, timeout=5)
            if r.status_code == 200:
                data = r.json().get('data', [])
                if data:
                    valid_rows = [row for row in data if row.get('daily-settlement-price-abs', 0) > 0 or row.get('open-interest', 0) > 0]
                    if valid_rows:
                        last = valid_rows[-1]
                        fem_curve.append({
                            "ticker": ticker_fem,
                            "tenor": tenor_label,
                            "year": y,
                            "month": m_num,
                            "settlement": last.get('daily-settlement-price-abs', 0),
                            "volume": last.get('total-volume', 0),
                            "open_interest": last.get('open-interest', 0),
                            "date": last.get('base-date')
                        })
        except Exception:
            pass
        time.sleep(0.03)

    print(f"\n✔ Discovered {len(fef_curve)} active forward monthly contracts for FEF (62% Fe)")
    print(f"✔ Discovered {len(fem_curve)} active forward monthly contracts for FEM (65% Fe)")

    print("\n" + "=" * 95)
    print(f"{'Tenor':<12} | {'FEF Ticker':<10} | {'FEF Settle ($/dmt)':<20} | {'FEF OI (Lots)':<15} | {'FEF Volume':<12} | {'Term Structure Slope'}")
    print("-" * 95)

    prompt_price = fef_curve[0]['settlement'] if fef_curve else 0

    for i, row in enumerate(fef_curve):
        settle = row['settlement']
        oi = row['open_interest']
        vol = row['volume']
        diff = settle - prompt_price
        pct = (diff / prompt_price) * 100 if prompt_price else 0
        slope_str = f"{diff:+.2f} ({pct:+.1f}%)" if i > 0 else "PROMPT BASELINE"
        regime = "Backwardation" if diff < -0.2 else ("Contango" if diff > 0.2 else "Flat")
        if i == 0: regime = "Prompt"

        print(f"{row['tenor']:<12} | {row['ticker']:<10} | ${settle:>10.2f} /dmt      | {oi:>10,.0f} lots  | {vol:>8,.0f}   | {slope_str:<18} [{regime}]")

    total_fef_oi = sum(r['open_interest'] for r in fef_curve)
    total_fef_vol = sum(r['volume'] for r in fef_curve)
    print("\n" + "=" * 95)
    print(f"FEF (62% Iron Ore) Total Curve Open Interest: {total_fef_oi:,.0f} lots (~{total_fef_oi/10000:.2f} Million Metric Tonnes)")
    print(f"FEF (62% Iron Ore) Total Daily Cleared Volume: {total_fef_vol:,.0f} lots (~{total_fef_vol/10000:.2f} Million Metric Tonnes/day)")
    print("=" * 95)

if __name__ == "__main__":
    audit_single_contract_depth()
    audit_expired_contracts()
    map_full_iron_ore_curve()
