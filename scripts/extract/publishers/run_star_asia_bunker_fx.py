"""
Star Asia weekly: the BUNKER PRICES (USD/ton) and EXCHANGE RATES tables -> two series.

Both tables are printed in every issue (2022 W29 onwards) on the commodities page; the MDs of the
older layouts carry them in several broken shapes (rows of one table inside the other, ports split
over a page break), so they are read from the PDF text layer, where every row prints the same way:

  bunkers:  PORT  price  price  price        (grades from the header: VLSFO (0.5%), HSFO (3.5%) or
                                              IFO380 CST in 2022, MGO (0.1%); a "$" and commas may print)
  FX:       USD / CNY (CHINA)  this week  last week  W-O-W % CHANGE

A price the issue leaves blank (2024 W12 Houston MGO) gives no row. The W-O-W % is kept as printed.

Output: data/extracted/series/star_asia_bunker_series.csv  (issue_date, report_week, port, grade,
          price_usd_t, source_file)
        data/extracted/series/star_asia_fx_series.csv      (issue_date, report_week, currency_pair,
          country, rate, rate_prev_week, wow_pct_printed, source_file)

    python scripts/extract/publishers/run_star_asia_bunker_fx.py [--corpus DIR]   rebuild both series
    python scripts/extract/publishers/run_star_asia_bunker_fx.py --new-only       append issues not in them
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "corpus" / "01-brokers" / "star_asia"
MD = ROOT / "data" / "extracted" / "md" / "star_asia"
SERIES = ROOT / "data" / "extracted" / "series"
BUNKER_CSV, FX_CSV = SERIES / "star_asia_bunker_series.csv", SERIES / "star_asia_fx_series.csv"
BUNKER_COLS = ["issue_date", "report_week", "port", "grade", "price_usd_t", "source_file"]
FX_COLS = ["issue_date", "report_week", "currency_pair", "country", "rate", "rate_prev_week", "wow_pct_printed",
           "source_file"]

PORTS = ("SINGAPORE", "HONG KONG", "FUJAIRAH", "ROTTERDAM", "HOUSTON")
GRADE = re.compile(r"VLSFO \(0\.5%\)|HSFO \(3\.5%\)|IFO380 CST|MGO \(0\.1%\)")
PRICE = r"\$?(\d[\d,]*(?:\.\d+)?)"
FX = re.compile(r"USD\s*/\s*([A-Z]{3})\s*\(([A-Za-z .]+)\)\s+(\d[\d,]*(?:\.\d+)?)\s+(\d[\d,]*(?:\.\d+)?)\s+"
                r"([+\-–]?\s?\d+(?:\.\d+)?%?)(?![\d.])")


def _text(pdf: Path) -> str:
    with pymupdf.open(pdf) as doc:
        return re.sub(r"\s+", " ", " ".join(p.get_text() for p in doc))


def bunker_rows(t: str) -> list[dict]:
    i = t.find("VLSFO (0.5%)")
    if i < 0:
        return []
    grades = GRADE.findall(t[i:i + 60])
    if len(grades) != 3:
        return []
    seg = t[i:i + 4000]
    rows = []
    for port in PORTS:
        m = re.search(re.escape(port) + r"\s+" + PRICE + r"(?:\s+" + PRICE + r")?(?:\s+" + PRICE + r")?(?![\d.,])", seg)
        if not m:
            continue
        for g, v in zip(grades, m.groups()):
            if v:
                rows.append({"port": port.title(), "grade": g, "price_usd_t": float(v.replace(",", ""))})
    return rows


def _rate(s: str) -> float:
    # "82,93" (2024 W08 INR, printed change +0.10% against 83.01) is a decimal comma, not a thousands one
    return float(s.replace(",", ".") if re.fullmatch(r"\d{1,3},\d{2}", s) else s.replace(",", ""))


def fx_rows(t: str) -> list[dict]:
    rows, seen = [], set()
    for cur, country, rate, prev, wow in FX.findall(t):
        if cur in seen:
            continue
        seen.add(cur)
        rows.append({"currency_pair": f"USD/{cur}", "country": country.replace(".", "").strip().title(),
                     "rate": _rate(rate), "rate_prev_week": _rate(prev),
                     "wow_pct_printed": wow.replace(" ", "").replace("–", "-")})
    return rows


def _issue(stem: str) -> tuple[str, str] | None:
    """issue_date and report_week from the issue's MD frontmatter (the dates every star_asia series uses)."""
    md = next(MD.rglob(f"{stem}.md"), None)
    if md is None:
        return None
    head = md.read_text(encoding="utf-8")[:2000]
    d = re.search(r'^issue_date:\s*"?([\d-]{10})', head, re.M)
    w = re.search(r"^report_week:\s*(\d+)", head, re.M)
    return (d.group(1), w.group(1)) if d and w else None


def rows_for_pdf(pdf: Path) -> tuple[list[dict], list[dict]] | None:
    iss = _issue(pdf.stem)
    if iss is None:
        return None
    t = _text(pdf)
    base = {"issue_date": iss[0], "report_week": iss[1]}
    src = f"corpus/01-brokers/star_asia/{pdf.parent.name}/{pdf.name}"
    b = [dict(base, **r, source_file=src) for r in bunker_rows(t)]
    f = [dict(base, **r, source_file=src) for r in fx_rows(t)]
    return b, f


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    rows.sort(key=lambda r: (r["issue_date"], str(r.get("port", r.get("currency_pair")))))
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=CORPUS, help="folder holding the Star Asia PDFs")
    ap.add_argument("--new-only", action="store_true", help="append issues not in the series yet")
    a = ap.parse_args(argv)
    old_b, old_f = (_read(BUNKER_CSV), _read(FX_CSV)) if a.new_only else ([], [])
    have = {r["issue_date"] for r in old_b} | {r["issue_date"] for r in old_f}
    new_b, new_f, done, partial = [], [], set(), []
    for pdf in sorted(a.corpus.rglob("*.pdf")):
        got = rows_for_pdf(pdf)
        if got is None or not (got[0] or got[1]):
            continue
        b, f = got
        date = (b or f)[0]["issue_date"]
        if date in have or date in done:      # the same issue collected under two file names
            continue
        done.add(date)
        new_b += b
        new_f += f
        if len(b) < 15 or len(f) < 5:
            partial.append(f"{pdf.stem} bunker={len(b)} fx={len(f)}")
    _write(BUNKER_CSV, BUNKER_COLS, old_b + new_b)
    _write(FX_CSV, FX_COLS, old_f + new_f)
    print(f"star asia bunker/fx: +{len(new_b)} bunker rows, +{len(new_f)} fx rows from {len(done)} issues")
    for p in partial:
        print("  partial:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
