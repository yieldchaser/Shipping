"""
Intermodal T/C rate backfill - REUSES the existing validated parser.

Why reuse rather than write a new extractor: scripts/update_intermodal_tc_rates.py
already defines 20 validated RATE_FIELDS patterns, and a probe confirmed all 20
fire on PyMuPDF text taken straight from the PDFs, in EVERY year tested
(2021/2023/2024/2026: 20/20 each). So the field definitions are correct - only
the script's INPUT PATH is broken.

The breakage: the script reads *.md from `reports/broker_reports/2026`, a
directory DELETED in the corpus migration (22 scripts still reference it). Its
output CSV therefore stops at 2026-09-11 after only 49 rows, while the PDF corpus
holds 252 documents spanning 2021-2026.

This backfills from the PDFs - ground truth - using the same patterns, so the
existing CSV gets 5 years of history instead of 18 months and the field
definitions stay single-sourced.

Output: data/extracted/intermodal_tc_rates_backfill.csv  (a SEPARATE file - the
existing CSV is not overwritten, so the two can be compared before any merge.)
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import pymupdf  # noqa: E402
from update_intermodal_tc_rates import RATE_FIELDS  # noqa: E402

SRC = ROOT / "corpus" / "01-brokers" / "intermodal"
OUT = ROOT / "data" / "extracted" / "intermodal_tc_rates_backfill.csv"

# Assessment date: prefer the Tanker Chartering table header, then the doc's own
# date line, then the filename's week, in that order - the header is authoritative.
DATE_TBL = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
DATE_LONG = re.compile(
    r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{4})\b", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])}


def doc_date(text: str, path: Path):
    """Best-effort assessment date. Returns (iso, provenance)."""
    m = re.search(r"Tanker\s+Chartering\s*\n?\s*(\d{1,2})/(\d{1,2})/(\d{4})",
                  text, re.I)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}", "tanker-table-header"
    m = DATE_LONG.search(text)
    if m:
        d, mon, y = m.group(1), m.group(2).lower(), m.group(3)
        return f"{y}-{MONTHS[mon]:02d}-{int(d):02d}", "long-date-in-text"
    # filename week + year, as a last resort (no day precision)
    m = re.search(r"(20\d\d).*?W(\d{1,2})", path.name)
    if m:
        return f"{m.group(1)}-W{m.group(2).zfill(2)}", "filename-week"
    return None, None


def main():
    pdfs = sorted(SRC.rglob("*.pdf"))
    rows = []
    fails = []
    print(f"intermodal backfill: {len(pdfs)} PDFs", flush=True)
    for i, p in enumerate(pdfs, start=1):
        try:
            with pymupdf.open(p) as d:
                txt = "".join(pg.get_text() for pg in d)
            row = {"file": p.name}
            iso, prov = doc_date(txt, p)
            row["date"] = iso
            row["date_source"] = prov
            for name, pat in RATE_FIELDS:
                m = re.search(pat, txt, re.I)
                row[name] = int(m.group(1).replace(",", "")) if m else None
            nfill = sum(1 for n, _ in RATE_FIELDS if row[n] is not None)
            row["fields_filled"] = nfill
            rows.append(row)
            if i % 25 == 0 or i == len(pdfs):
                print(f"  [{i}/{len(pdfs)}] {p.name[:46]:<46} "
                      f"fields={nfill}/20 date={iso}", flush=True)
        except Exception as e:
            fails.append((p.name, f"{type(e).__name__}: {str(e)[:90]}"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        cols = ["file", "date", "date_source", "fields_filled"] + \
               [n for n, _ in RATE_FIELDS]
        with OUT.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in cols})

    complete = [r for r in rows if r["fields_filled"] == 20]
    print()
    print(f"[intermodal] files={len(rows)}  all-20-fields={len(complete)}  "
          f"failed={len(fails)}")
    dated = [r for r in rows if r["date"]]
    if dated:
        ds = sorted(r["date"] for r in dated if r["date"][:4].isdigit())
        if ds:
            print(f"date range: {ds[0]} .. {ds[-1]}")
    print(f"wrote {OUT}")
    if fails:
        print("failures:", fails[:8])


if __name__ == "__main__":
    main()
