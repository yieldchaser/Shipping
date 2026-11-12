"""§7.4 acceptance gate — code checks every record, model output never trusted (plan §7.4).

Implements rules 1-5 for one chunk response:
  1. schema (done by `extract_schema.parse_extraction`)
  2. `sids` exist in the cited chunk; the quote is sliced by code from the sentence offsets (D7),
     capped at 3 sentences
  3. every printed number in `attrs_printed`, `magnitude_printed`, `when_printed`, `horizon_printed`
     occurs in the sliced quote — otherwise the record is DROPPED
  4. `src`, `dst` and roles resolve to a known id or to a `new_entities` item; a new entity name must
     occur in its own cited sentences
  5. dates are resolved by code from the printed text + `published_at` ("this week", "Q3"); the model
     never computes dates

Records that fail rule 2-4 are dropped and counted; rule 5 resolutions are attached so layer C can
store parsed intervals. Pure functions; unit-tested in `kb/tests/test_p4b.py`.
"""
from __future__ import annotations

import datetime as dt
import re

from extract_schema import NUMBER_RE, Extraction

MAX_QUOTE_SENTENCES = 3


def _boundary_match(needle: str, hay: str) -> bool:
    """True if `needle` occurs in `hay` and is not embedded inside a longer number.

    "2" inside "2,000" or "2025-07" must not match; "2026" in "September 30, 2026, our" must."""
    if not needle:
        return True
    start = 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            return False
        before = hay[i - 1] if i > 0 else " "
        after = hay[i + len(needle)] if i + len(needle) < len(hay) else " "
        before_num = before.isdigit() or (before in ".,/" and i >= 2 and hay[i - 2].isdigit())
        j = i + len(needle)
        after_num = after.isdigit() or (after in ".,/" and j + 1 < len(hay) and hay[j + 1].isdigit())
        if not before_num and not after_num:
            return True
        start = i + 1


def quote_for(rec_sids: list[int], sentences: list[tuple[int, str]]) -> tuple[str, list[int]]:
    """Rule 2: slice the quote by code from the cited sentences, capped at 3 sentences."""
    by_sid = dict(sentences)
    ok = sorted({s for s in rec_sids if s in by_sid})
    keep = ok[:MAX_QUOTE_SENTENCES]
    return " ".join(by_sid[s] for s in keep), keep


def printed_values(rec) -> list[str]:
    """Rule 3 inputs: the printed strings that must appear in the quote."""
    vals = []
    kind = type(rec).__name__
    if kind == "StateFact":
        vals = [a.value_as_printed for a in rec.attrs_printed]
        vals += [rec.valid_from_printed, rec.valid_to_printed]
    elif kind == "Event":
        vals = [rec.when_printed, rec.magnitude_printed]
    elif kind == "Claim":
        vals = [rec.horizon_printed]
    return [v for v in vals if v and str(v).strip()]


def numbers_ok(values: list[str], quote: str) -> tuple[bool, list[str]]:
    """Rule 3: every number as printed must occur in the quote after slicing."""
    missing = []
    for v in values:
        for num in NUMBER_RE.findall(str(v)):
            if not _boundary_match(num, quote):
                missing.append(num)
    return (not missing), missing


# --- rule 5: date resolution by code -------------------------------------------------------
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"], start=1)}
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4}

ISO_RE = re.compile(r"\b(19|20)\d{2}-\d{2}-\d{2}\b")
DOTTED_RE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./]((?:19|20)\d{2})\b")
MONTH_RE = re.compile(r"\b(" + "|".join(MONTHS) + r")\b\.?", re.I)
DAY_AFTER_MONTH_RE = re.compile(r"\s*(?:(\d{1,2})(?:st|nd|rd|th)?,?\s+)(?=\d{4}|,)|(\d{1,2}),\s*")
QUARTER_RE = re.compile(r"\bQ([1-4])\s*((?:19|20)\d{2})?\b", re.I)
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
WEEK_RE = re.compile(r"\b(this|last|next)\s+(week|month|quarter|year)\b", re.I)
DAYS_RE = re.compile(r"\b(yesterday|today|tomorrow)\b", re.I)
REL_DAYS_RE = re.compile(r"\b(\d{1,2})\s+days?\s+(ago|earlier|before|prior)\b", re.I)


def _month_end(year: int, month: int) -> dt.date:
    if month == 12:
        return dt.date(year, 12, 31)
    return dt.date(year, month + 1, 1) - dt.timedelta(days=1)


