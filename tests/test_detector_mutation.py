"""
tests/test_detector_mutation.py

Mutation test suite for fabrication detector per Prompt 13B §C8.
Asserts that the detector fails on:
  1. Pilbara list-of-dicts observation shape (F1b)
  2. Indonesia constant-fill estimated annotation shape (F1)
  3. Bare-path allowlist format (fails allowlist parser)
  4. F3b unverified provenance in file with literal data despite network calls
"""

import ast
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "verify"))
import check_no_fabrication


def test_detector_catches_pilbara_list_of_dicts():
    """Pilbara mutation: list of dicts with date and numeric throughput/exports (F1b)."""
    code = '''
MONTHLY_UPDATES = [
    {"date": "2026-06-01", "port": "Hedland", "total_mt": 52.3, "iron_ore_mt": 51.7},
    {"date": "2026-07-01", "port": "Hedland", "total_mt": 45.0, "iron_ore_mt": 44.2},
    {"date": "2026-08-01", "port": "Hedland", "total_mt": 45.0, "iron_ore_mt": 44.2},
]
'''
    tree = ast.parse(code)
    violations = []
    allowlist = {}
    fpath = ROOT / "scripts" / "acquire" / "mock_pilbara.py"
    hit = check_no_fabrication.check_f1b_list_of_dicts(fpath, tree, code.splitlines(), allowlist, violations)
    assert hit is True
    assert len(violations) == 1
    assert "F1b" in violations[0]["violation"]


def test_detector_catches_indonesia_constant_annotation():
    """Indonesia mutation: constant annotation with ~% stamped into row subscript (F1)."""
    code = '''
def process_data(records):
    for row in records:
        row["top_destination_1"] = "India (~25-28%)"
'''
    tree = ast.parse(code)
    violations = []
    allowlist = {}
    fpath = ROOT / "scripts" / "acquire" / "mock_indonesia.py"
    hit = check_no_fabrication.check_f1_constant_annotations(fpath, tree, code.splitlines(), allowlist, violations)
    assert hit is True
    assert len(violations) == 1
    assert "F1" in violations[0]["violation"]


def test_detector_rejects_bare_path_allowlist(tmp_path):
    """Allowlist parser must reject bare paths missing line:rule."""
    allowlist_file = tmp_path / "fabrication_allowlist.txt"
    allowlist_file.write_text("scripts/legacy_script.py # bare path without line:rule\n", encoding="utf-8")
    orig_file = check_no_fabrication.ALLOWLIST_FILE
    try:
        check_no_fabrication.ALLOWLIST_FILE = allowlist_file
        with pytest.raises(ValueError) as exc_info:
            check_no_fabrication.load_allowlist()
        assert "Bare path" in str(exc_info.value) or "path:line:rule" in str(exc_info.value)
    finally:
        check_no_fabrication.ALLOWLIST_FILE = orig_file


def test_detector_f3b_network_does_not_exempt_literal_data():
    """F3b: network imports do not exempt files claiming verified provenance if literal data exists."""
    code = '''"""Official authentic verified data harvest."""
import requests

DATA = [
    {"date": "2026-01-01", "val1": 10.0, "val2": 20.0},
    {"date": "2026-02-01", "val1": 12.0, "val2": 22.0},
    {"date": "2026-03-01", "val1": 14.0, "val2": 24.0},
]
def fetch():
    requests.get("https://example.com")
'''
    tree = ast.parse(code)
    violations = []
    allowlist = {}
    fpath = ROOT / "scripts" / "acquire" / "mock_hybrid.py"
    has_literal = check_no_fabrication.check_f1b_list_of_dicts(fpath, tree, code.splitlines(), allowlist, violations)
    assert has_literal is True
    check_no_fabrication.check_f3_unverified_provenance(fpath, tree, code, code.splitlines(), allowlist, violations, has_literal)
    f3b_violations = [v for v in violations if "F3b" in v["violation"]]
    assert len(f3b_violations) >= 1
