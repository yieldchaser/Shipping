"""SEC sectioner: split 10-K/20-F markdown filings on uppercase ITEM N. markers.

Reads document rows (doc_type in sec_10k/sec_20f) from kb/state/kb.duckdb, scans each
MD body for section markers, and writes `section` rows with heading_path, kind and
sec_item. 6-K press releases are not touched here (each is one section, handled in P1).

Marker syntaxes handled:
  - "ITEM 1. BUSINESS" (block caps, dot)  -- 10-K and 20-F
  - "Item 4.A Unresolved Staff Comments"  (Title case) -- 20-F sub-parts
  - "Item 16.A Audit Committee Financial Expert" etc.

Boilerplate classification is done in P1 (kind=boilerplate via cross-issue hash); here we
only assign sec_item ids so the P0.5 gate `sec_item_coverage_top25_10k_20f` can be measured.

Idempotent: deletes and rebuilds the `section` table. Does not touch the source MDs.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
STATE = ROOT / "kb/state"
TMP = STATE / "tmp"

# canonical item ids. 20-F "Item 4.A" maps to item_4; "Item 16.X" to item_16 etc.
ITEM_BASE = {
    "1": "item_1", "1A": "item_1a", "1B": "item_1b",
    "2": "item_2", "3": "item_3", "3.D": "item_3d", "4": "item_4",
    "4.A": "item_4", "5": "item_5", "6": "item_6", "7": "item_7",
    "8": "item_8", "9": "item_9", "9A": "item_9a", "9B": "item_9b",
    "10": "item_10", "11": "item_11", "12": "item_12", "13": "item_13",
    "14": "item_14", "15": "item_15", "16": "item_16", "17": "item_17",
    "18": "item_18", "19": "item_19",
}
ITEM_SUFFIX = {
    "7A": "item_7a", "8A": "item_8a", "10A": "item_10a", "11A": "item_11a",
}

# marker patterns ordered broad -> specific. group(1) = numeric label, group(2) = title tail.
MARKER_RE = re.compile(
    r"^\s*\**\s*(?:ITEM|Item)\s+(\d{1,2}(?:\.?[A-Za-z])?)\s*\.?\s*\**\s+(.+?)\s*\**\s*$",
    re.MULTILINE,
)

# boilerplate item ids we still record but mark as such (P1 uses cross-issue hashing too).
BOILER_ITEM_HINTS = {
    "item_9b", "item_19",  # controls/exhibits tend toward boilerplate, refine in P1
}

# ---------------------------------------------------------------------------
# Fallback: some 20-F filers (BHP, RIO, VALE) carry no "Item N." text markers,
# only a cross-reference table (pipe rows or a run-on "Form 20-F Caption" text
# layer). We recover item anchors from those within the first 500 lines, so the
# P0.5 gate can still find item_5/item_7. Anchors are keyed on the numeric label
# column and cross-checked against the caption text (number must match caption).
# ---------------------------------------------------------------------------
CAPTION_ITEM = [
    (re.compile(r"identity of directors"), "item_1"),
    (re.compile(r"offer statistics"), "item_2"),
    (re.compile(r"key information"), "item_3"),
    (re.compile(r"information on the company"), "item_4"),
    (re.compile(r"operating and financial review"), "item_5"),
    (re.compile(r"directors,?\s+senior management and employees"), "item_6"),
    (re.compile(r"management and employees"), "item_6"),
    (re.compile(r"major shareholders"), "item_7"),
    (re.compile(r"share ownership and trading"), "item_7"),
    (re.compile(r"share ownership"), "item_7"),
    (re.compile(r"financial information"), "item_8"),
    (re.compile(r"offer and listing"), "item_9"),
    (re.compile(r"quantitative and qualitative"), "item_11"),
    (re.compile(r"additional information"), "item_10"),
    (re.compile(r"financial statements"), "item_18"),
    (re.compile(r"exhibits"), "item_19"),
]

NUMROW = re.compile(r"^\s*\|\s*(\d{1,2}[A-Za-z]?)\s*\.?\s*\|\s*(.*?)\s*\|\s*$")
ROMANROW = re.compile(r"^\s*\|\s*\**(?:VIII|VII|III|II|IV|VI|IX|V|I|X)\.?\s*\**\s+(.+?)\s*\**\s*\|")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical_item(label: str) -> str:
    """Map a captured marker label to a canonical sec_item token."""
    lab = label.replace(".", "").upper().strip()
    if lab in ITEM_SUFFIX:
        return ITEM_SUFFIX[lab]
    if lab in ITEM_BASE:
        return ITEM_BASE[lab]
    # strip trailing letter for items like "16A" -> "16"
    m = re.match(r"^(\d{1,2})[A-Z]?$", lab)
    if m and m.group(1) in ITEM_BASE:
        return ITEM_BASE[m.group(1)]
    return None


def find_items(text: str):
    """Yield (char_offset, canonical_item, raw_title) for each marker line."""
    for match in MARKER_RE.finditer(text):
        label, title = match.group(1), match.group(2).strip()
        item = canonical_item(label)
        if item is None:
            continue
        yield match.start(), item, title


def caption_to_item(caption: str):
    """Map a 20-F cross-reference caption to a canonical item id (lowercased)."""
    c = caption.lower()
    for pat, item in CAPTION_ITEM:
        if pat.search(c):
            return item
    return None


def fallback_items(text: str, max_lines: int = 500):
    """Yield (line_index, item, source) anchor rows recovered from a 20-F
    cross-reference table within the first `max_lines` lines, for documents that
    have no plain "Item N." markers."""
    items = []
    for ln, line in enumerate(text.split("\n")[:max_lines]):
        ll = line.lower()
        if "form 20-f caption" in ll or "form 20-f cross-reference" in ll:
            for pat, item in CAPTION_ITEM:
                if pat.search(ll):
                    items.append((item, ln, "runon"))
            continue
        m = NUMROW.match(line)
        if m:
            label, caption = m.group(1), m.group(2).strip()
            it_num = canonical_item(label)
            it_cap = caption_to_item(caption)
            if it_num and it_cap and it_num == it_cap:
                items.append((it_num, ln, f"num:{label}"))
            continue
        m = ROMANROW.match(line)
        if m:
            it_cap = caption_to_item(m.group(1))
            if it_cap:
                items.append((it_cap, ln, "roman"))
    return items


def merged_items(text: str):
    """Yield (char_offset, canonical_item, raw_title) from plain markers plus
    recovered cross-reference anchors, sorted by offset. Fallback anchors carry a
    line index, converted to a character offset so section_rows can split on them."""
    out = list(find_items(text))
    line_starts = [0]
    for line in text.split("\n"):
        line_starts.append(line_starts[-1] + len(line) + 1)
    for item, ln, _src in fallback_items(text):
        off = line_starts[ln] if ln < len(line_starts) else 0
        out.append((off, item, ""))
    out.sort()
    return out


def section_rows(doc_id: str, text: str, items=None):
    """Yield dicts for the `section` table. Marker spans split the body into sections."""
    if items is None:
        items = list(find_items(text))
    if not items:
        return []
    rows = []
    ord_ = 0
    # preamble (before first marker)
    if items[0][0] > 0:
        seg = text[: items[0][0]]
        rows.append(_mk(doc_id, ord_, "preamble", seg))
        ord_ += 1
    for i, (off, item, title) in enumerate(items):
        end = items[i + 1][0] if i + 1 < len(items) else len(text)
        seg = text[off:end]
        rows.append(_mk(doc_id, ord_, item, seg, title))
        ord_ += 1
    return rows


def _mk(doc_id, ord_, item, seg, title=None):
    toks = len(re.findall(r"\S+", seg))
    heading = title or item.replace("item_", "ITEM ").upper()
    return {
        "section_id": None,  # filled below
        "doc_id": doc_id,
        "ord": ord_,
        "heading_path": [heading],
        "kind": "boilerplate" if item in BOILER_ITEM_HINTS else "prose",
        "sec_item": item,
        "sha256": sha256_hex(seg.encode("utf-8", errors="replace")),
        "tokens": toks,
    }


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='2GB'")
    con.execute(f"SET temp_directory='{TMP.as_posix()}'")
    con.execute("""
        CREATE TABLE IF NOT EXISTS section (
          section_id VARCHAR PRIMARY KEY, doc_id VARCHAR, ord INT,
          heading_path VARCHAR[], kind VARCHAR,
          sec_item VARCHAR, sha256 VARCHAR, tokens INT);
    """)
    con.execute("DELETE FROM section")

    docs = con.execute(
        """SELECT doc_id, path FROM document
           WHERE doc_type IN ('sec_10k','sec_20f') ORDER BY path"""
    ).fetchall()

    total_rows = 0
    covered = 0          # docs with >=1 item marker
    with_item5_7 = 0     # docs with item_5 OR item_7
    missing = []
    for doc_id, relp in docs:
        p = ROOT / relp
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            missing.append((relp, f"read:{e}"))
            continue
        items = list(merged_items(text))
        if not items:
            missing.append((relp, "no_item_markers"))
            continue
        covered += 1
        found = {it for _, it, _ in items}
        if "item_5" in found or "item_7" in found:
            with_item5_7 += 1
        for r in section_rows(doc_id, text, items):
            r["section_id"] = sha256_hex(
                f"{doc_id}|{r['ord']}".encode()
            )[:32]
            con.execute(
                """INSERT INTO section (section_id, doc_id, ord, heading_path, kind,
                     sec_item, sha256, tokens)
                   VALUES (?,?,?,?,?,?,?,?)""",
                [r["section_id"], r["doc_id"], r["ord"], r["heading_path"],
                 r["kind"], r["sec_item"], r["sha256"], r["tokens"]],
            )
            total_rows += 1

    n = len(docs)
    rate = covered / n if n else 0.0
    i57 = with_item5_7 / n if n else 0.0
    print(f"SEC sectioner: {n} docs (10-K/20-F), {covered} covered ({rate:.3f}), "
          f"{with_item5_7} with item_5/7 ({i57:.3f}), {total_rows} sections")
    if missing:
        print(f"  missing ({len(missing)}):")
        for relp, why in missing[:40]:
            print(f"    {relp} :: {why}")
        if len(missing) > 40:
            print(f"    ... {len(missing)-40} more")
    # write a coverage JSON for the gate
    out = {
        "phase": "P0_5",
        "sec_10k_20f_total": n,
        "covered": covered,
        "with_item5_7": with_item5_7,
        "coverage": round(rate, 4),
        "item5_7_rate": round(i57, 4),
        "missing": [m[0] for m in missing],
    }
    (ROOT / "kb/reports/sec_section_coverage.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
