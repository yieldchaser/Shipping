"""Rebuild the one 2018 Fearnleys weekly (week 29, July 18 2018) from its text layer.

The PDF embeds three Identity-H subset fonts without a ToUnicode map, so a plain text extraction is
garbage. Each code is the glyph id of the subset (no glyph names, no cmap). The maps below were read
off a rendered grid of every glyph in each embedded font; l/I pairs were told apart by advance width
(regular: l 222, I 277) and by the words they spell (bold "July" / "DIRTY", headings "Fearnleys" /
"NEWBUILDING"). With them every code on the three pages decodes, so the text is exact, not OCR.

MuPDF inserts a synthetic U+0020 at wide gaps, and with no ToUnicode that is indistinguishable from
glyph 32 ("d"); extraction therefore runs with TEXT_INHIBIT_SPACES and table cells are split at the
measured gaps between glyphs instead.

The body follows the sibling print-layout MDs (fearnleys_commentary_rebuild.py): commentary per
chapter and section; rate, price and activity cards are not reproduced. The deal lists of this
edition (newbuilding contracts, sale and purchase transactions) are printed text and are kept as tables.

    python scripts/md_cleanup/fearnleys_2018_glyph_rebuild.py [--apply]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "md_cleanup"))
import intermodal_table_rebuild as R  # noqa: E402
from fearnleys_commentary_rebuild import CARD_NOTE, join  # noqa: E402

MD = ROOT / "data/extracted/md/fearnleys/2018/fearnleys_2018_W29_fw_week_29_2018b.md"

REGU = [None, "A", "n", "o", "t", "h", "e", "r", " ", "l",
        "a", "i", "v", "y", "q", "u", "w", "k", "f", "V",
        "L", "C", "s", ".", "T", "M", "E", "G", "b", "‘",
        "m", "’", "d", ",", "W", "/", "c", "g", "p", "R",
        "N", "S", "-", "U", "z", "x", "B", "F", "j", "D",
        "2", "0", "6", "7", "5", "8", "3", "J", "O", "I",
        "H", "Z", "1", "9", "4", "K", "P", "(", ")", "'",
        "Y", ":", "*", "&", "+", "|", "$"]
BOLD = [None, "J", "u", "l", "y", " ", "1", "8", ".", "V",
        "L", "C", "s", "f", "i", "x", "e", "d", "a", "r",
        "t", "w", "k", ":", "v", "n", "M", "E", "G", "3",
        "0", "D", "I", "R", "T", "Y", "(", "S", "p", "o",
        "W", ")", "h", "2", "H", "g", "A", "N", "/", "c",
        "-", ",", "U", "P", "Z", "X", "B", "6", "5", "b",
        "O", "K", "m", "*", "F", "z"]
HEAD = [None, "T", "A", "N", "K", "E", "R", "S", "C", "r",
        "u", "d", "e", "P", "o", "c", "t", "F", "a", "n",
        "l", "y", "s", " ", "W", "k", "p", "D", "Y", "B",
        "U", "L", "i", "z", "m", "x", "G", "h", "g", "I",
        "O", "H"]
MAPS = {"NimbusSanL-Regu": REGU, "NimbusSanL-Bold": BOLD, "GR-Fearnley": HEAD}
COL_X = 255          # the commentary column starts here; the left column holds the cards
GAP = 0.35           # a gap wider than 0.35 x font size (a space is 0.28) between glyphs starts a new table cell
FLAGS = pymupdf.TEXTFLAGS_RAWDICT | pymupdf.TEXT_CID_FOR_UNKNOWN_UNICODE | pymupdf.TEXT_INHIBIT_SPACES
TABLES = {"NEWBUILDING CONTRACTS": "### Newbuilding Contracts",
          "SALE AND PURCHASE TRANSACTIONS": "## Sale and Purchase Transactions"}


def lines(doc):
    """[(page, y0, x0, size, font, runs)] in reading order; runs = [(x0, text)] split at wide gaps."""
    out = []
    for pno, page in enumerate(doc):
        for b in page.get_text("rawdict", flags=FLAGS)["blocks"]:
            for ln in b.get("lines", []):
                runs, prev = [], None
                for s in ln["spans"]:
                    m = MAPS[s["font"]]
                    for c in s["chars"]:
                        code = ord(c["c"])
                        if code >= len(m) or m[code] is None:
                            raise ValueError(f"unmapped code {code} in {s['font']} on page {pno + 1}")
                        if prev is None or c["bbox"][0] - prev > GAP * s["size"]:
                            runs.append([c["bbox"][0], ""])
                        runs[-1][1] += m[code]
                        prev = c["bbox"][2]
                s0 = ln["spans"][0]
                out.append((pno, round(ln["bbox"][1], 1), round(ln["bbox"][0], 1), round(s0["size"], 1),
                            s0["font"], [(x, t.strip()) for x, t in runs if t.strip()]))
    out.sort(key=lambda r: (r[0], r[1], r[2]))
    return out


def table(rows):
    """Markdown table; the first row is the header and its runs give the column positions."""
    rows = [sorted(r) for r in rows]
    xs = [x for x, _ in rows[0]]
    md = ["| " + " | ".join(t for _, t in rows[0]) + " |", "|" + "---|" * len(xs)]
    for r in rows[1:]:
        cells = [""] * len(xs)
        for x, t in r:
            k = max(i for i, hx in enumerate(xs) if hx <= x + 1.5)
            cells[k] = (cells[k] + " " + t).strip()
        md.append("| " + " | ".join(c.replace("|", r"\|") for c in cells) + " |")
    return md


def body_of(L):
    """Markdown lines of the commentary column: chapters, sections, prose and the two deal tables."""
    out, para, rows = [], [], {}
    chapter, mode = None, None            # mode: None (prose) or the table heading being collected

    def flush():
        if para:
            out.extend([join(para), ""])
            para.clear()
        if mode and rows:
            out.extend(table([rows[y] for y in sorted(rows)]) + [""])
            rows.clear()

    for p, y, x, s, f, runs in L:
        if x < COL_X or y < 60:
            continue
        text = " ".join(t for _, t in runs)
        if f == "GR-Fearnley":
            flush()
            if text in TABLES:
                if text.startswith("SALE") and chapter:      # the deal list closes the Newbuilding chapter
                    out.extend([CARD_NOTE, ""])
                    chapter = None
                mode = text
                out.extend([TABLES[text], ""])
            elif text.isupper():
                if chapter:
                    out.extend([CARD_NOTE, ""])
                chapter, mode = text.title(), None
                out.extend([f"## {chapter}", ""])
            else:
                mode = None
                out.extend([f"### {text}", ""])
        elif mode:
            rows.setdefault((p, y), []).extend(runs)
        elif f == "NimbusSanL-Regu" and s >= 6.5:
            para.append(text)
    flush()
    return out


def main():
    apply = "--apply" in sys.argv
    raw = MD.read_bytes().decode("utf-8")
    doc = pymupdf.open(R.source_pdf(raw))
    L = lines(doc)
    date = next(t for p, y, x, s, f, r in L for _, t in r
                if f == "NimbusSanL-Bold" and re.fullmatch(r"[A-Z][a-z]+ \d+\. \d{4}", t))
    fm = re.match(r"(---\r?\n.*?\r?\n---\r?\n)", raw, re.S).group(1)
    title = re.search(r'^title:\s*"(.*)"', fm, re.M).group(1)
    rel = re.search(r'^source_file:\s*"(.*)"', fm, re.M).group(1)
    text = "\n".join([f"# {title}", "", f"**{date}**", "", f"source: `{rel}`  |  pages: {len(doc)}", ""]
                     + body_of(L) + [CARD_NOTE.replace("of this chapter", "of the Market Brief"), ""])
    text = re.sub(r"\n{3,}", "\n\n", text)
    nl = "\r\n" if "\r\n" in raw else "\n"
    print(text)
    if apply:
        MD.write_bytes((fm + "\n" + text).replace("\r\n", "\n").replace("\n", nl).encode("utf-8"))
        print("(applied)")


if __name__ == "__main__":
    main()
