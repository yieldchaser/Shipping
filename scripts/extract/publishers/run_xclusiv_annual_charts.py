"""xclusiv ANNUAL chart snapshot - the cost-effective roll-out.

WHY ANNUAL, NOT ALL 266
-----------------------
Measured (docs/xclusiv_charts_ROLLOUT_VERDICT.md): the charts carry ROLLING ~2-year
windows, not cumulative history.
    2022-12-19 report -> Apr-21..Oct-22
    2022-12-27 report -> Apr-21..Oct-22   <- SAME window, one week later
    2026-08-31 report -> Aug-21..Feb-26
So consecutive reports re-read overlapping windows. A 2-year window sampled ONCE PER
YEAR covers every calendar year 2021-2026 with no year lost - only intra-year
resolution, and the chart exposes just 13 labelled x-positions anyway.

Full roll-out: 266 x 45 = 11,970 cr, mostly redundant.
Annual snapshot:  1 per year x 45 = 270 cr for 6 years.

THE CHART PAGE IS NOT ALWAYS 3
------------------------------
Page 3 in every era sampled for 2022-2026, but 2021 documents are 6 pages and print no
date labels on page 3 - a different layout. So the chart page is DETECTED per document
by the page that actually carries the TCE series labels, and the detection is recorded
so a miss is visible rather than silent.
"""
import argparse, glob, importlib.util, json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "extracted" / "llamaparse_xclusiv_charts"

_spec = importlib.util.spec_from_file_location(
    "lp", ROOT / "scripts" / "extract" / "publishers" / "test_xclusiv_charts.py")
T = importlib.util.module_from_spec(_spec)
sys.modules["lp"] = T
_spec.loader.exec_module(T)

# A prose mention ("VLCC average T/C ended the week up at USD...") appears on the
# commentary pages too, so matching a single label picked page 1 for 2021-2023. A real
# chart page carries a DENSE CLUSTER of series labels - the legend names several series
# at once, plus axis titles.
#
# MEASURED across one document per year (labels = regex hits, vec = vector drawings):
#     2021 p3  labels=19 vec=688      2024 p3 labels=21 vec=118
#     2022 p3  labels=33 vec=271      2025 p3 labels=20 vec=114
#     2023 p3  labels=33 vec=287      2026 p3 labels=18 vec=144
# Page 3 wins on label count in EVERY year, by a wide margin over the runner-up
# (next best is 7 labels). Vector count is NOT a usable signal: the 2024-2026 layout
# draws its charts with far fewer vector paths than 2021-2023 for the same charts, so a
# vector threshold that works for one era silently rejects the other three. Labels are
# the stable discriminator, so that is what the detection uses - with the vector count
# recorded for the log rather than used as a gate.
TCE_LABEL = re.compile(r"VLCC|SUEZMAX|AFRAMAX|MR ATLANTIC|1y\s*TC|TCE", re.I)
MIN_LABELS = 12
# The chart page is the SAME structural position across eras, so when detection is
# ambiguous, fall back to it rather than sending a wrong page. 2021-2026 all place the
# TCE charts on page 3.
FALLBACK_PAGE = 3


def chart_page_detail(pdf):
    """(page, labels, vector_drawings, source) for the chart page, or None.

    Picks the page with the most series labels. When no page clears MIN_LABELS the
    caller decides; a page-3 fallback is applied by the caller, not silently here.
    """
    import pymupdf
    best = None
    with pymupdf.open(pdf) as d:
        for pno, pg in enumerate(d, 1):
            labels = len(TCE_LABEL.findall(pg.get_text()))
            vec = len(pg.get_drawings())
            if best is None or labels > best[2]:
                best = (pno, labels, labels, vec)
    if best and best[2] >= MIN_LABELS:
        return (best[0], best[2], best[3], "labels")
    if best and best[1] >= 4 and best[0] == FALLBACK_PAGE:
        return (best[0], best[1], best[3], "fallback-page3")
    return None


