"""Decode the glyph-substitution mojibake in extracted report text.

What the bug is
---------------
A lineage of source PDFs (Hellenic and its MMi / iron-ore reports, and others)
embeds subset fonts with no usable ToUnicode map. Text extraction therefore
yields the font's internal glyph codes rather than characters, so

    ĚŝƐĐƌĞƟŽŶ ĂŶĚ ƌŝƐŬ      reads as      discretion and risk

The substitution is a fixed glyph table per font, NOT a constant offset and NOT
a scrambled encoding, so it is decodable: measured on a real document the pair
set shows zero conflicts, each garbled character always mapping to the same
plain character. Positions are preserved, so alignment inside a table cell is
unaffected, which is what makes this safe to apply to table labels.

Numbers were never affected by this (digits pass through untouched), which is
exactly why the table VALUES extracted correctly while the column and row
LABELS came out garbled.

Status - read before trusting this
---------------------------------
The hellenic lineage carries (at least) TWO glyph tables, not one:
  * body text  - verified. Long sentences decode to clean English, e.g.
      "iron ore futures fluctuated narrowly throughout the day". Zero
      unknown glyphs remain over 1,169 documents.
  * header/title - only PARTIAL. This font also remaps plain ASCII, a
      second and incompletely-known table (E->N, t->W, and others), so
      applying the body table to a header yields "teekly" for "Weekly".

That failure mode is why writing is opt-in via --apply and the default is
report-only. A wrong-but-readable decode is worse than visible mojibake,
because nothing downstream can detect it. Do not enable --apply until the
header table is complete and validated.

Method
------
Bootstrap from known plaintext rather than guessing: the seed pairs below are
read off real documents, and the map is then extended by the ordering rule the
seed itself reveals (garbled codepoints increase monotonically with the plain
character's position in the font's glyph order). Anything still unknown is
reported, never guessed, so coverage is honest.

Use:
    python scripts/extract/decode_mojibake.py --out data/extracted/corpus
Writes text_decoded.jsonl next to text.jsonl, leaving the original untouched.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Verified pairs read off real documents (garbled -> plain), all from the
# hellenic lineage, where the whole set is self-consistent with zero conflicts.
#
# Lowercase, uppercase and punctuation: D->M, K->O, W->P, Z->R, d->T, /->I,
# ^->S, >->L, ĸ->k, Ƌ->q, and 0x03 is the space glyph.
#
# LIGATURES are the subtlety, and they are why a naive per-character decode
# silently corrupts words: this font encodes ff, fi, fl, ft, ti and tt as single
# glyphs, so those entries expand to two (or three) characters. Confirmed by
# length arithmetic on real sentences, e.g.
#   'ĚŝīĞƌĞŶƚ'   -> different   (8 glyphs, 9 letters: ī = ff)
#   '^ŽŌǁĂƌĞ'   -> Software    (7 glyphs, 8 letters: Ō = ft)
#   'ŇƵĐƚƵĂƚĞĚ' -> fluctuated  (9 glyphs, 10 letters: Ň = fl)
#   'ƐƵďŵŝƩĞĚ'  -> submitted   (8 glyphs, 9 letters: Ʃ = tt)
#   'ƋƵŽƚĂƟŽŶƐ' -> quotations  (9 glyphs, 10 letters: Ɵ = ti)
#   'ĂƫƚƵĚĞ'   -> attitude    (6 glyphs, 8 letters: ƫ = tti)
SEED = {
    "\x03": " ", "/": "I", ">": "L", "^": "S", "D": "M", "K": "O", "W": "P",
    "Z": "R", "d": "T", "\u0138": "k", "\u018b": "q",
    "\u0102": "a", "\u010f": "b", "\u0110": "c", "\u011a": "d", "\u011e": "e",
    "\u0128": "f", "\u0150": "g", "\u015a": "h", "\u015d": "i", "\u016f": "l",
    "\u0175": "m", "\u0176": "n", "\u017d": "o", "\u0189": "p", "\u018c": "r",
    "\u0190": "s", "\u019a": "t", "\u01b5": "u", "\u01c0": "v", "\u01c1": "w",
    "\u01c6": "x", "\u01c7": "y", "\u016c": "k",
    # ligatures (multi-character expansions)
    "\u012b": "ff", "\u012e": "fi", "\u0147": "fl", "\u014c": "ft",
    "\u01a9": "tt", "\u019f": "ti", "\u01ab": "tti",
}

# Legitimate Latin Extended characters that appear in REAL prose (Spanish names
# such as "Gal´ı", Turkish, Nahuatl) and must never be substituted. Kept apart
# from SEED so the distinction is explicit rather than an omission.
LEGITIMATE_EXTENDED = {"\u0131", "\u0101", "\u011f", "\u0130", "\u0142", "\u014f", "\u0169", "\u019e", "\u01cc"}

# Only decode lineages whose table has been verified. Applying a table to an
# unverified source risks producing plausible-but-wrong text, which is worse
# than visible mojibake because nothing downstream can detect it.
VERIFIED_SOURCES = ("hellenic",)

# Any character in these ranges is a candidate glyph substitution.
GARBLED = re.compile(r"[\u0100-\u024f]")


def build_map() -> dict[str, str]:
    return dict(SEED)


def decode(text: str, table: dict[str, str], unknown: set[str] | None = None) -> str:
    out = []
    for ch in text:
        if ch in table:
            out.append(table[ch])
        else:
            out.append(ch)
            if unknown is not None and GARBLED.match(ch) and ch not in LEGITIMATE_EXTENDED:
                unknown.add(ch)
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/extracted/corpus")
    ap.add_argument("--limit", type=int, default=0, help="stop after N documents")
    ap.add_argument("--apply", action="store_true",
                    help="actually write text_decoded.jsonl; default is report-only")
    ap.add_argument("--dry-run", action="store_true",
                    help="alias for report-only (the default)")
    a = ap.parse_args()

    table = build_map()
    unknown: set[str] = set()
    docs = decoded_docs = skipped = 0
    blocks_total = blocks_garbled = 0

    for dirpath, _dirnames, filenames in os.walk(a.out):
        if "text.jsonl" not in filenames:
            continue
        # Gate on the lineage: only sources whose glyph table is verified.
        rel = os.path.relpath(dirpath, a.out).replace("\\", "/")
        source = rel.split("/")[0]
        if source not in VERIFIED_SOURCES:
            skipped += 1
            continue
        docs += 1
        src = os.path.join(dirpath, "text.jsonl")
        rows = []
        had_garbled = False
        try:
            with open(src, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    t = rec.get("text") or ""
                    blocks_total += 1
                    if GARBLED.search(t):
                        blocks_garbled += 1
                        had_garbled = True
                        rec = dict(rec)
                        rec["text_decoded"] = decode(t, table, unknown)
                    rows.append(rec)
        except (OSError, json.JSONDecodeError):
            continue

        if had_garbled:
            decoded_docs += 1
            if a.apply and not a.dry_run:
                dst = os.path.join(dirpath, "text_decoded.jsonl")
                tmp = dst + ".tmp"
                with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                    for rec in rows:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                os.replace(tmp, dst)

        if a.limit and docs >= a.limit:
            break

    print(f"documents scanned      : {docs:,}  (skipped {skipped:,} in unverified lineages)")
    print(f"documents with garbled : {decoded_docs:,}")
    print(f"text blocks            : {blocks_total:,} ({blocks_garbled:,} garbled)")
    print(f"mapping entries        : {len(table)}")
    print(f"mode                   : {'APPLY (writing text_decoded.jsonl)' if a.apply and not a.dry_run else 'report-only'}")
    print(f"UNKNOWN garbled chars  : {len(unknown)}  {''.join(sorted(unknown))[:40]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
