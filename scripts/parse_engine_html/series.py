"""Series CSVs (sales, matrix) from parsed issues + comparison with the existing series files."""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

from scripts.parse_engine_html.render import IssueContext

# vocabulary of the existing data/extracted/series files: singular sectors in the sales series ...
SALES_SECTOR = {"Bulkers": "Bulker", "Tankers": "Tanker", "Containers": "Container"}
SALES_FIELDS = (
    "issue_date", "sector", "vessel_name", "vessel_class", "dwt_spec", "built_date", "yard", "buyer",
    "price_usd_m", "vv_value_usd_m", "premium_pct", "comments", "source_file",
    "size", "size_unit", "built_iso", "seller", "n_vessels", "en_bloc", "action", "price_raw", "flags",
    "vessel_class_raw",
)
MATRIX_FIELDS = (
    "issue_date", "sector", "vessel_class", "benchmark_size", "age_years", "pct_change_weekly", "source_file",
    "benchmark_size_num",
)


# vessel_class vocabulary of the existing sales series; anything else keeps the verbatim class
LEGACY_CLASSES = {
    "VLCC", "Suezmax", "Aframax", "LR1", "LR2", "MR2", "MR", "Capesize", "Newcastlemax", "Kamsarmax", "Panamax",
    "Post Panamax", "Supramax", "Ultramax", "Handysize", "Feedermax", "Container", "General",
}
_CLASS_ALIAS = {"MRs": "MR", "Handy": "Handysize", "Sub-Panamax": "Sub Panamax", "Post-Panamax": "Post Panamax",
                "PostPanamax": "Post Panamax"}
_CLASS_SUFFIX = re.compile(r"\s+(?:BCs?|Bulkers?|Cont(?:ainer)?s?|Tankers?)$", re.I)


def canonical_class(sector: str, vessel_class: str) -> str:
    """Map a verbatim class ('Panamax BC', 'VLCCs', 'Handy Bulker', 'MR2 (Chem/Product)') to the vocabulary of the
    existing series files; a class outside that vocabulary is returned unchanged (never guessed)."""
    base = re.sub(r"\s*\([^)]*\)", "", vessel_class).strip()
    base = re.sub(r"[’']s$", "", base)
    base = _CLASS_SUFFIX.sub("", base).strip()
    if base == "Handy" and sector.lower().startswith("tanker"):
        return "Handy Tanker"
    for cand in (base, base[:-1] if base.endswith("s") else base, base[:-2] if base.endswith("es") else base):
        cand = _CLASS_ALIAS.get(cand, cand)
        if cand == "Handysize" or cand in LEGACY_CLASSES:
            return cand
    return vessel_class


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
                    "issue_date": a.issue_date.isoformat(), "sector": SALES_SECTOR.get(s.name, s.name),
                    "vessel_name": d.vessel_name,
                    "vessel_class": canonical_class(s.name, d.vessel_class), "vessel_class_raw": d.vessel_class,
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
        if ctx.matrix.image_date != ctx.article.issue_date.isoformat():
            continue                    # the image is another week's table: never filed under this issue date
        for c in ctx.matrix.cells:
            if c.pct is None:          # N/A cell: no observation
                continue
            verified = bool(c.ref_text)
            rows.append({
                "issue_date": ctx.article.issue_date.isoformat(), "sector": c.group, "vessel_class": f"{c.group} {c.column}",
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


def append_new_issues(path: Path, fields: tuple[str, ...], rows: list[dict]) -> int:
    """Append rows of issue dates that are not in the CSV yet, using the CSV's own header (so a file written by
    an older writer keeps its columns). Existing rows are never touched; returns the number of rows appended."""
    existing_dates: set[str] = set()
    header = list(fields)
    if path.exists() and path.stat().st_size > 0:
        with path.open(newline="", encoding="utf-8") as fh:
            rd = csv.DictReader(fh)
            header = list(rd.fieldnames or fields)
            existing_dates = {r.get("issue_date", "") for r in rd}
    new = [r for r in rows if r.get("issue_date") not in existing_dates]
    if not new:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore", lineterminator="\n")
        if fresh:
            w.writeheader()
        w.writerows(new)
    return len(new)


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
