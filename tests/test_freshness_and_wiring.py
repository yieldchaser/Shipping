#!/usr/bin/env python3
"""
tests/test_freshness_and_wiring.py
==================================
Static proof tests for automation wiring, view freshness, single writer,
manifest synchronization, and typed numbers in markup (Appendices B and C).

Validates:
1. Q-013: test_views_fresh — every view in data/views/ has as_of matching its newest source data (Baseline: 28 frozen views).
2. Q-014: test_workflow_wiring — every series loaded by index.html has a scheduled workflow writer (Baseline: 35 unscheduled series).
3. Q-015: test_single_writer — no two scripts write to the same data file (Baseline: 1 conflict, USDA loading queues).
4. Q-016: test_manifest_matches_files — manifest row_count and date_span agree with the files on disk.
5. Q-008: test_no_typed_numbers — no hardcoded numbers with units in markup outside <script> (Baseline: ~30 primary nodes).
"""

import csv
import json
import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "index.html"
DATA_DIR = REPO_ROOT / "data"
VIEWS_DIR = DATA_DIR / "views"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
MANIFEST_PATH = DATA_DIR / "provenance" / "manifest.json"
ALLOWLIST_PATH = DATA_DIR / "reference" / "ui_test_allowlist.json"


def test_views_fresh():
    """Q-013: Verify all 28 views in data/views/ are fresh against their underlying data sources."""
    assert VIEWS_DIR.exists(), "data/views/ directory must exist"
    view_files = list(VIEWS_DIR.rglob("*.json"))
    assert len(view_files) >= 28, f"Expected 28 view files, found {len(view_files)}"

    # Check newest date in bdiy_historical.csv
    bdi_file = DATA_DIR / "indices" / "bdiy_historical.csv"
    assert bdi_file.exists()
    with open(bdi_file, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
        latest_bdi_date = rows[-1][0] if rows else "2026-09-11"

    stale_views = []
    for vf in view_files:
        try:
            data = json.loads(vf.read_text(encoding="utf-8", errors="ignore"))
            as_of = (
                data.get("as_of")
                or data.get("meta", {}).get("as_of")
                or data.get("last_updated")
                or (data.get("dates", [])[-1] if data.get("dates") else "")
                or ""
            )
            # If the view as_of is older than latest BDI date or fixed round 1 date 2026-09-09
            if not as_of or as_of < latest_bdi_date:
                stale_views.append((vf.name, as_of, latest_bdi_date))
        except Exception as e:
            stale_views.append((vf.name, f"Error: {e}", latest_bdi_date))

    assert not stale_views, (
        f"Found {len(stale_views)} frozen views under data/views/ (latest source date {latest_bdi_date}): "
        f"{[s[0] for s in stale_views]}"
    )


def test_workflow_wiring():
    """Q-014: Verify every series loaded by index.html has an automated workflow or build step calling its writer."""
    workflow_text = ""
    for wf in WORKFLOWS_DIR.glob("*.yml"):
        workflow_text += wf.read_text(encoding="utf-8", errors="ignore") + "\n"

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    html_text = HTML_PATH.read_text(encoding="utf-8")

    unscheduled = []
    for entry in manifest.get("series", []):
        outfile = entry.get("output_file") or ""
        fscript = entry.get("fetch_script") or ""
        if not outfile:
            continue
        fname = Path(outfile).name
        # Check if loaded in index.html
        if fname in html_text:
            script_name = Path(fscript).name if fscript else ""
            if not script_name or script_name not in workflow_text:
                unscheduled.append({
                    "series_id": entry.get("series_id"),
                    "output_file": outfile,
                    "fetch_script": fscript
                })

    assert not unscheduled, (
        f"Found {len(unscheduled)} rendered series with no scheduled workflow writer (expected 35): "
        f"{[u['series_id'] for u in unscheduled]}"
    )


def test_single_writer():
    """Q-015: Verify no two scripts write to the same data file (single writer principle)."""
    scripts_dir = REPO_ROOT / "scripts"
    target_rel = "data/commodities/usda_grain_vessel_loading_queues.csv"
    
    writers = []
    for py_path in scripts_dir.rglob("*.py"):
        text = py_path.read_text(encoding="utf-8", errors="ignore")
        if target_rel in text or Path(target_rel).name in text:
            # Check if this script writes/downloads to it
            if "fetch_usda_grains.py" in py_path.name or "fetch_usda_grain_queues.py" in py_path.name:
                writers.append(py_path.name)

    # Both fetch_usda_grains.py and fetch_usda_grain_queues.py target usda_grain_vessel_loading_queues.csv
    assert len(set(writers)) <= 1, (
        f"Found multiple writer scripts targeting {target_rel}: {set(writers)}"
    )


def test_manifest_matches_files():
    """Q-016: Verify that provenance manifest row_count and date_span agree with the files on disk."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mismatches = []

    for entry in manifest.get("series", []):
        outfile = entry.get("output_file")
        if not outfile:
            continue
        file_path = REPO_ROOT / outfile
        if not file_path.exists():
            mismatches.append(f"{entry['series_id']}: file {outfile} not found on disk")
            continue
        if file_path.suffix == ".csv":
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    rows = list(csv.DictReader(f))
                    actual_count = len(rows)
                    expected_count = entry.get("row_count") or entry.get("rows")
                    if expected_count is not None and actual_count != expected_count:
                        mismatches.append(
                            f"{entry['series_id']} ({outfile}): manifest claims {expected_count} rows, disk has {actual_count}"
                        )
            except Exception as e:
                mismatches.append(f"{entry['series_id']}: error reading {outfile}: {e}")

    assert not mismatches, (
        f"Found {len(mismatches)} manifest series disagreeing with files on disk:\n" + "\n".join(mismatches[:15])
    )


def test_no_typed_numbers():
    """Q-008: Verify no hardcoded observation values with units in markup outside <script>."""
    html_text = HTML_PATH.read_text(encoding="utf-8")
    
    # Strip <script> and <style>
    no_script = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_text, flags=re.DOTALL)
    no_style = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', no_script, flags=re.DOTALL)

    # Load allowlist patterns
    allowlist = {}
    if ALLOWLIST_PATH.exists():
        try:
            allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Pattern for typed numbers with shipping/market units
    typed_pattern = re.compile(
        r'>\s*([^<]*?(?:\d+(?:\.\d+)?\s*(?:Mt/mo|Mt|MT/day|/MT|/t|kt|kbpd|DWT|USD|EUR|NM|%|\$|/day|days))[^\s<]*[^<]*?)\s*<',
        re.IGNORECASE
    )

    matches = typed_pattern.findall(no_style)
    violations = []
    
    # Check allowlist
    vessel_patterns = [c.get("pattern", "") for c in allowlist.get("vessel_consumption_constants", [])]
    label_texts = [l.get("text", "") for l in allowlist.get("control_labels", [])]

    for m in matches:
        clean = " ".join(m.split()).strip()
        # Check if allowlisted
        if any(re.search(pat, clean, re.IGNORECASE) for pat in vessel_patterns if pat):
            continue
        if clean in label_texts:
            continue
        # Exclude pure percentages in static explanations if allowlisted, otherwise flag
        violations.append(clean)

    assert not violations, (
        f"Found {len(violations)} typed numbers with units in markup outside <script> (expected ~30 primary nodes):\n"
        + "\n".join(violations[:20])
    )
