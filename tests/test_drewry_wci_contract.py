#!/usr/bin/env python3
"""
tests/test_drewry_wci_contract.py
=================================
Contract test for the shipped Drewry WCI history file.

``scripts/scrapers/fetch_drewry_wci.py`` merges every fetched print into
``data/indices/drewry_wci_historical.csv`` with a DATE-only dedupe (last row
wins). Because the publisher assesses the index on a THURSDAY, a misparsed
date could otherwise overwrite a real print without leaving a trace.

These invariants were measured on the shipped file (2026-10-01) and are the
ones that make the file safe to load:
  1. every date is a Thursday,
  2. dates are unique and strictly increasing,
  3. the five core lanes are never blank,
  4. ``rotterdam_shanghai`` MAY be blank - the publisher stops printing its
     level ("hovered around previous week's level") on 59 of the 121 rows,
     verified against each capture's own page; a blank there is faithful.
"""

import csv
import datetime as dt
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WCI_CSV = REPO_ROOT / "data" / "indices" / "drewry_wci_historical.csv"

CORE_LANES = ["composite_index", "shanghai_rotterdam", "shanghai_genoa",
              "shanghai_la", "shanghai_ny"]
THURSDAY = 3


def _rows():
    if not WCI_CSV.exists():
        pytest.skip(f"{WCI_CSV} not present")
    with WCI_CSV.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_header_is_canonical():
    rows = _rows()
    assert rows, "the WCI history file is empty"
    assert list(rows[0].keys()) == ["date"] + CORE_LANES + ["rotterdam_shanghai"]


def test_every_date_is_a_thursday():
    """The WCI is assessed on Thursdays; anything else is a parse artefact."""
    bad = []
    for r in _rows():
        try:
            d = dt.date.fromisoformat(r["date"])
        except ValueError:
            bad.append(r["date"])
            continue
        if d.weekday() != THURSDAY:
            bad.append(r["date"])
    assert not bad, f"{len(bad)} non-Thursday date(s) in the WCI file: {bad[:8]}"


def test_dates_are_unique_and_strictly_increasing():
    dates = [r["date"] for r in _rows()]
    assert len(dates) == len(set(dates)), "duplicate dates in the WCI file"
    assert dates == sorted(dates), "dates are not sorted ascending"


def test_core_lanes_are_never_blank():
    blank = [(r["date"], c) for r in _rows() for c in CORE_LANES if not (r.get(c) or "").strip()]
    assert not blank, f"{len(blank)} blank core cell(s): {blank[:8]}"
