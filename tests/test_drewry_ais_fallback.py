"""run_drewry_ais reads the Drewry AIS PDFs from the text layer only (rewritten 2026-10-12, 41dccf2cc2).

The earlier LlamaParse/plain-text fallback (extract_metrics_from_pages, _unwrap_plain_text) no longer exists;
these tests cover the tile reader that replaced it and, when the PDF is on disk, re-read one report and compare
it with the committed per-class KPI series row.
"""
import csv
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
import run_drewry_ais as A  # noqa: E402

PDF_NAME = "Drewry_AIS_Drybulk_Handysize_Week40_2026.pdf"


def test_tile_values_and_signs():
    assert A.tile_value("▼ 22.2%") == -22.2
    assert A.tile_value("▲ 3.3%") == 3.3
    assert A.tile_value("$866") == 866.0
    assert A.tile_value("87.5") == 87.5
    assert A.tile_value("$1,024") == 1024.0


def test_tile_captions_map_to_fields():
    assert A.TILES[A._caption("Current tonne-\nmiles index")] == "tonne_miles_index"
    assert A.TILES[A._caption("YoY change in tonne- miles index")] == "tonne_miles_yoy_pct"
    assert A.TILES[A._caption("per tonne price of  bunker at the end of the week")] == "bunker_price_usd_per_t"
    assert A.TILES[A._caption("MDWT change in tonnage at anchor (4- week moving average)")] == "anchor_4w_ma_change_mdwt"
    assert set(A.TILES.values()) <= set(A.FIELDS)


def test_filename_classification():
    assert A.classify_vessel(PDF_NAME) == "Drybulk_Handysize"
    assert A.classify_vessel("Drewry_AIS_Product_LR2_Week01_2026.pdf") == "Product_LR2"
    pub, week, year = A.parse_date_week_year(PDF_NAME, "Published on: 5 Oct, 2026")
    assert (pub, week, year) == ("2026-10-05", 40, 2026)


def _pdf():
    # PDFs are gitignored; in a worktree they sit in the main checkout
    roots = [ROOT]
    r = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode == 0:
        roots.append((ROOT / r.stdout.strip()).resolve().parent)
    for base in roots:
        p = base / "corpus" / "06-drewry" / "ais" / PDF_NAME
        if p.exists():
            return p
    return None


def test_report_matches_committed_series_row():
    pdf = _pdf()
    if pdf is None:
        pytest.skip(f"{PDF_NAME} not on disk (corpus is gitignored)")
    record, pages = A.read_report(pdf)
    with open(ROOT / "data/extracted/series/drewry_ais_drybulk_handysize_series.csv", encoding="utf-8") as fh:
        row = next(r for r in csv.DictReader(fh) if r["source_file"] == PDF_NAME)
    for field in ("current_utilisation_pct", "tonne_miles_index", "tonne_miles_yoy_pct", "bunker_price_usd_per_t",
                  "bunker_price_mom_pct"):
        got, want = record[field], row.get(field, "")
        assert (got is None and want == "") or float(want) == got, (field, got, want)
    assert record["commentary_title"] and record["commentary_title"] == row["commentary_title"]
    assert pages and pages[0]["page"] == 1
