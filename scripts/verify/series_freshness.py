"""Readiness gate, check 3: every recurring series keeps up with its publisher's parsed issues.

A series whose newest row is older than the newest MD of its publisher (beyond the publisher's cadence) means
new issues are parsed but never joined into the series: the auto-join step is missing or broken. Series that
are closed by design (a superseded channel, a one-off historical table) or printed only in some issues are
listed in CLOSED / OCCASIONAL with the reason, and reported, not failed.

    python scripts/verify/series_freshness.py            # table + exit 1 when a live series lags
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERIES = ROOT / "data" / "extracted" / "series"
MD = ROOT / "data" / "extracted" / "md"

# series-name prefix -> (MD folder of the publisher, allowed lag in days)
SOURCES = [
    (r"^hellenic_iron_ore_pdf_|^hellenic_iron_ore_(daily|commentary|table)|^hellenic_capesize|^hellenic_smm",
     "hellenic/iron_ore_pdf", 7),
    (r"^hellenic_alibra_dry", "hellenic/dry_charter", 10),
    (r"^hellenic_alibra_tanker", "hellenic/tanker_charter", 10),
    (r"^hellenic_vv_", "hellenic/vessel_valuations", 10),
    (r"^(hellenic_)?best_oasis_", "hellenic/demolition/best_oasis", 14),
    (r"^(hellenic_)?gms_", "hellenic/demolition/gms", 14),
    (r"^athenian_", "hellenic/demolition/athenian", 14),
    (r"^bancosta_", "banchero_costa", 10),
    (r"^star_asia_", "star_asia", 10),
    (r"^advanced_shipping_", "advanced_shipping", 10),
    (r"^drewry_ais_", "drewry/ais", 10),
    (r"^drewry_", "drewry/opinions", 10),
    (r"^(compare_vs_)?clarksons_", "clarksons", 10),
    (r"^ism_handy_", "ism", 35),          # the Handy edition comes every 4th week, coasters in between
    (r"^([a-z]+)_", None, 10),             # default: the first word is the MD folder
]

CLOSED = {   # closed by design: name -> reason
    "poten_fixtures_series": "fixture list printed until 2014 only",
    "poten_fleet_statistics_series": "fleet statistics table printed until 2020 only",
    "athenian_historical_demolition_prices_series": "one-off historical table",
    "athenian_market_commentary_series": "Athenian commentary channel replaced 2021",
    "clarksons_demolition_sales_series": "old Clarksons layout (to 2024-02)",
    "clarksons_demolition_series": "old Clarksons layout (to 2024-02)",
    "clarksons_desk_talk_series": "Hellenic shipbuilding channel, superseded 2026-08 by corpus/01-brokers/clarksons",
    "clarksons_macro_series": "Hellenic shipbuilding channel, superseded 2026-08",
    "clarksons_snp_sales_series": "Hellenic shipbuilding channel, superseded 2026-08 (clarksons_sales_series)",
    "compare_vs_clarksons_snp_sales_series": "comparison artefact of the superseded channel",
    "compare_vs_clarksons_sales_series": "comparison artefact",
    # HSN replaced the MMi 6-page daily with the SMM 1-page daily on 2026-09-14; these tables are MMi-only (the
    # SMM page continues in hellenic_iron_ore_pdf_{dashboard,indices,futures,brands,averages}, smm_market_drivers,
    # and carries on hellenic_iron_ore_daily / _commentary)
    **{f"hellenic_iron_ore_pdf_{t}_series": "MMi 6-page report, replaced by the SMM 1-page daily 2026-09-14"
       for t in ("brand_specs", "domestic_concentrate", "freight_rates", "import_volumes", "index_comparisons",
                 "normalisations", "port_differentials", "port_inventories", "spreads", "steel_mill_pnl", "steel")},
    "hellenic_iron_ore_table_series": "MMi 6-page report, replaced by the SMM 1-page daily 2026-09-14",
    "hellenic_capesize_c3_c5_series": "MMi 6-page report, replaced by the SMM 1-page daily 2026-09-14",
    "hellenic_vv_benchmark_sales_series": "legacy subset, superseded by hellenic_vv_sales_series (parse engine, has VV value)",
}
OCCASIONAL = {   # printed only in some issues: name -> reason
    "poten_top_charterers_series": "table in some opinions only",
    "poten_fleet_delivery_schedule_series": "table in some opinions only",
    "poten_tanker_orderbook_age_series": "table in some opinions only",
    "poten_vlcc_historical_rates_series": "table in some opinions only",
    "star_asia_ldt_comparison_series": "comparison printed in some issues only",
    "singletons_sales_series": "one-off broker documents",
    "signal_vessel_counts_series": "counts are text only in some monitors (W41 2026 prints Table 2 as a screenshot)",
    "seabrokers_renewables_and_ets_series": "feature article in some issues only",
    "carriers_demolition_series": "weeks with no demolition deal print \"None Reported\" (W39-W41 2026, checked on the PDFs)",
}
DATE_COLS = ("issue_date", "report_date", "date", "as_of_date", "week_ending")
ISO = re.compile(r"(20\d\d)-(\d\d)-(\d\d)")
NAME_DATE = re.compile(r"(20\d\d)-(\d\d)-(\d\d)|_(\d\d)_(\d\d)_(20\d\d)_|(20\d\d)_W(\d\d)")


def series_newest(path: Path) -> str | None:
    csv.field_size_limit(10 ** 9)
    with open(path, encoding="utf-8-sig", errors="ignore", newline="") as fh:
        rd = csv.reader(fh)
        try:
            hdr = next(rd)
        except StopIteration:
            return None
        cols = [i for i, c in enumerate(hdr) if c.strip().lower() in DATE_COLS]
        if not cols:
            return None
        i, best = cols[0], ""
        for row in rd:
            if i < len(row) and ISO.match(row[i]) and row[i][:10] > best:
                best = row[i][:10]
    return best or None


def md_date(md: Path) -> str | None:
    """The issue date in the file name (cheap; 20k MDs), else the frontmatter's."""
    m = NAME_DATE.search(md.name)
    if not m:
        with open(md, encoding="utf-8", errors="ignore") as fh:
            head = fh.read(1200)
        m = re.search(r"^(?:issue_date|report_date|date):\s*['\"]?(20\d\d-\d\d-\d\d)", head, re.M)
        return m.group(1) if m else None
    g = m.groups()
    if g[0]:
        return f"{g[0]}-{g[1]}-{g[2]}"
    if g[3]:
        return f"{g[5]}-{g[4]}-{g[3]}"
    try:
        return dt.date.fromisocalendar(int(g[6]), int(g[7]), 1).isoformat()
    except ValueError:
        return None


