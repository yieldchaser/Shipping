#!/usr/bin/env python3
"""
UN Comtrade Shared API Client & Strict Total Row Selector
=========================================================
Implements the definitive UN Comtrade monthly preview API harvester with strict
total row selection rules per Prompt 13B §C4:
- Invariant: the authoritative national/bilateral total row is uniquely identified by:
    motCode == 0 (all modes of transport)
    customsCode == "C00" (standard customs regime)
    partner2Code == 0 (total / direct partner)
- Zero or multiple matches will raise ValueError loudly (no silent fallback).
- Persists raw API JSON payloads to disk for deterministic re-derivation and audit tests.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RAW_CACHE_DIR = REPO_ROOT / "data" / "commodities" / ".cache_comtrade_raw"
DEFAULT_RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"

SKIPPED_QUERIES_FILE = REPO_ROOT / "data" / "commodities" / "_skipped_queries.json"


def record_skipped_query(script: str, period: str, commodity: str, reason: str):
    """Prompt 13C §D5: Record failed, skipped, or refused queries into sidecar."""
    SKIPPED_QUERIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    records = []
    if SKIPPED_QUERIES_FILE.exists():
        try:
            with open(SKIPPED_QUERIES_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []

    # Deduplicate by (script, period, commodity)
    existing = next((r for r in records if r.get("script") == script and r.get("period") == period and r.get("commodity") == commodity), None)
    entry = {
        "script": script,
        "period": period,
        "commodity": commodity,
        "reason": reason,
        "logged_at_utc": datetime.now(timezone.utc).isoformat()
    }
    if existing:
        existing.update(entry)
    else:
        records.append(entry)

    with open(SKIPPED_QUERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)



def select_total(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Select the unique total row matching motCode==0, customsCode=='C00', partner2Code==0.

    Raises:
        ValueError: if zero matches or more than one match is found (F2 prevention).
    """
    if not rows:
        raise ValueError("Cannot select total from empty row set")

    matches = [
        r for r in rows
        if r.get("motCode") == 0 and r.get("customsCode") == "C00" and r.get("partner2Code") == 0
    ]

    if len(matches) == 0:
        raise ValueError(
            f"No unique total row found matching motCode=0, customsCode='C00', partner2Code=0 across {len(rows)} candidates. "
            f"Available customs/mot combinations: {set((r.get('motCode'), r.get('customsCode'), r.get('partner2Code')) for r in rows)}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous total: found {len(matches)} rows matching motCode=0, customsCode='C00', partner2Code=0 across {len(rows)} candidates."
        )

    return matches[0]


def fetch_comtrade_monthly(
    reporter_code: str,
    partner_code: str,
    cmd_code: str,
    flow_code: str,
    period: str,
    raw_cache_dir: Optional[Path] = None,
    max_retries: int = 4,
    sleep_delay: float = 0.35,
    fallback_mode_sum: bool = False,
) -> Optional[Dict[str, Any]]:
    """Fetch monthly HS trade flow record from UN Comtrade with persistent raw caching."""
    cache_dir = raw_cache_dir or DEFAULT_RAW_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    query_id = f"comtrade_{reporter_code}_{partner_code}_{cmd_code}_{flow_code}_{period}"
    cache_path = cache_dir / f"{query_id}.json"

    raw_data: List[Dict[str, Any]] = []

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_obj = json.load(f)
                raw_data = cached_obj.get("data", [])
        except Exception as e:
            logging.warning("Failed reading raw cache %s: %s", cache_path.name, e)
            raw_data = []

    url = (
        f"{BASE_URL}"
        f"?reporterCode={reporter_code}"
        f"&partnerCode={partner_code}"
        f"&cmdCode={cmd_code}"
        f"&flowCode={flow_code}"
        f"&period={period}"
    )

    if not raw_data:
        for attempt in range(1, max_retries + 1):
            try:
                time.sleep(sleep_delay)
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code == 200:
                    resp_json = r.json()
                    raw_data = resp_json.get("data", [])
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump({"query_url": url, "fetched_utc": datetime.now(timezone.utc).isoformat(), "data": raw_data}, f, indent=2)
                    break
                elif r.status_code == 429:
                    wait_s = min(2 ** attempt * 1.5, 30.0)
                    logging.warning("Comtrade 429 on %s (attempt %d/%d); backing off %.1fs", url, attempt, max_retries, wait_s)
                    time.sleep(wait_s)
                    continue
                elif r.status_code in (400, 404):
                    logging.info("Comtrade returned HTTP %d for %s", r.status_code, url)
                    return None
                else:
                    logging.warning("Comtrade HTTP %d on %s", r.status_code, url)
            except Exception as e:
                logging.warning("Comtrade request error on %s: %s (attempt %d/%d)", url, e, attempt, max_retries)
                time.sleep(2.0)
        else:
            logging.error("Comtrade gave up on %s after %d retries", url, max_retries)
            return None

    if not raw_data:
        return None

    try:
        total_row = select_total(raw_data)
    except ValueError as e:
        logging.warning("select_total failed for %s period %s: %s", cmd_code, period, e)
        return None

    wgt_kg = float(total_row.get("netWgt") or total_row.get("qty") or 0.0)
    val_usd = float(total_row.get("primaryValue") or 0.0)
    is_mode_sum = False

    # Prompt 13C §D5: If total netWgt/qty is null or 0, check if mode rows exist to fill via mode sum
    if wgt_kg <= 0 and fallback_mode_sum:
        mode_rows = [
            r for r in raw_data
            if (r.get("motCode") or 0) > 0 and r.get("customsCode") == "C00" and r.get("partner2Code") == 0
        ]
        sum_mode_wgt = sum(float(r.get("netWgt") or r.get("qty") or 0.0) for r in mode_rows)
        if sum_mode_wgt > 0:
            wgt_kg = sum_mode_wgt
            is_mode_sum = True
            logging.info("Filled null total row with mode sum: %.1f kg across %d mode rows for %s %s", wgt_kg, len(mode_rows), cmd_code, period)

    return {
        "is_mode_sum": is_mode_sum,
        "period": period,
        "date": f"{period[:4]}-{period[4:6]}-01",
        "reporter_code": str(reporter_code),
        "partner_code": str(partner_code),
        "cmd_code": str(cmd_code),
        "flow_code": str(flow_code),
        "netWgt_kg": wgt_kg,
        "metric_tonnes": round(wgt_kg / 1000.0, 2),
        "value_usd": round(val_usd, 2),
        "source_url": url,
        "raw_record": total_row,
    }
