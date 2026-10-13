"""Proof-of-work checker for agent branches: every number an agent adds must be backed by evidence
that this script can re-verify mechanically.

Evidence file: docs/handoff/evidence/<lane>.jsonl, one JSON object per line:
  {"file": "data/extracted/md/.../x.md",      # file the value was written to (MD or CSV)
   "value": "12,5",                             # the value exactly as written in that file
   "printed": "$ 12,5m",                        # the text as printed on the page
   "pdf": "corpus/01-brokers/.../x.pdf",       # source document (relative to --corpus-root)
   "page": 3,                                   # 1-based page number
   "kind": "text" | "image",                    # text = page text layer has it; image = raster/outlined
   "crop": "docs/handoff/evidence/<lane>/<id>.png"}   # required for kind=image: crop of the cell(s)

Checks:
  E1 text evidence: every number in "printed" occurs among the page's text-layer words.
  E2 image evidence: crop exists (PNG, >1 KB). If rapidocr is installed, the crop is OCR'd and
     the numbers of "printed" must appear in the OCR text (else reported as OCR-UNCONFIRMED, which
     the reviewer must look at).
  E3 the value really is in "file" now.
  E4 coverage: every number ADDED in the branch diff (vs --base) to data/extracted/**/*.md or
     data/extracted/series/*.csv has at least one evidence line with that file and value.
     Numbers of 1-2 digits and years 1900-2099 are ignored.

    python scripts/verify/check_evidence.py --lane <lane> [--base origin/main]
           [--corpus-root C:/Users/Dell/Github/Shipping]
Exit 1 if any E1/E3/E4 failure or a missing crop.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NUM = re.compile(r"\d[\d.,]*\d|\d")


def nums(s: str) -> list[str]:
    out = []
    for n in NUM.findall(s):
        digits = re.sub(r"[.,]", "", n)
        if len(digits) <= 2 or (len(n) == 4 and n.isdigit() and 1900 <= int(n) <= 2099):
            continue
        out.append(n)
    return out


def canon(n: str) -> set[str]:
    """Equivalent spellings: 12,5 / 12.5 ; 1.234 / 1,234 / 1234."""
    forms = {n, n.replace(",", "."), n.replace(".", ","), re.sub(r"[.,]", "", n)}
    return forms


def page_words(pdf: Path, page: int, cache: dict) -> set[str]:
    key = (pdf, page)
    if key not in cache:
        import pymupdf
        doc = pymupdf.open(pdf)
        words = set()
        for w in doc[page - 1].get_text("words"):
            for n in NUM.findall(w[4]):
                words |= canon(n)
        cache[key] = words
    return cache[key]


def added_numbers(base: str) -> dict[str, set[str]]:
    diff = subprocess.run(["git", "diff", "-U0", f"{base}...HEAD", "--", "data/extracted"],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    out: dict[str, set[str]] = {}
    cur = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
        elif line.startswith("+") and not line.startswith("+++") and cur and cur.endswith((".md", ".csv")):
            out.setdefault(cur, set()).update(nums(line[1:]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=True)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--corpus-root", default=str(ROOT))
    a = ap.parse_args()
    ev_path = ROOT / "docs" / "handoff" / "evidence" / f"{a.lane}.jsonl"
    evidence = [json.loads(l) for l in ev_path.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if ev_path.exists() else []
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
    except Exception:
        ocr = None
    fails, warns, cache, covered = [], [], {}, {}
    for i, e in enumerate(evidence, 1):
        tag = f"evidence line {i} ({e.get('file')} = {e.get('value')})"
        f = ROOT / e["file"]
        if not f.exists() or e["value"] not in f.read_text(encoding="utf-8", errors="replace"):
            fails.append(f"E3 {tag}: value not found in file")
        covered.setdefault(e["file"], set()).update(canon(e["value"]))
        for n in nums(e["value"]):
            covered[e["file"]] |= canon(n)
        printed = nums(e.get("printed", ""))
        if e.get("kind") == "text":
            pdf = Path(a.corpus_root) / e["pdf"]
            if not pdf.exists():
                fails.append(f"E1 {tag}: pdf not found {pdf}")
                continue
            words = page_words(pdf, int(e["page"]), cache)
            missing = [n for n in printed if not (canon(n) & words)]
            if missing or not printed:
                fails.append(f"E1 {tag}: printed numbers {missing or 'none given'} not on page {e['page']}")
        elif e.get("kind") == "image":
            crop = ROOT / e.get("crop", "")
            if not e.get("crop") or not crop.exists() or crop.stat().st_size < 1024:
                fails.append(f"E2 {tag}: crop missing or empty ({e.get('crop')})")
                continue
            if ocr is not None:
                res, _ = ocr(str(crop))
                seen = set()
                for r in res or []:
                    for n in NUM.findall(r[1]):
                        seen |= canon(n)
                if any(not (canon(n) & seen) for n in printed):
                    warns.append(f"E2 {tag}: OCR-UNCONFIRMED, reviewer must look at {e['crop']}")
        else:
            fails.append(f"{tag}: kind must be text or image")
    for f, ns in added_numbers(a.base).items():
        have = covered.get(f, set())
        miss = sorted(n for n in ns if not (canon(n) & have))
        if miss:
            fails.append(f"E4 {f}: {len(miss)} added numbers without evidence, e.g. {miss[:8]}")
    for w in warns:
        print("WARN", w)
    for f in fails:
        print("FAIL", f)
    print(f"evidence lines: {len(evidence)}; failures: {len(fails)}; warnings: {len(warns)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
