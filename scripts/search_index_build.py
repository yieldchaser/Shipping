"""Build pre-tokenized BM25-ready search indexes for the browser Q&A panel.

For every ``knowledge/chunks/{stem}.jsonl`` shard this writes a compact
``knowledge/chunks/search/{stem}.idx.json`` index (vocabulary + per-doc
top-term posting lists) plus a manifest at
``knowledge/chunks/search/index.json``.

CLI:
    python scripts/search_index_build.py [--chunks-dir PATH] [--out-dir PATH] [--stems stem1,stem2]

Programmatic:
    from search_index_build import build_all
    manifest = build_all(chunks_dir, out_dir, stems=None)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

INDEX_VERSION = 1
MAX_TF = 9
TOP_TERMS = 40
SHARD_SUFFIX = ".jsonl"
IDX_SUFFIX = ".idx.json"
MANIFEST_NAME = "index.json"

_REPO_ROOT = Path(__file__).resolve().parents[1]

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset((
    "the,a,an,and,or,of,to,in,on,for,with,at,by,from,as,is,are,was,were,be,"
    "been,it,its,this,that,these,those,we,you,they,he,she,but,if,then,than,"
    "so,not,no,nor,only,own,same,too,very,can,will,just,should,now,has,have,"
    "had,do,does,did,doing,would,could,ought,i,me,my,our,your,him,his,her,"
    "them,their,what,which,who,whom,am,being,having,because,until,while,"
    "about,against,between,into,through,during,before,after,above,below,up,"
    "down,out,off,over,under,again,further,once,here,there,when,where,why,"
    "how,all,any,both,each,few,more,most,other,some,such"
).split(","))


def tokenize(text: str) -> list[str]:
    """Canonical tokenizer: lowercase, [a-z0-9]+ runs, drop len<2 and stopwords."""
    return [
        tok
        for tok in _TOKEN_RE.findall(text.lower())
        if len(tok) >= 2 and tok not in _STOPWORDS
    ]


def _doc_terms(
    text: str, vocab: list[str], vocab_index: dict[str, int]
) -> tuple[int, list[list[int]]]:
    """Return (distinct term count, top-N [[vocabIdx, tf], ...]) for one doc."""
    counts: dict[str, int] = {}
    for tok in tokenize(text):
        counts[tok] = counts.get(tok, 0) + 1
    entries: list[tuple[int, int]] = []
    for term, tf in counts.items():
        vid = vocab_index.get(term)
        if vid is None:
            vid = len(vocab)
            vocab_index[term] = vid
            vocab.append(term)
        entries.append((vid, tf if tf < MAX_TF else MAX_TF))
    entries.sort(key=lambda e: (-e[1], e[0]))
    return len(counts), [[vid, tf] for vid, tf in entries[:TOP_TERMS]]


def build_shard_index(shard_path: Path) -> dict:
    """Stream one JSONL shard into an index payload dict."""
    vocab: list[str] = []
    vocab_index: dict[str, int] = {}
    docs: list[dict] = []
    total_distinct = 0
    # "i" is the ordinal among successfully parsed docs, NOT the raw file line
    # number. The browser materializes chunk text by fetching the shard and
    # indexing into its parsed-rows array (blank/corrupt lines are dropped on
    # both sides), so both counters must skip the same lines.
    ordinal = 0
    with open(shard_path, "r", encoding="utf-8") as fh:
        for _raw_line_no, line in enumerate(fh):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            text = obj.get("text")
            if not isinstance(text, str):
                text = "" if text is None else str(text)
            distinct, terms = _doc_terms(text, vocab, vocab_index)
            docs.append(
                {
                    "i": ordinal,
                    "c": obj.get("chunk_id"),
                    "D": obj.get("date"),
                    "s": obj.get("section_title"),
                    "o": obj.get("doc_id"),
                    "n": distinct,
                    "t": terms,
                }
            )
            ordinal += 1
            total_distinct += distinct
    count = len(docs)
    return {
        "v": INDEX_VERSION,
        "stem": shard_path.name[: -len(SHARD_SUFFIX)],
        "count": count,
        "avgdl": round(total_distinct / count, 1) if count else 0.0,
        "vocab": vocab,
        "docs": docs,
    }


def _atomic_write_json(path: Path, payload: dict) -> int:
    """Write JSON atomically (tmp + os.replace); returns file size in bytes."""
    tmp = path.with_name(path.name + ".tmp")
    data = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(data)
    os.replace(tmp, path)
    return path.stat().st_size


def build_all(
    chunks_dir: str | Path | None = None,
    out_dir: str | Path | None = None,
    stems: list[str] | None = None,
) -> dict:
    """Build (or refresh) search indexes for all shards; returns the manifest."""
    chunks = Path(chunks_dir) if chunks_dir else _REPO_ROOT / "knowledge" / "chunks"
    out = Path(out_dir) if out_dir else chunks / "search"

    wanted: list[str] | None = None
    if stems:
        wanted = []
        for s in stems:
            s = s.strip()
            if s and s not in wanted:
                wanted.append(s)

    if not chunks.is_dir():
        print(f"[idx] chunks dir not found: {chunks}")
    shard_map = {
        p.name[: -len(SHARD_SUFFIX)]: p for p in chunks.glob(f"*{SHARD_SUFFIX}") if p.is_file()
    } if chunks.is_dir() else {}

    order = sorted(set(wanted)) if wanted is not None else sorted(shard_map)
    out.mkdir(parents=True, exist_ok=True)

    files: list[dict] = []
    total_bytes = 0
    for stem in order:
        shard_path = shard_map.get(stem)
        if shard_path is None:
            print(f"[idx] {stem}: skipped (shard not found)")
            continue
        payload = build_shard_index(shard_path)
        idx_path = out / f"{stem}{IDX_SUFFIX}"
        nbytes = _atomic_write_json(idx_path, payload)
        total_bytes += nbytes
        print(
            f"[idx] {stem}: {payload['count']} docs, "
            f"{len(payload['vocab'])} terms, {nbytes} bytes"
        )
        try:
            idx_rel = idx_path.relative_to(chunks).as_posix()
        except ValueError:
            idx_rel = f"{out.name}/{idx_path.name}"
        files.append(
            {"stem": stem, "idx": idx_rel, "bytes": nbytes, "count": payload["count"]}
        )

    files.sort(key=lambda e: e["stem"])
    manifest = {
        "v": INDEX_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": files,
    }
    _atomic_write_json(out / MANIFEST_NAME, manifest)
    print(f"[idx] manifest: {len(files)} shards, total {total_bytes / (1024 * 1024):.1f} MB")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build pre-tokenized BM25-ready search indexes from knowledge/chunks shards."
    )
    parser.add_argument("--chunks-dir", default=None, help="Directory containing {stem}.jsonl shards")
    parser.add_argument("--out-dir", default=None, help="Output directory for .idx.json files")
    parser.add_argument("--stems", default=None, help="Comma-separated subset of shard stems")
    args = parser.parse_args(argv)

    stems = (
        [s.strip() for s in args.stems.split(",") if s.strip()] if args.stems else None
    )
    build_all(args.chunks_dir, args.out_dir, stems)
    return 0


if __name__ == "__main__":
    sys.exit(main())
