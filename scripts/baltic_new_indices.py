"""
Baltic Exchange - Comprehensive Indices Scraper & Poller
=========================================================
Fetches all 11 benchmark indices from the Baltic Exchange public ticker API:
  https://blacksun-api.balticexchange.com/api/ticker
and upserts them into historical CSVs with non-destructive deduplication.

Supported Series:
  - Core Dry Bulk: BDI, BCI (Capesize), BPI (Panamax), BSI (Supramax), BHSI (Handysize)
  - Core Tanker:   BDTI (Dirty Tanker), BCTI (Clean Tanker)
  - Gas & Specialized: BLNG (LNG), BLPG (LPG), FBX (Container), BAI00 (Air Freight)

Schema & Formatting Guarantees:
  - Core series maintain standard ISO YYYY-MM-DD and signed percentage delta.
  - Gas/container/air series maintain legacy DD-MM-YYYY format.
  - Existing multi-decade histories are never rewritten or truncated; updates are
    strictly tail-only upserts with sanity guards.

Usage:
  python scripts/baltic_new_indices.py --repo .
  python scripts/baltic_new_indices.py --repo . --validate-only
"""

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


API_URL = "https://blacksun-api.balticexchange.com/api/ticker"

INDEX_CONFIGS = {
    # 7 Core Historical Indices (ISO YYYY-MM-DD date convention)
    "BDI": {
        "file": "data/indices/bdiy_historical.csv",
        "date_fmt": "%Y-%m-%d",
        "pct_fmt": "{pct:+.2f}%",
        "min_value": 100.0,
        "max_abs_daily_pct": 35.0,
    },
    "BCI": {
        "file": "data/indices/cape_historical.csv",
        "date_fmt": "%Y-%m-%d",
        "pct_fmt": "{pct:+.2f}%",
        "min_value": 50.0,
        "max_abs_daily_pct": 45.0,
    },
    "BPI": {
        "file": "data/indices/panama_historical.csv",
        "date_fmt": "%Y-%m-%d",
        "pct_fmt": "{pct:+.2f}%",
        "min_value": 100.0,
        "max_abs_daily_pct": 35.0,
    },
    "BSI": {
        "file": "data/indices/suprama_historical.csv",
        "date_fmt": "%Y-%m-%d",
        "pct_fmt": "{pct:+.2f}%",
        "min_value": 100.0,
        "max_abs_daily_pct": 30.0,
    },
    "BHSI": {
        "file": "data/indices/handysize_historical.csv",
        "date_fmt": "%Y-%m-%d",
        "pct_fmt": "{pct:+.2f}%",
        "min_value": 50.0,
        "max_abs_daily_pct": 30.0,
    },
    "BDTI": {
        "file": "data/indices/dirtytanker_historical.csv",
        "date_fmt": "%Y-%m-%d",
        "pct_fmt": "{pct:+.2f}%",
        "min_value": 100.0,
        "max_abs_daily_pct": 35.0,
    },
    "BCTI": {
        "file": "data/indices/cleantanker_historical.csv",
        "date_fmt": "%Y-%m-%d",
        "pct_fmt": "{pct:+.2f}%",
        "min_value": 100.0,
        "max_abs_daily_pct": 35.0,
    },
    # 4 Newer Indices (Legacy DD-MM-YYYY date convention)
    "BLNG": {
        "file": "data/indices/blng_historical.csv",
        "date_fmt": "%d-%m-%Y",
        "pct_fmt": "{pct:.2f}",
        "min_value": 100.0,
        "max_abs_daily_pct": 60.0,
    },
    "BLPG": {
        "file": "data/indices/blpg_historical.csv",
        "date_fmt": "%d-%m-%Y",
        "pct_fmt": "{pct:.2f}",
        "min_value": 1.0,
        "max_abs_daily_pct": 60.0,
    },
    "FBX": {
        "file": "data/indices/fbx_historical.csv",
        "date_fmt": "%d-%m-%Y",
        "pct_fmt": "{pct:.2f}",
        "min_value": 100.0,
        "max_abs_daily_pct": 60.0,
    },
    "BAI00": {
        "file": "data/indices/bai_historical.csv",
        "date_fmt": "%d-%m-%Y",
        "pct_fmt": "{pct:.2f}",
        "min_value": 100.0,
        "max_abs_daily_pct": 50.0,
    },
}

