# Extraction Strategy — Final (2026-09-21)

Canonical reference for the bulk-corpus extraction pass. Supersedes all earlier
strategy notes: the layout step is demoted, concurrency is capped at 2, and the
runtime estimate is measured, not guessed.

## Corpus (inventoried from disk, md5-deduped)

| Metric | Count |
|---|---|
| PDF files on disk | 9,912 (6.84 GB) |
| **Unique PDFs to process** | **7,816** (2,096 content-duplicates skipped) |
| Article HTML | 9,968 |
| Markdown (mirrors, stubs, knowledge trees) | ~14,500 |
| Images (charts/figures) | ~23,000 |
| Sources with configs | 33 |

## Per-source handling

| Source | PDFs | HTML | MD | Images | Eras / handling |
|---|---|---|---|---|---|
| Shipbrokers (18 houses) | 3,456 | — | 143 | — | T1 tables. Era pins: xclusiv split 2024, affinity split 2026, allied Report→Review 2022/23, intermodal redesign 2024, star_asia rebrand 2026 |
| Hellenic iron ore | 2,240 | — | — | 6,585 jpg | **Dual parser split at 2026-09-12** (6pp MMi → 1pp SMM) |
| Hellenic demolition | 1,050 | — | — | 326 png | Per-source beach-price tables (GMS / Best Oasis / Athenian) |
| Hellenic shipbuilding | 675 | 3,201 | — | — | 2 feeds: Breakwave PDFs + Clarksons HTML |
| Hellenic charters (dry/tanker) | — | — | — | jpg | Alibra tables are **IMAGE-ONLY** → OCR deferred, harvest now |
| Poten | 1,087 | — | 1,096 stubs | — | Era split 2014/2015: multipage essays (LLM) vs 1pp teasers (parse) |
| Drewry AIS | 276 | — | 548 opinions | — | Fixed 9pp Power BI template; p2 bullets + chart images |
| Drewry WCI | — | — | — | — | CSV direct, forward-fill ragged tail |
| Breakwave reports | 81 | 3,219 | — | 10,064 png + 4,967 jpg | 2pp template, p2 fundamentals regex; **HTML needs junk filter** (Yahoo/CNN dumps, Blogspot) |
| Dry bulk / Tankers | 210 / 79 | — | — | — | Strict bi-weekly, fixed 2pp since 2018 |
| Seabrokers | 97 | — | 97+97 | — | Most parse-friendly: fixed md table + OCR body |
| PPA (scratch) | 495 | — | — | — | Monthly stats; CSVs already extracted, PDFs verify-only |
| CFTC | 140 | — | — | — | Ledgers done; monthly workflow live |
| Baltic | — | 3,038 | — | — | Prose regex; **skip 820 bot-wall `assets/`** |
| Signal | 8 | 510 | 448 + 10 news | 1,069 png + 308 avif | Monitor era split 2026; newsroom ad-hoc; newsletters monthly |
| Fearnleys | — | — | 176 | charts | Text layer complete; only chart digitization remains |
| Textbooks | 12 | — | — | — | RAG baseline, no table work |
| Knowledge mirror | — | — | 11,963 | 10,388 json | Index, not source |

## The stack (updated)

| # | Tool | Role | Evidence |
|---|---|---|---|
| 1 | PyMuPDF | Route pages + paragraph-aware text blocks | 0.02 s/page |
| 2 | Camelot-stream | **PRIMARY** table extractor | 13/15 golden, 4/4 SSY, 4/4 Breakwave |
| 3 | pdfplumber | Union partner / verifier | union with #2 = **15/15 golden** |
| 4 | Tabula-stream | Arbiter when #2/#3 disagree | 9/15; Temurin JRE 21 installed |
| 5 | Docling | Gatekeeper: golden + per-source samples | 15/15 Star Asia but 1,900 s/doc → sampling only |
| 6 | Chart harvest | Every image + bbox + heading + dhash series ID | dhash recurrence proven |
| — | ~~pymupdf-layout~~ | **DEMOTED to opt-in (`--layout`)** | fired 0% on 100 probed pages; 2.4% segfault rate |
| — | ~~local VLM~~ | **REJECTED** | 3B hallucinated rows; 7B won't fit 8.3 GB RAM |

Hardware envelope: CPU-only, 8.3 GB RAM, 34 GB disk free → **max 2 workers**.

## Run plan

1. **Dry batch** — 300 docs across all sources; shake out era-mismatch bugs.
2. **Golden gate** — 15/15 must hold or the run is blocked.
3. **Full pass** — 7,816 docs, resumable, streaming output.
4. **Non-PDF pass** — HTML mirrors (strip-tags + regex), Baltic, Signal.
5. **Audit pass** — Docling cross-check on samples + review queue; publish drift report.

Measured throughput (35-doc stratified sample, default stack):
**1.13 s/page, 13.2 s/doc → ~14.3 h on 2 workers.**

## Output

Parquet tables (zstd) + JSONL text blocks + chart store + `manifest.jsonl` with
(source, doc, date, route, pages, tables, bbox provenance). All gitignored;
idempotent and resumable via content hash.

## Quarantine (9 categories)

lion_2024 misfile · `other/` triage bucket · rapport-2 stub · baltic `assets/` ·
breakwave corrupt HTML-as-PDF · poten unknown-01-01 stubs · pre-2025 CFTC scans ·
not-a-pdf headers (3) · `docs/research/Subscription Plans...pdf` (layout segfault)

## Deferred, with reasons

VLM value extraction (RAM) · chart digitization · Docling as bulk extractor
(CPU-prohibitive) · Alibra charter-table OCR (image-only source).
