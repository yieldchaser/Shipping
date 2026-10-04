"""
export_broker_voice_to_corpus.py
Exports Fearnleys weekly desk comments from data/derived/fearnleys_broker_comments.csv
into individual, clean, structured Markdown files in corpus/01-brokers/fearnleys/voice/<desk>/<year>/<date>_<slug>.md

Features:
- Segregated folder-wise by desk and publication year.
- Full YAML frontmatter with desk, date, year, week, comment type, and unique record ID.
- Clean text formatting: normalizes smart quotes, dashes, whitespace, and paragraph breaks.
- Incremental and idempotent (skips unchanged files).
- Callable from CLI or imported directly into daily_fearnleys_sync.py.
"""

import os
import re
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

BASE_DIR = Path(__file__).resolve().parents[2]
DERIVED_CSV = BASE_DIR / "data" / "derived" / "fearnleys_broker_comments.csv"
VOICE_CORPUS_ROOT = BASE_DIR / "corpus" / "01-brokers" / "fearnleys" / "voice"

# Desk mapping for weekly desk commentary
DESK_MAPPING = {
    "Capesize Weekly Comment": {
        "desk": "Capesize",
        "slug": "capesize",
        "sector": "Dry Bulk"
    },
    "Panamax Weekly Comment": {
        "desk": "Panamax",
        "slug": "panamax",
        "sector": "Dry Bulk"
    },
    "Supramax Weekly Comment": {
        "desk": "Supramax",
        "slug": "supramax",
        "sector": "Dry Bulk"
    },
    "VLCC Weekly Comment": {
        "desk": "VLCC",
        "slug": "vlcc",
        "sector": "Crude Tankers"
    },
    "Suezmax Weekly Comment": {
        "desk": "Suezmax",
        "slug": "suezmax",
        "sector": "Crude Tankers"
    },
    "Aframax Weekly Comment": {
        "desk": "Aframax",
        "slug": "aframax",
        "sector": "Crude Tankers"
    },
    "LNG Market Report": {
        "desk": "LNG",
        "slug": "lng",
        "sector": "Gas Carriers"
    },
    "Gas Market Weekly Comment - Eastern Market": {
        "desk": "LPG Eastern",
        "slug": "lpg_eastern",
        "sector": "Gas Carriers"
    },
    "Gas Market Weekly Comment - Western Market": {
        "desk": "LPG Western",
        "slug": "lpg_western",
        "sector": "Gas Carriers"
    },
    "SnP Weekly Comment": {
        "desk": "S&P",
        "slug": "snp",
        "sector": "Sale & Purchase"
    },
    "Chartering Weekly Comment": {
        "desk": "Chartering",
        "slug": "chartering",
        "sector": "Period Chartering"
    },
    "Gas Market Report": {
        "desk": "Gas",
        "slug": "gas",
        "sector": "Gas Carriers"
    },
    "Daily BLPG Report": {
        "desk": "BLPG",
        "slug": "blpg",
        "sector": "Gas Carriers"
    }
}


