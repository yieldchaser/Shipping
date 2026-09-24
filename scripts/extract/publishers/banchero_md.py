"""
Banchero Costa -> .md, built FROM the existing text.jsonl (not re-extracted).

Why this approach: banchero_costa already has a complete, verified per-document
extraction in the repository:

    data/extracted/corpus/shipbrokers/banchero_costa_<year>_<week>/
        text.jsonl    bbox, text, max_font, page, route
        tables.jsonl
        pages.jsonl
        charts/
    data/extracted/banchero_deals.parquet   3,120 structured deal rows,
                                            report_date 2021-06-28 -> 2026-08-24

Verified by reading it: the COMMENTARY PROSE IS INTACT, e.g. from 2026 W20,
'Soybeans are one of the most / important dry bulk commodities, and / account for
almost 5 percent of all / seaborne dry bulk trade...' - the exact text seen on the
rendered page. Routes are classified ('text' / 'garbled'), which flags documents
needing the mojibake decoder.

So the missing piece is only the .md TARGET FORMAT, not the extraction. Re-reading
252 PDFs would duplicate work that is already good; this converts what exists.

Structure read off the rendered pages:
    [red banner] COMMENT | MARKET REPORT - WEEK N/YYYY | page
    <SECTION TITLE>                       large font (~27pt on the cover, ~11-22pt in body)
    3-column dense prose with embedded statistics
    [bar charts with printed data labels]  on some pages

max_font is the discriminator for headings: measurements on 2026 W20 show titles at
22-28pt against body prose at ~11pt, so a threshold of ~13pt cleanly separates them
(and is derived from the data rather than hardcoded per document).

Output: data/extracted/md/banchero_costa/<stem>.md  and  .tables.json
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PUB = "banchero_costa"
SRC_PDFS = ROOT / "corpus" / "01-brokers" / PUB
EXTRACTED = ROOT / "data" / "extracted" / "corpus" / "shipbrokers"
DEALS = ROOT / "data" / "extracted" / "banchero_deals.parquet"
OUT = ROOT / "data" / "extracted" / "md" / PUB
STATE = OUT / "_run_state.json"

HEADING_MIN_FONT = 13.0     # derived: titles 22-28pt vs prose ~11pt

# banner furniture, stripped by exact phrase
BANNER = re.compile(
    r"^(COMMENT|MARKET REPORT\s*[-–]\s*WEEK\s*\d+/\d{4}|\d{1,3})$", re.I)


def find_dir(stem: str):
    """The extracted dir for a document stem."""
    cand = list(EXTRACTED.glob(f"{stem}*"))
    if cand:
        return cand[0]
    # stems carry a _compressed suffix sometimes; try a looser match
    base = re.sub(r"_compressed$", "", stem)
    cand = list(EXTRACTED.glob(f"{base}*"))
    return cand[0] if cand else None


def load_rows(d: Path):
    f = d / "text.jsonl"
    if not f.exists():
        return []
    rows = []
    for ln in f.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    return rows


def tidy(t: str) -> str:
    """Prose arrives with hard newlines from the 3-column layout. Reflow them."""
    t = t.replace("\n", " ")
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def is_heading(row) -> bool:
    t = row.get("text", "")
    if not t or len(t) > 120:
        return False
    if (row.get("max_font") or 0) < HEADING_MIN_FONT:
        return False
    # a heading is not a sentence and is not dominated by digits
    digits = sum(c.isdigit() for c in t)
    if digits > len(t) * 0.3:
        return False
    return not t.strip().endswith((".", ",", ";", ":"))


def build(stem: str):
    d = find_dir(stem)
    if d is None:
        raise FileNotFoundError(f"no extracted dir for {stem}")
    rows = load_rows(d)
    if not rows:
        raise FileNotFoundError(f"no text.jsonl rows in {d}")

    try:
        ref = next(SRC_PDFS.rglob(stem + ".pdf")).relative_to(ROOT).as_posix()
    except StopIteration:
        ref = f"corpus/01-brokers/{PUB}/**/{stem}.pdf"

    by_page = defaultdict(list)
    for r in rows:
        by_page[r.get("page", 0)].append(r)

    parts = [f"# {stem}", "", f"source: `{ref}`", ""]
    heads = 0
    prose_chars = 0
    routes = set()
    for pno in sorted(by_page):
        parts.append(f"\n<!-- page {pno + 1} -->\n")
        items = sorted(by_page[pno], key=lambda r: (r.get("bbox") or [0, 0])[1])
        for r in items:
            t = tidy(r.get("text", ""))
            if not t or BANNER.match(t):
                continue
            routes.add(r.get("route"))
            if is_heading(r):
                parts.append(f"\n### {t}\n")
                heads += 1
            else:
                parts.append(t)
                prose_chars += len(t)
    md = "\n".join(parts)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{stem}.md").write_text(md, encoding="utf-8")
    (OUT / f"{stem}.tables.json").write_text(json.dumps(
        {"note": "deal ledger already extracted separately to "
                 "data/extracted/banchero_deals.parquet (3120 rows); this file "
                 "carries the COMMENTARY derived from the existing text.jsonl",
         "source_dir": d.name, "text_rows": len(rows),
         "headings": heads, "prose_chars": prose_chars,
         "routes": sorted(x for x in routes if x)},
        indent=2, ensure_ascii=False), encoding="utf-8")
    return {"text_rows": len(rows), "headings": heads,
            "prose_chars": prose_chars, "routes": sorted(x for x in routes if x),
            "md_bytes": len(md)}


def main():
    stems = sorted({p.stem for p in SRC_PDFS.rglob("*.pdf")})
    st = {"done": {}, "failed": {}}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    todo = [s for s in stems if s not in st["done"]]
    print(f"[{PUB}] pdfs={len(stems)} done={len(st['done'])} todo={len(todo)}",
          flush=True)
    t0 = time.time()
    routes_all = defaultdict(int)
    for n, s in enumerate(todo, start=1):
        try:
            r = build(s)
            st["done"][s] = r
            st["failed"].pop(s, None)
            for x in r["routes"]:
                routes_all[x] += 1
            print(f"  [{n}/{len(todo)}] {s[:52]:<52} rows={r['text_rows']:>4} "
                  f"heads={r['headings']:>3} prose={r['prose_chars']:>6} "
                  f"{r['routes']} ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            st["failed"][s] = f"{type(e).__name__}: {str(e)[:150]}"
            print(f"  [{n}/{len(todo)}] {s[:52]:<52} FAILED {type(e).__name__}: "
                  f"{str(e)[:60]}", flush=True)
        if n % 10 == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")
    print(f"\n[{PUB}] COMPLETE ok={len(st['done'])}/{len(stems)} "
          f"failed={len(st['failed'])} elapsed={time.time()-t0:.0f}s")
    print(f"route tally: {dict(routes_all)}")
    if st["failed"]:
        print(json.dumps(st["failed"], indent=2)[:1000])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for a in sys.argv[1:]:
            print(json.dumps(build(Path(a).stem), indent=2, default=str))
    else:
        main()
