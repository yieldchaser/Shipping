"""Agora: drop the staff contact directory (names with mobile numbers and skype handles) from the last page.

The PDF's last page is a contact sheet; the extraction dumped it one word per line, staff mobiles included.
It holds no market data. Everything from 'CONTACT DETAILS' up to the company footer 'AGORA SHIPBROKING
CORPORATION' (office addresses and switchboards, kept) becomes one note line. Other text is untouched.

    python scripts/md_cleanup/agora_strip_contacts.py [--apply] [files...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTE = "> Contact details (desk e-mails, staff names and mobile numbers) omitted."
STAFF = re.compile(r"\b(?:mob|skype)\b", re.I)


def seq(lines: list[str], words: tuple[str, ...], start: int = 0) -> int | None:
    """Index of the first line where `words` appear on consecutive non-blank lines (or together on one)."""
    for i in range(start, len(lines)):
        if lines[i].strip().upper().startswith(" ".join(words)):
            return i
        if lines[i].strip().upper() == words[0]:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().upper().startswith(words[1]):
                return i
    return None


def process(text: str) -> str | None:
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    out = None
    # the sheet opens with 'CONTACT DETAILS' (2023+) or, when that heading sits above the footer, with 'Bulk desk:'
    for anchor in (("CONTACT", "DETAILS"), ("BULK", "DESK:")):
        a = seq(lines, anchor)
        b = seq(lines, ("AGORA", "SHIPBROKING"), a) if a is not None else None
        if b is not None and any(STAFF.search(l) for l in lines[a:b]):
            out = lines[:a] + [NOTE, ""] + lines[b:]
            break
    if out is None:
        # 2026 re-parses: a 'Contact Directory' section listing staff as '- **Name** - role (mob: ...)' bullets
        if not any(STAFF.search(l) and l.lstrip().startswith(("-", "*", "|")) for l in lines):
            return None
        out = []
        for l in lines:
            if STAFF.search(l) and l.lstrip().startswith(("-", "*", "|")):
                if not out or out[-1] != NOTE:
                    out.append(NOTE)
                continue
            out.append(l)
    # a stray 'mob:' / 'skype:' outside the sheet (seen on a following page): drop it with its number / handle
    i = 0
    while i < len(out):
        if STAFF.fullmatch(out[i].strip().rstrip(":")):
            j = i + 1
            while j < len(out) and (re.fullmatch(r"[\s+()\d.,-]+", out[j]) and out[j].strip()):
                j += 1
            if out[i].strip().lower().startswith("skype") and j < len(out):
                j += 1
            del out[i:j]
            continue
        i += 1
    if any(STAFF.search(l) for l in out):
        raise ValueError("staff contact left outside the block")
    return nl.join(out)


def main() -> int:
    apply = "--apply" in sys.argv
    files = [Path(a) for a in sys.argv[1:] if not a.startswith("--")] or sorted((ROOT / "data/extracted/md/agora").rglob("*.md"))
    n = 0
    for p in files:
        raw = p.read_bytes().decode("utf-8")
        new = process(raw)
        if new is None or new == raw:
            continue
        n += 1
        if apply:
            p.write_bytes(new.encode("utf-8"))
    print(f"{n} MDs{'' if apply else ' (dry run)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
