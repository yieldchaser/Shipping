"""Corpus-wide fidelity scan: every Markdown with a PDF/HTML source_file, compared to that source's text.

Per MD it reports
  md_nums      numbers (>=3 digits, not years) in the MD body
  invented     of those, how many are NOT anywhere on the PDF text layer (3.285 = 3,285 = 3285 accepted)
  pdf_nums     distinct numbers on the PDF text layer
  dropped      of those, how many never appear in the MD (charts' axis labels land here too)
  raster_pages pages with < 50 text-layer chars (scans / outlined pages: numbers there can't be checked)
  tables       MD table lines

invented > 0 is not proof of error (computed change columns, OCR of raster pages), dropped > 0 is not proof
of loss (chart axes, footers) -- they rank where to LOOK with scripts/verify/page_view.py.

    python scripts/audit/fidelity_scan.py [--source clarksons ...] [--out data/audit/fidelity.csv] [-j 6]
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
NUM = re.compile(r"\d[\d.,]*\d|\d")
FIELDS = ["source", "md", "pdf", "pages", "raster_pages", "tables", "md_nums", "derived", "invented",
          "pdf_nums", "dropped", "invented_sample", "error"]


def keep(n: str) -> str | None:
    n = n.strip(".,")
    d = re.sub(r"[.,]", "", re.sub(r"[.,]0{1,2}$", "", n))
    if len(d) <= 2 or (len(n) == 4 and n.isdigit() and 1900 <= int(n) <= 2099):
        return None
    return n


def canon(n: str) -> set[str]:
    out = {n, n.replace(",", "."), n.replace(".", ","), re.sub(r"[.,]", "", n)}
    # numeric value, both readings of the separators: 1816.0 = 1,816 ; 24.0 = 24 ; 903.00 = 903
    for s in (n.replace(",", ""), n.replace(".", "").replace(",", "."), n.replace(",", ".")):
        try:
            out.add(repr(round(float(s), 4)))
        except ValueError:
            pass
    return out


PATHLIKE = re.compile(r"!\[|\]\(|`[^`]*[/\\][^`]*`|\.(pdf|png|md|csv|json)\b", re.I)


def as_float(n: str) -> float | None:
    s = n.replace(",", "") if re.search(r",\d{3}(\D|$)", n) else n.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def is_derived(n: str, row: list[str]) -> bool:
    """n equals a difference / ratio-change of two other numbers printed on the same MD line."""
    v = as_float(n)
    vals = [x for x in (as_float(r) for r in row if r != n) if x is not None]
    if v is None:
        return False
    for i, a in enumerate(vals):
        for b in vals[i + 1:]:
            if abs(abs(a - b) - abs(v)) < 0.006 * max(1, abs(v)) * 0.01 + 0.006:
                return True
            if b and abs(abs((a - b) / b * 100) - abs(v)) < 0.06:
                return True
            if a and abs(abs((b - a) / a * 100) - abs(v)) < 0.06:
                return True
    return False


def body_and_source(md: Path) -> tuple[str, str]:
    text = md.read_text(encoding="utf-8", errors="replace")
    src = ""
    if text.startswith("---"):
        head, _, text = text[3:].partition("\n---")
        m = re.search(r"^source_file:\s*['\"]?(.+?)['\"]?\s*$", head, re.M)
        src = m.group(1) if m else ""
    return text, src


_BY_NAME: dict[str, Path] = {}


def _init(by_name: dict[str, Path]) -> None:
    _BY_NAME.update(by_name)


def source_pages(path: Path) -> list[str]:
    """Text of each page (PDF) or of the whole document (HTML: visible text plus script bodies, which carry
    embedded chart data such as Gibson's)."""
    if path.suffix.lower() == ".pdf":
        import pymupdf
        pymupdf.TOOLS.mupdf_display_errors(False)
        with pymupdf.open(path) as doc:
            return [pg.get_text() for pg in doc]
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    # embedded chart data sits in scripts and data-* attributes: keep the whole source, tags as spaces
    raw = path.read_bytes().decode("utf-8", errors="replace")
    return [soup.get_text(" ") + " " + re.sub(r"[<>\"'=:\[\]{}]", " ", raw)]


def scan(args: tuple[str, str]) -> dict:
    md_s, corpus_root = args
    md = Path(md_s)
    row = dict.fromkeys(FIELDS, "")
    row["source"] = md.relative_to(MD_ROOT).parts[0]
    row["md"] = md.relative_to(ROOT).as_posix()
    try:
        body, src = body_and_source(md)
        row["pdf"] = src
        if not src.lower().endswith((".pdf", ".html", ".htm")):
            row["error"] = "no pdf/html source_file"
            return row
        path = next((b / src for b in (Path(corpus_root), ROOT) if (b / src).exists()), None)
        if path is None and "/" not in src:      # some frontmatters carry the bare file name
            path = _BY_NAME.get(src)
        if path is None:
            row["error"] = "source missing"
            return row
        pages = source_pages(path)
        row["pages"] = len(pages)
        row["raster_pages"] = sum(len(t.strip()) < 50 for t in pages)
        # a JSON list "25500,23500,3250" is also three numbers
        words = {k for t in pages for n in NUM.findall(t) for k in map(keep, [n, *n.split(",")]) if k}
        layer = set().union(*(canon(w) for w in words)) if words else set()
        md_nums, inv, derived = [], [], 0
        for ln in body.splitlines():
            if PATHLIKE.search(ln):
                continue
            raw = [n.strip(".,") for n in NUM.findall(ln)]
            for n in raw:
                k = keep(n)
                if not k:
                    continue
                md_nums.append(k)
                if canon(k) & layer:
                    continue
                if is_derived(k, raw):
                    derived += 1
                else:
                    inv.append(k)
        row["derived"] = derived
        md_layer = set().union(*(canon(n) for n in md_nums)) if md_nums else set()
        row["tables"] = sum(1 for ln in body.splitlines() if ln.lstrip().startswith("|"))
        row["md_nums"] = len(md_nums)
        row["invented"] = len(inv)
        row["invented_sample"] = " ".join(list(dict.fromkeys(inv))[:8])
        row["pdf_nums"] = len(words)
        row["dropped"] = sum(1 for w in words if not (canon(w) & md_layer))
    except Exception as e:  # noqa: BLE001 - one bad PDF must not stop the scan
        row["error"] = f"{type(e).__name__}: {e}"[:200]
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", action="append")
    ap.add_argument("--out", default=str(ROOT / "data" / "audit" / "fidelity.csv"))
    ap.add_argument("--corpus-root", default="C:/Users/Dell/Github/Shipping")
    ap.add_argument("-j", type=int, default=6)
    a = ap.parse_args()
    dirs = [MD_ROOT / s for s in a.source] if a.source else [p for p in MD_ROOT.iterdir() if p.is_dir()]
    mds = sorted(str(p) for d in dirs for p in d.rglob("*.md"))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    by_name = {}
    for sub in ("corpus", "reports"):
        for p in (Path(a.corpus_root) / sub).rglob("*"):
            if p.suffix.lower() in (".pdf", ".html", ".htm"):
                by_name.setdefault(p.name, p)
    with out.open("w", newline="", encoding="utf-8") as f,             ProcessPoolExecutor(a.j, initializer=_init, initargs=(by_name,)) as ex:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for i, row in enumerate(ex.map(scan, [(m, a.corpus_root) for m in mds], chunksize=8), 1):
            w.writerow(row)
            if i % 500 == 0:
                print(f"{i}/{len(mds)}", file=sys.stderr, flush=True)
    print(out)


if __name__ == "__main__":
    main()
