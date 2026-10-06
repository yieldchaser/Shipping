"""Output validation: sections, tables, chart-axis dumps, garbage glyphs, text recall, table numeric recall."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable

import pymupdf

NUMERIC_LINE_RE = re.compile(r"^[\s\d.,%$()+\-−–/:]+$")
GARBAGE_RE = re.compile(r"�|\(cid:\d+\)")
WORD4_RE = re.compile(r"[A-Za-z]{4,}")
GENERIC_BOILERPLATE = [
    r"(?i)\bdisclaimer\b", r"(?i)the material and the information", r"(?i)\bkifissias\b",
    r"(?i)@[a-z0-9.-]+\.[a-z]{2,}", r"(?i)\bwww\.[a-z0-9.-]+", r"(?i)\+\(?\d{2}\)?[\d\s]{8,}",
]
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)


def split_frontmatter(md: str) -> str:
    return FRONTMATTER_RE.sub("", md, count=1)


# ----------------------------------------------------------------------------- markdown structure
def _cells(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", inner)]


def find_tables(md: str) -> list[list[str]]:
    """Each table is the list of its consecutive pipe-lines."""
    tables, cur = [], []
    for line in md.split("\n"):
        if line.lstrip().startswith("|"):
            cur.append(line)
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


def table_stats(tables: list[list[str]]) -> dict[str, Any]:
    header_only, ragged = 0, 0
    for t in tables:
        sep_idx = next((i for i, l in enumerate(t) if re.fullmatch(r"\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*", l)), None)
        body = [l for i, l in enumerate(t) if sep_idx is None or i > sep_idx]
        if sep_idx is None:
            header = t[0]
            body = t[1:]
        else:
            header = t[0]
        if not [b for b in body if any(c for c in _cells(b))]:
            header_only += 1
        width = len(_cells(header))
        if any(len(_cells(b)) != width for b in body):
            ragged += 1
    return {"tables": len(tables), "header_only_tables": header_only, "ragged_tables": ragged}


def numeric_runs(md: str, min_len: int = 6) -> int:
    runs, cur = 0, 0
    for line in md.split("\n"):
        s = line.strip()
        if s and not s.startswith("|") and NUMERIC_LINE_RE.match(s) and re.search(r"\d", s):
            cur += 1
            continue
        if cur >= min_len:
            runs += 1
        cur = 0
    if cur >= min_len:
        runs += 1
    return runs


def broken_sentences(md: str) -> int:
    """Paragraphs (not tables/headings) that end without terminal punctuation and are directly
    followed by a paragraph starting with a lower-case letter."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", md) if b.strip()]

    def is_para(b: str) -> bool:
        return not b.startswith(("#", "|"))

    count = 0
    for cur, nxt in zip(blocks, blocks[1:]):
        if not (is_para(cur) and is_para(nxt)):
            continue
        end = cur.rstrip("*_ ")
        first = re.sub(r"^[*_\s]+", "", nxt)
        if end and end[-1] not in ".!?:)\"'’”" and first and first[0].islower():
            count += 1
    return count


def sections_present(md: str, sections: Iterable[str]) -> dict[str, bool]:
    lines = [re.sub(r"^[#*_\s]+|[*_\s]+$", "", l).lower().replace("–", "-") for l in md.split("\n")]
    out = {}
    for sec in sections:
        keys = [k.lower() for k in sec.split("|")]      # "A|B": either spelling satisfies the section
        out[sec] = any(l.startswith(k) for k in keys for l in lines if l)
    return out


# ----------------------------------------------------------------------------- recall
def _is_boiler(line: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(line) for p in patterns)


def pdf_words(pdf: Path, pages: list[int], boiler: list[str], strip: list[str],
              dropped: list[dict[str, Any]] | None = None) -> list[str]:
    """4+ letter words of the text layer, minus boilerplate lines and profile-dropped regions."""
    pats = [re.compile(p) for p in (*GENERIC_BOILERPLATE, *boiler, *strip)]
    words: list[str] = []
    doc = pymupdf.open(pdf)
    for p in pages:
        boxes = [d["bbox"] for d in (dropped or []) if d["page"] == p]
        lines: dict[tuple[int, int], list[str]] = {}
        for x0, y0, x1, y1, text, b, l, _ in doc[p - 1].get_text("words"):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if any(bx0 <= cx <= bx1 and by0 <= cy <= by1 for bx0, by0, bx1, by1 in boxes):
                continue
            lines.setdefault((b, l), []).append(text)
        for ws in lines.values():
            line = " ".join(ws)
            if line.strip() and not _is_boiler(line, pats):
                words.extend(w.lower() for w in WORD4_RE.findall(line))
    return words


