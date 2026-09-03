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


def run(from_year=2011, limit_per_pattern=200, max_snapshots=50, sleep_s=0.5,
        deadline_s=540, max_consec_fail=10):
    t_start = time.monotonic()
    snapshots = []
    seen = set()
    for pat in WCI_WAYBACK_URL_PATTERNS:
        print(f"[+] CDX query: {pat} (from {from_year}, limit {limit_per_pattern})")
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
                    print(f"    [!] {consec_fail} consecutive Wayback failures; aborting "
                          f"with partial {len(collected)} rows (fail-soft).")
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
    from_year, limit_per_pattern, max_snapshots = 2011, 200, 50
    for i, a in enumerate(sys.argv):
        try:
            if a == "--from-year" and i + 1 < len(sys.argv):
                from_year = int(sys.argv[i + 1])
            elif a == "--limit-per-pattern" and i + 1 < len(sys.argv):
                limit_per_pattern = max(1, int(sys.argv[i + 1]))
            elif a == "--max-snapshots" and i + 1 < len(sys.argv):
                max_snapshots = max(1, int(sys.argv[i + 1]))
        except ValueError:
            pass
    run(from_year=from_year, limit_per_pattern=limit_per_pattern,
        max_snapshots=max_snapshots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
