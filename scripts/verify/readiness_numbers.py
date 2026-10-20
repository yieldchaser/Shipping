"""Readiness gate, check 1: every number printed in a PDF's text layer should appear in its Markdown.

For each MD under data/extracted/md/<publisher>/ the PDF named in its `source_file` frontmatter is read with
PyMuPDF. Per page, the numbers of the text layer (2+ digits, commas dropped, compared as values) are looked up in
the numbers of the whole MD. A page whose coverage is low, with enough numbers to judge, is flagged for a render
check. Pages excluded by design (contacts, equities, final market pages) will flag too; they are triaged, not fixed.

Pages without a text layer (scans, outlined glyphs) cannot be judged here and are counted as `no_text`.

Output: data/derived/readiness/numbers_coverage.csv (one row per MD) and numbers_flagged_pages.csv.

    python scripts/verify/readiness_numbers.py [--publisher ssy] [--workers 6] [--min-nums 8] [--threshold 0.9]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = ROOT / "data" / "extracted" / "md"
OUT = ROOT / "data" / "derived" / "readiness"
# Untracked PDFs live only in the main checkout when this runs from a worktree.
PDF_ROOTS = [ROOT, ROOT.parents[2]] if ROOT.parent.name == "worktrees" else [ROOT]

NUM = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")


PHONE = re.compile(r"\+\s?\d|\b(?:tel|mob|mobile|fax|phone)\b", re.I)


def numbers(text: str, page: bool = False) -> set[str]:
    """Values of the numbers in `text`. On a PDF page (page=True) lines with phone numbers are skipped, and so are
    bare years and round integers (100, 2000, 45000): chart axis ticks and year labels, which no MD transcribes."""
    out = set()
    if page:
        text = "\n".join(ln for ln in text.splitlines() if not PHONE.search(ln))
    for m in NUM.findall(text):
        s = m.replace(",", "").lstrip("-")
        if sum(c.isdigit() for c in s) < 2:
            continue
        if page and "." not in s and (1990 <= int(s) <= 2039 or (len(s) >= 3 and s.endswith("00"))):
            continue
        try:
            out.add(repr(float(s)))
        except ValueError:
            continue
    return out


def axis_ticks(text: str) -> set[str]:
    """Chart axis labels: 4 or more values on the page in one arithmetic progression (0.1 0.2 0.3 0.4,
    12 16 20 24). Printed data rarely is; a short table column that happens to be (1 2 3 4 ranks) is lost too."""
    vals = sorted({float(m.replace(",", "")) for m in NUM.findall(text)
                   if any(c.isdigit() for c in m)})
    have = set(vals)
    ticks = set()
    for i, a in enumerate(vals):
        for b in vals[i + 1:i + 6]:
            d = b - a
            if d <= 0:
                continue
            run = [a, b]
            while (nxt := round(run[-1] + d, 6)) in have:
                run.append(nxt)
            if len(run) >= 4:
                ticks.update(repr(abs(v)) for v in run)
    return ticks


def source_of(md: Path) -> str | None:
    head = md.read_text(encoding="utf-8", errors="ignore")[:3000]
    m = re.search(r'^source_file:\s*"?([^"\n]+)"?\s*$', head, re.M)
    return m.group(1).strip() if m else None


def check(args):
    md, min_nums, threshold = args
    import pymupdf

    rel = md.relative_to(MD_ROOT).as_posix()
    src = source_of(md)
    row = {"publisher": rel.split("/")[0], "md": rel, "pdf": src or "", "pages": 0, "no_text": 0,
           "pdf_nums": 0, "missing": 0, "coverage": "", "flagged_pages": 0, "status": ""}
    if not src or not src.lower().endswith(".pdf"):
        row["status"] = "no_pdf_source"
        return row, []
    path = next((r / src for r in PDF_ROOTS if (r / src).is_file()), None)
    if path is None:
        row["status"] = "pdf_missing"
        return row, []
    md_nums = numbers(md.read_text(encoding="utf-8", errors="ignore").replace("\\", ""))
    flagged = []
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001
        row["status"] = f"pdf_error {type(exc).__name__}"
        return row, []
    total = miss = 0
    for pno, page in enumerate(doc, 1):
        text = page.get_text()
        row["pages"] += 1
        if len(text.strip()) < 40:
            row["no_text"] += 1
            continue
        nums = numbers(text, page=True) - axis_ticks(text)
        lost = sorted(nums - md_nums, key=lambda s: float(s))
        total += len(nums)
        miss += len(lost)
        if len(nums) >= min_nums and 1 - len(lost) / len(nums) < threshold:
            flagged.append({"md": rel, "page": pno, "page_nums": len(nums), "missing": len(lost),
                            "coverage": round(1 - len(lost) / len(nums), 3),
                            "sample_missing": " ".join(x.removesuffix(".0") for x in lost[:12])})
    row.update(pdf_nums=total, missing=miss, flagged_pages=len(flagged),
               coverage=round(1 - miss / total, 4) if total else "", status="ok")
    return row, flagged


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--publisher", action="append")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--min-nums", type=int, default=8)
    ap.add_argument("--threshold", type=float, default=0.9)
    a = ap.parse_args(argv)
    pubs = a.publisher or sorted(p.name for p in MD_ROOT.iterdir() if p.is_dir())
    mds = [m for p in pubs for m in sorted((MD_ROOT / p).rglob("*.md"))]
    print(f"{len(mds)} MDs in {len(pubs)} publisher folder(s)", flush=True)
    rows, pages = [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, (row, fl) in enumerate(ex.map(check, [(m, a.min_nums, a.threshold) for m in mds],
                                            chunksize=16), 1):
            rows.append(row)
            pages.extend(fl)
            if i % 1000 == 0:
                print(f"  {i}/{len(mds)}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = "" if not a.publisher else "_" + "_".join(a.publisher)
    for name, data, cols in (("numbers_coverage", rows, list(rows[0]) if rows else []),
                             ("numbers_flagged_pages", pages,
                              ["md", "page", "page_nums", "missing", "coverage", "sample_missing"])):
        with open(OUT / f"{name}{suffix}.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
            w.writeheader()
            w.writerows(data)
    by = {}
    for r in rows:
        b = by.setdefault(r["publisher"], {"mds": 0, "ok": 0, "nums": 0, "miss": 0, "flagged_mds": 0, "other": 0})
        b["mds"] += 1
        if r["status"] == "ok":
            b["ok"] += 1
            b["nums"] += r["pdf_nums"]
            b["miss"] += r["missing"]
            b["flagged_mds"] += bool(r["flagged_pages"])
        else:
            b["other"] += 1
    print(f"{'publisher':18} {'mds':>6} {'checked':>7} {'coverage':>8} {'flag_mds':>8} {'no_pdf':>6}")
    for p, b in sorted(by.items()):
        cov = f"{1 - b['miss'] / b['nums']:.4f}" if b["nums"] else "-"
        print(f"{p:18} {b['mds']:6} {b['ok']:7} {cov:>8} {b['flagged_mds']:8} {b['other']:6}")
    print(f"flagged pages: {len(pages)} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
