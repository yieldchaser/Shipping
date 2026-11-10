"""P1 chunker: split every `section` into `chunk` rows + sentence offsets.

Follows docs/GRAPHRAG_BUILD_PLAN.md 5.2 / 5.3:

  - Prose: 300-700 tokens (tiktoken o200k_base), on paragraph boundaries inside a
    section, never across sections. Oversized paragraphs are split on sentence
    boundaries. Sentence offsets (shipping-aware splitter) go to `sentence`.
  - Tables: markdown pipe tables become one chunk each; long tables split every 40
    rows with the header row repeated. A row is never split.
  - Dedup: normalise (lowercase, collapse whitespace, mask numbers + dates) -> sha
    -> `norm_sha`; a repeat is stored once and points to the first occurrence via
    `is_duplicate_of`. Repeats are flagged `extract=false`.
  - context_prefix follows 5.3 (entities empty at P1).

Chunk text is verbatim slices of the section segment (or, for tables, verbatim
lines assembled with a repeated header). This keeps `chunk_roundtrip_exact_sample`
achievable: a prose chunk body is a contiguous substring of the cleaned source; a
table chunk body is its header line (verbatim) + a contiguous run of data rows.

Idempotent: deletes and rebuilds `chunk` and `sentence`. Owns no source files.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import duckdb
import tiktoken

import sec_sectioner
import p1_section

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
TMP = ROOT / "kb/state/tmp"
REPORTS = ROOT / "kb/reports"

MIN_TOKENS = 300
MAX_TOKENS = 700
TABLE_ROWS_PER_CHUNK = 40

ENC = tiktoken.get_encoding("o200k_base")

# ---- markdown table detection -------------------------------------------------
TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")


def is_sep_line(line: str) -> bool:
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return False
    if "-" not in s:
        return False
    return all(c in "| -:." for c in s)


# ---- sentence splitter (shipping-aware) ----------------------------------------
# protected abbreviations (dots already stripped, lowercase)
ABBR_STRIPPED = {
    "abt", "approx", "dwt", "mt", "mv", "us", "uk", "wc", "no", "nos", "incl",
    "etc", "eg", "ie", "vs", "viz", "cf", "fig", "sec", "min", "max", "mr",
    "mrs", "ms", "dr", "prof", "st", "inc", "ltd", "co", "corp", "llc", "pa",
    "kg", "as", "sa", "bv", "nv", "gmbh", "ag", "lng", "lpg", "bbl", "est",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
}

SENT_BOUNDARY_RE = re.compile(r'(?<=[.!?])(?=\s+[A-Z0-9"\u2018\u201C(\[\u00AB<])')


def _ends_with_abbrev(s: str) -> bool:
    """True if `s` (ending in a sentence terminator) should NOT end a sentence."""
    s = s.rstrip()
    if not s or not s.endswith((".", "!", "?")):
        return False
    if s.endswith(("!", "?")):
        return False
    m = re.search(r"(\S+)\.$", s)
    if not m:
        return True
    w = m.group(1).lstrip("(").strip("\"'")
    wl = w.lower()
    if re.fullmatch(r"\d+", wl):
        return True  # list marker / standalone number
    if "." in wl:
        parts = wl.split(".")
        if parts and all(0 < len(x) <= 3 for x in parts):
            return True  # initials / compound abbrev (U.S., e.g., i.e.)
    if re.fullmatch(r"[a-z]", wl):
        return True  # single initial (U. S.)
    if wl in ABBR_STRIPPED:
        return True
    return False


def split_sentences(text: str):
    """Return list of (start_char, end_char) half-open spans covering `text`."""
    if not text:
        return []
    spans = []
    start = 0
    for m in SENT_BOUNDARY_RE.finditer(text):
        if _ends_with_abbrev(text[start:m.start()]):
            continue
        spans.append((start, m.start()))
        start = m.start()
    spans.append((start, len(text)))
    return spans


# ---- normalisation (dedup) ------------------------------------------------------
def normalize(body: str) -> str:
    t = body.lower()
    t = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<DATE>", t)   # dates before numbers
    t = re.sub(r"\b\d+(?:[.,]\d+)+\b", "<NUM>", t)       # decimals
    t = re.sub(r"\b\d+\b", "<NUM>", t)                   # integers
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def num_tokens(s: str) -> int:
    return len(ENC.encode(s, disallowed_special=()))


# ---- prose chunking ------------------------------------------------------------
def paragraph_blocks(seg: str):
    """Yield (start, end) char-index blocks of `seg`; each starts at a paragraph
    (a non-blank line right after a blank line or the start). Blocks tile seg."""
    lines = seg.split("\n")
    n = len(lines)
    starts = []
    for idx, line in enumerate(lines):
        if line.strip() == "":
            continue
        if idx == 0 or lines[idx - 1].strip() == "":
            starts.append(idx)
    if not starts:
        return [] if not seg.strip() else [(0, n)]
    # convert line indices to char offsets
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line) + 1)
    blocks = []
    for k, ls in enumerate(starts):
        le = starts[k + 1] if k + 1 < len(starts) else n
        blocks.append((offsets[ls], offsets[le]))
    blocks[0] = (0, blocks[0][1])  # leading blank lines belong to first block
    return [(a, b) for a, b in blocks if b > a]


def sentence_groups(text: str):
    """Greedily group sentences of `text` into 300-700 token spans (char offsets)."""
    spans = split_sentences(text)
    out = []
    i = 0
    while i < len(spans):
        j = i
        while j < len(spans):
            tok = num_tokens(text[spans[i][0]:spans[j][1]])
            if tok > MAX_TOKENS:
                if j == i:
                    j += 1  # single oversized sentence emitted alone
                break
            j += 1
            if tok >= MIN_TOKENS:
                break
        out.append((spans[i][0], spans[j - 1][1]))
        i = j
    return out


def chunk_prose(seg: str):
    """Return list of (kind, body) chunks, bodies tiling `seg` exactly."""
    chunks = []
    for bs, be in paragraph_blocks(seg):
        block = seg[bs:be]
        bt = num_tokens(block)
        if bt <= MAX_TOKENS:
            # merge with previous chunk if small and adjacent
            if chunks and chunks[-1][0] == "prose" and num_tokens(chunks[-1][1] + block) <= MAX_TOKENS:
                chunks[-1] = ("prose", chunks[-1][1] + block)
            else:
                chunks.append(("prose", block))
        else:
            # oversized paragraph: sentence-group it
            for cs, ce in sentence_groups(block):
                chunks.append(("prose", block[cs:ce]))
    return chunks


def chunk_table_block(table_lines):
    """Return list of chunk bodies; header row repeated, <=40 data rows each."""
    header = None
    rows = []
    for ln in table_lines:
        if is_sep_line(ln):
            continue
        if header is None:
            header = ln
        else:
            rows.append(ln)
    if header is None or not rows:
        return []
    out = []
    for k in range(0, len(rows), TABLE_ROWS_PER_CHUNK):
        out.append(header + "\n" + "\n".join(rows[k:k + TABLE_ROWS_PER_CHUNK]))
    return out


def chunk_seg(seg: str):
    """Split a section segment into ordered (kind, body) chunks.

    Table runs (>=2 consecutive pipe lines) become table chunks; the rest is
    prose. Prose/table bodies are verbatim slices/lines of `seg`."""
    lines = seg.split("\n")
    n = len(lines)
    chunks = []
    i = 0
    while i < n:
        if TABLE_LINE_RE.match(lines[i]):
            j = i
            while j < n and TABLE_LINE_RE.match(lines[j]):
                j += 1
            if j - i >= 2:
                for body in chunk_table_block(lines[i:j]):
                    chunks.append(("table", body))
                i = j
                continue
            # lone pipe line: treat as a single prose line and advance past it
            chunks.extend(chunk_prose(lines[i]))
            i += 1
            continue
        j = i
        while j < n and not TABLE_LINE_RE.match(lines[j]):
            j += 1
        sub = "\n".join(lines[i:j])
        chunks.extend(chunk_prose(sub))
        i = j
    return chunks


# ---- section segment reconstruction (matches sectioners exactly) --------------
def sec_segs(text: str):
    """Ordered segment texts for a 10-K/20-F, mirroring sec_sectioner.section_rows."""
    items = sec_sectioner.merged_items(text)
    if not items:
        return []
    segs = []
    if items[0][0] > 0:
        segs.append(text[:items[0][0]])
    for i, (off, _item, _title) in enumerate(items):
        end = items[i + 1][0] if i + 1 < len(items) else len(text)
        segs.append(text[off:end])
    return segs


def segs_for_doc(doc_type: str, title, text: str):
    if doc_type in ("sec_10k", "sec_20f"):
        return sec_segs(text)
    return [s.seg for s in p1_section.sectionize(None, doc_type, title, text)]


def context_prefix(publisher, title, published_at, heading_path, sec_item):
    head = " / ".join(heading_path) if heading_path else ""
    parts = [publisher, title, str(published_at), head, sec_item]
    core = " · ".join(p for p in parts if p)
    return f"{core} · entities: "


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='2GB'")
    con.execute(f"SET temp_directory='{TMP.as_posix()}'")
    con.execute("""
        CREATE TABLE IF NOT EXISTS chunk (
          chunk_id VARCHAR PRIMARY KEY, doc_id VARCHAR, section_id VARCHAR, ord INT,
          kind VARCHAR, context_prefix VARCHAR, body VARCHAR, tokens INT, sha256 VARCHAR,
          norm_sha VARCHAR, is_duplicate_of VARCHAR, entity_ids VARCHAR[],
          vec_row INT, extract BOOLEAN);
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sentence (
          chunk_id VARCHAR, sid INT, start_char INT, end_char INT,
          PRIMARY KEY (chunk_id, sid));
    """)
    con.execute("DELETE FROM chunk")
    con.execute("DELETE FROM sentence")

    docs = con.execute(
        """SELECT doc_id, path, doc_type, title, publisher_id, published_at
           FROM document ORDER BY doc_id"""
    ).fetchall()
    doc_meta = {d[0]: d for d in docs}

    sections = con.execute(
        """SELECT section_id, doc_id, ord, heading_path, kind, sec_item
           FROM section ORDER BY doc_id, ord"""
    ).fetchall()

    sec_by_doc = {}
    for s in sections:
        sec_by_doc.setdefault(s[1], []).append(s)

    first_by_norm = {}
    chunk_rows = []
    sent_rows = []
    stat_docs = 0
    stat_chunks = 0
    stat_sents = 0
    stat_dups = 0
    stat_table = 0
    errors = []

    for doc_id, path, doc_type, title, publisher, published_at in docs:
        meta = doc_meta[doc_id]
        secs = sec_by_doc.get(doc_id, [])
        try:
            text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            errors.append((path, f"read:{e}"))
            continue
        segs = segs_for_doc(doc_type, title, text)
        if len(segs) != len(secs):
            errors.append((path, f"seg_mismatch {len(segs)} vs {len(secs)}"))
            continue
        stat_docs += 1
        for (section_id, _did, sord, heading_path, skind, sec_item), seg in zip(secs, segs):
            for ck, (kind, body) in enumerate(chunk_seg(seg)):
                cid = sha256_hex(f"{doc_id}|{section_id}|{ck}".encode())[:32]
                toks = num_tokens(body)
                nsha = sha256_hex(normalize(body).encode("utf-8"))
                is_dup = first_by_norm.get(nsha)
                extract = is_dup is None
                if is_dup is None:
                    first_by_norm[nsha] = cid
                else:
                    stat_dups += 1
                if kind == "table":
                    stat_table += 1
                prefix = context_prefix(publisher, title, published_at,
                                        heading_path, sec_item)
                chunk_rows.append([
                    cid, doc_id, section_id, ck, kind, prefix, body, toks,
                    sha256_hex(body.encode("utf-8", errors="replace")), nsha,
                    is_dup, [], None, extract,
                ])
                stat_chunks += 1
                if kind == "prose":
                    for sid, (a, b) in enumerate(split_sentences(body)):
                        sent_rows.append([cid, sid, a, b])
                        stat_sents += 1
            if len(chunk_rows) >= 4000:
                con.executemany(
                    """INSERT INTO chunk (chunk_id, doc_id, section_id, ord, kind,
                         context_prefix, body, tokens, sha256, norm_sha, is_duplicate_of,
                         entity_ids, vec_row, extract) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    chunk_rows)
                chunk_rows = []
            if len(sent_rows) >= 8000:
                con.executemany(
                    "INSERT INTO sentence (chunk_id, sid, start_char, end_char) VALUES (?,?,?,?)",
                    sent_rows)
                sent_rows = []

    if chunk_rows:
        con.executemany(
            """INSERT INTO chunk (chunk_id, doc_id, section_id, ord, kind,
                 context_prefix, body, tokens, sha256, norm_sha, is_duplicate_of,
                 entity_ids, vec_row, extract) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            chunk_rows)
    if sent_rows:
        con.executemany(
            "INSERT INTO sentence (chunk_id, sid, start_char, end_char) VALUES (?,?,?,?)",
            sent_rows)

    # refresh frozen scope chunk_ids (never shrinks: this is the first population)
    scope_path = REPORTS / "scope_P0_5.json"
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    scope["chunk_ids"] = [r[0] for r in con.execute(
        "SELECT chunk_id FROM chunk ORDER BY chunk_id").fetchall()]
    scope_path.write_text(json.dumps(scope, indent=2), encoding="utf-8")

    n_doc = con.execute("SELECT count(*) FROM document").fetchone()[0]
    n_sec = con.execute("SELECT count(*) FROM section").fetchone()[0]
    n_chunk = con.execute("SELECT count(*) FROM chunk").fetchone()[0]
    n_sent = con.execute("SELECT count(*) FROM sentence").fetchone()[0]
    con.close()

    out = {
        "phase": "P1",
        "documents": n_doc,
        "sections": n_sec,
        "chunks": n_chunk,
        "sentences": n_sent,
        "chunked_docs": stat_docs,
        "table_chunks": stat_table,
        "duplicate_chunks": stat_dups,
        "errors": errors,
    }
    (REPORTS / "p1_chunk.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"P1 chunker: {stat_docs:,} docs -> {stat_chunks:,} chunks "
          f"({stat_table:,} table), {stat_sents:,} sentences, {stat_dups:,} dups")
    if errors:
        print(f"  errors ({len(errors)}):")
        for p, why in errors[:40]:
            print(f"    {p} :: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
