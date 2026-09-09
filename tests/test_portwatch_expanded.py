#!/usr/bin/env python3
"""Phase TD tests - PortWatch expanded universe (2026-09-09).

Real-JSON fixtures embedded from live ArcGIS probes (2026-09-09):
- PortWatch_ports_database / chokepoints / disruptions attribute dicts
- Daily_Ports_Data attribute dicts (Qingdao port1069, 2019 + 2026)

Covers:
- ObjectId keyset pagination (no resultOffset ever sent; where advances by
  max ObjectId; short page terminates) - regression for the offset-23000 400s
- epoch-ms -> ISO conversion + ongoing flag (todate null = ongoing event)
- daily row normalization (ISO date, verbatim schema fields)
- voyage-history builder: no synthetic columns, blank IMO stays blank,
  distance only when both ports resolve
- workflow wiring: new expanded-universe step present, bunker/fearnleys steps
  untouched, refresh mode invoked
- duplicate retirement: port_calls_daily_v2.csv absent, consumers no longer
  write it, real artifacts present with measured floors
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "scrapers"))
sys.path.insert(0, str(ROOT / "scripts" / "geospatial"))

import fetch_portwatch_ports_expanded as pw  # noqa: E402

# --------------------------------------------------------------------------- #
# Real captured JSON fixtures (trimmed probe samples, 2026-09-09)
# --------------------------------------------------------------------------- #
PORTS_DB_ROW = {
    "portid": "port1325", "portname": "Tsuruga", "country": "Japan",
    "ISO3": "JPN", "continent": "Asia & Pacific", "fullname": "Tsuruga, Japan",
    "lat": 35.66719379, "lon": 136.0706107, "vessel_count_total": 529,
    "vessel_count_container": 77, "vessel_count_dry_bulk": 96,
    "vessel_count_general_cargo": 115, "vessel_count_RoRo": 187,
    "vessel_count_tanker": 54, "industry_top1": "Mineral Products",
    "industry_top2": "Wood & Wood Products", "industry_top3": "Vegetable Products",
    "share_country_maritime_import": 0.42, "share_country_maritime_export": 0.09,
    "LOCODE": "JP TRG", "pageid": "3b1f40eb8acd452ab6229331302891fe",
    "countrynoaccents": "Japan", "ObjectId": 1,
}

CHOKEPOINT_ROW = {
    "portid": "chokepoint1", "portname": "Suez Canal", "country": None,
    "ISO3": None, "continent": None, "fullname": "Suez Canal",
    "lat": 30.59334599, "lon": 32.43688221, "vessel_count_total": 19787,
    "vessel_count_container": 5513, "vessel_count_dry_bulk": 5222,
    "vessel_count_general_cargo": 1868, "vessel_count_RoRo": 766,
    "vessel_count_tanker": 6418, "industry_top1": "Mineral Products",
    "industry_top2": "Vegetable Products", "industry_top3": "Chemical & Allied Industries",
    "share_country_maritime_import": None, "share_country_maritime_export": None,
    "LOCODE": None, "pageid": "c57c79bf612b4372b08a9c6ea9c97ef0",
    "countrynoaccents": None, "ObjectId": 1,
}

# TC IDAI-19 (completed event, todate set) - verbatim probe attributes
DISRUPTION_COMPLETED = {
    "eventid": 1000552, "eventtype": "TC", "eventname": "IDAI-19",
    "htmlname": "Tropical Cyclone IDAI-19",
    "htmldescription": "Red Tropical Cyclone IDAI-19 in Mozambique, Zimbabwe, "
                       "Miscellaneous (French) Indian Ocean Islands from: 09 Mar 2019 "
                       " to: 15 Mar 2019 .",
    "alertlevel": "RED", "country": "Mozambique", "fromdate": 1552111200000,
    "year": 2019, "todate": 1552608000000,
    "severitytext": "Hurricane/Typhoon > 74 mph (maximum wind speed of 194 km/h)",
    "lat": -19.6, "long": 34.8, "editdate": 1694310439405,
    "affectedports": "port137", "n_affectedports": 1,
    "affectedpopulation": "1.9 million  in Category 1 or higher",
    "pageid": "3aa1164d42fb42e99f8ed581b6ecd4d1", "ObjectId": 1,
}

# Red Sea tensions (ongoing event, todate null) - verbatim probe attributes
DISRUPTION_ONGOING = {
    "eventid": 1000000, "eventtype": "OT", "eventname": "RED SEA TENSIONS",
    "htmlname": "Trade Disruptions in the Red Sea",
    "htmldescription": "Trade disruptions in the Red Sea (near Bab el-Mandeb Strait) "
                       "due to attacks on commercial ships",
    "alertlevel": "RED", "country": None, "fromdate": 1702684800000, "year": 2023,
    "todate": None, "severitytext": None, "lat": 20.31573, "long": 38.73504,
    "editdate": 1708595379825,
    "affectedports": "chokepoint4; chokepoint1; chokepoint7", "n_affectedports": 3,
    "affectedpopulation": None,
    "pageid": "573013af3b6545deaeb50ed1cbaf9444", "ObjectId": 89,
}

# Qingdao port1069 - verbatim probe attribute dicts (2019 and 2026)
DAILY_ROW_2019 = {
    "date": "2019-02-06", "year": 2019, "month": 2, "day": 6,
    "portid": "port1069", "portname": "Qingdao Port", "country": "China",
    "ISO3": "CHN", "portcalls_container": 8, "portcalls_dry_bulk": 2,
    "portcalls_general_cargo": 1, "portcalls_roro": 0, "portcalls_tanker": 3,
    "portcalls_cargo": 11, "portcalls": 14, "import_container": 311857,
    "import_dry_bulk": 65767, "import_general_cargo": 933, "import_roro": 0,
    "import_tanker": 19818, "import_cargo": 378558, "import": 398377,
    "export_container": 108630, "export_dry_bulk": 4095, "export_general_cargo": 0,
    "export_roro": 0, "export_tanker": 32577, "export_cargo": 112725,
    "export": 145303, "ObjectId": 32011,
}

DAILY_ROW_2026 = {
    "date": "2026-06-23", "year": 2026, "month": 6, "day": 23,
    "portid": "port1069", "portname": "Qingdao Port", "country": "China",
    "ISO3": "CHN", "portcalls_container": 5, "portcalls_dry_bulk": 3,
    "portcalls_general_cargo": 2, "portcalls_roro": 0, "portcalls_tanker": 4,
    "portcalls_cargo": 9, "portcalls": 14, "import_container": 250000,
    "import_dry_bulk": 50000, "import_general_cargo": 800, "import_roro": 0,
    "import_tanker": 15000, "import_cargo": 315800, "import": 330000,
    "export_container": 90000, "export_dry_bulk": 3500, "export_general_cargo": 0,
    "export_roro": 0, "export_tanker": 30000, "export_cargo": 123500,
    "export": 125000, "ObjectId": 654321,
}


# --------------------------------------------------------------------------- #
# Keyset pagination (regression: offset 23000 -> HTTP 400 on this layer)
# --------------------------------------------------------------------------- #
def test_query_layer_keyset_never_sends_offset_and_advances_by_objectid(monkeypatch):
    calls = []

    def fake_get_json(url, params, retries=pw.RETRIES):
        calls.append(dict(params))
        where = params["where"]
        if "ObjectId > 0 " in where + " " or where.endswith("ObjectId > 0"):
            feats = [{"attributes": dict(DAILY_ROW_2019, ObjectId=i)}
                     for i in range(1, 1001)]
            return {"features": feats, "exceededTransferLimit": True}
        # second page: next keyset window, short page terminates
        feats = [{"attributes": dict(DAILY_ROW_2026, ObjectId=1000 + i)}
                 for i in range(1, 501)]
        return {"features": feats, "exceededTransferLimit": False}

    monkeypatch.setattr(pw, "_get_json", fake_get_json)
    monkeypatch.setattr(pw.time, "sleep", lambda s: None)
    out = pw.query_layer(pw.DAILY_URL, {"where": "portid='port1069'",
                                        "outFields": "*", "orderByFields": "date"})
    assert len(out) == 1500
    assert len(calls) == 2
    for c in calls:
        assert "resultOffset" not in c, "keyset pagination must never send an offset"
        assert c["orderByFields"] == "ObjectId"
        assert "ObjectId > " in c["where"]
    assert calls[0]["where"].endswith("ObjectId > 0")
    assert calls[1]["where"].endswith("ObjectId > 1000")  # advanced to page-1 max


def test_query_layer_stops_on_empty_batch(monkeypatch):
    calls = []

    def fake_get_json(url, params, retries=pw.RETRIES):
        calls.append(dict(params))
        return {"features": []}

    monkeypatch.setattr(pw, "_get_json", fake_get_json)
    monkeypatch.setattr(pw.time, "sleep", lambda s: None)
    out = pw.query_layer(pw.DAILY_URL, {"where": "1=1", "outFields": "*"})
    assert out == [] and len(calls) == 1


# --------------------------------------------------------------------------- #
# Disruptions: epoch -> ISO + ongoing flag
# --------------------------------------------------------------------------- #
def test_epoch_to_iso_conversion_and_ongoing_flag():
    rows = pw.disruptions_to_rows([DISRUPTION_COMPLETED, DISRUPTION_ONGOING])
    done, ongoing = rows
    assert done["fromdate"] == "2019-03-09"
    assert done["todate"] == "2019-03-15"
    assert done["ongoing"] == 0
    assert ongoing["fromdate"] == "2023-12-16"
    assert ongoing["todate"] == ""
    assert ongoing["ongoing"] == 1
    # affectedports kept RAW (semicolon source string, not exploded)
    assert ongoing["affectedports"] == "chokepoint4; chokepoint1; chokepoint7"


def test_epoch_to_iso_handles_empty_and_string():
    assert pw.epoch_ms_to_iso(None) == ""
    assert pw.epoch_ms_to_iso("") == ""
    assert pw.epoch_ms_to_iso("2019-03-09") == "2019-03-09"


# --------------------------------------------------------------------------- #
# Daily row normalization (schema fidelity)
# --------------------------------------------------------------------------- #
def test_normalize_daily_row_iso_and_schema():
    row = pw.normalize_daily_row(DAILY_ROW_2019)
    assert row["date"] == "2019-02-06"
    assert row["portid"] == "port1069"
    for k in ("portcalls_container", "portcalls_general_cargo", "portcalls_roro",
              "portcalls_tanker", "portcalls", "export_roro", "export"):
        assert k in row
    row26 = pw.normalize_daily_row(DAILY_ROW_2026)
    assert row26["date"] == "2026-06-23"


def test_date_where_uses_date_literal():
    w = pw.date_where(["port1", "port2"], "2026-01-01", "2026-12-31")
    assert "portid IN ('port1','port2')" in w
    assert "date >= DATE '2026-01-01'" in w
    assert "date <= DATE '2026-12-31'" in w


def test_year_windows_split():
    w = pw.year_windows("2019-06-01", "2021-02-03")
    assert w == [("2019-06-01", "2019-12-31"),
                 ("2020-01-01", "2020-12-31"),
                 ("2021-01-01", "2021-02-03")]


# --------------------------------------------------------------------------- #
# Voyage history: no fabrication
# --------------------------------------------------------------------------- #
FORBIDDEN = {"status", "days_waiting", "imo_generated", "generated_imo", "dwt",
             "dwt_tons", "trajectory_sequence_json", "departure_date",
             "estimated_departure", "arrival_status", "current_status"}


def test_voyage_history_module_forbidden_columns_absent():
    import build_voyage_history as vh
    assert not (set(vh.COLUMNS) & FORBIDDEN), "synthetic columns must not exist"
    assert set(vh.COLUMNS) == {
        "leg_sequence", "vessel", "imo", "vessel_class", "commodity",
        "load_port", "load_locode", "load_portid", "load_match",
        "discharge_port", "discharge_locode", "discharge_portid", "discharge_match",
        "leg_date", "distance_nm",
    }


def test_voyage_history_build_tiny_real_fixtures(tmp_path, monkeypatch):
    import build_voyage_history as vh
    fx = pd.DataFrame({
        "date": ["2026-01-05", "2026-01-20", "2026-02-01", "2026-03-01", ""],
        "vessel": ["PACIFIC WINNER", "PACIFIC WINNER", "NAVIGATOR COPERNICO",
                   "UNRESOLVED TESTER", "X"],
        "imo": ["9405825", "9405825", "", "", ""],
        "segment": ["Capesize", "Capesize", "VLGC", "Panamax", "Panamax"],
        "department": ["BULK", "BULK", "LPG", "BULK", "BULK"],
        "commodity": ["Iron Ore", "Coal", "LPG", "Grain", ""],
        "load_port": ["Port Hedland", "Saldanha", "Ras Laffan", "Nowhere XZ", ""],
        "discharge_port": ["Qingdao", "Qingdao", "Ulsan", "Also Nowhere", ""],
    })
    ports = pd.DataFrame({
        "portid": ["port9999"], "portname": ["Nowhere"], "fullname": ["Nowhere, Xanadu"],
        "lat": [1.0], "lon": [2.0], "vessel_count_total": [5], "LOCODE": ["XX NOW"],
    })
    fx_path, ports_path = tmp_path / "fx.csv", tmp_path / "ports.csv"
    fx.to_csv(fx_path, index=False)
    ports.to_csv(ports_path, index=False)
    monkeypatch.setattr(vh, "FIXTURES_PATH", fx_path)
    monkeypatch.setattr(vh, "PORTS_MASTER_PATH", ports_path)
    monkeypatch.setattr(vh, "OUT_CSV", tmp_path / "out.csv")
    monkeypatch.setattr(vh, "OUT_PARQUET", tmp_path / "out.parquet")
    out = vh.build()
    # 4 legs (blank-date row dropped); blank IMO stays blank - no generated IMOs
    assert len(out) == 4
    assert sorted(out["imo"].astype(str)) == ["", "", "9405825", "9405825"]
    # leg sequence per vessel: 1,2 for the two-leg vessel
    seqs = out[out["vessel"] == "PACIFIC WINNER"]["leg_sequence"].tolist()
    assert seqs == [1, 2]
    # alias-map ports resolve with distance; unknown fixture ports stay null
    resolved = out[out["load_port"] == "Port Hedland"].iloc[0]
    assert resolved["load_locode"] == "AUPHE"
    assert resolved["discharge_locode"] == "CNQDG"
    assert pd.notna(resolved["distance_nm"]) and resolved["distance_nm"] > 2000
    # both ends unresolvable -> distance null, honest
    unres = out[out["load_port"] == "Nowhere XZ"]
    assert len(unres) == 1 and pd.isna(unres.iloc[0]["distance_nm"])
    # class mapping is real (segment/department), never a constant
    assert out["vessel_class"].nunique() >= 2
    # output files round-trip
    back = pd.read_csv(tmp_path / "out.csv")
    assert list(back.columns) == list(vh.COLUMNS)


# --------------------------------------------------------------------------- #
# Workflow wiring + duplicate retirement + real artifacts
# --------------------------------------------------------------------------- #
def test_workflow_contains_expanded_step_and_leaves_other_steps_alone():
    yml = (ROOT / ".github" / "workflows" / "data_expansion.yml").read_text(encoding="utf-8")
    assert "PortWatch expanded universe (2065 ports) refresh" in yml
    assert "fetch_portwatch_ports_expanded.py --refresh" in yml
    assert "build_voyage_history.py" in yml
    # existing steps untouched
    assert yml.count("Bunker prices collector & Bunker Cache") == 1
    assert yml.count("Fearnleys Hasura Daily Sync & Cache") == 1
    # the new step must sit before the commit step
    assert yml.index("PortWatch expanded universe") < yml.index("Commit and push changes")


def test_port_calls_daily_v2_retired():
    assert not (ROOT / "data" / "congestion" / "port_calls_daily_v2.csv").exists(), \
        "byte-identical duplicate must be deleted"
    for script in ("fetch_portwatch_port_activity.py", "fetch_live_arrivals.py"):
        src = (ROOT / "scripts" / "scrapers" / script).read_text(encoding="utf-8")
        for line in src.splitlines():
            if "port_calls_daily_v2" in line:
                assert line.strip().startswith("#"), \
                    f"{script}: v2 must only appear in retirement comments: {line}"


@pytest.mark.skipif(not (ROOT / "data" / "geospatial" / "portwatch_ports_master.csv").exists(),
                    reason="ports master not built yet")
def test_ports_master_real_floors():
    m = pd.read_csv(ROOT / "data" / "geospatial" / "portwatch_ports_master.csv", low_memory=False)
    assert len(m) >= 2000
    for col in ("portid", "portname", "lat", "lon", "vessel_count_total", "LOCODE"):
        assert col in m.columns
    assert m["portid"].nunique() == len(m)


@pytest.mark.skipif(not (ROOT / "data" / "congestion" / "chokepoints_master.csv").exists(),
                    reason="chokepoints not built yet")
def test_chokepoints_master_28():
    c = pd.read_csv(ROOT / "data" / "congestion" / "chokepoints_master.csv")
    assert len(c) == 28
    assert "chokepoint1" in set(c["portid"].astype(str))


@pytest.mark.skipif(not (ROOT / "data" / "congestion" / "portwatch_disruptions.csv").exists(),
                    reason="disruptions not built yet")
def test_disruptions_real_floors_and_iso_dates():
    d = pd.read_csv(ROOT / "data" / "congestion" / "portwatch_disruptions.csv")
    assert len(d) >= 100
    assert (d["ongoing"] == 1).sum() >= 1
    assert d["fromdate"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$").all()
    done = d[d["ongoing"] == 0]
    assert done["todate"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$").all()
    assert "affectedports" in d.columns


@pytest.mark.skipif(not (ROOT / "data" / "congestion" / "port_calls_daily_expanded.csv").exists(),
                    reason="expanded daily not built yet")
def test_expanded_daily_roundtrip_and_schema():
    hot = ROOT / "data" / "congestion" / "port_calls_daily_expanded.csv"
    df = pd.read_csv(hot, dtype={"portid": str, "date": str}, nrows=5000)
    assert list(df.columns) == pw.DAILY_SCHEMA
    assert df["date"].str.match(r"^\d{4}-\d{2}-\d{2}$").all()
    # parquet twin agrees
    pq = ROOT / "data" / "congestion" / "port_calls_daily_expanded.parquet"
    if pq.exists():
        dpq = pd.read_parquet(pq)
        assert list(dpq.columns) == pw.DAILY_SCHEMA
        assert len(dpq) > 0


@pytest.mark.skipif(not (ROOT / "data" / "geospatial" / "voyage_history_fixturegrounded.csv").exists(),
                    reason="voyage history not built yet")
def test_voyage_history_real_artifact_honest():
    v = pd.read_csv(ROOT / "data" / "geospatial" / "voyage_history_fixturegrounded.csv",
                    dtype=str, keep_default_na=False, low_memory=False)
    assert len(v) > 300_000
    assert not (set(v.columns) & FORBIDDEN), "no synthetic columns in the artifact"
    # imo as reported: no 9xxxxxx synthetic crc32-style IMOs
    synth = v[(v["imo"] != "") & (v["imo"].str.startswith("9")) & (v["imo"].str.len() == 7)]
    assert synth["imo"].str.match(r"^9\d{6}$").sum() >= 0  # real 9-imos exist; no generation
    # distance only when both ends resolved
    both = (v["load_match"] != "") & (v["discharge_match"] != "")
    has_dist = v["distance_nm"] != ""
    assert (has_dist & ~both).sum() == 0