def text_recall(pdf: Path, pages: list[int], md_body: str, boiler: list[str], strip: list[str],
                dropped: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    words = pdf_words(pdf, pages, boiler, strip, dropped)
    have = set(w.lower() for w in WORD4_RE.findall(md_body))
    # tokens split by hyphenation / soft wraps are matched on their parts too
    have |= {part for tok in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)+", md_body) for part in tok.lower().split("-") if len(part) >= 4}
    uniq = sorted(set(words))
    missing = [w for w in uniq if w not in have]
    total = len(words)
    miss_tokens = sum(1 for w in words if w not in have)
    return {
        "text_recall": round(1 - miss_tokens / total, 4) if total else None,
        "recall_words_total": total,
        "recall_words_missing_unique": len(missing),
        "recall_missing_sample": missing[:15],
    }


def _num_tokens(text: str) -> list[str]:
    out = []
    for tok in re.split(r"[\s|]+", text):
        tok = tok.strip("()*,;:“”\"'")
        glued = re.fullmatch(r"((?:19|20)\d{2})([A-Za-z]+)", tok)   # year glued to a yard name: "2021NEW"
        if glued:
            out.append(glued.group(1))
        elif re.search(r"\d", tok):
            out.append(tok.rstrip("-"))
    return out


def table_numeric_recall(regions: list[dict[str, Any]], pdf: Path, tables_text: str) -> dict[str, Any]:
    """Every numeric token inside a table bbox on the PDF must appear in the emitted tables."""
    if not regions:
        return {"table_numeric_recall": None, "table_numeric_tokens": 0, "table_numeric_missing": []}
    doc = pymupdf.open(pdf)
    haystack = tables_text
    total, missing = 0, []
    for reg in regions:
        x0, y0, x1, y1 = reg["bbox"]
        page = doc[reg["page"] - 1]
        for w in page.get_text("words"):
            cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            if x0 - 1 <= cx <= x1 + 1 and y0 - 1 <= cy <= y1 + 1:
                for tok in _num_tokens(w[4]):
                    total += 1
                    if tok not in haystack:
                        missing.append({"page": reg["page"], "table": reg["name"], "token": tok})
    return {
        "table_numeric_recall": round(1 - len(missing) / total, 4) if total else None,
        "table_numeric_tokens": total,
        "table_numeric_missing": missing[:20],
    }


# ----------------------------------------------------------------------------- driver
def resolve_sections(rule: Any, year: int | None) -> dict[str, list[str]]:
    if not rule:
        return {"required": [], "optional": []}
    for r in rule:
        if "until_year" in r and (year is None or year > r["until_year"]):
            continue
        if "from_year" in r and (year is None or year < r["from_year"]):
            continue
        return {"required": r.get("required", []), "optional": r.get("optional", [])}
    return {"required": [], "optional": []}


def validate_output(md: str, pdf: Path, pages: list[int], profile: dict[str, Any], year: int | None,
                    regions: list[dict[str, Any]] | None = None, issue_date: str | None = None,
                    dropped: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    body = split_frontmatter(md)
    secs = resolve_sections(profile.get("expected_sections"), year)
    req = sections_present(body, secs["required"])
    opt = sections_present(body, secs["optional"])
    tables = find_tables(body)
    stats = table_stats(tables)
    tables_text = "\n".join("\n".join(t) for t in tables)
    report: dict[str, Any] = {
        "sections_required": req,
        "sections_missing": [s for s, ok in req.items() if not ok],
        "sections_optional_present": [s for s, ok in opt.items() if ok],
        **stats,
        "numeric_axis_runs": numeric_runs(body),
        "garbage_chars": len(GARBAGE_RE.findall(body)),
        "broken_sentences": broken_sentences(body),
        "issue_date_missing": issue_date is None,
    }
    report.update(text_recall(pdf, pages, body, profile.get("boilerplate_patterns", []),
                              profile.get("strip_line_patterns", []), dropped))
    report.update(table_numeric_recall(regions or [], pdf, tables_text))
    th = profile.get("validation_thresholds", {})
    problems = []
    if report["sections_missing"]:
        problems.append("missing_sections")
    if report["header_only_tables"]:
        problems.append("header_only_tables")
    if report["ragged_tables"]:
        problems.append("ragged_tables")
    if report["numeric_axis_runs"]:
        problems.append("chart_axis_dump")
    if report["garbage_chars"]:
        problems.append("garbage_glyphs")
    if report["broken_sentences"]:
        problems.append("broken_sentences")
    if report["text_recall"] is not None and report["text_recall"] < th.get("min_text_recall", 0.95):
        problems.append("low_text_recall")
    if report["table_numeric_recall"] is not None and \
            report["table_numeric_recall"] < th.get("min_table_numeric_recall", 0.99):
        problems.append("low_table_numeric_recall")
    if issue_date is None:
        problems.append("issue_date_null")
    report["problems"] = problems
    report["passed"] = not [p for p in problems if p != "issue_date_null"]
    return report


def write_validation(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


SUMMARY_FIELDS = ["file", "engine", "tier", "api", "year", "issue_date", "pages_total", "pages_parsed",
                  "credits_used", "tables", "header_only_tables", "ragged_tables", "numeric_axis_runs",
                  "garbage_chars", "broken_sentences", "text_recall", "table_numeric_recall", "sections_missing", "problems", "flags", "tables_detail", "issue_date_conflict", "document_header_date", "source_sha256",
                  "passed", "output"]


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r = dict(r)
            for k in ("sections_missing", "problems", "flags"):
                if isinstance(r.get(k), list):
                    r[k] = ";".join(r[k])
            w.writerow(r)
