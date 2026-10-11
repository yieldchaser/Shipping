"""GMS / Best Oasis series export: upsert semantics on synthetic sidecars (no repo data is read or written)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.parse_engine import cli
from scripts.parse_engine.export_demolition_series import (BO_FILES, GMS_FILES, parse_price_cell, read_csv,
                                                           render_csv, run_demolition_series, _crude_this_week)


def write_issue(root: Path, stem: str, issue_date: str, tables: list[dict], week: int = 1, md: str | None = None) -> None:
    year_dir = root / issue_date[:4]
    year_dir.mkdir(parents=True, exist_ok=True)
    data = {"schema": "parse_engine/v1", "issue_date": issue_date, "report_week": week,
            "source_file": f"corpus/02-hellenic/demolition/pdfs/{stem}.pdf", "tables": tables}
    (year_dir / f"{stem}.tables.json").write_text(json.dumps(data), encoding="utf-8")
    if md is not None:
        (year_dir / f"{stem}.md").write_text(md, encoding="utf-8")


def gms_tables(rank_rows: list[list[str]], port_rows: list[list[str]] | None = None,
               sales_rows: list[list[str]] | None = None) -> list[dict]:
    tables = [{"name": "gms_rankings", "title": "GMS Market Rankings",
               "columns": ["Rank", "Location", "Sentiment", "Dry Bulk USD / LDT", "Tankers USD / LDT",
                           "Containers USD / LDT"], "rows": rank_rows}]
    if port_rows is not None:
        tables.append({"name": "port_alang", "title": "Alang - Port Position as of January 05, 2024",
                       "columns": ["No.", "Vessel Name", "LDT", "Type", "Status"], "rows": port_rows})
    if sales_rows is not None:
        tables.append({"name": "market_sales_reported", "title": "Market Sales Reported",
                       "columns": ["Vessel Name", "Type", "LDT", "Reported Price"], "rows": sales_rows})
    return tables


def seed(out_dir: Path, files, rows_by_name: dict[str, list[dict[str, str]]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for spec in files:
        text = render_csv(spec.header, rows_by_name.get(spec.name, []))
        for name in (spec.name, spec.twin):
            if name:
                (out_dir / name).write_text(text, encoding="utf-8", newline="")


def rank_row(date: str, rank: str, loc: str, dry: str, src: str = "old.pdf") -> dict[str, str]:
    return {"issue_date": date, "report_week": "1", "volume": "", "issue": "", "rank": rank, "location": loc,
            "sentiment": "Steady", "dry_bulk_usd_ldt": dry, "tankers_usd_ldt": "1 / LDT",
            "containers_usd_ldt": "2 / LDT", "source_file": src}


def test_gms_upsert_replaces_only_issues_with_sidecars(tmp_path):
    root, out = tmp_path / "md", tmp_path / "series"
    write_issue(root, "gms_2024-01-05_a", "2024-01-05",
                gms_tables([["1", "Bangladesh", "Firm", "410 / LDT", "420 / LDT", "430 / LDT"]],
                           [["1", "Asena", "3,196", "General Cargo", "Delivered December 18"]],
                           [["JACOB", "Tanker", "22,572", "USD 625/LT LDT (‘as is’ Batam)"]]),
                week=1, md="---\nreport_week: 1\nvolume: 9\nissue: 99\n---\n\n# Bangladesh\n\n### Market Sales Reported\n\n| x |\n")
    write_issue(root, "gms_2024-01-12_b", "2024-01-12",
                gms_tables([["1", "India", "Weak", "400 / LDT", "410 / LDT", "420 / LDT"]]), week=2)
    seed(out, GMS_FILES, {"gms_demolition_rankings_series.csv": [
        rank_row("2023-12-01", "1", "Pakistan", "500 / LDT"),
        rank_row("2024-01-05", "1", "STALE", "1 / LDT"),
        rank_row("2024-01-05", "2", "STALE TOO", "1 / LDT")]})

    res = run_demolition_series("gms", root, out, tmp_path / "report.txt")
    rows = read_csv(out / "gms_demolition_rankings_series.csv", GMS_FILES[0].header)

    assert [(r["issue_date"], r["location"]) for r in rows] == [
        ("2023-12-01", "Pakistan"), ("2024-01-05", "Bangladesh"), ("2024-01-12", "India")]
    assert rows[1]["dry_bulk_usd_ldt"] == "410 / LDT" and rows[1]["volume"] == "9" and rows[1]["issue"] == "99"
    assert rows[0]["source_file"] == "old.pdf"                       # untouched issue keeps its rows verbatim
    sales = read_csv(out / "gms_demolition_sales_series.csv", GMS_FILES[1].header)
    assert [(r["location"], r["vessel_name"], r["price_reported"]) for r in sales] == [
        ("Bangladesh", "JACOB", "USD 625/LT LDT (‘as is’ Batam)")]
    ports = read_csv(out / "gms_port_positions_series.csv", GMS_FILES[2].header)
    assert [(r["port"], r["as_of_date"], r["vessel_name"], r["ldt"]) for r in ports] == [
        ("Alang", "January 05, 2024", "Asena", "3,196")]
    assert res["written"]


def test_twin_files_are_written_identically(tmp_path):
    root, out = tmp_path / "md", tmp_path / "series"
    write_issue(root, "gms_2024-01-05_a", "2024-01-05",
                gms_tables([["1", "Bangladesh", "Firm", "410 / LDT", "420 / LDT", "430 / LDT"]],
                           [["1", "Asena", "3,196", "General Cargo", "Delivered December 18"]]))
    seed(out, GMS_FILES, {})
    run_demolition_series("gms", root, out, tmp_path / "report.txt")
    for spec in GMS_FILES:
        if spec.twin:
            assert (out / spec.name).read_bytes() == (out / spec.twin).read_bytes()
            assert (out / spec.name).read_bytes().count(b"\r") == 0


def test_dry_run_writes_no_csv_but_the_report(tmp_path):
    root, out = tmp_path / "md", tmp_path / "series"
    write_issue(root, "gms_2024-01-05_a", "2024-01-05",
                gms_tables([["1", "Bangladesh", "Firm", "410 / LDT", "420 / LDT", "430 / LDT"]]))
    seed(out, GMS_FILES, {"gms_demolition_rankings_series.csv": [rank_row("2024-01-05", "1", "STALE", "1 / LDT")]})
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    res = run_demolition_series("gms", root, out, tmp_path / "staging" / "series_compare.txt", dry_run=True)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert res["written"] == []
    report = (tmp_path / "staging" / "series_compare.txt").read_text(encoding="utf-8")
    assert "gms_demolition_rankings_series.csv" in report and "changed 1" in report and "STALE" in report


def test_cli_dispatches_gms_and_best_oasis_and_honours_dry_run(tmp_path, capsys):
    root, out = tmp_path / "md", tmp_path / "series"
    write_issue(root, "gms_2024-01-05_a", "2024-01-05",
                gms_tables([["1", "Bangladesh", "Firm", "410 / LDT", "420 / LDT", "430 / LDT"]]))
    seed(out, GMS_FILES, {})
    args = ["series", "--source", "gms", "--root", str(root), "--out-dir", str(out), "--staging-dir",
            str(tmp_path / "staging")]
    assert cli.main(args + ["--dry-run"]) == 0
    assert read_csv(out / "gms_demolition_rankings_series.csv", GMS_FILES[0].header) == []
    assert (tmp_path / "staging" / "gms" / "series_compare.txt").exists()
    assert cli.main(args) == 0
    assert len(read_csv(out / "hellenic_gms_demolition_series.csv", GMS_FILES[0].header)) == 1
    capsys.readouterr()


def chart(country: str, title: str, rows: list[list[str]]) -> dict:
    return {"name": title, "title": f"{title} {country}" if "Ships" in title else title, "country": country,
            "row_source": "best_oasis_chart", "columns": ["Category", "Previous Week", "This Week"], "rows": rows}


def test_best_oasis_figure_only_charts_give_no_rows(tmp_path):
    root, out = tmp_path / "md", tmp_path / "series"
    price = chart("India", "Price for Recycling Ships in", [["Container", "530", "531"], ["Tanker", "510", "511"],
                                                           ["Bulker", "500", "501"]])
    price["title"] = "Price for Recycling Ships in India"
    # the HMS / Shredded chart (and Pakistan's price chart) were left as `> Figure:` notes: no table in the sidecar
    write_issue(root, "2024-02-03_bo", "2024-02-03", [price],
                md="# INDIA\n\n> Figure: Price of HMS 1&2 (80:20) and Shredded - the series cannot be assigned; no table written.\n")
    write_issue(root, "2024-02-10_bo", "2024-02-10", [])          # nothing but figure notes
    seed(out, BO_FILES, {"best_oasis_demolition_series.csv": [
        {"issue_date": "2024-02-10", "location": "India", "market_status": "", "container_usd_ldt": "1.0",
         "tanker_usd_ldt": "", "bulker_usd_ldt": "", "hms_80_20_usd_mt": "", "shredded_usd_mt": "", "source_file": "x"}]})

    res = run_demolition_series("best_oasis", root, out, tmp_path / "report.txt")
    rows = read_csv(out / "best_oasis_demolition_series.csv", BO_FILES[0].header)

    by_date = {r["issue_date"]: r for r in rows}
    assert by_date["2024-02-03"]["container_usd_ldt"] == "531.0"          # This Week column, float text
    assert by_date["2024-02-03"]["hms_80_20_usd_mt"] == "" and by_date["2024-02-03"]["shredded_usd_mt"] == ""
    assert len([r for r in rows if r["issue_date"] == "2024-02-03"]) == 1  # no row for any figure-only chart
    assert by_date["2024-02-10"]["container_usd_ldt"] == "1.0"             # sidecar without rows never wipes old rows
    assert res["results"]["best_oasis_demolition_series.csv"].kept_empty_issues == ["2024-02-10"]


def test_best_oasis_ruled_tables_deals_and_exchange(tmp_path):
    root, out = tmp_path / "md", tmp_path / "series"
    tables = [
        {"columns": ["LOCATION", "MARKET STATUS", "CONTAINER (USD/LDT)", "TANKER (USD/LDT)", "BULKER (USD/LDT)",
                     "W-O-W CHANGE (%)"], "rows": [["INDIA", "MODERATE", "475", "445", "430", "(0)"]]},
        {"columns": ["LOCATION", "HMS 1&2", "Shredded", "W-O-W CHANGE (%)"], "rows": [["INDIA", "405", "410", "(0)"]]},
        {"columns": ["VESSEL NAME", "TYPE OF VESSEL", "LDT", "TERM OF SALE", "LOCATION OF DELIVERY",
                     "SALE PRICE/LDT (USD)"],
         "rows": [["LNG KANO", "LNG", "31,022", "DELIVERED", "ALANG, INDIA", "UNDISCLOSED"],
                  ["STAR 1", "BULKER", "5,000.5", "AS-IS", "ALANG, INDIA", "445-450"],
                  ["ASTRA", "BULKER", "6,000", "AS-IS", "ALANG, INDIA", "300 (BUNKERS ROB)"]]},
        {"columns": ["Item", "This Week", "Previous Week", "Change"],
         "rows": [["USD / INR", "96.72", "96.14", "Loss 0.58"], ["USD / BDT", "123.01", "122.94", "Loss 0.07"]]},
        {"columns": ["Item", "Values as printed", "Change"],
         "rows": [["BRENT CRUDE", "(99.73 102.72)", "+2.99"], ["WTI CRUDE", "(89.50 90.33)", "- 0.83"]]},
    ]
    write_issue(root, "2026-10-10_bo", "2026-10-10", tables)
    seed(out, BO_FILES, {})
    run_demolition_series("best_oasis", root, out, tmp_path / "report.txt")

    demo = read_csv(out / "best_oasis_demolition_series.csv", BO_FILES[0].header)
    assert [(r["location"], r["market_status"], r["container_usd_ldt"], r["hms_80_20_usd_mt"]) for r in demo] == [
        ("India", "Moderate", "475.0", "405.0")]
    deals = read_csv(out / "best_oasis_deals_series.csv", BO_FILES[1].header)
    assert [(r["vessel_name"], r["ldt"], r["price_usd_ldt"], r["price_status"], r["comments"]) for r in deals] == [
        ("LNG KANO", "31022.0", "", "Undisclosed", ""), ("STAR 1", "5000.5", "", "Reported", "445-450"),
        ("ASTRA", "6000.0", "300.0", "Reported", "300 (BUNKERS ROB)")]
    fx = read_csv(out / "best_oasis_exchange_rates_series.csv", BO_FILES[2].header)
    assert len(fx) == 1
    assert (fx[0]["usd_inr"], fx[0]["usd_bdt"], fx[0]["brent_crude_usd"], fx[0]["wti_crude_usd"]) == (
        "96.72", "123.01", "102.72", "")                      # WTI sign does not match its figures: left empty
    for spec in BO_FILES:
        if spec.twin:
            assert (out / spec.name).read_bytes() == (out / spec.twin).read_bytes()


def test_issue_differing_only_in_source_file_keeps_old_rows(tmp_path):
    root, out = tmp_path / "md", tmp_path / "series"
    write_issue(root, "gms_2024-01-05_a", "2024-01-05",
                gms_tables([["1", "Bangladesh", "Steady", "410 / LDT", "1 / LDT", "2 / LDT"]]))
    row = rank_row("2024-01-05", "1", "Bangladesh", "410 / LDT", src="legacy-name.pdf")
    seed(out, GMS_FILES, {"gms_demolition_rankings_series.csv": [row]})
    res = run_demolition_series("gms", root, out, tmp_path / "report.txt")
    assert res["results"]["gms_demolition_rankings_series.csv"].path_only_issues == ["2024-01-05"]
    assert read_csv(out / "gms_demolition_rankings_series.csv", GMS_FILES[0].header)[0]["source_file"] == "legacy-name.pdf"


def test_price_and_crude_helpers():
    assert parse_price_cell("568") == ("568.0", "Reported", "")
    assert parse_price_cell("557 (In-Court auction)") == ("557.0", "Reported", "557 (In-Court auction)")
    assert parse_price_cell("1.6 MM (LUMP SUM)") == ("", "Reported", "1.6 MM (LUMP SUM)")
    assert parse_price_cell("580/640") == ("", "Reported", "580/640")
    assert parse_price_cell("UNDISCLOSED") == ("", "Undisclosed", "")
    assert parse_price_cell("UNDISCLOSED (500MT BUNKERS ROB)")[:2] == ("", "Undisclosed")
    assert parse_price_cell("-") == ("", "", "")
    assert _crude_this_week("(99.73 102.72)", "+2.99") == "102.72"
    assert _crude_this_week("(110.17 101.20)", "+ 8.79") == ""
