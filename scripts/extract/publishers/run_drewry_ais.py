"""
Drewry AIS Analytics: report Markdown, KPI sidecars and per-class KPI series, from the PDF text layer.

The weekly Drewry AIS PDFs are Power BI exports with a full text layer, so nothing here is parsed by a
model or read off an image:
  - KPI tiles: the 14 pt figure ("89.9%", "▼ 1.0", "$859") and the bold 11 pt caption under it;
  - commentary: the bold headline above the "content_summary" marker and its ● bullets;
  - chart titles, with each chart's lines read exactly from the vector paths by run_drewry_ais_charts.py
    (the Markdown gives each line's latest reading; the full weekly history is in
    data/extracted/series/drewry_ais_chart_series.csv);
  - the glossary table.
An earlier version sent the pages to LlamaParse, which wrote tables of invented values under every chart
and left most tiles blank; those outputs were rebuilt from this script.

Outputs per report: data/extracted/md/drewry/ais/<class>/<stem>.md and <stem>.tables.json (the KPI record);
per class: data/extracted/series/drewry_ais_<class>_series.csv (one row per report).
"""

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pymupdf

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_drewry_ais_charts as charts  # noqa: E402

AIS_DIR = REPO_ROOT / "corpus" / "06-drewry" / "ais"
MD_BASE_DIR = REPO_ROOT / "data" / "extracted" / "md" / "drewry" / "ais"
SERIES_DIR = REPO_ROOT / "data" / "extracted" / "series"

VESSEL_CATEGORIES = ["Crude_Aframax", "Crude_Suezmax", "Crude_VLCC", "Drybulk_Capesize", "Drybulk_Panamax",
                     "Drybulk_Supramax", "Drybulk_Handysize", "Product_LR1", "Product_LR2", "LPG_FR"]

FIELDS = ["published_date", "report_year", "report_week", "sector", "vessel_class", "vessel_category",
          "current_utilisation_pct", "mom_utilisation_change_pp", "yoy_utilisation_change_pp",
          "tonne_miles_index", "tonne_miles_yoy_pct", "bunker_price_usd_per_t", "bunker_price_mom_pct",
          "ballast_speed_east_mom_pct", "ballast_speed_west_mom_pct", "anchor_capacity_west_mom_pct",
          "anchor_capacity_east_mom_pct", "anchor_4w_ma_change_mdwt", "laden_anchor_days_4w_change_pct",
          "laden_share_east_mom_pp", "laden_share_west_mom_pp", "commentary_title", "commentary_summary",
          "source_file"]

# tile caption (lower case, whitespace collapsed, "tonne- miles" joined) -> record field
TILES = {
    "current utilisation": "current_utilisation_pct",
    "mom percentage point change in utilisation": "mom_utilisation_change_pp",
    "mom change in utilisation": "mom_utilisation_change_pp",
    "yoy percentage point change in utilisation": "yoy_utilisation_change_pp",
    "yoy change in utilisation": "yoy_utilisation_change_pp",
    "current tonne-miles index": "tonne_miles_index",
    "yoy change in tonne-miles index": "tonne_miles_yoy_pct",
    "per tonne price of bunker at the end of the week": "bunker_price_usd_per_t",
    "mom change in bunker price": "bunker_price_mom_pct",
    "mom change in ballast speed in east": "ballast_speed_east_mom_pct",
    "mom change in ballast speed in west": "ballast_speed_west_mom_pct",
    "mom change in vessels' capacity at anchor in west": "anchor_capacity_west_mom_pct",
    "mom change in vessels' capacity at anchor in east": "anchor_capacity_east_mom_pct",
    "mdwt change in tonnage at anchor (4-week moving average)": "anchor_4w_ma_change_mdwt",
    "mdwt change in vessels at anchor (4-week moving average)": "anchor_4w_ma_change_mdwt",
    "change in laden anchor days (4-week moving average)": "laden_anchor_days_4w_change_pct",
    "mom percentage point change in the share of laden vessels in east": "laden_share_east_mom_pp",
    "mom percentage point change in the share of laden vessels in west": "laden_share_west_mom_pp",
}
TILE_RE = re.compile(r"([▲▼])?\s*(\$)?([\d,]+(?:\.\d+)?)(%?)")


