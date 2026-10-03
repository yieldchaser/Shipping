// Authoritative Scenario Snapshots Bundle
window.SCENARIO_SNAPSHOTS = {
  bdry: {
  "schema_version": "1.0.0",
  "generation_timestamp_utc": "2026-10-03T10:17:41.170179+00:00",
  "fund_symbol": "BDRY",
  "contract_spec_version": "2026.08.14-VERIFIED-V1",
  "holdings_snapshot_as_of_date": "2026-10-02",
  "is_official_as_of_date": true,
  "date_sourcing": "OFFICIAL_SOURCE_DISCLOSED",
  "source_urls": [
    "https://amplifyetfs.com/bdry-holdings/"
  ],
  "source_hashes": {
    "expected_registry_sha256": "000c806f321310ce561cd4859dfb1dc4b9c60fae7e7b7d0ba5039810ef9d73df",
    "computed_archive_sha256": "000c806f321310ce561cd4859dfb1dc4b9c60fae7e7b7d0ba5039810ef9d73df"
  },
  "provenance": {
    "official_source_url": "https://amplifyetfs.com/bdry-holdings/",
    "raw_source_path": "data/etf/raw_sources/amplify_master_2026-10-02.csv",
    "raw_source_sha256": "8d8f18e01a30994dd384037b70960827b2b38795177b3ded3689cd75153d8b74",
    "immutable_archive_path": "data/etf/raw_holdings/BDRY/2026-10-02.csv",
    "expected_registry_sha256": "000c806f321310ce561cd4859dfb1dc4b9c60fae7e7b7d0ba5039810ef9d73df",
    "computed_archive_sha256": "000c806f321310ce561cd4859dfb1dc4b9c60fae7e7b7d0ba5039810ef9d73df",
    "snapshot_content_sha256": "e4d9b2010f63c3e6c10b260e5059fed2cdf61e0068344b0d2210bce4769e8f3c",
    "manifest_snapshot_sha256": "e4d9b2010f63c3e6c10b260e5059fed2cdf61e0068344b0d2210bce4769e8f3c",
    "provenance_verified": true,
    "provenance_status": "VERIFIED_OFFICIAL_ARCHIVE"
  },
  "freshness_state": {
    "business_day_age": 0,
    "is_fresh": true,
    "max_freshness_limit_bdays": 3,
    "reference_time_utc": "2026-10-03T10:17:41.170179+00:00"
  },
  "baseline": {
    "as_of_date": "2026-10-02",
    "is_contemporaneous": true,
    "total_nav_dollars": 36071150.86,
    "shares_outstanding": 2475040,
    "nav_per_share": 14.574,
    "market_price": 14.52,
    "source_description": "Official Amplified Disclosures & CFTC Statements"
  },
  "positions": [
    {
      "contract_name": "Capesize 5TC FFA 180kt Timecharter Average M Oct 26",
      "ticker": "C5TCM V26 INDEX",
      "cusip": "C5TCM V26",
      "lots": 145.0,
      "multiplier": 1.0,
      "multiplier_unit": "Calendar Day of Time Charter (1 USD/day)",
      "price": 40268.0,
      "product_code": "CWF / C5T (SGX), C5 (CME)",
      "rulebook_ref": "SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 680",
      "route_class": "Capesize",
      "exchange": "SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe",
      "position_notional": 5838860.0
    },
    {
      "contract_name": "Capesize 5TC FFA 180kt Timecharter Average M Nov 26",
      "ticker": "C5TCM X26 INDEX",
      "cusip": "C5TCM X26",
      "lots": 145.0,
      "multiplier": 1.0,
      "multiplier_unit": "Calendar Day of Time Charter (1 USD/day)",
      "price": 41350.0,
      "product_code": "CWF / C5T (SGX), C5 (CME)",
      "rulebook_ref": "SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 680",
      "route_class": "Capesize",
      "exchange": "SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe",
      "position_notional": 5995750.0
    },
    {
      "contract_name": "Capesize 5TC FFA 180kt Timecharter Average M Dec 26",
      "ticker": "C5TCM Z26 INDEX",
      "cusip": "C5TCM Z26",
      "lots": 145.0,
      "multiplier": 1.0,
      "multiplier_unit": "Calendar Day of Time Charter (1 USD/day)",
      "price": 40946.0,
      "product_code": "CWF / C5T (SGX), C5 (CME)",
      "rulebook_ref": "SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 680",
      "route_class": "Capesize",
      "exchange": "SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe",
      "position_notional": 5937170.0
    },
    {
      "contract_name": "Panamax 5TC FFA 82kt Timecharter Average M Oct 26",
      "ticker": "P5TCM V26 INDEX",
      "cusip": "P5TCM V26",
      "lots": 220.0,
      "multiplier": 1.0,
      "multiplier_unit": "Calendar Day of Time Charter (1 USD/day)",
      "price": 21807.0,
      "product_code": "P4T / P5T (SGX), P5 (CME)",
      "rulebook_ref": "SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 681",
      "route_class": "Panamax",
      "exchange": "SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe",
      "position_notional": 4797540.0
    },
    {
      "contract_name": "Panamax 5TC FFA 82kt Timecharter Average M Nov 26",
      "ticker": "P5TCM X26 INDEX",
      "cusip": "P5TCM X26",
      "lots": 220.0,
      "multiplier": 1.0,
      "multiplier_unit": "Calendar Day of Time Charter (1 USD/day)",
      "price": 21957.0,
      "product_code": "P4T / P5T (SGX), P5 (CME)",
      "rulebook_ref": "SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 681",
      "route_class": "Panamax",
      "exchange": "SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe",
      "position_notional": 4830540.0
    },
    {
      "contract_name": "Panamax 5TC FFA 82kt Timecharter Average M Dec 26",
      "ticker": "P5TCM Z26 INDEX",
      "cusip": "P5TCM Z26",
      "lots": 220.0,
      "multiplier": 1.0,
      "multiplier_unit": "Calendar Day of Time Charter (1 USD/day)",
      "price": 21779.0,
      "product_code": "P4T / P5T (SGX), P5 (CME)",
      "rulebook_ref": "SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 681",
      "route_class": "Panamax",
      "exchange": "SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe",
      "position_notional": 4791380.0
    },
    {
      "contract_name": "Supramax 58 TC FFA 58kt Timecharter Average M Oct 26",
      "ticker": "S58FM V26 INDEX",
      "cusip": "S58FM V26",
      "lots": 60.0,
      "multiplier": 1.0,
      "multiplier_unit": "Calendar Day of Time Charter (1 USD/day)",
      "price": 20575.0,
      "product_code": "S10 / S5T (SGX), S1 (CME)",
      "rulebook_ref": "SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 682",
      "route_class": "Supramax",
      "exchange": "SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe",
      "position_notional": 1234500.0
    },
    {
      "contract_name": "Supramax 58 TC FFA 58kt Timecharter Average M Nov 26",
      "ticker": "S58FM X26 INDEX",
      "cusip": "S58FM X26",
      "lots": 60.0,
      "multiplier": 1.0,
      "multiplier_unit": "Calendar Day of Time Charter (1 USD/day)",
      "price": 20268.0,
      "product_code": "S10 / S5T (SGX), S1 (CME)",
      "rulebook_ref": "SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 682",
      "route_class": "Supramax",
      "exchange": "SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe",
      "position_notional": 1216080.0
    },
    {
      "contract_name": "Supramax 58 TC FFA 58kt Timecharter Average M Dec 26",
      "ticker": "S58FM Z26 INDEX",
      "cusip": "S58FM Z26",
      "lots": 60.0,
      "multiplier": 1.0,
      "multiplier_unit": "Calendar Day of Time Charter (1 USD/day)",
      "price": 19868.0,
      "product_code": "S10 / S5T (SGX), S1 (CME)",
      "rulebook_ref": "SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 682",
      "route_class": "Supramax",
      "exchange": "SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe",
      "position_notional": 1192080.0
    }
  ]
},
  bwet: {
  "schema_version": "1.0.0",
  "generation_timestamp_utc": "2026-10-03T10:17:41.211034+00:00",
  "fund_symbol": "BWET",
  "contract_spec_version": "2026.08.14-VERIFIED-V1",
  "holdings_snapshot_as_of_date": "2026-10-02",
  "is_official_as_of_date": true,
  "date_sourcing": "OFFICIAL_SOURCE_DISCLOSED",
  "source_urls": [
    "https://amplifyetfs.com/bwet-holdings/"
  ],
  "source_hashes": {
    "expected_registry_sha256": "01a6a4a25934d9282939753de5dc1af8f5a890bcbf692e38947b864e5872675e",
    "computed_archive_sha256": "01a6a4a25934d9282939753de5dc1af8f5a890bcbf692e38947b864e5872675e"
  },
  "provenance": {
    "official_source_url": "https://amplifyetfs.com/bwet-holdings/",
    "raw_source_path": "data/etf/raw_sources/amplify_master_2026-10-02.csv",
    "raw_source_sha256": "8d8f18e01a30994dd384037b70960827b2b38795177b3ded3689cd75153d8b74",
    "immutable_archive_path": "data/etf/raw_holdings/BWET/2026-10-02.csv",
    "expected_registry_sha256": "01a6a4a25934d9282939753de5dc1af8f5a890bcbf692e38947b864e5872675e",
    "computed_archive_sha256": "01a6a4a25934d9282939753de5dc1af8f5a890bcbf692e38947b864e5872675e",
    "snapshot_content_sha256": "12f5b63785ab71868804916c43f27f36d5275d2498fc13536596f281581261a8",
    "manifest_snapshot_sha256": "12f5b63785ab71868804916c43f27f36d5275d2498fc13536596f281581261a8",
    "provenance_verified": true,
    "provenance_status": "VERIFIED_OFFICIAL_ARCHIVE"
  },
  "freshness_state": {
    "business_day_age": 0,
    "is_fresh": true,
    "max_freshness_limit_bdays": 3,
    "reference_time_utc": "2026-10-03T10:17:41.211034+00:00"
  },
  "baseline": {
    "as_of_date": "2026-10-02",
    "is_contemporaneous": true,
    "total_nav_dollars": 194380722.01,
    "shares_outstanding": 240100,
    "nav_per_share": 809.5823,
    "market_price": 826.13,
    "source_description": "Official Amplified Disclosures & CFTC Statements"
  },
  "positions": [
    {
      "contract_name": "TD3C FFA 270kt Middle East Gulf to China USD/MT M Oct 26",
      "ticker": "DD3CM V26 INDEX",
      "cusip": "DD3CM V26",
      "lots": 242.0,
      "multiplier": 1000.0,
      "multiplier_unit": "1,000 Metric Tons (MT) of Crude Oil Cargo",
      "price": 236.56,
      "product_code": "TL (Monthly Futures), TLB (BALMO)",
      "rulebook_ref": "NYMEX Rulebook Chapter 684 (\"Freight Route TD3C (Baltic) Futures\")",
      "route_class": "VLCC",
      "exchange": "NYMEX (New York Mercantile Exchange) / CME ClearPort",
      "position_notional": 57247520.00000001
    },
    {
      "contract_name": "TD3C FFA 270kt Middle East Gulf to China USD/MT M Nov 26",
      "ticker": "DD3CM X26 INDEX",
      "cusip": "DD3CM X26",
      "lots": 292.0,
      "multiplier": 1000.0,
      "multiplier_unit": "1,000 Metric Tons (MT) of Crude Oil Cargo",
      "price": 208.977,
      "product_code": "TL (Monthly Futures), TLB (BALMO)",
      "rulebook_ref": "NYMEX Rulebook Chapter 684 (\"Freight Route TD3C (Baltic) Futures\")",
      "route_class": "VLCC",
      "exchange": "NYMEX (New York Mercantile Exchange) / CME ClearPort",
      "position_notional": 61021284.0
    },
    {
      "contract_name": "TD3C FFA 270kt Middle East Gulf to China USD/MT M Dec 26",
      "ticker": "DD3CM Z26 INDEX",
      "cusip": "DD3CM Z26",
      "lots": 302.0,
      "multiplier": 1000.0,
      "multiplier_unit": "1,000 Metric Tons (MT) of Crude Oil Cargo",
      "price": 178.948,
      "product_code": "TL (Monthly Futures), TLB (BALMO)",
      "rulebook_ref": "NYMEX Rulebook Chapter 684 (\"Freight Route TD3C (Baltic) Futures\")",
      "route_class": "VLCC",
      "exchange": "NYMEX (New York Mercantile Exchange) / CME ClearPort",
      "position_notional": 54042296.0
    },
    {
      "contract_name": "TD20 FFA 130kt West Africa to Continent USD/MT M Oct 26",
      "ticker": "DD20M V26 INDEX",
      "cusip": "DD20M V26",
      "lots": 75.0,
      "multiplier": 1000.0,
      "multiplier_unit": "1,000 Metric Tons (MT) of Crude Oil Cargo",
      "price": 124.504,
      "product_code": "T2D (Monthly Futures), T2B (BALMO), T2M (Mini)",
      "rulebook_ref": "NYMEX Rulebook Chapter 944 (\"Freight Route TD20 (Baltic) Futures\")",
      "route_class": "Suezmax",
      "exchange": "NYMEX (New York Mercantile Exchange) / CME ClearPort",
      "position_notional": 9337800.000000002
    },
    {
      "contract_name": "TD20 FFA 130kt West Africa to Continent USD/MT M Nov 26",
      "ticker": "DD20M X26 INDEX",
      "cusip": "DD20M X26",
      "lots": 75.0,
      "multiplier": 1000.0,
      "multiplier_unit": "1,000 Metric Tons (MT) of Crude Oil Cargo",
      "price": 106.618,
      "product_code": "T2D (Monthly Futures), T2B (BALMO), T2M (Mini)",
      "rulebook_ref": "NYMEX Rulebook Chapter 944 (\"Freight Route TD20 (Baltic) Futures\")",
      "route_class": "Suezmax",
      "exchange": "NYMEX (New York Mercantile Exchange) / CME ClearPort",
      "position_notional": 7996349.999999999
    },
    {
      "contract_name": "TD20 FFA 130kt West Africa to Continent USD/MT M Dec 26",
      "ticker": "DD20M Z26 INDEX",
      "cusip": "DD20M Z26",
      "lots": 75.0,
      "multiplier": 1000.0,
      "multiplier_unit": "1,000 Metric Tons (MT) of Crude Oil Cargo",
      "price": 83.027,
      "product_code": "T2D (Monthly Futures), T2B (BALMO), T2M (Mini)",
      "rulebook_ref": "NYMEX Rulebook Chapter 944 (\"Freight Route TD20 (Baltic) Futures\")",
      "route_class": "Suezmax",
      "exchange": "NYMEX (New York Mercantile Exchange) / CME ClearPort",
      "position_notional": 6227025.0
    }
  ]
}
};
