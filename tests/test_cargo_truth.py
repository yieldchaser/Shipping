#!/usr/bin/env python3
"""
tests/test_cargo_truth.py
=========================
Cargo & Trade Flows: every plotted number must trace to a published source.

Guards the defects found 2026-09-13:
- fetch_eia_petroleum_exports.py wrote a "PADD 3" column as US total x 0.92 and a
  "total petroleum" column as US total x 2.45;
- build_cargo_cache.py read a renamed EIA column and shipped an all-zero envelope;
- the US Gulf grain flagship volume was a generated 4.2 + (i % 5) * 0.35 sawtooth;
- Guinea bauxite was paired with Panamax P1A_82, a route unrelated to that trade;
- UN Comtrade's 2017 China-Guinea months (11% of Guinea's exports) were plotted.
"""

import csv
import itertools
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
COMMODITIES = ROOT / "data" / "commodities"
SUMMARY = ROOT / "data" / "cargo" / "cargo_frontend_summary.json"


def _summary():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_no_commodity_column_is_a_fixed_multiple_or_offset_of_another():
    """A column that is always k x, or always k + another column is a formula, not an
    observation. Found 2026-09-13: EIA "PADD 3" = US x 0.92, Paranagua = Santos + 1.25,
    Gulf-China = Gulf-Japan + 2.50, PNW-China = PNW-Japan + 1.80. Only time series are
    checked: a single day's forward curve legitimately holds near-constant spreads."""
    hits = []
    for f in sorted(COMMODITIES.glob("*.csv")):
        df = pd.read_csv(f, low_memory=False)
        if "date" not in df.columns or df["date"].nunique() < 24:
            continue
        num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
               and df[c].notna().sum() >= 24 and df[c].nunique() >= 10]
        for a, b in itertools.combinations(num, 2):
            x = df[[a, b]].dropna()
            x = x[(x[a] != 0) & (x[b] != 0)]
            if len(x) < 24:
                continue
            r = x[b] / x[a]
            k = r.median()
            if k == 0 or abs(k - 1) < 1e-9:
                continue
            # Share of rows within 0.5% of one constant ratio; rounding a derived
            # column to 1 dp scatters it a little (0.919-0.921), so exact matching misses it.
            share = ((r / k - 1).abs() < 0.005).mean()
            if share > 0.9:
                hits.append((f.name, a, b, "x", round(float(k), 4), round(float(share), 2)))
            d = (x[b] - x[a]).round(2)
            top = d.value_counts()
            if top.index[0] != 0 and top.iloc[0] / len(d) > 0.8:
                hits.append((f.name, a, b, "+", float(top.index[0]), round(float(top.iloc[0] / len(d)), 2)))
    assert not hits, f"columns that are fixed multiples of another column: {hits}"


def test_eia_export_envelope_is_built_from_the_real_series():
    rows = list(csv.DictReader((COMMODITIES / "us_eia_weekly_crude_exports.csv").open(encoding="utf-8")))
    assert set(rows[0]) == {"date", "us_total_crude_exports_kbpd", "crude_4w_avg_kbpd"}, rows[0].keys()
    env = _summary()["us_crude_exports"]["envelope"]
    assert env["years"], "EIA envelope has no years"
    latest = max(r["date"] for r in rows)
    assert env["latest_year"] == str(__import__("datetime").date.fromisoformat(latest).isocalendar()[0])
    from datetime import date
    by_week = {}
    for r in rows:
        y, w, _ = date.fromisoformat(r["date"]).isocalendar()
        by_week[(str(y), w)] = float(r["us_total_crude_exports_kbpd"])
    checked = 0
    for y, vals in env["years"].items():
        for i, v in enumerate(vals):
            if v is None:
                continue
            assert abs(v - by_week[(y, i + 1)]) < 0.01, (y, i + 1, v, by_week[(y, i + 1)])
            checked += 1
    assert checked > 100
    assert any(m for m in env["mean"] if m), "EIA 5Y mean is all zero"


def test_us_gulf_grain_volume_is_usda_monthly_sums():
    mt, weeks = defaultdict(float), defaultdict(set)
    for r in csv.DictReader((COMMODITIES / "usda_ytd_grain_inspections_top20.csv").open(encoding="utf-8", errors="ignore")):
        if (r.get("ams_reg") or "").strip() == "GULF":
            mt[r["date"][:7]] += float(r["mt"] or 0)
            weeks[r["date"][:7]].add(r["date"][:10])
    pair = _summary()["flagship_pairs"]["usg_grain"]
    plotted = 0
    for m, v in zip(pair["months"], pair["volume_data"]):
        expected = round(mt[m] / 1e6, 2) if len(weeks[m]) >= 4 else None
        assert v == expected, f"{m}: plotted {v}, USDA monthly sum {expected}"
        plotted += v is not None
    assert plotted >= 12


def test_guinea_is_volume_only_and_traces_to_its_csv():
    s = _summary()
    pair = s["flagship_pairs"]["guinea_cape"]
    assert pair["route_code"] is None and pair["freight_unit"] is None
    assert all(v is None for v in pair["freight_data"]), "Guinea bauxite must not be paired with an unrelated route"

    gb = s["guinea_bauxite"]
    excluded = {e["year"] for e in gb["provenance"].get("excluded_mirror_years", [])}
    # 2017 was previously excluded when it was UN Comtrade undercount (4.8 Mt); now rebuilt from official GACC (27.6 Mt, 64% of national exports)
    assert "2017" not in excluded
    mirror = {}
    for r in csv.DictReader((COMMODITIES / "guinea_bauxite_exports.csv").open(encoding="utf-8")):
        if r["granularity"] == "monthly_bilateral_mirror":
            mirror[r["date"][:7]] = round(float(r["tonnes"]) / 1e6, 2)
            if "metal.com" in r["source_url"]:
                mil = f"{float(r['tonnes']) / 1e6:g}"
                assert mil in r["source_quote"], f"{r['date']}: {mil} not in quote {r['source_quote']!r}"
    expected = {m: v for m, v in mirror.items() if m[:4] not in excluded}
    assert gb["monthly_volume_mt"] == expected
    for m, v in zip(pair["months"], pair["volume_data"]):
        assert v == expected.get(m), m