def classify_vessel(filename: str) -> str:
    for cat in VESSEL_CATEGORIES:
        if cat.lower() in filename.lower():
            return cat
    return "Unknown"


def parse_date_week_year(filename: str, page1_text: str = "") -> tuple:
    m = re.search(r"Week(\d+)_(\d{4})", filename)
    week, year = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    pub = None
    m = re.search(r"Published on:\s*(\d{1,2}) ([A-Za-z]{3}),? (\d{4})", page1_text)
    if m:
        pub = datetime.strptime(" ".join(m.groups()), "%d %b %Y").strftime("%Y-%m-%d")
    return pub, week, year


def _caption(text):
    t = re.sub(r"\s+", " ", text).strip().lower()
    return t.replace("tonne- miles", "tonne-miles").replace("(4- week", "(4-week")


def read_page_text(page, k):
    """Tiles, commentary and glossary rows of one page, from its spans."""
    spans = [s for b in page.get_text("dict")["blocks"] for ln in b.get("lines", []) for s in ln["spans"]
             if s["text"].strip()]
    tiles, commentary, glossary = [], None, []

    left = [s for s in spans if s["bbox"][0] < 200 * k]
    for i, s in enumerate(left):
        if round(s["size"] / k) == 14 and "Bold" in s["font"] and TILE_RE.fullmatch(s["text"].strip()):
            cap = []
            for t in left[i + 1:]:
                if round(t["size"] / k) != 11 or "Bold" not in t["font"]:
                    break
                cap.append(t["text"])
            if cap:
                caption = " ".join(" ".join(cap).split()).replace("tonne- miles", "tonne-miles")
                tiles.append((s["text"].strip(), caption.replace("(4- week", "(4-week")))

    marker = next((s for s in spans if s["text"].strip() == "content_summary"), None)
    if marker:
        mx0, my0 = marker["bbox"][0], marker["bbox"][1]
        head = [s for s in spans if "Bold" in s["font"] and s["color"] == 0xFFFFFF and round(s["size"] / k) == 12
                and abs(s["bbox"][0] - mx0) < 30 * k and 0 < my0 - s["bbox"][1] < 45 * k]
        body = [s for s in spans if s["color"] == 0x353D42 and abs(s["bbox"][0] - mx0) < 30 * k and s["bbox"][1] > my0]
        text = " ".join(s["text"] for s in sorted(body, key=lambda s: (s["bbox"][1], s["bbox"][0])))
        bullets = [" ".join(b.split()) for b in text.split("●") if b.strip()]
        commentary = (" ".join(" ".join(s["text"] for s in sorted(head, key=lambda s: s["bbox"][1])).split()), bullets)

    if page.get_text().count("Define") and "Glossary" in page.get_text():
        rows, cur = [], None
        for s in sorted(spans, key=lambda s: (s["bbox"][1], s["bbox"][0])):
            x, txt = s["bbox"][0] / k, s["text"].strip()
            if s["bbox"][1] < 80 * k or txt in ("S No.", "Terms", "Define") or "PowerVisuals" in s["font"]:
                continue
            if x < 70 and txt.isdigit():
                cur = [txt, [], []]
                rows.append(cur)
            elif cur and 70 <= x < 185:
                cur[1].append(txt)
            elif cur and x >= 185:
                cur[2].append(txt)
        glossary = [(" ".join(t), " ".join(d)) for _, t, d in rows]
    return tiles, commentary, glossary


def tile_value(raw):
    m = TILE_RE.fullmatch(raw)
    v = float(m.group(3).replace(",", ""))
    return -v if m.group(1) == "▼" else v


