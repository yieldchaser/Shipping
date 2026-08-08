"""Fetch Fearnleys TC rates from Hasura GraphQL API and save to CSV."""
import requests
import pandas as pd
import os
import sys

URL = "https://pbrokerapp.hasura.app/v1/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://fearnpulse.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126",
}

QUERY = """
query Q($routes:[String!],$rateTypes:[String!],$rateSubtypes:[String!],$dateFrom:date,$dateTo:date){
  rate_meta(where:{info:{route:{_in:$routes},rate_type:{_in:$rateTypes},rate_subtype:{_in:$rateSubtypes}},rate_unit:{_eq:"usd"}}){
    rates(where:{date:{_gte:$dateFrom,_lte:$dateTo}},order_by:{date:asc}){date rate}
    info{route rate_type rate_subtype}
  }
}
"""

VARIABLES = {
    "routes": [
        "Capesize (180 000 dwt)",
        "Panamax (75 000 dwt)",
        "Supramax (58 000 dwt)",
        "Handysize (38 000 dwt)",
        "VLCC",
        "Suezmax",
        "Aframax",
    ],
    "rateTypes": ["BULK", "TANK"],
    "rateSubtypes": ["TC", "1 Year T/C"],
    "dateFrom": "2000-01-01",
    "dateTo": "2026-12-31",
}

ROUTE_MAP = {
    "Capesize (180 000 dwt)": "capesize_1y_avg",
    "Panamax (75 000 dwt)": "panamax_1y_avg",
    "Supramax (58 000 dwt)": "supramax_1y_avg",
    "Handysize (38 000 dwt)": "handysize_1y_avg",
    "VLCC": "vlcc_1y",
    "Suezmax": "suezmax_1y",
    "Aframax": "aframax_1y",
}

OUTPUT = os.path.join("data", "derived", "time_charter_rates_fearnleys.csv")


def main():
    print("Fetching Fearnleys TC rates...")
    resp = requests.post(URL, json={"query": QUERY, "variables": VARIABLES}, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        print("GraphQL errors:", data["errors"])
        sys.exit(1)

    rate_metas = data["data"]["rate_meta"]
    print(f"Received {len(rate_metas)} rate_meta entries")

    # Build per-route DataFrames and merge on date
    frames = []
    for meta in rate_metas:
        route = meta["info"]["route"]
        rate_type = meta["info"]["rate_type"]
        rate_subtype = meta["info"]["rate_subtype"]
        col = ROUTE_MAP.get(route)
        if col is None:
            print(f"  Skipping unknown route: {route}")
            continue
        rates = meta["rates"]
        print(f"  {route} ({rate_type}/{rate_subtype}): {len(rates)} data points -> {col}")
        if not rates:
            continue
        df = pd.DataFrame(rates)
        df.rename(columns={"rate": col}, inplace=True)
        df["date"] = pd.to_datetime(df["date"])
        frames.append(df[["date", col]])

    if not frames:
        print("No data received!")
        sys.exit(1)

    # Outer-merge all frames on date
    merged = frames[0]
    for f in frames[1:]:
        merged = merged.merge(f, on="date", how="outer")

    # Ensure all expected columns exist
    expected_cols = ["date"] + list(ROUTE_MAP.values())
    for c in expected_cols:
        if c not in merged.columns:
            merged[c] = float("nan")

    merged = merged[expected_cols].sort_values("date").reset_index(drop=True)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    merged.to_csv(OUTPUT, index=False)
    print(f"\nSaved to {OUTPUT}")

    # Verification
    print(f"Row count: {len(merged)}")
    print(f"Date range: {merged['date'].min().date()} to {merged['date'].max().date()}")
    print(f"Columns: {list(merged.columns)}")
    print(f"\nFirst 3 rows:\n{merged.head(3).to_string(index=False)}")
    print(f"\nLast 3 rows:\n{merged.tail(3).to_string(index=False)}")


if __name__ == "__main__":
    main()
