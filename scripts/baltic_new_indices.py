"""
Baltic Exchange - New Indices Scraper
=====================================
Fetches BLNG, BLPG, FBX, and BAI00 from the Baltic Exchange public ticker API
  https://blacksun-api.balticexchange.com/api/ticker
and upserts them into historical CSVs.

Each series is updated against its own published indexDate from the API, so
mixed publication schedules are handled correctly. The script also validates
that local CSV tails match the latest API payload after every run.

Output schema (matches existing repo CSVs):
  Date (DD-MM-YYYY), Index, % Change

Usage:
  pip install requests
  python baltic_new_indices.py --repo /path/to/Shipping
  python baltic_new_indices.py --repo /path/to/Shipping --validate-only
"""

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


API_URL = "https://blacksun-api.balticexchange.com/api/ticker"
DATE_FMT = "%d-%m-%Y"

# Indices to record, keyed by indexDataSetName from the API
NEW_INDICES = {
    "BLNG": "blng_historical.csv",
    "BLPG": "blpg_historical.csv",
    "FBX": "fbx_historical.csv",
    "BAI00": "bai_historical.csv",
}


for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, DATE_FMT)


def format_value(value: float) -> str:
    return str(float(value))


def fetch_ticker(retries: int = 4, delay_seconds: int = 5) -> dict[str, dict]:
    """
    Call the Baltic Exchange ticker API.
    Returns:
      {
        "BLNG": {
          "value": 9020.0,
          "date_str": "08-04-2026",
          "raw_dt": "2026-04-08T10:54:56",
        },
        ...
      }
    """
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(API_URL, timeout=30, headers={"Accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()

            result = {}
            for item in data:
                code = (item.get("indexDataSetName") or "").strip()
                current = item.get("current") or {}
                value = current.get("value")
                raw_dt = current.get("indexDate")
                if code and value is not None and raw_dt:
                    date_str = datetime.fromisoformat(raw_dt).strftime(DATE_FMT)
                    result[code] = {
                        "value": float(value),
                        "date_str": date_str,
                        "raw_dt": raw_dt,
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


def compute_change(new_val: float, prev_val: float | None) -> str:
    if prev_val is None or prev_val == 0:
        return ""
    pct = (new_val - prev_val) / prev_val * 100
    return f"{pct:.2f}"


def normalize_rows(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        date_str = (row.get("Date") or row.get("date") or "").strip()
        index_str = str(row.get("Index", row.get("index", ""))).strip()
        change_str = str(row.get("% Change", row.get("% change", row.get("change", "")))).strip()
        if not date_str or not index_str:
            continue
        try:
            parse_date(date_str)
            float(index_str.replace(",", ""))
        except (ValueError, TypeError):
            continue
        normalized.append({
            "Date": date_str,
            "Index": format_value(float(index_str.replace(",", ""))),
            "% Change": change_str,
        })
    normalized.sort(key=lambda row: parse_date(row["Date"]))
    return normalized


def recompute_changes(rows: list[dict]) -> list[dict]:
    rows = normalize_rows(rows)
    prev_val = None
    for row in rows:
        current_val = float(row["Index"])
        row["% Change"] = compute_change(current_val, prev_val)
        prev_val = current_val
    return rows


def upsert_to_csv(path: Path, date_str: str, code: str, value: float) -> str:
    """
    Upsert one row in a historical CSV by date and recompute dependent % changes.
    Returns: added | updated | unchanged
    """
    rows = normalize_rows(load_existing_csv(path))
    value_str = format_value(value)

    for row in rows:
        if row["Date"] != date_str:
            continue
        old_value = float(row["Index"])
        if old_value == value:
            print(f"[--] {code}: {date_str} already in {path.name} with same value - skipped")
            return "unchanged"
        row["Index"] = value_str
        rows = recompute_changes(rows)
        write_csv(path, rows)
        print(f"[up] {code}: {date_str} corrected to {value:,.2f} -> {path.name}")
        return "updated"

    rows.append({"Date": date_str, "Index": value_str, "% Change": ""})
    rows = recompute_changes(rows)
    write_csv(path, rows)
    change = rows[-1]["% Change"]
    pct_str = f" ({'+' if change and float(change) > 0 else ''}{change}%)" if change else ""
    print(f"[ok] {code}: {value:,.2f}{pct_str} -> {path.name}")
    return "added"


def validate_local_files(repo_root: Path, ticker: dict[str, dict]) -> tuple[bool, list[str]]:
    problems = []
    for code, filename in NEW_INDICES.items():
        expected = ticker.get(code)
        if not expected:
            problems.append(f"{code}: missing from API payload")
            continue

        rows = normalize_rows(load_existing_csv(repo_root / filename))
        if not rows:
            problems.append(f"{code}: local CSV empty")
            continue

        latest = rows[-1]
        latest_date = latest["Date"]
        latest_value = float(latest["Index"])
        expected_date = expected["date_str"]
        expected_value = expected["value"]

        if latest_date != expected_date:
            problems.append(f"{code}: local latest date {latest_date} != API {expected_date}")
            continue

        if abs(latest_value - expected_value) > 1e-9:
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
    print("  Baltic New Indices Scraper")
    print(f"  Repo: {repo_root}")
    print("=" * 60)

    print(f"\n[..] Fetching {API_URL}")
    try:
        ticker = fetch_ticker()
    except Exception as exc:
        print(f"[x] API fetch failed: {exc}")
        return 1

    print(f"[ok] Got {len(ticker)} indices from API\n")

    for code in NEW_INDICES:
        payload = ticker.get(code)
        if payload:
            print(f"[dbg] {code}: {payload['value']:,.2f} @ {payload['raw_dt']}")
        else:
            print(f"[dbg] {code}: missing from API payload")

    if not args.validate_only:
        print()
        for code, filename in NEW_INDICES.items():
            payload = ticker.get(code)
            if not payload:
                print(f"[!] {code} not found in API response - skipped")
                continue
            upsert_to_csv(repo_root / filename, payload["date_str"], code, payload["value"])

    print("\n[..] Validating local CSV tails against API ...")
    ok, problems = validate_local_files(repo_root, ticker)
    if ok:
        print("[ok] Local files match current API payload")
        print("\n[done]")
        print(f"Files verified in: {repo_root}")
        return 0

    print("[x] Validation failed:")
    for problem in problems:
        print(f" - {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