_md_cache: dict[str, str | None] = {}


def md_newest(folder: str) -> str | None:
    if folder not in _md_cache:
        d = MD / folder
        dates = [x for x in (md_date(p) for p in d.rglob("*.md")) if x] if d.is_dir() else []
        _md_cache[folder] = max(dates) if dates else None
    return _md_cache[folder]


def folder_for(name: str) -> tuple[str | None, int]:
    for rx, folder, lag in SOURCES:
        m = re.match(rx, name)
        if m:
            if folder is None:
                f = m.group(1)
                f = {"advanced": "advanced_shipping", "star": "star_asia"}.get(f, f)
                return (f if (MD / f).is_dir() else None), lag
            return folder, lag
    return None, 10


def main() -> int:
    rows, failing = [], 0
    for p in sorted(SERIES.glob("*_series.csv")):
        name = p.stem
        folder, lag = folder_for(name)
        s_new = series_newest(p)
        m_new = md_newest(folder) if folder else None
        if not (s_new and m_new):
            continue
        behind = (dt.date.fromisoformat(m_new) - dt.date.fromisoformat(s_new)).days
        if name in CLOSED:
            state = "closed: " + CLOSED[name]
        elif name in OCCASIONAL:
            state = "occasional: " + OCCASIONAL[name]
        elif behind > lag:
            state = "LAGGING"
            failing += 1
        else:
            state = "ok"
        rows.append((state != "ok" and state.startswith("LAG"), name, s_new, folder, m_new, behind, state))
    print(f"{'series':52} {'newest row':10} {'newest MD':10} {'days':>5}  state")
    for _, name, s_new, folder, m_new, behind, state in sorted(rows, key=lambda r: (not r[0], r[1])):
        print(f"{name:52} {s_new:10} {m_new:10} {behind:5}  {state}")
    print(f"\n{failing} live series lag their publisher's newest parsed issue")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
