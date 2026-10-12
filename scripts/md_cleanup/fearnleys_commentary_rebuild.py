"""Rebuild the body of the Fearnleys weekly report MDs (data/extracted/md/fearnleys, PDF-backed) as commentary.

Owner decision 2026-10-12: for these reports only the commentary goes into the GraphRAG corpus; the rate,
price and activity cards (and charts) are Fearnpulse series that come from the Fearnpulse API. The old
bodies were text-layer dumps: commentary complete, but headings out of place (Suezmax text under "## Rates"),
rate cards as loose numbers and headings such as "## WS 27.0". The 2026 W38-W41 MDs (run_fearnleys_normalized.py)
also lost commentary paragraphs and printed rounded / mispaired rates.

The PDF is read by layout (font size, colour, weight), lines in reading order:
  chapter      45 pt blue bold ("Tankers"), numbered by the 96 pt "01"     -> "## 01 Tankers"
  section      27 pt blue bold ("VLCC", "Rates")                           -> "### VLCC" (only if it has text)
  commentary   13.5 pt grey regular                                        -> paragraphs
  subheading   a commentary-style line on its own, <= 4 words, no stop     -> "#### North Sea"
  disclaimer   10.5 pt text after the "Disclaimer" label                   -> "## Disclaimer"
Everything else (cards, chart axes, page headers) is skipped; a chapter that had cards gets one note.

Frontmatter is kept byte-identical. Checks before a body is replaced (any failure leaves the MD as is):
  - every word of the PDF's commentary text is in the new body (same order),
  - every prose sentence of the old body (>= 8 words) is in the new body.

    python scripts/md_cleanup/fearnleys_commentary_rebuild.py [--apply] [paths...]
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "md_cleanup"))
import intermodal_table_rebuild as R  # noqa: E402

MD_DIR = "data/extracted/md/fearnleys"
CARD_NOTE = ("> Rate, price and activity cards of this chapter are not reproduced: Fearnleys rates and prices "
             "come from the Fearnpulse API series.")
# ligatures spelled out; invisible joiners the export puts inside words ("still ⁠at war") dropped
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
                           "⁠": None, "​": None, "‌": None, "‍": None, "﻿": None})
STOP = re.compile(r"[.!?:;)\"”’]$")


def lines_of(doc):
    """[(page, y0, x0, size, colour, bold, text)] in reading order."""
    out = []
    for pno, page in enumerate(doc):
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                t = "".join(s["text"] for s in ln["spans"]).translate(LIGATURES).strip()
                if not t:
                    continue
                s = ln["spans"][0]
                out.append((pno, round(ln["bbox"][1], 1), ln["bbox"][0], round(s["size"], 1),
                            f"{s['color']:06x}", bool(s["flags"] & 16), t))
    return sorted(out, key=lambda r: (r[0], r[1], r[2]))


CHAPTERS = {"Tankers", "Dry Bulk", "Gas", "Newbuilding", "Sale & Purchase", "Market Brief"}
CANON = {c.replace(" ", ""): c for c in CHAPTERS}


def style_of(rows):
    """Layout of one PDF -> dict of predicates on rows (page, y, x, size, colour, bold, text), or None.

    fearnpulse  2023-W28 onward, web report printed from fearnpulse.com: chapters 45 pt blue, sections
                27 pt blue, commentary 13.5 pt regular (grey; one 2024 print is near-black)
    print       2021-2023 "Printer version": chapters are the six chapter names (grey / white, larger than
                the text), sections are a black size just under the commentary size, "Comments" is a label;
                one long page (2021-22), 7-8 pages, or 441 pages of which only the first 5 carry text
    """
    prose = Counter()
    for r in rows:
        if not r[5] and len(r[6].split()) >= 3 and not FURNITURE.search(r[6]):
            prose[(r[3], r[4])] += len(r[6])
    if not prose:
        return None
    def blue(c):
        r, g, b_ = int(c[:2], 16), int(c[2:4], 16), int(c[4:], 16)
        return b_ > r + 60
    # Fearnpulse at any print scale k: sections 27k blue, chapters 45k blue, chapter numbers 96k, text 13.5k.
    # The text style is the prose style that has blue section headings at twice its size (the disclaimer
    # can outweigh commentary that the print broke into short lines).
    for (bs, bcol), _ in prose.most_common():
        k = bs / 13.5
        near = lambda v, w, k=k: abs(v - w * k) <= 0.04 * w * k        # noqa: E731
        if bcol != "000000" and any(near(r[3], 27.0) and blue(r[4]) for r in rows):
            return {"name": "fearnpulse", "gap": 30.0 * k,
                    "body": lambda r, bs=bs, bcol=bcol: r[3] == bs and r[4] == bcol and not r[5],
                    "chapter": lambda r, near=near: near(r[3], 45.0) and blue(r[4]),
                    "chapter_no": lambda r, near=near: near(r[3], 96.0),
                    "section": lambda r, near=near: near(r[3], 27.0) and blue(r[4]),
                    "week": lambda r, near=near: near(r[3], 12.0) and r[6].startswith("Week")}
    (bs, bcol), _ = prose.most_common(1)[0]
    if bcol != "000000":
        return None
    sec = [r[3] for r in rows if r[6] == "Comments" and r[4] == "000000"]
    if not sec:
        return None
    ss = Counter(sec).most_common(1)[0][0]
    return {"name": "print", "gap": bs * 2.2,
            "body": lambda r: r[3] == bs and r[4] == "000000" and not r[5],
            "chapter": lambda r: r[6] in CHAPTERS and r[4] in ("ababab", "ffffff") and r[3] > bs,
            "chapter_no": lambda r: False,
            "section": lambda r: r[3] == ss and r[4] == "000000" and r[6] != "Comments",
            "week": lambda r: r[6].startswith("Week ") and r[4] in ("ababab", "ffffff")}


FURNITURE = re.compile(r"fearnpulse\.com|Fearnleys Weekly Report|^\d+\s*(/|of)\s*\d+$|^\d{1,2}/\d{1,2}/\d{2,4}|"
                       r"Printer version|^©|An Astrup Fearnley Company|info@|^[-]$")


def join(lines):
    text = ""
    for t in lines:
        if not text:
            text = t
        elif text.endswith("-") and t[:1].islower() and not re.match(r"(and|or)\b", t):
            text += t
        else:
            text += " " + t
    text = re.sub(r"\s+", " ", text).strip()
    # glyph-spacing artefacts of some prints: "breather .", "WS 67 .5", "owner ʼ s"
    text = re.sub(r"(?<=\d) \.(?=\d)", ".", text)
    text = re.sub(r"(?<=\w) (?=[.,;:](\s|$))", "", text)
    return re.sub(r" ?([ʼ’]) ?(?=[a-z]\b)", r"\1", text)


def commentary_body(rows, st):
    """-> (markdown body lines, commentary text as printed)."""
    out, printed = [], []
    # a paragraph break is a vertical gap clearly larger than the usual line spacing
    body_rows = [r for r in rows if st["body"](r)]
    steps = sorted(b[1] - a[1] for a, b in zip(body_rows, body_rows[1:]) if a[0] == b[0] and b[1] > a[1])
    gap = steps[len(steps) // 2] * 1.45 if steps else st["gap"]
    chapter_no, chapter, section = "", None, None
    chapter_row = None              # a chapter title printed in two pieces ("T" + "ankers") is joined
    pending_section = None          # a section heading waits for its first paragraph
    cards = False                   # current chapter showed cards
    para, last = [], None           # current paragraph lines, (page, y) of its last line
    disclaimer = False
    # the disclaimer text ("All rates published ...") is printed just above its "Disclaimer" label
    disc = []
    first = next((i for i, r in enumerate(rows) if r[6].startswith("All rates published in this report")), None)
    if first is not None:
        for r in rows[first:]:
            if r[6] == "Disclaimer" or r[0] != rows[first][0]:
                break
            if not FURNITURE.search(r[6]):
                disc.append(r)
    disc_rows = {(r[0], r[1], r[2]) for r in disc}

    def flush():
        nonlocal para, pending_section
        if not para:
            return
        text = join(para)
        printed.append(text)
        if pending_section:
            out.extend(["", f"### {pending_section}"])
            pending_section = None
        if len(para) == 1 and len(text.split()) <= 4 and not STOP.search(text) and not disclaimer:
            out.extend(["", f"#### {text}"])
        else:
            out.extend(["", text])
        para = []

    def close_chapter():
        nonlocal cards
        if cards:
            out.extend(["", CARD_NOTE])
        cards = False

    for row in rows:
        pno, y, x, size, col, bold, t = row
        if st["chapter_no"](row):
            chapter_no = t
            continue
        if st["chapter"](row):
            t = CANON.get(t.replace(" ", ""), t)      # "Dr y Bulk" (glyph spacing) -> "Dry Bulk"
            if chapter_row and chapter_row[0] == pno and chapter not in CHAPTERS and chapter + t in CHAPTERS:
                chapter = chapter + t
                out[-1] = f"## {chapter_no} {chapter}".replace("  ", " ").strip()
                continue
            flush()
            close_chapter()
            chapter, section, pending_section, chapter_row = t, None, None, row
            out.extend(["", f"## {chapter_no} {t}".replace("  ", " ").strip()])
            continue
        if st["section"](row):
            flush()
            section, pending_section = t, t
            continue
        if (pno, y, x) in disc_rows or t == "Disclaimer":
            continue
        body = st["body"](row)
        if body and len(t.split()) <= 4 and not STOP.search(t) and (not para or STOP.search(para[-1])):
            flush()                 # a short line of its own after a finished sentence: a subheading
            para.append(t)
            flush()
            last = None
            continue
        if body:
            # a new paragraph after a vertical gap; across a page break only after a full stop
            if para and last:
                step = y - last[1] if pno == last[0] else None
                if (step is not None and step > gap) or (step is None and STOP.search(para[-1])):
                    flush()
            para.append(t)
            last = (pno, y)
            continue
        if chapter and not FURNITURE.search(t) and not st["week"](row):
            cards = True            # a card label / value / change, a card group title, a chart label
        # page headers, footers, chart axes and other furniture: skipped (they do not end a paragraph,
        # so commentary that runs over a page break stays one paragraph)
    flush()
    close_chapter()
    if disc:                        # printed above its "Disclaimer" label at the foot of the last page
        disclaimer, pending_section = True, None
        out.extend(["", "## Disclaimer"])
        para = [r[6] for r in disc]
        flush()
    return out, printed


def words(text):
    return re.findall(r"[A-Za-z0-9]+", text.lower())


def covered(needle_words, hay_words):
    """All words of needle appear in hay in order (subsequence)."""
    it = iter(hay_words)
    return all(w in it for w in needle_words)


def prose_sentences(body):
    out = []
    for ln in body.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith(("|", "#", "<!--", ">", "source:")):
            continue
        for s in re.split(r"(?<=[.!?])\s+", ln):
            w = words(s)
            if len(w) >= 8 and sum(x.isalpha() for x in w) / len(w) > 0.8:
                out.append(s)
    return out


def rebuild(md_path):
    raw = md_path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    m = re.match(r"(---\n.*?\n---\n)(.*)", text, re.S)
    if not m:
        return None, "no frontmatter"
    front, old_body = m.groups()
    pdf = R.source_pdf(text)
    if pdf is None:
        return None, "no pdf"
    doc = pymupdf.open(pdf)
    rows = lines_of(doc)
    st = style_of(rows)
    if st is None:
        return None, "layout not handled yet"
    body, printed = commentary_body(rows, st)
    if not printed:
        return None, "no commentary read"
    title = re.search(r'^title:\s*"?([^"\n]+)', front, re.M)
    week = next((r[6] for r in rows[:40] if st["week"](r)), "")
    head = [f"# {title.group(1) if title else md_path.stem}", ""]
    if week:
        head += [f"**{week}**", ""]
    head += [f"source: `{Path(pdf).relative_to(ROOT if str(pdf).startswith(str(ROOT)) else ROOT.parents[2]).as_posix()}`"
             f"  |  pages: {len(doc)}"]
    new_body = "\n".join(head + body).strip() + "\n"
    nb = words(new_body)
    # check 1: the PDF's commentary, word for word
    pdf_words = words(" ".join(r[6] for r in rows if st["body"](r)))
    if not covered(pdf_words, nb):
        return None, "commentary words not all in new body"
    # check 2: every prose sentence of the old body survives
    # (a sentence made of card / header text, e.g. "LPG/FOB Prices (Propane) (USD/Tonne, Weekly Change)",
    # may go: it is printed in the PDF outside the commentary style)
    other = " ".join(r[6] for r in rows if not st["body"](r))
    other_words = words(other)
    def kept(s):
        # the print's page header timestamp ("11/03/2026, 21:29", "18/1/23, 8:19 μ.μ.") sat inside old sentences
        w = words(re.sub(r"\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(\s*[μπ]\.μ\.)?", " ", s))
        if covered(w, nb) or not (Counter(w) - Counter(other_words)):
            return True
        # a card title glued in front of the prose by the old dump ("LPG Rates concluded out of ...")
        return any(covered(w[:k], other_words) and covered(w[k:], nb) for k in range(1, 9))
    olds = prose_sentences(old_body.translate(LIGATURES))
    lost = [s for s in olds if not kept(join([s]))]
    if len(olds) < 3:
        return None, "old body has no prose to compare"
    if lost:
        return None, f"old prose not in new body: {len(lost)} e.g. {lost[0][:90]!r}"
    new = front + "\n" + new_body
    return (new.replace("\n", "\r\n") if crlf else new), "ok"


def main():
    apply = "--apply" in sys.argv
    paths = [Path(a) for a in sys.argv[1:] if a.endswith(".md")]
    if not paths:
        out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z", MD_DIR], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8").stdout
        paths = sorted(Path(p) for p in out.split("\0") if p.endswith(".md"))
    stat = Counter()
    for p in paths:
        path = p if p.is_absolute() else ROOT / p
        raw = path.read_bytes()
        if b"\nsource_file:" not in raw[:2000]:
            stat["no source pdf (API commentary)"] += 1
            continue
        new, why = rebuild(path)
        stat[why.split(":")[0]] += 1
        if new is None:
            if why not in ("layout not handled yet",):
                print(f"SKIP {path.name}: {why}")
            continue
        if new.encode("utf-8") != raw:
            stat["changed"] += 1
            if apply:
                path.write_bytes(new.encode("utf-8"))
    for k, v in sorted(stat.items()):
        print(f"{v:6d}  {k}")
    print("(applied)" if apply else "(dry run)")


if __name__ == "__main__":
    main()
