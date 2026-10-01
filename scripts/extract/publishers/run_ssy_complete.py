"""
Dedicated SSY Capesize Index Full Extraction Pipeline.

Extracts 100% of data across all 519 SSY Capesize reports (2021-2026):
  1. Basin Classification: Atlantic (259) vs Pacific (260)
  2. Dates & Metadata: Issue Date, Report Week, Rates Dates (Current & Previous)
  3. Market Commentary: Clean unbroken prose (filtering boilerplates & contacts)
  4. Route Freight Rates ($/t): 10 assessed routes per report (Trade, Cargo Size, Weight %, Rate Prev, Rate Curr, Change)
  5. SSY Calculated Index: Index (Prev, Curr) and Historical Changes (Prev Index, 4-Week, 1-Year, 2-Year)
  6. Time Charter Equivalents ($/Day): Trip and Round-voyage rates (from table or narrative prose)
  7. Vector Chart Integration: Connects vector curves from charts/ssy/*.charts.json
  8. Master Series CSVs:
     - data/extracted/series/ssy_route_rates_series.csv (5,190 rows)
     - data/extracted/series/ssy_capesize_index_time_series.csv (519 rows)
  9. Markdown & Sidecars:
     - data/extracted/md/ssy/<stem>.md
     - data/extracted/md/ssy/<stem>.tables.json
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pymupdf

try:  # shared byte-duplicate filter (see doc_dedup.py for why)
    from doc_dedup import byte_duplicate_stems
except ImportError:  # run as a script, not via the orchestrator
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from doc_dedup import byte_duplicate_stems

ROOT = Path(__file__).resolve().parents[3]
PUB = "ssy"
SRC = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB


def duplicate_stems() -> set:
    """Stems of corpus PDFs that are byte-identical to another corpus PDF.

    Measured 2026-10-01: 530 PDFs / 516 unique, 14 duplicate groups; 132 rows double-counted in the delivered ssy series (route_rates 120, capesize_index_time 12). Both copies were parsed and stacked, so the dropped copy's rows
    double-count. Keep the richest extraction, skip the rest.
    """
    return byte_duplicate_stems(SRC, OUT_MD)
OUT_CHARTS = ROOT / "data" / "extracted" / "charts" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"
STATE = OUT_MD / "_run_state_complete.json"

MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december"
]

PERCENT_RE = re.compile(r"^\d+(?:[.,]\d+)?\s*%$")
NUMERIC_RE = re.compile(r"^[\d][\d,.]*%?$|^[+-][\d][\d,.]*$|^[\d][\d,.]*/\d+%?$")
PROSE_RE = re.compile(r"[a-z]{3,}\s+[a-z]{3,}")
XCUT = 205.0


def parse_iso(tok: any) -> float | None:
    if tok is None:
        return None
    s = str(tok).strip().replace("%", "").replace("$", "").strip()
    if not s or not re.search(r"\d", s):
        return None
    neg = s.startswith("-")
    s = s.lstrip("+-").replace(",", "")
    s = re.sub(r"\.+", ".", s)  # handle publisher typos like 13..3 -> 13.3
    if s.count(".") > 1:
        return None
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def is_numeric_cell(t: str) -> bool:
    s = t.strip().replace("%", "").strip()
    if not s or not re.search(r"\d", s) or len(s) > 14:
        return False
    return bool(
        re.fullmatch(r"[\d.,]+( DWT)?", s)
        or re.fullmatch(r"[\d.,]+/[\d.]+%?", s)
        or re.fullmatch(r"[+-]?[\d.,]+", s)
    )


def spans_of(pg: pymupdf.Page):
    out = []
    for blk in pg.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                t = sp["text"].strip()
                if t:
                    out.append((sp["bbox"], t, round(sp["size"], 1)))
    return out


def detect_table_size(spans) -> float:
    sizes = Counter(sz for bb, t, sz in spans if is_numeric_cell(t))
    return sizes.most_common(1)[0][0] if sizes else 9.0


def _assemble_rows(rows_y, merged, tsz, tol, xmin=None):
    out = []
    for grp in merged:
        ylo, yhi = min(grp), max(grp) + 3
        cells = []
        for y, items in rows_y.items():
            if not (ylo <= y < yhi):
                continue
            for bb, t, sz in items:
                if abs(sz - tsz) > tol:
                    continue
                if len(t) > 44 or (PROSE_RE.search(t) and len(t) > 24):
                    continue
                if xmin is not None and bb[0] < xmin:
                    continue
                cells.append((round(bb[0]), round(bb[1]), round(bb[2]), t))
        if not cells:
            continue
        cells.sort()
        seen, row = set(), []
        for x0, y, x1, t in cells:
            if (x0, y, t) in seen:
                continue
            seen.add((x0, y, t))
            row.append((x0, x1, t))
        if (sum(1 for c in row if is_numeric_cell(c[2])) >= 2
                and any(not is_numeric_cell(c[2]) for c in row)):
            out.append({"y": min(grp), "cells": row})
    return out


def extract_page_rows(pg: pymupdf.Page):
    spans = spans_of(pg)
    tsz = detect_table_size(spans)
    tol = 0.65

    rows_y = {}
    for bb, t, sz in spans:
        key = round(bb[1] / 3.0) * 3.0
        rows_y.setdefault(key, []).append((bb, t, sz))

    bands = [
        y for y, items in sorted(rows_y.items())
        if sum(1 for bb, t, sz in items if is_numeric_cell(t) and abs(sz - tsz) <= tol) >= 2
    ]

    merged = []
    for y in bands:
        if merged and abs(y - merged[-1][-1]) <= 6:
            merged[-1].append(y)
        else:
            merged.append([y])

    first = _assemble_rows(rows_y, merged, tsz, tol)
    tx = Counter(r["cells"][0][0] for r in first).most_common(1)[0][0] if first else XCUT
    rows = _assemble_rows(rows_y, merged, tsz, tol, xmin=tx - 2.0)
    return rows, tx, tsz


def extract_metadata_and_dates(doc: pymupdf.Document, fname: str) -> dict:
    txt = doc[0].get_text()
    txt_upper = txt.upper()

    # Basin
    if "ATLANTIC" in fname.upper() or "_A20" in fname.upper() or "ATLANTIC CAPESIZE INDEX" in txt_upper[:400]:
        basin = "Atlantic"
    elif "PACIFIC" in fname.upper() or "_P20" in fname.upper() or "PACIFIC CAPESIZE INDEX" in txt_upper[:400]:
        basin = "Pacific"
    else:
        basin = "Unknown"

    # Column Dates
    col_dates = re.findall(r"(\d{2}/\d{2}/\d{4})", txt)
    prev_d, curr_d = None, None
    if len(col_dates) >= 2:
        try:
            d1 = datetime.strptime(col_dates[0], "%d/%m/%Y").strftime("%Y-%m-%d")
            d2 = datetime.strptime(col_dates[1], "%d/%m/%Y").strftime("%Y-%m-%d")
            prev_d, curr_d = (d1, d2) if d1 <= d2 else (d2, d1)
        except Exception:
            pass

    # Pub Date from text
    pub_date = None
    m_pub = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(20\d{2})", txt)
    if m_pub and m_pub.group(2).lower() in MONTHS:
        d = int(m_pub.group(1))
        m = MONTHS.index(m_pub.group(2).lower()) + 1
        y = int(m_pub.group(3))
        pub_date = f"{y:04d}-{m:02d}-{d:02d}"

    # Fallback to Filename Date
    fn_date = None
    m_fn1 = re.search(r"(?:A|P)?(20\d{2})(\d{2})(\d{2})", fname)
    m_fn2 = re.search(r"(\d{2})_(\d{2})_(20\d{2})", fname)
    if m_fn1:
        fn_date = f"{m_fn1.group(1)}-{m_fn1.group(2)}-{m_fn1.group(3)}"
    elif m_fn2:
        fn_date = f"{m_fn2.group(3)}-{m_fn2.group(2)}-{m_fn2.group(1)}"

    issue_date = curr_d or pub_date or fn_date
    dt = datetime.strptime(issue_date, "%Y-%m-%d")
    report_week = dt.isocalendar()[1]
    year = dt.year

    title = f"SSY {basin} Capesize Index"
    return {
        "publisher": "SSY",
        "title": title,
        "basin": basin,
        "issue_date": issue_date,
        "report_week": report_week,
        "year": year,
        "rates_date_curr": curr_d or issue_date,
        "rates_date_prev": prev_d,
        "publication_date_text": pub_date
    }


def extract_commentary_and_notes(doc: pymupdf.Document) -> dict:
    blocks = doc[0].get_text("blocks")
    commentary_paras = []
    index_notes = []
    contact_info = []

    for b in blocks:
        txt = b[4].strip()
        lines = [l.strip() for l in txt.split("\n") if l.strip()]
        if not lines:
            continue
        full = " ".join(lines)
        if ("This publication has been provided" in full or
                "While reasonable care has been taken" in full or
                "SSY Consultancy & Research" in full or
                "strictly prohibited" in full or
                "trading recommendation" in full):
            continue
        if ("London:" in full or "Email:" in full or "Website" in full):
            continue
        if ("Trade" in full and "Cargo Size" in full) or "Jan Feb Mar" in full:
            continue

        # Clean text
        t_clean = full.replace("\n", " ")
        t_clean = re.sub(r"(\b[a-zA-Z]+)-\s+([a-zA-Z]+\b)", r"\1\2", t_clean)
        t_clean = re.sub(r"\s+", " ", t_clean).strip()

        # Split off index notes
        m_idx = re.search(r"(The (?:Atlantic|Pacific) Capesize Index started at 5,?000 points.*)", t_clean, re.I)
        if m_idx:
            index_notes.append(m_idx.group(1).strip())
            t_clean = t_clean[:m_idx.start()].strip()

        # Split off contact info
        m_cont = re.search(r"(For more information (?:please )?contact.*)", t_clean, re.I)
        if m_cont:
            contact_info.append(m_cont.group(1).strip())
            t_clean = t_clean[:m_cont.start()].strip()

        # If narrative commentary remains
        keywords = ["fell", "rose", "climbed", "gained", "declined", "points", "rate", "rates", "spot", "voyage", "halved", "weakened", "strengthened"]
        if any(kw in t_clean.lower() for kw in keywords) and len(t_clean) > 30:
            if not t_clean.startswith("SSY ") or len(t_clean) > 40:
                commentary_paras.append(t_clean)

    return {
        "market_commentary": " ".join(commentary_paras) if commentary_paras else None,
        "index_notes": " ".join(index_notes) if index_notes else None,
        "contact_info": " ".join(contact_info) if contact_info else None
    }


def parse_tables_from_rows(raw_cell_rows: list[list[str]], meta: dict, doc_txt: str) -> dict:
    trade_rates = []
    tc_day_rates = []
    idx = {}

    seen_routes = set()

    for r in raw_cell_rows:
        if not r:
            continue
        head = r[0].strip()

        # Route Freight Rates ($/t)
        if ("/" in head or head.startswith("T/C")) and len(r) >= 4:
            weight = (r[2] or "").strip() if len(r) > 2 else ""
            if PERCENT_RE.match(weight):
                if head not in seen_routes:
                    seen_routes.add(head)
                    rate_prev = parse_iso(r[3]) if len(r) > 3 else None
                    rate_curr = parse_iso(r[4]) if len(r) > 4 else None
                    chg = round(rate_curr - rate_prev, 2) if (rate_curr is not None and rate_prev is not None) else None
                    trade_rates.append({
                        "route": head,
                        "cargo_size": r[1].strip() if len(r) > 1 else None,
                        "weight_pct": weight,
                        "rate_prev": rate_prev,
                        "rate_curr": rate_curr,
                        "change_usd_t": chg
                    })
            else:
                # Time charter day rate row from bottom table
                day_prev = parse_iso(r[2]) if len(r) > 2 else None
                day_curr = parse_iso(r[3]) if len(r) > 3 else None
                chg_day = round(day_curr - day_prev, 2) if (day_curr is not None and day_prev is not None) else None
                tc_day_rates.append({
                    "route": head,
                    "cargo_size": r[1].strip() if len(r) > 1 else None,
                    "day_rate_prev": day_prev,
                    "day_rate_curr": day_curr,
                    "change_usd_day": chg_day,
                    "source": "table"
                })

        # Calculated Index
        elif head.lower() == "calculated index":
            # The values are in r[1] and r[2] or r[3] and r[4]
            vals = [parse_iso(c) for c in r[1:] if parse_iso(c) is not None]
            if len(vals) >= 2:
                idx["value_prev"] = vals[0]
                idx["value_curr"] = vals[1]
            elif len(vals) == 1:
                idx["value_curr"] = vals[0]

        # Changes
        elif head.lower().startswith("change on"):
            key = (head.replace("Change on ", "").replace("change on ", "")
                   .lower().replace(" ago", "").replace(" ", "_"))
            vals = [parse_iso(c) for c in r[1:] if parse_iso(c) is not None]
            if len(vals) >= 2:
                idx[key] = {"prev": vals[0], "curr": vals[1]}
            elif len(vals) == 1:
                idx[key] = {"curr": vals[0]}

    # Fallback for prose day rates (2021-2022 era)
    if not tc_day_rates:
        doc_clean = doc_txt.replace("\n", " ")
        doc_clean = re.sub(r"\s+", " ", doc_clean)
        # Atlantic
        m_atl = re.search(
            r"round\s*-?\s*voyage and fronthaul rates (?:stand at|to a respective|to)\s*\$([\d,]+)/?\s*day\s*and\s*\$([\d,]+)/?\s*day",
            doc_clean, re.I
        )
        if m_atl:
            round_curr = parse_iso(m_atl.group(1))
            front_curr = parse_iso(m_atl.group(2))
            tc_day_rates.append({
                "route": "T/C TRANSATLANTIC ROUND",
                "cargo_size": "180,000 DWT",
                "day_rate_prev": None,
                "day_rate_curr": round_curr,
                "change_usd_day": None,
                "source": "prose"
            })
            tc_day_rates.append({
                "route": "T/C TRIP CONT/FAR EAST",
                "cargo_size": "180,000 DWT",
                "day_rate_prev": None,
                "day_rate_curr": front_curr,
                "change_usd_day": None,
                "source": "prose"
            })
        else:
            # Pacific
            m_pac = re.search(
                r"round\s*-?\s*voyage rate (?:rose|fell|increased|dropped|was|to)?.*?to\s*\$([\d,]+)/?\s*day",
                doc_clean, re.I
            )
            if m_pac:
                pac_curr = parse_iso(m_pac.group(1))
                tc_day_rates.append({
                    "route": "T/C TRANSPACIFIC ROUND",
                    "cargo_size": "180,000 DWT",
                    "day_rate_prev": None,
                    "day_rate_curr": pac_curr,
                    "change_usd_day": None,
                    "source": "prose"
                })

    return {
        "trade_rates": trade_rates,
        "timecharter_day_rates": tc_day_rates,
        "index": idx
    }


def generate_markdown(meta: dict, comm: dict, tables: dict, source_rel: str) -> str:
    lines = [
        "---",
        f"title: \"{meta['title']}\"",
        f"basin: \"{meta['basin']}\"",
        f"issue_date: \"{meta['issue_date']}\"",
        f"report_week: {meta['report_week']}",
        f"year: {meta['year']}",
        f"rates_date_curr: \"{meta['rates_date_curr']}\"",
        f"rates_date_prev: \"{meta['rates_date_prev']}\"",
        f"calculated_index: {tables['index'].get('value_curr', 'null')}",
        f"source_file: \"{source_rel}\"",
        "---",
        "",
        f"# {meta['title']} — Week {meta['report_week']}, {meta['year']}",
        "",
        f"**Issue Date:** {meta['issue_date']}  ",
        f"**Assessment Dates:** Current: {meta['rates_date_curr']} | Previous: {meta['rates_date_prev']}  ",
        f"**Source Document:** `{source_rel}`",
        "",
        "## Market Commentary",
        ""
    ]

    if comm.get("market_commentary"):
        lines.append(comm["market_commentary"])
    else:
        lines.append("*No desk narrative commentary published in this issue (pure quantitative data dashboard format).*")
    lines.append("")

    # Route Rates Table
    prev_d = meta["rates_date_prev"] or "Previous"
    curr_d = meta["rates_date_curr"] or "Current"

    lines.extend([
        "## Route Freight Rates ($/t)",
        "",
        f"| Route | Cargo Size | Weight (%) | {prev_d} ($/t) | {curr_d} ($/t) | Change ($/t) |",
        "|---|---|---|---|---|---|"
    ])
    for r in tables["trade_rates"]:
        chg_str = f"{r['change_usd_t']:+.2f}" if r["change_usd_t"] is not None else ""
        prev_str = f"{r['rate_prev']:.2f}" if r["rate_prev"] is not None else ""
        curr_str = f"{r['rate_curr']:.2f}" if r["rate_curr"] is not None else ""
        lines.append(f"| {r['route']} | {r['cargo_size']} | {r['weight_pct']} | {prev_str} | {curr_str} | {chg_str} |")
    lines.append("")

    # Calculated Index Table
    idx = tables["index"]
    lines.extend([
        "## Calculated Index & Historical Changes",
        "",
        f"| Metric | {prev_d} | {curr_d} |",
        "|---|---|---|"
    ])
    if "value_curr" in idx:
        v_prev = f"{idx.get('value_prev', 0):,.0f}" if idx.get("value_prev") is not None else ""
        v_curr = f"{idx.get('value_curr', 0):,.0f}" if idx.get("value_curr") is not None else ""
        lines.append(f"| **Calculated Index** | {v_prev} | {v_curr} |")

    metrics_map = [
        ("previous_index", "Change on Previous Index"),
        ("four_weeks", "Change on Four Weeks Ago"),
        ("previous_year", "Change on Previous Year"),
        ("two_years", "Change on Two Years Ago"),
    ]
    for key, label in metrics_map:
        if key in idx:
            item = idx[key]
            p_val = f"{item['prev']:+,.0f}" if isinstance(item, dict) and item.get("prev") is not None else ""
            c_val = f"{item['curr']:+,.0f}" if isinstance(item, dict) and item.get("curr") is not None else ""
            lines.append(f"| {label} | {p_val} | {c_val} |")
    lines.append("")

    # Timecharter Day Rates
    if tables["timecharter_day_rates"]:
        lines.extend([
            "## Timecharter Equivalents ($/Day)",
            "",
            f"| Route | Cargo Size | {prev_d} ($/Day) | {curr_d} ($/Day) | Change ($/Day) | Source |",
            "|---|---|---|---|---|---|"
        ])
        for tc in tables["timecharter_day_rates"]:
            prev_s = f"${tc['day_rate_prev']:,.0f}" if tc["day_rate_prev"] is not None else "—"
            curr_s = f"${tc['day_rate_curr']:,.0f}" if tc["day_rate_curr"] is not None else "—"
            chg_s = f"{tc['change_usd_day']:+,.0f}" if tc["change_usd_day"] is not None else "—"
            lines.append(f"| {tc['route']} | {tc['cargo_size'] or '180,000 DWT'} | {prev_s} | {curr_s} | {chg_s} | {tc['source']} |")
        lines.append("")

    # Index Inception Notes & Contact
    if comm.get("index_notes") or comm.get("contact_info"):
        lines.append("## Index Background & Contact")
        lines.append("")
        if comm.get("index_notes"):
            lines.append(f"**Index Definition:** {comm['index_notes']}  ")
        if comm.get("contact_info"):
            lines.append(f"**Contact:** {comm['contact_info']}  ")
        lines.append("")

    return "\n".join(lines)


def process_report(pdf_path: Path):
    stem = pdf_path.stem
    rel_path = pdf_path.resolve().relative_to(ROOT).as_posix()
    doc = pymupdf.open(pdf_path)
    doc_txt = doc[0].get_text()

    meta = extract_metadata_and_dates(doc, pdf_path.name)
    comm = extract_commentary_and_notes(doc)
    rows, tx, tsz = extract_page_rows(doc[0])
    raw_cells = [[c[2] for c in r["cells"]] for r in rows]
    tables = parse_tables_from_rows(raw_cells, meta, doc_txt)

    # Check for chart series
    chart_file = OUT_CHARTS / f"{pdf_path.name}.charts.json"
    chart_info = {"available": False}
    if chart_file.exists():
        try:
            cdata = json.loads(chart_file.read_text(encoding="utf-8"))
            chart_info = {
                "available": True,
                "n_series": len(cdata.get("series", [])),
                "total_points": sum(s.get("n_points", 0) for s in cdata.get("series", [])),
                "relative_gap_vs_printed": cdata.get("check", {}).get("rel_gap")
            }
        except Exception:
            pass

    md_content = generate_markdown(meta, comm, tables, rel_path)

    sidecar = {
        "metadata": meta,
        "commentary": comm,
        "calculated_index": tables["index"],
        "trade_rates": tables["trade_rates"],
        "timecharter_day_rates": tables["timecharter_day_rates"],
        "chart_series": chart_info,
        "n_trade_routes": len(tables["trade_rates"]),
        "n_tc_routes": len(tables["timecharter_day_rates"])
    }

    # Write files
    OUT_MD.mkdir(parents=True, exist_ok=True)
    (OUT_MD / f"{stem}.md").write_text(md_content, encoding="utf-8")
    (OUT_MD / f"{stem}.tables.json").write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "stem": stem,
        "meta": meta,
        "tables": tables,
        "n_routes": len(tables["trade_rates"]),
        "n_tc": len(tables["timecharter_day_rates"]),
        "curr_index": tables["index"].get("value_curr")
    }


def main():
    pdfs = sorted(SRC.rglob("*.pdf"))
    _dup = duplicate_stems()
    if _dup:
        _b = len(pdfs)
        pdfs = [q for q in pdfs if q.stem not in _dup]
        print(f"[dedup] skipped {_b - len(pdfs)} byte-identical duplicate document(s)")
    print(f"[{PUB}] Starting complete overhaul across all {len(pdfs)} reports...", flush=True)

    route_rows = []
    index_rows = []

    t0 = time.time()
    for idx, p in enumerate(pdfs, 1):
        res = process_report(p)
        meta = res["meta"]
        tables = res["tables"]

        # Collect route freight rates
        for tr in tables["trade_rates"]:
            route_rows.append({
                "issue_date": meta["issue_date"],
                "report_week": meta["report_week"],
                "year": meta["year"],
                "basin": meta["basin"],
                "route": tr["route"],
                "cargo_size": tr["cargo_size"],
                "weight_pct": tr["weight_pct"],
                "rates_date_prev": meta["rates_date_prev"],
                "rates_date_curr": meta["rates_date_curr"],
                "rate_prev": tr["rate_prev"],
                "rate_curr": tr["rate_curr"],
                "change_usd_t": tr["change_usd_t"],
                "source_file": p.name
            })

        # Collect index time series
        c_idx = tables["index"]
        prev_idx = c_idx.get("previous_index", {})
        fw_idx = c_idx.get("four_weeks", {})
        py_idx = c_idx.get("previous_year", {})
        ty_idx = c_idx.get("two_years", {})

        # Extract day rates
        tc_trip_curr, tc_trip_prev = None, None
        tc_round_curr, tc_round_prev = None, None
        for tc in tables["timecharter_day_rates"]:
            rt = tc["route"].upper()
            if "TRIP" in rt:
                tc_trip_curr = tc["day_rate_curr"]
                tc_trip_prev = tc["day_rate_prev"]
            elif "ROUND" in rt:
                tc_round_curr = tc["day_rate_curr"]
                tc_round_prev = tc["day_rate_prev"]

        index_rows.append({
            "issue_date": meta["issue_date"],
            "report_week": meta["report_week"],
            "year": meta["year"],
            "basin": meta["basin"],
            "rates_date_prev": meta["rates_date_prev"],
            "rates_date_curr": meta["rates_date_curr"],
            "calculated_index_prev": c_idx.get("value_prev"),
            "calculated_index_curr": c_idx.get("value_curr"),
            "change_prev_index": prev_idx.get("curr") if isinstance(prev_idx, dict) else prev_idx,
            "change_4w": fw_idx.get("curr") if isinstance(fw_idx, dict) else fw_idx,
            "change_1y": py_idx.get("curr") if isinstance(py_idx, dict) else py_idx,
            "change_2y": ty_idx.get("curr") if isinstance(ty_idx, dict) else ty_idx,
            "tc_trip_day_curr": tc_trip_curr,
            "tc_round_day_curr": tc_round_curr,
            "tc_trip_day_prev": tc_trip_prev,
            "tc_round_day_prev": tc_round_prev,
            "source_file": p.name
        })

        if idx % 50 == 0 or idx == len(pdfs):
            print(f"  [{idx}/{len(pdfs)}] processed: {p.stem[:45]:<45} "
                  f"routes={res['n_routes']} tc={res['n_tc']} idx={res['curr_index']} ({time.time()-t0:.1f}s)", flush=True)

    # Write Master Series CSVs
    OUT_SERIES.mkdir(parents=True, exist_ok=True)

    # 1. Route Rates Series
    route_csv = OUT_SERIES / "ssy_route_rates_series.csv"
    with open(route_csv, "w", newline="", encoding="utf-8") as f:
        fields = [
            "issue_date", "report_week", "year", "basin", "route", "cargo_size",
            "weight_pct", "rates_date_prev", "rates_date_curr", "rate_prev",
            "rate_curr", "change_usd_t", "source_file"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(route_rows)

    # 2. Capesize Index Time Series
    index_csv = OUT_SERIES / "ssy_capesize_index_time_series.csv"
    with open(index_csv, "w", newline="", encoding="utf-8") as f:
        fields = [
            "issue_date", "report_week", "year", "basin", "rates_date_prev",
            "rates_date_curr", "calculated_index_prev", "calculated_index_curr",
            "change_prev_index", "change_4w", "change_1y", "change_2y",
            "tc_trip_day_curr", "tc_round_day_curr", "tc_trip_day_prev",
            "tc_round_day_prev", "source_file"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(index_rows)

    print(f"\n[SSY COMPLETE] All {len(pdfs)} reports successfully processed!", flush=True)
    print(f"  -> Generated {len(route_rows)} route rate observations in {route_csv.name}", flush=True)
    print(f"  -> Generated {len(index_rows)} index time series records in {index_csv.name}", flush=True)
    print(f"  -> Total execution time: {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
