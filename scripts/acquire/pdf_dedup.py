"""Byte-identical PDF guard for the fetchers.

Two crawlers read the same Hellenic Shipping News shipbroker category under different naming schemes:
scripts/acquire/sync_hellenic_live.py (report_ingest.yml, broker names: star_asia_2026_W41_Market-Report-Week-41.pdf)
and scripts/scrapers/fetch_hsn_shipbrokers.py (broker_reports_weekly.yml, dated slugs: star_asia_12_10_2026_...).
Without this check each saved its own copy of the same issue (Star Asia W41/W42, Oct 2026).

identical_copy(folder, data) returns the path of a PDF already holding these exact bytes: any *.pdf in the
destination folder, or the name recorded for this hash in data/derived/pdf_md5_index.json (which covers PDFs that
are not checked out on a CI runner). The caller then skips the write.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "data" / "derived" / "pdf_md5_index.json"


def _index() -> dict:
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except Exception:
        return {}


def identical_copy(folder: Path, data: bytes) -> Path | None:
    h = hashlib.md5(data).hexdigest()
    if folder.is_dir():
        for p in folder.glob("*.pdf"):
            try:
                if p.stat().st_size == len(data) and hashlib.md5(p.read_bytes()).hexdigest() == h:
                    return p
            except OSError:
                continue
    rel = _index().get(h)
    return ROOT / rel if rel else None
