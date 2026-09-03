"""
Standalone Drewry World Container Index (WCI) Tracker Scraper.
Extracts the composite index and route-by-route spot assessments from
Drewry's public WCI pages, maintains a clean time-series CSV, and saves
the weekly narrative snapshot as Markdown.

Only uses requests, beautifulsoup4 and pandas (per implementation plan).
"""

import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "indices"
REPORTS_DIR = REPO_ROOT / "reports" / "drewry"
CHECKPOINT_FILE = REPO_ROOT / "data" / "derived" / "drewry_checkpoint.json"

WCI_PAGE_URLS = [
    "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry",
    "https://www.drewry.co.uk/trackers-and-indices/latest-trackers-and-indices",
]
RED_SEA_URL = "https://www.drewry.co.uk/red-sea-freight-tracker"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CSV_COLUMNS = [
    "date",
    "composite_index",
    "shanghai_rotterdam",
    "shanghai_genoa",
    "shanghai_la",
    "shanghai_ny",
    "rotterdam_shanghai",
]

# Route label variants seen across Drewry pages/articles -> CSV column
ROUTE_PATTERNS = [
    (r"shanghai\s*[-\u2013\u2014to]+\s*rotterdam", "shanghai_rotterdam"),
    (r"shanghai\s*[-\u2013\u2014to]+\s*genoa", "shanghai_genoa"),
    (r"shanghai\s*[-\u2013\u2014to]+\s*los\s*angeles", "shanghai_la"),
    (r"shanghai\s*[-\u2013\u2014to]+\s*new\s*york", "shanghai_ny"),
    (r"rotterdam\s*[-\u2013\u2014to]+\s*shanghai", "rotterdam_shanghai"),
]
COMPOSITE_PAT = re.compile(
    r"(?:world\s*container\s*index|wci|composite\s*index)[^.]{0,120}?"
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:per|/)?\s*(?:40\s*(?:ft|foot)|40')",
    re.I,
)
ROUTE_VALUE_PAT = re.compile(
    r"([a-z][a-z\s]*?)\s*[-\u2013\u2014to]+\s*([a-z][a-z\s]*?)\D{0,60}?"
    r"\$\s*([\d,]+(?:\.\d+)?)",
    re.I,
)


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_checkpoint(cp):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps(cp, indent=2), encoding="utf-8")


def get_with_backoff(url, attempts=3):
    delay = 2.0
    last_exc = None
    for _ in range(attempts):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                time.sleep(delay)
                delay *= 2
                continue
            print(f"    [!] HTTP {resp.status_code} for {url}")
            return None
        except Exception as exc:
            last_exc = exc
            time.sleep(delay)
            delay *= 2
    if last_exc:
        print(f"    [!] Failed {url}: {last_exc}")
    return None


def clean_number(raw):
    try:
        return float(re.sub(r"[^0-9.]", "", raw))
    except Exception:
        return None


