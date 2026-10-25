"""Intermodal: repair the Newbuilding Orders table where the parse split the size unit into its own cell.

LlamaParse often reads "158,000 dwt" as two cells, "158,000 | dwt". Either the whole table gains a column
(header "Size | Size" or "Size |  |"; nothing is lost) or the row keeps the header's width and drops a cell:
the Delivery cell (yard is then followed by the buyer) or the last cell (Comments). Measured on the 2021-2026
issues: 171 rows in 70 issues, which also shifted the intermodal_newbuilding_orders series by one column.

The unit goes back into Size. A dropped cell is read from the PDF text layer, where each order prints as
"units type size unit yard delivery buyer price comments": Delivery is the token between the yard and the
buyer, Comments the text after the price up to the next order. A value that is not found exactly once is
left blank and reported, never guessed.

    python scripts/md_cleanup/intermodal_orders_fix.py [--apply] [files...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = ROOT / "data" / "extracted" / "md" / "intermodal"
CORPUS = ROOT / "corpus" / "01-brokers" / "intermodal"
UNIT = re.compile(r"^(dwt|teu|cbm|ceu|bopd|gt|cgt|lm|Im|m|m3|cu\.?m\.?|cbm/dwt|dwt/cbm|pax|loa|mtpa|grt|meters|"
                  r"lane meters|tns|tons?|hp|bhp|kw)$", re.I)
DELIV = re.compile(r"^(20\d\d(\s*[-–/]\s*20\d\d)?|undisclosed|prompt|tbc|tba|\w{3}-\d\d|\d{4}-\d{2,4})$", re.I)
ROWSTART = r"\d+(?:\s*\+\s*\d+)*\s+[A-Z][A-Za-z/.]+"
STOP = r"(?=\s+" + ROWSTART + r"|\s+©|\s+www\.|\s+Size\b|\s+Newbuilding Orders|$)"
BLOCK = re.compile(r"(?:^\|[^\n]*\n)+", re.M)


def _esc(v: str) -> str:
    return r"\s*".join(re.escape(ch) for ch in re.sub(r"\s+", "", v.replace("\\", "")))


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def fix_text(text: str, pdf_text: str = "") -> tuple[str, list[str]]:
    """Repair every orders table in one MD text; pdf_text is the issue's PDF text, whitespace-collapsed."""
    notes: list[str] = []

    def fix_block(m: re.Match) -> str:
        lines = m.group(0).rstrip("\n").split("\n")
        h = [c.lower() for c in _cells(lines[0])]
        if not (any("unit" in c for c in h) and any("yard" in c for c in h)) or len(lines) < 3:
            return m.group(0)
        split_hdr = len(h) > 3 and h[2] == "size" and h[3] in ("size", "")
        if split_hdr:
            hdr = _cells(lines[0])
            del hdr[3]
            h = h[:3] + h[4:]
            lines[0] = _row(hdr)
            lines[1] = _row(["---"] * len(hdr))
        hh = h[:-1] if h[-1] == "" else h
        n = len(hh)
        out = lines[:2]
        for ln in lines[2:]:
            c = _cells(ln)
            if split_hdr and len(c) > 3:
                ln = _row(c[:2] + [(c[2] + " " + c[3]).strip()] + c[4:])
            elif len(c) > 3 and UNIT.match(c[3]) and re.search(r"\d", c[2]):
                c = c[:2] + [c[2] + " " + c[3]] + c[4:]
                while len(c) > n and c[-1] == "":
                    c = c[:-1]
                if len(c) == n - 1:
                    di = hh.index("delivery") if "delivery" in hh else None
                    if di is not None and not DELIV.match(c[di]):
                        got = {g.group(1) for g in re.finditer(
                            _esc(c[3]) + r"\s+(\S+(?:\s*[-–]\s*\S+)?)\s+" + _esc(c[di]), pdf_text)}
                        v = got.pop() if len(got) == 1 else ""
                        v = v if DELIV.match(v) else ""
                        c = c[:di] + [v] + c[di:]
                        if not v:
                            notes.append(f"delivery not found: {c[:4]}")
                    else:
                        got = {re.sub(r"\s*(www\.intermodal\.gr|Size|Newbuilding Orders.*)$", "", g.group(1) or "").strip()
                               for g in re.finditer(_esc(c[-2]) + r"\s+" + _esc(c[-1]) + r"(?:\s+(.{0,120}?))??" + STOP,
                                                    pdf_text)}
                        v = got.pop() if len(got) == 1 else ""
                        if re.match(ROWSTART, v) or re.search(r"Units|Newbuilding|Indicative|Demolition", v):
                            v = ""
                        c = c + [v]
                        if not v:
                            notes.append(f"comments empty or not found: {c[:4]}")
                ln = _row(c + [""] * (len(h) - len(c)))
            out.append(ln)
        return "\n".join(out) + "\n"

    return BLOCK.sub(fix_block, text), notes


def pdf_text_of(pdf_path: Path) -> str:
    import pymupdf
    with pymupdf.open(pdf_path) as doc:
        return re.sub(r"\s+", " ", " ".join(p.get_text() for p in doc)).strip()


def rebuild(full_text: str, pdf_path: Path) -> tuple[str, str]:
    """Pipeline hook: repair the parsed text of one issue before its tables are read."""
    if not re.search(r"^\|[^\n]*\bUnits\b[^\n]*\bYard\b", full_text, re.M | re.I):
        return full_text, "no orders table"
    fixed, notes = fix_text(full_text, pdf_text_of(pdf_path))
    if fixed == full_text:
        return full_text, "orders table clean"
    return fixed, "orders table repaired" + (f" ({len(notes)} cell(s) left blank)" if notes else "")


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    files = [Path(a) for a in argv if not a.startswith("--")] or sorted(MD_ROOT.rglob("*.md"))
    changed = 0
    for md in files:
        raw = open(md, encoding="utf-8", newline="").read()
        nl = "\r\n" if "\r\n" in raw else "\n"
        text = raw.replace("\r\n", "\n")
        if not re.search(r"^\|[^\n]*\bUnits\b[^\n]*\bYard\b", text, re.M | re.I):
            continue
        pdf = next(CORPUS.rglob(f"{md.stem}.pdf"), None)
        fixed, notes = fix_text(text, pdf_text_of(pdf) if pdf else "")
        if fixed != text:
            changed += 1
            print(f"{md.name}: repaired" + "".join(f"\n  {n}" for n in notes))
            if apply:
                open(md, "w", encoding="utf-8", newline="").write(fixed.replace("\n", nl))
    print(f"{changed} file(s) {'repaired' if apply else 'to repair'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
