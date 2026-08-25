# 2026-08-25 audit: this script is a MANUAL forensic tool only — it is NOT wired
# into any workflow, and it must not be run against data/derived/time_charter_rates.csv
# without re-applying the archive-truth corrections committed in feat/audit-fixes
# (docs/alibra_data/integration_rejections.log pairs + verified scrappage/TC fixes).
# Its positional column slicing (_vals[-6:] / _vals[-4:]) is the root cause of the
# column-misalignment artifacts corrected in that branch.
import json
import csv
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
CHUNKS_DIR = REPO_ROOT / "knowledge" / "chunks"
DERIVED_DIR = REPO_ROOT / "data" / "derived"

CHARTER_SEGMENT_ALIASES = {
    "dry_charter": {
        "capesize": ["capesize", "cape"],
        "panamax": ["panamax", "pmax", "pana/kmax", "kamsarmax", "kmax", "panaikmax", "pa"],
        "supramax": ["supramax", "supra", "smx", "ultramax", "umx", "smax", "smaxiultra", "smax/ultra", "suavuurra", "swaxultra", "smawultra"],
        "handysize": ["handysize", "handy", "hsize", "hanor", "won"],
    },
    "tanker_charter": {
        "vlcc": ["vlcc", "vicc", "v1cc", "vlce", "vice", "vilcc", "vvilcc", "vee", "vce", "vlee"],
        "suezmax": ["suezmax", "suez"],
        "aframax": ["aframax", "afra", "jafra", "aera", "larna", "apra", "arra"],
        "lr2": ["lr2", "lr 2", "1r2", "ure", "ur2"],
        "lr1": ["lr1", "lr 1", "lri", "trl", "uri", "tr1", "lr", "ut", "1r1", "lrt", "ir1"],
        "mr": ["mr imo", "mr", "m.r.", "mri", "handymax", "mr1", "mr2"],
        "handytanker": ["handy", "handytanker", "h.tanker", "small tanker"],
    },
}

def extract_line_numbers(text):
    nums = []
    # match patterns like 28,000, 28000, 28.5k, etc.
    cleaned = text.replace(",", "").replace("$", " ")
    for token in re.findall(r"\b\d+(?:\.\d+)?\b", cleaned):
        try:
            val = float(token)
            if 1000 <= val <= 250000: # realistic daily TCE range
                nums.append(val)
        except ValueError:
            continue
    return nums

def extract_hellenic_charter_signals(text, category):
    alias_map = CHARTER_SEGMENT_ALIASES.get(category, {})
    observations = []
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        if any(skip in lower for skip in ["image reference:", "source asset:", "linked image asset:", "embedded info:", "exif text:"]):
            continue
        
        matching_segments = []
        for segment, aliases in alias_map.items():
            matched = False
            for alias in aliases:
                if len(alias.strip()) <= 3:
                    if re.search(r"\b" + re.escape(alias.strip()) + r"\b", lower):
                        matched = True
                        break
                else:
                    if alias in lower:
                        matched = True
                        break
            if matched:
                matching_segments.append(segment)
                
        if not matching_segments:
            continue
            
        values = extract_line_numbers(line)
        if not values:
            continue
            
        for segment in matching_segments[:2]:
            observations.append({
                "segment": segment,
                "values": values,
                "source_line": line
            })
    return {"rate_observations": observations}

