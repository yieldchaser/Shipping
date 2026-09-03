#!/usr/bin/env python3
"""
Data Spike & Flatline Health Scanner (read-only, never deletes data).

Scans:
  data/derived/*.csv + data/commodities/*.csv + data/congestion/*.csv

Detectors per numeric series:
  1. WoW jump      : |cur - prev| / |prev| > 30% on consecutive non-null points
  2. Sigma break   : |x - mean(prior 252)| > 3 * stdev(prior 252), min 30 priors
  3. Flatline      : > 15 consecutive identical non-null repeats (one flag per run)
  4. Empty-row info: date present but every numeric field null (quality signal,
                     e.g. data/derived/iron_ore_restocking.csv 2018-07-19)

Allow-list (never flagged):
  - NEWBUILDING valuations : any row with a field == 'NEWBUILDING' (case-insensitive),
    e.g. data/derived/vessel_valuations.csv long-run newbuilding price levels.
  - ton-mile model_disclosed: the `model_disclosed` flag column itself in
    data/derived/ton_mile_utilization_matrix.csv (a boolean, not a price).
  - SGX expiry >= 2030     : any row with expiry_year >= 2030 or an expiry/expiry_date
    year >= 2030 (far-dated illiquid contracts).

Series grouping: files with entity keys (category/tenor_type/vessel_class/
contract/expiry_month/expiry_year/portid/hub_code) are checked per group so
consecutive rows from different entities are never compared.

Output: knowledge/manifests/spike_queue.jsonl (one JSON object per line).
Always exits 0. Never modifies or deletes anything under data/.
Known P0 context (flagged, NOT auto-corrected — no fabrication):
  - scrappage_prices.csv 2024-08-03 container_india 763.0 (+42.6% vs 535.0):
    source HTML reports/hellenic/demolition/2024/2024-08-03_*.html carries only a
    PDF link, no inline table; PDF text not verified via file-read tools.
  - usda_grain_vessel_rates_japan.csv lines 143-154 (Oct 2007-Aug 2008 Gulf_To_Japan
    ~10-13 vs ~90-130 era levels, 10x decimal-shift pattern): no archived USDA
    xlsx/cache in data/cache proves the scale (only req_jun2026_hist.xlsx present;
    fetch_usda_grains.py pulls the live API), so values are flagged, not rescaled.
"""

import csv
import json
import statistics
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_PATTERNS = [
    "data/derived/*.csv",
    "data/commodities/*.csv",
    "data/congestion/*.csv",
]
OUT_PATH = ROOT / "knowledge" / "manifests" / "spike_queue.jsonl"

WOW_PCT = 0.30
SIGMA = 3.0
SIGMA_WINDOW = 252
SIGMA_MIN_PRIORS = 30
FLATLINE_N = 15

DATE_COLS = {"date", "datestr", "asofdate", "timestamp"}
SKIP_COLS = {
    "date", "datestr", "asofdate", "timestamp",
    "year", "month", "expiry_year", "expiry_month",
    "contract", "portid", "hub_code", "portname", "country",
    "category", "tenor_type", "vessel_class",
    "model_disclosed",  # ton-mile boolean flag, not a price
}
GROUP_COLS = (
    "category", "tenor_type", "vessel_class",
    "contract", "expiry_month", "expiry_year",
    "portid", "hub_code",
)
EXPIRY_YEAR_COLS = {"expiry_year", "expiry date", "expiry_date"}


