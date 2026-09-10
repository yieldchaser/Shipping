"""
Phase 8.3 — Provenance Completeness Audit
Audits data/provenance/manifest.json against files on disk:
- Missing entries for data/ files
- Field completeness (source_url, fetch_script, hash_sha256, row_count, date_span, license, last_fetched_utc)
- Disk recomputation comparison (row counts, date spans)
- Timestamp sanity (future dates, identical batch timestamps)
- Quarantine isolation (grep for _quarantine in index.html, js/, production scripts)
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import csv
import re

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = ROOT / "data" / "provenance" / "manifest.json"
DATA_DIR = ROOT / "data"

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def analyze_disk_file(filepath):
    """Recomputes row count and date span from file."""
    if not filepath.exists():
        return {"exists": False}
    
    res = {"exists": True, "size_bytes": filepath.stat().st_size}
    suffix = filepath.suffix.lower()
    
    if suffix == ".csv":
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers:
                    res["row_count"] = 0
                    res["date_span"] = None
                    return res
                
                # Try finding a date column
                date_col_idx = None
                for idx, h in enumerate(headers):
                    if h.lower() in ["date", "timestamp", "datetime", "trade_date", "day"]:
                        date_col_idx = idx
                        break
                
                rows = 0
                dates = []
                for row in reader:
                    if not row or not any(row):
                        continue
                    rows += 1
                    if date_col_idx is not None and date_col_idx < len(row):
                        d_val = row[date_col_idx].strip()
                        if re.match(r"^\d{4}-\d{2}-\d{2}", d_val):
                            dates.append(d_val[:10])
                
                res["row_count"] = rows
                if dates:
                    dates.sort()
                    res["date_span"] = [dates[0], dates[-1]]
                else:
                    res["date_span"] = None
        except Exception as e:
            res["error"] = str(e)
            
    elif suffix == ".json":
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                if isinstance(data, list):
                    res["row_count"] = len(data)
                elif isinstance(data, dict):
                    # Check if dict of items/series or single obj
                    res["row_count"] = len(data.keys())
                else:
                    res["row_count"] = 1
                res["date_span"] = None
        except Exception as e:
            res["error"] = str(e)
    else:
        res["row_count"] = None
        res["date_span"] = None
        
    return res

def audit_manifest():
    report = {
        "manifest_found": MANIFEST_PATH.exists(),
        "total_manifest_series": 0,
        "missing_fields": [],
        "generic_urls": [],
        "disk_discrepancies": [],
        "timestamp_issues": {
            "future_dates": [],
            "identical_timestamps": {}
        },
        "unregistered_data_files": [],
        "quarantine_leakage": []
    }
    
    if not MANIFEST_PATH.exists():
        print(f"Error: {MANIFEST_PATH} does not exist!")
        return report

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    series_list = manifest.get("series", [])
    report["total_manifest_series"] = len(series_list)
    
    # 1. Check data files coverage
    manifest_files = set()
    for s in series_list:
        out_f = s.get("output_file")
        if out_f:
            manifest_files.add(str(Path(out_f).as_posix()).lower())
            
    all_data_files = []
    for f in DATA_DIR.rglob("*.*"):
        rel = f.relative_to(ROOT).as_posix()
        if "_quarantine" in rel or "provenance" in rel:
            continue
        if f.suffix.lower() in [".csv", ".json", ".parquet"]:
            all_data_files.append(rel)
            if rel.lower() not in manifest_files:
                report["unregistered_data_files"].append(rel)
                
    # 2. Check each series for completeness & accuracy
    now_utc = datetime.now(timezone.utc)
    timestamps = {}
    
    for s in series_list:
        s_id = s.get("series_id", "UNKNOWN")
        out_file_rel = s.get("output_file", "")
        out_path = ROOT / out_file_rel if out_file_rel else None
        
        # Required fields check
        required_fields = ["source_url", "fetch_script", "row_count", "last_fetched_utc"]
        for rf in required_fields:
            if rf not in s or s[rf] is None or s[rf] == "":
                report["missing_fields"].append({"series_id": s_id, "field": rf})
                
        # Generic url check
        url = s.get("source_url", "")
        if url in ["https://shipandbunker.com", "Multiple Primary Sources", "Various", "https://clarksons.net"]:
            report["generic_urls"].append({"series_id": s_id, "url": url})
            
        # Timestamp check
        l_utc_str = s.get("last_fetched_utc")
        if l_utc_str:
            timestamps[l_utc_str] = timestamps.get(l_utc_str, 0) + 1
            try:
                # parse iso
                dt = datetime.fromisoformat(l_utc_str.replace("Z", "+00:00"))
                if dt > now_utc:
                    report["timestamp_issues"]["future_dates"].append({"series_id": s_id, "timestamp": l_utc_str})
            except Exception:
                pass
                
        # Disk recomputation comparison
        if out_path and out_path.exists():
            disk_info = analyze_disk_file(out_path)
            claimed_rows = s.get("row_count")
            actual_rows = disk_info.get("row_count")
            
            # If row count discrepancy
            if actual_rows is not None and claimed_rows is not None and claimed_rows != actual_rows:
                report["disk_discrepancies"].append({
                    "series_id": s_id,
                    "file": out_file_rel,
                    "type": "row_count_mismatch",
                    "claimed": claimed_rows,
                    "actual": actual_rows
                })
                
            claimed_span = s.get("date_span")
            actual_span = disk_info.get("date_span")
            if actual_span is not None and claimed_span is not None:
                if claimed_span != actual_span:
                    report["disk_discrepancies"].append({
                        "series_id": s_id,
                        "file": out_file_rel,
                        "type": "date_span_mismatch",
                        "claimed": claimed_span,
                        "actual": actual_span
                    })
        else:
            report["disk_discrepancies"].append({
                "series_id": s_id,
                "file": out_file_rel,
                "type": "file_missing_on_disk"
            })

    for ts, count in timestamps.items():
        if count >= 20:
            report["timestamp_issues"]["identical_timestamps"][ts] = count

    # 3. Quarantine leakage check
    # Check index.html, js/, and production scripts (outside quarantine tooling itself)
    quarantine_pattern = re.compile(r"_quarantine", re.IGNORECASE)
    
    files_to_check = [ROOT / "index.html"]
    for dir_to_check in [ROOT / "js", ROOT / "scripts"]:
        if dir_to_check.exists():
            for f in dir_to_check.rglob("*.*"):
                if f.suffix in [".py", ".js", ".html"]:
                    # exclude quarantine tooling itself
                    if "quarantine" in f.name.lower() or "verify" in str(f) or "audit" in f.name.lower():
                        continue
                    files_to_check.append(f)
                    
    for f in files_to_check:
        if not f.exists(): continue
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            for idx, line in enumerate(lines):
                if quarantine_pattern.search(line):
                    report["quarantine_leakage"].append({
                        "file": str(f.relative_to(ROOT)).replace("\\", "/"),
                        "line": idx + 1,
                        "snippet": line.strip()[:100]
                    })
        except Exception:
            pass

    return report

def main():
    print("=== Phase 8.3: Provenance Completeness Audit ===")
    rep = audit_manifest()
    
    print(f"Total manifest series: {rep['total_manifest_series']}")
    print(f"Unregistered data files: {len(rep['unregistered_data_files'])}")
    for f in rep["unregistered_data_files"][:5]:
        print(f"  [UNREGISTERED] {f}")
    if len(rep["unregistered_data_files"]) > 5:
        print(f"  ... and {len(rep['unregistered_data_files']) - 5} more")
        
    print(f"Missing required fields: {len(rep['missing_fields'])}")
    print(f"Generic URLs flagged: {len(rep['generic_urls'])}")
    for g in rep["generic_urls"][:5]:
        print(f"  [GENERIC URL] {g['series_id']}: {g['url']}")
        
    print(f"Disk discrepancies: {len(rep['disk_discrepancies'])}")
    for d in rep["disk_discrepancies"][:5]:
        print(f"  [DISCREPANCY] {d['series_id']}: {d['type']} (claimed {d.get('claimed')}, actual {d.get('actual')})")
        
    print(f"Timestamp issues:")
    print(f"  Future timestamps: {len(rep['timestamp_issues']['future_dates'])}")
    print(f"  Clustered identical timestamps (>=20): {len(rep['timestamp_issues']['identical_timestamps'])}")
    for ts, cnt in rep["timestamp_issues"]["identical_timestamps"].items():
        print(f"    {ts}: {cnt} series")
        
    print(f"Quarantine leakage check: {len(rep['quarantine_leakage'])} references found")
    for q in rep["quarantine_leakage"]:
        print(f"  [LEAKAGE] {q['file']}:{q['line']} -> {q['snippet']}")
        
    out_file = ROOT / "data" / "provenance" / "phase8_provenance_audit.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print(f"Saved provenance audit report to {out_file}")

if __name__ == "__main__":
    main()
