"""
Source 4: XCLUSIV - dedicated pipeline.

Xclusiv's payload is INSIDE PROSE, not in a table grid. Measured facts
(docs/xclusiv_survey.md, scratch/recon_source.py, scratch/xclusiv_vocab.py):

  * 266 PDFs, 2021:23 2022:51 2023:50 2024:51 2025:51 2026:40
  * page count GROWS: 6 (2021) -> 7 (2022/23) -> 9 (2024-26). Pin nothing to a
    page number.
  * numbers are ISO/US (US-thousands 1100-2400 per doc vs European thousands
    0-10). The advanced_shipping European parser must NOT be reused.
  * charts are VECTOR on 4-6 pages, plus one raster page from 2024.
  * the rates read like:
        "VLCC: average T/C ended the week up by 5.1k/day at USD 219,233/day."
        "Capesize 1y T/C rate is down this week at USD 27,750/day, while Panamax.."
        "Products: the LR2 route (TC1) Middle East to Japan ... USD 153,488/day."

Two correctness rules, each earned by a measured failure:

  1. LABELS BY EXACT VOCABULARY, never by position. A positional attempt
     produced fragments ('clo', 'Continent to F.') and accepted the page HEADING
     'IN A NUTSHELL' as a subject. Vocabulary matching lifted labelling from
     7/31 to ~80% and removed every heading leak.
  2. THE VALUE IS ANCHORED TO THE SUBJECT'S POSITION, not to the end of the
     sentence. Taking the last USD value returned 29,250 for Capesize where the
     page says 27,750 - sentences carry values for more than one subject. A
     wrong number is worse than a missing one.

The .md is emitted for every document regardless of whether the typed rows are
confident; the typed layer is best-effort and marked so.
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PUB = "xclusiv"
SRC = ROOT / "corpus" / "01-brokers" / PUB
OUT = ROOT / "data" / "extracted" / "md" / PUB
STATE = OUT / "_run_state.json"

import pymupdf  # noqa: E402

VAL = re.compile(r"USD\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*/\s*day")
CHG = re.compile(r"\bby\s+(\d+(?:\.\d+)?)\s*k\s*/\s*day", re.I)

VESSEL = ["Kamsarmax/Panamax", "Ultramax/Supramax", "Post Panamax", "Handymax",
          "Capesize", "Kamsarmax", "Panamax", "Ultramax", "Supramax",
          "Handysize", "VLCC", "Suezmax", "Aframax", "VLGC", "LR2", "LR1", "MR"]
ROUTE_HINT = ["Middle East to Japan", "Middle East Gulf", "West Africa",
              "US Gulf", "Continent to F.", "Transatlantic", "Transpacific",
              "Brazil", "Baltic", "Mediterranean", "Japan", "China", "Korea",
              "India"]
BLOCK = ["IN A NUTSHELL", "MARKET COMMENTARY", "NUTSHELL", "DISCLAIMER",
         "FREIGHT MARKET", "SALES", "SUMMARY", "CONTACT", "www.xclusiv.gr",
         "Xclusiv Shipbrokers"]


def sentences(text: str):
    flat = re.sub(r"\s*\n\s*", " ", text)
    flat = re.sub(r"\s{2,}", " ", flat)
    return re.split(r"(?<=[.!?])\s+(?=[A-Z])", flat)


def subject_of(sent: str, val_pos: int):
    """The term CLOSEST BEFORE the value, not merely present in the sentence.

    Scanning the whole sentence for vocabulary produced wrong pairs: a sentence
    about 'West Africa to Continent' came out labelled 'Middle East Gulf' because
    that name appears later in the same sentence for a different route. The label
    must be the nearest term PRECEDING the value, and nothing if none is near.
    """
    up = sent.upper()
    for bad in BLOCK:
        if up.strip().startswith(bad.upper()):
            return None
    best, best_pos = None, -1
    for term in sorted(VESSEL + ROUTE_HINT, key=len, reverse=True):
        for m in re.finditer(r"\b" + re.escape(term.upper()) + r"\b", up):
            if m.end() <= val_pos and m.end() > best_pos:
                # prefer the latest position; on a tie prefer the longer term
                if m.end() > best_pos or (best is None or len(term) > len(best)):
                    best, best_pos = term, m.end()
    # a label further than 120 chars back belongs to another clause, not this value
    if best_pos >= 0 and (val_pos - best_pos) > 120:
        return None
    return best


def extract_rates(text: str):
    """Rates, with the two defects pass 2's verification exposed removed:

    1. STRAY NOISE - a value of 1 was emitted from an 'IN A NUTSHELL' sentence.
       Real T/C rates are thousands per day, so a floor removes narrative
       integers without touching a genuine rate.
    2. DUPLICATE VALUES - 153,488 appeared BOTH as LR2 and as MR on one page.
       The same value cannot belong to two routes, so when a value repeats
       within a document the row carrying a label wins; if both carry one, the
       first is kept and the later is dropped as a re-mention.
    """
    MIN_RATE = 100          # real T/C rates are thousands/day
    rows = []
    for s in sentences(text):
        if not VAL.search(s):
            continue
        hits = [(m.start(), m.group(1)) for m in VAL.finditer(s)]
        raw_pos, raw = hits[0]
        try:
            v = int(raw.replace(",", ""))
        except ValueError:
            continue
        if v < MIN_RATE:
            continue            # narrative integer, not a rate
        subj = subject_of(s, raw_pos)
        chg = CHG.findall(s)
        rows.append({"subject": subj,
                     "value": v,
                     "value_raw": raw,
                     "change_kday": float(chg[0]) if chg else None,
                     "sentence": s[:200]})

    # de-duplicate by value: prefer the labelled row, keep the first occurrence
    by_val = {}
    for r in rows:
        k = r["value"]
        if k not in by_val:
            by_val[k] = r
        elif by_val[k]["subject"] is None and r["subject"] is not None:
            by_val[k] = r        # a labelled row supersedes an unlabelled one
    return list(by_val.values())


def process(pdf: Path):
    with pymupdf.open(pdf) as d:
        npages = d.page_count
        text = "".join(pg.get_text() for pg in d)
        # chart pages: vector-heavy, for provenance
        gfx = {}
        for i, pg in enumerate(d, start=1):
            segs = sum(1 for dr in pg.get_drawings()
                       for it in dr["items"] if it[0] == "l")
            if segs > 200:
                gfx[str(i)] = {"vector_segments": segs}
    rates = extract_rates(text)
    labelled = [r for r in rates if r["subject"]]

    try:
        ref = pdf.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        ref = pdf.as_posix()
    md = [f"# {pdf.stem}", "", f"source: `{ref}`  |  pages: {npages}", "",
          "## T/C rates (prose-derived)",
          "",
          "| subject | USD/day | change k/day | sentence |",
          "|---|---|---|---|"]
    for r in rates:
        md.append(f"| {r['subject'] or ''} | {r['value_raw']} | "
                  f"{r['change_kday'] if r['change_kday'] is not None else ''} | "
                  f"{r['sentence'].replace('|', '/')[:110]} |")
    md += ["", "## Full page text", ""]
    with pymupdf.open(pdf) as d:
        for i, pg in enumerate(d, start=1):
            md += [f"\n### Page {i}\n", pg.get_text().strip(), ""]

    OUT.mkdir(parents=True, exist_ok=True)
    stem = pdf.stem
    (OUT / f"{stem}.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / f"{stem}.tables.json").write_text(json.dumps(
        {"convention": "iso", "n_rates": len(rates), "n_labelled": len(labelled),
         "typed_confidence": "best-effort: see docs/xclusiv_survey.md",
         "rates": rates}, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / f"{stem}.charts.json").write_text(
        json.dumps(gfx, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"pages": npages, "rates": len(rates), "labelled": len(labelled),
            "md_bytes": len("\n".join(md))}


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
            print(f"  [{n}/{len(todo)}] {p.stem[:52]:<52} rates={r['rates']:>2} "
                  f"lab={r['labelled']:>2} ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            st["failed"][p.stem] = f"{type(e).__name__}: {str(e)[:160]}"
            print(f"  [{n}/{len(todo)}] {p.stem[:52]:<52} FAILED {type(e).__name__}",
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
