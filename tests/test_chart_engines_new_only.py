"""New-only (incremental) merge of the free vector chart engines: ssy, intermodal,
xclusiv, ism. Synthetic rows only; nothing here touches data/ or the corpus.

Contract per engine: new keys are appended, existing rows are kept, and a second run with
the same input changes nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PUB = Path(__file__).resolve().parents[1] / "scripts" / "extract" / "publishers"
sys.path.insert(0, str(PUB))

import chart_series_incremental as inc  # noqa: E402
import merge_intermodal_charts as im  # noqa: E402
import merge_ssy_charts as ssy  # noqa: E402
import run_ism_series as ism  # noqa: E402
import run_xclusiv_vector_charts as xc  # noqa: E402


def _bytes(path: Path) -> bytes:
    return path.read_bytes()


# ---------------------------------------------------------------------------- helper

def test_upsert_new_keys_appends_keeps_and_is_idempotent():
    fields = ["k", "v"]
    existing = [{"k": "a", "v": "1"}, {"k": "b", "v": "2"}]
    produced = [{"k": "b", "v": "999"}, {"k": "c", "v": 3}]
    merged, added, kept = inc.upsert_new_keys(existing, produced, lambda r: (r["k"],), fields)
    assert [r["k"] for r in merged] == ["a", "b", "c"]
    assert merged[1]["v"] == "2"            # existing value never overwritten
    assert (added, kept) == (1, 1)
    again, added2, _ = inc.upsert_new_keys(merged, produced, lambda r: (r["k"],), fields)
    assert again == merged and added2 == 0


# ---------------------------------------------------------------------------- ssy

def _ssy_doc(fname, report_date, printed, change, points):
    return {
        "file": fname, "route": "ATLANTIC", "report_date": report_date,
        "check": {"printed_calculated_index": printed, "change_on_previous": change,
                  "series_last": points[-1][2]},
        "series": [{"year": "2026", "points": [
            {"date": "2026-SEP", "month_frac": mf, "index_value": v} for _, mf, v in points]}],
    }


def test_ssy_merge_new_only(tmp_path, monkeypatch):
    series = tmp_path / "series"
    charts = tmp_path / "charts"
    series.mkdir()
    charts.mkdir()
    monkeypatch.setattr(ssy, "OUT", series)
    old = {"route": "ATLANTIC", "base": "ATLANTIC-b3", "year": "2026", "month": "SEP", "bucket": "2",
           "n_reports": "5", "value": "100.0", "min": "90.0", "max": "110.0", "value_sd": "4.0"}
    inc.write_rows(series / ssy.CSV_NAME, ssy.CSV_COLS, [old])
    inc.write_rows(series / ssy.TIME_SERIES_NAME,
                   ["issue_date", "basin", "calculated_index_prev", "calculated_index_curr", "source_file"],
                   [{"issue_date": "2026-09-18", "basin": "Atlantic", "calculated_index_prev": "900",
                     "calculated_index_curr": "950", "source_file": "old.pdf"}])
    # bucket 2 == day 8..11 of SEP  (month_frac 8.2 -> day 7 -> bucket 1 ; 8.3 -> day 10 -> bucket 2)
    # printed 900 - change 0 = 900 == prior printed 900  => same base, no rebasing
    doc = _ssy_doc("new.pdf", "2026-09-25", 900.0, 0.0, [(0, 8.3, 555.0), (1, 8.9, 777.0)])
    (charts / "new.pdf.charts.json").write_text(json.dumps(doc), encoding="utf-8")

    ssy.merge_new_only(charts, series)
    rows = inc.read_rows(series / ssy.CSV_NAME)[1]
    by = {ssy.row_key(r): r for r in rows}
    assert by[("ATLANTIC-b3", "ATLANTIC", "2026", "SEP", "2")]["value"] == "100.0"   # kept
    assert ("ATLANTIC-b3", "ATLANTIC", "2026", "SEP", "7") in by                      # appended
    assert len(rows) == 2

    first = _bytes(series / ssy.CSV_NAME)
    ssy.merge_new_only(charts, series)
    assert _bytes(series / ssy.CSV_NAME) == first                                      # idempotent


def test_ssy_rebase_continues_base_number(tmp_path):
    existing = [{"route": "ATLANTIC", "base": "ATLANTIC-b3", "year": "2026", "month": "SEP",
                 "bucket": "2"}]
    ts = [{"issue_date": "2026-09-18", "basin": "Atlantic", "calculated_index_prev": "1000",
           "calculated_index_curr": "1100", "source_file": "old.pdf"}]
    docs = [(None, _ssy_doc("n.pdf", "2026-09-25", 5000.0, 10.0, [(0, 8.3, 1.0)]))]
    assert ssy.incremental_bases(docs, existing, ts)["n.pdf"] == "ATLANTIC-b4"        # 4990 vs 1000


# ---------------------------------------------------------------------------- intermodal

def test_intermodal_merge_new_only(tmp_path, monkeypatch):
    series = tmp_path / "series"
    charts = tmp_path / "charts"
    series.mkdir()
    charts.mkdir()
    monkeypatch.setattr(im, "OUT", series)
    inc.write_rows(series / im.CSV_NAME, im.CSV_COLS,
                   [{"series": "BDI", "date": "2026-08-31", "n_reports": "9", "value": "1000.0",
                     "min": "900.0", "max": "1100.0", "value_sd": "50.0"}])
    doc = {"file": "r.pdf", "charts": [{"series": [{"name": "BDI", "points": [
        {"date": "2026-08-31", "value": 4242.0}, {"date": "2026-09-30", "value": 1200.0}]}]}]}
    (charts / "r.pdf.charts.json").write_text(json.dumps(doc), encoding="utf-8")

    im.merge_new_only(charts, series)
    rows = inc.read_rows(series / im.CSV_NAME)[1]
    by = {im.row_key(r): r for r in rows}
    assert by[("BDI", "2026-08-31")]["value"] == "1000.0"                              # kept
    assert by[("BDI", "2026-09-30")]["value"] == "1200.0"                              # appended
    first = _bytes(series / im.CSV_NAME)
    im.merge_new_only(charts, series)
    assert _bytes(series / im.CSV_NAME) == first


# ---------------------------------------------------------------------------- xclusiv

def test_xclusiv_run_new_only(tmp_path, monkeypatch):
    series = tmp_path / "series"
    src = tmp_path / "corpus" / "2026"
    series.mkdir()
    src.mkdir(parents=True)
    (src / "a.pdf").write_bytes(b"old")
    (src / "b.pdf").write_bytes(b"new")
    inc.write_rows(series / xc.BC_SERIES_CSV.name, xc.FIELDS_BC,
                   [{"issue_date": "2026-09-28", "report_week": "39", "vessel_class": "Capesize 5TC",
                     "rate_usd_per_day": "1.0", "chart_page": "2", "source_file": "a.pdf"}])

    def fake_rows(p):
        d = "2026-09-28" if p.name == "a.pdf" else "2026-10-05"
        return ([{"issue_date": d, "report_week": 40, "vessel_class": "Capesize 5TC",
                  "rate_usd_per_day": 9.0, "chart_page": 2, "source_file": p.name}], [])

    monkeypatch.setattr(xc, "rows_for_pdf", fake_rows)
    xc.run_new_only(src=tmp_path / "corpus", series_dir=series)
    rows = inc.read_rows(series / xc.BC_SERIES_CSV.name)[1]
    assert [(r["issue_date"], r["rate_usd_per_day"]) for r in rows] == [
        ("2026-09-28", "1.0"), ("2026-10-05", "9.0")]
    first = _bytes(series / xc.BC_SERIES_CSV.name)
    xc.run_new_only(src=tmp_path / "corpus", series_dir=series)
    assert _bytes(series / xc.BC_SERIES_CSV.name) == first


# ---------------------------------------------------------------------------- ism

def _ism_row(date, value, edge, report):
    return {"date": date, "segment": "Coaster", "route_title": "R", "series_name": "S",
            "value": value, "unit": "$/t", "n_reports": "3", "value_edge": edge,
            "value_report": report, "min_value": "1.0", "max_value": "9.0", "value_sd": "0.5"}


def test_ism_upsert_appends_keeps_and_settles_provisional_edge_once():
    existing = [_ism_row("2026-09-14", "5.0", "0", "2026-09-14"),
                _ism_row("2026-09-21", "6.0", "1", "2026-09-21")]       # provisional edge
    produced = [_ism_row("2026-09-14", "5.5", "0", "2026-09-28"),       # restated: kept as-is
                _ism_row("2026-09-21", "6.4", "0", "2026-09-28"),       # settles the edge row
                _ism_row("2026-09-28", "7.0", "1", "2026-09-28")]       # new week
    merged, added, settled = ism.upsert_ism_rows(existing, produced)
    by = {r["date"]: r for r in merged}
    assert by["2026-09-14"]["value"] == "5.0"
    assert (by["2026-09-21"]["value"], by["2026-09-21"]["value_edge"], by["2026-09-21"]["n_reports"]) == ("6.4", "0", "6")
    assert by["2026-09-28"]["value"] == "7.0"
    assert (added, settled) == (1, 1)
    again, added2, settled2 = ism.upsert_ism_rows(merged, produced)
    assert again == merged and (added2, settled2) == (0, 0)