def read_report(pdf_path: Path):
    doc = pymupdf.open(pdf_path)
    pub, week, year = parse_date_week_year(pdf_path.name, doc[0].get_text())
    cat = classify_vessel(pdf_path.name)
    sector, vessel = cat.split("_")
    record = {f: None for f in FIELDS}
    record.update(published_date=pub, report_year=year, report_week=week, sector=sector, vessel_class=vessel,
                  vessel_category=cat, commentary_title="", commentary_summary="", source_file=pdf_path.name)
    pages = []
    unmapped = []
    for page in doc:
        k = max(1, round(page.rect.width / 996))
        spans = charts._spans(page)
        header = [s["text"] for s in spans if s["color"] == 0xFFFFFF and round(s["size"] / k) == 14]
        name = header[-1] if header else f"Page {page.number + 1}"
        tiles, commentary, glossary = read_page_text(page, k)
        for raw, cap in tiles:
            field = TILES.get(_caption(cap))
            if field is None:
                unmapped.append(cap)
            elif field.endswith("utilisation_change_pp") and abs(tile_value(raw)) > 20:
                print(f"  {pdf_path.name}: tile '{raw} {cap}' prints a level, not a change; not recorded")
            elif record[field] is None:
                record[field] = tile_value(raw)
        if commentary and not record["commentary_title"]:
            record["commentary_title"], record["commentary_summary"] = commentary[0], " | ".join(commentary[1])
        log = []
        rows = []
        drawings = None
        chart_titles = []
        for title, box in charts._panels(page, spans, k):
            if commentary and title in commentary[0]:
                continue
            drawings = drawings if drawings is not None else page.get_drawings()
            got = [] if title.lower().startswith(charts.SKIP_CHARTS) else charts.read_chart(page, spans, drawings,
                                                                                            title, box, log, k)
            chart_titles.append((title, got))
            rows.extend(got)
        pages.append({"page": page.number + 1, "name": name, "tiles": tiles, "commentary": commentary,
                      "glossary": glossary, "charts": chart_titles})
    doc.close()
    if unmapped:
        print(f"  {pdf_path.name}: unmapped tiles {unmapped}")
    return record, pages


def _fmt(v):
    return f"{v:g}"


def _latest(rows):
    """One line per series: the latest point of each line on the chart."""
    out = []
    by = {}
    for r in rows:
        by.setdefault((r["series"], r["axis"]), []).append(r)
    for (series, axis), rs in by.items():
        if axis == "seasonal":
            years = sorted({r["year"] for r in rs})
            last = max(rs, key=lambda r: (r["year"], r["week"]))
            label = (series + " " if series else "") + f"one line per year {years[0]}-{years[-1]}"
            out.append(f"{label}; latest {last['year']} week {last['week']}: {_fmt(last['value'])}")
        else:
            first = min(rs, key=lambda r: (r["year"], r["week"]))
            last = max(rs, key=lambda r: (r["year"], r["week"]))
            label = (series + ": " if series else "") + (f"weekly {first['year']}-W{first['week']:02d} to "
                                                         f"{last['year']}-W{last['week']:02d}")
            out.append(f"{label}; latest {_fmt(last['value'])}")
    return sorted(out)


def render_md(record, pages, pdf_path: Path, frontmatter=None):
    cat = record["vessel_category"]
    sector, vessel = cat.split("_")
    week, year, pub = record["report_week"], record["report_year"], record["published_date"]
    source_rel = f"corpus/06-drewry/ais/{pdf_path.name}"
    title = f"Drewry AIS Fleet Performance Indicators - {sector} {vessel} (Week {week}, {year})"
    if frontmatter is None:
        frontmatter = "\n".join([
            "---", f'title: "{title}"', f'issue_date: "{pub}"', f"year: {year}", f"report_week: {week}",
            'publisher: "Drewry Maritime Research"', 'category: "ais_analytics"', f'sector: "{sector}"',
            f'vessel_class: "{vessel}"', f"current_utilisation_pct: {record['current_utilisation_pct']}",
            f"mom_utilisation_change_pp: {record['mom_utilisation_change_pp']}",
            f"yoy_utilisation_change_pp: {record['yoy_utilisation_change_pp']}",
            f"bunker_price_usd_per_t: {record['bunker_price_usd_per_t']}", f'source_file: "{source_rel}"',
            f"pages: {len(pages)}", "---"]) + "\n"
    L = [f"# {title}", "",
         f"**Publisher:** Drewry Maritime Research | **Issue Date:** {pub} | **Report Week:** Week {week:02d}, {year}",
         f"**Source Document:** `{source_rel}`", "",
         "Chart lines are read exactly from the report's vector paths; the full weekly history of every line is in "
         "`data/extracted/series/drewry_ais_chart_series.csv`. Lines plotted on a right axis (Baltic spot rates, "
         "bunker price) are not read.", ""]
    for p in pages[1:]:
        if not (p["tiles"] or p["commentary"] or p["charts"] or p["glossary"]):
            continue
        L += ["---", "", f"## {p['name']}", ""]
        for raw, cap in p["tiles"]:
            L.append(f"- **{cap}:** {raw}")
        if p["tiles"]:
            L.append("")
        if p["commentary"]:
            head, bullets = p["commentary"]
            L += [f"### {head}", ""] + [f"- {b}" for b in bullets] + [""]
        for ctitle, rows in p["charts"]:
            L.append(f"### {ctitle}")
            L.append("")
            if rows:
                unit = rows[0]["unit"]
                L += [f"- {line}" + (f" ({unit})" if unit else "") for line in _latest(rows)]
            elif ctitle.lower().startswith(charts.SKIP_CHARTS):
                L.append("- Bar chart of the month-on-month change of the fleet-performance lines; not read.")
            else:
                L.append("- Chart not read: its axes could not be calibrated exactly.")
            L.append("")
        if p["glossary"]:
            L += [f"- **{t}:** {d}" for t, d in p["glossary"]] + [""]
    return frontmatter + "\n" + "\n".join(L).rstrip() + "\n"


