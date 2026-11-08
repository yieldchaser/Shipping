"""Agora: rebuild the text of the pages that carry no data table (cover, notes, contact sheet) from the PDF.

run_agora wrote those pages one word per line, from word boxes that glue words set less than 2.5pt apart, so
the notes read '1.' / 'CrudeOil-U.S.DollarsandCentsperbarrel(contractof1,000barrels,...' and the cover and
disclaimer were a column of single words. run_agora.page_prose now writes them from the PDF's text blocks with
the printed spacing; this pass puts that text into the stored MDs. Tables, front matter and every other line
are untouched. The contact sheet keeps the existing note and only the letterhead / disclaimer.

Checks per page: with whitespace (and Markdown escapes) removed, the new text holds exactly the characters of
the old one; on the contact sheet the new text holds no staff detail and only characters of the old one.

    python scripts/md_cleanup/agora_prose_rebuild.py [--pdf-root DIR] [--apply]

--pdf-root: a checkout holding corpus/01-brokers/agora/**.pdf (the PDFs are not committed); default: this repo.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
import run_agora  # noqa: E402

MDS = ROOT / "data" / "extracted" / "md" / "agora"
MARK = "_no data table on this page_"


def chars(s: str) -> Counter:
    return Counter(re.sub(r"\s+|\\", "", s))


def rebuild(text: str, doc) -> tuple[str, int]:
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    heads = [i for i, l in enumerate(lines) if re.match(r"^## Page \d+\s*$", l)]
    out, pos, n = [], 0, 0
    for h_i, h in enumerate(heads):
        end = heads[h_i + 1] if h_i + 1 < len(heads) else len(lines)
        body = lines[h + 1:end]
        k = next((j for j, l in enumerate(body) if l.strip()), None)
        if k is None or body[k].strip() != MARK:
            continue
        pno = int(lines[h].split()[2]) - 1
        old = "\n".join(body[k + 1:])
        new = run_agora.page_prose(doc[pno])
        if run_agora.CONTACT_NOTE in new:
            if run_agora.STAFF_RE.search(new.replace(run_agora.CONTACT_NOTE, "")):
                raise ValueError(f"page {pno + 1}: staff detail")
            # (a page holding only a staff line spilled over from the sheet gets the note too)
            gained = chars(new.replace(run_agora.CONTACT_NOTE, "")) - chars(old.replace(run_agora.CONTACT_NOTE, ""))
            if gained:
                raise ValueError(f"page {pno + 1}: contact page gained characters {dict(gained)}")
        elif chars(new) != chars(old):
            raise ValueError(f"page {pno + 1}: characters differ missing={dict(chars(old) - chars(new))} "
                             f"extra={dict(chars(new) - chars(old))}")
        out += lines[pos:h + 1] + body[:k + 1] + ["", new, ""]
        pos = end
        n += 1
    out += lines[pos:]
    res = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return res.replace("\n", nl), n


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    pdf_root = Path(argv[argv.index("--pdf-root") + 1]) if "--pdf-root" in argv else ROOT
    files = pages = 0
    for md in sorted(MDS.rglob("*.md")):
        raw = md.read_bytes().decode("utf-8")
        if MARK not in raw:
            continue
        m = re.search(r'^source_file: "([^"]+\.pdf)"', raw, re.M) or re.search(r"^source: `([^`]+\.pdf)`", raw, re.M)
        pdf = pdf_root / m.group(1)
        if not pdf.exists():
            print("no PDF:", pdf)
            continue
        with pymupdf.open(pdf) as doc:
            new, n = rebuild(raw, doc)
        if n and new != raw:
            files += 1; pages += n
            if apply:
                md.write_bytes(new.encode("utf-8"))
    print(f"{'applied' if apply else 'dry run'}: {pages} pages in {files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
