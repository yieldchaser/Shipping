"""Validation and integrity tests for Hellenic Shipping News extraction series.

Covers:
- Athenian, Best Oasis, GMS Demolition series
- Clarksons Platou Hellas S&P and Demolition series
- VesselsValue transaction deals and valuation premiums
- Alibra Dry Bulk and Tanker Time Charter series
- Markdown frontmatter and JSON sidecar integrity
"""

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERIES_DIR = ROOT / "data" / "extracted" / "series"
MD_DIR = ROOT / "data" / "extracted" / "md" / "hellenic"
CLARKSONS_MD_DIR = ROOT / "data" / "extracted" / "md" / "clarksons"


def test_hellenic_demolition_series_integrity():
    """Verify Hellenic Athenian, Best Oasis, and GMS demolition master series."""
    # 1. Athenian
    athenian_csv = SERIES_DIR / "hellenic_athenian_demolition_series.csv"
    assert athenian_csv.exists(), "Athenian series CSV missing"
    with open(athenian_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 3000, f"Expected >= 3,000 Athenian rows, found {len(rows)}"
    assert all(r["issue_date"] and r["country"] and r["price_usd_per_ldt"] for r in rows)

    # 2. Best Oasis
    bo_csv = SERIES_DIR / "hellenic_best_oasis_demolition_series.csv"
    assert bo_csv.exists(), "Best Oasis demolition series CSV missing"
    with open(bo_csv, "r", encoding="utf-8") as f:
        bo_rows = list(csv.DictReader(f))
    assert len(bo_rows) >= 200, f"Expected >= 200 Best Oasis price rows, found {len(bo_rows)}"

    bo_deals_csv = SERIES_DIR / "hellenic_best_oasis_deals_series.csv"
    assert bo_deals_csv.exists(), "Best Oasis deals series CSV missing"
    with open(bo_deals_csv, "r", encoding="utf-8") as f:
        bo_deals = list(csv.DictReader(f))
    assert len(bo_deals) >= 500, f"Expected >= 500 Best Oasis deal rows, found {len(bo_deals)}"

    # 3. GMS (272 unique reports: 246 native PDFs + 26 2021 HTML articles)
    gms_csv = SERIES_DIR / "hellenic_gms_demolition_series.csv"
    assert gms_csv.exists(), "GMS demolition series CSV missing"
    with open(gms_csv, "r", encoding="utf-8") as f:
        gms_rows = list(csv.DictReader(f))
    assert len(gms_rows) >= 1088, f"Expected >= 1,088 GMS ranking rows, found {len(gms_rows)}"
    assert all(r["issue_date"] and r["location"] and r["sentiment"] for r in gms_rows)

    gms_pos_csv = SERIES_DIR / "hellenic_gms_port_positions_series.csv"
    assert gms_pos_csv.exists(), "GMS port positions CSV missing"
    with open(gms_pos_csv, "r", encoding="utf-8") as f:
        gms_pos = list(csv.DictReader(f))
    assert len(gms_pos) >= 2800, f"Expected >= 2,800 GMS port position rows, found {len(gms_pos)}"

    gms_sales_csv = SERIES_DIR / "gms_demolition_sales_series.csv"
    assert gms_sales_csv.exists(), "GMS demolition sales CSV missing"
    with open(gms_sales_csv, "r", encoding="utf-8") as f:
        gms_sales = list(csv.DictReader(f))
    assert len(gms_sales) >= 50, f"Expected >= 50 GMS sales rows, found {len(gms_sales)}"

    gms_comm_csv = SERIES_DIR / "gms_market_commentary_series.csv"
    assert gms_comm_csv.exists(), "GMS commentary CSV missing"
    with open(gms_comm_csv, "r", encoding="utf-8") as f:
        gms_comm = list(csv.DictReader(f))
    assert len(gms_comm) >= 1200, f"Expected >= 1,200 GMS commentary rows, found {len(gms_comm)}"


def test_clarksons_hellas_series_integrity():
    """Verify Clarksons Platou Hellas multi-year S&P and Demolition series."""
    sales_csv = SERIES_DIR / "clarksons_sales_series.csv"
    assert sales_csv.exists(), "Clarksons sales CSV missing"
    with open(sales_csv, "r", encoding="utf-8") as f:
        sales = list(csv.DictReader(f))
    assert len(sales) >= 1200, f"Expected >= 1,200 Clarksons sales rows, found {len(sales)}"

    # Check multi-year coverage
    years = set(r["issue"][:4] for r in sales)
    assert {"2021", "2022", "2023", "2024", "2026"}.issubset(years), f"Missing expected years in {years}"

    # Verify demolition series
    demo_csv = SERIES_DIR / "clarksons_demolition_series.csv"
    assert demo_csv.exists(), "Clarksons demolition CSV missing"
    with open(demo_csv, "r", encoding="utf-8") as f:
        demos = list(csv.DictReader(f))
    assert len(demos) >= 100, f"Expected >= 100 Clarksons demolition rows, found {len(demos)}"


def test_vesselsvalue_valuations_integrity():
    """Verify VesselsValue S&P transactions and valuation premium calculations."""
    vv_csv = SERIES_DIR / "hellenic_vv_sales_series.csv"
    assert vv_csv.exists(), "VesselsValue sales CSV missing"
    with open(vv_csv, "r", encoding="utf-8") as f:
        deals = list(csv.DictReader(f))
    assert len(deals) >= 2000, f"Expected >= 2,000 VV deals, found {len(deals)}"

    # Verify premium calculation accuracy on deals with both prices
    checked = 0
    for d in deals:
        if d["price_usd_m"] and d["vv_value_usd_m"]:
            p = float(d["price_usd_m"])
            vv = float(d["vv_value_usd_m"])
            prem = float(d["premium_pct"])
            expected_prem = round(((p - vv) / vv) * 100.0, 2)
            assert abs(prem - expected_prem) < 0.05, f"Premium calculation mismatch on {d['vessel_name']}: {prem} vs {expected_prem}"
            checked += 1
    assert checked >= 1500, f"Expected >= 1,500 checked valuation pairs, got {checked}"


def test_markdown_and_sidecars_existence():
    """Verify existence and valid JSON structure of generated sidecars."""
    # Check demolition markdown
    demo_md_files = list((MD_DIR / "demolition").glob("**/*.md"))
    assert len(demo_md_files) >= 500, f"Expected >= 500 demolition markdown files, found {len(demo_md_files)}"

    # Check Clarksons markdown
    clarksons_md = list(CLARKSONS_MD_DIR.glob("*.md"))
    assert len(clarksons_md) >= 170, f"Expected >= 170 Clarksons markdown files, found {len(clarksons_md)}"

    # Check VesselsValue markdown
    vv_md = list((MD_DIR / "vessel_valuations").glob("**/*.md"))
    assert len(vv_md) >= 250, f"Expected >= 250 VV markdown files, found {len(vv_md)}"


def test_alibra_time_charter_integrity():
    """Verify Alibra Dry Bulk and Tanker Time Charter master series."""
    dry_csv = SERIES_DIR / "hellenic_alibra_dry_tc_series.csv"
    wet_csv = SERIES_DIR / "hellenic_alibra_tanker_tc_series.csv"
    if not dry_csv.exists() or not wet_csv.exists():
        pytest.skip("Alibra Time Charter series currently extracting in background")

    with open(dry_csv, "r", encoding="utf-8") as f:
        dry_rows = list(csv.DictReader(f))
    assert len(dry_rows) >= 5000, f"Expected >= 5,000 Dry TC rows, got {len(dry_rows)}"
    assert all(r["rate_usd_pdpr"] and int(r["rate_usd_pdpr"]) > 0 for r in dry_rows)
    assert all(r["trend"] in ("up", "down", "flat") for r in dry_rows)

    with open(wet_csv, "r", encoding="utf-8") as f:
        wet_rows = list(csv.DictReader(f))
    assert len(wet_rows) >= 5000, f"Expected >= 5,000 Wet TC rows, got {len(wet_rows)}"
    assert all(r["rate_usd_pdpr"] and int(r["rate_usd_pdpr"]) > 0 for r in wet_rows)
    assert all(r["trend"] in ("up", "down", "flat") for r in wet_rows)


def test_vesselsvalue_matrix_series_integrity():
    """Verify VesselsValue weekly change mini matrix series."""
    matrix_csv = SERIES_DIR / "hellenic_vv_matrix_series.csv"
    if not matrix_csv.exists():
        pytest.skip("VesselsValue matrix CSV not yet created")

    with open(matrix_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 10000, f"Expected >= 10,000 VV matrix rows, found {len(rows)}"
    assert all(r["issue_date"] and r["age_years"] for r in rows)


def test_gms_demolition_rankings_series_integrity():
    """Verify GMS weekly demolition rankings master series."""
    gms_csv = SERIES_DIR / "hellenic_gms_demolition_series.csv"
    if not gms_csv.exists():
        pytest.skip("GMS demolition CSV not yet created")

    with open(gms_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 900, f"Expected >= 900 GMS ranking rows, found {len(rows)}"
    locations = set(r["location"] for r in rows)
    assert {"India", "Pakistan", "Bangladesh", "Turkey"}.issubset(locations)


def test_derived_time_charter_rates_integrity():
    """Verify synchronization and integrity of data/derived/time_charter_rates.csv."""
    tc_csv = ROOT / "data" / "derived" / "time_charter_rates.csv"
    assert tc_csv.exists(), "time_charter_rates.csv missing"

    with open(tc_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 2000, f"Expected >= 2,000 rows in time_charter_rates.csv, found {len(rows)}"

    # Check alibra_ocr rows
    ocr_rows = [r for r in rows if r["source"] == "alibra_ocr"]
    assert len(ocr_rows) >= 260, f"Expected >= 260 alibra_ocr rows, found {len(ocr_rows)}"

    # Check non-null rate fields on sample row
    sample = ocr_rows[-1]
    assert float(sample["capesize_1y_avg"]) > 0
    assert float(sample["vlcc_1y"]) > 0


def test_hellenic_iron_ore_series_integrity():
    """Verify Hellenic MMi daily iron ore index series."""
    table_csv = SERIES_DIR / "hellenic_iron_ore_table_series.csv"
    comm_csv = SERIES_DIR / "hellenic_iron_ore_commentary_series.csv"
    if not table_csv.exists():
        pytest.skip("Iron ore table CSV not yet created")
    with open(table_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 20, f"Expected >= 20 iron ore table rows, found {len(rows)}"
    indices = set(r["index_code"] for r in rows)
    assert {"IOPI62", "IOSI62"}.intersection(indices), f"Expected IOPI62 or IOSI62 in indices: {indices}"


def test_derived_iron_ore_restocking_integrity():
    """Verify data/derived/iron_ore_restocking.csv integrity and non-zero prices."""
    io_csv = ROOT / "data" / "derived" / "iron_ore_restocking.csv"
    assert io_csv.exists(), "iron_ore_restocking.csv missing"
    with open(io_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1000, f"Expected >= 1,000 rows in iron_ore_restocking.csv, found {len(rows)}"
    non_null_cfr = [r for r in rows if r.get("cfr_62") and float(r["cfr_62"]) > 0]
    assert len(non_null_cfr) >= 500, f"Expected >= 500 non-null cfr_62 rows, found {len(non_null_cfr)}"


def test_athenian_demolition_world_class_integrity():
    """Verify Athenian Shipbrokers Demolition Quick Updates deliverables and coverage."""
    # 1. Indicative Demolition Series CSV
    athenian_csv = SERIES_DIR / "athenian_indicative_demolition_series.csv"
    assert athenian_csv.exists(), "Athenian indicative demolition series CSV missing"
    with open(athenian_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3052, f"Expected 3,052 Athenian rows, found {len(rows)}"
    years = set(r["issue_date"][:4] for r in rows)
    assert {"2021", "2022", "2023", "2024", "2025", "2026"}.issubset(years)

    # 2. Yearly Demolition Volume Series CSV
    vol_csv = SERIES_DIR / "athenian_yearly_demolition_volume_series.csv"
    assert vol_csv.exists(), "Athenian yearly demolition volume series CSV missing"
    with open(vol_csv, "r", encoding="utf-8") as f:
        vol_rows = list(csv.DictReader(f))
    assert len(vol_rows) >= 4000, f"Expected >= 4,000 volume rows, found {len(vol_rows)}"

    # 3. Historical Demolition Prices Series CSV (derived dynamically from Era 1 text tables)
    hist_csv = SERIES_DIR / "athenian_historical_demolition_prices_series.csv"
    assert hist_csv.exists(), "Athenian historical demolition prices CSV missing"
    with open(hist_csv, "r", encoding="utf-8") as f:
        hist_rows = list(csv.DictReader(f))
    assert len(hist_rows) == 240, f"Expected 240 historical price rows, found {len(hist_rows)}"

    # 4. Markdown and JSON Sidecars
    athenian_md_dir = ROOT / "data" / "extracted" / "md" / "hellenic" / "demolition" / "athenian"
    assert athenian_md_dir.exists(), "Athenian MD directory missing"
    md_files = list(athenian_md_dir.rglob("*.md"))
    json_files = list(athenian_md_dir.rglob("*.tables.json"))
    assert len(md_files) == 257, f"Expected 257 Athenian markdown files, found {len(md_files)}"
    assert len(json_files) == 257, f"Expected 257 Athenian JSON sidecars, found {len(json_files)}"


def test_best_oasis_demolition_integrity():
    """
    Validates complete integrity of Best Oasis Ship Recycling extraction:
    - Indicative Demolition Prices Series CSV (>= 850 rows spanning 2021-2026)
    - Demolition Deals Series CSV (>= 850 fixtures)
    - Exchange Rates & Macro Series CSV (>= 150 weeks)
    - Market Commentary Series CSV (>= 1,000 sections)
    - Markdown & JSON Sidecar files (213 clean publication-grade reports across all years)
    """
    # 1. Indicative Demolition Prices Series CSV
    demo_csv = SERIES_DIR / "best_oasis_demolition_series.csv"
    assert demo_csv.exists(), "best_oasis_demolition_series.csv missing"
    with open(demo_csv, "r", encoding="utf-8") as f:
        demo_rows = list(csv.DictReader(f))
    assert len(demo_rows) >= 850, f"Expected >= 850 Best Oasis demolition rows, found {len(demo_rows)}"
    years = set(r["issue_date"][:4] for r in demo_rows)
    assert {"2021", "2022", "2023", "2024", "2025", "2026"}.issubset(years)

    # Validate price bounds
    for r in demo_rows:
        for col in ["container_usd_ldt", "tanker_usd_ldt", "bulker_usd_ldt"]:
            val = r.get(col)
            if val and val.strip():
                fval = float(val)
                assert 200 <= fval <= 850, f"Unrealistic scrap price {fval} in {r['source_file']}"

    # 2. Demolition Deals Series CSV
    deals_csv = SERIES_DIR / "best_oasis_deals_series.csv"
    assert deals_csv.exists(), "best_oasis_deals_series.csv missing"
    with open(deals_csv, "r", encoding="utf-8") as f:
        deals_rows = list(csv.DictReader(f))
    assert len(deals_rows) >= 850, f"Expected >= 850 Best Oasis deals rows, found {len(deals_rows)}"

    # 3. Exchange Rates Series CSV
    macro_csv = SERIES_DIR / "best_oasis_exchange_rates_series.csv"
    assert macro_csv.exists(), "best_oasis_exchange_rates_series.csv missing"
    with open(macro_csv, "r", encoding="utf-8") as f:
        macro_rows = list(csv.DictReader(f))
    assert len(macro_rows) >= 150, f"Expected >= 150 macro rows, found {len(macro_rows)}"

    # 4. Market Commentary Series CSV
    comm_csv = SERIES_DIR / "best_oasis_market_commentary_series.csv"
    assert comm_csv.exists(), "best_oasis_market_commentary_series.csv missing"
    with open(comm_csv, "r", encoding="utf-8") as f:
        comm_rows = list(csv.DictReader(f))
    assert len(comm_rows) >= 1000, f"Expected >= 1,000 commentary rows, found {len(comm_rows)}"

    # 5. Markdown and JSON Sidecars
    bo_md_dir = ROOT / "data" / "extracted" / "md" / "hellenic" / "demolition" / "best_oasis"
    assert bo_md_dir.exists(), "Best Oasis MD directory missing"
    md_files = list(bo_md_dir.rglob("*.md"))
    json_files = list(bo_md_dir.rglob("*.tables.json"))
    assert len(md_files) >= 213, f"Expected >= 213 Best Oasis markdown files, found {len(md_files)}"
    assert len(json_files) >= 213, f"Expected >= 213 Best Oasis JSON sidecars, found {len(json_files)}"




