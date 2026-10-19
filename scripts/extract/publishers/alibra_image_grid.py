"""Alibra TC tables checked against the table image itself.

LlamaParse reads the yellow "unchanged" dash as "-" (down), drops whole tenor columns on some issues and
leaves marker glyphs in the size labels. This module re-reads the image:
  - trend: the marker colour in each cell (red down-triangle, green/teal up-triangle, yellow/orange dash),
    clustered into a rows x columns grid; a grid that does not have exactly one marker per cell is unreadable
  - rate: local OCR (rapidocr) of the number tokens, clustered into rows of exactly ncols numbers
and rebuilds the rows only when everything agrees on the table's shape. A table that cannot be made
complete is dropped (no rows) rather than written half-right.
"""
from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image

DRY_COLS = [("6 MOS", "ATL"), ("6 MOS", "PAC"), ("1 YR", "ATL"), ("1 YR", "PAC"), ("2 YR", "ATL"), ("2 YR", "PAC")]
TNK_COLS = [("1 YR", False), ("2 YR", False), ("3 YR", True), ("5 YR", True)]   # 3/5 YEAR* = eco tonnage
NUMTOK = re.compile(r"^\$?(\d{1,3}(?:[,.]\d{3})|\d{4,6})$")
# OCR / parse misreads of the size labels -> the label the image prints (each checked on an image)
LABEL = {
    "CAPE SIZE": "CAPESIZE", "S MAX/ULTRA": "SMAX/ULTRA", "PANAMA/MAX": "PANA/KMAX", "PANAK/MAX": "PANA/KMAX",
    "PANAJ/MAX": "PANA/KMAX", "Pana/KMAX": "PANA/KMAX", "HANDY (38k det)": "HANDY (38k dwt)",
    "HANDY (38k dat)": "HANDY (38k dwt)", "HANDY (35k dwt)": "HANDY (38k dwt)", "HANDY (30k dwt)": "HANDY (38k dwt)",
}
_ocr = None


