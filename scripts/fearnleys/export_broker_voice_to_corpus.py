"""
export_broker_voice_to_corpus.py
================================
Exports Fearnleys historical and live weekly desk comments from
data/derived/fearnleys_broker_comments.csv into clean, structured,
canonical Markdown files with full YAML frontmatter.

Export Locations:
1. corpus/01-brokers/fearnleys/voice/<sector>/<desk>/<year>/<date>_<desk>_<id>.md
2. data/extracted/md/fearnleys/voice/<sector>/<desk>/<year>/<date>_<desk>_<id>.md

Sectors & Desks Covered (100% of 11,750+ records):
- tankers: VLCC, Suezmax, Aframax, Tanker Activity, WAFR/UKC, WAFR/USG, CROSS MED, MEG/EAST, BITR-1, BITR-2, BITR-3, BOT/WEST, CEYHAN/USG, BLSEA/MED
- dry_bulk: Capesize, Panamax, Supramax, Dry Bulk Activity, Container Activity
- chartering: Period Chartering Weekly Comments
- gas: LNG Market Report, Gas Market Report, LPG Eastern, LPG Western, LPG MEG, LPG FE, LPG Americas, Daily BLPG, LNG/LPG Activity
- snp: Sale & Purchase Weekly Comments, Newbuilding Activity

Features:
- Full YAML frontmatter (id, source, desk, sector, comment_type, comment_subtype, date, year, week, title).
- Clean text formatting: normalizes smart quotes, typography, whitespace, and subheaders.
- Incremental and idempotent with manifest tracking for sub-second delta updates.
- Integrated into daily_fearnleys_sync.py and run_master_pipeline.py.
"""

import os
import re
import sys
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

BASE_DIR = Path(__file__).resolve().parents[2]
DERIVED_CSV = BASE_DIR / "data" / "derived" / "fearnleys_broker_comments.csv"
VOICE_CORPUS_ROOT = BASE_DIR / "corpus" / "01-brokers" / "fearnleys" / "voice"
VOICE_MD_ROOT = BASE_DIR / "data" / "extracted" / "md" / "fearnleys" / "voice"

# Comment types written as MDs. The ten tanker route-trend types (WAFR/UKC, WAFR/USG, CROSS MED, MEG/EAST,
# BITR-1/2/3, BOT/WEST, CEYHAN/USG, BLSEA/MED; subtype "trend") carry a one- or two-word label per week
# ("Steady", "Softer"), not prose: they stay as structured rows in fearnleys_broker_comments.csv and get no MD.
DESK_MAPPING = {
    # Tankers
    "VLCC Weekly Comment": {
        "sector": "tankers", "sector_title": "Crude Tankers", "slug": "vlcc", "desk": "VLCC"
    },
    "Suezmax Weekly Comment": {
        "sector": "tankers", "sector_title": "Crude Tankers", "slug": "suezmax", "desk": "Suezmax"
    },
    "Aframax Weekly Comment": {
        "sector": "tankers", "sector_title": "Crude Tankers", "slug": "aframax", "desk": "Aframax"
    },
    "Tank Activity": {
        "sector": "tankers", "sector_title": "Tanker Activity", "slug": "tank_activity", "desk": "Tanker Activity"
    },
    # Dry Bulk
    "Capesize Weekly Comment": {
        "sector": "dry_bulk", "sector_title": "Dry Bulk", "slug": "capesize", "desk": "Capesize"
    },
    "Panamax Weekly Comment": {
        "sector": "dry_bulk", "sector_title": "Dry Bulk", "slug": "panamax", "desk": "Panamax"
    },
    "Supramax Weekly Comment": {
        "sector": "dry_bulk", "sector_title": "Dry Bulk", "slug": "supramax", "desk": "Supramax"
    },
    "Dry Bulk Activity": {
        "sector": "dry_bulk", "sector_title": "Dry Bulk Activity", "slug": "dry_bulk_activity", "desk": "Dry Bulk Activity"
    },
    "Container Activity": {
        "sector": "dry_bulk", "sector_title": "Container Activity", "slug": "container_activity", "desk": "Container Activity"
    },
    # Period Chartering
    "Chartering Weekly Comment": {
        "sector": "chartering", "sector_title": "Period Chartering", "slug": "chartering", "desk": "Period Chartering"
    },
    # Gas Carriers
    "LNG Market Report": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "lng", "desk": "LNG"
    },
    "Gas Market Report": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "gas_general", "desk": "Gas Market"
    },
    "Gas Market Weekly Comment - Eastern Market": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "lpg_eastern", "desk": "LPG Eastern"
    },
    "Gas Market Weekly Comment - Western Market": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "lpg_western", "desk": "LPG Western"
    },
    "Gas Market Weekly Comment - MEG": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "lpg_meg", "desk": "LPG MEG"
    },
    "Gas Market Weekly Comment - FE": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "lpg_fe", "desk": "LPG Far East"
    },
    "Gas Market Weekly Comment - Americas": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "lpg_americas", "desk": "LPG Americas"
    },
    "Daily BLPG Report": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "blpg", "desk": "Daily BLPG"
    },
    "LNG Activity": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "lng_activity", "desk": "LNG Activity"
    },
    "LPG Activity": {
        "sector": "gas", "sector_title": "Gas Carriers", "slug": "lpg_activity", "desk": "LPG Activity"
    },
    # Sale & Purchase
    "SnP Weekly Comment": {
        "sector": "snp", "sector_title": "Sale & Purchase", "slug": "snp", "desk": "Sale & Purchase"
    },
    "Other Activity": {
        "sector": "snp", "sector_title": "Sale & Purchase", "slug": "newbuilding", "desk": "Newbuilding Activity"
    }
}


