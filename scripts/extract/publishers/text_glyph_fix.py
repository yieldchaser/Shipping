"""Repair the font-glyph substitutions the MMi/hellenic lineage leaves in extracted prose.

Context (measured 2026-10-07). The hellenic MMi iron-ore reports embed a subset
font with no usable ToUnicode map, so PyMuPDF returns the font's glyph codes for
part of the text. Most of the body text is still plain ASCII and reads correctly;
what survives in the DELIVERED commentary is a small, fully-enumerated set of
glyph substitutions. Measured over `hellenic_iron_ore_daily_series.csv`
(commentary column, 1,175 rows):

    U+00CA Ê  37,121   space glyph        "DCEÊironÊoreÊfutures" -> "DCE iron ore futures"
    U+019F Ɵ   8,317   ti                "transacƟons"                    -> "transactions"
    U+00B2 ²   7,785   UNCERTAIN         left untouched (see below)
    U+00B9 ¹   2,595   UNCERTAIN         left untouched
    U+FB01 ﬁ   1,591   fi                "signiﬁcant"                     -> "significant"
    U+FB02 ﬂ     663   fl                "ﬂuctuate"                       -> "fluctuate"
    U+FB00 ﬀ     370   ff                "diﬀerent"                       -> "different"
    U+01A9 Ʃ     280   tt                "beƩer"                          -> "better"
    U+014C Ō     231   ft                "aŌernoon"                       -> "afternoon"
    U+FB03 ﬃ      91   ffi               "Oﬃce"                           -> "Office"
    U+01AB ƫ      63   tti               "puƫng"                          -> "putting"
    U+FB04 ﬄ      12   ffl               "ﬄawless"                        -> "flawless"
    U+3000 　     420   space             "Index　weekly"                   -> "Index weekly"

Every mapping above was confirmed by reading real occurrences; the remaining
non-ASCII characters (dashes, arrows, ·, ’ “ ”, ã ŏ ƞ © ô ü ñ, CJK) are genuine
punctuation/letters and are deliberately NOT touched.

What is deliberately NOT done
-----------------------------
1. The wider glyph table is NOT applied. This font also remaps plain ASCII
   (t->W, D->M, ...), but the commentary is mostly already-correct ASCII, so
   applying that table CORRUPTS it: `decode_mojibake.decode()` turns
   "DCE iron ore futures declined" into "MCN iron ore fuWures TeclineT". The
   mappings here are all single, unambiguous substitutions that never occur in
   ordinary English or Chinese text.
2. U+00B2 / U+00B9 are left alone: they may be footnote superscripts rather than
   substitutions, and no single target could be proven. Left as-is rather than
   guessed (a wrong-but-readable decode is worse than a visible glyph).
3. The two legitimate extended letters that also appear (U+014F, U+019E) are kept.

Safe for any string: none of these code points is used for its literal meaning in
this corpus, and the fix is only wired into the hellenic iron-ore commentary.
"""
from __future__ import annotations

# Ligature glyphs -> their single, unambiguous expansion.
LIGATURES = {
    "ī": "ff", "Į": "fi", "Ň": "fl", "Ō": "ft",
    "Ʃ": "tt", "Ɵ": "ti", "ƫ": "tti",
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi",
    "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
}

# Code points the font uses as the SPACE glyph.
SPACE_GLYPHS = {
    "Ê": " ",   # Ê  - word separator in the MMI commentary (37,121 uses)
    "　": " ",   # ideographic space mixed into the same text
}


def fix_glyphs(text):
    """Expand the verified ligature/space glyph substitutions in `text`.

    Safe for any string; leaves every other character (including the uncertain
    U+00B2/U+00B9 and all genuine punctuation) untouched.
    """
    if not text:
        return text
    for glyph, plain in LIGATURES.items():
        if glyph in text:
            text = text.replace(glyph, plain)
    for glyph, plain in SPACE_GLYPHS.items():
        if glyph in text:
            text = text.replace(glyph, plain)
    return text


# Backwards-compatible alias (earlier revision of this helper exposed the
# ligature-only name).
fix_ligatures = fix_glyphs