def resolve_printed(text: str, published_at: dt.date | None) -> dict | None:
    """Resolve a printed date phrase to {'start','end','grain','as_printed'} or None.

    Deterministic: only handles forms that can be read without guessing. "this week" resolves to the
    calendar week around `published_at`; a bare quarter to its first/last day; a bare year to Jan1/Dec31.
    """
    if not text:
        return None
    s = str(text).strip()
    low = s.lower()
    if published_at:
        m = WEEK_RE.search(low)
        if m:
            unit = m.group(2).lower()
            if unit == "week":
                start = published_at - dt.timedelta(days=published_at.weekday())
                end = start + dt.timedelta(days=6)
            elif unit == "month":
                start = published_at.replace(day=1)
                end = _month_end(start.year, start.month)
            elif unit == "quarter":
                q = (published_at.month - 1) // 3
                start = dt.date(published_at.year, 3 * q + 1, 1)
                end = _month_end(start.year, start.month + 2)
            else:
                start, end = dt.date(published_at.year, 1, 1), dt.date(published_at.year, 12, 31)
            shift = {"this": 0, "last": -1, "next": 1}[m.group(1).lower()]
            if shift:
                if unit == "week":
                    start, end = start + dt.timedelta(days=7 * shift), end + dt.timedelta(days=7 * shift)
                elif unit == "month":
                    y, mo = start.year, start.month + shift
                    y, mo = (y + (mo - 1) // 12, (mo - 1) % 12 + 1)
                    start, end = dt.date(y, mo, 1), _month_end(y, mo)
                elif unit == "quarter":
                    y, q = start.year, (start.month - 1) // 3 + 1 + shift
                    y, q = (y + (q - 1) // 4, (q - 1) % 4 + 1)
                    start = dt.date(y, 3 * (q - 1) + 1, 1)
                    end = _month_end(y, start.month + 2)
                else:
                    start, end = dt.date(start.year + shift, 1, 1), dt.date(start.year + shift, 12, 31)
            return {"start": start.isoformat(), "end": end.isoformat(), "grain": unit, "as_printed": s}
        m = DAYS_RE.search(low)
        if m:
            d = published_at + dt.timedelta(days={"yesterday": -1, "today": 0, "tomorrow": 1}[m.group(1).lower()])
            return {"start": d.isoformat(), "end": d.isoformat(), "grain": "day", "as_printed": s}
        m = REL_DAYS_RE.search(low)
        if m:
            d = published_at - dt.timedelta(days=int(m.group(1)))
            return {"start": d.isoformat(), "end": d.isoformat(), "grain": "day", "as_printed": s}
    m = ISO_RE.search(s)
    if m:
        d = dt.date.fromisoformat(m.group(0))
        return {"start": d.isoformat(), "end": d.isoformat(), "grain": "day", "as_printed": s}
    m = DOTTED_RE.search(s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                day = dt.date(y, mo, d)
            except ValueError:
                day = None
            if day:
                return {"start": day.isoformat(), "end": day.isoformat(), "grain": "day", "as_printed": s}
    m = QUARTER_RE.search(s)
    if m:
        q = int(m.group(1))
        year = int(m.group(2)) if m.group(2) else (published_at.year if published_at else None)
        if year:
            start = dt.date(year, 3 * (q - 1) + 1, 1)
            return {"start": start.isoformat(), "end": _month_end(year, start.month + 2).isoformat(),
                    "grain": "quarter", "as_printed": s}
    m = MONTH_RE.search(s)
    if m:
        month = MONTHS[m.group(1).lower()]
        rest = s[m.end():]
        year = published_at.year if published_at else None
        day = None
        ym = re.match(r"\s*((?:19|20)\d{2})\b", rest)
        if ym:
            year = int(ym.group(1))
        else:
            dm = re.match(r"\s*(\d{1,2})(?:st|nd|rd|th)?\b", rest)
            if dm:
                day = int(dm.group(1))
            ym2 = re.search(r"((?:19|20)\d{2})\b", rest)
            if ym2:
                year = int(ym2.group(1))
        if year:
            if day and 1 <= day <= 31:
                try:
                    d0 = dt.date(year, month, day)
                except ValueError:
                    d0 = dt.date(year, month, 1)
                return {"start": d0.isoformat(), "end": d0.isoformat(), "grain": "day", "as_printed": s}
            start = dt.date(year, month, 1)
            return {"start": start.isoformat(), "end": _month_end(year, month).isoformat(),
                    "grain": "month", "as_printed": s}
    m = YEAR_RE.search(s)
    if m:
        year = int(m.group(1))
        return {"start": dt.date(year, 1, 1).isoformat(), "end": dt.date(year, 12, 31).isoformat(),
                "grain": "year", "as_printed": s}
    return None


# --- main gate -----------------------------------------------------------------------------
def gate_chunk(ext: Extraction, chunk: dict) -> dict:
    """Run rules 2-5 over every record of one response (one chunk or a packed call, plan §7.2).

    `chunk` = {"chunk_id": str, "sentences": [(sid, text)], "known_ids": set[str],
               "new_names": {id: name}, "published_at": date|None}
    or, for a packed call: {"chunks": [<the above>], "known_ids": union, "new_names": {...}}.
    Every record is gated against the chunk named in its own `chunk` field; a record citing a
    chunk that is not in the call is dropped (`chunk_mismatch`).
    """
    if "chunks" in chunk:
        parts = list(chunk["chunks"])
        default_published = chunk.get("published_at")
    else:
        parts = [chunk]
        default_published = chunk.get("published_at")
    cmap = {p["chunk_id"]: p for p in parts}
    default = parts[0]
    cid = default["chunk_id"]
    known_ids = set(chunk.get("known_ids") or ())
    for p in parts:
        known_ids |= set(p.get("known_ids") or ())
    new_names = dict(chunk.get("new_names") or {})
    for p in parts:
        new_names.update(p.get("new_names") or {})
    sentences = default.get("sentences") or []
    published = default.get("published_at", default_published)
    valid_sids = {s for s, _ in sentences}

    records: list[dict] = []
    kept = {"state_facts": [], "events": [], "claims": []}

    def verdict(kind: str, idx: int, rec, quote: str, reasons: list[str]) -> dict:
        return {"kind": kind, "index": idx, "quote": quote, "dropped": bool(reasons),
                "reasons": reasons, "chunk": rec.chunk, "sids": list(rec.sids),
                "confidence": float(rec.confidence) if getattr(rec, "confidence", None) is not None else None}

    # rule 4 needs the new entities' sentence text: a name must occur in its own cited sentences
    new_ok = {}
    for ne in ext.new_entities:
        part = cmap.get(ne.chunk)
        ne_sents = (part or default).get("sentences") or []
        q, _keep = quote_for(ne.sids, ne_sents)
        new_ok[ne.id] = bool(ne.name and re.search(re.escape(ne.name.strip()), q, re.I))
        new_names.setdefault(ne.id, ne.name)

    def resolve_entity(ref: str, quote: str) -> bool:
        if ref in known_ids or ref in new_ok:
            return ref not in new_ok or new_ok[ref]
        return False

    for kind, items in (("state_facts", ext.state_facts), ("events", ext.events), ("claims", ext.claims)):
        for idx, rec in enumerate(items):
            reasons: list[str] = []
            part = cmap.get(rec.chunk)
            if part is None:
                reasons.append("chunk_mismatch")
                part = {"sentences": [], "published_at": published}
            sentences = part.get("sentences") or []
            valid_sids = {s for s, _ in sentences}
            rec_published = part.get("published_at", published)
            quote, keep = quote_for(rec.sids, sentences)
            if [s for s in rec.sids if s not in valid_sids]:
                reasons.append("sid_missing")
            if not quote:
                reasons.append("quote_empty")
            ok_nums, missing = numbers_ok(printed_values(rec), quote)
            if not ok_nums:
                reasons.append("number_not_in_quote:" + ",".join(missing[:4]))
            attr_notes: list[str] = []
            if kind == "state_facts":
                for ref in (rec.src, rec.dst):
                    if not resolve_entity(ref, quote):
                        reasons.append(f"entity_unresolved:{ref}")
                # Plan §7.4 gates 1-4 do not whitelist attr keys; an unexpected key is a metric,
                # not a drop, because §7.3 types `key` as a free string.
                allowed = set(EDGE_TYPES_ATTRS.get(rec.type, []))
                attr_notes = [a.key for a in rec.attrs_printed if a.key not in allowed]
            elif kind == "events":
                for role in rec.roles:
                    if not resolve_entity(role.entity, quote):
                        reasons.append(f"entity_unresolved:{role.entity}")
            else:
                for ref in rec.subjects:
                    if not resolve_entity(ref, quote):
                        reasons.append(f"entity_unresolved:{ref}")
            v = verdict(kind, idx, rec, quote, reasons)
            v["attr_notes"] = attr_notes
            if kind == "state_facts":
                v["valid_from"] = resolve_printed(rec.valid_from_printed, rec_published)
                v["valid_to"] = resolve_printed(rec.valid_to_printed, rec_published)
                v["date_unresolved"] = [x for x, r in ((rec.valid_from_printed, v["valid_from"]),
                                                       (rec.valid_to_printed, v["valid_to"])) if x and r is None]
            elif kind == "events":
                v["when"] = resolve_printed(rec.when_printed, rec_published)
            else:
                v["horizon"] = resolve_printed(rec.horizon_printed, rec_published)
            records.append(v)
            if not reasons:
                kept[kind].append(rec)
    total = len(records)
    ok = total - sum(1 for r in records if r["dropped"])
    return {"chunk_id": cid, "records_total": total, "records_ok": ok,
            "gates_2_4_failed": total - ok, "records": records,
            "kept": kept, "new_entities_ok": {k: v for k, v in new_ok.items()},
            "no_content": ext.no_content}


# allowed printed-attr keys per edge type (imported lazily to keep this module pure)
from extract_schema import EDGE_TYPES as EDGE_TYPES_ATTRS  # noqa: E402