# Backwards compatibility mappings
SANITY = {code: {"min_value": cfg["min_value"], "max_abs_daily_pct": cfg["max_abs_daily_pct"]}
          for code, cfg in INDEX_CONFIGS.items()}
NEW_INDICES = {code: cfg["file"] for code, cfg in INDEX_CONFIGS.items()}


for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def parse_any_date(date_str: str) -> datetime:
    """Parse dates robustly whether ISO (YYYY-MM-DD), UK/EU (DD-MM-YYYY), or slash separated."""
    d = date_str.strip()
    if len(d) >= 10:
        prefix = d[:10]
        if prefix[4] == "-" and prefix[7] == "-":
            return datetime.strptime(prefix, "%Y-%m-%d")
        if prefix[2] == "-" and prefix[5] == "-":
            return datetime.strptime(prefix, "%d-%m-%Y")
        if "/" in prefix:
            return datetime.strptime(prefix, "%Y/%m/%d")
    return datetime.fromisoformat(d)


def format_value(value: float) -> str:
    return str(float(value))


def fetch_ticker(retries: int = 4, delay_seconds: int = 5) -> dict[str, dict]:
    """
    Call the Baltic Exchange ticker API and extract structured payloads for all indices.
    """
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            headers = {
                "Accept": "application/json",
                "Origin": "https://www.balticexchange.com",
                "Referer": "https://www.balticexchange.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            }
            resp = requests.get(API_URL, timeout=30, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            result = {}
            for item in data:
                code = (item.get("indexDataSetName") or "").strip()
                current = item.get("current") or {}
                previous = item.get("previous") or {}
                value = current.get("value")
                raw_dt = current.get("indexDate")
                if code and value is not None and raw_dt:
                    dt = datetime.fromisoformat(raw_dt)
                    cfg = INDEX_CONFIGS.get(code, {})
                    date_fmt = cfg.get("date_fmt", "%Y-%m-%d")
                    result[code] = {
                        "value": float(value),
                        "prev_value": float(previous.get("value")) if previous.get("value") is not None else None,
                        "date_str": dt.strftime(date_fmt),
                        "raw_dt": raw_dt,
                        "dt": dt,
                    }
            return result
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                print(f"[retry] API fetch attempt {attempt}/{retries} failed: {exc}")
                time.sleep(delay_seconds * attempt)
    raise RuntimeError(f"API fetch failed after {retries} attempts: {last_error}")


def load_existing_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Index", "% Change"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def upsert_to_csv(path: Path, date_str: str, code: str, value: float) -> str:
    """
    Upsert one row in a historical CSV by date.
    Maintains existing schema and avoids reformatting historical data.
    Returns: added | updated | unchanged | rejected
    """
    cfg = INDEX_CONFIGS.get(code, {})
    min_val = cfg.get("min_value", 1.0)
    max_jump = cfg.get("max_abs_daily_pct", 50.0)
    pct_fmt = cfg.get("pct_fmt", "{pct:.2f}")

    # Positivity / Floor guard
    if value is None or value <= 0 or value < min_val:
        print(f"[xx] {code}: value {value:,.2f} failed positivity/floor guard - NOT WRITTEN")
        return "rejected"

    rows = load_existing_csv(path)
    value_str = format_value(value)

    # 1. Check if date already exists in the file (tail scan)
    for i in range(len(rows) - 1, -1, -1):
        row = rows[i]
        d = (row.get("Date") or row.get("date") or "").strip()
        if d == date_str:
            old_value = float(str(row.get("Index") or 0).replace(",", ""))
            if old_value == value:
                print(f"[--] {code}: {date_str} already in {path.name} with same value - skipped")
                return "unchanged"
            # Guard against erroneous wild intra-day corrections
            if old_value > 0 and (abs(value - old_value) / old_value * 100 > max_jump):
                print(f"[xx] {code}: correction {old_value:,.2f} -> {value:,.2f} exceeds {max_jump:.0f}% guard - NOT WRITTEN")
                return "rejected"
            row["Index"] = value_str
            write_csv(path, rows)
            print(f"[up] {code}: {date_str} corrected to {value:,.2f} -> {path.name}")
            return "updated"

    # 2. Guard against wild jump from prior print
    if rows:
        last_row = rows[-1]
        try:
            prev_val = float(str(last_row.get("Index") or 0).replace(",", ""))
            if prev_val > 0:
                jump = abs(value - prev_val) / prev_val * 100
                if jump > max_jump:
                    print(f"[xx] {code}: new {date_str} {value:,.2f} vs prior {prev_val:,.2f} = {jump:.1f}% exceeds {max_jump:.0f}% guard - NOT WRITTEN")
                    return "rejected"
                pct = ((value - prev_val) / prev_val) * 100
                chg_str = pct_fmt.format(pct=pct)
            else:
                chg_str = ""
        except Exception:
            chg_str = ""
    else:
        chg_str = ""

    # Append new row
    rows.append({
        "Date": date_str,
        "Index": value_str,
        "% Change": chg_str
    })

    # Sort rows by parsed date chronologically
    try:
        rows.sort(key=lambda r: parse_any_date(r.get("Date") or r.get("date") or "1970-01-01"))
    except Exception as e:
        print(f"[!] Warning: Sorting failed for {code}: {e}")

    write_csv(path, rows)
    pct_display = f" ({chg_str})" if chg_str else ""
    print(f"[ok] {code}: {value:,.2f}{pct_display} -> {path.name}")
    return "added"


def validate_local_files(repo_root: Path, ticker: dict[str, dict]) -> tuple[bool, list[str]]:
    problems = []
    for code, cfg in INDEX_CONFIGS.items():
        filename = cfg["file"]
        expected = ticker.get(code)
        if not expected:
            print(f"[!] {code} missing from API payload - validation skipped for this index")
            continue

        rows = load_existing_csv(repo_root / filename)
        if not rows:
            problems.append(f"{code}: local CSV empty")
            continue

        latest = rows[-1]
        latest_date = (latest.get("Date") or latest.get("date") or "").strip()
        latest_value = float(str(latest.get("Index") or 0).replace(",", ""))
        expected_date = expected["date_str"]
        expected_value = expected["value"]

        if latest_date != expected_date:
            problems.append(f"{code}: local latest date {latest_date} != API {expected_date}")
            continue

        if abs(latest_value - expected_value) > 1e-4:
            problems.append(
                f"{code}: local latest value {latest_value:,.2f} != API {expected_value:,.2f} on {expected_date}"
            )

    return (len(problems) == 0, problems)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".", help="Path to Shipping repo root (default: .)")
    parser.add_argument("--validate-only", action="store_true", help="Do not write files, only compare local CSVs to API")
    args = parser.parse_args()
    repo_root = Path(args.repo).resolve()

    print("=" * 60)
    print("  Baltic Comprehensive Indices Scraper & Poller")
    print(f"  Repo: {repo_root}")
    print("=" * 60)

    print(f"\n[..] Fetching {API_URL}")
    try:
        ticker = fetch_ticker()
    except Exception as exc:
        print(f"[x] API fetch failed: {exc}")
        return 1

    print(f"[ok] Got {len(ticker)} indices from API\n")

    for code in INDEX_CONFIGS:
        payload = ticker.get(code)
        if payload:
            print(f"[dbg] {code}: {payload['value']:,.2f} @ {payload['raw_dt']} ({payload['date_str']})")
        else:
            print(f"[dbg] {code}: missing from API payload")

    if not args.validate_only:
        print()
        for code, cfg in INDEX_CONFIGS.items():
            filename = cfg["file"]
            payload = ticker.get(code)
            if not payload:
                print(f"[!] {code} not found in API response - skipped")
                continue
            upsert_to_csv(repo_root / filename, payload["date_str"], code, payload["value"])

    print("\n[..] Validating local CSV tails against API ...")
    ok, problems = validate_local_files(repo_root, ticker)
    if ok:
        print("[ok] All local index files match current Baltic API payload")
        print("\n[done]")
        print(f"Files verified in: {repo_root}")
        return 0

    print("[x] Validation failed:")
    for problem in problems:
        print(f" - {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
