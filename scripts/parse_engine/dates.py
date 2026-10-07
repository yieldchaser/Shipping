"""issue_date extraction. Never invents a date: a full day + month + year must be present."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _build(order: str, groups: tuple[str, ...]) -> date | None:
    try:
        if order == "ymd":
            y, m, d = (int(g) for g in groups[:3])
        elif order == "dmy":
            d, m, y = (int(g) for g in groups[:3])
        elif order == "dmy_name":
            d, y = int(groups[0]), int(groups[2])
            m = MONTHS.get(groups[1].lower().rstrip("."))
            if m is None:
                return None
        else:
            return None
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def _first_match(patterns: list[dict[str, Any]], text: str) -> date | None:
    for p in patterns or []:
        m = re.search(p["regex"], text)
        if m:
            d = _build(p["order"], m.groups())
            if d is not None:
                return d
    return None


STALE_HEADER_MAX_DAYS = 7


def _all_matches(patterns: list[dict[str, Any]], text: str) -> list[date]:
    """Every distinct valid date any filename pattern finds, in pattern order (first = primary)."""
    out: list[date] = []
    for p in patterns or []:
        m = re.search(p["regex"], text)
        if m:
            d = _build(p["order"], m.groups())
            if d is not None and d not in out:
                out.append(d)
    return out


def parse_issue_date(date_patterns: dict[str, Any], header_text: str, filename: str,
                     header_chars: int = 400, folder_year: int | None = None
                     ) -> tuple[str | None, str | None, bool, str | None]:
    """Return (issue_date | None, source, conflict, header_date | None).

    The filename dates come in profile order (printed-date patterns first, crawl-date prefix last);
    names[0] is the primary one. Without a header date the primary filename date is used. With both:
      header == primary filename date                no conflict, source 'header'
      filename_over_header_year_typo                 same day and month as a filename date, but the header year
                                                     is not the folder year and the filename date's year is
      header_corroborated_by_filename                a later filename date equals the header (e.g. the prefix
                                                     is the crawl date)
      filename_over_stale_header                     header earlier than the primary filename date by 1-7 days
      header                                         any other conflict: header wins, conflict left unresolved
    Both dates are always reported (header_date is the date printed in the document). Week-only
    headers ("Week 10") never match."""
    head = _first_match(date_patterns.get("header_text", []), header_text[:header_chars])
    names = _all_matches(date_patterns.get("filename", []), filename)
    name = names[0] if names else None
    head_iso = head.isoformat() if head else None
    if head and name:
        if folder_year is not None and head.year != folder_year:
            typo = next((d for d in names if (d.month, d.day) == (head.month, head.day) and d.year == folder_year), None)
            if typo is not None:
                return typo.isoformat(), "filename_over_header_year_typo", True, head_iso
        if head == name:
            return head_iso, "header", False, head_iso
        if head in names:
            return head_iso, "header_corroborated_by_filename", True, head_iso
        if 1 <= (name - head).days <= STALE_HEADER_MAX_DAYS:
            return name.isoformat(), "filename_over_stale_header", True, head_iso
        return head_iso, "header", True, head_iso
    if head:
        return head_iso, "header", False, head_iso
    if name:
        return name.isoformat(), "filename", False, None
    return None, None, False, None
