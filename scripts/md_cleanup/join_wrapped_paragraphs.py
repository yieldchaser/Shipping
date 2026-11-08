"""Rejoin sentences that a PDF/HTML conversion cut into separate Markdown paragraphs.

Converters that emit one paragraph per printed line (SEC filings laid out as positioned lines, PDF page text,
books) left a blank line at every line or page end, so one sentence became two or more paragraphs:

    program of work whose appointment is approved by the Audit & Risk

    Committee. There is a clear policy to address any conflicts of

GitHub shows them as separate paragraphs, and a chunker can put the halves in different chunks. This pass joins
paragraph A into the next paragraph B only when A clearly stops mid-sentence:

  * A's last line ends without sentence punctuation (. ? ! : ; or a closing quote / bracket), and
  * B starts lowercase (the same sentence continues), or
  * the file is laid out line by line (most paragraphs are single wrapped lines of similar width) and A is a full
    wrapped line (at least 75% of the file's typical line width) whose last word is followed by a B that is
    ordinary text (not a heading, table, list, bold title or ALL-CAPS line).

Tables, headings, lists, block quotes, HTML, code fences, images and front matter are never joined or moved.
Page furniture between the two halves (`<!-- Page N -->` markers, page numbers such as "-53-" / "F-12" / "Page 4",
and running headers: short single-line paragraphs printed 4+ times in the file) moves to just after the joined
paragraph instead of ending up inside the sentence. Nothing is added or removed: with whitespace removed the
output holds exactly the input's characters, and in the same order once the moved furniture is set aside (checked).

    python scripts/md_cleanup/join_wrapped_paragraphs.py corpus/10-companies            # dry run, counts
    python scripts/md_cleanup/join_wrapped_paragraphs.py corpus/10-companies --apply
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
import sys
from pathlib import Path

END = re.compile(r"[.?!:;\"'”’)\]|*>]\s*$")
MARKER = re.compile(r"^\s*<!--.*-->\s*$")
PAGENUM = re.compile(r"^\s*(?:[-–—]\s*)?(?:Page\s+)?(?:[A-Z]{1,2}-)?\d{1,4}(?:\s+of\s+\d{1,4})?(?:\s*[-–—])?\s*$", re.I)
# a figure / table / source caption the layout dropped into the middle of a sentence
CAPTION = re.compile(r"^\s*(?:\*{1,2}|_)?(?:Figure|Fig\.|Table|Chart|Exhibit|Box|Source|Sources|Note|Notes)\b[^|]*$|^\s*!\[", re.I)
# lowercase roman page numbers ("xli xlii") and OCR'd folios ("l89") are page furniture too
_ROMAN = r"(?=[clxvi])c{0,3}(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
ROMAN_OR_OCR_FOLIO = re.compile(rf"^\s*(?:{_ROMAN}(?:\s+{_ROMAN}){{0,2}}|[lI]\d{{1,3}})\s*$")
# a lowercase start that opens a sub-item, not a continuation: "a) On January", "(b) the", "o general", bullets
SUBITEM = re.compile(r"^(?:\(?[a-z]{1,4}\)\s|o\s|[•·▪◦])")
LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
STRUCT = re.compile(r"^\s*(#|\||>|!\[|<|```|~~~|[-*+]\s|\d+[.)]\s|\*\*|__|---|===|\$\$)")


def _blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    """('fm'|'fence'|'blank'|'marker'|'struct'|'text', lines) in order."""
    out: list[tuple[str, list[str]]] = []
    i, n = 0, len(lines)
    if n and lines[0].strip() == "---":
        j = next((k for k in range(1, n) if lines[k].strip() == "---"), None)
        if j is not None:
            out.append(("fm", lines[: j + 1])); i = j + 1
    while i < n:
        l = lines[i]
        s = l.strip()
        if s.startswith(("```", "~~~")):
            j = i + 1
            while j < n and not lines[j].strip().startswith(s[:3]):
                j += 1
            out.append(("fence", lines[i: j + 1])); i = j + 1; continue
        if not s:
            out.append(("blank", [l])); i += 1; continue
        if MARKER.match(l):
            out.append(("marker", [l])); i += 1; continue
        j = i
        while j < n and lines[j].strip() and not MARKER.match(lines[j]) and not lines[j].strip().startswith(("```", "~~~")):
            j += 1
        para = lines[i:j]
        kind = "struct" if (STRUCT.match(para[0]) or l.startswith(("    ", "\t"))) else "text"
        out.append((kind, para)); i = j
    return out


def _heading_like(s: str) -> bool:
    letters = re.sub(r"[^A-Za-z]", "", s)
    return bool(letters) and letters.isupper() and len(letters) > 3


def _caption(para: list[str]) -> bool:
    """A caption / source line: caption-shaped start, short, one sentence ("Figure 2.3 portrays ... The" is prose)."""
    s = " ".join(x.strip() for x in para)
    return bool(CAPTION.match(para[0])) and (para[0].lstrip().startswith("![") or (
        len(para) <= 2 and len(s) <= 200 and not re.search(r"[a-z]{2}[.?!]\s+[A-Z]", s)))


def _prose(s: str) -> bool:
    """Running text, not a flattened table row: at least half its words start lowercase."""
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", s)
    return len(words) >= 4 and sum(w[0].islower() for w in words) >= 0.5 * len(words)


def join_wrapped(text: str) -> tuple[str, int]:
    crlf = "\r\n" in text
    lines = text.replace("\r\n", "\n").split("\n")
    blocks = _blocks(lines)
    texts = [b[1] for b in blocks if b[0] == "text"]
    single = [len(p[0].strip()) for p in texts if len(p) == 1]
    line_mode = False
    width = 0
    if len(single) >= 20 and len(single) >= 0.6 * max(1, len(texts)):
        width = sorted(single)[int(0.9 * (len(single) - 1))]
        line_mode = 40 <= width <= 140 and statistics.median(single) >= 0.5 * width


    # running headers / footers: short one-line paragraphs repeated 4+ times, page numbers normalised away
    # ("VALE ANNUAL REPORT FORM 20-F | 29" and "... | 30" are one footer)
    shape = lambda s: re.sub(r"\d+", "#", s.strip())
    freq = Counter(shape(b[1][0]) for b in blocks if b[0] in ("text", "struct") and len(b[1]) == 1)
    furniture = {s for s, c in freq.items() if c >= 4 and len(s) <= 80 and re.search(r"[A-Za-z]", s)}
    blocks = [("gap", b[1]) if b[0] in ("text", "struct") and len(b[1]) == 1 and
              (PAGENUM.match(b[1][0]) or ROMAN_OR_OCR_FOLIO.match(b[1][0]) or shape(b[1][0]) in furniture)
              else b for b in blocks]
    out: list[tuple[str, list[str]]] = []
    joins = 0
    k = 0
    while k < len(blocks):
        kind, para = blocks[k]
        # a list item (a footnote "1. Remuneration is reported in US$. The amounts have been") can continue too
        list_a = kind == "struct" and bool(LIST.match(para[0]))
        caption_a = bool(CAPTION.match(para[0])) and not re.search(r"[a-z]{2}[.?!]\s+[A-Z]", para[0])
        if not (kind == "text" or list_a) or caption_a:   # a caption is never the first half of a sentence
            out.append((kind, para)); k += 1; continue
        cur = list(para)
        moved: list[list[str]] = []
        while True:
            # next text paragraph, across blanks and page markers only
            m = k + 1
            gap_markers, captions = [], []
            while m < len(blocks):
                kd = blocks[m][0]
                if kd in ("marker", "gap"):
                    gap_markers.append(blocks[m][1])
                elif kd in ("text", "struct") and len(captions) < 6 and (
                        _caption(blocks[m][1]) or blocks[m][1][0].lstrip().startswith("|")):   # caption or table
                    captions.append(m); gap_markers.append(blocks[m][1])
                elif kd != "blank":
                    break
                m += 1
            if m >= len(blocks) or blocks[m][0] != "text":
                break
            last, nxt = cur[-1].rstrip(), blocks[m][1][0].strip()
            if END.search(last) or len(last.strip()) < 3 or _heading_like(last) or PAGENUM.match(last):
                break
            ok = bool(re.match(r"[a-z]", nxt)) and not re.match(r"(?:www\.|https?:|mailto:)", nxt) \
                and not SUBITEM.match(nxt)
            if not ok and line_mode and len(last.strip()) >= 0.75 * width and not _heading_like(nxt) \
                    and re.search(r"[A-Za-z,]$", last) and re.match(r"[A-Z0-9(\"'“$]", nxt):
                ok = True
            if list_a and not re.match(r"[a-z]", nxt):
                break
            if not ok or (captions and not (re.match(r"[a-z]", nxt) and _prose(last) and len(last.strip()) >= 40)):
                break
            for ci in captions:          # captions / tables jumped over move after the paragraph, like page furniture
                blocks[ci] = ("gap", blocks[ci][1])
            joined = cur[-1].rstrip() + ("" if last.endswith("-") and re.match(r"[a-z]", nxt) else " ") + blocks[m][1][0].lstrip()
            cur = cur[:-1] + [joined] + blocks[m][1][1:]
            moved.extend(gap_markers)
            joins += 1
            k = m
        out.append((kind, cur))
        for mk in moved:
            out.append(("blank", [""])); out.append(("marker", mk))
        k += 1
    new_lines = [l for _, ls in out for l in ls]
    # collapse blank runs we may have created
    res: list[str] = []
    for l in new_lines:
        if not l.strip() and res and not res[-1].strip():
            continue
        res.append(l)
    new = "\n".join(res)
    if text.replace("\r\n", "\n").endswith("\n") and not new.endswith("\n"):
        new += "\n"
    body = lambda bl: re.sub(r"\s+", "", "".join(l for kd, ls in bl if kd not in ("gap", "marker") for l in ls))
    # (captions moved past a sentence were re-tagged "gap" in `blocks` above, so both sides leave them out)
    assert body(out) == body(blocks), "join_wrapped changed text content or order"
    assert Counter(re.sub(r"\s+", "", new)) == Counter(re.sub(r"\s+", "", "\n".join(lines))), "characters added or lost"
    return (new.replace("\n", "\r\n") if crlf else new), joins


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    roots = [a for a in argv if not a.startswith("--")]
    total = files = 0
    if "--changed" in argv:
        # CI: the MDs this run wrote or rewrote (untracked or modified), whichever extractor wrote them
        import subprocess
        out = subprocess.run(["git", "-c", "core.quotepath=off", "status", "--porcelain", "-z", "--untracked-files=all",
                              "--", *(roots or ["data/extracted/md", "corpus"])],
                             capture_output=True, text=True, encoding="utf-8").stdout
        changed = sorted({e[3:] for e in out.split("\0") if e[3:].endswith(".md") and e[:2].strip() in ("??", "M", "A", "AM", "MM")})
        roots = [p for p in changed if Path(p).is_file()]
    for root in roots:
        paths = [Path(root)] if Path(root).is_file() else sorted(Path(root).rglob("*.md"))
        for p in paths:
            raw = p.read_bytes().decode("utf-8")
            new, n = join_wrapped(raw)
            if n:
                files += 1; total += n
                if apply:
                    p.write_bytes(new.encode("utf-8"))
    print(f"{'applied' if apply else 'dry run'}: {total} joins in {files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
