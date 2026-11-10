"""P1 sectioning for non-SEC documents: brokers, books, 6-K, 10-Q, 8-K.

Runs AFTER sec_sectioner.py (which owns sec_10k/sec_20f). This module is
INSERT-only for its doc_types; it deletes only the section rows of the
doc_ids it is about to (re)write, and never touches 10-K/20-F rows.

Sectioning is also exposed as `sectionize(doc_id, doc_type, title, text) ->
list[Section]` so kb/p1_chunk.py can regenerate the *identical* segment text
for chunking. Sections are verbatim slices of the file body; the only edits
are whole-line removals (image markdown, `*Chart:*` captions, HTML comments,
horizontal rules) which act as hard boundaries, never as inline mutations —
this is what keeps `chunk_roundtrip_exact_sample` achievable.

section_id = sha256(f"{doc_id}|{ord}")[:32]  (same rule as sec_sectioner).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
TMP = ROOT / "kb/state/tmp"
REPORTS = ROOT / "kb/reports"

NON_SEC_TYPES = ("book", "broker_weekly", "broker_daily", "broker_monthly",
                 "sec_6k", "sec_10q", "sec_8k")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

# 10-Q / 10-K-style markers (uppercase or title case, with/without space before dot)
MARKER_RE = re.compile(
    r"^\s*\**\s*(?:ITEM|Item)\s+(\d{1,2}(?:\.?[A-Za-z])?)\s*\.?\s*"
)
# 8-K markers: "Item 2.02", "Item 9.01" (dotted decimal, title case)
MARKER_8K_RE = re.compile(r"^\s*\**\s*(?:Item)\s+(\d{1,2}\.\d{2})\b")

# section-level boundaries besides ITEM markers (10-Q / 8-K)
PART_RE = re.compile(r"^\s*\**\s*(?:PART)\s+([IVX]+)\b", re.IGNORECASE)
SIGNATURE_RE = re.compile(r"^\s*\**\s*(?:SIGNATURES?|EXHIBIT\s+INDEX)\b", re.IGNORECASE)

BOILERPLATE_HEADING_HINTS = (
    "disclaimer", "contact", "about us", "about ", "legal", "copyright",
    "terms of", "methodology", "subscription", "notes", "footnote", "appendix",
    "analyst certification", "important notice", "important information",
    "confidential", "source", "glossary", "disclosure",
)

# image markdown / chart captions / comments / horizontal rules — dropped whole-line.
def _is_dropped(line: str) -> bool:
    s = line.strip()
    if not s:
        return False  # blank lines kept (paragraph separators)
    if s.startswith("!["):
        return True
    if s.startswith("*Chart") or s.startswith("*Figure") or s.startswith("*Table:"):
        return True
    if s.startswith("<!--"):
        return True
    if s in ("---", "***", "___", "* * *", "----"):
        return True
    return False


def frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m[1]] = m[2].strip().strip("'\"")
    return fm, text[end + 4:]


def clean_body(body: str) -> str:
    """Drop non-text whole lines; keep blank lines. Returns verbatim-elsewhere text."""
    return "\n".join(l for l in body.split("\n") if not _is_dropped(l))


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical_10q_item(label: str) -> str:
    """'1' -> item_1, '1A' -> item_1a, '7A' -> item_7a, else item_<label>."""
    lab = label.replace(".", "").upper().strip()
    base = {"1": "item_1", "1A": "item_1a", "1B": "item_1b", "2": "item_2",
            "3": "item_3", "4": "item_4", "5": "item_5", "6": "item_6",
            "7": "item_7", "7A": "item_7a", "8": "item_8", "9": "item_9",
            "9A": "item_9a", "9B": "item_9b"}
    if lab in base:
        return base[lab]
    return "item_" + lab.lower()


def canonical_8k_item(label: str) -> str:
    return "item_" + label.replace(".", "_")


def _heading_kind(heading: str) -> str:
    h = heading.lower()
    return "boilerplate" if any(x in h for x in BOILERPLATE_HEADING_HINTS) else "prose"


class Section:
    __slots__ = ("heading_path", "kind", "sec_item", "seg")

    def __init__(self, heading_path, kind, sec_item, seg):
        self.heading_path = heading_path
        self.kind = kind
        self.sec_item = sec_item
        self.seg = seg


def _mk_preamble(seg):
    # metadata block (`**Date:**` / `**Publisher:**`) -> boilerplate
    head = seg[:500].lower()
    if "**date:" in head or "**publisher:" in head or "**original url:" in head:
        return Section([], "boilerplate", None, seg)
    return Section([], "prose", None, seg)


def _sectionize_on_headings(body: str, sec_item_map) -> list[Section]:
    """Split body at markdown heading lines; heading text becomes heading_path."""
    lines = body.split("\n")
    sections: list[Section] = []
    # find heading line indices
    head_idx = [i for i, l in enumerate(lines) if HEADING_RE.match(l.strip())]
    segs = []  # (heading_text or None, start_line, end_line)
    if not head_idx:
        return [_mk_preamble(body)]

    # preamble before first heading
    if head_idx[0] > 0:
        pre = "\n".join(lines[:head_idx[0]])
        if pre.strip():
            sections.append(_mk_preamble(pre))

    for k, idx in enumerate(head_idx):
        hline = lines[idx].strip()
        m = HEADING_RE.match(hline)
        heading = m.group(2)
        end = head_idx[k + 1] if k + 1 < len(head_idx) else len(lines)
        # body starts on the line AFTER the heading line; heading text excluded
        seg = "\n".join(lines[idx + 1:end])
        kind = _heading_kind(heading)
        # metadata block directly under the title heading -> boilerplate
        if "**date:" in seg[:500].lower() or "**publisher:" in seg[:500].lower():
            kind = "boilerplate"
        sec_item = sec_item_map(heading) if sec_item_map else None
        sections.append(Section([heading], kind, sec_item, seg))
    return sections


def _sectionize_on_markers(body: str, label_style: str) -> list[Section]:
    """Split a 10-Q/8-K body at Item/PART/SIGNATURE markers (keep marker line in seg)."""
    lines = body.split("\n")
    bounds = []  # (line_idx, sec_item, is_boilerplate)
    for i, raw in enumerate(lines):
        l = raw.strip()
        mm = MARKER_8K_RE.match(l) if label_style == "8k" else None
        if label_style == "8k" and mm:
            bounds.append((i, canonical_8k_item(mm.group(1)), False))
            continue
        m = MARKER_RE.match(l)
        if label_style != "8k" and m:
            bounds.append((i, canonical_10q_item(m.group(1)), False))
            continue
        if PART_RE.match(l):
            bounds.append((i, "part_" + PART_RE.match(l).group(1).lower(), False))
            continue
        if SIGNATURE_RE.match(l):
            bounds.append((i, "signatures", True))
            continue

    sections: list[Section] = []
    if not bounds:
        return [_mk_preamble(body)]

    if bounds[0][0] > 0:
        pre = "\n".join(lines[:bounds[0][0]])
        if pre.strip():
            sections.append(_mk_preamble(pre))

    for k, (idx, item, is_boil) in enumerate(bounds):
        end = bounds[k + 1][0] if k + 1 < len(bounds) else len(lines)
        seg = "\n".join(lines[idx:end])  # marker line included
        kind = "boilerplate" if is_boil else "prose"
        sections.append(Section([item], kind, item, seg))
    return sections


def sectionize(doc_id: str, doc_type: str, title, text: str) -> list[Section]:
    """Return ordered Section objects for a non-SEC document body (frontmatter stripped)."""
    _fm, body = frontmatter(text)
    body = clean_body(body)

    if doc_type == "book":
        return _sectionize_on_headings(body, None)
    if doc_type in ("broker_weekly", "broker_daily", "broker_monthly"):
        return _sectionize_on_headings(body, None)
    if doc_type == "sec_6k":
        heading = title or "Press Release"
        return [Section([heading], "prose", "press_release", body)]
    if doc_type == "sec_10q":
        return _sectionize_on_markers(body, "10q")
    if doc_type == "sec_8k":
        return _sectionize_on_markers(body, "8k")
    return [_mk_preamble(body)]


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='2GB'")
    con.execute(f"SET temp_directory='{TMP.as_posix()}'")
    con.execute("""
        CREATE TABLE IF NOT EXISTS section (
          section_id VARCHAR PRIMARY KEY, doc_id VARCHAR, ord INT,
          heading_path VARCHAR[], kind VARCHAR,
          sec_item VARCHAR, sha256 VARCHAR, tokens INT);
    """)

    docs = con.execute(
        f"""SELECT doc_id, path, doc_type, title FROM document
            WHERE doc_type IN ({','.join('?' * len(NON_SEC_TYPES))})
            ORDER BY path""",
        list(NON_SEC_TYPES),
    ).fetchall()

    # idempotent: clear only this module's doc_ids, never SEC rows
    doc_ids = [d[0] for d in docs]
    for i in range(0, len(doc_ids), 500):
        chunk = doc_ids[i:i + 500]
        con.execute(
            f"DELETE FROM section WHERE doc_id IN ({','.join('?' * len(chunk))})",
            chunk,
        )

    total_rows = 0
    per_type = {t: 0 for t in NON_SEC_TYPES}
    per_type_sections = {t: 0 for t in NON_SEC_TYPES}
    empty_docs = []

    rows = []
    for doc_id, relp, doc_type, title in docs:
        p = ROOT / relp
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            empty_docs.append((relp, f"read:{e}"))
            continue
        secs = sectionize(doc_id, doc_type, title, text)
        if not secs:
            empty_docs.append((relp, "no_sections"))
            continue
        per_type[doc_type] += 1
        per_type_sections[doc_type] += len(secs)
        for ord_, s in enumerate(secs):
            sid = sha256_hex(f"{doc_id}|{ord_}".encode())[:32]
            seg = s.seg
            toks = len(re.findall(r"\S+", seg))
            rows.append([
                sid, doc_id, ord_, s.heading_path, s.kind, s.sec_item,
                sha256_hex(seg.encode("utf-8", errors="replace")), toks,
            ])
            total_rows += 1
        if len(rows) >= 4000:
            con.executemany(
                """INSERT INTO section (section_id, doc_id, ord, heading_path, kind,
                     sec_item, sha256, tokens) VALUES (?,?,?,?,?,?,?,?)""",
                rows,
            )
            rows = []

    if rows:
        con.executemany(
            """INSERT INTO section (section_id, doc_id, ord, heading_path, kind,
                 sec_item, sha256, tokens) VALUES (?,?,?,?,?,?,?,?)""",
            rows,
        )

    print(f"P1 sectioner: {len(docs)} non-SEC docs -> {total_rows} sections")
    for t in NON_SEC_TYPES:
        print(f"  {t}: {per_type[t]} docs, {per_type_sections[t]} sections")
    if empty_docs:
        print(f"  empty/error docs ({len(empty_docs)}):")
        for relp, why in empty_docs[:30]:
            print(f"    {relp} :: {why}")

    (REPORTS / "p1_section.json").write_text(json.dumps({
        "phase": "P1",
        "non_sec_docs": len(docs),
        "total_sections": total_rows,
        "per_type_docs": per_type,
        "per_type_sections": per_type_sections,
        "empty_docs": [e[0] for e in empty_docs],
    }, indent=2), encoding="utf-8")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
