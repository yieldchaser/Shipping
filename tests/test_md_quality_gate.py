"""
tests/test_md_quality_gate.py

Unit tests for scripts/verify/md_quality_gate.py enforcing rules R1-R5.
Each rule includes explicit pass and fail fixture cases.
"""

from pathlib import Path
from scripts.verify.md_quality_gate import (
    check_r1,
    check_r2,
    check_r3,
    check_r4_table,
    check_r5,
    scan_file,
    split_table_row,
)


def test_r1_bare_price_cell():
    # Fail cases: bare price cells
    fail_line_1 = "| Capesize | $ | 15,000 |"
    fail_line_2 = "| Panamax | Region $ | 12,000 |"
    fail_line_3 = "| Supramax | High $ | Low $ |"

    assert check_r1(fail_line_1) == ["$"]
    assert check_r1(fail_line_2) == ["Region $"]
    assert check_r1(fail_line_3) == ["High $", "Low $"]

    # Pass cases: properly formatted or non-bare price cells
    pass_line_1 = "| Capesize | $15,000 | $16,000 |"
    pass_line_2 = "| Region | High ($/day) | Low ($/day) |"
    pass_line_3 = "|---|---|---|"

    assert check_r1(pass_line_1) == []
    assert check_r1(pass_line_2) == []
    assert check_r1(pass_line_3) == []


def test_r2_fake_zero_change():
    # Fail case: two different prices with 0.0% / 0.00% change
    fail_line_1 = "| S10 S China-Indo RV | usd/day | 16,543 | 16,550 | 0.0% |"
    fail_line_2 = "| 4250 teu (1Y, g'less) | usd/day | $59,300 | $59,315 | ~~-0.00%~~ |"

    res_1 = check_r2(fail_line_1)
    assert len(res_1) == 1
    p1, p2, zc = res_1[0]
    assert (p1, p2) == (16543.0, 16550.0)
    assert zc == "0.0%"

    res_2 = check_r2(fail_line_2)
    assert len(res_2) == 1
    p1, p2, zc = res_2[0]
    assert (p1, p2) == (59300.0, 59315.0)
    assert "0.00%" in zc

    # Pass cases: identical prices with genuine 0.0% change, or non-zero change
    pass_line_1 = "| Kamsarmax 1-Y Period | usd/day | 20,000 | 20,000 | +0.0% |"
    pass_line_2 = "| VLCC 1-Y Period | usd/day | 210,000 | 200,000 | +5.0% |"
    pass_line_3 = "| Route | Unit | Rate |"

    assert check_r2(pass_line_1) == []
    assert check_r2(pass_line_2) == []
    assert check_r2(pass_line_3) == []


def test_r3_personal_phone():
    # Fail case: personal phone number not in publisher switchboard allow-list
    fail_line_1 = "Contact broker at +44 7802 304129 for details."
    fail_line_2 = "Direct mobile: +49 (0)176 311 48 514"

    assert check_r3(fail_line_1) == ["+44 7802 304129"]
    assert check_r3(fail_line_2) == ["+49 (0)176 311 48 514"]

    # Pass case: allowed publisher switchboards
    pass_line_1 = "Intermodal Athens HQ Tel: +30 210 6293300, Fax: +30 210 6293333"
    pass_line_2 = "Banchero Costa Genoa tel +39 010 5631 1"
    pass_line_3 = "Fearnleys Oslo office tel: +4722936000"

    assert check_r3(pass_line_1) == []
    assert check_r3(pass_line_2) == []
    assert check_r3(pass_line_3) == []

    # Pass case: markdown image path with encoded plus
    pass_img = "![Greek+title+2024 05 01](../../assets/img.png)"
    assert check_r3(pass_img) == []


def test_r4_chart_readings_table():
    # Fail case: >= 80% month dates in column 1
    fail_table = [
        ["Date", "Index", "Change"],
        ["9/Jul/20", "1500", "+10"],
        ["16/Jul/20", "1520", "+20"],
        ["23/Jul/20", "1550", "+30"],
        ["30/Jul/20", "1600", "+50"],
    ]
    ratio = check_r4_table(fail_table)
    assert ratio is not None
    assert ratio >= 0.80

    # Pass case: normal route / commodity table (not dates)
    pass_table = [
        ["Route", "Vessel", "Rate"],
        ["CVB - Med", "10k DWCC", "3500"],
        ["Danube - ARA", "5k DWCC", "2800"],
        ["Rostov - Marmara", "3k DWCC", "1900"],
    ]
    assert check_r4_table(pass_table) is None


def test_r5_frontmatter_source():
    tmp_corpus = Path("corpus/01-brokers/ism/2026")
    existing_pdf = "corpus/01-brokers/ism/2026/ism_2026_W41_ISM_coaster_week41.pdf"

    # Pass case: valid existing source_file
    pass_fm = {"source_file": existing_pdf}
    assert check_r5(pass_fm, [Path(".")]) is None

    # Fail cases: missing or non-existent file
    fail_fm_missing = {}
    assert check_r5(fail_fm_missing, [Path(".")]) == "frontmatter missing or empty 'source_file'"

    fail_fm_nonexistent = {"source_file": "corpus/01-brokers/fake/does_not_exist.pdf"}
    err = check_r5(fail_fm_nonexistent, [Path(".")])
    assert err is not None
    assert "does not exist under corpus/" in err


def test_scan_file_integration(tmp_path):
    # Test end-to-end scanner on a temporary markdown file
    md_file = tmp_path / "data" / "extracted" / "md" / "intermodal" / "test_report.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)

    content = """---
source_file: corpus/non_existent.pdf
---

# Market Report

| Size | Rate |
|---|---|
| Capesize | $ |

| Route | Price A | Price B | Chg |
|---|---|---|---|
| Tanker | 1000 | 1200 | 0.0% |

Call broker at +44 7802 304129.

| Date | Value |
|---|---|
| Jan-22 | 10 |
| Feb-22 | 12 |
| Mar-22 | 14 |
| Apr-22 | 16 |
"""
    md_file.write_text(content, encoding="utf-8")
    findings = scan_file(md_file, corpus_roots=[tmp_path / "corpus"])

    rules_found = {f.rule for f in findings}
    assert "R1" in rules_found
    assert "R2" in rules_found
    assert "R3" in rules_found
    assert "R4" in rules_found
    assert "R5" in rules_found
