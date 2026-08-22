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
TC_REJECTION_LOG = ALIBRA_DATA_DIR / "integration_rejections.log"

TC_COLS = [
    "date",
    "source",
    "capesize_4_6m_atl", "capesize_4_6m_pac", "capesize_4_6m_avg",
    "capesize_1y_atl", "capesize_1y_pac", "capesize_1y_avg",
    "capesize_2y_atl", "capesize_2y_pac", "capesize_2y_avg",
    "panamax_4_6m_atl", "panamax_4_6m_pac", "panamax_4_6m_avg",
    "panamax_1y_atl", "panamax_1y_pac", "panamax_1y_avg",
    "panamax_2y_atl", "panamax_2y_pac", "panamax_2y_avg",
    "supramax_4_6m_atl", "supramax_4_6m_pac", "supramax_4_6m_avg",
    "supramax_1y_atl", "supramax_1y_pac", "supramax_1y_avg",
    "supramax_2y_atl", "supramax_2y_pac", "supramax_2y_avg",
    "handysize_4_6m_atl", "handysize_4_6m_pac", "handysize_4_6m_avg",
    "handysize_1y_atl", "handysize_1y_pac", "handysize_1y_avg",
    "handysize_2y_atl", "handysize_2y_pac", "handysize_2y_avg",
    "vlcc_1y", "vlcc_2y", "vlcc_3y", "vlcc_5y",
    "suezmax_1y", "suezmax_2y", "suezmax_3y", "suezmax_5y",
    "aframax_1y", "aframax_2y", "aframax_3y", "aframax_5y",
    "mr_1y", "mr_2y", "mr_3y", "mr_5y",
    "lr1_1y", "lr1_2y", "lr1_3y", "lr1_5y",
    "lr2_1y", "lr2_2y", "lr2_3y", "lr2_5y",
    "handytanker_1y", "handytanker_2y", "handytanker_3y", "handytanker_5y"
]

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

def log_tc_rejection(date, column, old, new, source):
    """Appends a guarded-overwrite rejection to the integration rejection log."""
    is_new = not TC_REJECTION_LOG.exists()
    TC_REJECTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TC_REJECTION_LOG, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["date", "column", "old", "new", "source"])
        writer.writerow([date, column, old, new, source])

def guarded_tc_overwrite(row_dict, col, new_val, source):
    """Overwrite guard for TC enrichment: skips when an existing non-null value
    deviates more than 35% from the incoming value; null-cell writes bypass."""
    old_val = clean_num(row_dict.get(col))
    if old_val is not None and new_val is not None and old_val != 0:
        if abs(new_val - old_val) / abs(old_val) > 0.35:
            print(f"[GUARD] {row_dict.get('date')} {col}: keeping {old_val}, rejected {new_val} from {source}")
            log_tc_rejection(row_dict.get("date", ""), col, old_val, new_val, source)
            return
    row_dict[col] = new_val

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

def parse_archive_file(filepath):
    """Parses an Alibra dry bulk archive CSV into {date: {handysize, supramax, panamax, capesize}}.

    Expected CSV columns (header row):
        BULK CARRIER | Date | HANDYSIZE | SMAX/ULTRA | PANAMAX | CAPESIZE | <optional tag col>
    Uses DictReader so any column reorder or insertion produces a KeyError/warning
    rather than silently mapping the wrong value to the wrong field.
    """
    records = {}
    if not filepath.exists():
        return records
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Warn once if expected columns are absent (schema change upstream)
        required_cols = {"Date", "HANDYSIZE", "SMAX/ULTRA", "PANAMAX", "CAPESIZE"}
        if reader.fieldnames:
            missing = required_cols - set(reader.fieldnames)
            if missing:
                print(f"[WARNING] parse_archive_file: missing expected columns in {filepath.name}: {missing}")
        for row in reader:
            date_col = row.get("Date", "")
            # Last column (variable name) acts as the ISO tag
            tag_col = row.get(reader.fieldnames[-1], "") if reader.fieldnames else ""
            iso_date = parse_iso_date(tag_col, date_col)
            if not iso_date or iso_date < "2008-01-01":
                continue
            records[iso_date] = {
                "handysize": clean_num(row.get("HANDYSIZE", "")),
                "supramax":  clean_num(row.get("SMAX/ULTRA", "")),
                "panamax":   clean_num(row.get("PANAMAX", "")),
                "capesize":  clean_num(row.get("CAPESIZE", "")),
            }
    return records

