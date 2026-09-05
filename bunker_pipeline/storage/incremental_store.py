#!/usr/bin/env python3
"""
Storage & Incremental Accumulation Engine
Manages persistent local repository at bunker_master_historical.csv and bunker_master_historical.json.
Enforces composite primary key deduplication: (port_code, grade, observation_date).
Neutralizes rolling sliding-window restrictions to accumulate multi-year historical depth locally.
"""

import os
import json
import logging
import pandas as pd

logger = logging.getLogger("IncrementalStore")

DEFAULT_CSV_PATH = "data/bunkers/bunker_master_historical.csv"
DEFAULT_JSON_PATH = "data/bunkers/bunker_master_historical.json"
ROOT_CSV_PATH = "bunker_master_historical.csv"
ROOT_JSON_PATH = "bunker_master_historical.json"

MASTER_COLUMNS = [
    "observation_date",
    "port_code",
    "port_name",
    "grade",
    "delivery_term",
    "price_usd",
    "change_usd",
    "high_usd",
    "low_usd",
    "spread_usd",
    "unit",
    "source",
]

class IncrementalBunkerStore:
    def __init__(self, csv_path: str = DEFAULT_CSV_PATH, json_path: str = DEFAULT_JSON_PATH):
        self.csv_path = csv_path
        self.json_path = json_path
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)

    def load_master_df(self) -> pd.DataFrame:
        """Loads existing master store DataFrame, or returns an empty initialized DataFrame."""
        if os.path.exists(self.csv_path) and os.path.getsize(self.csv_path) > 0:
            try:
                df = pd.read_csv(self.csv_path, dtype=str)
                # Cast numeric columns
                numeric_cols = ["price_usd", "change_usd", "high_usd", "low_usd", "spread_usd"]
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                for col in MASTER_COLUMNS:
                    if col not in df.columns:
                        df[col] = None
                return df[MASTER_COLUMNS]
            except Exception as e:
                logger.error(f"Error loading master CSV {self.csv_path}: {e}")
                
        return pd.DataFrame(columns=MASTER_COLUMNS)

    def save_master(self, df: pd.DataFrame):
        """Atomically saves DataFrame to CSV and JSON."""
        # Ensure correct column ordering
        for col in MASTER_COLUMNS:
            if col not in df.columns:
                df[col] = None
        out_df = df[MASTER_COLUMNS].copy()

        # Sort chronologically, then by port_code, then grade
        out_df = out_df.sort_values(
            by=["observation_date", "port_code", "grade"],
            ascending=[True, True, True]
        ).reset_index(drop=True)

        # 1. Save to primary csv and json paths
        temp_csv = f"{self.csv_path}.tmp"
        out_df.to_csv(temp_csv, index=False)
        if os.path.exists(self.csv_path):
            os.remove(self.csv_path)
        os.rename(temp_csv, self.csv_path)

        temp_json = f"{self.json_path}.tmp"
        out_df.to_json(temp_json, orient="records", indent=2)
        if os.path.exists(self.json_path):
            os.remove(self.json_path)
        os.rename(temp_json, self.json_path)

        # 2. Mirror to root directory only when using default store
        if self.csv_path == DEFAULT_CSV_PATH:
            try:
                out_df.to_csv(ROOT_CSV_PATH, index=False)
                out_df.to_json(ROOT_JSON_PATH, orient="records", indent=2)
            except Exception as e:
                logger.warning(f"Could not mirror to root directory: {e}")

        logger.info(f"Successfully committed {len(out_df)} records to {self.csv_path}")

    def ingest_records(self, new_records: list) -> dict:
        """
        Ingests a list of dictionary records.
        Deduplicates against composite primary key (port_code, grade, observation_date).
        Returns ingestion statistics dictionary.
        """
        if not new_records:
            return {"incoming": 0, "added": 0, "total_master": 0}

        new_df = pd.DataFrame(new_records)
        for col in MASTER_COLUMNS:
            if col not in new_df.columns:
                new_df[col] = None
                
        # Numeric parsing
        for col in ["price_usd", "change_usd", "high_usd", "low_usd", "spread_usd"]:
            if col in new_df.columns:
                new_df[col] = pd.to_numeric(new_df[col], errors="coerce")

        # Standardize strings
        new_df["observation_date"] = new_df["observation_date"].astype(str).str.strip()
        new_df["port_code"] = new_df["port_code"].astype(str).str.strip()
        new_df["grade"] = new_df["grade"].astype(str).str.strip()

        # Deduplicate incoming records first
        new_df = new_df.drop_duplicates(subset=["port_code", "grade", "observation_date"], keep="last")

        existing_df = self.load_master_df()
        initial_count = len(existing_df)

        if existing_df.empty:
            merged_df = new_df
            added_count = len(new_df)
        else:
            existing_df["observation_date"] = existing_df["observation_date"].astype(str).str.strip()
            existing_df["port_code"] = existing_df["port_code"].astype(str).str.strip()
            existing_df["grade"] = existing_df["grade"].astype(str).str.strip()

            # Merge: new records update existing or append
            combined = pd.concat([existing_df, new_df], ignore_index=True)
            # Keep the one with non-null change/high/low if available, else keep last
            merged_df = combined.drop_duplicates(subset=["port_code", "grade", "observation_date"], keep="last")
            added_count = len(merged_df) - initial_count

        self.save_master(merged_df)

        stats = {
            "incoming": len(new_records),
            "added": added_count,
            "total_master": len(merged_df)
        }
        logger.info(f"Ingestion complete: +{added_count} new unique records. Master store now contains {len(merged_df)} observations.")
        return stats

# Global store singleton
STORE = IncrementalBunkerStore()
