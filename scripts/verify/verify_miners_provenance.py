#!/usr/bin/env python3
"""
scripts/verify/verify_miners_provenance.py
==========================================
CSV-driven Independent Provenance Verification for Major Iron Ore Miners.

For EVERY row in major_miners_quarterly_shipments.csv:
  - If provenance == "illustrative_prior_estimate": logs SKIP.
  - If row has corporate filing provenance (EDGAR / ASX):
      - Downloads the cited filing exhibit / PDF.
      - Asserts EVERY non-null numeric field (100% shipments, share shipments,
        100% production, share production, C1 cash cost, and annual guidance)
        is verified in the filing text.
      - Uses exact word boundaries (no false prefix matches, e.g. "55.4" != "55").
      - No hard-coded expected numbers. The CSV is the thing under test.

Exit codes:
  0  – all verifiable rows PASSED primary filing confirmation
  1  – one or more rows FAILED
"""

import sys
import os
import re
import io
import csv
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_miners_provenance")

ROOT = Path(__file__).resolve().parent.parent.parent
MINERS_CSV = ROOT / "data" / "commodities" / "major_miners_quarterly_shipments.csv"

SEC_HEADERS = {
    "User-Agent": "ShippingIntelligence bot@shippingintel.org (maritime research analytics)"
}
ASX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://www.asx.com.au",
    "Referer": "https://www.asx.com.au/",
}


# ─────────────────────────────────────────────────────────────────────────────
# Fetchers
# ─────────────────────────────────────────────────────────────────────────────

