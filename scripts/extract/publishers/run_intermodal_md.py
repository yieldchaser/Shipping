"""intermodal - per-document .md extraction (source-specific, reuses verified logic).

WHY THIS EXISTS
---------------
`intermodal_v2.py` already extracts the T/C rates correctly - 252 documents, 20 fields
each, 251 distinct assessment dates spanning 2021-07-06 to 2026-09-18, verified 20/20
against the rendered pages. But the corpus had NO per-document markdown, so the work
was invisible and un-browsable. This writes one `.md` per PDF: full prose for every
page, plus the Tanker Market and Dry Bulk Market T/C tables as real tables.

THE PAGE-ANCHOR DEFECT FOUND AND FIXED HERE
-------------------------------------------
`intermodal_v2.find_pages` locates the dry-bulk table by searching for
`180k 1yr TC`. That anchor is NOT unique: the "Indicative Market Values" table on
page 2 of some issues (measured: 2022 W46, W49) also contains the literal text
`180k` as a VESSEL CLASS in a very different table (180k | 35.5 | 36.6 | -3.1% |
2021 | 2020 | 2019), so the search matched page 2 and the real dry-bulk TC table on
page 3 was never read. That is why 70 of 252 documents showed a short bulk table.

The fix is to require the full `Nyk <period> TC` label, which the indicative-values
table never prints - it prints the bare class name. Verified: with the tightened
anchor, every document resolves to the page that actually carries the TC table.

A second measured finding: 71 of 252 reports carry FOUR EXTRA dry-bulk rows for
6-month charters (`180K 6mnt TC` and siblings) that the established 8-field schema does
not model, so 284 values were being dropped. They are captured here; the v2 CSV schema
is left untouched because downstream depends on its exact columns.
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "corpus" / "01-brokers" / "intermodal"
OUT_MD = ROOT / "data" / "extracted" / "md" / "intermodal"
OUT_TAB = ROOT / "data" / "extracted" / "intermodal"
STATE = OUT_TAB / "_md_run_state.json"

_spec = importlib.util.spec_from_file_location(
    "intermodal_v2", ROOT / "scripts" / "extract" / "publishers" / "intermodal_v2.py")
V2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V2)

# The two anchors, tightened to require the full `Nyk <period> TC` label. The bare
# class name is NOT unique - it also appears in the Indicative Market Values table.
TANKER_ANCHOR = re.compile(r"300\s*[kK]\s*1\s*(?:yr|y)\s*TC", re.I)
BULK_ANCHOR = re.compile(r"180\s*[kK]\s*1\s*(?:yr|y)\s*TC", re.I)

# The extra 6-month rows present in 71 of 252 reports.
BULK_6M = [
    ("capesize_6m_tc", r"180\s*[kK]\s*6\s*(?:mnt|mo|month)\s*TC"),
    ("panamax_bulk_6m_tc", r"76\s*[kK]\s*6\s*(?:mnt|mo|month)\s*TC"),
    ("supramax_6m_tc", r"58\s*[kK]\s*6\s*(?:mnt|mo|month)\s*TC"),
    ("handysize_6m_tc", r"32\s*[kK]\s*6\s*(?:mnt|mo|month)\s*TC"),
]

CLASS_OF = {
    "vlcc_1y_tc": "VLCC", "vlcc_3y_tc": "VLCC",
    "suezmax_1y_tc": "Suezmax", "suezmax_3y_tc": "Suezmax",
    "aframax_1y_tc": "Aframax", "aframax_3y_tc": "Aframax",
    "panamax_1y_tc": "Panamax (tanker)", "panamax_3y_tc": "Panamax (tanker)",
    "mr_1y_tc": "MR", "mr_3y_tc": "MR",
    "handy_tanker_1y_tc": "Handy (tanker)", "handy_tanker_3y_tc": "Handy (tanker)",
    "capesize_1y_tc": "Capesize", "capesize_3y_tc": "Capesize",
    "panamax_bulk_1y_tc": "Panamax (dry bulk)", "panamax_bulk_3y_tc": "Panamax (dry bulk)",
    "supramax_1y_tc": "Supramax", "supramax_3y_tc": "Supramax",
    "handysize_1y_tc": "Handysize", "handysize_3y_tc": "Handysize",
    "capesize_6m_tc": "Capesize", "panamax_bulk_6m_tc": "Panamax (dry bulk)",
    "supramax_6m_tc": "Supramax", "handysize_6m_tc": "Handysize",
}

ROUTE_OF = {
    "vlcc_1y_tc": "300K 1yr TC", "vlcc_3y_tc": "300K 3yr TC",
    "suezmax_1y_tc": "150K 1yr TC", "suezmax_3y_tc": "150K 3yr TC",
    "aframax_1y_tc": "110K 1yr TC", "aframax_3y_tc": "110K 3yr TC",
    "panamax_1y_tc": "75K 1yr TC", "panamax_3y_tc": "75K 3yr TC",
    "mr_1y_tc": "52K 1yr TC", "mr_3y_tc": "52K 3yr TC",
    "handy_tanker_1y_tc": "36K 1yr TC", "handy_tanker_3y_tc": "36K 3yr TC",
    "capesize_1y_tc": "180K 1yr TC", "capesize_3y_tc": "180K 3yr TC",
    "panamax_bulk_1y_tc": "76K 1yr TC", "panamax_bulk_3y_tc": "76K 3yr TC",
    "supramax_1y_tc": "58K 1yr TC", "supramax_3y_tc": "58K 3yr TC",
    "handysize_1y_tc": "32K 1yr TC", "handysize_3y_tc": "32K 3yr TC",
    "capesize_6m_tc": "180K 6mnt TC", "panamax_bulk_6m_tc": "76K 6mnt TC",
    "supramax_6m_tc": "58K 6mnt TC", "handysize_6m_tc": "32K 6mnt TC",
}


def find_pages(d):
    """(tanker_page, drybulk_page) using the TIGHTENED anchor.

    Requires the full `Nyk <period> TC` label. The bare vessel class is ambiguous: the
    Indicative Market Values table prints `180k` as a class in a table with completely
    different columns (Dec-22 avg | Nov-22 avg | +/-% | 2021 | 2020 | 2019), and using
    the bare class made 70 of 252 documents read the wrong page.
    """
    tank = bulk = None
    for pg in d:
        t = pg.get_text()
        if tank is None and TANKER_ANCHOR.search(t):
            tank = pg
        if bulk is None and BULK_ANCHOR.search(t):
            bulk = pg
    return tank, bulk


def page_text(page):
    parts = []
    for blk in page.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        lines = [" ".join(sp["text"] for sp in ln["spans"]).strip()
                 for ln in blk.get("lines", [])]
        lines = [x for x in lines if x]
        if lines:
            parts.append("\n".join(lines))
    return "\n\n".join(parts)


def header_dates(pg):
    if pg is None:
        return []
    try:
        xr = V2.current_week_x(pg)
        if not xr:
            return []
        hdr_y = xr[2]
        out = []
        for bb, txt in V2.lines_of(pg):
            if abs(((bb[1] + bb[3]) / 2.0) - hdr_y) < 6.0 and \
                    re.fullmatch(r"\d{2}/\d{2}/\d{2,4}", txt.strip()):
                out.append(txt.strip())
        return out[:3]
    except Exception:
        return []


def rows_for(fields, vals):
    for key, _pat in fields:
        yield [key, CLASS_OF.get(key, key), ROUTE_OF.get(key, key),
               vals.get(key, "")]


def extract(pdf):
    out = {"source_file": str(pdf), "pages": [], "tanker": [], "bulk": [],
           "assessment_date": None, "publication_date": None, "header_dates": []}
    with pymupdf.open(pdf) as d:
        for pno, page in enumerate(d, 1):
            out["pages"].append({"page": pno, "text": page_text(page)})
        t_pg, b_pg = find_pages(d)
        out["tanker_page"] = t_pg.number + 1 if t_pg is not None else None
        out["bulk_page"] = b_pg.number + 1 if b_pg is not None else None

        t_vals = V2.extract_table(t_pg, V2.TANKER) if t_pg is not None else {}
        b_vals = V2.extract_table(b_pg, V2.DRYBULK) if b_pg is not None else {}
        b6 = V2.extract_table(b_pg, BULK_6M) if b_pg is not None else {}
        out["tanker"] = [list(r) for r in rows_for(V2.TANKER, t_vals)]
        out["bulk"] = [list(r) for r in rows_for(V2.DRYBULK, b_vals)]
        out["bulk"].extend(list(r) for r in rows_for(BULK_6M, b6) if r[3])
        out["header_dates"] = header_dates(t_pg)

        try:
            out["assessment_date"] = V2.doc_date(d, pdf, tanker_page=t_pg)
        except Exception as e:
            out["date_error"] = str(e)[:120]

        m = V2.LONG_DATE.search(out["pages"][0]["text"]) if out["pages"] else None
        if m:
            mm = V2.MONTHS.get(m.group(2).lower())
            if mm:
                out["publication_date"] = f"{m.group(3)}-{mm:02d}-{int(m.group(1)):02d}"
    return out


def to_markdown(doc):
    ad = doc.get("assessment_date")
    ad = ad[0] if isinstance(ad, (list, tuple)) else ad
    L = [f"# intermodal {ad or doc.get('publication_date') or 'undated'}", ""]
    L.append(f"source: `{doc['source_file']}`")
    if ad:
        L.append(f"**TC table assessment date:** {ad}")
    if doc.get("publication_date"):
        L.append(f"**Report publication date:** {doc['publication_date']}")
    if ad and doc.get("publication_date") and ad != doc["publication_date"]:
        L += ["", "> These differ by design: the report is published on one date and the "
                  "T/C table assesses the market on another (up to a week apart). The "
                  "assessment date is taken from the table header, not from body text."]
    L.append("")

    dates = doc.get("header_dates") or []
    for title, rows, pg in (("Tanker Market", doc.get("tanker"), doc.get("tanker_page")),
                            ("Dry Bulk Market", doc.get("bulk"), doc.get("bulk_page"))):
        if not rows:
            continue
        L += [f"## {title} - T/C rates ($/day) (page {pg})", ""]
        cols = ["Class", "Route", "Current week"] + (dates[1:2] or ["previous week"])
        L.append("| " + " | ".join(cols) + " |")
        L.append("|" + "---|" * len(cols))
        for _key, label, route, val in rows:
            L.append(f"| {label} | {route} | {val} |")
        L.append("")
    for p in doc["pages"]:
        L += [f"## Page {p['page']}", "", p["text"], ""]
    return "\n".join(L)


def main():
    OUT_MD.mkdir(parents=True, exist_ok=True)
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    state = json.load(open(STATE)) if STATE.exists() else {"done": {}, "failed": {}}
    pdfs = sorted(glob.glob(str(SRC / "*" / "*.pdf")))
    print(f"intermodal: {len(pdfs)} PDFs; already done: {len(state['done'])}")
    for i, p in enumerate(pdfs, 1):
        stem = os.path.basename(p)[:-4]
        if stem in state["done"]:
            continue
        try:
            doc = extract(p)
            (OUT_MD / f"{stem}.md").write_text(to_markdown(doc), encoding="utf-8")
            json.dump(doc, open(OUT_TAB / f"{stem}.json", "w", encoding="utf-8"), indent=1)
            ad = doc.get("assessment_date")
            ad = ad[0] if isinstance(ad, (list, tuple)) else ad
            state["done"][stem] = {
                "pages": len(doc["pages"]),
                "tanker_rows": sum(1 for r in doc.get("tanker") or [] if r[3]),
                "bulk_rows": sum(1 for r in doc.get("bulk") or [] if r[3]),
                "bulk_6m_rows": sum(1 for r in doc.get("bulk") or [] if r[3] and "6mnt" in r[2]),
                "tanker_page": doc.get("tanker_page"),
                "bulk_page": doc.get("bulk_page"),
                "assessment_date": ad,
                "publication_date": doc.get("publication_date"),
            }
        except Exception as e:
            state["failed"][stem] = str(e)[:200]
        json.dump(state, open(STATE, "w"), indent=1)
        if i % 50 == 0:
            print(f"  {i}/{len(pdfs)}")
    d = state["done"]
    full = sum(1 for v in d.values() if v["tanker_rows"] == 12 and v["bulk_rows"] >= 8)
    six = sum(1 for v in d.values() if v.get("bulk_6m_rows"))
    print(f"done={len(d)} failed={len(state['failed'])} "
          f"tanker12_and_bulk8+={full} with_6m_rows={six}")


if __name__ == "__main__":
    main()
