"""Visual audit helper: put the printed page in front of a vision model next to our Markdown.

Subcommands (all PNGs go to --out, default <tmp>/page_view; open them with your image viewer/read tool):

  absent MD
      Numbers (>=3 digits, not years) in the MD body that are NOT on the source PDF's text layer
      (source_file in the frontmatter; 3.285 = 3,285 = 3285 accepted). For each, the row label and the
      page(s) where that label is printed; renders those pages with the label highlighted.
      Absent != wrong: outlined/raster pages have no text layer, change columns may be computed.
      LOOK at every rendered page before deciding anything.

  page PDF PAGE [--find TEXT ...] [--dpi 150]
      Render one page; every text-layer match of each --find is boxed in red.

  side MD PDF PAGE [--grep TEXT]   (best first look at any page)
      One PNG: page render on the left, the MD lines on the right (only lines containing TEXT
      if given; else only the MD table lines whose numbers are on this page; MD numbers missing from
      the page text layer are marked >>like this<<). Compare every cell; look hardest at >> <<.

  crop PDF PAGE (--find TEXT | --bbox x0,y0,x1,y1) --save PATH [--dpi 300]
      Evidence crop for check_evidence.py kind=image: the full-width row band around TEXT (or the
      bbox in PDF points). Save under docs/handoff/evidence/<lane>/.

PAGE is 1-based. --corpus-root (default: the main checkout C:/Users/Dell/Github/Shipping, then repo)
resolves corpus/... paths.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
NUM = re.compile(r"\d[\d.,]*\d|\d")
RED = (1, 0, 0)


def nums(s: str) -> list[str]:
    out = []
    for n in NUM.findall(s):
        d = re.sub(r"[.,]", "", n)
        if len(d) <= 2 or (len(n) == 4 and n.isdigit() and 1900 <= int(n) <= 2099):
            continue
        out.append(n.strip(".,"))
    return out


def canon(n: str) -> set[str]:
    """3.285 = 3,285 = 3285, and the value itself (881 = 881.00, 24.0 = 24) under each separator reading."""
    out = {n, n.replace(",", "."), n.replace(".", ","), re.sub(r"[.,]", "", n)}
    for s in (n.replace(",", ""), n.replace(".", "").replace(",", "."), n.replace(",", ".")):
        try:
            out.add(repr(round(float(s), 4)))
        except ValueError:
            pass
    return out


def resolve(p: str, root: str) -> Path:
    for base in (Path(root), ROOT):
        if (base / p).exists():
            return base / p
    sys.exit(f"not found: {p} (tried {root} and {ROOT})")


def md_split(md: Path) -> tuple[dict, list[str]]:
    text = md.read_text(encoding="utf-8", errors="replace")
    fm, body = {}, text
    if text.startswith("---"):
        head, _, body = text[3:].partition("\n---")
        for ln in head.splitlines():
            k, _, v = ln.partition(":")
            fm[k.strip()] = v.strip().strip("'\"")
    return fm, body.splitlines()


def render(doc, page: int, finds: list[str], dpi: int, out: Path) -> Path:
    pg = doc[page - 1]
    for t in finds:
        for r in pg.search_for(t):
            pg.draw_rect(r + (-2, -2, 2, 2), color=RED, width=1.5)
    path = out / f"p{page:03d}.png"
    pg.get_pixmap(dpi=dpi).save(path)
    return path


def cmd_absent(a, out: Path) -> None:
    fm, lines = md_split(Path(a.md))
    if not fm.get("source_file", "").lower().endswith(".pdf"):
        sys.exit("MD has no PDF source_file")
    doc = pymupdf.open(resolve(fm["source_file"], a.corpus_root))
    words = set()
    for pg in doc:
        for w in pg.get_text("words"):
            for n in NUM.findall(w[4]):
                words |= canon(n.strip(".,"))
    absent, pages = [], {}
    for ln in lines:
        miss = [n for n in nums(ln) if not (canon(n) & words)]
        if not miss:
            continue
        label = ln.strip("| ").split("|")[0].strip() if ln.lstrip().startswith("|") else ln.strip()[:40]
        hit = [i + 1 for i, pg in enumerate(doc) if label and len(label) > 2 and pg.search_for(label[:40])]
        absent.append((label, miss, hit))
        for p in hit[:2]:
            pages.setdefault(p, set()).add(label[:40])
    print(f"{a.md}\n  pages {len(doc)}; text layer chars on p1: {len(doc[0].get_text())}")
    for label, miss, hit in absent:
        print(f"  ABSENT {miss} | row {label[:50]!r} | label on pages {hit or 'none (outlined/raster?)'}")
    if not absent:
        print("  every MD number is on the text layer (still eye-check one table per issue)")
    for p, labels in sorted(pages.items()):
        print("  RENDERED", render(doc, p, sorted(labels), a.dpi, out))


def cmd_page(a, out: Path) -> None:
    doc = pymupdf.open(resolve(a.pdf, a.corpus_root))
    print(render(doc, a.page, a.find or [], a.dpi, out))


def cmd_side(a, out: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont
    doc = pymupdf.open(resolve(a.pdf, a.corpus_root))
    pg_png = render(doc, a.page, [a.grep] if a.grep else [], a.dpi, out)
    _, lines = md_split(Path(a.md))
    if a.grep:
        sel = [ln for ln in lines if a.grep in ln]
    else:
        # MD table lines that belong to THIS page: a line whose numbers are mostly on the page's text
        # layer. Raster/outlined pages have no text layer -> show every table line.
        words = set()
        for w in doc[a.page - 1].get_text("words"):
            for n in NUM.findall(w[4]):
                words |= canon(n.strip(".,"))
        tbl = [ln for ln in lines if ln.lstrip().startswith("|")]
        if words:
            def on_page(ln):
                ns = nums(ln)
                return not ns or sum(bool(canon(n) & words) for n in ns) * 2 >= len(ns)
            keep = [ln for ln in tbl if on_page(ln)]
            # drop header/separator lines that are not followed by any kept data line
            sel = [ln for i, ln in enumerate(keep) if nums(ln) or any(nums(x) for x in keep[i + 1:i + 3])]
        else:
            sel = tbl
    sel = sel[:160]
    # mark MD numbers that are NOT on this page's text layer with >> << so the eye goes there first
    if not a.grep and words:
        sel = [re.sub(NUM, lambda m: m.group(0) if (len(re.sub(r"[.,]", "", m.group(0))) <= 2
                                                     or canon(m.group(0).strip(".,")) & words)
                      else f">>{m.group(0)}<<", ln) for ln in sel]
    left = Image.open(pg_png)
    try:
        font = ImageFont.truetype("consola.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    lh = 19
    right_w = 1400
    img = Image.new("RGB", (left.width + right_w, max(left.height, lh * (len(sel) + 2))), "white")
    img.paste(left, (0, 0))
    d = ImageDraw.Draw(img)
    d.text((left.width + 10, 4), f"MD: {Path(a.md).name}", fill="blue", font=font)
    for i, ln in enumerate(sel, 1):
        d.text((left.width + 10, 4 + i * lh), ln[:175], fill="black", font=font)
    path = out / f"side_p{a.page:03d}.png"
    img.save(path)
    print(path)


def cmd_crop(a, out: Path) -> None:
    doc = pymupdf.open(resolve(a.pdf, a.corpus_root))
    pg = doc[a.page - 1]
    if a.bbox:
        rect = pymupdf.Rect(*[float(x) for x in a.bbox.split(",")])
    else:
        hits = pg.search_for(a.find)
        if not hits:
            sys.exit(f"{a.find!r} not on the text layer of page {a.page}: use --bbox (points; "
                     f"page is {pg.rect.width:.0f}x{pg.rect.height:.0f}) after looking at the render")
        r = hits[0]
        rect = pymupdf.Rect(pg.rect.x0, r.y0 - 4, pg.rect.x1, r.y1 + 4)
    Path(a.save).parent.mkdir(parents=True, exist_ok=True)
    pg.get_pixmap(dpi=a.dpi, clip=rect).save(a.save)
    print(a.save, f"bbox={rect.x0:.0f},{rect.y0:.0f},{rect.x1:.0f},{rect.y1:.0f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "page_view"))
    ap.add_argument("--corpus-root", default="C:/Users/Dell/Github/Shipping")
    ap.add_argument("--dpi", type=int, default=150)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("absent"); s.add_argument("md")
    s = sub.add_parser("page"); s.add_argument("pdf"); s.add_argument("page", type=int)
    s.add_argument("--find", action="append")
    s = sub.add_parser("side"); s.add_argument("md"); s.add_argument("pdf"); s.add_argument("page", type=int)
    s.add_argument("--grep")
    s = sub.add_parser("crop"); s.add_argument("pdf"); s.add_argument("page", type=int)
    s.add_argument("--find"); s.add_argument("--bbox"); s.add_argument("--save", required=True)
    a = ap.parse_args()
    if a.cmd == "crop" and a.dpi == 150:
        a.dpi = 300
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    {"absent": cmd_absent, "page": cmd_page, "side": cmd_side, "crop": cmd_crop}[a.cmd](a, out)


if __name__ == "__main__":
    main()
