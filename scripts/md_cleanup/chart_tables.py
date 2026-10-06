"""Remove chart-estimated ("guessed") time-series tables from extracted markdown.

An LLM parser sometimes turns a chart image into a table by eyeballing values.
Those numbers are not printed anywhere in the source document, so they must not
feed the knowledge graph. This tool classifies every markdown table (GFM pipe
tables and raw HTML <table> blocks) deterministically:

* Numeric cells of the table are compared with the numeric tokens of the source
  text layer (PDF text via PyMuPDF, or visible HTML text for HTML sources).
* printed_ratio < 0.6 with >= 4 numeric cells  -> GUESSED (replaced by a figure note)
* No usable text layer / missing source        -> GUESSED only when the nearest
  heading matches a known chart title, else KEEP (unverifiable)
* Everything else                              -> KEEP

Source markdown is never modified: cleaned copies go to the staging directory.

Usage:
    python -m scripts.md_cleanup.chart_tables [--workers N] [--limit N] [--scopes a,b]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_lib
import os
import pickle
import random
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CHECKOUT = Path(r"C:\Users\Dell\Github\Shipping")
MD_ROOT_REL = Path("data/extracted/md")
STAGING_REL = Path(".reparse_staging/chart_cleanup")

SCOPES = [
    "banchero_costa",
    "hellenic/iron_ore_pdf",
    "hellenic/demolition/athenian",
    "hellenic/demolition/gms",
    "drewry/ais",
    "seabrokers",
    "advanced_shipping",
    "ssy",
    "affinity",
    "lion",
    "fearnleys-md",
    "poten",
    "gibson",
]

CHART_TITLE_PATTERNS = [
    r"FORWARD CURVE",
    r"1-YR TC \(USD/DAY\)",
    r"^BCI TC",
    r"^BPI",
    r"^BSI TC",
    r"^BHSI",
    r"1 YR TC PERIOD",
    r"^TD\d+",
    r"^TC\d+",
    r"MR (PACIFIC|ATLANTIC) BASKET",
    r"JPY/USD",
    r"FREIGHTOS BALTIC CONTAINER INDEX",
    r"\(1-Year Trend\)",
    r"1-Year Forward WS Rates",
    r"Newbuilding Prices \(m\$\)",
    r"Total China Iron Ore Import Volumes",
    r"Yearly Demolition Volume",
    r"Dry Bulk Freight Rates Historical Line Data",
    r"Historical Iron Ore Index Comparisons",
]
CHART_TITLE_RE = [re.compile(p, re.IGNORECASE) for p in CHART_TITLE_PATTERNS]

PRINTED_RATIO_THRESHOLD = 0.6
MIN_NUMERIC_CELLS = 4
MIN_TEXT_WORDS = 50
MIN_STOPWORD_RATIO = 0.04
FIGURE_NOTE = "> Figure: {title} \u2014 chart values not transcribed (not printed in the source; visual estimates removed)."

_STOPWORDS = frozenset(
    "the of and to in a is for on with as by at from that this are be was it an or".split()
)
_NUM_CELL_RE = re.compile(r"^[\(\-\u2212+]?\d[\d.,]*\)?(?:\s?(?:m|k|bn|mn|mt|mln))?$", re.IGNORECASE)
_NUM_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*")
_SPACED_THOUSANDS_RE = re.compile(r"\d{1,3}(?: \d{3})+(?:[.,]\d+)?")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_VECTOR_RE = re.compile(r"vector", re.IGNORECASE)
_SEP_CELL_RE = re.compile(r"^:?-{1,}:?$")


# --------------------------------------------------------------------------- numbers

def num_candidates(token: str) -> frozenset:
    """Return the possible absolute float values of a numeric token.

    Handles "1,234.5", "1.234,5", "33,0" (== 33.0) and the ambiguous "1.234" /
    "1,234" (returns both 1234 and 1.234).
    """
    t = token.strip()
    if not t or not t[0].isdigit() or not t[-1].isdigit():
        return frozenset()
    has_dot, has_com = "." in t, "," in t
    try:
        if has_dot and has_com:
            dec = "." if t.rfind(".") > t.rfind(",") else ","
            thou = "," if dec == "." else "."
            return frozenset({round(float(t.replace(thou, "").replace(dec, ".")), 6)})
        if has_dot or has_com:
            sep = "." if has_dot else ","
            parts = t.split(sep)
            if len(parts) > 2:
                if all(len(p) == 3 for p in parts[1:]):
                    return frozenset({round(float("".join(parts)), 6)})
                return frozenset()
            whole, frac = parts
            as_dec = round(float(whole + "." + frac), 6)
            if len(frac) == 3 and 1 <= len(whole) <= 3:
                return frozenset({as_dec, round(float(whole + frac), 6)})
            return frozenset({as_dec})
        return frozenset({round(float(t), 6)})
    except ValueError:
        return frozenset()


def _is_year(raw: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", raw)) and 1990 <= int(raw) <= 2035


def cell_numeric(cell: str):
    """Return candidate values for a numeric table cell, or None if not numeric/ignored."""
    c = html_lib.unescape(cell).replace("\xa0", " ")
    c = re.sub(r"[*_`]", "", c).strip()
    c = re.sub(r"^(?:US)?[$\u00a3\u20ac]\s*", "", c)
    c = re.sub(r"\s*%$", "", c).strip()
    if not _NUM_CELL_RE.match(c):
        return None
    core = re.sub(r"(?:\s?(?:m|k|bn|mn|mt|mln))$", "", c, flags=re.IGNORECASE)
    core = core.strip("()-\u2212+ ")
    if _is_year(core):
        return None
    cands = num_candidates(core)
    return cands or None


def text_numeric_keys(text: str) -> set:
    keys: set = set()
    for m in _NUM_TOKEN_RE.finditer(text):
        keys.update(num_candidates(m.group(0)))
    for m in _SPACED_THOUSANDS_RE.finditer(text):
        keys.update(num_candidates(m.group(0).replace(" ", "")))
    return keys


# --------------------------------------------------------------------------- source text

def _stem_index(main_checkout: Path) -> dict:
    idx: dict = {}
    corpus = main_checkout / "corpus"
    for dp, _dn, fns in os.walk(corpus):
        for fn in fns:
            low = fn.lower()
            if low.endswith((".pdf", ".html", ".htm")):
                idx.setdefault(Path(fn).stem, Path(dp) / fn)
    return idx


_STEM_INDEX: dict | None = None


def _get_stem_index(main_checkout: Path) -> dict:
    global _STEM_INDEX
    if _STEM_INDEX is None:
        _STEM_INDEX = _stem_index(main_checkout)
    return _STEM_INDEX


def resolve_source(md_path: Path, frontmatter_source: str | None, roots: list, stem_index=None):
    """Resolve the source PDF/HTML. roots: checkouts to resolve repo-relative paths against."""
    if frontmatter_source:
        for r in roots:
            p = Path(r) / frontmatter_source
            if p.exists():
                return p
    stem = md_path.stem
    if stem_index is not None:
        hit = stem_index.get(stem)
        if hit is not None and Path(hit).exists():
            return Path(hit)
    return None


def frontmatter_source_file(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    head = text[: end if end > 0 else 3000]
    m = re.search(r'^source_file:\s*"?(.+?)"?\s*$', head, re.MULTILINE)
    return m.group(1).strip() if m else None


def _text_usable(text: str) -> bool:
    words = text.split()
    if len(words) < MIN_TEXT_WORDS:
        return False
    alpha = re.findall(r"[A-Za-z]+", text.lower())
    if not alpha:
        return False
    return sum(1 for w in alpha if w in _STOPWORDS) / len(alpha) >= MIN_STOPWORD_RATIO


def load_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pymupdf

        with pymupdf.open(str(path)) as doc:
            return "\n".join(page.get_text() for page in doc)
    raw = path.read_text(encoding="utf-8", errors="replace")
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(" ")


def _cached_text_info(src: Path, cache_dir: Path) -> dict:
    st = src.stat()
    key = hashlib.sha1(f"{src}|{st.st_size}|{int(st.st_mtime)}|{MIN_STOPWORD_RATIO}".encode()).hexdigest()
    cp = cache_dir / f"{key}.pkl"
    if cp.exists():
        try:
            return pickle.loads(cp.read_bytes())
        except Exception:
            pass
    info = build_text_info(load_source_text(src))
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_bytes(pickle.dumps(info))
    os.replace(tmp, cp)
    return info


def build_text_info(text: str | None) -> dict | None:
    """text None -> no source. Returns {'usable': bool, 'keys': set}."""
    if text is None:
        return None
    usable = _text_usable(text)
    return {"usable": usable, "keys": text_numeric_keys(text) if usable else set()}


# --------------------------------------------------------------------------- tables

def _parse_pipe_rows(lines: list) -> list:
    rows = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("|"):
            s = s[1:]
        if s.endswith("|"):
            s = s[:-1]
        cells = [c.strip() for c in s.split("|")]
        if cells and all(_SEP_CELL_RE.match(c) for c in cells if c) and any(cells):
            continue
        rows.append(cells)
    return rows


def _parse_html_rows(block: str) -> list:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(block, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    return rows


def find_tables(text: str) -> list:
    """Locate GFM pipe tables and HTML tables.

    Returns dicts: start, end (line indexes, end exclusive), kind, rows, heading,
    heading_line, prev_line. `lines` is returned alongside for rewriting.
    """
    lines = text.split("\n")
    i = 0
    if lines and lines[0].strip() == "---":
        j = 1
        while j < len(lines) and lines[j].strip() != "---":
            j += 1
        i = j + 1
    tables = []
    heading = None
    heading_line = None
    prev_line = ""
    stack: dict = {}
    n = len(lines)
    while i < n:
        ln = lines[i]
        stripped = ln.strip()
        hm = _HEADING_RE.match(ln)
        if hm:
            heading, heading_line, prev_line = hm.group(1), i, ""
            level = len(ln.strip()) - len(ln.strip().lstrip("#"))
            stack = {k: v for k, v in stack.items() if k < level}
            stack[level] = heading
            i += 1
            continue
        if re.match(r"<table\b", stripped, re.IGNORECASE):
            j = i
            while j < n and not re.search(r"</table>", lines[j], re.IGNORECASE):
                j += 1
            end = min(j + 1, n)
            block = "\n".join(lines[i:end])
            tables.append({"start": i, "end": end, "kind": "html", "rows": _parse_html_rows(block),
                           "heading": heading, "heading_line": heading_line, "prev_line": prev_line,
                           "sections": list(stack.values())})
            i = end
            continue
        if stripped.startswith("|"):
            j = i
            while j < n and lines[j].strip().startswith("|"):
                j += 1
            if j - i >= 2:
                tables.append({"start": i, "end": j, "kind": "pipe", "rows": _parse_pipe_rows(lines[i:j]),
                               "heading": heading, "heading_line": heading_line, "prev_line": prev_line,
                           "sections": list(stack.values())})
                i = j
                continue
        if stripped:
            prev_line = stripped
        i += 1
    return tables


def title_matches(*candidates: str | None) -> bool:
    for c in candidates:
        if not c:
            continue
        c = re.sub(r"[*_`]", "", c).strip()
        if any(rx.search(c) for rx in CHART_TITLE_RE):
            return True
    return False


def numeric_cells(rows: list) -> list:
    out = []
    for row in rows:
        for cell in row:
            cands = cell_numeric(cell)
            if cands:
                out.append(cands)
    return out


def printed_ratio(cells: list, keys: set) -> float:
    if not cells:
        return 0.0
    return sum(1 for c in cells if c & keys) / len(cells)


def _is_arith(vals: list) -> bool:
    if len(vals) < 4:
        return False
    step = vals[1] - vals[0]
    if abs(step) < 1e-9:
        return False
    return all(abs((vals[k + 1] - vals[k]) - step) < 1e-6 for k in range(len(vals) - 1))


def _first_value(cell: str):
    c = cell_numeric(cell)
    if not c:
        return None
    return min(c) if len(c) == 1 else None


def structural_flags(rows: list) -> list:
    flags = []
    if not rows:
        return flags
    for row in rows:
        vals = [_first_value(c) for c in row]
        run = [v for v in vals if v is not None]
        if len(run) == len([c for c in row if c.strip()]) and _is_arith(run):
            flags.append("arith_progression_row")
            break
    width = max(len(r) for r in rows)
    for col in range(width):
        run = []
        for row in rows[1:]:
            if col < len(row) and row[col].strip():
                v = _first_value(row[col])
                if v is None:
                    if _is_arith(run):
                        break
                    run = []
                    continue
                run.append(v)
        if _is_arith(run):
            flags.append("arith_progression_col")
            break
    header = [c.strip().lower() for c in rows[0]]
    head_set = {c for c in header if c}
    for row in rows[1:]:
        low = [c.strip().lower() for c in row]
        nonempty = {c for c in low if c}
        if not nonempty or any(cell_numeric(c) for c in row):
            continue
        if nonempty <= head_set or (header and header[0] and low and low[0] == header[0]):
            flags.append("duplicate_header_row")
            break
    return flags


_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
_DATE_CELL_RES = [
    re.compile(rf"^\d{{1,2}}[-/ .]{_MONTHS}[-/ .]?\d{{0,4}}$", re.IGNORECASE),
    re.compile(rf"^{_MONTHS}[-/ .']?\s?\d{{2,4}}$", re.IGNORECASE),
    re.compile(r"^\d{4}-\d{2}(?:-\d{2})?$"),
    re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$"),
    re.compile(r"^Q[1-4][-/ ]?\d{2,4}$", re.IGNORECASE),
    re.compile(r"^(?:19|20)\d{2}$"),
]


_SERIES_HEADERS = frozenset({"date", "time", "week", "month", "period", "year", "quarter", "day"})


def _is_date_cell(cell: str) -> bool:
    c = re.sub(r"[*_`]", "", cell).strip()
    return bool(c) and any(rx.match(c) for rx in _DATE_CELL_RES)


def is_time_series(rows: list) -> bool:
    """True when the table is a chart-style series: header says Date/Week/..., or the first column is mostly dates."""
    if len(rows) < 3:
        return False
    head0 = re.sub(r"[*_`]", "", rows[0][0]).strip().lower() if rows[0] else ""
    if head0 in _SERIES_HEADERS:
        return True
    first = [r[0] for r in rows[1:] if r and r[0].strip()]
    if len(first) < 2:
        return False
    return sum(1 for c in first if _is_date_cell(c)) / len(first) >= 0.6


def classify_table(table: dict, info: dict | None, guard_published: bool = True) -> dict:
    cells = numeric_cells(table["rows"])
    n = len(cells)
    title = table["heading"]
    tmatch = title_matches(table["heading"], table["prev_line"] if len(table["prev_line"]) <= 100 else None)
    if any(_VECTOR_RE.search(h or "") for h in [table["heading"], *table.get("sections", [])]):
        return {"numeric_cells": n, "title_match": tmatch, "printed_ratio": "", "verifiable": False,
                "reason": "vector_chart_engine", "time_series": False, "cls": "KEEP_VECTOR", "flags": [],
                "title": title or "chart"}
    ts = is_time_series(table["rows"])
    rec = {"numeric_cells": n, "title_match": tmatch, "printed_ratio": "", "verifiable": False,
           "reason": "", "time_series": ts}
    if n < MIN_NUMERIC_CELLS:
        rec["cls"], rec["reason"] = "KEEP_SMALL", "few_numeric_cells"
    elif info is not None and info["usable"]:
        rec["verifiable"] = True
        ratio = printed_ratio(cells, info["keys"])
        rec["printed_ratio"] = round(ratio, 3)
        if ratio < PRINTED_RATIO_THRESHOLD:
            if guard_published and not ts and not tmatch:
                rec["cls"], rec["reason"] = "KEEP_UNVERIFIABLE", "low_ratio_not_time_series"
            else:
                rec["cls"], rec["reason"] = "GUESSED", "low_printed_ratio"
        else:
            rec["cls"] = "KEEP_VERIFIED"
    else:
        reason = "no_source" if info is None else "no_text_layer"
        rec["reason"] = reason
        if tmatch:
            rec["cls"] = "GUESSED"
            rec["reason"] = reason + "+chart_title"
        else:
            rec["cls"] = "KEEP_UNVERIFIABLE"
    rec["flags"] = structural_flags(table["rows"]) if rec["cls"] != "GUESSED" else []
    rec["title"] = title or table["prev_line"] or "chart"
    return rec


def clean_markdown(text: str, info_loader, guard_published: bool = True) -> tuple:
    """Return (new_text, records). info_loader() is called lazily once to get the text info."""
    tables = find_tables(text)
    lines = text.split("\n")
    info_cache: dict = {}
    records = []
    replacements = []
    for t in tables:
        cells_n = len(numeric_cells(t["rows"]))
        if cells_n >= MIN_NUMERIC_CELLS and "info" not in info_cache:
            info_cache["info"] = info_loader()
        rec = classify_table(t, info_cache.get("info"), guard_published)
        rec["kind"] = t["kind"]
        rec["heading"] = t["heading"] or ""
        rec["first_rows"] = " // ".join(" | ".join(r) for r in t["rows"][:3])
        records.append(rec)
        if rec["cls"] == "GUESSED":
            title = re.sub(r"[*_`]", "", rec["title"]).strip()
            replacements.append((t["start"], t["end"], FIGURE_NOTE.format(title=title)))
    for start, end, note in reversed(replacements):
        lines[start:end] = [note]
    return "\n".join(lines), records


# --------------------------------------------------------------------------- driver

def process_file(args: tuple) -> dict:
    md_path_s, rel_s, scope, roots_s, out_dir_s, guard_published, apply = args
    md_path = Path(md_path_s)
    raw = md_path.read_bytes().decode("utf-8", errors="surrogateescape")
    text = raw.replace("\r\n", "\n")
    crlf = "\r\n" in raw
    state: dict = {}

    def loader():
        if "info" not in state:
            src = resolve_source(md_path, frontmatter_source_file(text), [Path(r) for r in roots_s],
                                 _get_stem_index(Path(roots_s[0])))
            state["src"] = src
            try:
                state["info"] = _cached_text_info(src, REPO_ROOT / STAGING_REL / ".cache") if src else None
            except Exception as exc:  # unreadable PDF/HTML -> treated as no source
                state["info"] = None
                state["error"] = repr(exc)
        return state["info"]

    new_text, records = clean_markdown(text, loader, guard_published)
    changed = new_text != text
    if changed:
        out = md_path if apply else Path(out_dir_s) / rel_s
        out.parent.mkdir(parents=True, exist_ok=True)
        data = new_text.replace("\n", "\r\n") if crlf else new_text
        out.write_bytes(data.encode("utf-8", errors="surrogateescape"))
    return {"file": rel_s, "scope": scope, "records": records, "changed": changed,
            "source": str(state.get("src") or ""), "error": state.get("error", "")}


def collect_files(repo_root: Path, scopes: list) -> list:
    files = []
    md_root = repo_root / MD_ROOT_REL
    for scope in scopes:
        for p in sorted((md_root / scope).rglob("*.md")):
            files.append((p, scope))
    return files


DREWRY_CHECKS = ["Ballast speed vs bunker price", "Laden speed vs bunker price",
                 "Utilisation vs Baltic rates", "Tonnage at anchor"]


def write_reports(results: list, out_dir: Path, seed: int = 7) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in results:
        for k, rec in enumerate(r["records"]):
            rows.append({"publisher": r["scope"], "file": r["file"], "table_index": k,
                         "heading": rec["heading"], "kind": rec["kind"], "class": rec["cls"],
                         "reason": rec["reason"], "numeric_cells": rec["numeric_cells"],
                         "printed_ratio": rec["printed_ratio"], "title_match": rec["title_match"],
                         "time_series": rec["time_series"],
                         "flags": ";".join(rec["flags"]), "source": r["source"],
                         "first_rows": rec["first_rows"][:300]})
    fields = ["publisher", "file", "table_index", "heading", "kind", "class", "reason", "numeric_cells",
              "printed_ratio", "title_match", "time_series", "flags", "source", "first_rows"]
    with open(out_dir / "report.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    per = defaultdict(Counter)
    files_per = Counter()
    changed_per = Counter()
    for r in results:
        files_per[r["scope"]] += 1
        changed_per[r["scope"]] += int(r["changed"])
    for row in rows:
        per[row["publisher"]]["tables"] += 1
        per[row["publisher"]][row["class"]] += 1
    removed = Counter()
    kept_unv = Counter()
    for row in rows:
        key = re.sub(r"\s+", " ", row["heading"]).strip().lower()
        if row["class"] == "GUESSED":
            removed[key] += 1
        elif row["class"] == "KEEP_UNVERIFIABLE":
            kept_unv[key] += 1
    rng = random.Random(seed)
    guessed = [r for r in rows if r["class"] == "GUESSED"]
    chartlike_kept = [r for r in rows if r["class"] == "KEEP_VERIFIED" and r["title_match"]]
    flagged = [r for r in rows if r["flags"] and r["class"].startswith("KEEP")]
    errors = [(r["file"], r["error"]) for r in results if r["error"]]
    no_src = Counter(r["scope"] for r in results if not r["source"] and r["records"])

    out = ["# Chart-table cleanup summary", "",
           "| Publisher | Files | Files changed | Tables | KEEP verified | KEEP unverifiable | KEEP small (<4 numeric) | KEEP vector-engine | GUESSED removed |",
           "|---|---|---|---|---|---|---|---|---|"]
    tot = Counter()
    for scope in SCOPES:
        if scope not in files_per:
            continue
        c = per[scope]
        out.append(f"| {scope} | {files_per[scope]} | {changed_per[scope]} | {c['tables']} | "
                   f"{c['KEEP_VERIFIED']} | {c['KEEP_UNVERIFIABLE']} | {c['KEEP_SMALL']} | {c['KEEP_VECTOR']} | {c['GUESSED']} |")
        tot.update({"f": files_per[scope], "ch": changed_per[scope], "t": c["tables"],
                    "kv": c["KEEP_VERIFIED"], "ku": c["KEEP_UNVERIFIABLE"], "ks": c["KEEP_SMALL"], "kvec": c["KEEP_VECTOR"],
                    "g": c["GUESSED"]})
    out.append(f"| **TOTAL** | {tot['f']} | {tot['ch']} | {tot['t']} | {tot['kv']} | {tot['ku']} | {tot['ks']} | {tot['kvec']} | {tot['g']} |")
    out += ["", "Files with tables but no resolvable source (per publisher): "
            + (", ".join(f"{k}={v}" for k, v in sorted(no_src.items())) or "none"), ""]
    if errors:
        out += [f"Source read errors: {len(errors)} (first 5: {errors[:5]})", ""]
    out += ["## Top 30 removed titles", ""]
    out += [f"- {n} x {t or '(no heading)'}" for t, n in removed.most_common(30)]
    out += ["", "## Top 30 kept-unverifiable titles", ""]
    out += [f"- {n} x {t or '(no heading)'}" for t, n in kept_unv.most_common(30)]

    def fmt(r):
        return (f"- `{r['file']}` | heading: {r['heading']!r} | ratio: {r['printed_ratio']} | "
                f"class: {r['class']} ({r['reason']}) | rows: {r['first_rows'][:200]}")

    out += ["", "## 10 random removed examples", ""]
    out += [fmt(r) for r in rng.sample(guessed, min(10, len(guessed)))]
    out += ["", "## 10 random kept chart-like examples (title matched, printed_ratio >= 0.6)", ""]
    out += [fmt(r) for r in rng.sample(chartlike_kept, min(10, len(chartlike_kept)))]
    out += ["", "## GUESSED tables by shape (time_series = Date/Week/Month-led or date-valued first column)", "",
            "| Publisher | GUESSED time-series | GUESSED other (published-table suspects) |", "|---|---|---|"]
    for scope in SCOPES:
        g = [r for r in guessed if r["publisher"] == scope]
        if g:
            ts_n = sum(1 for r in g if r["time_series"])
            out.append(f"| {scope} | {ts_n} | {len(g) - ts_n} |")
    out += ["", f"## Kept tables with structural flags (not changed): {len(flagged)}", ""]
    out += [f"- {r['flags']} | `{r['file']}` | {r['heading']!r}" for r in flagged[:100]]
    if len(flagged) > 100:
        out.append(f"- ... {len(flagged) - 100} more in report.csv (flags column)")

    out += ["", "## Drewry AIS spot checks", ""]
    for name in DREWRY_CHECKS:
        sel = [r for r in rows if r["publisher"] == "drewry/ais" and name.lower() in r["heading"].lower()]
        if not sel:
            out.append(f"- {name}: no tables with this heading")
            continue
        cls = Counter(r["class"] for r in sel)
        ratios = [r["printed_ratio"] for r in sel if r["printed_ratio"] != ""]
        rs = (f"printed_ratio min/mean/max = {min(ratios):.2f}/{sum(ratios) / len(ratios):.2f}/{max(ratios):.2f}"
              if ratios else "no ratios (no text layer)")
        out.append(f"- {name}: {len(sel)} tables, {dict(cls)}; {rs}")
    (out_dir / "summary.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def write_applied_report(results: list, out_dir: Path) -> None:
    with open(out_dir / "applied_report.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "publisher", "heading", "kind", "numeric_cells", "printed_ratio", "reason"])
        for r in results:
            for rec in r["records"]:
                if rec["cls"] == "GUESSED":
                    w.writerow([r["file"], r["scope"], rec["heading"], rec["kind"], rec["numeric_cells"],
                                rec["printed_ratio"], rec["reason"]])


def main(argv=None) -> int:
    global MAIN_CHECKOUT
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument("--main-checkout", default=str(MAIN_CHECKOUT))
    ap.add_argument("--scopes", default=",".join(SCOPES))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--no-guard-published", dest="guard_published", action="store_false",
                    help="disable the default guard (literal rule). Guard: on the text-layer path, low-ratio "
                         "tables that are not time series and have no chart title are kept")
    ap.add_argument("--apply", action="store_true",
                    help="overwrite changed MDs in place under data/extracted/md and write applied_report.csv")
    ap.add_argument("--out-subdir", default="", help="optional subfolder under the staging dir")
    ap.add_argument("--limit", type=int, default=0, help="process only first N files (debug)")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root)
    MAIN_CHECKOUT = Path(args.main_checkout)
    out_dir = repo_root / STAGING_REL / args.out_subdir if args.out_subdir else repo_root / STAGING_REL
    scopes = [s for s in args.scopes.split(",") if s]
    files = collect_files(repo_root, scopes)
    if args.limit:
        files = files[: args.limit]
    roots = [str(MAIN_CHECKOUT), str(repo_root)]
    jobs = [(str(p), (MD_ROOT_REL / p.relative_to(repo_root / MD_ROOT_REL)).as_posix(), scope, roots,
             str(out_dir), args.guard_published, args.apply) for p, scope in files]
    print(f"{len(jobs)} files, {args.workers} workers", file=sys.stderr)
    results = []
    if args.workers <= 1:
        for k, j in enumerate(jobs, 1):
            results.append(process_file(j))
            if k % 200 == 0:
                print(f"{k}/{len(jobs)}", file=sys.stderr)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for k, res in enumerate(ex.map(process_file, jobs, chunksize=4), 1):
                results.append(res)
                if k % 200 == 0:
                    print(f"{k}/{len(jobs)}", file=sys.stderr)
    write_reports(results, out_dir)
    if args.apply:
        write_applied_report(results, out_dir)
    print(f"report: {out_dir / 'summary.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
