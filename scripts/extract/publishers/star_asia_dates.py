"""Star Asia date-cell normalisation (arrival_date / beaching_date).

Measured 2026-09-28 against corpus/01-brokers/star_asia (192 PDFs, 3,327 rows):
the publisher prints dates as European ``DD.MM.YYYY`` and the extractor stored
that string verbatim, so an ISO date join silently dropped 2,680 of 3,327
arrival values.  The stored values are FAITHFUL to the page -- verified against
the PDF text layer of star_asia_2022_W29 (``03.07.2022`` / ``12.07.2022``) --
so this module only reformats and classifies.  It never invents a value it
cannot prove.

Rules
-----
* ``DD.MM.YYYY`` or ``DD-MM-YYYY`` with a 4-digit year  -> ISO ``YYYY-MM-DD``.
* exactly 8 digits with only punctuation separators      -> read as DDMMYYYY
  (recovers ``14.102025`` -> 2025-10-14, ``11..02.2024`` -> 2024-02-11);
  flagged ``RECONSTRUCTED_8DIGIT`` and the raw value is kept.
* status words (AWAITING plus the publisher's own typos AWATIING / AWAIITNG /
  AWATING / AWAITNG, plus ARRESTED / BEACHED / NIL) -> a canonical status
  token in a separate column, NOT a date.
* 6-, 7- or 9-digit year fields (``05.02.206``, ``19.03.20``, ``02.02.20323``)
  are the PUBLISHER's own truncation in the PDF text layer: verified as a
  single span with no detached glyph to its right and a bbox width consistent
  with the glyph count.  Left UNPARSED -- never guessed.
"""
from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from typing import Any, Dict, Tuple

STATUS_CANON = {
    "AWAITING": "AWAITING",
    "AWATIING": "AWAITING",
    "AWAIITNG": "AWAITING",
    "AWATING": "AWAITING",
    "AWAITNG": "AWAITING",
    "ARRESTED": "ARRESTED",
    "BEACHED": "BEACHED",
    "NIL": "NIL",
}

MIN_YEAR = 2015
MAX_YEAR = 2030

_FOUR_DIGIT_YEAR = re.compile(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$")
_DIGITS_ONLY = re.compile(r"\D")


def _clean(value: Any) -> str:
    """Page-faithful cell text: nbsp->space, trim quotes/backticks/space only.

    Accents are PRESERVED (the page really prints 'ÀWAITING'); folding
    happens only for classification, in _fold().
    """
    if value is None:
        return ""
    s = str(value).replace(" ", " ").strip()
    return s.strip("`'‘’\" 	")


def _fold(value: str) -> str:
    """Accent-folded, upper-cased copy used ONLY for status classification."""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.upper()


def _iso_or_none(y: int, m: int, d: int) -> str:
    if not (MIN_YEAR <= y <= MAX_YEAR):
        return ""
    try:
        return _dt.date(y, m, d).isoformat()
    except ValueError:
        return ""


def normalise_date_cell(value: Any) -> Tuple[str, str, str, str]:
    """Return ``(iso_date, status, raw, note)`` for one table cell."""
    raw = _clean(value)
    if raw == "":
        return "", "", "", ""
    if set(raw) <= {"-", "\u2013", "\u2014"}:
        return "", "", raw, "EMPTY_DASH"

    letters = re.sub(r"[^A-Za-z]", "", _fold(raw))
    if letters and letters in STATUS_CANON:
        return "", STATUS_CANON[letters], raw, "STATUS"

    m = _FOUR_DIGIT_YEAR.match(raw)
    if m:
        iso = _iso_or_none(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if iso:
            return iso, "", raw, "EU_DDMMYYYY"
        return "", "", raw, "UNPARSED"

    if not re.search(r"[A-Za-z]", raw):
        digits = _DIGITS_ONLY.sub("", raw)
        if len(digits) == 8:
            iso = _iso_or_none(int(digits[4:8]), int(digits[2:4]), int(digits[0:2]))
            if iso:
                return iso, "", raw, "RECONSTRUCTED_8DIGIT"
    return "", "", raw, "UNPARSED"


def normalise_deal_dates(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Rewrite one deals record in place with ISO dates plus raw/status/note."""
    for field in ("arrival_date", "beaching_date"):
        iso, status, raw, note = normalise_date_cell(rec.get(field))
        rec[field] = iso
        rec[f"{field}_raw"] = raw
        rec[f"{field}_status"] = status
        rec[f"{field}_note"] = note
    return rec
