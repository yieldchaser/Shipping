"""
Star Asia Recycling Ship Price Trends Chart Extraction Pipeline.

Extracts the 4 regional scrap price curves ($/LDT) from Page 11 of Star Asia weekly reports (2021-2026):
  1) India Ship Recycling Prices ($/LDT) - Blue RGB(46, 117, 182)
  2) Bangladesh Ship Recycling Prices ($/LDT) - Orange RGB(237, 125, 49)
  3) Pakistan Ship Recycling Prices ($/LDT) - Green RGB(112, 173, 71)
  4) Turkey Ship Recycling Prices ($/LDT) - Gold RGB(255, 192, 0)

Outputs:
  - data/extracted/series/star_asia_scrap_price_trends_series.csv
"""

import csv
import glob
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
STAR_ASIA_DIR = ROOT / "corpus" / "01-brokers" / "star_asia"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)
SERIES_CSV = OUT_SERIES_DIR / "star_asia_scrap_price_trends_series.csv"


def extract_date_and_week(doc: pymupdf.Document, pdf_path: Path) -> Tuple[str, int]:
    fn = pdf_path.stem
    m_wk = re.search(r"week[_\-\s]*(\d{1,2})", fn, re.I) or re.search(r"W(\d{1,2})", fn, re.I)
    wk = int(m_wk.group(1)) if m_wk else 0

    p1 = doc[0].get_text()
    MONTHS = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    dt = None
    for line in p1.splitlines()[:25]:
        cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", line, flags=re.I)
        m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(202\d)", cleaned)
        if m and m.group(1).lower() in MONTHS:
            mo = MONTHS[m.group(1).lower()]
            da = int(m.group(2))
            yr = int(m.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break
        m2 = re.search(r"(\d{1,2})\s+([A-Za-z]+),?\s+(202\d)", cleaned)
        if m2 and m2.group(2).lower() in MONTHS:
            da = int(m2.group(1))
            mo = MONTHS[m2.group(2).lower()]
            yr = int(m2.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break

    if not dt:
        m_dt = re.search(r"(\d{2})_(\d{2})_(202\d)", fn)
        if m_dt:
            d, m, y = int(m_dt.group(1)), int(m_dt.group(2)), int(m_dt.group(3))
            dt = f"{y:04d}-{m:02d}-{d:02d}"
        else:
            m_yr = re.search(r"(202\d)", str(pdf_path))
            dt = f"{m_yr.group(1)}-00-00" if m_yr else "2026-00-00"

    return dt, wk


def process_chart_image(img_bytes: bytes, country: str, target_rgb: Tuple[int, int, int], max_val: float) -> Optional[float]:
    try:
        import io
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        arr = np.array(im)
    except Exception:
        return None

    # Curve mask
    r, g, b = target_rgb
    mask = (np.abs(arr[:, :, 0] - r) < 25) & (np.abs(arr[:, :, 1] - g) < 25) & (np.abs(arr[:, :, 2] - b) < 25)
    y_coords, x_coords = np.where(mask)

    if len(x_coords) == 0:
        return None

    # Axis grid line Y coordinates
    # Grid lines are light grey around Y ~ 100 to 500
    # Top grid line (max_val) is around Y ~ 100, zero line is around Y ~ 450-480
    y_zero = 455.0
    y_top = 105.0
    span = y_zero - y_top

    # Latest reading (highest X)
    max_x = x_coords.max()
    latest_y = y_coords[x_coords >= max_x - 4].mean()

    # Price in $/LDT
    price = max_val - (latest_y - y_top) * (max_val / span)
    return max(0.0, round(price, 1))


def run_star_asia_charts():
    pdfs = sorted(glob.glob(str(STAR_ASIA_DIR / "*/*.pdf")))
    print(f"Scanning {len(pdfs)} Star Asia PDFs for recycling price trend charts...")

    all_rows = []

    # Country chart definitions: (country, target RGB, max_val $/LDT)
    CHART_DEFS = [
        ("India", (46, 117, 182), 800.0),
        ("Bangladesh", (237, 125, 49), 800.0),
        ("Pakistan", (112, 173, 71), 800.0),
        ("Turkey", (255, 192, 0), 500.0)
    ]

    for pdf_str in pdfs:
        pdf_path = Path(pdf_str)
        try:
            doc = pymupdf.open(pdf_path)
        except Exception:
            continue

        issue_date, report_week = extract_date_and_week(doc, pdf_path)

        # Locate Page with "Recycling Ships Price Trend" (usually around page 10-12)
        trend_page = None
        for pno, page in enumerate(doc):
            t = page.get_text()
            if "RECYCLING SHIPS PRICE TREND" in t.upper() or ("SHIPS SOLD FOR RECYCLING" in t.upper() and len(page.get_images()) >= 3):
                trend_page = page
                break

        if not trend_page:
            continue

        # Extract images >= 500x300
        chart_images = []
        for img_info in trend_page.get_images():
            xref = img_info[0]
            base = doc.extract_image(xref)
            if base["width"] >= 500 and base["height"] >= 300:
                chart_images.append(base["image"])

        if len(chart_images) >= 4:
            for i, (country, rgb, max_val) in enumerate(CHART_DEFS):
                val = process_chart_image(chart_images[i], country, rgb, max_val)
                if val is not None:
                    all_rows.append({
                        "issue_date": issue_date,
                        "report_week": report_week,
                        "country": country,
                        "scrap_price_usd_per_ldt": val,
                        "chart_metric": f"{country} Ship Recycling Price Trend",
                        "source_file": pdf_path.name
                    })

    print(f"Total Star Asia scrap price trend rows extracted: {len(all_rows)}")
    if all_rows:
        fields = ["issue_date", "report_week", "country", "scrap_price_usd_per_ldt", "chart_metric", "source_file"]
        with open(SERIES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"Exported {len(all_rows)} rows to {SERIES_CSV.name}")


if __name__ == "__main__":
    run_star_asia_charts()