def main():
    print("=== Recompiling time_charter_rates.csv with full 66-column schema ===")
    tc_records = {}

    import glob
    all_tc_chunk_files = []
    
    # Tanker charter chunks
    _tc_base = CHUNKS_DIR / "hellenic_tanker_charter.jsonl"
    if _tc_base.exists():
        all_tc_chunk_files.append((_tc_base, "tanker_charter"))
    for _sf in sorted(glob.glob(str(CHUNKS_DIR / "hellenic_tanker_charter_*.jsonl"))):
        all_tc_chunk_files.append((Path(_sf), "tanker_charter"))
        
    # Dry charter chunks
    _dc_base = CHUNKS_DIR / "hellenic_dry_charter.jsonl"
    if _dc_base.exists():
        all_tc_chunk_files.append((_dc_base, "dry_charter"))
    for _sf in sorted(glob.glob(str(CHUNKS_DIR / "hellenic_dry_charter_*.jsonl"))):
        all_tc_chunk_files.append((Path(_sf), "dry_charter"))

    print(f"Scanning {len(all_tc_chunk_files)} chunk files...")
    for _cf, _cat in all_tc_chunk_files:
        try:
            with open(_cf, encoding="utf-8") as _fh:
                for _line in _fh:
                    _line = _line.strip()
                    if not _line:
                        continue
                    try:
                        _chunk = json.loads(_line)
                    except json.JSONDecodeError:
                        continue
                    _date = _chunk.get("date")
                    if _date == "2022-10-21":
                        _date = "2022-10-19"
                    _text = _chunk.get("text", "")
                    if not _date or not _text:
                        continue
                    if "OCR text:" not in _text and "TIME CHARTER" not in _text.upper():
                        continue
                    _extracted = extract_hellenic_charter_signals(_text, _cat)
                    _rate_obs = _extracted.get("rate_observations", []) or []
                    if not _rate_obs:
                        continue
                    if _date not in tc_records:
                        tc_records[_date] = {}
                    for _obs in _rate_obs:
                        _seg = _obs.get("segment")
                        _vals = _obs.get("values") or []
                        if not _seg or not _vals:
                            continue
                        if _cat == "dry_charter":
                            _rates = _vals[-6:]
                            if len(_rates) == 6:
                                tc_records[_date][f"{_seg}_4_6m_atl"] = _rates[0]
                                tc_records[_date][f"{_seg}_4_6m_pac"] = _rates[1]
                                tc_records[_date][f"{_seg}_4_6m_avg"] = (_rates[0] + _rates[1]) / 2.0
                                tc_records[_date][f"{_seg}_1y_atl"] = _rates[2]
                                tc_records[_date][f"{_seg}_1y_pac"] = _rates[3]
                                tc_records[_date][f"{_seg}_1y_avg"] = (_rates[2] + _rates[3]) / 2.0
                                tc_records[_date][f"{_seg}_2y_atl"] = _rates[4]
                                tc_records[_date][f"{_seg}_2y_pac"] = _rates[5]
                                tc_records[_date][f"{_seg}_2y_avg"] = (_rates[4] + _rates[5]) / 2.0
                            elif len(_rates) == 5:
                                tc_records[_date][f"{_seg}_4_6m_pac"] = _rates[0]
                                tc_records[_date][f"{_seg}_4_6m_avg"] = _rates[0]
                                tc_records[_date][f"{_seg}_1y_atl"] = _rates[1]
                                tc_records[_date][f"{_seg}_1y_pac"] = _rates[2]
                                tc_records[_date][f"{_seg}_1y_avg"] = (_rates[1] + _rates[2]) / 2.0
                                tc_records[_date][f"{_seg}_2y_atl"] = _rates[3]
                                tc_records[_date][f"{_seg}_2y_pac"] = _rates[4]
                                tc_records[_date][f"{_seg}_2y_avg"] = (_rates[3] + _rates[4]) / 2.0
                        else: # tanker_charter
                            _rates = _vals[-4:]
                            if len(_rates) == 4:
                                _k1 = f"{_seg}_1y"
                                if _k1 not in tc_records[_date]:
                                    tc_records[_date][f"{_seg}_1y"] = _rates[0]
                                    tc_records[_date][f"{_seg}_2y"] = _rates[1]
                                    tc_records[_date][f"{_seg}_3y"] = _rates[2]
                                    tc_records[_date][f"{_seg}_5y"] = _rates[3]
        except OSError:
            continue

    tc_file = DERIVED_DIR / "time_charter_rates.csv"
    tc_cols = [
        "date",
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
    
    existing_backfill_rows = []
    if tc_file.exists():
        with open(tc_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("source") == "fearnleys":
                    # reformat fearnleys row to 66 cols
                    cleaned_f_row = {"date": row.get("date", ""), "source": "fearnleys"}
                    for col in tc_cols[1:]:
                        cleaned_f_row[col] = row.get(col, "")
                    existing_backfill_rows.append(cleaned_f_row)

    alibra_rows = []
    tc_cols_with_source = ["date", "source"] + tc_cols[1:]
    for date in sorted(tc_records.keys()):
        row_dict = {"date": date, "source": "alibra_ocr"}
        data = tc_records[date]
        for col in tc_cols[1:]:
            val = None
            if col in data:
                val = data[col]
            else:
                col_parts = col.split("_", 1)
                if len(col_parts) == 2:
                    col_seg, col_suffix = col_parts
                    for key, key_val in data.items():
                        key_parts = key.split("_", 1)
                        if len(key_parts) == 2:
                            key_seg, key_suffix = key_parts
                            if key_suffix == col_suffix:
                                if col_seg == "panamax" and ("panam" in key_seg or "kmax" in key_seg):
                                    val = key_val
                                    break
                                elif col_seg == "supramax" and ("supra" in key_seg or "smax" in key_seg or "ultra" in key_seg):
                                    val = key_val
                                    break
                                elif col_seg == "handytanker" and ("handytanker" in key_seg or "h.tanker" in key_seg):
                                    val = key_val
                                    break
            row_dict[col] = val if val is not None else ""
        alibra_rows.append(row_dict)

    all_rows = existing_backfill_rows + alibra_rows
    all_rows.sort(key=lambda r: r.get("date", ""))
    
    with open(tc_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=tc_cols_with_source, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)
            
    print(f"Saved {len(all_rows)} rows across {len(tc_cols_with_source)} columns to {tc_file}!")
    print(f"  - Fearnleys rows: {len(existing_backfill_rows)}")
    print(f"  - Alibra OCR rows: {len(alibra_rows)} ({alibra_rows[0]['date']} -> {alibra_rows[-1]['date']})")

if __name__ == "__main__":
    main()
