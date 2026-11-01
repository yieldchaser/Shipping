"""SEC statement tables must come out one row per line item.

Regression for the standardizer defects that stacked rows into one cell (VALE 6-K 3Q26, SFL 20-F, GNK 10-Q ...):
a negative number such as "(814)" was merged with the column to its right as if it were an "(a)" sub-item marker,
and a header swallowed the data rows below it when their values were ranges or carried units. No network access.
"""
from __future__ import annotations

from scripts.acquire import standardize_sec_markdown as S
from scripts.audit import detect_sec_stacked_tables as D


def _cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def test_negative_numbers_without_thousands_separator_stay_in_their_own_columns():
    table = [
        "|  | Notes | Three-month period ended September 30, — 2026 | 2025 | Nine-month period ended September 30, — 2026 | 2025 |",
        "| Net operating revenue | 3(b) | 54,462 | 56,701 | 156,154 | 153,919 |",
        "| Cost of goods sold and services rendered | 4(a) | (40,798) | (36,077) | (110,054) | (102,309) |",
        "| Selling and administrative | 4(b) | (814) | (858) | (2,502) | (2,445) |",
        "| Research and development |  | (973) | (820) | (2,594) | (2,437) |",
    ]
    out = S.repair_table_block(table)
    assert len(out) == 2 + 4
    assert _cells(out[0])[0] == "Line Item"
    assert _cells(out[2]) == ["Net operating revenue", "3(b)", "54,462", "56,701", "156,154", "153,919"]
    assert _cells(out[4]) == ["Selling and administrative", "4(b)", "(814)", "(858)", "(2,502)", "(2,445)"]
    assert not any(D.stacked_cell(c) for line in out for c in _cells(line))


def test_header_does_not_swallow_data_rows_with_ranges_or_units():
    table = [
        "| Significant Input | March 31, 2024 | December 31, 2023 |",
        "| Closing share price of our common stock | \\$14.36 to \\$18.17 | \\$14.36 to \\$16.30 |",
        "| Risk-free rate of return | 3.81 % to 4.38 % | 3.81 % to 4.38 % |",
        "| Expected volatility of our common stock | 48.34 % to 54.53 % | 53.38 % to 54.53 % |",
    ]
    out = S.repair_table_block(table)
    assert _cells(out[0]) == ["Significant Input", "March 31, 2024", "December 31, 2023"]
    assert len(out) == 2 + 3


def test_sub_item_titles_are_still_merged_in_contents_tables():
    table = [
        "| Item 4 | (a) | Information on the Company | 12 |",
        "| Item 5 | (b) | Operating and Financial Review | 40 |",
    ]
    out = S.repair_table_block(table)
    assert any("(a) Information on the Company" in line for line in out)


def test_header_digits_are_not_values():
    for header in ("March 31, 2024", "2026", "Q4 2021", "9M 2024", "Notes 3", "(1)", "Year Ended December 31, 2022"):
        assert not S.has_value_token(header), header
    for value in ("\\$17,200,000 — \\$19,200,000", "5,800 TEU", "3.81 % to 4.38 %"):
        assert S.has_value_token(value), value


def test_detector_flags_stacked_cells_only():
    stacked = "| Gross profit |  | 13,664 20,624 (1,244) | 46,100 51,610 |"
    clean = "| Gross profit |  | 13,664 | 20,624 | 46,100 | 51,610 |"
    assert D.analyse(stacked)["stacked_cells"] == 1
    assert D.analyse(clean)["stacked_cells"] == 0
    assert D.analyse("| Contact | +61 1300 55 4757 | ABN 49 004 028 077 |")["stacked_cells"] == 0