def extract_assessments(html_text):
    """Pull composite + route values from tables and free text."""
    soup = BeautifulSoup(html_text, "html.parser")
    flat_text = soup.get_text(" \n", strip=True)

    values = {}

    m = COMPOSITE_PAT.search(flat_text)
    if m:
        val = clean_number(m.group(1))
        if val:
            values["composite_index"] = val

    # Route values from rendered tables first (label cell next to $ cell)
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            row_text = " | ".join(cells)
            for pat, col in ROUTE_PATTERNS:
                if col in values:
                    continue
                rm = re.search(pat, row_text, re.I)
                if not rm:
                    continue
                vm = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", row_text)
                if vm:
                    val = clean_number(vm.group(1))
                    if val:
                        values[col] = val

    # Free-text fallback for routes missing from tables
    if len(values) < len(CSV_COLUMNS):
        for line in flat_text.splitlines():
            line_low = line.lower()
            for pat, col in ROUTE_PATTERNS:
                if col in values:
                    continue
                if re.search(pat, line_low):
                    vm = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", line)
                    if vm:
                        val = clean_number(vm.group(1))
                        if val:
                            values[col] = val

    # As-of date on the page
    page_date = None
    dm = re.search(
        r"(?:as\s*of|published|assessment\s*date|dated)[:\s]*([A-Za-z]+ \d{1,2},? \d{4})",
        flat_text,
        re.I,
    ) or re.search(r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", flat_text)
    if dm:
        for fmt in ("%B %d, %Y", "%B %d %Y", "%d %B %Y"):
            try:
                page_date = datetime.strptime(dm.group(1).replace(",", ""), fmt.replace(",", "")).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
    if not page_date:
        page_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return values, page_date, flat_text


WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
# WCI pages to look up in the Wayback CDX index (2011 -> present).
WCI_WAYBACK_URL_PATTERNS = [
    "drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry*",
    "drewry.co.uk/*world-container-index*",
    "drewry.co.uk/*container-index*",
]

# Build F: synthetic baseline removed. This stub is kept only for backward
# compatibility with older imports; it NEVER synthesizes values.
def generate_canonical_wci_history():
    print("    [!] generate_canonical_wci_history() is deprecated (Build F): no values synthesized.")
    return pd.DataFrame(columns=CSV_COLUMNS)


def fetch_wayback_cdx(url_pattern, from_year=2011, limit=200):
    """Query the Wayback CDX API for snapshot list. Returns list of dicts.

    Fail-soft: per-request timeout 30s, max 3 attempts with backoff.
    Returns [] on persistent archive.org errors (e.g. GitHub Actions IP
    throttling) so the caller can commit partial results instead of wedging.
    """
    params = {
        "url": url_pattern,
        "from": str(from_year),
        "output": "json",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "fl": "timestamp,original,statuscode,digest",
        "collapse": "digest",
        "limit": str(limit),
    }
    delay = 2.0
    for attempt in range(1, 4):
        try:
            resp = requests.get(WAYBACK_CDX_URL, params=params, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as exc:
                    print(f"    [!] CDX JSON decode failed for {url_pattern}: {exc}")
                    return []
                if not data or len(data) < 2:
                    return []
                header, rows = data[0], data[1:]
                return [dict(zip(header, r)) for r in rows]
            if resp.status_code in (429, 503):
                print(f"    [!] CDX HTTP {resp.status_code} for {url_pattern} (attempt {attempt}/3)")
            else:
                print(f"    [!] CDX HTTP {resp.status_code} for {url_pattern}")
                return []
        except Exception as exc:
            print(f"    [!] CDX query failed for {url_pattern} (attempt {attempt}/3): {exc}")
        if attempt < 3:
            time.sleep(delay)
            delay *= 2
    return []


def backfill_drewry_wayback(from_year=2011, limit_per_pattern=200, max_snapshots=50, sleep_s=0.5,
                            deadline_s=540, max_consec_fail=10):
    """Backfill assessed WCI history via the Wayback Machine CDX API.

    - Covers drewry.co.uk WCI pages from from_year -> present.
    - Bounds work: newest max_snapshots only (default 50), per-request
      timeout 30s via get_with_backoff(), max 3 attempts with backoff,
      overall deadline_s budget + consecutive-failure circuit breaker so
      archive.org throttling (ConnectTimeout / Connection refused on
      GitHub Actions IPs) fails soft instead of wedging the job.
    - Parses each snapshot with extract_assessments(); only real assessed
      values are kept. Missing weeks are left absent (frontend renders gaps
      with spanGaps:true); values are NEVER invented.
    - Upserts into data/indices/drewry_wci_historical.csv with dedup + sort,
      preserving the canonical header (date, composite_index, ...).
    - Idempotent: re-running yields the same sorted, deduped CSV.
    - Fail-soft: returns partial (csv_path, n) on timeout/circuit-break;
      never raises on Wayback errors.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "drewry_wci_historical.csv"
    t_start = time.monotonic()

    snapshots = []
    seen_ts = set()
    for pat in WCI_WAYBACK_URL_PATTERNS:
        print(f"[+] CDX query: {pat} (from {from_year}, limit {limit_per_pattern})")
        rows = fetch_wayback_cdx(pat, from_year=from_year, limit=limit_per_pattern)
        print(f"    found {len(rows)} snapshots")
        for r in rows:
            key = (r.get("timestamp"), r.get("digest") or r.get("original"))
            if key in seen_ts:
                continue
            seen_ts.add(key)
            snapshots.append(r)
    snapshots.sort(key=lambda r: r.get("timestamp", ""))
    if len(snapshots) > max_snapshots:
        # Keep newest snapshots: bounds runtime and prefers recent assessed
        # prints over deep-history (e.g. flaky 2022 snapshots).
        snapshots = snapshots[-max_snapshots:]
        print(f"    capped to newest {len(snapshots)} snapshots")

    collected = []
    consec_fail = 0
    for idx, snap in enumerate(snapshots, 1):
        if time.monotonic() - t_start > deadline_s:
            print(f"    [!] Wayback deadline ({deadline_s}s) reached at {idx}/{len(snapshots)}; "
                  f"keeping partial {len(collected)} rows (fail-soft).")
            break
        ts = snap.get("timestamp", "")
        orig = snap.get("original", "")
        wb_url = f"https://web.archive.org/web/{ts}id_/{orig}"
        try:
            resp = get_with_backoff(wb_url, attempts=3)
            if not resp:
                consec_fail += 1
                if consec_fail >= max_consec_fail:
                    print(f"    [!] {consec_fail} consecutive Wayback failures; archive.org likely "
                          f"throttling this IP. Aborting with partial {len(collected)} rows (fail-soft).")
                    break
                continue
            values, page_date, _ = extract_assessments(resp.text)
            if not values.get("composite_index") and len(values) < 2:
                consec_fail += 1
                if consec_fail >= max_consec_fail:
                    print(f"    [!] {consec_fail} consecutive unparseable snapshots; aborting "
                          f"with partial {len(collected)} rows (fail-soft).")
                    break
                continue
            consec_fail = 0
            row = {col: values.get(col) for col in CSV_COLUMNS}
            # Prefer the assessed page date; fall back to snapshot date.
            if page_date:
                row["date"] = page_date
            else:
                try:
                    row["date"] = datetime.strptime(ts[:8], "%Y%m%d").strftime("%Y-%m-%d")
                except Exception:
                    continue
            collected.append(row)
        except Exception as exc:
            print(f"    [!] snapshot parse failed {wb_url}: {exc}")
            consec_fail += 1
            if consec_fail >= max_consec_fail:
                print(f"    [!] circuit-breaker tripped; keeping partial {len(collected)} rows.")
                break
            continue
        finally:
            if sleep_s:
                time.sleep(sleep_s)

    print(f"[+] Wayback: parsed {len(collected)} assessed snapshots")
    if not collected:
        print("[!] No assessed WCI values recovered from Wayback; CSV left unchanged.")
        return csv_path, 0

    new_df = pd.DataFrame(collected)
    csv_path = upsert_wci_rows(new_df)
    return csv_path, len(collected)


def upsert_wci_rows(new_df):
    """Idempotent upsert: merge new rows, dedup by date (last wins), sort, keep header."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "drewry_wci_historical.csv"
    if csv_path.exists():
        try:
            existing = pd.read_csv(csv_path)
        except Exception:
            existing = pd.DataFrame(columns=CSV_COLUMNS)
    else:
        existing = pd.DataFrame(columns=CSV_COLUMNS)
    combined = pd.concat([existing, new_df], ignore_index=True) if len(new_df) else existing
    # Keep only canonical columns (extra keys dropped), preserve header order.
    for col in CSV_COLUMNS:
        if col not in combined.columns:
            combined[col] = None
    combined = combined[CSV_COLUMNS]
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined = combined.dropna(subset=["date"]).drop_duplicates(subset="date", keep="last").sort_values("date")
    combined.to_csv(csv_path, index=False)
    return csv_path


def update_csv(row=None, extra_df=None):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "drewry_wci_historical.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            df = pd.DataFrame(columns=CSV_COLUMNS)
    else:
        df = pd.DataFrame(columns=CSV_COLUMNS)

    frames = [df]
    if row and row.get("date"):
        frames.append(pd.DataFrame([row]))
    if extra_df is not None and len(extra_df):
        frames.append(extra_df)
    if len(frames) > 1:
        df = pd.concat(frames, ignore_index=True)

    return upsert_wci_rows(df) if len(df) else upsert_wci_rows(pd.DataFrame(columns=CSV_COLUMNS))


def _parse_backfill_args(argv):
    """Parse optional backfill bounds. Defaults keep weekly runs bounded."""
    from_year, limit_per_pattern, max_snapshots = 2011, 200, 50
    for i, a in enumerate(argv):
        try:
            if a == "--from-year" and i + 1 < len(argv):
                from_year = int(argv[i + 1])
            elif a == "--limit-per-pattern" and i + 1 < len(argv):
                limit_per_pattern = max(1, int(argv[i + 1]))
            elif a == "--max-snapshots" and i + 1 < len(argv):
                max_snapshots = max(1, int(argv[i + 1]))
        except ValueError:
            continue
    return from_year, limit_per_pattern, max_snapshots


def main():
    print("=" * 80)
    print("  DREWRY WORLD CONTAINER INDEX INGESTION")
    print("=" * 80)

    if "--backfill" in sys.argv:
        from_year, limit_per_pattern, max_snapshots = _parse_backfill_args(sys.argv)
        print(f"\n[+] Wayback backfill requested (--backfill): {from_year} -> present, "
              f"newest {max_snapshots} (limit {limit_per_pattern}/pattern), no synthesis.")
        try:
            csv_path, n = backfill_drewry_wayback(
                from_year=from_year, limit_per_pattern=limit_per_pattern,
                max_snapshots=max_snapshots)
        except Exception as exc:
            print(f"    [!] Wayback backfill failed (fail-soft): {exc}")
            csv_path = upsert_wci_rows(pd.DataFrame(columns=CSV_COLUMNS))
            n = 0
        print(f"\n[OK] Wayback backfill complete: {n} assessed snapshots -> {csv_path.relative_to(REPO_ROOT)}")
        return 0

    checkpoint = load_checkpoint()
    primary = None
    narrative = ""
    for url in WCI_PAGE_URLS:
        print(f"\n[+] Fetching {url}")
        resp = get_with_backoff(url)
        if not resp:
            continue
        values, page_date, flat_text = extract_assessments(resp.text)
        print(f"    parsed values: {values} (page date: {page_date})")
        if values.get("composite_index") or len(values) >= 2:
            primary = {"url": url, "values": values, "date": page_date}
            narrative = "\n".join(
                line.strip() for line in flat_text.splitlines()
                if re.search(r"wci|container index|\$[\d,]+|red sea", line, re.I) and len(line.strip()) > 25
            )[:6000]
            break

    if not primary:
        print("\n[!] Live WCI page JS-rendered or offline; attempting limited Wayback backfill (no synthesis).")
        print("    Missing weeks are left as gaps (frontend spanGaps:true); no values invented.")
        try:
            # Fail-soft fallback: bounded (newest 50) so a blocked archive.org
            # never wedges the weekly job; partial results are committed.
            csv_path, n = backfill_drewry_wayback(
                limit_per_pattern=200, max_snapshots=50, sleep_s=0.5)
            print(f"\n[OK] Time-series backfilled: {csv_path.relative_to(REPO_ROOT)} ({n} assessed snapshots)")
        except Exception as exc:
            print(f"    [!] Wayback backfill failed: {exc}; ensuring header-only CSV exists.")
            csv_path = upsert_wci_rows(pd.DataFrame(columns=CSV_COLUMNS))
            print(f"\n[OK] Time-series preserved: {csv_path.relative_to(REPO_ROOT)}")
        return 0

    row = {col: primary["values"].get(col) for col in CSV_COLUMNS}
    row["date"] = primary["date"]
    csv_path = update_csv(row)
    print(f"\n[OK] Time-series updated: {csv_path.relative_to(REPO_ROOT)}")

    year_dir = REPORTS_DIR / primary["date"][:4]
    year_dir.mkdir(parents=True, exist_ok=True)
    md_path = year_dir / f"{primary['date']}_drewry_wci.md"
    md_content = f"""---
title: "Drewry World Container Index Snapshot - {primary['date']}"
date: "{primary['date']}"
source: "drewry"
category: "containers"
source_url: "{primary['url']}"
---

# Drewry World Container Index Snapshot - {primary['date']}

## Assessed Values ($/40ft)

| Metric | Value |
| --- | --- |
""" + "\n".join(
        f"| {col} | {primary['values'].get(col, '')} |" for col in CSV_COLUMNS[1:] if col != "date"
    ) + f"""

## Page Commentary

{narrative}
"""
    md_path.write_text(md_content, encoding="utf-8", errors="ignore")
    print(f"[OK] Narrative saved: {md_path.relative_to(REPO_ROOT)}")

    checkpoint["last_success_date"] = primary["date"]
    checkpoint["last_values"] = primary["values"]
    save_checkpoint(checkpoint)

    # Red Sea tracker narrative (best effort, never fatal)
    resp = get_with_backoff(RED_SEA_URL)
    if resp:
        rs_soup = BeautifulSoup(resp.text, "html.parser")
        rs_text = rs_soup.get_text("\n", strip=True)
        rs_lines = [
            line.strip() for line in rs_text.splitlines()
            if re.search(r"suez|transit|cape of good hope|diversion|red sea", line, re.I) and len(line.strip()) > 30
        ][:60]
        if rs_lines:
            rs_path = year_dir / f"{primary['date']}_drewry_red_sea_tracker.md"
            rs_path.write_text(
                f"""---
title: "Drewry Red Sea Freight Tracker Notes - {primary['date']}"
date: "{primary['date']}"
source: "drewry"
category: "containers"
source_url: "{RED_SEA_URL}"
---

# Drewry Red Sea Freight Tracker Notes - {primary['date']}

""" + "\n\n".join(rs_lines),
                encoding="utf-8",
                errors="ignore",
            )
            print(f"[OK] Red Sea notes saved: {rs_path.relative_to(REPO_ROOT)}")

    print("\n[DONE] Drewry ingestion complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
