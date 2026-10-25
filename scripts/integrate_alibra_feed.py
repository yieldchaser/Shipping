"""
Alibra Data Integration Engine
------------------------------
Integrates Alibra historical archives (2008-2026), live snapshot tables,
and tanker forward curves into data/derived/ time series datasets.

Usage:
    python scripts/integrate_alibra_feed.py
"""

import csv
import json
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALIBRA_DATA_DIR = REPO_ROOT / "docs" / "alibra_data"
DERIVED_DIR = REPO_ROOT / "data" / "derived"
TANKER_CURVE_STATE_FILE = REPO_ROOT / "data" / "manifests" / "tanker_curve_state.json"

def clean_num(val):
    """Clean string number with commas or symbols to float, or None."""
    if val is None:
        return None
    val_str = str(val).strip().replace(",", "").replace("$", "").replace('"', "")
    if not val_str or val_str.upper() in ["#N/A", "N/A", "NAN", "-", "NULL"]:
        return None
    try:
        return float(val_str)
    except ValueError:
        return None

def sha256_file(filepath):
    """Computes the SHA-256 hex digest of a file's raw bytes."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def dedupe_forward_rows(rows):
    """Drops all-None rate rows, then keeps the FIRST occurrence per forward_month
    so spurious trailing sub-table rows (e.g. repeated 1-Dec-27) never reach the
    live snapshot or the history accumulator."""
    seen_months = set()
    deduped = []
    for r in rows:
        rate_cols = [k for k in r.keys() if k not in ("snapshot_date", "forward_month", "contract_label")]
        if all(r.get(k) is None for k in rate_cols):
            continue
        if r["forward_month"] in seen_months:
            continue
        seen_months.add(r["forward_month"])
        deduped.append(r)
    return deduped

def parse_iso_date(tag_str, fallback_date_str=""):
    """Extract YYYY-MM-DD from ISO tag (e.g. 'Week 1|2008-01-01') or parse date string."""
    if tag_str:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", str(tag_str))
        if m:
            return m.group(1)
    if fallback_date_str:
        cleaned = str(fallback_date_str).strip()
        for fmt in ["%d %b %Y", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None

def integrate_historical_time_charter():
    """Rebuilds time_charter_rates.csv; cell ownership lives in update_derived_tc_rates.

    The Alibra dry archive is the 4/6-month T/C series, so it fills only the
    *_4_6m_* columns on dates without a printed weekly grid.
    """
    import update_derived_tc_rates
    update_derived_tc_rates.build_time_charter_rates()

def integrate_tanker_forward_curves():
    """Parses all forward_curves CSVs and saves formatted latest snapshot and historical archive."""
    fc_dir = ALIBRA_DATA_DIR / "forward_curves"
    fc_files = sorted(list(fc_dir.glob("*.csv")))
    if not fc_files:
        print("No forward curve files found.")
        return

    # Check if last_updated_stamp is available for latest file
    stamp_dir = ALIBRA_DATA_DIR / "last_updated_stamp"
    stamp_files = sorted(list(stamp_dir.glob("*.csv")))
    latest_stamp_date = None
    if stamp_files:
        with open(stamp_files[-1], encoding="utf-8") as f:
            stamp_text = f.read().strip()
            parsed_stamp = parse_iso_date("", stamp_text)
            if parsed_stamp:
                latest_stamp_date = parsed_stamp

    all_history_rows = []
    latest_rows = []

    for idx, fc_file in enumerate(fc_files):
        snapshot_date = fc_file.stem
        # For the latest file, the stamp date applies only when the archive
        # content actually changed since the last integration. Weekly source,
        # polled daily: freshness by stamp, not by content, fabricated snapshots.
        if idx == len(fc_files) - 1:
            apply_stamp = True
            if TANKER_CURVE_STATE_FILE.exists() and latest_stamp_date:
                try:
                    with open(TANKER_CURVE_STATE_FILE, encoding="utf-8") as f:
                        state = json.load(f)
                    if state.get("sha256") == sha256_file(fc_file):
                        prior_date = state.get("snapshot_date")
                        if prior_date:
                            snapshot_date = prior_date
                            apply_stamp = False
                            print(f"[INFO] Forward-curves content unchanged; reusing snapshot_date {prior_date} (stamp {latest_stamp_date} not applied)")
                except (ValueError, OSError) as _e:
                    print(f"[WARNING] Could not read tanker-curve state file: {_e}")
            if apply_stamp and latest_stamp_date:
                snapshot_date = latest_stamp_date

        file_rows = []
        with open(fc_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            raw_fields = reader.fieldnames or []

            # Map Alibra's verbose column names to our internal keys by keyword fragments.
            # This is resilient: if Alibra renames the column slightly, we still match it.
            # Emit a warning if any expected route cannot be identified.
            ROUTE_MAP = {
                "vlcc_td3c":        lambda h: "TD3C" in h.upper() and "ECO" not in h.upper(),
                "vlcc_eco_td3c":    lambda h: "TD3C" in h.upper() and "ECO" in h.upper(),
                "suezmax_td20":     lambda h: "TD20" in h.upper(),
                "aframax_td25":     lambda h: "TD25" in h.upper(),
                "lr1_tc5":          lambda h: "TC5" in h.upper() and "ECO" not in h.upper(),
                "lr1_eco_tc5":      lambda h: "TC5" in h.upper() and "ECO" in h.upper(),
                "mr_tc2":           lambda h: "TC2" in h.upper() and "ECO" not in h.upper() and "14" not in h,
                "mr_eco_tc2":       lambda h: "TC2" in h.upper() and "ECO" in h.upper(),
                "mr_tc14":          lambda h: "TC14" in h.upper() and "ECO" not in h.upper(),
                "mr_eco_tc14":      lambda h: "TC14" in h.upper() and "ECO" in h.upper(),
                "mr_tc6":           lambda h: "TC6" in h.upper() and "TRIANGULATION" not in h.upper(),
                "mr_triangulation": lambda h: "TRIANGULATION" in h.upper(),
            }
            col_map = {}  # internal_key → csv_field_name
            for key, matcher in ROUTE_MAP.items():
                matched = [f for f in raw_fields if matcher(f)]
                if matched:
                    col_map[key] = matched[0]
                else:
                    print(f"[WARNING] integrate_tanker_forward_curves: cannot find column for '{key}' in {fc_file.name}")

            for row in reader:
                month_str = (row.get(raw_fields[0], "") if raw_fields else "").strip()
                if not month_str:
                    continue

                fwd_iso = parse_iso_date("", month_str)
                if not fwd_iso:
                    try:
                        dt = datetime.strptime(month_str, "%d-%b-%y")
                        fwd_iso = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        fwd_iso = month_str

                item = {
                    "snapshot_date":   snapshot_date,
                    "forward_month":   fwd_iso,
                    "contract_label":  month_str,
                    **{key: clean_num(row.get(field, "")) for key, field in col_map.items()},
                }
                file_rows.append(item)

        # Live-writer dedup: drop all-None rows and duplicate forward months (keep-first)
        file_rows = dedupe_forward_rows(file_rows)
        all_history_rows.extend(file_rows)

        if idx == len(fc_files) - 1:
            latest_rows = file_rows

    if not latest_rows:
        return

    # 1. Write current snapshot CSV
    out_snapshot = DERIVED_DIR / "tanker_forward_curves.csv"
    fc_fieldnames = list(latest_rows[0].keys())
    with open(out_snapshot, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fc_fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in latest_rows:
            writer.writerow(r)

    # 2. Write historical forward curves archive (deduplicated)
    out_history = DERIVED_DIR / "tanker_forward_curves_history.csv"
    existing_keys = set()
    historical_merged = []
    if out_history.exists():
        with open(out_history, encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                k = (r.get("snapshot_date"), r.get("forward_month"))
                if k not in existing_keys:
                    existing_keys.add(k)
                    historical_merged.append(r)

    for r in all_history_rows:
        k = (r["snapshot_date"], r["forward_month"])
        if k not in existing_keys:
            existing_keys.add(k)
            historical_merged.append(r)

    with open(out_history, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fc_fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in historical_merged:
            writer.writerow(r)

    # Persist integration state (hash + date actually used) only when integration proceeded
    try:
        TANKER_CURVE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TANKER_CURVE_STATE_FILE, "w", encoding="utf-8", newline="\n") as f:
            json.dump({
                "sha256": sha256_file(fc_files[-1]),
                "snapshot_date": latest_rows[-1]["snapshot_date"] if latest_rows else None,
                "updated": datetime.utcnow().strftime("%Y-%m-%d")
            }, f, indent=2)
    except OSError as _e:
        print(f"[WARNING] Could not persist tanker-curve state file: {_e}")

    print(f"Successfully generated {out_snapshot} and updated {out_history} ({len(historical_merged)} total history rows across {len(fc_files)} snapshots)!")

def main():
    print("=== RUNNING ALIBRA FEED INTEGRATION ===")
    integrate_historical_time_charter()
    integrate_tanker_forward_curves()
    try:
        import build_alibra_tce_matrix
        build_alibra_tce_matrix.generate_tce_matrix_json()
    except Exception as _e:
        print(f"[WARN] build_alibra_tce_matrix failed: {_e}")
    print("=== INTEGRATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
