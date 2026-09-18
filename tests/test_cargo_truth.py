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


def test_argentina_grain_exports_integrity_and_reconciliation():
    """
    P0 Regression Guard:
    Every row of argentina_grain_exports_monthly.csv must reconcile:
    1. Continuous 55 months from 2022-01-01 to 2026-07-01 with zero gaps.
    2. No individual crop component exceeds the total grain volume.
    3. Sum of components reconciles within tolerance [65%, 105%] of total.
    4. Port basin breakdown (Up-River + Deepwater) reconciles within 2% of total.
    5. Up-river share is realistic (50%–95%).
    6. Specific audited invariant: 2026-07 must be 8.101 Mt (corn 4.531 Mt, 8 active terminals).
    7. Specific audited invariant: 2025-10 must be 6.755 Mt (curing the 0.068 Mt corruption).
    """
    df_monthly = pd.read_csv(COMMODITIES / "argentina_grain_exports_monthly.csv")
    assert len(df_monthly) == 55, f"Expected exactly 55 months, got {len(df_monthly)}"
    assert df_monthly["date"].is_monotonic_increasing, "Monthly dates must be strictly monotonic increasing"
    assert df_monthly["date"].iloc[0] == "2022-01-01", f"First month is {df_monthly['date'].iloc[0]}, expected 2022-01-01"
    assert df_monthly["date"].iloc[-1] == "2026-07-01", f"Last month is {df_monthly['date'].iloc[-1]}, expected 2026-07-01"

    assert "other_grains_mt" in df_monthly.columns, "argentina_grain_exports_monthly.csv must have other_grains_mt column"
    crops = ["corn_mt", "wheat_mt", "soybeans_mt", "soymeal_pellets_mt", "barley_mt", "sorghum_mt", "sunflower_mt", "other_grains_mt"]
    for _, row in df_monthly.iterrows():
        dt = row["date"]
        tot = float(row["total_grain_mt"])
        assert tot > 0, f"{dt}: non-positive total {tot}"

        # No crop exceeds total
        for c in crops:
            cval = float(row.get(c, 0.0))
            assert cval <= tot, f"{dt}: {c} ({cval} Mt) exceeds total ({tot} Mt)"

        # Strict component sum check (tolerance <= 0.5%, except documented 2022-06 MAGyP subtotal print typo of 1.58%)
        c_sum = sum(float(row.get(c, 0.0)) for c in crops)
        thresh = 0.016 if dt == "2022-06-01" else 0.005
        assert abs(c_sum - tot) / tot <= thresh, f"{dt}: component sum ({c_sum:.3f} Mt) diverges from total ({tot:.3f} Mt) by > {thresh*100:.1f}%"

        # Port basin check
        up = float(row.get("up_river_parana_mt", 0.0))
        ocean = float(row.get("ocean_deepwater_mt", 0.0))
        basin_sum = up + ocean
        assert abs(basin_sum - tot) / tot <= 0.02, f"{dt}: basin sum ({basin_sum:.3f} Mt) diverges from total ({tot:.3f} Mt) by > 2%"

        up_share = float(row.get("up_river_share_pct", 0.0))
        assert 50.0 <= up_share <= 95.0, f"{dt}: anomalous up-river share {up_share}%"

    # Invariant: July 2026 ground-truth verification
    row_jul26 = df_monthly[df_monthly["date"] == "2026-07-01"].iloc[0]
    assert abs(float(row_jul26["total_grain_mt"]) - 8.101) < 0.01, f"July 2026 total was {row_jul26['total_grain_mt']}, expected 8.101"
    assert abs(float(row_jul26["corn_mt"]) - 4.531) < 0.01, f"July 2026 corn was {row_jul26['corn_mt']}, expected 4.531"
    assert abs(float(row_jul26["soymeal_pellets_mt"]) - 2.031) < 0.01, f"July 2026 soymeal was {row_jul26['soymeal_pellets_mt']}, expected 2.031"
    assert abs(float(row_jul26["wheat_mt"]) - 0.671) < 0.01, f"July 2026 wheat was {row_jul26['wheat_mt']}, expected 0.671"
    assert abs(float(row_jul26["up_river_share_pct"]) - 82.01) < 0.1, f"July 2026 up-river share was {row_jul26['up_river_share_pct']}, expected 82.01"

    # Invariant: July 2025 ground-truth verification
    row_jul25 = df_monthly[df_monthly["date"] == "2025-07-01"].iloc[0]
    assert abs(float(row_jul25["total_grain_mt"]) - 8.397) < 0.01, f"July 2025 total was {row_jul25['total_grain_mt']}, expected 8.397"
    assert abs(float(row_jul25["corn_mt"]) - 3.499) < 0.01, f"July 2025 corn was {row_jul25['corn_mt']}, expected 3.499"
    assert abs(float(row_jul25["wheat_mt"]) - 0.564) < 0.01, f"July 2025 wheat was {row_jul25['wheat_mt']}, expected 0.564"
    assert abs(float(row_jul25["soybeans_mt"]) - 1.445) < 0.01, f"July 2025 soybeans was {row_jul25['soybeans_mt']}, expected 1.445"
    assert abs(float(row_jul25["soymeal_pellets_mt"]) - 2.294) < 0.01, f"July 2025 soymeal was {row_jul25['soymeal_pellets_mt']}, expected 2.294"

    # Invariant: August 2025 ground-truth verification
    row_ago25 = df_monthly[df_monthly["date"] == "2025-08-01"].iloc[0]
    assert abs(float(row_ago25["total_grain_mt"]) - 8.391) < 0.01, f"August 2025 total was {row_ago25['total_grain_mt']}, expected 8.391"
    assert abs(float(row_ago25["corn_mt"]) - 2.447) < 0.01, f"August 2025 corn was {row_ago25['corn_mt']}, expected 2.447"
    assert abs(float(row_ago25["wheat_mt"]) - 0.865) < 0.01, f"August 2025 wheat was {row_ago25['wheat_mt']}, expected 0.865"
    assert abs(float(row_ago25["soybeans_mt"]) - 1.519) < 0.01, f"August 2025 soybeans was {row_ago25['soybeans_mt']}, expected 1.519"
    assert abs(float(row_ago25["soymeal_pellets_mt"]) - 2.960) < 0.01, f"August 2025 soymeal was {row_ago25['soymeal_pellets_mt']}, expected 2.960"

    # Invariant: October 2025 ground-truth verification
    row_oct25 = df_monthly[df_monthly["date"] == "2025-10-01"].iloc[0]
    assert abs(float(row_oct25["total_grain_mt"]) - 6.755) < 0.01, f"October 2025 total was {row_oct25['total_grain_mt']}, expected 6.755"

    # Port breakdown terminals reconciliation
    df_ports = pd.read_csv(COMMODITIES / "argentina_grain_ports_breakdown.csv")
    jul26_ports = df_ports[df_ports["date"] == "2026-07-01"]
    assert len(jul26_ports) == 8, f"July 2026 active terminals count was {len(jul26_ports)}, expected 8"
    assert abs(jul26_ports["total_tonnes"].sum() / 1e6 - 8.101) < 0.01, "July 2026 ports sum must equal 8.101 Mt"