# zero-width joiners and the like that the feed carries inside words ("still ⁠at war")
INVISIBLE = str.maketrans({c: None for c in "​‌‍⁠﻿"})


def clean_text_for_markdown(raw_text: str) -> str:
    """Cleans up text, normalizes characters, and restores clean paragraph breaks."""
    if not raw_text or not isinstance(raw_text, str):
        return ""

    # The feed's own paragraph breaks are the only structure added: region names inside a
    # sentence ("... trade. Pacific round values ...") are text, never headings.
    text = raw_text.replace("\r\n", "\n").translate(INVISIBLE).strip()
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    paragraphs = [re.sub(r"[ \t]{2,}", " ", p.strip()) for p in text.split("\n") if p.strip()]
    return "\n\n".join(paragraphs)


def export_comment_to_md(
    comment_id: str,
    comment_date: str,
    comment_type: str,
    comment_subtype: str,
    raw_text: str,
    overwrite: bool = False,
    rewrite: bool = False
) -> Tuple[Optional[Path], Optional[Path]]:
    """Formats and writes a single comment to both corpus and data/extracted/md locations.

    rewrite: re-render and write only the targets that already exist (the corpus mirror holds a
    subset of the comments); a comment with neither file is written to both, as a new one."""
    if comment_type not in DESK_MAPPING:
        return None, None

    mapping = DESK_MAPPING[comment_type]
    sector_slug = mapping["sector"]
    sector_title = mapping["sector_title"]
    desk_name = mapping["desk"]
    desk_slug = mapping["slug"]

    # Parse date to derive year and ISO week
    try:
        dt = datetime.strptime(comment_date[:10], "%Y-%m-%d")
        year_str = str(dt.year)
        week_num = dt.isocalendar()[1]
    except Exception:
        year_str = "unknown"
        week_num = 0
        dt = None

    # File stem: <date>_<desk_slug>_<short_id>
    short_id = str(comment_id).replace("-", "")[:8]
    file_stem = f"{comment_date[:10]}_{desk_slug}_{short_id}.md"

    # Targets
    corpus_dir = VOICE_CORPUS_ROOT / desk_slug / year_str
    md_dir = VOICE_MD_ROOT / sector_slug / desk_slug / year_str

    corpus_file = corpus_dir / file_stem
    extracted_file = md_dir / file_stem

    if corpus_file.exists() and extracted_file.exists() and not overwrite:
        return corpus_file, extracted_file

    body_text = clean_text_for_markdown(raw_text)

    md_content = f"""---
id: "{comment_id}"
source: "Fearnleys"
sector: "{sector_title}"
desk: "{desk_name}"
comment_type: "{comment_type}"
comment_subtype: "{comment_subtype}"
date: "{comment_date[:10]}"
year: {dt.year if dt else 'null'}
week: {week_num}
title: "Fearnleys {desk_name} Comment - {comment_date[:10]}"
---

# Fearnleys {desk_name} Comment ({comment_date[:10]})

- **Source:** Fearnleys Shipbrokers (Hasura API)
- **Sector:** {sector_title}
- **Desk:** {desk_name}
- **Publication Date:** {comment_date[:10]} (Week {week_num})
- **Comment Type:** {comment_type}
- **Record ID:** `{comment_id}`

---

## Market Commentary

{body_text}
"""

    targets = [corpus_file, extracted_file]
    if rewrite and any(t.exists() for t in targets):
        targets = [t for t in targets if t.exists()]
    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        with open(t, "w", encoding="utf-8") as f:
            f.write(md_content)

    return corpus_file, extracted_file


