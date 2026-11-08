"""Rebuild the Notes and Bibliography of corpus/books/sea_and_civilization_paine.md from the PDF's own layout.

The first conversion broke both sections: every wrapped bibliography line became its own paragraph, notes whose
number is followed by a wide gap ("4.      nationalist ...") rendered as code blocks, a note's last line ("7.", the
page it cites) looked like an empty note, and two-line chapter titles became two headings.

The PDF lays both sections out with a hanging indent: a note starts at x=107 with its number and continues at
x=137; a bibliography entry starts at x=107 and continues at x=122. Chapter titles inside Notes are 25 pt. Lines
that share a baseline (justified lines the PDF emits in pieces) are merged first. Text is taken verbatim; the
check at the end compares the rebuilt sections' characters with the PDF pages' characters.

    python scripts/md_cleanup/paine_backmatter_rebuild.py            # dry run
    python scripts/md_cleanup/paine_backmatter_rebuild.py --apply
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
MD = ROOT / "corpus/books/sea_and_civilization_paine.md"
PDF = ROOT / "corpus/books/sea_and_civilization_paine.pdf"


def page_lines(page):
    """[(x0, size, text)] in reading order, pieces on one baseline merged."""
    rows = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            txt = "".join(s["text"] for s in l["spans"])
            if not txt.strip():
                continue
            rows.append([l["bbox"][1], l["bbox"][0], l["spans"][0]["size"], txt])
    rows.sort(key=lambda r: (round(r[0], 0), r[1]))
    out = []
    for y, x, sz, t in rows:
        if out and abs(out[-1][0] - y) < 2:
            out[-1][3] = (out[-1][3].rstrip() + " " + t.strip())
        else:
            out.append([y, x, sz, t.strip()])
    return [(x, sz, re.sub(r"\s+", " ", t).strip()) for _, x, sz, t in out]


def join(a: str, b: str) -> str:
    # justified lines break after a hyphen only inside a hyphenated word ("Anglo-" / "Saxon"): keep it, no space
    return a + b if a.endswith(("-", "–", "/")) else a + " " + b


def esc(s: str) -> str:
    return re.sub(r"^(\d+)\. ", r"\1\\. ", s)


def notes(doc, p0, p1):
    md, cur, head = [], None, []
    for p in range(p0, p1):
        for x, sz, t in page_lines(doc[p]):
            if sz > 20:
                if t.lower() == "notes":
                    continue
                if cur:
                    md.append(cur); cur = None
                head.append(t); continue
            if head:
                md.append("### " + " ".join(head)); head = []
            m = re.match(r"^(\d+)\.\s+(.*)$", t)
            if x < 120 and m:
                if cur:
                    md.append(cur)
                cur = f"{m.group(1)}. {m.group(2)}"
            elif cur is not None:
                cur = join(cur, t)
            else:
                raise ValueError(f"note text before any note number p{p + 1}: {t[:60]}")
    if cur:
        md.append(cur)
    return md


def bibliography(doc, p0, p1):
    md, cur = [], None
    for p in range(p0, p1):
        for x, sz, t in page_lines(doc[p]):
            if sz > 20:
                if t != "Bibliography":   # sub-headings such as 'Abbreviations'
                    if cur:
                        md.append(esc(cur)); cur = None
                    md.append("### " + t)
                continue
            if x < 115:
                if cur:
                    md.append(esc(cur))
                cur = t
            else:
                if cur is None:
                    raise ValueError(f"continuation before any entry p{p + 1}")
                cur = join(cur, t)
    if cur:
        md.append(esc(cur))
    return md


def chars(s):
    return Counter(re.sub(r"\s+|\\", "", s))


def main():
    doc = pymupdf.open(PDF)
    first = lambda key, lo, hi: next(i for i in range(lo, hi) if doc[i].get_text().strip().startswith(key))
    n0 = first("Notes", 760, 900); b0 = first("Bibliography", n0 + 1, len(doc)); i0 = first("Index", b0 + 1, len(doc))
    N, B = notes(doc, n0, b0), bibliography(doc, b0, i0)
    for name, sec, (lo, hi) in (("notes", N, (n0, b0)), ("bibliography", B, (b0, i0))):
        src = "".join(l[2] for p in range(lo, hi) for l in page_lines(doc[p]) if not (l[1] > 20 and l[2] in ("Notes", "Bibliography")))
        got = "".join(re.sub(r"^#+ ", "", s) for s in sec)
        diff = chars(src) - chars(got), chars(got) - chars(src)
        print(f"{name}: {len(sec)} items, pages {lo + 1}-{hi}, char diff missing={sum(diff[0].values())} extra={sum(diff[1].values())}")
        assert not diff[0] and not diff[1], diff
    raw = MD.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    a, b, c = t.index("\n## Notes\n"), t.index("\n## Bibliography\n"), t.index("\n## Index\n")
    new = (t[:a] + "\n## Notes\n\n" + "\n\n".join(N) + "\n\n## Bibliography\n\n" + "\n\n".join(B) + "\n" + t[c:])
    print("headings in notes:", sum(1 for s in N if s.startswith("###")), "| notes:", sum(1 for s in N if not s.startswith("#")),
          "| bibliography entries:", len(B))
    if "--apply" in sys.argv:
        MD.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
        print("written")


if __name__ == "__main__":
    main()
