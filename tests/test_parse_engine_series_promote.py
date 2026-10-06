"""Tests for the series export, price parsing and the promotion planner. No network, no git writes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.parse_engine import export_series as xs
from scripts.parse_engine import promote
from scripts.parse_engine.config import load_profile
from scripts.parse_engine.engine import dedupe_pdfs

CLARKSONS = load_profile("clarksons")


@pytest.mark.parametrize("raw,usd,qual,en_bloc,scope", [
    ("USD 22,7m", 22.7, "", False, "vessel"),
    ("LOW USD 11m", 11.0, "LOW", False, "vessel"),
    ("RGN USD 11 M", 11.0, "RGN", False, "vessel"),
    ("Mid/High USD 12 M bss DD due", 12.0, "MID/HIGH", False, "vessel"),
    ("USD XS 90 M ENBLOC", 90.0, "XS", True, "group"),
    ("USD 66 M each (en bloc)", 66.0, "", True, "vessel"),
    ("USD 222.5 M (En Bloc deal including six-year time charters)", 222.5, "", True, "group"),
    ("RGN 20.1 M", 20.1, "RGN", False, "vessel"),
    ("USD 2.35 B", 2350.0, "", False, "vessel"),
    ("$21.7 M", 21.7, "", False, "vessel"),
])
def test_parse_price(raw, usd, qual, en_bloc, scope):
    p = xs.parse_price(raw)
    assert (p["price_usd_m"], p["price_qualifier"], p["en_bloc"], p["price_scope"]) == (usd, qual, en_bloc, scope)


@pytest.mark.parametrize("raw", ["U/D", "-", "", "undisclosed"])
def test_undisclosed_price_is_blank(raw):
    assert xs.parse_price(raw)["price_usd_m"] == ""


def test_parse_int_handles_thousands_separators():
    assert xs.parse_int("31,842") == 31842
    assert xs.parse_int("175.085") == 175085
    assert xs.parse_int("81762") == 81762
    assert xs.parse_int("N/A") == ""


def test_demolition_helpers():
    assert xs.parse_ldt("9,543 LDT") == 9543
    assert xs.parse_ldt("8.895 LDT") == 8895
    assert xs.parse_demo_price("USD 585.5 / LDT") == 585.5
    assert xs.parse_demo_price("530/LDT") == 530.0


def _write_issue(root: Path, year: str, stem: str, issue_date: str, tables: list[dict]) -> None:
    d = root / year
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.md").write_text(f"---\ntitle: t\nissue_date: '{issue_date}'\nsource_file: corpus/{stem}.pdf\n"
                                  f"source_sha256: abc\n---\n\nbody\n", encoding="utf-8")
    (d / f"{stem}.tables.json").write_text(json.dumps(tables), encoding="utf-8")


def test_export_series_rows_and_en_bloc_groups(tmp_path):
    cols = ["Vessel", "DWT", "Year", "Yard", "Details", "SS/DD", "Price", "Buyer"]
    sales = {"name": "Bulk Carriers", "columns": cols, "empty": False, "en_bloc_rows": [1, 2], "rows": [
        ["A", "50,000", "2011", "BOHAI", "MAN", "SS 01/25", "LOW USD 10 M", "GREEKS"],
        ["B", "30.000", "2012", "IMABARI", "MAN", "SS 02/25", "USD 20 M", "U/D"],
        ["C", "30,100", "2012", "IMABARI", "MAN", "SS 03/25", "USD 20 M", "U/D"]]}
    tanker = {"name": "Tankers - Chemicals - LPG/LNGs", "columns": cols, "empty": True,
              "rows": [["No reported sales", "", "", "", "", "", "", ""]]}
    demo = {"name": "Demolition - Bulk Carriers GCs", "columns": ["Vessel", "DWT", "Built", "Details", "Price", "Delivery"],
            "empty": False, "rows": [["K", "69,235", "1993 JAPAN", "9,543 LDT", "USD 585.5 / LDT", "BANGLADESH"]]}
    _write_issue(tmp_path / "stage", "2021", "2021-07-09_x", "2021-07-09", [sales, tanker, demo])
    res = xs.export(tmp_path / "stage", tmp_path / "out")
    rows = res["sales"]
    assert [r["vessel"] for r in rows] == ["A", "B", "C"]            # "No reported sales" is not a vessel
    assert rows[0]["price_usd_m"] == 10.0 and rows[0]["price_qualifier"] == "LOW" and rows[0]["en_bloc"] is False
    assert rows[1]["dwt"] == 30000 and rows[1]["en_bloc"] is True and rows[1]["price_usd_m"] == 20.0
    assert rows[1]["en_bloc_group"] == rows[2]["en_bloc_group"] != ""
    assert rows[0]["report_week"] == 27 and rows[0]["section"] == "bulk"
    assert res["demolition_rows"] == 1 and res["demo"][0]["ldt"] == 9543 and res["demo"][0]["price_usd_ldt"] == 585.5
    assert (tmp_path / "out" / "clarksons_sales_series.csv").exists()


def test_compare_counts_by_issue_date_and_vessel(tmp_path):
    old = tmp_path / "old.csv"
    old.write_text("issue_date,NAME\n2021-07-09,A\n2021-07-09,Z\n2021-08-01,Q\n", encoding="utf-8")
    c = xs.compare([{"issue_date": "2021-07-09", "vessel": "a"}, {"issue_date": "2021-07-09", "vessel": "B"}],
                   old, "issue_date", "NAME")
    assert c["old_not_in_new"] == 2 and c["new_not_in_old"] == 1
    assert c["old_not_in_new_common_dates"] == 1 and c["dates_only_in_old"] == 1


# ------------------------------------------------------------------------------------ promotion
def _staged(staging: Path, year: str, stem: str, issue_date: str | None, flags: list[str]) -> None:
    d = staging / "clarksons" / year
    d.mkdir(parents=True, exist_ok=True)
    fm = f"issue_date: '{issue_date}'\n" if issue_date else "issue_date: null\n"
    (d / f"{stem}.md").write_text(f"---\n{fm}source_file: corpus/{stem}.pdf\n---\n\nbody\n", encoding="utf-8")
    (d / f"{stem}.tables.json").write_text("[]", encoding="utf-8")
    (d / f"{stem}.validation.json").write_text(json.dumps({"flags": flags}), encoding="utf-8")


def _old(path: Path, issue_date: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = f"issue_date: '{issue_date}'\n" if issue_date else ""
    path.write_text(f"---\n{fm}---\n\nold\n", encoding="utf-8")
    path.with_suffix(".tables.json").write_text("[]", encoding="utf-8")


def test_promotion_plan_maps_old_to_new_and_keeps_unmatched(tmp_path):
    staging, dest = tmp_path / "stage", tmp_path / "data" / "clarksons"
    legacy_b = tmp_path / "data" / "hellenic" / "clarksons"
    s1, s2, s3 = "2022-08-19_a_aaaaaaaaaaaa", "2022-08-26_b_bbbbbbbbbbbb", "2022-09-02_c_cccccccccccc"
    _staged(staging, "2022", s1, "2022-08-19", [])
    _staged(staging, "2022", s2, "2022-08-26", ["low_text_recall"])           # flagged: not promoted
    _staged(staging, "2022", s3, "2022-09-02", ["issue_date_conflict_header_chosen"])
    _old(dest / "2022" / (s1 + ".md"), "2022-08-19")                           # same stem: overwritten in place
    _old(legacy_b / "2022" / "2022-08-19_other_name_zzzzzzzzzzzz.md", "2022-08-19")   # same issue, other set
    _old(legacy_b / "2022" / "2022-08-26_other_name_yyyyyyyyyyyy.md", "2022-08-26")   # issue not promoted
    _old(legacy_b / "2022" / "2021-01-01_unrelated_xxxxxxxxxxxx.md", "2021-01-01")    # no new issue at all
    plan = promote.build_plan("clarksons", staging, dest, [dest, legacy_b], accept_flags=set(),
                              date_patterns=CLARKSONS["date_patterns"], repo_root=tmp_path)
    actions = {(r["action"], Path(r["old_path"]).name or Path(r["new_path"]).name) for r in plan.rows}
    assert ("promote", s1 + ".md") in actions
    assert ("overwrite_in_place", s1 + ".md") in actions and ("overwrite_in_place", s1 + ".tables.json") in actions
    assert ("git_rm", "2022-08-19_other_name_zzzzzzzzzzzz.md") in actions
    assert ("git_rm", "2022-08-19_other_name_zzzzzzzzzzzz.tables.json") in actions
    assert ("keep_issue_flagged", "2022-08-26_other_name_yyyyyyyyyyyy.md") in actions
    assert ("keep_unmatched", "2021-01-01_unrelated_xxxxxxxxxxxx.md") in actions
    assert sum(1 for r in plan.rows if r["action"] == "skip_flagged") == 2
    assert promote.summarize(plan)["promote"] == 1


def test_accepted_flag_allows_promotion_and_hash_duplicates_are_removed(tmp_path):
    staging, dest = tmp_path / "stage", tmp_path / "data" / "clarksons"
    s1 = "2023-07-21_a_cebb0332bb75"
    _staged(staging, "2023", s1, "2023-07-21", ["issue_date_conflict_filename_chosen"])
    _old(dest / "2023" / "2023-07-24_dup_cebb0332bb75.md", "2023-07-24")      # same PDF hash, other date
    plan = promote.build_plan("clarksons", staging, dest, [dest], accept_flags={"issue_date_conflict_filename_chosen"},
                              date_patterns=CLARKSONS["date_patterns"], repo_root=tmp_path)
    assert promote.summarize(plan)["promote"] == 1
    assert {r["action"] for r in plan.rows if r["old_path"].endswith("cebb0332bb75.md") or
            r["old_path"].endswith("cebb0332bb75.tables.json")} == {"git_rm_hash_duplicate"}
    assert len(plan.remove) == 2


def test_old_md_named_by_publisher_date_pattern_is_matched(tmp_path):
    staging, dest = tmp_path / "stage", tmp_path / "data" / "clarksons"
    _staged(staging, "2026", "2026-09-04_x_aaaaaaaaaaaa", "2026-09-04", [])
    _old(dest / "2026" / "clarksons_2026_nan_Weekly-Sales-04th-Sept-2026.md", None)   # no frontmatter date
    plan = promote.build_plan("clarksons", staging, dest, [dest], set(), date_patterns=CLARKSONS["date_patterns"],
                              repo_root=tmp_path)
    assert any(r["action"] == "git_rm" and r["old_path"].endswith("Weekly-Sales-04th-Sept-2026.md") for r in plan.rows)


def test_dedupe_prefers_year_partitioned_hashed_names(tmp_path):
    a = tmp_path / "pdfs" / "2022-08-19_Weekly-Sales.pdf"
    b = tmp_path / "pdfs" / "2022" / "2022-08-19_x_aaaaaaaaaaaa.pdf"
    c = tmp_path / "pdfs" / "2022" / "2022-08-19_Weekly-Sales.pdf"
    for p in (a, b, c):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"same bytes")
    keep, dropped = dedupe_pdfs([a, b, c], CLARKSONS["prefer_path_regex"], CLARKSONS["prefer_name_regex"])
    assert keep == [b] and {d for d, _ in dropped} == {a, c}


def test_old_file_at_a_promoted_destination_is_overwritten_not_removed(tmp_path):
    """Header date differs from the filename date, so the old MD (same stem, other date) must not be git-rm'd."""
    staging, dest = tmp_path / "stage", tmp_path / "data" / "clarksons"
    stem = "2022-04-22_x_report-23-04-2022_59c9d2476238"
    _staged(staging, "2022", stem, "2022-04-23", [])
    _old(dest / "2022" / (stem + ".md"), "2022-04-22")
    plan = promote.build_plan("clarksons", staging, dest, [dest], set(), date_patterns=CLARKSONS["date_patterns"],
                              repo_root=tmp_path)
    assert plan.remove == []
    assert {r["action"] for r in plan.rows if r["old_path"]} == {"overwrite_in_place"}
