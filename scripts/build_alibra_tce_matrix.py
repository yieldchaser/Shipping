import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALIBRA_DIR = REPO_ROOT / "docs" / "alibra_data"
DERIVED_DIR = REPO_ROOT / "data" / "derived"

def generate_tce_matrix_json():
    dry_files = sorted(list((ALIBRA_DIR / "dry_bulk_tce_table").glob("*.csv")))
    tanker_files = sorted(list((ALIBRA_DIR / "tanker_tce_table").glob("*.csv")))
    stamp_files = sorted(list((ALIBRA_DIR / "last_updated_stamp").glob("*.csv")))

    report_date = "2026-08-12"
    if stamp_files:
        with open(stamp_files[-1], encoding="utf-8") as f:
            txt = f.read().strip()
            if txt:
                report_date = txt.splitlines()[0].strip()

    matrix = {
        "report_date": report_date,
        "dry_bulk": [],
        "tankers": []
    }

    if dry_files:
        with open(dry_files[-1], encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if not r or not r.get("Size"):
                    continue
                matrix["dry_bulk"].append({
                    "size": r.get("Size", "").strip(),
                    "rate_6m_atl": float(r.get("6MonthsATL", 0) or 0),
                    "chg_6m_atl": float(r.get("6MchangeATL", 0) or 0),
                    "rate_1y_atl": float(r.get("1YearATL", 0) or 0),
                    "chg_1y_atl": float(r.get("1YRchangeATL", 0) or 0),
                    "rate_2y_atl": float(r.get("2YearATL", 0) or 0),
                    "chg_2y_atl": float(r.get("2YRchangeATL", 0) or 0),
                    "rate_6m_pac": float(r.get("6MonthsPAC", 0) or 0),
                    "chg_6m_pac": float(r.get("6MchangePAC", 0) or 0),
                    "rate_1y_pac": float(r.get("1YearPAC", 0) or 0),
                    "chg_1y_pac": float(r.get("1YRchangePAC", 0) or 0),
                    "rate_2y_pac": float(r.get("2YearPAC", 0) or 0),
                    "chg_2y_pac": float(r.get("2YRchangePAC", 0) or 0),
                })

    if tanker_files:
        with open(tanker_files[-1], encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if not r or not r.get("Size"):
                    continue
                matrix["tankers"].append({
                    "size": r.get("Size", "").strip(),
                    "rate_1y": float(r.get("1Year", 0) or 0),
                    "chg_1y": float(r.get("1Yrchange", 0) or 0),
                    "rate_2y": float(r.get("2Years", 0) or 0),
                    "chg_2y": float(r.get("2Yrchange", 0) or 0),
                    "rate_3y": float(r.get("3Years", 0) or 0),
                    "chg_3y": float(r.get("3Yrchange", 0) or 0),
                    "rate_5y": float(r.get("5 Years", 0) or 0),
                    "chg_5y": float(r.get("5Yrchange", 0) or 0),
                })

    out_file = DERIVED_DIR / "alibra_tce_matrix.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(matrix, f, indent=2)

    print(f"Generated {out_file} with {len(matrix['dry_bulk'])} dry bulk and {len(matrix['tankers'])} tanker classes!")
    return matrix

if __name__ == "__main__":
    generate_tce_matrix_json()