def parse_date(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y",
                "%d/%m/%Y", "%Y-%m", "%b %Y", "%B %Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # "October 2007" style with extra day noise
    try:
        parts = s.replace(",", " ").split()
        if len(parts) == 2:
            return datetime.strptime(s, "%B %Y")
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def to_float(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if s == "" or s.lower() in ("na", "n/a", "nan", "none", "null", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def is_allowlisted_row(row):
    """NEWBUILDING valuations + SGX expiry >= 2030 rows are never flagged."""
    for k, v in row.items():
        if v is None:
            continue
        if str(v).strip().upper() == "NEWBUILDING":
            return True, "NEWBUILDING valuations allow-listed"
    for col in EXPIRY_YEAR_COLS:
        for key in row:
            if key is not None and str(key).strip().lower() == col:
                yr = None
                raw = str(row[key]).strip()
                try:
                    yr = int(float(raw))
                    if yr < 100:  # not a year
                        yr = None
                except ValueError:
                    dt = parse_date(raw)
                    yr = dt.year if dt else None
                if yr is not None and yr >= 2030:
                    return True, "SGX expiry>=2030 allow-listed"
                break
    return False, ""


def scan_file(path):
    findings = []
    rel = path.relative_to(ROOT).as_posix()
    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            rows = list(reader)
    except Exception as e:  # unreadable file: note and continue, never fail
        print(f"WARN {rel}: unreadable ({e})")
        return findings
    if not rows or not fields:
        return findings

    date_col = next((c for c in fields if c and c.strip().lower() in DATE_COLS), None)
    if date_col is None:
        # USDA-style "Date" like "October 2007" still parses; accept case-insensitively
        date_col = next((c for c in fields if c and c.strip().lower() == "date"), None)
    num_cols = [c for c in fields
                if c and c.strip().lower() not in SKIP_COLS and c != date_col]
    # Drop text identifier columns (>50% non-numeric among non-empty)
    checked_cols = []
    for c in num_cols:
        vals = [r.get(c) for r in rows if r.get(c) not in (None, "")]
        if not vals:
            continue
        numeric = sum(1 for v in vals if to_float(v) is not None)
        if numeric >= 0.5 * len(vals):
            checked_cols.append(c)
    if not checked_cols:
        return findings

    group_keys = [c for c in GROUP_COLS if c in fields]
    groups = {}
    order = []
    for i, r in enumerate(rows):
        dt = parse_date(r.get(date_col)) if date_col else None
        key = tuple(str(r.get(c)) for c in group_keys) if group_keys else ("__all__",)
        if key not in groups:
            groups[key] = []
            order.append(key)
        datestr = str(r.get(date_col)).strip() if date_col else f"row{i + 1}"
        groups[key].append((dt, datestr, i, r))
    for key in order:
        pts = groups[key]
        pts.sort(key=lambda t: (t[0] is None, t[0], t[2]))
        allow_skip = sum(1 for (_, _, _, r) in pts if is_allowlisted_row(r)[0])
        if allow_skip and allow_skip == len(pts):
            continue  # whole group allow-listed
        for col in checked_cols:
            series = []
            for dt, datestr, i, r in pts:
                allowed, _ = is_allowlisted_row(r)
                if allowed:
                    continue
                v = to_float(r.get(col))
                series.append((dt, datestr, v))
            # 4. empty-row info is emitted per file below, not per column
            prev = None
            run_val = None
            run_len = 0
            run_end = ""
            history = []
            for dt, datestr, v in series:
                if v is None:
                    prev = None
                    run_val, run_len = None, 0
                    continue
                if prev is not None and prev[1] != 0:
                    pct = abs(v - prev[1]) / abs(prev[1])
                    if pct > WOW_PCT:
                        findings.append({
                            "file": rel, "date": datestr, "column": col,
                            "value": v, "prev_value": prev[1],
                            "prev_date": prev[0], "pct_change": round(pct * 100, 2),
                            "check": "wow_gt30pct", "severity": "high" if pct > 0.5 else "medium",
                            "status": "flagged",
                            "action": "human_review — value NOT auto-corrected, never fabricate",
                            "provenance": "check_data_spike_health.py WoW detector",
                        })
                if len(history) >= SIGMA_MIN_PRIORS:
                    window = history[-SIGMA_WINDOW:]
                    try:
                        mu = statistics.mean(window)
                        sd = statistics.pstdev(window) if len(window) > 1 else 0.0
                    except statistics.StatisticsError:
                        mu, sd = v, 0.0
                    if sd > 0 and abs(v - mu) > SIGMA * sd:
                        findings.append({
                            "file": rel, "date": datestr, "column": col,
                            "value": v, "mean_prior252": round(mu, 4),
                            "stdev_prior252": round(sd, 4),
                            "zscore": round((v - mu) / sd, 2),
                            "check": "sigma3_vs252d", "severity": "high",
                            "status": "flagged",
                            "action": "human_review — value NOT auto-corrected, never fabricate",
                            "provenance": "check_data_spike_health.py 3-sigma detector",
                        })
                history.append(v)
                if run_val is not None and v == run_val:
                    run_len += 1
                    run_end = datestr
                else:
                    if run_val is not None and run_len > FLATLINE_N:
                        findings.append({
                            "file": rel, "date": run_end, "column": col,
                            "value": run_val, "repeat_count": run_len,
                            "check": "flatline_gt15", "severity": "medium",
                            "status": "flagged",
                            "action": "human_review — confirm feed freeze vs genuine flat market",
                            "provenance": "check_data_spike_health.py flatline detector",
                        })
                    run_val, run_len, run_end = v, 1, datestr
                prev = (datestr, v)
            if run_val is not None and run_len > FLATLINE_N:
                findings.append({
                    "file": rel, "date": run_end, "column": col,
                    "value": run_val, "repeat_count": run_len,
                    "check": "flatline_gt15", "severity": "medium",
                    "status": "flagged",
                    "action": "human_review — confirm feed freeze vs genuine flat market",
                    "provenance": "check_data_spike_health.py flatline detector",
                })
    # Empty-row quality signal (e.g. iron_ore_restocking.csv 2018-07-19)
    if date_col and checked_cols:
        for r in rows:
            datestr = str(r.get(date_col)).strip()
            if not datestr:
                continue
            if all(to_float(r.get(c)) is None for c in checked_cols):
                findings.append({
                    "file": rel, "date": datestr, "column": "*",
                    "value": None, "check": "empty_row_all_null",
                    "severity": "info",
                    "status": "flagged",
                    "action": "loader filters fully-empty rows; PapaParse skipEmptyLines=true",
                    "provenance": "check_data_spike_health.py empty-row detector",
                })
    return findings


def main():
    targets = []
    for pat in SCAN_PATTERNS:
        targets.extend(sorted(ROOT.glob(pat)))
    print(f"Scanning {len(targets)} CSVs for spikes/flatlines (read-only)...")
    all_findings = []
    for p in targets:
        try:
            all_findings.extend(scan_file(p))
        except Exception as e:  # never fail the run on one bad file
            print(f"WARN {p.name}: scanner error ({e})")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for item in all_findings:
            f.write(json.dumps(item) + "\n")
    n_high = sum(1 for x in all_findings if x.get("severity") == "high")
    print(f"Files scanned: {len(targets)} | findings: {len(all_findings)} "
          f"({n_high} high) -> {OUT_PATH.relative_to(ROOT).as_posix()}")
    # Always exit 0: this is a queue builder for human review, never a gate,
    # and it must never delete or modify data/ files.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
