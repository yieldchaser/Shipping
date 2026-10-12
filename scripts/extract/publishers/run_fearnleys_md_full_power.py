"""
Fearnleys Bespoke Research Library (fearnleys-md) structured sidecars.

For every corpus MD this writes data/extracted/md/fearnleys-md/<year>/<stem>.tables.json holding only
exact data:
  - tables: the report's own data tables (API fullWidthTable / halfWidthTable blocks), cell for cell,
    with the nearest preceding heading as context;
  - printed_image_tables: tables Fearnleys publishes as images (the Cape composite model), transcribed
    in scripts/md_cleanup/fearnleys_md_image_tables.md and verified against OCR;
  - charts: the title and image file of every chart (the charts themselves are raster images with no
    embedded data, so no values are read off them).
It also seeds the extracted MD copy (with image links rewritten) when it does not exist yet.

An earlier version "calibrated" five chart families into series CSVs with hardcoded axis ranges and a
prose regex that mixed up volume and supply growth; those outputs were wrong and have been deleted
(for 2026-10-07 its P5 value was 10,273.97 against about 19,100 on the chart). Do not reintroduce
hardcoded-axis chart reading here.
"""

import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "md_cleanup"))
import fearnleys_md_rebuild  # noqa: E402

FEARNLEYS_MD_DIR = ROOT / "corpus" / "01-brokers" / "fearnleys-md"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "fearnleys-md"
CATALOG = ROOT / "data" / "reports" / "fearnleys_reports_catalog.json"

OUT_MD_DIR.mkdir(parents=True, exist_ok=True)


def parse_yaml_frontmatter(content):
    meta = {}
    m = re.match(r"^---\n(.*?)\n---", content, re.S)
    if not m:
        return meta
    for line in m.group(1).split("\n"):
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta


def blocks_of(report):
    blocks = report.get("content") or []
    return json.loads(blocks) if isinstance(blocks, str) else blocks


def table_rows(text):
    text = (text or "").replace("\xa0", " ").replace("​", "").strip("\n")   # keep the header's leading tab
    rows = [[c.strip() for c in r.split("\t")] for r in text.split("\n")]
    return [r for r in rows if any(r)]


def structure(report):
    tables, printed, charts = [], [], []
    heading = ""
    image_tables = fearnleys_md_rebuild.image_tables()
    for b in blocks_of(report):
        if not isinstance(b, dict):
            continue
        t, c = b.get("type", ""), b.get("content", "")
        if t in ("heading1", "heading2"):
            heading = fearnleys_md_rebuild.clean(c)
        elif t.endswith("Table"):
            rows = table_rows(c)
            if rows:
                tables.append({"section": heading, "header": rows[0], "rows": rows[1:]})
        elif t.endswith("ChartFromFile") or t == "chart":
            m = fearnleys_md_rebuild.BLOB.search((c or "").strip())
            if not m:
                continue
            fname = urllib.parse.unquote(m.group(2).split("?")[0].strip())
            key = f"{m.group(1)}/{fname}"
            title = fearnleys_md_rebuild.clean(b.get("title")) or Path(fname).stem.strip()
            charts.append({"section": heading, "title": title, "image": key})
            if key in image_tables:
                printed.append({"section": heading, "image": key, "markdown": image_tables[key].strip()})
    return tables, printed, charts


def run_fearnleys_md_pipeline():
    catalog = {r["id"]: r for r in json.load(open(CATALOG, encoding="utf-8"))}
    md_files = sorted(p for p in FEARNLEYS_MD_DIR.glob("*/*.md") if p.name != "INDEX.md")
    written = 0
    for md_p in md_files:
        content = md_p.read_text(encoding="utf-8")
        meta = parse_yaml_frontmatter(content)
        report = catalog.get(meta.get("report_id", ""))
        tables, printed, charts = structure(report) if report else ([], [], [])
        yr = str(meta.get("year") or md_p.parent.name)
        out_year_dir = OUT_MD_DIR / yr
        out_year_dir.mkdir(parents=True, exist_ok=True)
        sidecar = {
            "report_id": meta.get("report_id", ""),
            "issue_date": meta.get("issue_date", ""),
            "year": int(yr) if yr.isdigit() else 0,
            "department": meta.get("department", ""),
            "report_title": meta.get("title", ""),
            "source_markdown": md_p.name,
            "tables": tables,
            "printed_image_tables": printed,
            "charts_count": len(charts),
            "charts": charts,
        }
        (out_year_dir / f"{md_p.stem}.tables.json").write_text(
            json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        year_md_file = out_year_dir / f"{md_p.stem}.md"
        if not year_md_file.exists():
            # image links in the corpus copy are relative to corpus/01-brokers/fearnleys-md/<year>/
            content = content.replace("](../images/", "](../../../../../corpus/01-brokers/fearnleys-md/images/")
            year_md_file.write_text(content, encoding="utf-8", newline="\n")
        written += 1
    print(f"Wrote {written} fearnleys-md sidecars in {OUT_MD_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    run_fearnleys_md_pipeline()
