#!/usr/bin/env python3
"""
scripts/extract/sync_digests.py
===============================
Synchronizes clean extracted Markdown reports to corpus/01-brokers/_digests.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
digests_dir = ROOT / "corpus" / "01-brokers" / "_digests"
extracted_dir = ROOT / "data" / "extracted" / "md"

# 1. Update fearnleys week 40 in _digests with the clean extracted markdown
w40_extracted = extracted_dir / "fearnleys" / "2026" / "fearnleys_01_10_2026_fearnleys_week_40_2026.md"
w40_digest = digests_dir / "fearnleys" / "2026" / "fearnleys_01_10_2026_fearnleys_week_40_2026.md"

if w40_extracted.exists():
    w40_digest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(w40_extracted, w40_digest)
    print(f"Updated {w40_digest} with clean extracted markdown!")

# 2. Update agora week 39 in _digests if exists
w39_agora_extracted = extracted_dir / "agora" / "2026" / "agora_30_09_2026_agora_shipbroking_corporation_snapshot_of_commercial_indicator.md"
w39_agora_digest = digests_dir / "agora" / "2026" / "agora_30_09_2026_agora_shipbroking_corporation_snapshot_of_commercial_indicator.md"

if w39_agora_extracted.exists():
    w39_agora_digest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(w39_agora_extracted, w39_agora_digest)
    print(f"Updated {w39_agora_digest} with clean extracted markdown!")

print("Digest sync complete.")