def clean_text_for_markdown(raw_text: str) -> str:
    """Cleans up text, normalizes characters, and restores clean paragraph breaks."""
    if not raw_text or not isinstance(raw_text, str):
        return ""

    text = raw_text.strip()
    
    # Replace common unicode replacement characters or garbled entities
    text = text.replace("\ufffd", " - ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")

    # If text already has newline breaks, preserve them
    if "\n" in text:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        return "\n\n".join(paragraphs)

    # In flattened text from CSV, detect section subheaders like "North Sea", "US Gulf", "Meg", etc.
    # Look for capitalized sub-headers followed by capital letters or sentence starts
    subheaders = [
        "North Sea", "NSEA", "Baltic", "Med", "Black Sea", "West Africa", "WAFR",
        "US Gulf", "USG", "Caribs", "MEG", "East of Suez", "Pacific", "Atlantic",
        "Continent", "Far East", "SPORE", "UKC"
    ]
    for sh in subheaders:
        # Match pattern where subheader appears mid-text without leading period
        pattern = re.compile(rf'(?<=[.!?])\s+({re.escape(sh)}\b)', re.IGNORECASE)
        text = pattern.sub(r'\n\n**\1**\n\n', text)
        
        pattern_colon = re.compile(rf'\b({re.escape(sh)}:)', re.IGNORECASE)
        text = pattern_colon.sub(r'\n\n**\1**', text)

    # Clean double spaces
    text = re.sub(r' {2,}', ' ', text)
    # Clean excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def export_comment_to_md(
    comment_id: str,
    comment_date: str,
    comment_type: str,
    comment_subtype: str,
    raw_text: str,
    overwrite: bool = False
) -> Optional[Path]:
    """Formats and writes a single comment to its destination markdown file."""
    if comment_type not in DESK_MAPPING:
        return None

    mapping = DESK_MAPPING[comment_type]
    desk_name = mapping["desk"]
    desk_slug = mapping["slug"]
    sector_name = mapping["sector"]

    # Parse date to derive year and ISO week
    try:
        dt = datetime.strptime(comment_date[:10], "%Y-%m-%d")
        year_str = str(dt.year)
        week_num = dt.isocalendar()[1]
    except Exception:
        year_str = "unknown"
        week_num = 0

    dest_dir = VOICE_CORPUS_ROOT / desk_slug / year_str
    dest_dir.mkdir(parents=True, exist_ok=True)

    # File naming: <date>_<desk_slug>.md (or with short ID suffix if needed)
    base_stem = f"{comment_date[:10]}_{desk_slug}_weekly_comment"
    dest_file = dest_dir / f"{base_stem}.md"

    # If file exists with different ID, append short hash to avoid collision
    if dest_file.exists() and not overwrite:
        try:
            with open(dest_file, "r", encoding="utf-8") as existing:
                content = existing.read()
                if f'id: "{comment_id}"' in content or f"id: '{comment_id}'" in content:
                    return dest_file  # Already written with identical ID
        except Exception:
            pass
        # Collision with distinct comment: append short ID
        short_id = str(comment_id).replace("-", "")[:8]
        dest_file = dest_dir / f"{base_stem}_{short_id}.md"
        if dest_file.exists() and not overwrite:
            return dest_file

    body_text = clean_text_for_markdown(raw_text)

    md_content = f"""---
id: "{comment_id}"
source: "Fearnleys"
desk: "{desk_name}"
sector: "{sector_name}"
comment_type: "{comment_type}"
comment_subtype: "{comment_subtype}"
date: "{comment_date[:10]}"
year: {dt.year if year_str != 'unknown' else 'null'}
week: {week_num}
title: "Fearnleys {desk_name} Weekly Comment - {comment_date[:10]}"
---

# Fearnleys {desk_name} Weekly Comment ({comment_date[:10]})

- **Source:** Fearnleys Shipbrokers (Hasura API)
- **Desk:** {desk_name} ({sector_name})
- **Publication Date:** {comment_date[:10]} (Week {week_num})
- **Comment Type:** {comment_type}
- **Record ID:** `{comment_id}`

---

## Market Commentary

{body_text}
"""

    with open(dest_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    return dest_file


MANIFEST_PATH = VOICE_CORPUS_ROOT / ".voice_manifest.json"


def load_manifest() -> set:
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    # Scan existing files once to initialize
    seen = set()
    if VOICE_CORPUS_ROOT.exists():
        for p in VOICE_CORPUS_ROOT.rglob("*.md"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    head = f.read(400)
                    m = re.search(r'id:\s*["\']([^"\']+)["\']', head)
                    if m:
                        seen.add(m.group(1))
            except Exception:
                pass
    save_manifest(seen)
    return seen


def save_manifest(ids: set):
    try:
        VOICE_CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(list(ids)), f)
    except Exception:
        pass


def export_all_voice_comments(overwrite: bool = False) -> Dict[str, Any]:
    """Processes all weekly desk comments from CSV into corpus markdown files."""
    if not DERIVED_CSV.exists():
        raise FileNotFoundError(f"Missing comments CSV at {DERIVED_CSV}")

    manifest = load_manifest() if not overwrite else set()

    stats = {
        "total_read": 0,
        "matched_desk_comments": 0,
        "written": 0,
        "by_desk": {},
        "by_year": {}
    }

    newly_added = False

    with open(DERIVED_CSV, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["total_read"] += 1
            c_type = (row.get("comment_type") or "").strip()
            if c_type in DESK_MAPPING:
                stats["matched_desk_comments"] += 1
                c_id = str(row.get("id") or "").strip()
                c_date = str(row.get("date") or "").strip()
                c_subtype = str(row.get("comment_subtype") or "").strip()
                c_text = str(row.get("text") or "").strip()

                desk = DESK_MAPPING[c_type]["desk"]
                yr = c_date[:4] if len(c_date) >= 4 else "unknown"

                if c_id in manifest and not overwrite:
                    stats["written"] += 1
                    stats["by_desk"][desk] = stats["by_desk"].get(desk, 0) + 1
                    stats["by_year"][yr] = stats["by_year"].get(yr, 0) + 1
                    continue

                out_file = export_comment_to_md(
                    comment_id=c_id,
                    comment_date=c_date,
                    comment_type=c_type,
                    comment_subtype=c_subtype,
                    raw_text=c_text,
                    overwrite=overwrite
                )
                if out_file:
                    stats["written"] += 1
                    manifest.add(c_id)
                    newly_added = True
                    stats["by_desk"][desk] = stats["by_desk"].get(desk, 0) + 1
                    stats["by_year"][yr] = stats["by_year"].get(yr, 0) + 1

    if newly_added:
        save_manifest(manifest)

    return stats


def main():
    print("=" * 80)
    print("EXPORTING FEARNLEYS BROKER VOICE DESK COMMENTS TO CORPUS DIRECTORY")
    print("=" * 80)
    stats = export_all_voice_comments(overwrite=False)
    print(f"Total rows read: {stats['total_read']}")
    print(f"Weekly desk comments matched: {stats['matched_desk_comments']}")
    print(f"Files written/verified in corpus: {stats['written']}")
    print("\nBreakdown by Desk:")
    for desk, cnt in sorted(stats["by_desk"].items()):
        print(f"  - {desk:15s}: {cnt:5d} markdown files")
    print("\nBreakdown by Year:")
    for yr, cnt in sorted(stats["by_year"].items()):
        print(f"  - {yr:4s}: {cnt:5d} markdown files")
    print("=" * 80)


if __name__ == "__main__":
    main()
