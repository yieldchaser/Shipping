"""
Source #1: ADVANCED SHIPPING - per-publisher extraction pipeline.

Purpose: turn one broker's PDFs into faithful .md + typed tables + chart series,
verified page by page, before any other publisher is attempted.

Publisher-specific facts measured on W36 2021 (do not generalise without checking):
  * DECIMAL COMMAS. "34,5" means 34.5 and "1,37%" means 1.37%. Parsing these as
    thousands separators inflates every fractional value 10-100x. This is the
    same defect class that inflated 62,084 cells elsewhere in this project.
  * Charts are VECTOR on pp.1/2/5/8 (1458/1506/2243/1133 path segments) so the
    polylines are exact data; axis tick labels are positioned text.
  * p.7 bar charts are raster GRAPHICS but their values are printed as TEXT on
    top, so no vision is required there either.
  * Tables are ruled grids (rect-only pages 3,4,6,9,10).

Output layout (one directory per publisher, per the source-by-source plan):
  data/extracted/md/<publisher>/<stem>.md        readable doc, tables inline
  data/extracted/md/<publisher>/<stem>.tables.json  typed rows
  data/extracted/md/<publisher>/<stem>.charts.json  chart series
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

PUBLISHER = "advanced_shipping"
OUT_ROOT = Path("data/extracted/md") / PUBLISHER

# ---------------------------------------------------------- decimal commas
DEC = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d+)?$|^-?\d+,\d+$")


def parse_number(tok: str):
    """'34,5' -> 34.5 ; '1.234,5' -> 1234.5 ; '1,37%' -> 1.37 ; '55' -> 55.0

    Advanced Shipping writes decimal COMMAS. Treating ',' as a thousands
    separator would read 34,5 as 345 - a 10x error in the plausible direction.
    """
    if tok is None:
        return None
    s = str(tok).strip().replace("%", "").replace("$", "").strip()
    if not s:
        return None
    neg = s.startswith("-")
    s = s.lstrip("+-")
    if not re.fullmatch(r"[\d.,]+", s):
        return None
    # decimal comma: a comma followed by 1-2 digits at the end
    if re.search(r",\d{1,2}$", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


# ---------------------------------------------------------------- tables
def extract_tables(pdf: Path):
    """pdf-inspector won, measured, on every table liteparse broke."""
    import pdf_inspector as pi
    try:
        out = pi.process_pdf(str(pdf))
    except Exception as e:
        return [], f"pdf_inspector: {type(e).__name__}: {str(e)[:80]}"
    md = out if isinstance(out, str) else getattr(out, "markdown", None) or str(out)
    tables = []
    cur = None
    for line in md.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue                      # separator row
            if cur is None:
                cur = {"header": cells, "rows": []}
            else:
                cur["rows"].append(cells)
        else:
            if cur and cur["rows"]:
                tables.append(cur)
            cur = None
    if cur and cur["rows"]:
        tables.append(cur)
    return tables, None


# ---------------------------------------------------------------- charts
def _ticks(pg):
    """Axis tick labels: text with coordinates -> the chart's value scale."""
    out = []
    for blk in pg.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for ln in blk["lines"]:
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if re.fullmatch(r"\d{1,4}", t):
                x0, y0, x1, y1 = ln["bbox"]
                out.append({"x": x0, "y": (y0 + y1) / 2, "v": float(t)})
    return out


def _fit_scale(ticks):
    """value = a*y + b, from one chart's ticks only.

    Must be per-chart: this page stacks a 270-630 Bulkers chart over a 180-300
    Turkey chart in the same x column, and one fit across both gave 124.5 error.
    """
    if len(ticks) < 3:
        return None
    ys = [t["y"] for t in ticks]
    vs = [t["v"] for t in ticks]
    n = len(ys)
    sy, sv = sum(ys), sum(vs)
    syy = sum(y * y for y in ys)
    syv = sum(y * v for y, v in zip(ys, vs))
    den = n * syy - sy * sy
    if abs(den) < 1e-9:
        return None
    a = (n * syv - sy * sv) / den
    b = (sv - a * sy) / n
    err = max(abs((a * ys[i] + b) - vs[i]) for i in range(n))
    return {"a": a, "b": b, "max_err": round(err, 4), "n_ticks": n}


