"""
Star Asia - closing verification, run over the delivered artefacts.

Four checks, each answering a question the pipeline could plausibly have got
wrong, and each reading the OUTPUT (not the pipeline's own opinion of itself):

  1 ARITHMETIC SELF-CONSISTENCY. Every printed %change is recomputed from the
    values printed beside it. This is the check that validates the number
    convention AND the column mapping using nothing but the page.
  2 FAILURE CLASSIFICATION. A failure is either sign-only (|computed| equals
    |printed|) or a magnitude mismatch. Measured on the corpus these are two
    different things and only one is a publisher defect.
  3 HEADER REPAIR AUDIT. How many headers were recovered from a title slot, how
    many were short by their label column, how many were inherited from the
    previous table - the three repairs, so none is invisible.
  4 VALUE RECALL ON A SEEDED RANDOM SAMPLE. For each sampled document, every
    numeric value the page prints (pymupdf, ground truth) is looked for in the
    delivered .md plus every table cell, comparing PARSED values so '1,460'
    matches an extracted '1.460'. Whatever is still missing is printed with its
    page and line.
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))

import pymupdf  # noqa: E402
import star_asia as S  # noqa: E402

OUT = ROOT / "data" / "extracted" / "md" / "star_asia"
SRC = ROOT / "corpus" / "01-brokers" / "star_asia"
NUM = re.compile(r"\d[\d.,]*")
FURNITURE = ("star-asia.com.sg", "BIMCO", "Baltic Exchange", "Page ",
             "Tel:", "Fax", "snp@starasiasg.com", "Member of")


def recall(pdf: Path, tables: list, md: str):
    have = set()
    blob = (" ".join(c for t in tables for r in t["rows"] for c in r)
            + " " + " ".join(c for t in tables for c in t["header"]) + " " + md)
    for tok in NUM.findall(blob):
        v = S.parse_number(tok.strip(".,"))
        if v is not None:
            have.add(round(v, 4))
    missing = []
    with pymupdf.open(pdf) as d:
        npages = d.page_count
        for i, pg in enumerate(d, start=1):
            for line in pg.get_text().splitlines():
                if any(f in line for f in FURNITURE):
                    continue
                for tok in NUM.findall(line):
                    v = S.parse_number(tok.strip(".,"))
                    if v is None or abs(v) < 1:
                        continue
                    if round(v, 4) not in have:
                        missing.append((round(v, 2), i, line.strip()[:70]))
    return npages, missing


def main():
    files = sorted(OUT.glob("*.tables.json"))
    checked = passed = 0
    sign_only = mag = 0
    failing_docs = {}
    recovered = short = inherited = 0
    tabs_n = 0
    imgonly = Counter()
    imgonly_docs = 0
    for f in files:
        stem = f.name.replace(".tables.json", "")
        tabs = json.loads(f.read_text(encoding="utf-8"))
        tabs_n += len(tabs)
        recovered += sum(1 for t in tabs if t.get("header_recovered"))
        short += sum(1 for t in tabs if t.get("header_short"))
        inherited += sum(1 for t in tabs if t.get("header_inherited"))
        r = S.verify_change_arithmetic(tabs)
        checked += r["checked"]
        passed += r["passed"]
        bad = []
        for fl in r["fails"]:
            try:
                c = float(fl["computed"])
                p = S.parse_number(fl["printed"])
            except (TypeError, ValueError):
                p = None
            if p is not None and abs(abs(c) - abs(p)) <= 0.05 + abs(p) * 1e-4:
                sign_only += 1
            else:
                mag += 1
            bad.append(fl)
        if bad:
            failing_docs[stem] = bad
        pj = OUT / f"{stem}.pages.json"
        if pj.exists():
            pages = json.loads(pj.read_text(encoding="utf-8"))
            io = [p["page"] for p in pages if p["image_only"]]
            if io:
                imgonly_docs += 1
                for p in io:
                    imgonly[p] += 1

    print("=" * 92)
    print(f"STAR ASIA - CLOSING VERIFICATION ({len(files)} docs, {tabs_n} tables)")
    print("=" * 92)
    print("1/2  ARITHMETIC SELF-CONSISTENCY (printed %change vs the values beside it)")
    print(f"     checks run            : {checked}")
    print(f"     passed                : {passed} ({100*passed/max(checked,1):.2f}%)")
    print(f"     failed                : {checked-passed}")
    print(f"       sign-only mismatches: {sign_only}  (|computed| == |printed|)")
    print(f"       magnitude mismatches: {mag}")
    print(f"     documents with a failure: {len(failing_docs)}")
    print()
    print("3  HEADER REPAIR AUDIT")
    print(f"     header recovered from a title slot : {recovered}")
    print(f"     header restored to full width      : {short}")
    print(f"     header inherited from previous     : {inherited}")
    print()
    print("4  IMAGE-ONLY PAGES (no recoverable text at all)")
    print(f"     {imgonly_docs}/{len(files)} documents carry at least one")
    print(f"     by page: {sorted(imgonly.items())}")

    print()
    print("5  VALUE RECALL on a seeded random sample")
    pdfs = sorted(SRC.rglob("*.pdf"))
    rng = random.Random(20260924)
    sample = rng.sample(pdfs, 15)
    tot_missing = 0
    for pdf in sample:
        tj = OUT / f"{pdf.stem}.tables.json"
        mj = OUT / f"{pdf.stem}.md"
        if not tj.exists() or not mj.exists():
            print(f"     MISSING ARTEFACT for {pdf.stem}")
            continue
        tabs = json.loads(tj.read_text(encoding="utf-8"))
        npages, missing = recall(pdf, tabs, mj.read_text(encoding="utf-8"))
        tot_missing += len(missing)
        tag = "OK " if not missing else "GAP"
        print(f"     {tag} {pdf.stem[:48]:<48} pages={npages:>2} "
              f"tables={len(tabs):>2} missing={len(missing)}")
        for v, pno, line in missing[:3]:
            print(f"           {v:>12}  p{pno}  {line}")
    print(f"     total values absent from the KB across the sample: {tot_missing}")
    print()
    print("6  FAILING DOCUMENTS (named, with the failing rows)")
    for stem, bad in sorted(failing_docs.items()):
        print(f"     {stem}")
        for fl in bad[:4]:
            print(f"        {fl['row'][:26]:<26} {fl['base']:>10} vs {fl['vs']:>10} "
                  f"printed {fl['printed']:>9} computed {fl['computed']:>9}")


if __name__ == "__main__":
    main()
