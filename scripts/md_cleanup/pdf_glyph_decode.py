"""Exact text for PDF pages whose embedded subset fonts carry a bogus ToUnicode map.

Some Office-exported PDFs (Banchero Costa 2024-2026) embed TrueType subsets whose ToUnicode map is an
identity over the subset codes, so a plain extraction returns "!\"#$" for "Unit". The glyph outlines
are intact, though: each subset glyph is matched by exact outline geometry against the reference font
of the same name (Calibri, Arial), which gives the real character. MuPDF's text trace reports each
character's glyph id. Several subsets of one font share a name on a page, so a span is assigned to the
subset whose glyph advances reproduce the span's character widths; a span that two subsets fit equally
well but decode differently (one tabular digit) takes the subset of the nearest unambiguous span.

Where a glyph's outline is not in the reference set, the trace's own Unicode is kept when that subset's
ToUnicode map agrees with the outlines elsewhere on the page, else U+FFFD marks it.

The reference outlines live in pdf_glyph_reference.json (outline hash -> character per font name), built
once from the Windows system fonts with --build-reference, so CI needs no fonts installed.

    python scripts/md_cleanup/pdf_glyph_decode.py --build-reference
    python scripts/md_cleanup/pdf_glyph_decode.py FILE.pdf PAGE      # print decoded spans
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from functools import lru_cache
from pathlib import Path

import pymupdf
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

REFERENCE = Path(__file__).with_name("pdf_glyph_reference.json")
SYSTEM_FONTS = {
    "Calibri": "calibri.ttf", "Calibri-Bold": "calibrib.ttf", "Calibri-Italic": "calibrii.ttf",
    "Calibri-BoldItalic": "calibriz.ttf", "ArialMT": "arial.ttf", "Arial-BoldMT": "arialbd.ttf",
    "Arial-ItalicMT": "ariali.ttf", "Arial-BoldItalicMT": "arialbi.ttf",
}
# Basic Latin first so that a shape shared by two code points maps to the ASCII one
RANGES = [(0x21, 0x7E), (0xA0, 0x24F), (0x2010, 0x205E), (0x20A0, 0x20C0), (0x2100, 0x2150), (0x2190, 0x21FF),
          (0x2200, 0x22FF), (0x25A0, 0x25FF)]
AMBIGUOUS_GAP = 0.05


def _outline(glyphset, gname):
    pen = DecomposingRecordingPen(glyphset)
    glyphset[gname].draw(pen)
    pts = tuple((op, tuple(tuple(round(c) for c in pt) if pt is not None else None for pt in args))
                for op, args in pen.value)
    return pts, glyphset[gname].width


def _hash(outline):
    return hashlib.sha1(repr(outline).encode()).hexdigest()[:16]


def build_reference(font_dir=Path("C:/Windows/Fonts")):
    ref = {}
    for name, fname in SYSTEM_FONTS.items():
        t = TTFont(font_dir / fname)
        gs, cmap = t.getGlyphSet(), t.getBestCmap()
        table = {}
        for lo, hi in RANGES:
            for cp in range(lo, hi + 1):
                g = cmap.get(cp)
                if g:
                    outline, _ = _outline(gs, g)
                    if outline:
                        table.setdefault(_hash(outline), chr(cp))
        ref[name] = table
    REFERENCE.write_text(json.dumps(ref, ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8")
    return ref


@lru_cache(None)
def reference():
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


def _font_key(basefont):
    return basefont.split("+")[-1]


def subset_maps(doc, pno):
    """{font name: [(gid -> char, gid -> advance per unit size, basefont)]} for the page's subsets."""
    ref, out = reference(), {}
    for xref, ext, typ, basefont, *_ in doc[pno].get_fonts():
        name = _font_key(basefont)
        if name not in ref or "+" not in basefont:
            continue
        buf = doc.extract_font(xref)[3]
        if not buf:
            continue
        try:
            t = TTFont(io.BytesIO(buf))
            gs, upem = t.getGlyphSet(), t["head"].unitsPerEm
            chars, adv = {}, {}
            for gid, gname in enumerate(t.getGlyphOrder()):
                outline, width = _outline(gs, gname)
                chars[gid] = ref[name].get(_hash(outline)) if outline else " "
                adv[gid] = width / upem
        except Exception:
            continue
        out.setdefault(name, []).append((chars, adv, basefont))
    return out


def decode_page(doc, pno):
    """[(bbox, text, basefont or None, size)] per text-trace span, decoded from glyph outlines."""
    maps = subset_maps(doc, pno)
    pending, trust = [], {}
    for sp in doc[pno].get_texttrace():
        uni = "".join(chr(c[0]) for c in sp["chars"])
        gids = [c[1] for c in sp["chars"]]
        fits = []
        for chars, adv, bf in maps.get(sp["font"], []):
            if any(g not in chars for g in gids):
                continue
            err = sum(abs((c[3][2] - c[3][0]) - adv[g] * sp["size"]) for c, g in zip(sp["chars"], gids))
            fits.append((err, [chars[g] for g in gids], bf))
        fits.sort(key=lambda f: f[0])
        if fits:   # does this subset's ToUnicode agree with the outlines we can read?
            for ch, c in zip(fits[0][1], sp["chars"]):
                if ch not in (None, " "):
                    t = trust.setdefault(fits[0][2], [0, 0])
                    t[0] += ch == chr(c[0])
                    t[1] += 1
        amb = len(fits) > 1 and fits[1][0] - fits[0][0] < AMBIGUOUS_GAP and fits[1][1] != fits[0][1]
        pending.append((sp["bbox"], uni, fits, amb, sp["size"]))

    def text(dec, bf, uni):
        a, n = trust.get(bf, (0, 0))
        ok = n and a / n > 0.95
        return "".join(ch if ch is not None else (u if ok else "\ufffd") for ch, u in zip(dec, uni))

    spans = []
    for bbox, uni, fits, amb, size in pending:
        if not fits:
            spans.append((bbox, uni, None, size))
            continue
        pick = fits[0]
        if amb:
            cy, cx = (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2
            near = sorted((abs((b[1] + b[3]) / 2 - cy) + abs((b[0] + b[2]) / 2 - cx), f[0][2])
                          for b, _, f, a, _ in pending if f and not a)
            if near:
                pick = next((f for f in fits if f[2] == near[0][1] and f[0] - fits[0][0] < AMBIGUOUS_GAP), fits[0])
        spans.append((bbox, text(pick[1], pick[2], uni), pick[2], size))
    return spans


if __name__ == "__main__":
    if "--build-reference" in sys.argv:
        ref = build_reference()
        print({k: len(v) for k, v in ref.items()})
    else:
        doc = pymupdf.open(sys.argv[1])
        for bbox, s, bf, size in decode_page(doc, int(sys.argv[2]) - 1):
            print([round(x) for x in bbox], round(size, 1), repr(s), bf)