def clean_label(s: str) -> str:
    s = re.sub(r"~~|[*_]", "", s)
    s = re.sub(r"[▲▼—–]|-01$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return LABEL.get(s, s)


def markers(img_path: Path):
    im = Image.open(img_path).convert("RGB")
    if im.width > 800:   # sizes/gaps below are tuned on the usual 600 px image; 2026-10-14 came at 1717 px
        im = im.resize((600, round(im.height * 600 / im.width)), Image.BOX)
    a = np.asarray(im).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # row backgrounds (blue, pale green) have g-b <= 20 and g-r <= 25
    masks = {
        "down": (r > 170) & (g < 150) & (r - g > 80) & (r - b > 80),
        "up": (g > 110) & (r < 140) & (g - r > 40) & (g >= b - 10),
        "flat": (r > 180) & (g > 150) & (r - g > -30) & (r - g < 90) & (g - b > 45),
    }
    out = []
    for name, m in masks.items():
        n, _, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
        for x, y, w, h, area in stats[1:]:
            if area >= 6 and w <= 40 and h <= 30:
                out.append((name, x + w / 2, y + h / 2, int(area)))
    return out


def _clusters(vals, gap):
    vals = sorted(vals)
    cl, cur = [], [vals[0]]
    for v in vals[1:]:
        if v - cur[-1] > gap:
            cl.append(cur)
            cur = []
        cur.append(v)
    cl.append(cur)
    return [(sum(c) / len(c), len(c)) for c in cl]


def trend_grid(ms, ncols: int, nrows: int) -> Optional[List[List[str]]]:
    """Choose ncols marker columns (from the best-populated few) such that exactly nrows rows have a marker
    under every column; each cell must be dominated (3x area) by one colour. None when not exactly one fit."""
    if not ms:
        return None
    cands = sorted(_clusters([m[1] for m in ms], 15), key=lambda c: -c[1])[:ncols + 3]
    if len(cands) < ncols:
        return None

    def cell(yc, xc):
        area: Dict[str, int] = {}
        for m in ms:
            if abs(m[1] - xc) <= 8 and abs(m[2] - yc) <= 7:
                area[m[0]] = area.get(m[0], 0) + m[3]
        return area

    yall = [yc for yc, _ in _clusters([m[2] for m in ms], 8)]
    fits = []
    for xs in combinations(sorted(c[0] for c in cands), ncols):
        ys = [yc for yc in yall if all(cell(yc, xc) for xc in xs)]
        if len(ys) == nrows:
            fits.append((xs, ys))
    if len(fits) != 1:
        return None
    xs, ys = fits[0]
    out = []
    for yc in ys:
        row = []
        for xc in xs:
            area = sorted(cell(yc, xc).items(), key=lambda kv: -kv[1])
            if len(area) > 1 and area[0][1] < 3 * area[1][1]:
                return None
            row.append(area[0][0])
        out.append(row)
    return out


def ocr_rates(img_path: Path, ncols: int) -> List[List[int]]:
    """Rows (top to bottom) that hold exactly ncols number tokens, read left to right."""
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    res, _ = _ocr(str(img_path))
    toks = []
    for box, txt, _conf in res or []:
        m = NUMTOK.match(txt.replace(" ", ""))
        if m:
            toks.append((sum(p[0] for p in box) / 4, sum(p[1] for p in box) / 4,
                         int(re.sub(r"[,.]", "", m.group(1)))))
    toks.sort(key=lambda t: t[1])
    rows, cur = [], []
    for t in toks:
        if cur and t[1] - cur[-1][1] > 9:
            rows.append(cur)
            cur = []
        cur.append(t)
    if cur:
        rows.append(cur)
    return [[t[2] for t in sorted(r)] for r in rows if len(r) == ncols]


def verify_rows(rows: List[Dict[str, Any]], img_path: Optional[Path], cat: str, log=print) -> List[Dict[str, Any]]:
    """Return the table rows rebuilt against the image: cleaned labels, OCR rates, marker trends.
    [] when the table cannot be made complete (every class needs every column)."""
    if not rows or img_path is None:
        return rows
    dry = cat == "dry"
    cols = DRY_COLS if dry else TNK_COLS
    keys = [c if dry else c[0] for c in cols]
    proto = rows[0]
    classes = list(dict.fromkeys(clean_label(r["vessel_class"]) for r in rows))
    grid: Dict[str, Dict[Any, Dict[str, Any]]] = {}
    for r in rows:
        k = (r["tenor"], r["basin"]) if dry else r["tenor"]
        grid.setdefault(clean_label(r["vessel_class"]), {})[k] = r

    ocr = ocr_rates(img_path, len(cols))
    if len(ocr) == len(classes):
        rates = ocr
    elif all(len(grid[c]) == len(cols) for c in classes):
        rates = [[grid[c][k]["rate_usd_pdpr"] for k in keys] for c in classes]
        log(f"  [alibra] OCR found {len(ocr)} rows for {len(classes)} classes; rates kept from the parse: {img_path.name}")
    else:
        log(f"  [alibra] table incomplete and OCR cannot complete it -> no rows: {img_path.name}")
        return []
    for c, row in zip(classes, rates):
        for k, v in zip(keys, row):
            old = grid[c].get(k, {}).get("rate_usd_pdpr")
            if old is not None and old != v:
                log(f"  [alibra] {img_path.name} {c} {k}: parse {old} -> image {v}")

    trends = trend_grid(markers(img_path), len(cols), len(classes))
    if trends is None:
        log(f"  [alibra] marker grid unreadable, trend from the parse: {img_path.name}")
    out = []
    for i, c in enumerate(classes):
        for j, (col, k) in enumerate(zip(cols, keys)):
            if trends is not None:
                tr = trends[i][j]
            elif k in grid[c]:
                tr = grid[c][k]["trend"]
            else:
                log(f"  [alibra] {c} {k}: no trend from image or parse -> no rows: {img_path.name}")
                return []
            rec = {"issue_date": proto["issue_date"], "vessel_class": c}
            if dry:
                rec.update(tenor=col[0], basin=col[1], rate_usd_pdpr=rates[i][j], trend=tr)
            else:
                rec.update(tenor=col[0], rate_usd_pdpr=rates[i][j], eco_scrubber=col[1], trend=tr)
            rec["source_file"] = proto["source_file"]
            out.append(rec)
    return out
