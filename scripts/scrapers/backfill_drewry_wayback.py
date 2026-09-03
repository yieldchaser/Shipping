"""
Drewry WCI Wayback backfill (Build F).

Idempotent historical extension for data/indices/drewry_wci_historical.csv:
- Queries the Wayback CDX API for drewry.co.uk WCI pages, 2011 -> present.
- Parses each snapshot with fetch_drewry_wci.extract_assessments().
- Writes the raw assessed rows to a /tmp candidate CSV first, then upserts
  (dedup by date, sort, canonical header) into the repo CSV.
- NEVER invents values: only Drewry-assessed snapshots are kept. Missing
  weeks stay absent; the frontend renders them as gaps (spanGaps:true).

Usage:
    python scripts/scrapers/backfill_drewry_wayback.py [--from-year 2011]
"""

import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_drewry_wci import (  # noqa: E402
    CSV_COLUMNS,
    WCI_WAYBACK_URL_PATTERNS,
    extract_assessments,
    fetch_wayback_cdx,
    get_with_backoff,
    upsert_wci_rows,
)

DATA_DIR = REPO_ROOT / "data" / "indices"
TARGET_CSV = DATA_DIR / "drewry_wci_historical.csv"


def candidate_path():
    # Task asks for a /tmp candidate; use the OS temp dir cross-platform
    # (on Linux this IS /tmp; on Windows it is %TEMP%).
    tmp = Path(tempfile.gettempdir())
    try:
        tmp.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return tmp / "drewry_wci_wayback_candidate.csv"


def run(from_year=2011, limit_per_pattern=1500, max_snapshots=400, sleep_s=1.0):
    snapshots = []
    seen = set()
    for pat in WCI_WAYBACK_URL_PATTERNS:
        print(f"[+] CDX query: {pat} (from {from_year})")
        rows = fetch_wayback_cdx(pat, from_year=from_year, limit=limit_per_pattern)
        print(f"    found {len(rows)} snapshots")
        for r in rows:
            key = (r.get("timestamp"), r.get("digest") or r.get("original"))
            if key in seen:
                continue
            seen.add(key)
            snapshots.append(r)
    snapshots.sort(key=lambda r: r.get("timestamp", ""))
    if len(snapshots) > max_snapshots:
        step = len(snapshots) / max_snapshots
        snapshots = [snapshots[int(i * step)] for i in range(max_snapshots)]
        print(f"    thinned to {len(snapshots)} snapshots across 2011->present")

    collected = []
    for snap in snapshots:
        ts = snap.get("timestamp", "")
        orig = snap.get("original", "")
        wb_url = f"https://web.archive.org/web/{ts}id_/{orig}"
        try:
            resp = get_with_backoff(wb_url, attempts=2)
            if not resp:
                continue
            values, page_date, _ = extract_assessments(resp.text)
            if not values.get("composite_index") and len(values) < 2:
                continue
            row = {col: values.get(col) for col in CSV_COLUMNS}
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
            continue
        finally:
            if sleep_s:
                time.sleep(sleep_s)

    print(f"[+] Parsed {len(collected)} assessed snapshots (no synthesis).")

    cand = candidate_path()
    cand_df = pd.DataFrame(collected, columns=CSV_COLUMNS) if collected else pd.DataFrame(columns=CSV_COLUMNS)
    cand_df.to_csv(cand, index=False)
    print(f"[OK] Candidate written: {cand} ({len(cand_df)} rows)")

    if len(cand_df):
        out = upsert_wci_rows(cand_df)
        print(f"[OK] Upserted + deduped + sorted -> {out.relative_to(REPO_ROOT)}")
    else:
        print("[!] No assessed rows recovered; target CSV left unchanged.")
    return cand, len(cand_df)


def main():
    from_year = 2011
    for i, a in enumerate(sys.argv):
        if a == "--from-year" and i + 1 < len(sys.argv):
            try:
                from_year = int(sys.argv[i + 1])
            except ValueError:
                pass
    run(from_year=from_year)
    return 0


if __name__ == "__main__":
    sys.exit(main())
