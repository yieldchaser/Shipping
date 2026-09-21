"""v1 per-source extraction configs: era pins, junk filters, quarantine, route overrides.

Derived from fingerprint vectors (seed 42) + golden bench. Each entry drives
scripts/extract/extract_all.py behavior per document.
"""
from datetime import date

SOURCES = {
    "agora": {"eras": [("2021-01-01", "2026-12-31", "snapshot-5pp")],
              "tables": "camelot+plumber union", "charts": "harvest",
              "notes": "Cleanest broker. img 5->11 in 2025 cosmetic."},
    "ssy": {"eras": [("2021-01-01", "2026-12-31", "index-sheet")],
            "tables": "union", "notes": "1pp Atlantic+Pacific same layout."},
    "advanced_shipping": {"eras": [("2021-01-01", "2026-12-31", "weekly-10pp")],
                          "tables": "union", "notes": "Skeleton stable; 2021 table-count noise."},
    "xclusiv": {"eras": [("2021-01-01", "2023-12-31", "indices-first-7pp"),
                         ("2024-01-01", "2026-12-31", "commentary-first-9pp")],
                "tables": "union per era"},
    "affinity": {"eras": [("2021-01-01", "2025-12-31", "one-pager"),
                          ("2026-01-01", "2026-12-31", "crude-product-split-2pp")],
                 "tables": "union per era"},
    "intermodal": {"eras": [("2021-01-01", "2023-12-31", "dense-tables"),
                            ("2024-01-01", "2026-12-31", "chart-heavy")],
                   "tables": "union; 2024+ needs chart vision later",
                   "notes": "2026 images jump 20s->60s."},
    "fearnleys": {"eras": [("2018-01-01", "2026-12-31", "fearnpulse-20pp")],
                  "quarantine": ["rapport-2.md", "2018 garbled-font PDFs -> garbled route"],
                  "tables": "union; text layer already complete in md mirrors"},
    "carriers": {"eras": [("2024-01-01", "2026-12-31", "house-3pp")],
                 "quarantine": ["pre-2024 Seasure-template files"],
                 "tables": "union"},
    "banchero_costa": {"eras": [("2021-01-01", "2026-12-31", "skeleton-16pp")],
                       "tables": "camelot-only fast path (chart-heavy, plumber slow)",
                       "charts": "harvest priority (few extractable tables)"},
    "star_asia": {"eras": [("2022-01-01", "2025-12-31", "macro-20pp"),
                           ("2026-01-01", "2026-12-31", "rebrand-16pp")],
                  "tables": "union"},
    "ism": {"eras": [("2023-01-01", "2026-12-31", "prose")],
            "tables": "none; NLP path only"},
    "clarksons": {"eras": [("2026-08-01", "2026-12-31", "desk-talk")],
                  "tables": "union; densest 8-24 tables"},
    "lion": {"eras": [("2025-01-01", "2026-12-31", "genuine-3pp")],
             "quarantine": ["2024 misfiled Star Asia 20pp file", "manifest gibson pollution"],
             "tables": "union"},
    "gibson": {"eras": [("2021-01-01", "2023-12-31", "tanker-8pp")],
               "post_2023": "text-only upstream; md mirrors cover",
               "tables": "union"},
    "allied": {"eras": [("2021-01-01", "2022-12-31", "stats-report"),
                        ("2023-01-01", "2024-02-28", "weekly-review")],
               "status": "dead-upstream", "tables": "union per era"},
    "golden_destiny": {"status": "dead-upstream", "eras": [("2021-01-01", "2024-12-31", "frozen-sp")]},
    "anchor": {"status": "dead-upstream", "eras": [("2021-01-01", "2022-12-31", "frozen")]},
    "poten": {"eras": [("2004-01-01", "2014-12-31", "essay-multipage"),
                       ("2015-01-01", "2026-12-31", "teaser-1pp")],
              "paths": {"essay": "LLM-summarize", "teaser": "parse direct"},
              "quarantine": ["unknown-01-01 stub dirs (weak dates)"]},
    "drewry_ais": {"eras": [("2024-01-01", "2026-12-31", "powerbi-9pp")],
                   "tables": "p2 bullets LLM-ready; charts vision later"},
    "drewry_wci": {"path": "csv direct; forward-fill; ragged tail"},
    "breakwave_dry_tanker": {"eras": [("2018-01-01", "2026-12-31", "fixed-2pp")],
                             "tables": "p2 fundamentals regex-parseable"},
    "breakwave_insights": {"junk_filter": "drop Yahoo/CNN dumps, Blogspot reposts (domain+boilerplate)",
                           "tables": "genuine 1-head articles parse direct"},
    "seabrokers": {"eras": [("2024-01-01", "2026-12-31", "fixed-md-table")],
                   "tables": "md table direct (most parse-friendly)"},
    "iron_ore": {"eras": [("2021-01-01", "2026-09-11", "mmi-6pp"),
                          ("2026-09-14", "2026-12-31", "smm-1pp")],
                 "tables": "dual parsers split 2026-09-12"},
    "demolition": {"eras": [("2021-01-01", "2026-12-31", "gms-best-oasis-athenian")],
                   "tables": "beach-price tables per source"},
    "dry_tanker_charter": {"tables": "IMAGE-ONLY Alibra; OCR deferred",
                           "notes": "layout identical since 2021; harvest jpgs"},
    "vessel_valuations": {"tables": "HTML regex S&P lines"},
    "signal_monitors": {"eras": [("2023-01-01", "2025-12-31", "short-notes"),
                                 ("2026-01-01", "2026-12-31", "structured-briefs")],
                        "tables": "prose+VLM charts later"},
    "signal_newsroom": {"tables": "ad-hoc prose, per-article"},
    "signal_newsletters": {"eras": [("2025-01-01", "2026-12-31", "monthly")],
                           "tables": "month-end index snapshot lines"},
    "baltic": {"quarantine": ["assets/ bot-wall placeholders"],
               "tables": "prose route-code regex; Alibra CSVs structured alternative"},
    "cftc": {"path": "ledgers done; monthly workflow live"},
    "ppa": {"path": "CSVs extracted; PDFs verify-only"},
}

