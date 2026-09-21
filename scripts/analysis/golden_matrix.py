"""Multi-source golden set + engine matrix.

Ground truth established by direct visual reading of rendered pages (2026-09-21),
not by trusting any extractor. Scores each engine on cell-level recall.

Usage: python scripts/analysis/golden_matrix.py
"""
import json
import os
import re
import sys
import warnings

REPO = "C:/Users/Dell/Github/Shipping/"

GOLDEN = {
    # Athenian Shipbrokers Ship Recycling, Week 24 2026 (page 1)
    # HISTORICAL DEMOLITION PRICES table, read from the render
    "demolition_athenian": {
        "pdf": REPO + "reports/hellenic/demolition/pdfs/"
                     "2026-06-16_gms-week-24-premium-cracks-pen-hovers_"
                     "week-24-athenian-demolition-report-2_03f79e746643.pdf",
        "page": 0,
        "table_cells": ["482", "405", "435", "425", "300", "440", "380", "410",
                        "570", "550", "520", "475", "385", "445",
                        "456", "375", "400", "285", "280", "425", "370", "390",
                        "555", "445"],
        "circle_prices": ["415", "450", "460", "276", "435", "470", "475", "286",
                          "445", "480", "485", "296"],
        "bar_values": ["40", "55.8", "47", "34.3", "38.8", "44.6", "35.3", "30.4",
                       "16.9", "23.2", "23.7", "12.5", "10.5", "9.85", "11.45", "4.35"],
    },
    # Seabrokers August 2026 (page index 6): 4x7 OSV rates table.
    # Ground truth from the committed markdown mirror, itself verified against PDF.
    # NOTE 2026-09-21: an earlier version of this golden set pointed at page 1
    # (the contents page) and wrongly concluded the table was image-only. The
    # values are in the text layer on page index 6.
    "seabrokers_aug": {
        "pdf": REPO + "data/reports/seabrokers/pdfs/2026-08-01_market-report-august-2026.pdf",
        "page": 6,
        "table_cells": ["18,000", "4,737", "279.99", "15,000", "20,000",
                        "21,445", "5,925", "261.94", "9,000", "31,000",
                        "62,332", "15,899", "292.05", "38,517", "117,359",
                        "96,015", "16,024", "499.19", "34,237", "195,598"],
    },
    # Star Asia W35 2026 (page 3): S&P fixtures + vessel values
    "star_asia": {
        "pdf": REPO + "reports/shipbrokers/star_asia/2026/"
                     "star_asia_2026_W35_Market-Report-Week-35.pdf",
        "page": 2,
        "table_cells": ["princess eternity", "182,263", "78.0", "mount dampier",
                        "38.0", "sidra", "19.2", "spar scorpio", "11.25",
                        "arklow spirit", "16.6", "glory bridge", "7.5",
                        "bdi", "3,186"],
    },
    # SSY Atlantic Capesize index 14 Sep 2026 (page 1)
    "ssy_atlantic": {
        "pdf": REPO + "reports/shipbrokers/ssy/2026/"
                     "ssy_14_09_2026_ssy_atlantic_capesize_index_14_september_2026.pdf",
        "page": 0,
        "table_cells": ["atlantic capesize", "narvik/rotterdam", "10.65", "10.40",
                        "tubarao/qingdao", "41.50", "42.10", "calculated index",
                        "18,137", "17,887", "+1,780", "-250", "+8,477", "+7,872"],
    },
    # Breakwave Dry Bulk 15 Sep 2026 (page 2): fundamentals table
    "breakwave_dry": {
        "pdf": REPO + "reports/drybulk/2026/2026-09-15_Breakwave_Dry_Bulk.pdf",
        "page": 1,
        "table_cells": ["dry bulk fundamentals", "china steel production",
                        "iron ore", "ytd", "yoy", "bdi"],
    },
}


def norm(s):
    return re.sub(r"\s+", " ", str(s)).casefold().strip()


def score(text, cells, label):
    t = norm(text)
    hits = [c for c in cells if norm(c) in t]
    return {"label": label, "hits": len(hits), "total": len(cells),
            "recall": round(len(hits) / max(1, len(cells)), 3),
            "missed": [c for c in cells if c not in hits]}


def run_camelot(pdf, page):
    import camelot
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tabs = camelot.read_pdf(pdf, pages=str(page + 1), flavor="stream")
        return "\n".join(tabs[i].df.to_csv(index=False, header=False, lineterminator="\n")
                                 for i in range(tabs.n))


def run_camelot_lattice(pdf, page):
    import camelot
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tabs = camelot.read_pdf(pdf, pages=str(page + 1), flavor="lattice")
        return "\n".join(tabs[i].df.to_csv(index=False, header=False, lineterminator="\n")
                                 for i in range(tabs.n))


def run_plumber(pdf, page):
    import pdfplumber
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pdfplumber.open(pdf) as pl:
            p = pl.pages[page]
            return "\n".join(
                " ".join("" if c is None else str(c) for c in row)
                for t in p.find_tables() for row in t.extract())


def run_plumber_text(pdf, page):
    """Plumber page text, not table-structured: catches circle/bar labels."""
    import pdfplumber
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pdfplumber.open(pdf) as pl:
            return pl.pages[page].extract_text() or ""


def run_tabula(pdf, page):
    try:
        import tabula
        dfs = tabula.read_pdf(pdf, pages=page + 1, multiple_tables=True, stream=True)
        return "\n".join(d.to_csv(index=False, header=False, lineterminator="\n") for d in dfs)
    except Exception as exc:
        return f"__ERROR__ {exc}"


def run_pymupdf_text(pdf, page):
    import pymupdf
    d = pymupdf.open(pdf)
    t = d[page].get_text()
    d.close()
    return t


ENGINES = [
    ("camelot-stream", run_camelot),
    ("camelot-lattice", run_camelot_lattice),
    ("pdfplumber-tables", run_plumber),
    ("tabula-stream", run_tabula),
    ("plumber-text", run_plumber_text),
    ("pymupdf-text", run_pymupdf_text),
]


def main():
    matrix = {}
    for src, spec in GOLDEN.items():
        pdf = spec["pdf"]
        if not os.path.exists(pdf):
            print(f"SKIP {src}: missing")
            continue
        cells = spec["table_cells"]
        extra = {}
        if "circle_prices" in spec:
            extra["circle+bar values"] = spec["circle_prices"] + spec["bar_values"]
        print(f"\n=== {src}  ({len(cells)} table cells"
              f"{', ' + str(len(spec['circle_prices']) + len(spec['bar_values'])) + ' other values' if extra else ''})")
        out = {}
        for name, fn in ENGINES:
            try:
                txt = fn(pdf, spec["page"])
            except Exception as exc:
                out[name] = {"error": f"{type(exc).__name__}: {exc}"[:90]}
                print(f"  {name:20s} ERROR {out[name]['error']}")
                continue
            r = score(txt, cells, name)
            line = f"  {name:20s} table {r['hits']:2d}/{r['total']:2d} ({r['recall']:.0%})"
            if extra:
                re_ = score(txt, extra["circle+bar values"], name)
                line += f"   circle+bar {re_['hits']:2d}/{re_['total']:2d}"
                r["circle_bar_hits"] = re_["hits"]
                r["circle_bar_total"] = re_["total"]
            print(line)
            if r["missed"]:
                print(f"      missed: {r['missed'][:8]}")
            out[name] = r
        matrix[src] = out
    with open(REPO + "scripts/analysis/golden_matrix.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(matrix, f, indent=1)
    print("\n-> scripts/analysis/golden_matrix.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
