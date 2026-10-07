"""Coverage for matrix images the OCR could not validate: reuse the CURRENT series rows only where the current data
is demonstrably accurate.

1. Accuracy: every current row of an issue whose staged matrix is OK is compared cell by cell (percentage) with the
   staged value, per year.
2. A failed staged issue keeps its current rows only if (a) its year's accuracy is >= the threshold (default 98%)
   and (b) the issue's current rows are structurally valid: all 13 classes x 6 ages present exactly once, each class
   under its correct sector, no unknown class labels. Everything else is dropped and listed with the reason.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.parse_engine_html.matrix import AGES, COLUMNS
from scripts.parse_engine_html.series import MATRIX_FIELDS, read_csv, write_csv

THRESHOLD = 0.98
CLASS_TO_KEY = {f"{g} {c}": (g, c) for g, c in COLUMNS}


def staged_cells(tables_dir: Path) -> tuple[dict, set[str]]:
    """({(issue_date, group, column, age): pct}, failed issue dates) read from the staged .tables.json sidecars."""
    ok: dict = {}
    failed: set[str] = set()
    for p in sorted(tables_dir.glob("*/vv_*.tables.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        m = d.get("matrix")
        if not d.get("issue_date") or m is None:
            continue
        if m["status"] != "ok":
            failed.add(d["issue_date"])
            continue
        for c in m["cells"]:
            ok[(d["issue_date"], c["group"], c["column"], c["age"])] = c["pct"]
    return ok, failed


def accuracy_by_year(current: list[dict], ok: dict) -> dict[str, dict]:
    ok_dates = {k[0] for k in ok}
    stats: dict[str, Counter] = defaultdict(Counter)
    for r in current:
        if r["issue_date"] not in ok_dates:
            continue
        y = r["issue_date"][:4]
        key = CLASS_TO_KEY.get(r["vessel_class"].strip())
        if key is None:
            stats[y]["unknown_label"] += 1
            stats[y]["compared"] += 1
            continue
        age = int(r["age_years"]) if r["age_years"].isdigit() else -1
        if (r["issue_date"], key[0], key[1], age) not in ok:
            stats[y]["no_staged_cell"] += 1
            stats[y]["compared"] += 1
            continue
        want = ok[(r["issue_date"], key[0], key[1], age)]
        got = r["pct_change_weekly"]
        stats[y]["compared"] += 1
        try:
            same = want is not None and abs(float(got) - float(want)) < 1e-9
        except ValueError:
            same = False
        stats[y]["match" if same else "mismatch"] += 1
        if r["sector"] != key[0]:
            stats[y]["wrong_sector"] += 1
    out = {}
    for y, c in sorted(stats.items()):
        out[y] = {"compared": c["compared"], "match": c["match"], "mismatch": c["mismatch"],
                  "unknown_label": c["unknown_label"], "no_staged_cell": c["no_staged_cell"],
                  "wrong_sector": c["wrong_sector"],
                  "accuracy": round(c["match"] / c["compared"], 4) if c["compared"] else None}
    return out


def structural_problems(rows: list[dict]) -> list[str]:
    problems: list[str] = []
    seen = Counter()
    for r in rows:
        key = CLASS_TO_KEY.get(r["vessel_class"].strip())
        if key is None:
            problems.append(f"unknown class label {r['vessel_class']!r}")
            continue
        if r["sector"] != key[0]:
            problems.append(f"{r['vessel_class']} under sector {r['sector']!r}, expected {key[0]!r}")
        age = r["age_years"]
        if not age.isdigit() or int(age) not in AGES:
            problems.append(f"age {age!r} is not one of {AGES}")
            continue
        seen[(key, int(age))] += 1
    missing = [(g, c, a) for g, c in COLUMNS for a in AGES if (((g, c), a)) not in seen]
    if missing:
        problems.append(f"{len(missing)} of 78 class/age cells missing")
    dup = [k for k, n in seen.items() if n > 1]
    if dup:
        problems.append(f"{len(dup)} duplicated class/age cells")
    return list(dict.fromkeys(problems))


def build(tables_dir: Path, current_csv: Path, staged_csv: Path, out_csv: Path, report_json: Path,
          threshold: float = THRESHOLD) -> dict:
    ok, failed = staged_cells(tables_dir)
    current = read_csv(current_csv)
    acc = accuracy_by_year(current, ok)
    good_years = {y for y, a in acc.items() if a["accuracy"] is not None and a["accuracy"] >= threshold}
    by_issue: dict[str, list[dict]] = defaultdict(list)
    for r in current:
        by_issue[r["issue_date"]].append(r)
    kept, dropped, merged = [], [], read_csv(staged_csv)
    for d in sorted(failed):
        year = d[:4]
        rows = by_issue.get(d, [])
        if not rows:
            dropped.append({"issue_date": d, "reason": "no current rows"})
        elif year not in good_years:
            a = acc.get(year, {}).get("accuracy")
            dropped.append({"issue_date": d, "reason": f"year {year} current accuracy {a} < {threshold}"})
        else:
            probs = structural_problems(rows)
            if probs:
                dropped.append({"issue_date": d, "reason": "; ".join(probs)})
            else:
                kept.append(d)
                merged += [{k: r.get(k, "") for k in MATRIX_FIELDS} | {"benchmark_size_num": ""} for r in rows]
    merged.sort(key=lambda r: (r["issue_date"], r["sector"], r["vessel_class"], int(r["age_years"] or 0)))
    write_csv(out_csv, MATRIX_FIELDS, merged)
    report = {"threshold": threshold, "accuracy_by_year": acc, "years_meeting_threshold": sorted(good_years),
              "failed_staged_issues": len(failed), "kept_from_current": kept, "dropped": dropped,
              "merged_rows": len(merged)}
    report_json.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main_cli(out: Path, existing_series: Path, threshold: float = THRESHOLD) -> dict:
    series = out / "series"
    return build(out, existing_series / "hellenic_vv_matrix_series.csv", series / "hellenic_vv_matrix_series.csv",
                 series / "hellenic_vv_matrix_series_with_current_fallback.csv", out / "_fallback_report.json",
                 threshold)

