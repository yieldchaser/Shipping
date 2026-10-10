"""Targeted fixer for Star Asia weekly markdown (data/extracted/md/star_asia).

The Star Asia MDs were audited good except two defect classes. This tool repairs ONLY
those; every other byte (including line endings) is preserved. Nothing is re-parsed.

* snapshot - the "Ship Recycling ... Snapshot" price table is broken (header split over
             rows, rows spilled into free text, rows or cells missing, notes merged into
             table cells). The table is rebuilt ONLY from the PDF text layer of that
             table's region: header columns come from the printed header spans, rows from
             the y-clusters of the printed price cells, cells from x-column binding.
             Nothing is computed. A table that already matches the PDF is left alone.
             Where the mangled bullet notes under the table were swallowed into the broken
             region they are re-emitted as bullet lines from the PDF text layer.
* footer   - page furniture lines: text printed at the same position on at least half of
             the PDF pages inside the header/footer band (company URL footer; in the 2026
             template also the "STAR ASIA | WEEKLY MARKET REPORT" / "Week N | date" header,
             "Page N", contact line, membership line). Only whole MD lines whose text
             equals such a PDF furniture line (markdown markup stripped) are removed.

The "## Page N" lines are extractor page markers, not PDF furniture: they are never
removed, only counted.

Source markdown is never modified: fixed copies go to .reparse_staging/star_asia/.

Usage:
    python -m scripts.md_cleanup.star_asia_fix [--detect-only] [--limit N] [--years 2025,2026]
    python -m scripts.md_cleanup.star_asia_fix --promote            # dry-run list (default)
    python -m scripts.md_cleanup.star_asia_fix --promote --apply    # copy changed files
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CHECKOUT = Path(r"C:\Users\Dell\Github\Shipping")
MD_ROOT_REL = Path("data/extracted/md/star_asia")
STAGING_REL = Path(".reparse_staging/star_asia")

CRLF = chr(13) + chr(10)
LF = chr(10)
ESC_STAR = chr(92) + "*"   # the MDs already write a printed asterisk as backslash-star
N_COLS = 6          # DESTINATION + 4 price columns + sentiment
N_ROWS = 4          # Alang, Chattogram, Gaddani, Turkey/Aliaga
HEADER_BAND_TOP = 60.0      # furniture bands (points from page top / bottom)
HEADER_BAND_BOTTOM = 100.0


class SnapshotError(Exception):
    pass


# ---------------------------------------------------------------- text helpers
def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compact(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.lower())


def split_row(line: str) -> list[str]:
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") else body
    return [c.strip() for c in body.split("|")]


def join_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def is_sep(line: str) -> bool:
    return bool(re.match(r"^\|(\s*:?-{3,}:?\s*\|)+\s*$", line.strip()))


def norm_md_line(line: str) -> str:
    t = line.strip()
    t = re.sub(r"^#+\s*", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = t.replace("**", "").replace("__", "")
    t = t.strip("*_ ")
    return squash(t).casefold()


def mask_digits(text: str) -> str:
    return re.sub(r"\d+", "#", text)


# ---------------------------------------------------------------- PDF model
def page_spans(page) -> list[dict]:
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                if s["text"].strip():
                    x0, y0, x1, y1 = s["bbox"]
                    out.append({"x0": x0, "x1": x1, "yc": (y0 + y1) / 2, "text": s["text"],
                                "size": s["size"]})
    return out


def join_spans(spans: list[dict]) -> str:
    """Spans of one printed line, left to right; a space only where the PDF has a gap."""
    out = ""
    prev = None
    for s in sorted(spans, key=lambda s: s["x0"]):
        if prev is not None and s["x0"] - prev["x1"] >= 1.5 \
                and not out.endswith(" ") and not s["text"].startswith(" "):
            out += " "
        out += s["text"]
        prev = s
    return squash(out)


def group_lines(spans: list[dict], tol: float = 3.0) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for s in sorted(spans, key=lambda s: (s["yc"], s["x0"])):
        if lines and abs(lines[-1][0]["yc"] - s["yc"]) <= tol:
            lines[-1].append(s)
        else:
            lines.append([s])
    return lines


def lines_text(spans: list[dict]) -> str:
    """Printed lines top to bottom. A line holding only one or two capitals is the wrapped tail
    of the word above it (header "CONTAINER" / "S"), so no space is inserted."""
    out = ""
    for ln in group_lines(spans):
        t = join_spans(ln)
        glue = bool(re.fullmatch(r"[A-Z]{1,2}", t)) and out[-1:].isalpha()
        out += ("" if glue or not out else " ") + t
    return squash(out)


# ---------------------------------------------------------------- snapshot extraction
PRICE_CELL = re.compile(r"^\*?\$?\d[\d,.]*(\s*[~–-]\s*\$?\d[\d,.]*)?$|^\*?\s*N/?A$", re.I)
PAGE_MARKER = re.compile(r"^#{1,6}\s*Page \d+\s*$")     # extractor marker, never furniture
STRAY_MARK = {".", "·", "•"}     # a lone dot printed under a destination label


def extract_snapshot(spans: list[dict]) -> dict:
    """Return {header, rows, cells, ignored, notes} for the snapshot table on one page."""
    titles = [s for s in spans if "snapshot" in s["text"].lower()]
    if not titles:
        raise SnapshotError("no snapshot title on page")
    top = min(t["yc"] for t in titles)
    below = [s for s in spans if s["yc"] > top + 3]
    dest = [s for s in below if s["text"].strip().upper() == "DESTINATION"]
    tank = [s for s in below if s["text"].strip().upper() == "TANKERS"]
    if not dest or not tank:
        raise SnapshotError("DESTINATION/TANKERS header spans not found")
    dest, tank = min(dest, key=lambda s: s["yc"]), min(tank, key=lambda s: s["yc"])
    price_like = [s for s in below if s["yc"] > dest["yc"] + 10 and PRICE_CELL.match(s["text"].strip())
                  and tank["x0"] - 12 <= (s["x0"] + s["x1"]) / 2 <= tank["x1"] + 12]
    if not price_like:
        raise SnapshotError("no price cells under TANKERS")
    first_price = min(s["yc"] for s in price_like)
    hdr_spans = [s for s in below if s["yc"] < first_price - 8 and abs(s["yc"] - dest["yc"]) <= 40
                 and s["text"].strip() not in STRAY_MARK]
    clusters: list[dict] = []
    for s in sorted(hdr_spans, key=lambda s: s["x0"]):
        if clusters and s["x0"] <= clusters[-1]["x1"] + 3:
            c = clusters[-1]
            c["x1"] = max(c["x1"], s["x1"])
            c["spans"].append(s)
        else:
            clusters.append({"x0": s["x0"], "x1": s["x1"], "spans": [s]})
    if len(clusters) != N_COLS:
        raise SnapshotError(f"{len(clusters)} header columns, expected {N_COLS}")
    for c in clusters:
        c["cx"] = (c["x0"] + c["x1"]) / 2
    header = [lines_text(c["spans"]) for c in clusters]
    hdr_bottom = max(s["yc"] for s in hdr_spans)
    body = [s for s in below if s["yc"] > hdr_bottom + 3]

    def col_of(s):
        cx = (s["x0"] + s["x1"]) / 2
        return min(range(N_COLS), key=lambda i: abs(clusters[i]["cx"] - cx))

    anchors = [s for s in body if 1 <= col_of(s) <= 4 and PRICE_CELL.match(s["text"].strip())]
    row_lines = group_lines(anchors, tol=4.0)
    if len(row_lines) < N_ROWS:
        raise SnapshotError(f"{len(row_lines)} price rows, expected {N_ROWS}")
    row_y = [statistics.mean(s["yc"] for s in ln) for ln in row_lines]
    pitch = statistics.median([b - a for a, b in zip(row_y[:N_ROWS], row_y[1:N_ROWS])])
    if len(row_y) > N_ROWS and row_y[N_ROWS] - row_y[N_ROWS - 1] < 2.5 * pitch:
        raise SnapshotError("more than 4 price rows in the snapshot table")
    row_y = row_y[:N_ROWS]
    bottom = row_y[-1] + 0.75 * pitch
    rows_cells: list[list[list[dict]]] = [[[] for _ in range(N_COLS)] for _ in range(N_ROWS)]
    ignored = []
    for s in body:
        if s["yc"] > bottom:
            continue
        if s["x0"] < clusters[1]["x0"] - 1 and s["x1"] > clusters[2]["x0"] - 5:
            ignored.append(squash(s["text"]))        # a note line running across the table
            continue
        ri = min(range(N_ROWS), key=lambda i: abs(row_y[i] - s["yc"]))
        if abs(row_y[ri] - s["yc"]) > 0.75 * pitch:
            continue
        ci = col_of(s)
        if ci == 0 and s["text"].strip() in STRAY_MARK:
            ignored.append(squash(s["text"]))
            continue
        rows_cells[ri][ci].append(s)
    rows, cells_ev = [], []
    for ri, rc in enumerate(rows_cells):
        row = []
        for ci, sp in enumerate(rc):
            txt = lines_text(sp)
            row.append(txt.replace("*", ESC_STAR))
            if sp:
                cells_ev.append({"row": ri, "col": ci, "text": txt,
                                 "x0": round(min(s["x0"] for s in sp), 1),
                                 "x1": round(max(s["x1"] for s in sp), 1),
                                 "yc": round(statistics.mean(s["yc"] for s in sp), 1)})
        if not row[0] or any(not c for c in row[1:5]):
            raise SnapshotError(f"row {ri} has an empty destination or price cell")
        rows.append(row)
    header = [h.replace("*", ESC_STAR) for h in header]
    units = {unit_key(s["text"]) for s in hdr_spans + [b for b in body if b["yc"] <= bottom]}
    units |= {unit_key(t) for t in header} | {unit_key(c) for r in rows for c in r}
    units.discard("")
    return {"units": units, "title": squash(min(titles, key=lambda t: t["yc"])["text"]), "header": header, "rows": rows, "cells": cells_ev, "ignored": ignored,
            "notes": extract_notes(spans, bottom)}


def extract_notes(spans: list[dict], bottom: float) -> list[str]:
    """Bullet notes printed under the table (up to the next title-sized span)."""
    under = [s for s in spans if s["yc"] > bottom]
    stop = [s["yc"] for s in under if s["size"] >= 11 and len(s["text"].strip()) > 6]
    limit = min(stop) if stop else 1e9
    under = [s for s in under if s["yc"] < limit - 3]
    bullets: list[str] = []
    for ln in group_lines(under):
        ln = sorted(ln, key=lambda s: s["x0"])
        first = ln[0]["text"].strip()
        if len(first) == 1 and not first.isalnum() and first != "*":
            bullets.append(join_spans(ln[1:]))
        elif bullets:
            bullets[-1] = squash(bullets[-1] + " " + join_spans(ln))
    return [b.replace("*", ESC_STAR) for b in bullets if b]


def snapshot_page(doc):
    hits = [p for p in doc if "snapshot" in p.get_text().lower() and "destination" in p.get_text().lower()]
    if len(hits) != 1:
        raise SnapshotError(f"{len(hits)} pages carry a snapshot table")
    return hits[0]


# ---------------------------------------------------------------- furniture
def pdf_furniture(doc) -> dict[tuple, dict]:
    """Lines repeated at the same y on >= half the pages inside the header/footer band."""
    need = max(2, math.ceil(len(doc) * 0.5))
    seen: dict[tuple, dict] = {}
    for page in doc:
        h = page.rect.height
        per_page = {}
        for ln in group_lines(page_spans(page), tol=2.0):
            yc = statistics.mean(s["yc"] for s in ln)
            if not (yc < HEADER_BAND_TOP or yc > h - HEADER_BAND_BOTTOM):
                continue
            text = join_spans(ln)
            per_page[(mask_digits(text.casefold()), round(yc / 6))] = (text, round(yc, 1))
        for key, (text, yc) in per_page.items():
            e = seen.setdefault(key, {"text": text, "yc": yc, "pages": 0})
            e["pages"] += 1
    return {k: v for k, v in seen.items() if v["pages"] >= need}


def furniture_match(line: str, fur: dict) -> dict | None:
    if line.lstrip().startswith("|") or PAGE_MARKER.match(line):
        return None
    t = norm_md_line(line)
    if not t:
        return None
    cands = {t, mask_digits(t)}
    for (key_text, _), e in fur.items():
        if key_text in cands or ("star asia " + key_text) in cands:
            return e
    return None


# ---------------------------------------------------------------- markdown side
HEADING_RE = re.compile(r"snapshot", re.I)
END_RE = re.compile(r"5-?\s*year|^\(week|^\*\*destination|^\|\s*destination\s*\|\s*20\d\d|^## page \d+\s*$", re.I)
INTACT_NOTE = re.compile(r"^-\s+All prices are USD per light displacement tonnage in the long ton\.\s*$")
NOTE_FRAGMENT = re.compile(r"prices reported|displacement tonnage|simple Japanese", re.I)


def find_region(lines: list[str]) -> tuple[int, int, bool, bool] | None:
    """(start, end, notes_swallowed, headless): lines[start:end] is the snapshot region under its
    heading. Headless: the title was swallowed into the table header, so the region starts at that
    table line and the title is restored from the PDF."""
    heads = [i for i, ln in enumerate(lines) if HEADING_RE.search(ln) and "recycl" in ln.lower()
             and len(ln) < 100 and not ln.startswith("|")]
    headless = False
    if not heads:
        heads = [i for i, ln in enumerate(lines) if ln.startswith("|") and "snapshot" in ln.lower()
                 and "destination" in ln.lower()]
        headless = True
    if len(heads) != 1:
        return None
    start = heads[0] if headless else heads[0] + 1
    end = next((j for j in range(start, len(lines))
                if END_RE.search(norm_md_line(lines[j])) or re.match(r"^#{1,6}\s", lines[j])), len(lines))
    intact = next((j for j in range(start, end) if INTACT_NOTE.match(lines[j])), None)
    if intact is not None:
        return start, intact, False, headless
    return start, end, any(NOTE_FRAGMENT.search(ln) for ln in lines[start:end]), headless


def table_rows(region: list[str]) -> list[list[str]] | None:
    nonblank = [ln for ln in region if ln.strip()]
    if not nonblank or not all(ln.startswith("|") for ln in nonblank):
        return None
    return [split_row(ln) for ln in nonblank if not is_sep(ln)]


def region_is_good(region: list[str], snap: dict) -> bool:
    rows = table_rows(region)
    if rows is None or len(rows) != N_ROWS + 1 or any(len(r) != N_COLS for r in rows):
        return False
    if [compact(c) for c in rows[0]] != [compact(c) for c in snap["header"]]:
        return False
    return all(r[0] and [compact(c) for c in r[1:]] == [compact(c) for c in p[1:]]
               for r, p in zip(rows[1:], snap["rows"]))


def region_is_clean_table(region: list[str]) -> bool:
    rows = table_rows(region)
    return rows is not None and len(rows) == N_ROWS + 1 and all(len(r) == N_COLS and r[0] for r in rows)


def build_region(snap: dict, with_notes: bool, old: list[str] | None = None,
                 ascii_dash: bool = False) -> tuple[list[str], dict]:
    """New region lines. Material of the old region that is already intact is kept verbatim: an
    intact header row (6 non-empty cells, DESTINATION first, separator below, no continuation row)
    and every body row whose price/sentiment cells equal the PDF row. Only the rest is rebuilt."""
    rows = [list(r) for r in snap["rows"]]
    if ascii_dash:
        for r in rows:
            r[1:5] = [c.replace("–", "-") for c in r[1:5]]
    header, sep = join_row(snap["header"]), "|" + "---|" * N_COLS
    kept_header, keep = False, {}
    old = old or []
    table = [i for i, ln in enumerate(old) if ln.startswith("|") and ln.rstrip().endswith("|")]
    if table:
        i = table[0]
        cells = split_row(old[i])
        nxt = old[i + 2] if i + 2 < len(old) else ""
        if len(cells) == N_COLS and all(cells) and compact(cells[0]) == "destination"                 and i + 1 < len(old) and is_sep(old[i + 1])                 and not (nxt.startswith("|") and not split_row(nxt)[0]):
            header, sep, kept_header = old[i], old[i + 1], True
        for ln in (old[j] for j in table):
            c = split_row(ln)
            if len(c) == N_COLS and c[0] and not is_sep(ln) and compact(c[0]) != "destination":
                keep.setdefault(tuple(compact(x) for x in c[1:]), ln)
    body = []
    kept_rows = 0
    for r in rows:
        old_ln = keep.get(tuple(compact(x) for x in r[1:]))
        kept_rows += old_ln is not None
        body.append(old_ln if old_ln is not None else join_row(r))
    out = ["", header, sep] + body + [""]
    if with_notes:
        out += ["- " + n for n in snap["notes"]]
        out.append("")
    return out, {"kept_header": kept_header, "kept_rows": kept_rows, "ascii_dash": ascii_dash}


def unit_key(text: str) -> str:
    """A printed table cell/span with markdown escapes removed (case kept)."""
    return squash(re.sub(r"\\?\*", "", text))


def is_cell_sequence(line: str, units: set[str]) -> bool:
    """True if the line is a whole-token concatenation of printed table cells/spans."""
    toks = unit_key(line).split()
    ok = [True] + [False] * len(toks)
    for i in range(len(toks)):
        if ok[i]:
            for j in range(i + 1, len(toks) + 1):
                if " ".join(toks[i:j]) in units:
                    ok[j] = True
    return bool(toks) and ok[len(toks)]


def find_orphans(lines: list[str], head: int, units: set[str], cap: int) -> int | None:
    """First index of the run of non-blank lines directly above the heading that are each a
    concatenation of printed snapshot-table cells; None if there is none or the run is longer
    than the number of table cells (then it is not a leftover of this table)."""
    first, count, j = None, 0, head - 1
    while j >= 0:
        ln = lines[j]
        if not ln.strip():
            j -= 1
            continue
        if ln.startswith(("#", "|")) or not is_cell_sequence(ln, units):
            break
        first, count, j = j, count + 1, j - 1
    return first if first is not None and count <= cap else None


def uses_ascii_dash(text: str) -> bool:
    ranges = re.findall(r"\$?\d{3}\s?([–-])\s?\$?\d{3}", text)
    return "-" in ranges and "–" not in ranges


# ---------------------------------------------------------------- per-document fix
def fix_document(text: str, doc) -> tuple[str, list[dict], list[dict]]:
    lines = text.split(LF)
    changes: list[dict] = []
    unresolved: list[dict] = []
    replace: dict[int, list[str]] = {}      # original start index -> replacement lines
    dead: set[int] = set()                  # original indices removed
    region = find_region(lines)
    if region is not None:
        s, e, swallowed, headless = region
        try:
            snap = extract_snapshot(page_spans(snapshot_page(doc)))
            if swallowed and not snap["notes"]:
                raise SnapshotError("notes swallowed into the broken region but the PDF yields no bullet notes")
            if not headless:
                first = find_orphans(lines, s - 1, snap["units"], len(snap["cells"]))
                if first is not None:
                    dead.update(range(first, s - 1))
                    changes.append({"line": first + 1, "class": "snapshot_orphan", "old": lines[first:s - 1],
                                    "new": [], "pdf_evidence": "each line is a concatenation of cells printed in the PDF "
                                    "snapshot table; fragments of it left above the heading"})
            if headless or not region_is_good(lines[s:e], snap):
                new, info = build_region(snap, swallowed, lines[s:e], uses_ascii_dash(text))
                if headless:
                    new = ["## " + snap["title"]] + new
                if new != lines[s:e]:
                    replace[s] = new
                    dead.update(range(s, e))
                    changes.append({"line": s + 1, "class": "snapshot", "old": lines[s:e], "new": new,
                                    "pdf_evidence": {"cells": snap["cells"],
                                                     "ignored_note_spans": snap["ignored"],
                                                     "notes_from_pdf": swallowed, **info}})
        except SnapshotError as exc:
            if not region_is_clean_table(lines[s:e]):
                unresolved.append({"line": s + 1, "class": "snapshot", "reason": str(exc)})
    fur = pdf_furniture(doc)
    for i, ln in enumerate(lines):
        if i in dead:
            continue
        m = furniture_match(ln, fur)
        if m:
            dead.add(i)
            changes.append({"line": i + 1, "class": "footer", "old": ln, "new": None,
                            "pdf_evidence": f"PDF furniture '{m['text']}' at y={m['yc']} on {m['pages']} of {len(doc)} pages"})
            # a footer between two blank lines leaves one blank line, not two
            if i > 0 and not lines[i - 1].strip() and (i - 1) not in dead \
                    and i + 1 < len(lines) and not lines[i + 1].strip() and (i + 1) not in dead:
                dead.add(i + 1)
    out: list[str] = []
    for i, ln in enumerate(lines):
        if i in replace:
            out.extend(replace[i])
        elif i not in dead:
            out.append(ln)
    for i, ln in enumerate(lines):
        if i not in dead and "star-asia.com.sg" in ln.lower():
            unresolved.append({"line": i + 1, "class": "footer", "reason": "URL line not matched to PDF furniture",
                               "text": ln[:120]})
    changes.sort(key=lambda c: c["line"])
    return LF.join(out), changes, unresolved


# ---------------------------------------------------------------- driver
def resolve_pdf(md_text: str) -> Path | None:
    m = re.search(r"^source_file:\s*\"?([^\"\n]+)\"?", md_text, flags=re.M)
    if not m:
        return None
    rel = Path(m.group(1).strip())
    for root in (REPO_ROOT, MAIN_CHECKOUT):
        if (root / rel).exists():
            return root / rel
    return None


def change_lines(c: dict) -> int:
    return len(c["old"]) if isinstance(c["old"], list) else 1


def run(years: list[str] | None, limit: int | None, detect_only: bool, out_root: Path) -> dict:
    import pymupdf
    summary = {"files": 0, "files_changed": 0, "lines_changed": 0, "no_pdf": [], "by_year_class": {},
               "lines_by_year_class": {}, "unresolved": [], "page_marker_lines": {}, "per_file_changes": {}}
    byyc: dict = defaultdict(Counter)
    lines_yc: dict = defaultdict(Counter)
    markers: Counter = Counter()
    paths = sorted((REPO_ROOT / MD_ROOT_REL).glob("*/*.md"))
    if years:
        paths = [p for p in paths if p.parent.name in years]
    if limit:
        paths = paths[:limit]
    for p in paths:
        raw = p.read_bytes().decode("utf-8")
        eol = CRLF if CRLF in raw else LF
        txt = raw.replace(CRLF, LF)
        yr = p.parent.name
        summary["files"] += 1
        if txt.replace(LF, eol) != raw:
            summary["no_pdf"].append(p.name + " (mixed line endings, skipped)")
            continue
        markers[yr] += sum(1 for ln in txt.split(LF) if re.match(r"^## Page \d+\s*$", ln))
        pdf = resolve_pdf(txt)
        if pdf is None:
            summary["no_pdf"].append(p.name)
            continue
        doc = pymupdf.open(pdf)
        new, ch, un = fix_document(txt, doc)
        for c in ch:
            byyc[yr][c["class"]] += 1
            lines_yc[yr][c["class"]] += change_lines(c)
        for u in un:
            summary["unresolved"].append({"file": p.name, "year": yr, **u})
        if ch:
            nlines = sum(change_lines(c) for c in ch)
            summary["files_changed"] += 1
            summary["lines_changed"] += nlines
            summary["per_file_changes"][p.name] = {"year": yr, "changes": len(ch), "lines": nlines}
            if not detect_only:
                d = out_root / yr
                d.mkdir(parents=True, exist_ok=True)
                (d / p.name).write_text(new.replace(LF, eol), encoding="utf-8", newline="")
                (d / (p.stem + ".changelog.json")).write_text(
                    json.dumps({"md": str(MD_ROOT_REL / yr / p.name), "pdf": pdf.name,
                                "source_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                "changes": ch, "unresolved": un}, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    summary["by_year_class"] = {y: dict(c) for y, c in byyc.items()}
    summary["lines_by_year_class"] = {y: dict(c) for y, c in lines_yc.items()}
    summary["page_marker_lines"] = dict(markers)
    return summary


def apply_staged(staging: Path, md_root: Path, do_apply: bool) -> dict:
    """Copy staged MDs over the real MDs, only for files that have a changelog and whose
    source is byte-identical to what the fixer read. Dry-run unless do_apply."""
    res = {"applied": [], "refused": [], "dry_run": not do_apply}
    for log in sorted(staging.glob("*/*.changelog.json")):
        meta = json.loads(log.read_text(encoding="utf-8"))
        staged = log.with_name(log.name[: -len(".changelog.json")] + ".md")
        target = REPO_ROOT / meta["md"]
        if not meta.get("changes") or not staged.exists() or not target.exists():
            res["refused"].append({"file": log.name, "reason": "no changes / missing staged or target"})
            continue
        if hashlib.sha256(target.read_bytes()).hexdigest() != meta.get("source_sha256"):
            res["refused"].append({"file": log.name, "reason": "target changed since staging"})
            continue
        if do_apply:
            target.write_bytes(staged.read_bytes())
        res["applied"].append(str(target.relative_to(REPO_ROOT)))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect-only", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--years")
    ap.add_argument("--promote", action="store_true", help="list/apply staged files, do not re-run the fixer")
    ap.add_argument("--apply", action="store_true",
                    help="copy staged files into data/extracted/md/star_asia (default is a dry-run list)")
    a = ap.parse_args()
    if a.apply and not a.promote:
        ap.error("--apply requires --promote")
    if a.promote:
        r = apply_staged(REPO_ROOT / STAGING_REL, REPO_ROOT / MD_ROOT_REL, a.apply)
        print(json.dumps({"dry_run": r["dry_run"], "applied": len(r["applied"]), "refused": r["refused"]}, indent=1))
        return
    s = run(a.years.split(",") if a.years else None, a.limit, a.detect_only, REPO_ROOT / STAGING_REL)
    out = REPO_ROOT / STAGING_REL
    out.mkdir(parents=True, exist_ok=True)
    (out / "_summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in s.items() if k not in ("per_file_changes", "unresolved")},
                     indent=1, ensure_ascii=False))
    print("unresolved:", len(s["unresolved"]))


if __name__ == "__main__":
    main()
