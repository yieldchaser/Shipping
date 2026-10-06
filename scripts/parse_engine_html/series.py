"""Series CSVs (sales, matrix) from parsed issues + comparison with the existing series files."""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from scripts.parse_engine_html.render import IssueContext

SALES_FIELDS = (
    "issue_date", "sector", "vessel_name", "vessel_class", "dwt_spec", "built_date", "yard", "buyer",
    "price_usd_m", "vv_value_usd_m", "premium_pct", "comments", "source_file",
    "size", "size_unit", "built_iso", "seller", "n_vessels", "en_bloc", "action", "price_raw", "flags",
)
MATRIX_FIELDS = (
    "issue_date", "sector", "vessel_class", "benchmark_size", "age_years", "pct_change_weekly", "source_file",
    "benchmark_size_num",
)


def _num(x) -> str:
    if x is None:
        return ""
    return f"{x:.4f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def sales_rows(ctxs: list[IssueContext]) -> list[dict]:
    rows = []
    for ctx in ctxs:
        a = ctx.article
        for s in a.sectors:
            for d in s.deals:
                rows.append({
                    "issue_date": a.issue_date.isoformat(), "sector": s.name,
                    "vessel_name": d.vessel_name, "vessel_class": d.vessel_class,
                    "dwt_spec": f"{d.size_text} {d.size_unit}".strip(), "built_date": d.built_text,
                    "yard": d.yard, "buyer": d.buyer, "price_usd_m": _num(d.price_usd_m),
                    "vv_value_usd_m": _num(d.vv_value_usd_m), "premium_pct": _num(d.premium_pct),
                    "comments": d.comments_all, "source_file": a.source_file,
                    "size": _num(d.size), "size_unit": d.size_unit, "built_iso": d.built or "",
                    "seller": d.seller, "n_vessels": _num(d.n_vessels),
                    "en_bloc": "1" if "en_bloc" in d.flags else "", "action": d.action,
                    "price_raw": d.price_raw, "flags": ";".join(d.flags),
                })
    return rows


def matrix_series_rows(ctxs: list[IssueContext]) -> list[dict]:
    rows = []
    for ctx in ctxs:
        if ctx.matrix is None or ctx.matrix.status != "ok":
            continue
        for c in ctx.matrix.cells:
            if c.pct is None:          # N/A cell: no observation
                continue
            verified = (c.age, c.group, c.column) not in ctx.unverified_refs
            rows.append({
                "issue_date": ctx.article.issue_date.isoformat(), "sector": c.group, "vessel_class": c.column,
                "benchmark_size": c.ref_text if verified else "", "age_years": c.age,
                "pct_change_weekly": _num(c.pct), "source_file": ctx.article.source_file,
                "benchmark_size_num": _num(c.ref_size) if verified else "",
            })
    return rows


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def by_year(rows: list[dict]) -> dict[str, int]:
    return dict(sorted(Counter((r.get("issue_date") or "????")[:4] for r in rows).items()))


def issues(rows: list[dict]) -> set[str]:
    return {r["issue_date"] for r in rows if r.get("issue_date")}


def compare(new_sales: list[dict], new_matrix: list[dict], existing_dir: Path) -> dict:
    old_sales = read_csv(existing_dir / "hellenic_vv_sales_series.csv")
    old_matrix = read_csv(existing_dir / "hellenic_vv_matrix_series.csv")
    out = {}
    for name, new, old in (("sales", new_sales, old_sales), ("matrix", new_matrix, old_matrix)):
        ni, oi = issues(new), issues(old)
        out[name] = {
            "existing_rows": len(old), "staged_rows": len(new),
            "existing_by_year": by_year(old), "staged_by_year": by_year(new),
            "existing_issues": len(oi), "staged_issues": len(ni),
            "issues_only_in_existing": sorted(oi - ni), "issues_only_in_staged": sorted(ni - oi),
        }
    per_issue_old = Counter(r["issue_date"] for r in old_matrix)
    per_issue_new = Counter(r["issue_date"] for r in new_matrix)
    out["matrix"]["existing_cells_per_issue_median"] = _median(list(per_issue_old.values()))
    out["matrix"]["staged_cells_per_issue_median"] = _median(list(per_issue_new.values()))
    return out


def _median(vals: list[int]) -> float:
    if not vals:
        return 0
    vals = sorted(vals)
    n = len(vals)
    return float(vals[n // 2]) if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