# Modern-tool escalation ladder (free/local only), decided from bench
# v1.1 upgrade 2026-09-21: pymupdf-layout (CPU ONNX, ~3.4s/pg amortized) gives
# labeled regions (table/section-header/page-header/footer). Table bboxes fed
# as camelot table_areas (y-flipped) -> Star Asia golden 13/15 -> 15/15.
TOOL_LADDER = [
    ("pymupdf", "router + first-pass text; never the table parser"),
    ("camelot-stream", "PRIMARY table extractor (bordered + borderless, 13/15 golden)"),
    ("pdfplumber", "verifier/union partner; union = 15/15 golden with laid-out recall"),
    ("tabula-stream", "4th engine, revived via Temurin JRE 21; arbiter when engines disagree"),
    ("docling", "GATEKEEPER on golden + per-source samples (15/15 Star Asia, 1900s/doc CPU)"),
    ("pymupdf-layout", "DEMOTED 2026-09-21 to opt-in (--layout): of 100 text-dense pages the "
                       "union found zero tables on 0 of them, so the gate fired 0% and added "
                       "nothing while costing a subprocess and a segfault vector"),
    ("local VLM audit", "REJECTED: qwen2.5vl:3b hallucinated rows on a real table (58s/pg); "
                        "7B cannot fit 8.3GB RAM. Docling is the CPU-viable auditor."),
]

# Hardware envelope (verified 2026-09-21, constrains every tool choice)
HARDWARE = {"cpu_only": True, "gpu": None, "ram_total_gb": 8.3, "ram_free_gb": 2.4,
            "disk_free_gb": 34, "max_workers": 2,
            "implication": "no local VLM bulk/audit; classical stack + Docling sampling only; "
                           "concurrency capped at 2; output must stay Parquet/zstd"}

# Measured throughput, 35-doc stratified sample, default stack (no layout):
#   436s / 387 pages / 911 tables / 1.13s per page / 13.2s per doc
#   -> 7,816 unique docs = 28.7h single worker, 14.3h on 2 workers

# Bench record 2026-09-21, Star Asia W35 p2 (15 golden cells), SSY, Breakwave p2
BENCH = {"camelot-stream": "13/15, 4/4, 4/4", "pdfplumber": "13/15, 4/4, 1/4",
         "union": "15/15 golden", "layout+areas": "15/15 single-engine",
         "docling": "15/15 Star Asia (1901s), 3/4 Breakwave (238s)",
         "tabula-stream": "9/15", "pymupdf-tables": "0 (router only)",
         "img2table": "rejected: cv2 niBlackThreshold API incompat in this env",
         "marker/mineru": "rejected bulk: GPU-hungry on CPU-only box; mineru ~2min/pg CPU"}

# Layout-model crash evidence (2026-09-21): 41 docs probed in isolated
# subprocesses -> 40 ok, 1 CRASH (exit 0xC0000005 access violation) on
# docs/research/Subscription Plans - UN Comtrade Help Center.pdf.
# A 2.4% crash rate would abort a bulk run without subprocess isolation;
# the file is quarantined and isolation (LayoutWorker) stays in the code.
QUARANTINE_GLOBAL = ["lion_2024 misfile", "other/ triage bucket", "rapport-2 stub",
                     "baltic assets/", "breakwave corrupt HTML-as-PDF",
                     "poten unknown-01-01 stubs", "pre-2025 CFTC scans (image-only)",
                     "not-a-pdf headers (3 found: breakwave x2, signal fueleu)",
                     "docs/research/Subscription Plans - UN Comtrade Help Center.pdf (layout segfault)"]


def era_for(source, doc_date):
    cfg = SOURCES.get(source, {})
    d = doc_date if isinstance(doc_date, date) else date.fromisoformat(str(doc_date)[:10])
    for start, end, name in cfg.get("eras", []):
        if date.fromisoformat(start) <= d <= date.fromisoformat(end):
            return name
    return "unknown-era"
