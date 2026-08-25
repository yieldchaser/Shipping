#!/usr/bin/env python3
"""
Major Global Iron Ore Miners Production & Shipments — REAL FEED PREFERRED, DIAGNOSTIC FALLBACK.

Companies (Vale, Rio Tinto, BHP, Fortescue) publish quarterly production/shipment
volumes in their investor relations (IR) reports / operational reviews. The authoritative,
structured source is each company's quarterly results XLSX/PDF.

Behaviour (data-provenance policy, 2026-08-25 audit):
  - If a live IR feed is reachable and parseable, write REAL rows (provenance=live_ir).
  - Otherwise emit the frozen editorial estimate with provenance=editorial_estimate_diagnostic.
    The frontend tooltip discloses this. Never fabricate within a "real" provenance.
  - The editorial values below are illustrative DISR/company-guidance-style figures and are
    explicitly flagged, not presented as published data.
"""
import logging
import urllib.request
import ssl
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "commodities"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / "major_miners_quarterly_shipments.csv"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

EDITORIAL = [
    # date, quarter, miner, production_mt, shipments_mt, c1_cash_cost_usd_t, annual_guidance, primary_loading_terminals
    ("2024-03-31", "2024 Q1", "Vale", 70.8, 63.8, 20.6, "310-320 Mt", "Ponta da Madeira / Tubarão"),
    ("2024-03-31", "2024 Q1", "Rio Tinto", 78.0, 78.0, 21.5, "323-338 Mt", "Dampier / Cape Lambert"),
    ("2024-03-31", "2024 Q1", "BHP", 68.1, 69.8, 18.2, "254-260 Mt", "Port Hedland (Nelson Point/Finucane)"),
    ("2024-03-31", "2024 Q1", "Fortescue", 43.3, 43.3, 18.9, "192-197 Mt", "Port Hedland (Herb Elliott)"),
    ("2024-06-30", "2024 Q2", "Vale", 80.6, 79.8, 21.2, "310-320 Mt", "Ponta da Madeira / Tubarão"),
    ("2024-06-30", "2024 Q2", "Rio Tinto", 79.5, 80.3, 21.8, "323-338 Mt", "Dampier / Cape Lambert"),
    ("2024-06-30", "2024 Q2", "BHP", 76.8, 75.9, 18.0, "254-260 Mt", "Port Hedland (Nelson Point/Finucane)"),
    ("2024-06-30", "2024 Q2", "Fortescue", 53.7, 53.7, 17.8, "192-197 Mt", "Port Hedland (Herb Elliott)"),
    ("2024-09-30", "2024 Q3", "Vale", 91.0, 81.8, 20.4, "323-330 Mt", "Ponta da Madeira / Tubarão"),
    ("2024-09-30", "2024 Q3", "Rio Tinto", 84.1, 84.5, 21.4, "323-338 Mt", "Dampier / Cape Lambert"),
    ("2024-09-30", "2024 Q3", "BHP", 71.6, 71.4, 18.4, "255-265 Mt", "Port Hedland (Nelson Point/Finucane)"),
    ("2024-09-30", "2024 Q3", "Fortescue", 47.7, 47.7, 18.2, "190-200 Mt", "Port Hedland (Herb Elliott)"),
    ("2024-12-31", "2024 Q4", "Vale", 89.4, 87.2, 20.8, "328 Mt Actual", "Ponta da Madeira / Tubarão"),
    ("2024-12-31", "2024 Q4", "Rio Tinto", 86.8, 87.1, 21.9, "331 Mt Actual", "Dampier / Cape Lambert"),
    ("2024-12-31", "2024 Q4", "BHP", 72.8, 73.2, 18.1, "260 Mt Actual", "Port Hedland (Nelson Point/Finucane)"),
    ("2024-12-31", "2024 Q4", "Fortescue", 49.4, 49.4, 18.5, "194 Mt Actual", "Port Hedland (Herb Elliott)"),
    ("2025-03-31", "2025 Q1", "Vale", 72.5, 65.2, 21.0, "325-335 Mt", "Ponta da Madeira / Tubarão"),
    ("2025-03-31", "2025 Q1", "Rio Tinto", 80.2, 80.5, 22.1, "325-340 Mt", "Dampier / Cape Lambert"),
    ("2025-03-31", "2025 Q1", "BHP", 70.4, 71.2, 18.6, "258-268 Mt", "Port Hedland (Nelson Point/Finucane)"),
    ("2025-03-31", "2025 Q1", "Fortescue", 45.1, 45.1, 19.2, "195-200 Mt", "Port Hedland (Herb Elliott)"),
    ("2025-06-30", "2025 Q2", "Vale", 83.1, 82.0, 21.5, "325-335 Mt", "Ponta da Madeira / Tubarão"),
    ("2025-06-30", "2025 Q2", "Rio Tinto", 82.4, 83.0, 22.4, "325-340 Mt", "Dampier / Cape Lambert"),
    ("2025-06-30", "2025 Q2", "BHP", 78.9, 78.1, 18.3, "258-268 Mt", "Port Hedland (Nelson Point/Finucane)"),
    ("2025-06-30", "2025 Q2", "Fortescue", 55.4, 55.4, 18.1, "195-200 Mt", "Port Hedland (Herb Elliott)"),
    ("2025-09-30", "2025 Q3", "Vale", 93.8, 84.5, 20.9, "330-340 Mt", "Ponta da Madeira / Tubarão"),
    ("2025-09-30", "2025 Q3", "Rio Tinto", 86.7, 87.2, 22.0, "328-342 Mt", "Dampier / Cape Lambert"),
    ("2025-09-30", "2025 Q3", "BHP", 73.9, 74.0, 18.7, "260-270 Mt", "Port Hedland (Nelson Point/Finucane)"),
    ("2025-09-30", "2025 Q3", "Fortescue", 49.8, 49.8, 18.5, "195-205 Mt", "Port Hedland (Herb Elliott)"),
    ("2025-12-31", "2025 Q4", "Vale", 92.1, 89.9, 21.1, "338 Mt Actual", "Ponta da Madeira / Tubarão"),
    ("2025-12-31", "2025 Q4", "Rio Tinto", 89.2, 89.8, 22.3, "339 Mt Actual", "Dampier / Cape Lambert"),
    ("2025-12-31", "2025 Q4", "BHP", 75.1, 75.5, 18.4, "267 Mt Actual", "Port Hedland (Nelson Point/Finucane)"),
    ("2025-12-31", "2025 Q4", "Fortescue", 51.2, 51.2, 18.8, "200 Mt Actual", "Port Hedland (Herb Elliott)"),
    ("2026-03-31", "2026 Q1", "Vale", 75.4, 67.8, 21.4, "335-345 Mt", "Ponta da Madeira / Tubarão"),
    ("2026-03-31", "2026 Q1", "Rio Tinto", 82.9, 83.1, 22.5, "330-345 Mt", "Dampier / Cape Lambert"),
    ("2026-03-31", "2026 Q1", "BHP", 71.2, 71.8, 18.9, "258-268 Mt", "Port Hedland (Nelson Point/Finucane)"),
    ("2026-03-31", "2026 Q1", "Fortescue", 46.0, 46.0, 19.0, "195-205 Mt", "Port Hedland (Herb Elliott)"),
    ("2026-06-30", "2026 Q2", "Vale", 84.5, 83.0, 21.6, "335-345 Mt", "Ponta da Madeira / Tubarão"),
    ("2026-06-30", "2026 Q2", "Rio Tinto", 84.0, 84.6, 22.6, "330-345 Mt", "Dampier / Cape Lambert"),
    ("2026-06-30", "2026 Q2", "BHP", 79.0, 78.3, 18.5, "258-268 Mt", "Port Hedland (Nelson Point/Finucane)"),
    ("2026-06-30", "2026 Q2", "Fortescue", 55.9, 55.9, 18.2, "195-205 Mt", "Port Hedland (Herb Elliott)"),
]


def _try_live_ir() -> pd.DataFrame | None:
    """Placeholder for structured IR feed parsing. Returns None until implemented
    (company IR endpoints require per-source scraping; out of scope for this audit pass)."""
    return None


def main() -> pd.DataFrame:
    live = _try_live_ir()
    if live is not None and len(live):
        df = live.copy()
        df["provenance"] = "live_ir"
    else:
        logging.warning("Live miner IR feed not available — emitting EDITORIAL ESTIMATE flagged DIAGNOSTIC (not real data).")
        df = pd.DataFrame(EDITORIAL, columns=[
            "date", "quarter", "miner", "production_mt", "shipments_mt",
            "c1_cash_cost_usd_t", "annual_guidance", "primary_loading_terminals"
        ])
        df["provenance"] = "editorial_estimate_diagnostic"
    df.to_csv(OUT_FILE, index=False)
    logging.info("Wrote %d rows (provenance=%s) -> %s", len(df), df["provenance"].iloc[0], OUT_FILE)
    return df


if __name__ == "__main__":
    main()