def chart_page(pdf):
    det = chart_page_detail(pdf)
    return det[0] if det else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-year", type=int, default=1, help="documents per year")
    ap.add_argument("--tier", default="agentic_plus")
    ap.add_argument("--position", default="mid", choices=["early", "mid", "late"])
    a = ap.parse_args()

    key, source = T.get_api_key()
    if not key:
        print("ABORT: no LLAMA_CLOUD_API_KEY")
        sys.exit(2)
    from llama_cloud import LlamaCloud
    client = LlamaCloud(api_key=key)
    print(f"credential source: {source}")

    pdfs = sorted(glob.glob(str(ROOT / "corpus/01-brokers/xclusiv/*/*.pdf")))
    byyear = {}
    for p in pdfs:
        m = re.search(r"xclusiv/(\d{4})/", p.replace("\\", "/"))
        if m:
            byyear.setdefault(m.group(1), []).append(p)
    years = sorted(byyear)
    print(f"years: {years}  ({sum(len(v) for v in byyear.values())} docs total)")

    # choose per year, spread through the year so the rolling windows differ
    picks = []
    for y in years:
        docs = byyear[y]
        if not docs:
            continue
        frac = {"early": 0.2, "mid": 0.5, "late": 0.8}[a.position]
        n = max(1, min(a.per_year, len(docs)))
        for i in range(n):
            idx = int((frac + i / max(n, 1) * 0.4) * (len(docs) - 1))
            picks.append(docs[min(idx, len(docs) - 1)])
    print(f"selected {len(picks)} documents ({a.per_year}/year, {a.position})")
    for p in picks:
        print(f"   {os.path.basename(p)[:64]}")

    OUT.mkdir(parents=True, exist_ok=True)
    state_f = OUT / "_annual_state.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {"done": {}, "failed": {}}
    cr = 45
    est = 0
    for p in picks:
        stem = os.path.basename(p)[:-4]
        if stem in state["done"]:
            continue
        pg = chart_page(p)
        if not pg:
            state["failed"][stem] = "no TCE chart page detected"
            print(f"  {stem[:52]}: NO CHART PAGE DETECTED - skipped, not guessed")
            state_f.write_text(json.dumps(state, indent=1))
            continue
        est += cr
        t0 = time.time()
        try:
            fo = client.files.create(file=p, purpose="parse")
            res = client.parsing.parse(
                file_id=fo.id, tier=a.tier, version="latest",
                page_ranges={"target_pages": str(pg)},
                processing_options={"specialized_chart_parsing": a.tier},
                expand=["markdown_full", "items"],
            )
            md = getattr(res, "markdown_full", None) or ""
            (OUT / f"{stem}.md").write_text(md, encoding="utf-8")
            try:
                items = json.loads(res.items.model_dump_json())
                (OUT / f"{stem}.items.json").write_text(json.dumps(items), encoding="utf-8")
                tabs = []
                for page in (items.get("pages") or []):
                    for it in (page.get("items") or []):
                        if (it.get("type") or "").lower() == "table" and it.get("rows"):
                            tabs.append(it["rows"])
                (OUT / f"{stem}.tables.json").write_text(json.dumps(tabs, indent=1),
                                                         encoding="utf-8")
                tce = sum(1 for t in tabs
                          if re.search(r"TCE|VLCC|SUEZMAX|AFRAMAX|MR ", json.dumps(t), re.I))
                state["done"][stem] = {"chart_page": pg, "tables": len(tabs),
                                       "tce_like": tce, "secs": round(time.time() - t0)}
                print(f"  {stem[:52]}: page {pg}, {len(tabs)} tables, {tce} TCE-like, "
                      f"{time.time()-t0:.0f}s (cum est {est} cr)")
            except Exception as e:
                state["done"][stem] = {"chart_page": pg, "items_error": str(e)[:120]}
                print(f"  {stem[:52]}: page {pg}, markdown ok, items parse failed")
        except Exception as e:
            state["failed"][stem] = str(e)[:200]
            print(f"  {stem[:52]}: FAILED {str(e)[:120]}")
        state_f.write_text(json.dumps(state, indent=1))

    print()
    print(f"done={len(state['done'])} failed={len(state['failed'])} "
          f"credits~{est}")
    for k, v in state["failed"].items():
        print(f"   {k[:50]}: {v}")


if __name__ == "__main__":
    main()
