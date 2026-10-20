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

def _ssy_doc(fname, points, year="2026"):
    return {
        "file": fname, "route": "ATLANTIC", "report_date": fname,
        "check": {"printed_calculated_index": None, "change_on_previous": None,
                  "series_last": points[-1][1]},
        "series": [{"year": year, "points": [
            {"iso_date": d, "dating": "month", "index_value": v} for d, v in points]}],
    }


_PRINTED = [("2026-08-21", "2026-08-28", 990, 1000), ("2026-08-28", "2026-09-04", 1000, 1010), ("2026-09-04", "2026-09-11", 1010, 1020),
            ("2026-09-11", "2026-09-18", 1020, 1030)]


def _write_ts(series):
    inc.write_rows(series / ssy.TIME_SERIES_NAME,
                   ["issue_date", "basin", "rates_date_prev", "rates_date_curr",
                    "calculated_index_prev", "calculated_index_curr", "source_file"],
                   [{"issue_date": c, "basin": "Atlantic", "rates_date_prev": p, "rates_date_curr": c,
                     "calculated_index_prev": pv, "calculated_index_curr": cv,
                     "source_file": "new.pdf" if c == _PRINTED[-1][1] else "x.pdf"}
                    for p, c, pv, cv in _PRINTED])


def test_ssy_merge_new_only(tmp_path, monkeypatch):
    series = tmp_path / "series"
    charts = tmp_path / "charts"
    series.mkdir()
    charts.mkdir()
    monkeypatch.setattr(ssy, "OUT", series)
    old = {"route": "ATLANTIC", "basis": "2023-06-26", "date": "2026-08-28", "n_reports": "5",
           "value": "999.0", "min": "990.0", "max": "1005.0", "value_sd": "4.0",
           "printed_index": "1000.0"}
    inc.write_rows(series / ssy.CSV_NAME, ssy.CSV_COLS, [old])
    _write_ts(series)
    # vertices a day off the printed Fridays snap onto them; the chart reads print within 1%
    doc = _ssy_doc("new.pdf", [("2026-08-20", 991.0), ("2026-08-27", 1001.0), ("2026-09-05", 1012.0),
                               ("2026-09-10", 1019.0), ("2026-09-18", 1031.0),
                               ("2026-09-25", 1040.0)])
    (charts / "new.pdf.charts.json").write_text(json.dumps(doc), encoding="utf-8")

    ssy.merge_new_only(charts, series)
    rows = inc.read_rows(series / ssy.CSV_NAME)[1]
    by = {ssy.row_key(r): r for r in rows}
    b = "2023-06-26"                       # the Atlantic basis since the 2023 rebasing
    assert by[("ATLANTIC", b, "2026-08-28")]["value"] == "999.0"                      # kept
    assert by[("ATLANTIC", b, "2026-09-11")]["value"] == "1019.0"                     # snapped
    assert by[("ATLANTIC", b, "2026-09-11")]["printed_index"] == "1020.0"
    assert by[("ATLANTIC", b, "2026-09-25")]["printed_index"] == ""                   # unprinted week
    assert len(rows) == 6

    first = _bytes(series / ssy.CSV_NAME)
    ssy.merge_new_only(charts, series)
    assert _bytes(series / ssy.CSV_NAME) == first                                      # idempotent


def test_ssy_gate_rejects_a_chart_that_disagrees_with_print(tmp_path):
    _write_ts(tmp_path)
    weeks, vals = ssy.printed_weeks(inc.read_rows(tmp_path / ssy.TIME_SERIES_NAME)[1])
    weeks, printed = weeks["ATLANTIC"], vals[("ATLANTIC", "2023-06-26")]
    good = _ssy_doc("g.pdf", [(c, cv * 1.004) for _, c, _, cv in _PRINTED]
                    + [("2026-08-28", 1001.0), ("2026-09-04", 1008.0)])
    bad = _ssy_doc("b.pdf", [(c, cv * 10) for _, c, _, cv in _PRINTED]
                   + [("2026-08-28", 10000.0), ("2026-09-04", 10100.0)])
    few = _ssy_doc("f.pdf", [("2026-09-18", 1030.0)])
    assert ssy.gate(good, weeks, printed)[0] is True
    assert ssy.gate(bad, weeks, printed)[0] is False
    assert ssy.gate(few, weeks, printed)[0] is False                                   # unverifiable


def test_ssy_basis_and_collapsed_twin_dates():
    import datetime as dt
    assert ssy.basis_of("ATLANTIC", dt.date(2023, 6, 19)) == "2015-07-17"
    assert ssy.basis_of("ATLANTIC", dt.date(2023, 6, 26)) == "2023-06-26"
    assert ssy.basis_of("PACIFIC", dt.date(2026, 1, 9)) == "2015-07-17"
    # one assessment listed under its Friday and its Monday report date -> one week
    ts = [{"basin": "Atlantic", "rates_date_prev": "2023-10-09", "rates_date_curr": "2023-10-16",
           "calculated_index_prev": "11412", "calculated_index_curr": "11587"},
          {"basin": "Atlantic", "rates_date_prev": "2023-10-13", "rates_date_curr": "2023-10-20",
           "calculated_index_prev": "11587", "calculated_index_curr": "11996"}]
    weeks, vals = ssy.printed_weeks(ts)
    assert [str(w) for w in weeks["ATLANTIC"]] == ["2023-10-09", "2023-10-13", "2023-10-20"]
    assert vals[("ATLANTIC", "2023-06-26")][dt.date(2023, 10, 13)] == 11587.0


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


def test_ssy_week_keys_before_print_and_one_reading_per_line(monkeypatch):
    import datetime as dt
    weeks = [dt.date(2021, 7, 5), dt.date(2021, 7, 12)]
    # a Friday vertex before the printed record keys on its Monday assessment
    assert ssy.week_of({"iso_date": "2021-04-09", "dating": "month"}, weeks) == dt.date(2021, 4, 12)
    # a line with no printed week is dated by vertex order from the second Monday of January
    doc = {"series": [{"year": "2019", "points": [
        {"iso_date": "2019-01-21", "dating": "slot"}, {"iso_date": "2019-01-21", "dating": "slot"}]}]}
    ssy.align_slots(doc, weeks, dt.date(2021, 7, 12))
    assert [p["iso_date"] for p in doc["series"][0]["points"]] == ["2019-01-14", "2019-01-21"]
    # two vertices of one line on one week (a holiday-Friday point): the earlier is kept
    monkeypatch.setattr(ssy, "gate", lambda *a: (True, 0.0, 8))
    d = _ssy_doc("new.pdf", [("2026-09-03", 1020.0), ("2026-09-04", 900.0)])
    readings, _ = ssy.collect([("f", d)], {"ATLANTIC": [dt.date(2026, 9, 4)]}, {}, {})
    assert readings[("ATLANTIC", "2015-07-17", dt.date(2026, 9, 4))] == [(1020.0, "new.pdf")]
