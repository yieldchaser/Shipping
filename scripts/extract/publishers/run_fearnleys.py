"""
Source 5: FEARNLEYS - commentary text extraction (.md for the knowledge base).

WHY THIS EXISTS, and why the earlier skip was wrong:
The first decision was to skip fearnleys entirely because its NUMBERS are already
ingested (563k+ rows via the publisher's Hasura backend: comments 11,733,
fixtures 549,480, SNP 2,643, catalog 357). That reasoning was correct about the
numbers and WRONG about the text. The documents carry vessel-class and regional
MARKET COMMENTARY that the API harvest does not reproduce as narrative, and this
project's purpose is getting these documents into machine-processable .md form.

Measured on the rendered page (2026 W18, page 2), read by eye:

    [commentary]                       <- extract this
        'Aframax'                          vessel-class heading
          'North Sea'                      region sub-heading
            "The anticipated strengthening of the US markets has happened
             which is pulling tonnage from the early part of the North Sea
             available list..."
          'Mediterranean'
            "It's sentiment versus fundamentals so far this week ..."
    [Rates cards]                      <- do NOT extract as the data source
        'Dirty (Spot WS 2026, Daily Change)' then cards like
        MEG/WEST 280' 200 0>   MEG/Japan 280' 395 -5?   MEG/Singapore 280' 425 0>
        These duplicate the Hasura rows and are recorded only as an appendix.

TWO ERAS, both handled here:
  Era A - 2023-2026, 19-20pp: an HTML page PRINTED to PDF. Browser print header
          ('29/04/2026, 18:42  Fearnleys Weekly Report | Fearnpulse'), a surviving
          UI artefact ('Click rate to view graph'), and the footer carries the
          fearnpulse.com report URL. Text is ~670 chars/page - sparse, because the
          page is mostly cards and charts.
  Era B - 2021-2022, 1pp posters: ~9,300 chars of dense commentary on one page
          with vessel-class headings. 
The 2018 docs are a third shape; they fall through the same text walk harmlessly.

Approach: rebuild the .md from the page's own text layer, classifying lines as
headings / sub-headings / prose, and DROP the known furniture (print header,
footer URL, page numbers, 'Click rate to view graph', 'Printer version').
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PUB = "fearnleys"
SRC = ROOT / "corpus" / "01-brokers" / PUB
OUT = ROOT / "data" / "extracted" / "md" / PUB
STATE = OUT / "_run_state.json"

import pymupdf  # noqa: E402

# --- furniture that must never reach the knowledge base ---
FURNITURE = [
    re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{4},\s*\d{2}:\d{2}\s"),
    re.compile(r"Fearnleys Weekly Report \| Fearnpulse", re.I),
    re.compile(r"^https?://fearnpulse\.com/", re.I),
    re.compile(r"^Click rate to view graph$", re.I),
    re.compile(r"^Printer version$", re.I),
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),          # page numbers like '2/19'
    re.compile(r"^\s*www\.fearnpulse\.com\s*$", re.I),
]
# vessel classes and market sections become headings
CLASSES = {"VLCC", "Suezmax", "Aframax", "Panamax", "Kamsarmax", "Capesize",
           "Supramax", "Ultramax", "Handysize", "Handymax", "Products",
           "Tankers", "Dry Bulk", "Gas", "LNG", "LPG", "Container",
           "Rates", "Comments", "Market", "Summary"}
# known region sub-headings (appear on their own line, short)
REGIONISH = re.compile(
    r"^(North Sea|Mediterranean|US Gulf|USG|WCI|ECI|ECSA|WCSA|Baltic|Continent|"
    r"Middle East|MEG|West Africa|WAF|East|West|Atlantic|Pacific|Far East|"
    r"Australia|Brazil|India|China|Japan|Korea|Caribbean|South Africa|"
    r"Arabian Gulf|Red Sea|Black Sea|USEC|USWC|Singapore|UKC|ARA)$", re.I)


def is_furniture(line: str) -> bool:
    return any(p.search(line) for p in FURNITURE)


def classify(line: str):
    t = line.strip()
    if not t:
        return "blank"
    if t.upper() in {c.upper() for c in CLASSES}:
        return "heading"
    if REGIONISH.match(t):
        return "region"
    # short line without terminal punctuation often a heading
    if len(t) < 40 and not t.endswith((".", ",", ";", ":")) and t.isupper():
        return "heading"
    return "prose"


def build_md(pdf: Path):
    try:
        ref = pdf.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        ref = pdf.as_posix()

    with pymupdf.open(pdf) as d:
        npages = d.page_count
        parts = [f"# {pdf.stem}", "", f"source: `{ref}`  |  pages: {npages}", ""]
        total_chars = 0
        kept = 0
        for i, pg in enumerate(d, start=1):
            lines = [l.strip() for l in pg.get_text().splitlines()]
            body = []
            for ln in lines:
                if not ln or is_furniture(ln):
                    continue
                kind = classify(ln)
                if kind == "heading":
                    body.append(f"## {ln}")
                elif kind == "region":
                    body.append(f"### {ln}")
                else:
                    body.append(ln)
            # merge wrapped prose lines into paragraphs: a line that does not end
            # a sentence and is followed by a lowercase start is a continuation
            merged, buf = [], ""
            for ln in body:
                if ln.startswith("#"):
                    if buf:
                        merged.append(buf.strip())
                        buf = ""
                    merged.append(ln)
                    continue
                if not buf:
                    buf = ln
                elif buf.endswith((".", "!", "?", ":")) or ln[:1].isupper():
                    merged.append(buf.strip())
                    buf = ln
                else:
                    buf += " " + ln
            if buf:
                merged.append(buf.strip())
            if merged:
                parts.append(f"\n<!-- page {i} -->\n")
                parts.extend(merged)
                parts.append("")
                total_chars += sum(len(x) for x in merged)
                kept += sum(1 for x in merged if not x.startswith("#"))

    md = "\n".join(parts)
    return md, npages, total_chars, kept


def process(pdf: Path):
    md, npages, chars, paras = build_md(pdf)
    stem = pdf.stem
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{stem}.md").write_text(md, encoding="utf-8")
    (OUT / f"{stem}.tables.json").write_text(json.dumps(
        {"note": "no numeric extraction for this source by design: the numbers are "
                 "already ingested from the publisher's Hasura backend (fixtures, "
                 "TC, SNP, comments). This source contributes COMMENTARY TEXT.",
         "pages": npages, "commentary_chars": chars, "prose_lines": paras},
        indent=2, ensure_ascii=False), encoding="utf-8")
    return {"pages": npages, "chars": chars, "prose_lines": paras,
            "md_bytes": len(md)}


def main():
    pdfs = sorted(SRC.rglob("*.pdf"))
    st = {"done": {}, "failed": {}}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    todo = [p for p in pdfs if p.stem not in st["done"]]
    print(f"[{PUB}] total={len(pdfs)} done={len(st['done'])} todo={len(todo)}", flush=True)
    t0 = time.time()
    for n, p in enumerate(todo, start=1):
        try:
            r = process(p)
            st["done"][p.stem] = r
            st["failed"].pop(p.stem, None)
            print(f"  [{n}/{len(todo)}] {p.stem[:50]:<50} pp={r['pages']:>2} "
                  f"chars={r['chars']:>6} ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            st["failed"][p.stem] = f"{type(e).__name__}: {str(e)[:160]}"
            print(f"  [{n}/{len(todo)}] {p.stem[:50]:<50} FAILED {type(e).__name__}",
                  flush=True)
            traceback.print_exc(limit=2)
        if n % 10 == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    print(f"\n[{PUB}] COMPLETE ok={len(st['done'])}/{len(pdfs)} "
          f"failed={len(st['failed'])} elapsed={time.time()-t0:.0f}s", flush=True)
    if st["failed"]:
        print(json.dumps(st["failed"], indent=2)[:1200])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for a in sys.argv[1:]:
            print(json.dumps(process(Path(a)), indent=2, default=str))
    else:
        main()
