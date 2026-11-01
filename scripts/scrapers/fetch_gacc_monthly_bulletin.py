#!/usr/bin/env python3
"""
China customs monthly bulletin (GACC English site) - major imports and exports by quantity and value.

chinadata.live retired its per-HS JSON API in 2026-10 (404), and stats.customs.gov.cn answers scripts with
a JavaScript challenge (412). GACC also publishes the monthly bulletin as plain HTML tables on
english.customs.gov.cn ("Statistics > Monthly Bulletin"):
  (5) China's Major Exports by Quantity and Value, <Mon YYYY> (in USD)
  (6) China's Major Imports by Quantity and Value, <Mon YYYY> (in USD)
Each table gives, per commodity as printed by GACC, the month's quantity and value and the year-to-date
totals. Units as printed: quantity in "10,000 Tons" (or "Ton"), value in USD 1 million.

Outputs:
  data/commodities/china_customs_major_trade_gacc.csv
      one row per (month, flow, commodity) exactly as printed, quantity converted to tonnes and value to USD
  data/commodities/china_customs_monthly_imports.csv
      continued for the rows whose GACC bulletin line has the same scope as the stored HS series (checked
      against the 2026-08 chinadata.live values: iron ore 2601, soybeans 1201, crude 2709 match to the
      0.1 USD million). Coal (bulletin: coal AND lignite), natural gas, fertilizers and steel products have a
      different scope and are NOT spliced into those HS series; they live in the bulletin CSV only.
      Partner shares are not in the bulletin; new rows leave them blank.

Months already stored are skipped (no revisions are rewritten); a month whose table fails to parse is left out
and retried on the next run.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = ROOT / "data" / "commodities"
BULLETIN_CSV = COMMODITIES_DIR / "china_customs_major_trade_gacc.csv"
HS_CSV = COMMODITIES_DIR / "china_customs_monthly_imports.csv"

BASE = "http://english.customs.gov.cn"
LIST_URL = BASE + "/Statistics/Statistics?ColumnId=1&page={page}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MAX_PAGES = 6          # about 3 months of bulletins per list page; covers the recent backlog (--pages N to backfill)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                      "nov", "dec"], 1)}
LINK_RE = re.compile(r'href="(?P<href>[^"]*Statics/[0-9a-f-]+\.html)"[^>]*>\s*\((?P<n>[56])\)\s*China&#39;s Major '
                     r'(?P<flow>Exports|Imports) by Quantity and Value,\s*(?P<mon>[A-Za-z]{3})[a-z]*\.?'
                     r'(?:\s*-\s*(?P<mon2>[A-Za-z]{3})[a-z]*\.?)?\s*(?P<yr>\d{4})'
                     r'\s*\(in USD')

# bulletin line -> stored HS series, only where the scope is the same (see module docstring)
HS_CONTINUATION = {
    ("import", "Iron ores and concentrates"): "2601",
    ("import", "Soya beans"): "1201",
    ("import", "Crude petroleum oils"): "2709",
}
BULLETIN_FIELDS = ["date", "period_months", "flow", "commodity", "qty_unit_printed", "quantity_tonnes", "value_usd",
                   "ytd_quantity_tonnes", "ytd_value_usd", "source_url", "publisher"]


def _get(url: str) -> str:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=40)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            return r.text
        except Exception as exc:  # noqa: BLE001
            logging.warning("GET %s failed (%s), attempt %d", url, exc, attempt + 1)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"GACC page unavailable: {url}")


def _num(v) -> float | None:
    s = str(v).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _tonnes(q: float | None, unit: str) -> float | None:
    if q is None:
        return None
    u = " ".join(unit.lower().split())      # GACC sometimes prints "10,000  Tons"
    if "10,000 ton" in u:
        return round(q * 10_000, 1)
    if u.strip() in ("ton", "tons"):
        return q
    return None    # other units (sets, cubic metres...) are not tonnes


def list_bulletins(pages: int = MAX_PAGES) -> dict[tuple[str, str], tuple[str, int]]:
    """{(YYYY-MM, flow): (table url, months covered)} for the USD tables (5) exports and (6) imports.

    Some years GACC publishes January and February as one table ("January-February YYYY"); it is keyed by
    February with 2 months covered, so it is never read as a single month."""
    found: dict[tuple[str, str], str] = {}
    empty = 0
    for page in range(1, pages + 1):
        try:
            html = _get(LIST_URL.format(page=page))
        except RuntimeError:
            if page == 1:
                raise
            continue
        # some list pages carry only tables (1)-(4); the list has ended after 3 pages without any bulletin link
        empty = 0 if "Statics/" in html else empty + 1
        if empty >= 3:
            break
        for m in LINK_RE.finditer(html):
            first = MONTHS[m["mon"].lower()]
            last = MONTHS[m["mon2"].lower()] if m["mon2"] else first
            month = f"{m['yr']}-{last:02d}"
            href = m["href"] if m["href"].startswith("http") else BASE + "/" + m["href"].lstrip("/")
            found.setdefault((month, "export" if m["flow"] == "Exports" else "import"), (href, last - first + 1))
        time.sleep(1)
    return found


def parse_table(url: str, month: str, flow: str, period_months: int = 1) -> list[dict]:
    df = max(pd.read_html(io.StringIO(_get(url))), key=len)
    head = " ".join(str(x) for x in df.iloc[:4].values.ravel())
    if "USD1 Million" not in head.replace(" ", "").replace("USD1Million", "USD1 Million"):
        raise RuntimeError(f"{url}: value unit is not 'USD1 Million' - table layout changed")
    # column pairs are labelled on the header row: monthly tables print (month, "1-N Total", ...); the combined
    # January-February table prints ("1-2 Total", "1-2 Total[, <previous year>]", year-on-year), i.e. its own pair
    # IS the year to date and the second pair is last year's figure (checked on the printed year-on-year column)
    hdr = next((i for i in range(len(df)) if " ".join(str(df.iloc[i, 1]).split()) in ("QTY Unit", "Quantity Unit")),
               None)
    if hdr is None:
        raise RuntimeError(f"{url}: header row not found - table layout changed")
    second = str(df.iloc[hdr, 4])
    prior_year = period_months == 2
    if "Total" not in second:
        raise RuntimeError(f"{url}: unexpected column label {second!r} - table layout changed")
    rows = []
    for _, r in df.iloc[hdr + 2:].iterrows():
        name = str(r.iloc[0]).strip()
        unit = str(r.iloc[1]).strip()
        if not name or name.lower() == "nan":
            continue
        q, v, yq, yv = (_num(r.iloc[i]) for i in (2, 3, 4, 5))
        if prior_year:
            yq, yv = q, v
        if v is None:
            continue
        rows.append({
            "date": f"{month}-01", "period_months": period_months, "flow": flow, "commodity": name,
            "qty_unit_printed": unit,
            "quantity_tonnes": _tonnes(q, unit), "value_usd": round(v * 1e6, 0),
            "ytd_quantity_tonnes": _tonnes(yq, unit), "ytd_value_usd": round(yv * 1e6, 0) if yv is not None else None,
            "source_url": url, "publisher": "General Administration of Customs of China (GACC), Monthly Bulletin",
        })
    if not rows:
        raise RuntimeError(f"{url}: no commodity rows parsed")
    return rows


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    pages = int(sys.argv[sys.argv.index("--pages") + 1]) if "--pages" in sys.argv else MAX_PAGES
    bulletin = _read(BULLETIN_CSV)
    for r in bulletin:
        r.setdefault("period_months", "1")
        r["period_months"] = r["period_months"] or "1"
    have = {(r["date"][:7], r["flow"]) for r in bulletin}
    try:
        tables = list_bulletins(pages)
    except Exception as exc:  # noqa: BLE001
        logging.error("GACC bulletin list unavailable (%s); files kept as-is", exc)
        return 1
    new_rows, failed = [], []
    for (month, flow), (url, span) in sorted(tables.items()):
        if (month, flow) in have:
            continue
        try:
            new_rows += parse_table(url, month, flow, span)
            logging.info("GACC %s %s: parsed %s", month, flow, url)
        except Exception as exc:  # noqa: BLE001
            # each month is independent: a month that fails stays missing (retried next run), the rest are kept
            logging.error("GACC %s %s failed (%s); month not written", month, flow, exc)
            failed.append((month, flow))
        time.sleep(1)
    rc = 1 if any(m == max(t[0] for t in tables) for m, _ in failed) else 0    # fail the job only when the newest month failed
    if not new_rows:
        logging.info("GACC bulletin: nothing new (latest stored %s)", max((m for m, _ in have), default="-"))
        return rc

    bulletin += new_rows
    bulletin.sort(key=lambda r: (r["date"], r["flow"], r["commodity"]))
    with open(BULLETIN_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BULLETIN_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(bulletin)
    logging.info("Wrote %d new bulletin rows -> %s", len(new_rows), BULLETIN_CSV.name)

    # continue the HS series where the scope is the same
    hs_rows = _read(HS_CSV)
    if hs_rows:
        fields = list(hs_rows[0].keys())
        stored = {(r["date"][:7], r["hs_code"]) for r in hs_rows}
        template = {}
        for r in hs_rows:
            template[r["hs_code"]] = r      # last stored row per HS: commodity label and shipping class
        added = 0
        for r in new_rows:
            hs = HS_CONTINUATION.get((r["flow"], r["commodity"]))
            if int(r["period_months"]) != 1:
                continue      # a two-month table is not a monthly value of the HS series
            if not hs or (r["date"][:7], hs) in stored or hs not in template:
                continue
            t = template[hs]
            row = {k: "" for k in fields}
            row.update({"date": r["date"], "hs_code": hs, "commodity": t["commodity"], "flow": r["flow"],
                        "shipping_class": t["shipping_class"], "value_usd": f"{r['value_usd']:.1f}",
                        "source_url": r["source_url"], "publisher": r["publisher"],
                        "method": "GACC Monthly Bulletin table (6), same scope as the HS series"})
            if "partner_count" in row:
                row["partner_count"] = ""
            hs_rows.append(row)
            added += 1
        if added:
            hs_rows.sort(key=lambda r: (r["commodity"], r["date"]))   # stored order
            with open(HS_CSV, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
                w.writeheader()
                w.writerows(hs_rows)
            logging.info("Continued %d HS series rows in %s", added, HS_CSV.name)
    if failed:
        logging.warning("GACC months not parsed: %s", ", ".join(f"{m} {f}" for m, f in failed))
    return rc


if __name__ == "__main__":
    sys.exit(main())
