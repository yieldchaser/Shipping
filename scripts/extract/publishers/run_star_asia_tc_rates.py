"""
Star Asia weekly: the "12 MONTHS T/C RATES AVERAGE (IN USD/DAY)" tables (bulker and tanker) -> one series.

Star Asia printed the two tables from the first issue in the corpus (2022 W29) to 2024 W50 (111 issues;
2025-2026 issues no longer carry them). They are read from the PDF text layer, not from the MD: the MD tables of these years come in several
shapes (merged headers, rows under other titles), while the text layer prints every row the same way:
TYPE, DWT, CURRENT, LAST WEEK, LAST YEAR, W-O-W %, Y-O-Y %.

A row is a known vessel type followed by those seven fields, on a page that carries the table title. The
printed percentages are the control: a row is kept only when at least one of them reproduces from the
rates ((current - previous) / previous, within 0.06 points), which rejects rows of the valuation tables
on the same pages (VLCC 310,000 126 125 100 ...). Where only one reproduces, the other is a print slip
(a flipped sign, the W-o-W figure printed again as Y-o-Y, Y-o-Y taken against the current rate); the row is
kept with the percentages as printed and the slip named in `check`.

Output: data/extracted/series/star_asia_tc_rates_series.csv
  issue_date, report_week, sector, vessel_type, dwt, rate_usd_day, last_week_usd_day, last_year_usd_day,
  wow_pct_printed, yoy_pct_printed, check, page, source_file

    python scripts/extract/publishers/run_star_asia_tc_rates.py [--corpus DIR]
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
OUT = ROOT / "data" / "extracted" / "series" / "star_asia_tc_rates_series.csv"
COLS = ["issue_date", "report_week", "sector", "vessel_type", "dwt", "rate_usd_day", "last_week_usd_day",
        "last_year_usd_day", "wow_pct_printed", "yoy_pct_printed", "check", "page", "source_file"]

TITLE = re.compile(r"12\s+MONTHS\s+T/C\s+RATES\s+AVERAGE", re.I)
BULK = ("CAPESIZE", "CAPE", "PANAMAX", "SUPRAMAX", "HANDYSIZE")
TANK = ("VLCC", "SUEZMAX", "AFRAMAX", "LR2", "LR1", "MR")
PCT = r"([+\-]?\s?\d+(?:\.\d+)?%?)"
ROW = re.compile(r"(?<![A-Z0-9])(" + "|".join(BULK + TANK) + r")\s+([\d,]{5,7})\s+([\d,]{3,7})\s+([\d,]{3,7})\s+"
                 r"([\d,]{3,7})\s+" + PCT + r"\s+" + PCT + r"(?![\d.])")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _pct(s: str) -> float:
    return float(s.replace("%", "").replace(" ", ""))


def _reproduces(cur: float, prev: float, printed: str) -> bool:
    return prev != 0 and abs((cur - prev) / prev * 100 - _pct(printed)) <= 0.06


def tc_rows(pdf: Path) -> list[dict]:
    rows, seen = [], set()
    with pymupdf.open(pdf) as doc:
        for page in doc:
            text = re.sub(r"\s+", " ", page.get_text())
            if not TITLE.search(text):
                continue
            for m in ROW.finditer(text):
                ty, dwt, cur, lw, ly, wow, yoy = m.groups()
                if (ty, cur, lw, ly) in seen:
                    continue
                c, l1, l2 = _num(cur), _num(lw), _num(ly)
                a, b = _reproduces(c, l1, wow), _reproduces(c, l2, yoy)
                if not (a or b):
                    continue
                seen.add((ty, cur, lw, ly))
                rows.append({
                    "sector": "Bulker" if ty in BULK else "Tanker",
                    "vessel_type": "CAPESIZE" if ty == "CAPE" else ty,
                    "dwt": int(_num(dwt)), "rate_usd_day": int(c), "last_week_usd_day": int(l1),
                    "last_year_usd_day": int(l2), "wow_pct_printed": wow.replace(" ", ""),
                    "yoy_pct_printed": yoy.replace(" ", ""),
                    "check": "" if a and b else ("w-o-w" if not a else "y-o-y") + " % as printed does not reproduce",
                    "page": page.number + 1,
                })
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=CORPUS, help="folder holding the Star Asia PDFs")
    a = ap.parse_args(argv)
    out, skipped = [], []
    for pdf in sorted(a.corpus.rglob("*.pdf")):
        rows = tc_rows(pdf)
        if not rows:
            continue
        iss = _issue(pdf.stem)
        if iss is None:
            skipped.append(pdf.name)
            continue
        src = f"corpus/01-brokers/star_asia/{pdf.parent.name}/{pdf.name}"
        out += [dict(r, issue_date=iss[0], report_week=iss[1], source_file=src) for r in rows]
    out.sort(key=lambda r: (r["issue_date"], r["sector"]))
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"star asia t/c rates: {len(out)} rows from {len({r['issue_date'] for r in out})} issues"
          f" ({sum(1 for r in out if r['check'])} with a printed % slip); no MD for: {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