def integrate_historical_time_charter():
    """Integrates Alibra Atlantic (2015-2026) and Pacific (2008-2026) archives into time_charter_rates.csv."""
    tc_file = DERIVED_DIR / "time_charter_rates.csv"
    existing_rows = {}
    
    if tc_file.exists():
        with open(tc_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = row.get("date", "").strip()
                if d:
                    existing_rows[d] = row

    atl_files = sorted(list((ALIBRA_DATA_DIR / "dry_bulk_archive_atl").glob("*.csv")))
    pac_files = sorted(list((ALIBRA_DATA_DIR / "dry_bulk_archive_pac").glob("*.csv")))

    atl_records = {}
    atl_source_name = ""
    if atl_files:
        atl_records = parse_archive_file(atl_files[-1])
        atl_source_name = atl_files[-1].name
        print(f"Loaded {len(atl_records)} Atlantic archive rows ({min(atl_records.keys())} -> {max(atl_records.keys())})")

    pac_records = {}
    pac_source_name = ""
    if pac_files:
        pac_records = parse_archive_file(pac_files[-1])
        pac_source_name = pac_files[-1].name
        print(f"Loaded {len(pac_records)} Pacific archive rows ({min(pac_records.keys())} -> {max(pac_records.keys())})")

    all_dates = set(existing_rows.keys()) | set(atl_records.keys()) | set(pac_records.keys())
    merged_rows = []

    for d in sorted(all_dates):
        row = existing_rows.get(d, {})
        if d < "2008-01-01" and row.get("source") == "alibra_archive":
            continue
        row_dict = {"date": d}
        for col in TC_COLS[1:]:
            row_dict[col] = row.get(col, "")

        # Set source provenance
        if not row_dict.get("source"):
            if d in atl_records or d in pac_records:
                row_dict["source"] = "alibra_archive"
            elif d < "2021-07-07":
                row_dict["source"] = "fearnleys"
            else:
                row_dict["source"] = "alibra_ocr"

        # Enrich Atlantic rates
        if d in atl_records:
            a = atl_records[d]
            if a["capesize"] is not None:
                guarded_tc_overwrite(row_dict, "capesize_1y_atl", a["capesize"], atl_source_name)
            if a["panamax"] is not None:
                guarded_tc_overwrite(row_dict, "panamax_1y_atl", a["panamax"], atl_source_name)
            if a["supramax"] is not None:
                guarded_tc_overwrite(row_dict, "supramax_1y_atl", a["supramax"], atl_source_name)
            if a["handysize"] is not None:
                guarded_tc_overwrite(row_dict, "handysize_1y_atl", a["handysize"], atl_source_name)

        # Enrich Pacific rates
        if d in pac_records:
            p = pac_records[d]
            if p["capesize"] is not None:
                guarded_tc_overwrite(row_dict, "capesize_1y_pac", p["capesize"], pac_source_name)
            if p["panamax"] is not None:
                guarded_tc_overwrite(row_dict, "panamax_1y_pac", p["panamax"], pac_source_name)
            if p["supramax"] is not None:
                guarded_tc_overwrite(row_dict, "supramax_1y_pac", p["supramax"], pac_source_name)
            if p["handysize"] is not None:
                guarded_tc_overwrite(row_dict, "handysize_1y_pac", p["handysize"], pac_source_name)

        # Compute averages if both atl and pac are present
        for seg in ["capesize", "panamax", "supramax", "handysize"]:
            atl_val = clean_num(row_dict.get(f"{seg}_1y_atl"))
            pac_val = clean_num(row_dict.get(f"{seg}_1y_pac"))
            current_avg = clean_num(row_dict.get(f"{seg}_1y_avg"))

            if atl_val is not None and pac_val is not None:
                row_dict[f"{seg}_1y_avg"] = (atl_val + pac_val) / 2.0
            elif current_avg is None:
                if pac_val is not None:
                    row_dict[f"{seg}_1y_avg"] = pac_val
                elif atl_val is not None:
                    row_dict[f"{seg}_1y_avg"] = atl_val

        merged_rows.append(row_dict)

    merged_rows.sort(key=lambda r: r["date"])

    with open(tc_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TC_COLS, extrasaction="ignore")
        writer.writeheader()
        for r in merged_rows:
            writer.writerow(r)

    print(f"Successfully integrated Alibra historical archives into {tc_file} ({len(merged_rows)} total rows)!")

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
        writer = csv.DictWriter(f, fieldnames=fc_fieldnames)
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
        writer = csv.DictWriter(f, fieldnames=fc_fieldnames)
        writer.writeheader()
        for r in historical_merged:
            writer.writerow(r)

    # Persist integration state (hash + date actually used) only when integration proceeded
    try:
        TANKER_CURVE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TANKER_CURVE_STATE_FILE, "w", encoding="utf-8") as f:
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
