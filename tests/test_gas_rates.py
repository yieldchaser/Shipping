#!/usr/bin/env python3
"""LNG/LPG rate CSVs must equal the Fearnleys catalog and keep pace with it.

They had no writer and froze at 2026-08-05 while the Broker Desk read them.
scripts/fearnleys/build_gas_rate_csvs.py now rebuilds them daily.
"""
import csv
import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gas", ROOT / "scripts" / "fearnleys" / "build_gas_rate_csvs.py")
gas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gas)


def test_gas_rate_csvs_equal_catalog_and_are_current():
    series = gas.load_catalog()
    for fname, cols in gas.FILES.items():
        rows = list(csv.DictReader((ROOT / "data" / "derived" / fname).open(encoding="utf-8")))
        assert rows, fname
        for c, _ in cols:
            got = {r["date"]: float(r[c]) for r in rows if r[c]}
            assert got == series[c], f"{fname}:{c} differs from the catalog"
        newest_catalog = max(max(series[c]) for c, _ in cols)
        newest_file = max(r["date"] for r in rows)
        lag = (date.fromisoformat(newest_catalog) - date.fromisoformat(newest_file)).days
        assert lag == 0, f"{fname} ends {newest_file}, catalog has {newest_catalog}"


def test_lng_has_same_size_price_for_charter_payback():
    rows = list(csv.DictReader((ROOT / "data" / "derived" / "lng_charter_rates.csv").open(encoding="utf-8")))
    assert "lngc_174k_nb_price" in rows[0]
    assert any(r["lngc_174k_nb_price"] and (r["lngc_174k_10y_tc"] or r["lngc_174k_7y_tc"]) for r in rows)