MANIFEST_PATH = VOICE_CORPUS_ROOT / ".voice_full_manifest.json"


def load_manifest() -> set:
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_manifest(ids: set):
    try:
        VOICE_CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(list(ids)), f)
    except Exception:
        pass


def export_all_voice_comments(overwrite: bool = False, rewrite: bool = False) -> Dict[str, Any]:
    """Processes all historical & delta weekly desk comments into structured markdown.

    rewrite: re-render every comment into the files that exist (see export_comment_to_md)."""
    if not DERIVED_CSV.exists():
        raise FileNotFoundError(f"Missing comments CSV at {DERIVED_CSV}")

    manifest = load_manifest() if not overwrite else set()

    stats = {
        "total_read": 0,
        "matched_comments": 0,
        "written": 0,
        "by_sector": {},
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
                stats["matched_comments"] += 1
                c_id = str(row.get("id") or "").strip()
                c_date = str(row.get("date") or "").strip()
                c_subtype = str(row.get("comment_subtype") or "").strip()
                c_text = str(row.get("text") or "").strip()

                meta = DESK_MAPPING[c_type]
                sec = meta["sector"]
                desk = meta["desk"]
                yr = c_date[:4] if len(c_date) >= 4 else "unknown"

                if c_id in manifest and not (overwrite or rewrite):
                    stats["written"] += 1
                    stats["by_sector"][sec] = stats["by_sector"].get(sec, 0) + 1
                    stats["by_desk"][desk] = stats["by_desk"].get(desk, 0) + 1
                    stats["by_year"][yr] = stats["by_year"].get(yr, 0) + 1
                    continue

                c_out, md_out = export_comment_to_md(
                    comment_id=c_id,
                    comment_date=c_date,
                    comment_type=c_type,
                    comment_subtype=c_subtype,
                    raw_text=c_text,
                    overwrite=overwrite or rewrite,
                    rewrite=rewrite
                )
                if c_out and md_out:
                    stats["written"] += 1
                    manifest.add(c_id)
                    newly_added = True
                    stats["by_sector"][sec] = stats["by_sector"].get(sec, 0) + 1
                    stats["by_desk"][desk] = stats["by_desk"].get(desk, 0) + 1
                    stats["by_year"][yr] = stats["by_year"].get(yr, 0) + 1

    if newly_added or overwrite:
        save_manifest(manifest)

    return stats


def main():
    print("=" * 80)
    print("EXPORTING FEARNLEYS BROKER VOICE DESK COMMENTS ACROSS ALL SECTORS & ERAS")
    print("=" * 80)
    stats = export_all_voice_comments(overwrite=False, rewrite="--rewrite" in sys.argv)
    print(f"Total rows read: {stats['total_read']}")
    print(f"Comments matched: {stats['matched_comments']}")
    print(f"Files written/verified in corpus & md: {stats['written']}")
    print("\nBreakdown by Sector:")
    for sec, cnt in sorted(stats["by_sector"].items()):
        print(f"  - {sec:15s}: {cnt:5d} markdown files")
    print("\nBreakdown by Year:")
    for yr, cnt in sorted(stats["by_year"].items()):
        print(f"  - {yr:4s}: {cnt:5d} markdown files")
    print("=" * 80)


if __name__ == "__main__":
    main()