def write_report(pdf_path: Path):
    record, pages = read_report(pdf_path)
    cat = record["vessel_category"]
    md_dir = MD_BASE_DIR / cat
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{pdf_path.stem}.md"
    front = None
    if md_path.exists():    # keep an existing frontmatter, filling only the KPI fields it left empty
        old = md_path.read_text(encoding="utf-8")
        m = re.match(r"---\n.*?\n---\n", old, re.S)
        front = m.group(0) if m else None
        for key in ("current_utilisation_pct", "mom_utilisation_change_pp", "yoy_utilisation_change_pp",
                    "bunker_price_usd_per_t"):
            if front and record[key] is not None:
                front = front.replace(f"\n{key}: None\n", f"\n{key}: {record[key]}\n")
    md_path.write_text(render_md(record, pages, pdf_path, front), encoding="utf-8", newline="\n")
    (md_dir / f"{pdf_path.stem}.tables.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                                         encoding="utf-8", newline="\n")
    return record


def _upsert(cat, records):
    path = SERIES_DIR / f"drewry_ais_{cat.lower()}_series.csv"
    rows = {}
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows[r["source_file"]] = {k: r.get(k, "") for k in FIELDS}
    for rec in records:
        rows[rec["source_file"]] = {k: "" if rec[k] is None else rec[k] for k in FIELDS}
    out = sorted(rows.values(), key=lambda r: (int(r["report_year"] or 0), int(r["report_week"] or 0),
                                               r["source_file"]))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)


def extract_drewry_ais(pdf_path: Path, dry_run: bool = False) -> dict:
    """Entry point for the incremental orchestrator."""
    pdf_path = Path(pdf_path)
    cat = classify_vessel(pdf_path.name)
    if dry_run:
        pub, week, _ = parse_date_week_year(pdf_path.name)
        return {"stem": pdf_path.stem, "issue_date": pub, "report_week": week, "cat": cat}
    rec = write_report(pdf_path)
    _upsert(cat, [rec])
    return {"stem": pdf_path.stem, "record": rec, "cat": cat}


def run_pipeline(paths=None):
    pdfs = [Path(p) for p in paths] if paths else sorted(AIS_DIR.glob("*.pdf")) if AIS_DIR.is_dir() else []
    by_cat = {}
    for pdf in pdfs:
        cat = classify_vessel(pdf.name)
        if cat == "Unknown":
            print(f"skip {pdf.name}: unknown vessel class")
            continue
        by_cat.setdefault(cat, []).append(write_report(pdf))
    for cat, recs in by_cat.items():
        _upsert(cat, recs)
        print(f"{cat}: {len(recs)} reports")


if __name__ == "__main__":
    run_pipeline([a for a in sys.argv[1:] if not a.startswith("-")] or None)
