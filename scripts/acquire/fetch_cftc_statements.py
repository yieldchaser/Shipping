"""Fetch Amplify BDRY/BWET monthly account statements (CFTC 4.22 source PDFs).

Probes the last N months for each fund; downloads only PDFs not already
present in data/cftc_statements/raw_pdf/<FUND>/. Idempotent: exits 0 with
"no new statements" when the publisher hasn't released anything new
(e.g. August 2026 still 404 as of 2026-09-21).

Usage:
    python scripts/acquire/fetch_cftc_statements.py [--months 4]
"""
import argparse
import os
import sys
from datetime import date

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIRS = {
    "BDRY": os.path.join(REPO_ROOT, "data", "cftc_statements", "raw_pdf", "BDRY"),
    "BWET": os.path.join(REPO_ROOT, "data", "cftc_statements", "raw_pdf", "BWET"),
}
URL = "https://amplifyetfs.com/wp-content/uploads/files/{fund}/Account_Statements/{fund}_{month}-{year}.pdf"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Shipping-CFTC-ingest/1.0"})


def fetch(months: int) -> int:
    today = date.today()
    new = 0
    for fund, dest in RAW_DIRS.items():
        os.makedirs(dest, exist_ok=True)
        for back in range(months):
            m = today.month - back
            y = today.year
            while m < 1:
                m += 12
                y -= 1
            month_name = date(y, m, 1).strftime("%B")
            fname = f"{fund}_{month_name}-{y}.pdf"
            fp = os.path.join(dest, fname)
            if os.path.exists(fp) and os.path.getsize(fp) > 1000:
                continue
            url = URL.format(fund=fund, month=month_name, year=y)
            try:
                r = SESSION.get(url, timeout=60)
            except requests.RequestException as exc:
                print(f"  ! {fname}: request failed ({exc})")
                continue
            ctype = r.headers.get("Content-Type", "")
            if r.status_code == 200 and "pdf" in ctype.lower():
                with open(fp, "wb") as f:
                    f.write(r.content)
                print(f"  + {fname} ({len(r.content) // 1024} KB)")
                new += 1
            else:
                print(f"  - {fname}: HTTP {r.status_code} (not yet published)")
    print(f"[*] {new} new statement(s) downloaded")
    return new


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch Amplify monthly account statements")
    ap.add_argument("--months", type=int, default=4, help="How many trailing months to probe")
    args = ap.parse_args()
    fetch(args.months)
    return 0


if __name__ == "__main__":
    sys.exit(main())