def _tick_groups(ticks, gap=30.0):
    """Split into per-CHART tick runs.

    Two things must be separated (both measured, both bugs the first time):
      1. side-by-side charts share a y range -> cluster by x column first
      2. stacked charts share an x column -> split by a y gap LARGER than the
         tick pitch (18.1pt within a chart, 78pt between stacked charts).
         A 6pt threshold split every individual tick into its own group.
    """
    if not ticks:
        return []
    # cluster by x column (ticks of different charts differ by >100pt in x)
    xs = sorted(t["x"] for t in ticks)
    col_groups, cur_col = [], [xs[0]]
    for x in xs[1:]:
        if x - cur_col[-1] > 40:
            col_groups.append(cur_col)
            cur_col = [x]
        else:
            cur_col.append(x)
    if cur_col:
        col_groups.append(cur_col)

    out = []
    for cg in col_groups:
        lo, hi = min(cg) - 5, max(cg) + 5
        col_ticks = sorted([t for t in ticks if lo <= t["x"] <= hi],
                           key=lambda t: t["y"])
        if not col_ticks:
            continue
        run = [col_ticks[0]]
        for t in col_ticks[1:]:
            if t["y"] - run[-1]["y"] > gap:
                if len(run) >= 3:
                    out.append(run)
                run = [t]
            else:
                run.append(t)
        if len(run) >= 3:
            out.append(run)
    return out


def extract_chart_series(pdf: Path, page_no: int):
    """Vector polylines -> values, calibrated by that chart's own ticks."""
    with pymupdf.open(pdf) as d:
        pg = d[page_no - 1]
        ticks = _ticks(pg)
        charts = []
        for g in _tick_groups(ticks):
            if len(g) < 3:
                continue
            scale = _fit_scale(g)
            # 0.05 was too tight for real ticks (font baseline jitter);
            # a wrong scale would show up as error on the order of the step.
            if not scale or scale["max_err"] > 0.6:
                continue
            y_lo = min(t["y"] for t in g)
            y_hi = max(t["y"] for t in g)
            # polylines inside this chart's y band, grouped by stroke colour
            series = {}
            for dr in pg.get_drawings():
                col = dr.get("color")
                if col is None:
                    continue
                pts = []
                for it in dr["items"]:
                    if it[0] == "l":
                        p0, p1 = it[1], it[2]
                        if y_lo - 2 <= p0.y <= y_hi + 2 and y_lo - 2 <= p1.y <= y_hi + 2:
                            pts.append((round(p0.x, 2), round(p0.y, 2)))
                if len(pts) >= 8:
                    key = ",".join(f"{c:.3f}" for c in col)
                    series.setdefault(key, []).extend(pts)
            if series:
                charts.append({
                    "scale": scale,
                    "series": {k: v[:400] for k, v in series.items()},
                })
        return {"ticks": ticks, "charts": charts}


def build_md(pdf: Path):
    """Readable markdown for the KB (liteparse, per page)."""
    import liteparse
    # output_format must be explicit or get_page(i).markdown comes back empty
    lp = liteparse.LiteParse(extract_blocks=True, quiet=True,
                             output_format="markdown", keep_headers_footers=True)
    res = lp.parse(str(pdf))
    lines = [f"# {pdf.stem}", "",
             f"source: `{pdf.as_posix()}`  |  pages: {res.num_pages}", ""]
    for i in range(1, res.num_pages + 1):
        lines.append(f"\n## Page {i}\n")
        lines.append((res.get_page(i).markdown or "").strip())
    return "\n".join(lines)


def process(pdf: Path):
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    tables, terr = extract_tables(pdf)
    with pymupdf.open(pdf) as dx:
        npages = dx.page_count
    charts = {}
    for p in range(1, npages + 1):
        c = extract_chart_series(pdf, p)
        good = [ch for ch in c.get("charts", []) if ch.get("series")]
        if good:
            charts[str(p)] = good
    md = build_md(pdf)
    stem = pdf.stem
    (OUT_ROOT / f"{stem}.md").write_text(md, encoding="utf-8")
    (OUT_ROOT / f"{stem}.tables.json").write_text(
        json.dumps(tables, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_ROOT / f"{stem}.charts.json").write_text(
        json.dumps(charts, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"stem": stem, "pages": npages, "tables": len(tables),
            "table_err": terr, "chart_pages": sorted(charts),
            "md_bytes": len(md)}


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        print(json.dumps(process(Path(arg)), indent=2, default=str))
