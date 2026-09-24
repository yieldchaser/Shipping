"""intermodal chart values vs the page's OWN printed table - an independent control.

Every intermodal page prints a 'Baltic Indices' table with the CURRENT value of BDI, BCI,
BPI, BSI and BHSI, beside the chart. The chart's last plotted reading should equal that
current value. The two come from completely different machinery - the table from the text
layer, the chart from vector geometry and an axis interpolation - so agreement is a real
control, not a self-check.

This is the check that catches a bad calibration, a wrong series-to-legend colour match
and a mis-clustered scale, none of which the fit's own error metric can see.

Run:  python3 -B scratch/verify_intermodal_charts.py
"""
from __future__ import annotations

import glob
import importlib.util
import re
import sys
from pathlib import Path

import pymupdf

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ic", REPO / "scripts" / "extract" / "publishers" / "run_intermodal_charts.py")
ic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ic)

TICKERS = ("BDI", "BCI", "BPI", "BSI", "BHSI")


def printed_table(pdf):
    """{ticker: current value} from the Baltic Indices table on page 3.

    READ BY GEOMETRY, NOT BY LINE. Each cell of the table is its own text line: measured
    2026 W35 page 3, the lines are literally 'BDI', 'BCI', 'BPI', 'BSI', 'BHSI' with no
    numbers attached, and the figures follow as separate lines. A regex over the line
    therefore finds a ticker and no value, which is why a first version reported "no
    printed Baltic table found" on every document.

    The value is the nearest number to the RIGHT of the ticker on a similar baseline,
    inside the table's own x range. The table's first numeric column is CURRENT (the two
    columns are headed by the two report dates, current first), so the nearest number to
    the right is the current reading.
    """
    with pymupdf.open(pdf) as d:
        page = d[2]
        spans = []
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln["spans"]:
                    t = sp["text"].strip()
                    if t:
                        spans.append((sp["bbox"][0], sp["bbox"][1], t))
    out = {}
    for x, y, t in spans:
        if t not in TICKERS:
            continue
        # numbers on the same baseline, to the right, within the table's width
        cands = []
        for x2, y2, t2 in spans:
            if x2 <= x:
                continue
            if abs(y2 - y) > 3:
                continue
            m = re.fullmatch(r"[\d,]{3,}", t2)
            if m and x2 < x + 220:
                cands.append((x2, float(t2.replace(",", ""))))
        if cands:
            cands.sort()
            out.setdefault(t, cands[0][1])
    return out


def main(n=12):
    pdfs = sorted(glob.glob(str(REPO / "corpus" / "01-brokers" / "intermodal" / "*" / "*.pdf")))
    step = max(1, len(pdfs) // n)
    picks = pdfs[::step][:n]
    rows = []
    for p in picks:
        name = Path(p).name
        try:
            d = ic.extract(p)
        except Exception as e:                               # noqa: BLE001
            print(f"{name[:50]:<52} ERROR {e}")
            continue
        table = printed_table(p)
        if not table:
            print(f"{name[:50]:<52} no printed Baltic table found")
            continue
        # the chart whose ticks top out below 20,000 is the Baltic chart
        bal = next((c for c in d["charts"]
                    if c["ticks"] and c["ticks"][0]["v"] < 20000), None)
        if not bal:
            print(f"{name[:50]:<52} no Baltic chart in output")
            continue
        got = {s["name"]: s["last"] for s in bal["series"] if s["name"] in TICKERS}
        rel = []
        for t in TICKERS:
            if t in table and t in got and got[t] is not None:
                rel.append((t, table[t], got[t],
                            abs(got[t] - table[t]) / max(abs(table[t]), 1)))
        if not rel:
            print(f"{name[:50]:<52} nothing comparable")
            continue
        worst = max(rel, key=lambda z: z[3])
        detail = "  ".join(f"{t} {a:,.0f}->{b:,.0f}({g*100:.2f}%)" for t, a, b, g in rel)
        print(f"{name[:50]:<52} worst={worst[3]*100:5.2f}%  {detail}")
        rows.extend(x[3] for x in rel)
    if rows:
        rows.sort()
        n_ok = sum(1 for r in rows if r <= 0.05)
        print()
        print(f"COMPARISONS {len(rows)}   within 5%: {n_ok} ({100*n_ok/len(rows):.1f}%)")
        print(f"median {rows[len(rows)//2]*100:.3f}%   p90 {rows[int(len(rows)*0.9)]*100:.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 12))
