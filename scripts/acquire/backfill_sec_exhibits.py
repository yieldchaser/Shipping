#!/usr/bin/env python3
"""
scripts/acquire/backfill_sec_exhibits.py

Backfill EX-99.x exhibits into existing 6-K / 8-K corpus files that lack them.

For every corpus/10-companies/{TICKER}/{6-K,8-K}/*.md without an `exhibits:` key in its
frontmatter, the filing index is read, EX-99.x exhibits are downloaded (cached under
data/raw/sec_exhibits_cache/), converted with the main-document converter and appended as
`## Exhibit 99.x -- <description>` sections. The frontmatter gains `exhibits: [EX-99.1, ...]`.
Only corpus/10-companies is written; data/extracted/md is never touched.

Filings whose index lists no EX-99.x text exhibit are left unchanged and listed in the report
(for example press releases that were filed only as images).

Usage:
    python scripts/acquire/backfill_sec_exhibits.py [--forms 6-K 8-K] [--tickers VALE RIO]
                                                    [--limit N] [--report-json PATH] [FILE.md ...]
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import sec_exhibits as X  # noqa: E402

REPO_ROOT = SCRIPT_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
CORPUS_DIR = REPO_ROOT / "corpus" / "10-companies"


def read_frontmatter_field(md_text: str, key: str) -> Optional[str]:
    m = re.search(rf"^{re.escape(key)}:\s*[\"']?([^\"'\r\n]+)[\"']?\s*$", md_text[:2000], re.MULTILINE)
    return m.group(1).strip() if m else None


def backfill_file(path: Path, client: X.SecClient) -> Dict[str, object]:
    """Backfill one file. Returns {'status': 'appended'|'no_exhibits'|'already'|'error', ...}."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    if X.has_exhibits(text):
        return {"status": "already"}
    cik = read_frontmatter_field(text, "cik")
    accession = read_frontmatter_field(text, "accession_number")
    if not cik or not accession:
        return {"status": "error", "error": "frontmatter lacks cik / accession_number"}
    try:
        sections = X.build_exhibit_sections(client, cik, accession)
    except X.SecFetchError as e:
        return {"status": "error", "error": str(e)}
    if not sections:
        refs = X.parse_index_html(client.get_text(X.index_url(cik, accession)))
        seen = sorted({r.doc_type for r in refs if r.doc_type and r.doc_type != "6-K" and r.doc_type != "8-K"})
        return {"status": "no_exhibits", "document_types": seen}
    new_text = X.append_exhibits(text, sections)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)
    return {"status": "appended", "exhibits": [t for t, _ in sections]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill EX-99.x exhibits into existing 6-K / 8-K corpus files.")
    ap.add_argument("paths", nargs="*", help="Specific corpus files (default: every 6-K / 8-K file)")
    ap.add_argument("--forms", nargs="+", default=list(X.FORMS_WITH_EXHIBITS))
    ap.add_argument("--tickers", nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=None, help="Process at most N files (testing)")
    ap.add_argument("--report-json", type=str, default=None, help="Write a per-file JSON report here")
    args = ap.parse_args()

    files: List[Path] = [Path(p) for p in args.paths]
    if not files:
        for form in args.forms:
            files.extend(sorted(CORPUS_DIR.glob(f"*/{form}/*.md")))
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        files = [p for p in files if p.parent.parent.name in wanted]
    if args.limit:
        files = files[: args.limit]

    client = X.SecClient()
    results: Dict[str, Dict[str, object]] = {}
    counts: Counter = Counter()
    for n, path in enumerate(files, 1):
        res = backfill_file(path, client)
        results[path.name] = res
        counts[str(res["status"])] += 1
        if res["status"] == "error":
            print(f"[{n}/{len(files)}] ERROR {path.name}: {res['error']}")
        elif n % 50 == 0:
            print(f"[{n}/{len(files)}] {dict(counts)} (network requests: {client.network_requests})")

    print(f"Done: {dict(counts)} of {len(files)} files; network requests: {client.network_requests}")
    if args.report_json:
        Path(args.report_json).write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
