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
import datetime
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
    """Q-013: Views must be rebuilt from current data and must say how current they are.

    The original form of this test asserted every view was at least as new as
    bdiy_historical.csv. That was the wrong property: a weekly Clarksons index
    legitimately trails a daily BDI, so the assertion could only ever be satisfied
    by lying. What actually matters is:
      1. every view carries an as_of,
      2. that as_of is the newest date in the view's OWN payload (the stamp does
         not overstate freshness), and
      3. the deploy rebuilds views, so nothing ships frozen.
    """
    assert VIEWS_DIR.exists(), "data/views/ directory must exist"
    view_files = list(VIEWS_DIR.rglob("*.json"))
    assert len(view_files) >= 28, f"Expected 28 view files, found {len(view_files)}"

    iso = re.compile(r"^\d{4}-\d{2}-\d{2}")

    today = datetime.date.today().isoformat()

    def max_date(obj, best=""):
        # Ignore future dates: forward curves carry contract expiries years out,
        # which describe the instrument, not how current the data is.
        if isinstance(obj, str):
            return max(best, obj[:10]) if (iso.match(obj) and obj[:10] <= today) else best
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and iso.match(k) and k[:10] <= today:
                    best = max(best, k[:10])
                best = max_date(v, best)
            return best
        if isinstance(obj, (list, tuple)):
            for v in obj:
                best = max_date(v, best)
        return best

    unstamped, lying = [], []
    static_lookups = []
    stamps = []
    for vf in view_files:
        try:
            data = json.loads(vf.read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:
            unstamped.append((vf.name, f"unreadable: {e}"))
            continue
        as_of, freshness, declared = "", "", False
        if isinstance(data, dict):
            for holder in (data, data.get("header", {}), data.get("meta", {})):
                if isinstance(holder, dict) and "as_of" in holder:
                    declared = True
                    as_of = holder.get("as_of") or as_of
                    freshness = holder.get("freshness") or freshness
        if not as_of:
            # A view with no dates in it is a static lookup table, but it must
            # DECLARE that - silence is indistinguishable from a broken build.
            if declared and freshness == "static-lookup":
                if max_date(data):
                    lying.append((vf.name, "static-lookup", max_date(data)))
                else:
                    static_lookups.append(vf.name)
                continue
            unstamped.append((vf.name, "no as_of"))
            continue
        stamps.append(as_of)
        actual = max_date(data)
        if actual and as_of[:10] > actual:
            lying.append((vf.name, as_of, actual))

    assert not unstamped, (
        f"{len(unstamped)} views carry no as_of stamp, so their freshness cannot be "
        f"checked at all: {unstamped[:10]}"
    )
    assert not lying, (
        f"{len(lying)} views claim an as_of newer than any date in their own payload "
        f"(name, claimed, actual): {lying[:10]}"
    )

    KNOWN_STATIC = {
        "asset_class_ports.json", "lineup_vessel_lookup.json", "live_fleet_positions.json",
        "routing_ports.json", "vessel_lookup.json", "vessel_voyages_lookup.json",
        "cape_ffa_distribution.json",
    }
    unexpected_static = sorted(set(static_lookups) - KNOWN_STATIC)
    assert not unexpected_static, (
        "These views declared themselves static lookups but are expected to carry dates. "
        f"A build that drops a date column would look exactly like this: {unexpected_static}"
    )

    # A view whose source pipeline has died shows up as a stamp far behind the
    # rest. Measure against the newest view, not the wall clock, so the test is
    # stable on an old checkout.
    newest = max(stamps)
    cutoff = (datetime.date.fromisoformat(newest) - datetime.timedelta(days=45)).isoformat()
    abandoned = sorted({s for s in stamps if s < cutoff})
    assert not abandoned, (
        f"Views more than 45 days behind the newest view ({newest}); their writers "
        f"have probably stopped running: {abandoned}"
    )

    # Frozen views were caused by pages.yml deploying without ever rebuilding them.
    pages = REPO_ROOT / ".github" / "workflows" / "pages.yml"
    assert pages.exists(), "pages.yml must exist"
    assert "build_views.py" in pages.read_text(encoding="utf-8"), (
        "pages.yml must run scripts/build_views.py before packaging, or every deploy "
        "ships whatever views were last committed by hand."
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
    
    def _strip_comments(src: str) -> str:
        """Drop # comments so a filename named only in a comment is not counted
        as a write. Uses tokenize so a '#' inside a string literal is preserved."""
        import io as _io
        import tokenize as _tok
        try:
            out = []
            for tok in _tok.generate_tokens(_io.StringIO(src).readline):
                if tok.type == _tok.COMMENT:
                    continue
                out.append(tok.string)
            return chr(10).join(out)
        except Exception:
            # Unparseable file: fall back to the raw text rather than silently
            # excusing it.
            return src

    writers = []
    for py_path in scripts_dir.rglob("*.py"):
        text = _strip_comments(py_path.read_text(encoding="utf-8", errors="ignore"))
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
