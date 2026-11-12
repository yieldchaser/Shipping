"""P2 prospector: characterize every CSV in data/extracted/series/ for series_map generation.

For each file emit:
  - columns, row count
  - date column candidates
  - numeric (value) columns: measured by non-empty cells parseable as float
  - string/label columns
  - has_source_file
  - value-column numeric density (0..1) to separate matrix files from transaction files
Deterministic; reads only. Writes kb/reports/p2_prospect.json
"""
import csv, json, re, sys
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path("data/extracted/series")

NUM_RE = re.compile(r"^-?\s*\$?\s*[\d,]+(?:\.\d+)?\s*%?\s*$")

DATE_CAND = {"issue_date","published_date","report_date","date","print_date","rates_date",
             "rates_date_prev","rates_date_curr"}

def is_numeric_cell(s):
    if s is None or s == "":
        return None
    s = s.strip()
    if s.lower() in ("-","n/a","na","u/d","n.d.","tba","tbc","","—","–"):
        return None
    return bool(NUM_RE.match(s))

def parse_float(s):
    s = s.strip().lstrip("$").rstrip("%").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None

out = []
for p in sorted(ROOT.glob("*.csv")):
    with open(p, newline="", encoding="utf-8", errors="replace") as f:
        rd = csv.reader(f)
        try:
            hdr = next(rd)
        except StopIteration:
            hdr = []
        rows = list(rd)
    n = len(rows)
    has_sf = "source_file" in hdr
    # per-column numeric density among non-empty
    col_info = {}
    for ci, name in enumerate(hdr):
        vals = [r[ci] if ci < len(r) else "" for r in rows]
        nonempty = [v for v in vals if v is not None and v.strip() != ""]
        parsed = [parse_float(v) for v in nonempty]
        num_ok = [x for x in parsed if x is not None]
        col_info[name] = {
            "nonempty": len(nonempty),
            "numeric": len(num_ok),
            "density": round(len(num_ok)/len(nonempty), 3) if nonempty else 0.0,
        }
    date_cols = [c for c in hdr if c in DATE_CAND and col_info.get(c) and col_info[c]["numeric"] == 0]
    # value cols: density high
    value_cols = [c for c in hdr if c not in DATE_CAND and col_info[c]["density"] >= 0.9
                  and col_info[c]["nonempty"] > 0 and c != "issue"]
    label_cols = [c for c in hdr if c not in ("source_file","issue","page") and c not in DATE_CAND
                  and c not in value_cols and col_info[c]["numeric"] < 0.5]
    out.append({
        "file": p.stem,
        "rows": n,
        "cols": hdr,
        "has_source_file": has_sf,
        "date_cols": date_cols,
        "value_cols": value_cols,
        "label_cols": label_cols,
        "col_info": col_info,
    })

json.dump(out, open("kb/reports/p2_prospect.json","w",encoding="utf-8"), indent=1)

# concise summary
print(f"files: {len(out)}")
for o in out:
    print(f"{o['file']:<42} rows={o['rows']:>6} date={o['date_cols']} val={o['value_cols']}")