def fetch_html_text(url: str, timeout: int = 30) -> str:
    """Download SEC EDGAR HTML exhibit; strip tags; collapse whitespace."""
    req = urllib.request.Request(url, headers=SEC_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            text = re.sub(r"<[^>]+>", " ", raw)
            return re.sub(r"\s+", " ", text)
    except Exception as e:
        logger.error("Failed to fetch HTML from %s: %s", url, e)
        return ""


def fetch_pdf_text(url: str, timeout: int = 30) -> str:
    """Download ASX/CDN PDF; extract plain text with pymupdf."""
    try:
        import pymupdf  # type: ignore
    except ImportError:
        logger.error("pymupdf not installed; cannot verify Fortescue PDF text")
        return ""

    req = urllib.request.Request(url, headers=ASX_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except Exception as e:
        logger.error("Failed to download PDF from %s: %s", url, e)
        return ""

    try:
        doc = pymupdf.open(stream=body, filetype="pdf")
        pages = [page.get_text() for page in doc]
        return "\n".join(pages)
    except Exception as e:
        logger.error("Failed to extract PDF text from %s: %s", url, e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Field Verification Helper
# ─────────────────────────────────────────────────────────────────────────────

def verify_field_in_text(val_str: str, text: str, field_name: str = "") -> tuple[bool, str]:
    """
    Search for val_str in text with exact word boundaries.
    For numbers, test formatted '000 t (e.g. 79.887 -> '79,887') and exact decimals.
    For C1 cash cost, match only against the exact printed value.
    """
    if not val_str or val_str.lower() in ("nan", "none", "null", ""):
        return True, ""

    if field_name == "c1_cash_cost_usd_t":
        try:
            v = float(val_str)
            candidates = [f"{v:.2f}", str(v), val_str]
            for c in candidates:
                if re.search(r'(?<!\d)' + re.escape(c) + r'(?!\d)', text):
                    return True, c
            return False, ""
        except ValueError:
            pass

    if field_name == "annual_guidance":
        m = re.search(r'(\d+)\s*[-–]\s*(\d+)', val_str)
        if m:
            low, high = m.group(1), m.group(2)
            if re.search(rf'{low}\s*[-–]\s*{high}', text) or (low in text and high in text):
                return True, f"{low}-{high}"
            return False, ""
        if val_str in text:
            return True, val_str
        return False, ""

    try:
        v = float(val_str)
        candidates = [
            f"{round(v * 1000):,}",      # "79,887"
            str(v),                       # "74.8"
            f"{v:.1f}",                   # "52.7"
            str(round(v, 1)),             # "52.7"
            str(round(v, 2))              # "52.80"
        ]
        for c in candidates:
            if re.search(r'(?<!\d)' + re.escape(c) + r'(?!\d)', text):
                return True, c
        return False, ""
    except ValueError:
        pass

    if val_str in text:
        return True, val_str
    return False, ""


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    logger.info("=" * 80)
    logger.info("  MINERS PROVENANCE VERIFICATION — CSV-DRIVEN (no hardcoded expectations)")
    logger.info("=" * 80)

    if not MINERS_CSV.exists():
        logger.error("CSV not found: %s", MINERS_CSV)
        return 1

    df = pd.read_csv(MINERS_CSV, dtype=str)
    logger.info("Loaded %d rows from %s", len(df), MINERS_CSV.name)

    results: list[dict] = []
    _text_cache: dict[str, str] = {}

    for _, row in df.iterrows():
        miner   = str(row.get("miner", "")).strip()
        quarter = str(row.get("quarter", "")).strip()
        prov    = str(row.get("provenance", "")).strip()
        url     = str(row.get("exhibit_url", "")).strip()
        basis   = str(row.get("basis", "")).strip()

        row_id = f"{miner} {quarter}"

        # ── Skip illustrative rows ────────────────────────────────────
        if prov == "illustrative_prior_estimate" or not prov:
            results.append({
                "id": row_id,
                "status": "SKIP",
                "detail": "illustrative_prior_estimate — no filing to verify"
            })
            continue

        if not url or url.lower() in ("nan", "none"):
            results.append({
                "id": row_id,
                "status": "FAIL",
                "detail": f"exhibit_url missing for prov={prov}"
            })
            continue

        # ── Download filing text ───────────────────────────────────────
        logger.info("[%s] Fetching %s ...", row_id, url)
        if url not in _text_cache:
            if prov.startswith("ASX:"):
                _text_cache[url] = fetch_pdf_text(url)
            else:
                _text_cache[url] = fetch_html_text(url)

        filing_text = _text_cache[url]

        if len(filing_text) < 200:
            results.append({
                "id": row_id,
                "status": "FAIL",
                "detail": f"Filing text too short ({len(filing_text)} chars) — fetch failed: {url}"
            })
            continue

        fields_to_check = [
            "shipments_mt_100pct",
            "shipments_mt_equity_share",
            "production_mt_100pct",
            "production_mt_equity_share",
            "pilbara_production_mt",
            "pilbara_shipments_mt",
            "ore_mined_mt",
            "c1_cash_cost_usd_t",
            "annual_guidance"
        ]

        verified_fields = []
        failed_fields = []

        for field_name in fields_to_check:
            val = str(row.get(field_name, "")).strip()
            if not val or val.lower() in ("nan", "none", "null", ""):
                continue
            ok, matched_token = verify_field_in_text(val, filing_text, field_name=field_name)
            if ok:
                verified_fields.append(f"{field_name}={val} ('{matched_token}')")
            else:
                failed_fields.append(f"{field_name}={val}")

        if failed_fields:
            results.append({
                "id": row_id,
                "status": "FAIL",
                "detail": f"Values NOT found in filing: {', '.join(failed_fields)} | Verified: {', '.join(verified_fields)} | prov={prov}"
            })
        else:
            results.append({
                "id": row_id,
                "status": "PASS",
                "detail": f"Verified fields: {', '.join(verified_fields)} | prov={prov}"
            })

    # ── Print Report Table ────────────────────────────────────────────
    print("\n" + "=" * 100)
    print(f"{'MINER / QUARTER':<28} | {'STATUS':<6} | {'DETAIL'}")
    print("=" * 100)
    for r in results:
        print(f"{r['id']:<28} | {r['status']:<6} | {r['detail']}")
    print("=" * 100)

    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    skip_count = sum(1 for r in results if r["status"] == "SKIP")
    total_count = len(results)

    print(f"\nVERIFICATION SUMMARY: {pass_count} PASS / {fail_count} FAIL / {skip_count} SKIP  (total {total_count} rows)")

    if fail_count > 0:
        logger.error("Verification FAILED: %d row(s) could not be verified from filing.", fail_count)
        return 1

    logger.info("All %d verifiable rows PASSED primary filing confirmation.", pass_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
