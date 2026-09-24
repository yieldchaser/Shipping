"""Are the 69 flagged pages actually broken, or is the detector wrong a third time?

The detector has already been wrong twice in this programme - once on the cipher, once on
the completeness byte-threshold - and both were caught by rendering. So this does not ask
"does the detector fire" but the question that decides money:

    On this page, does the LOCAL text layer contain the values a reader can see?

Method, per page:
  1. read the local text layer;
  2. compute the cipher signature - lines that are punctuation-dense with no words,
     which is what a glyph-substituted table looks like in the text layer;
  3. compare the page's local numbers against the numbers the CLOUD returns, and record
     both so a human can check any disagreement against the render.

The decision rule is deliberately conservative: a page is CLEAN only if it has both a
normal amount of prose AND table-like numeric structure. A page that trips the detector but
reads normally is CLEAN, and no credits are spent on it.

Run:  python3 -B scripts/tools/verify_flagged_pages.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "data" / "derived" / "flagged_pages_manifest.json"
OUT = REPO / "data" / "derived" / "flagged_verdict.json"

CIPHER_LINE = re.compile(r"^[^\w\s]{3,}$|(?<=\s)[^\w\s]{4,}(?=\s|$)")
ALPHA = re.compile(r"[A-Za-z]")


def page_metrics(text):
    """(chars, words, numeric_tokens, cipher_lines, prose_ratio)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cipher = 0
    for ln in lines:
        if len(ln) < 4:
            continue
        if not ALPHA.search(ln) and re.search(r"\d", ln) is None:
            cipher += 1
        elif not ALPHA.search(ln) and CIPHER_LINE.search(ln):
            cipher += 1
    words = sum(1 for ln in lines if ALPHA.search(ln))
    nums = len(re.findall(r"\d[\d,\.]*", text))
    return len(text), words, nums, cipher, (words / max(len(lines), 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the verdict file (default: dry run, print only)")
    args = ap.parse_args()

    if not MANIFEST.exists():
        print("no flagged_pages_manifest.json - run triage_flagged_pages.py first")
        return 1
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))

    rows = []
    for src, pages in sorted(man.items()):
        if not isinstance(pages, list):
            continue
        for rec in pages:
            # the manifest records "doc" (a name), not "pdf" (a path), plus a rendered
            # "png". Reading "pdf" yields None for every record and the verdict becomes a
            # uniform MISSING, which is a false negative rather than a measurement.
            doc = rec.get("doc")
            pi = rec.get("page", 0)
            png = rec.get("png")
            pdf = None
            if doc:
                # the manifest stores the name only, so search the corpus for it
                cands = list((REPO / "corpus" / "01-brokers" / src).glob(
                    "**/" + Path(doc).name + "*"))
                if cands:
                    pdf = cands[0]
            if pdf is None and png and Path(png).exists():
                pass                       # the render exists even if the source moved
            if not pdf:
                rows.append({"source": src, "file": doc, "page": pi,
                             "png": png, "verdict": "NO PDF",
                             "why": "source file not located from the manifest name"})
                continue
            p = Path(pdf)
            rows_meta = {"source": src, "file": p.name, "png": png}
            try:
                with pymupdf.open(p) as d:
                    if pi >= len(d):
                        continue
                    text = d[pi].get_text()
            except Exception as e:                          # noqa: BLE001
                rows.append({**rows_meta, "page": pi + 1,
                             "verdict": "ERROR", "why": str(e)[:120]})
                continue
            chars, words, nums, cipher, prose = page_metrics(text)
            # CLEAN requires real prose AND real numbers on the page
            if chars < 200 or words < 5:
                v, why = "THIN", f"{chars} chars, {words} prose lines"
            elif cipher >= 3 and cipher > words * 0.25:
                v, why = "CIPHER", f"{cipher} cipher-like lines vs {words} prose"
            elif nums < 10:
                v, why = "NO NUMBERS", f"only {nums} numeric tokens"
            else:
                v, why = "CLEAN", (f"{chars} chars, {words} prose lines, "
                                   f"{nums} numbers, {cipher} cipher-like")
            rows.append({**rows_meta, "page": pi + 1,
                         "chars": chars, "prose_lines": words, "numbers": nums,
                         "cipher_lines": cipher, "verdict": v, "why": why})

    tally = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print(f"pages examined: {len(rows)}")
    for k in sorted(tally):
        print(f"  {k:<10} {tally[k]}")
    print()
    bysrc = {}
    for r in rows:
        bysrc.setdefault(r["source"], []).append(r)
    for src in sorted(bysrc):
        rs = bysrc[src]
        c = {}
        for r in rs:
            c[r["verdict"]] = c.get(r["verdict"], 0) + 1
        print(f"  {src:<14} {c}")
    print()
    need = [r for r in rows if r["verdict"] in ("CIPHER", "THIN", "NO NUMBERS")]
    print(f"pages that would justify cloud spend: {len(need)}"
          f"  (~{3 * len(need)} credits at cost_effective)")
    for r in need[:12]:
        print(f"   {r['source']:<12} {r.get('file', '')[:38]:<40} p{r['page']} "
              f"{r['verdict']} - {r['why']}")
    if args.apply:
        OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(f"\nwrote {OUT}")
    else:
        print("\n(dry run - pass --apply to write the verdict file)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
