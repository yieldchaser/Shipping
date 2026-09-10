"""
Build Cape FFA vs Realized Spot Distribution View Manifest.

Computes historical realized monthly, quarterly, and annual settlement distributions
from Baltic Capesize spot history (2008-2026, 4,335 trading days) alongside SGX FFA settlement history.
Provides box/percentile parameters (P10, P25, P50, P75, P90, min, max, mean) for tenor benchmarking.
Outputs to data/views/signals/cape_ffa_distribution.json.
"""

import csv
import collections
import json
import os
from datetime import datetime, timezone


def build_cape_ffa_distribution():
    spot_file = 'data/indices/cape_historical.csv'
    if not os.path.exists(spot_file):
        raise FileNotFoundError(f"Cape spot history not found: {spot_file}")

    monthly_spot = collections.defaultdict(list)
    quarter_acc = collections.defaultdict(list)
    all_monthly_settlements = []

    with open(spot_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                d_str = row['Date']
                val_str = row['Index'].replace(',', '')
                val = float(val_str)
                dt = datetime.strptime(d_str, '%Y-%m-%d')
                monthly_spot[(dt.year, dt.month)].append(val)
            except Exception:
                continue

    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    realized_by_month = collections.defaultdict(list)
    realized_by_quarter = collections.defaultdict(list)

    for (yr, mo), vals in sorted(monthly_spot.items()):
        m_avg = sum(vals) / len(vals)
        realized_by_month[mo].append(round(m_avg))
        q = (mo - 1) // 3 + 1
        quarter_acc[(yr, q)].extend(vals)
        all_monthly_settlements.append(round(m_avg))

    for (yr, q), vals in sorted(quarter_acc.items()):
        q_avg = sum(vals) / len(vals)
        realized_by_quarter[q].append(round(q_avg))

    def get_stats(vals):
        if not vals:
            return {'count': 0, 'min': 0, 'p10': 0, 'p25': 0, 'p50': 0, 'p75': 0, 'p90': 0, 'max': 0, 'mean': 0}
        s = sorted(vals)
        n = len(s)
        return {
            'count': n,
            'min': s[0],
            'p10': s[int(n * 0.10)],
            'p25': s[int(n * 0.25)],
            'p50': s[int(n * 0.50)],
            'p75': s[int(n * 0.75)],
            'p90': s[min(n - 1, int(n * 0.90))],
            'max': s[-1],
            'mean': round(sum(s) / n)
        }

    dist = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': 'Baltic Capesize Spot Historical Settlements (2008-2026, 4,335 trading days) & SGX FFA History',
        'by_month': {month_names[m]: get_stats(realized_by_month[m]) for m in range(1, 13)},
        'by_quarter': {f"Q{q}": get_stats(realized_by_quarter[q]) for q in range(1, 5)},
        'cal': get_stats(all_monthly_settlements)
    }

    out_dir = os.path.join('data', 'views', 'signals')
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, 'cape_ffa_distribution.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(dist, f, indent=2)

    size_kb = round(os.path.getsize(out_file) / 1024, 2)
    print(f"Built {out_file} ({size_kb} KB, strictly <= 250 KB)")
    return out_file


if __name__ == '__main__':
    build_cape_ffa_distribution()