def test_fixture_ledger_coverage_and_effective_span():
    """
    Audit Item 2 & 3:
    Fixture ledger YoY comparisons are coverage-affected sampling artifacts.
    Verify that effective span is 2019–2026 (earliest 1974), coverage warning is explicit,
    and fixtures-per-year distribution reflects the 2024–2026 ramp.
    """
    matrix_file = ROOT / "data" / "cargo" / "commodity_flow_matrix.json"
    with open(matrix_file, "r", encoding="utf-8") as f:
        matrix = json.load(f)

    meta = matrix["metadata"]
    assert meta["effective_span"] == "2019–2026"
    assert meta["earliest_year"] == 1974
    assert "Effective Coverage: 2019–2026" in meta["provenance_span_claim"]
    assert "coverage_ramp_warning" in meta and len(meta["coverage_ramp_warning"]) > 20

    dist = meta["fixtures_by_year"]
    pre_2019 = sum(v for k, v in dist.items() if k.isdigit() and int(k) < 2019)
    post_2023 = sum(v for k, v in dist.items() if k.isdigit() and int(k) >= 2024)
    total = meta["total_fixtures"]

    # Pre-2019 are stragglers (< 2% of ledger)
    assert pre_2019 / total < 0.02, f"Pre-2019 fixtures {pre_2019} should be < 2% of {total}"
    # Contemporary period 2024–2026 holds > 90% of all fixtures
    assert post_2023 / total > 0.90, f"2024–2026 fixtures {post_2023} should be > 90% of {total}"


def test_major_miners_all_rows_have_filing_provenance():
    """
    Safeguard: Fail the build if any row in major_miners_quarterly_shipments.csv
    has an unverified provenance (e.g. 'illustrative_prior_estimate') or lacks
    a resolvable corporate filing citation (EDGAR: or ASX:).
    """
    miners_csv = COMMODITIES / "major_miners_quarterly_shipments.csv"
    assert miners_csv.exists(), f"Miners CSV not found at {miners_csv}"

    df = pd.read_csv(miners_csv, dtype=str)
    assert len(df) == 40, f"Expected 40 quarterly miner records (10 quarters x 4 miners), got {len(df)}"

    # 1. Zero illustrative / unverified rows
    illustrative_mask = df["provenance"].fillna("").str.contains("illustrative", case=False)
    assert not illustrative_mask.any(), (
        f"Found {illustrative_mask.sum()} row(s) with illustrative provenance in major_miners_quarterly_shipments.csv"
    )

    # 2. Every row MUST start with EDGAR: or ASX:
    valid_prov_mask = df["provenance"].fillna("").str.startswith(("EDGAR:", "ASX:"))
    invalid_provs = df[~valid_prov_mask]
    assert len(invalid_provs) == 0, (
        f"Found {len(invalid_provs)} row(s) without valid EDGAR/ASX provenance citation: "
        f"{invalid_provs[['miner', 'quarter', 'provenance']].to_dict('records')}"
    )

    # 3. Every row MUST have a valid non-empty exhibit URL pointing to SEC EDGAR or ASX/Markit
    valid_url_mask = df["exhibit_url"].fillna("").str.contains(r"sec\.gov|asx\.com\.au|markitdigital\.com", regex=True)
    invalid_urls = df[~valid_url_mask]
    assert len(invalid_urls) == 0, (
        f"Found {len(invalid_urls)} row(s) with missing/invalid exhibit URL: "
        f"{invalid_urls[['miner', 'quarter', 'exhibit_url']].to_dict('records')}"
    )

    # 4. Strictly disallow company-hosted URLs (which move/break over time)
    company_site_mask = df["exhibit_url"].fillna("").str.contains(r"fortescue\.com", regex=True)
    assert not company_site_mask.any(), (
        f"Found {company_site_mask.sum()} row(s) citing company-hosted fortescue.com URLs instead of exchange filings"
    )

    # 5. Table row label and basis must be documented for every row
    assert not df["table_row_label"].isna().any(), "Found rows with missing table_row_label"
    assert not (df["table_row_label"].str.strip() == "").any(), "Found rows with empty table_row_label"
    assert not df["basis"].isna().any(), "Found rows with missing basis"
    assert not (df["basis"].str.strip() == "").any(), "Found rows with empty basis"

