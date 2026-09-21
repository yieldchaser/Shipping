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

## Engine matrix — measured on 5 hand-verified golden pages

Ground truth established by direct visual reading of rendered pages, not by
trusting any extractor. Cell-level recall:

| Golden page (cells) | camelot-stream | camelot-lattice | pdfplumber | tabula-stream | plumber-TEXT | pymupdf-TEXT |
|---|---|---|---|---|---|---|
| Star Asia W35 (15) | 87% | 13% | 87% | 60% | **100%** | **100%** |
| SSY Atlantic (14) | 100% | 0% | 100% | 93% | **100%** | **100%** |
| Breakwave Dry (6) | 83% | 33% | 50% | 17% | **100%** | **100%** |
| Athenian demolition (24) | 0% | 0% | 17% | 0% | 17% | 17% |
| Seabrokers Aug (20) | 0% | 0% | 0% | 0% | **0%** | **0%** |
| *demolition circle+bar values (28)* | *15* | *0* | *28* | *0* | ***28*** | ***28*** |

### What the matrix changes

1. **The text layer is the primary RECALL source, not an afterthought.** Plain
   text extraction hit 100% on three of five pages and swept all 28 demolition
   circle/bar values, while the best table extractor reached 83-100% and only
   15/28 on the same page. Implemented: every table now carries a
   `text_verified` ratio and each page tracks `values_only_in_text` — the grid
   provides schema, the text provides recall, and the gap is now measurable
   per page instead of assumed.
2. **Seabrokers is IMAGE-ONLY for its rates table** — every engine, including
   text, scored 0/20. The committed markdown was produced by OCR ("Anydoc OCR"
   in its own header), which is why it looked parse-friendly. It belongs in the
   same OCR queue as the Alibra charter tables.
3. **camelot-lattice is the wrong flavor** (0-33%); stream is correct throughout.
4. **Tabula is a legitimate third engine** (93% SSY, 60% Star Asia) but needs a
   JRE on PATH or it silently returns nothing — measured: 0% without Java, 93%
   with. CI must install a JRE.
5. **60% of table cells on hard pages are recoverable from text but dropped by
   the grid** — the reconciliation this now records is the single largest
   remaining accuracy lever.

## The stack (updated)

| # | Tool | Role | Evidence |
|---|---|---|---|
| 1 | PyMuPDF | Route pages; paragraph-aware text blocks | 0.02 s/page; **text = 100% cell recall on 3/5 golden pages** |
| 2 | Camelot-stream | Table SCHEMA extractor | 87-100% cell recall on text-layer tables |
| 3 | pdfplumber | Union partner; table + page text | 100% SSY, union raises Star Asia to 15/15 |
| 4 | Tabula-stream | Third engine / arbiter | 93% SSY, 60% Star Asia — **requires JRE on PATH** |
| 5 | Reconciliation | `text_verified` per table + `values_only_in_text` per page | **implemented 2026-09-21** — largest remaining accuracy lever |
| 6 | Docling | Gatekeeper: golden + per-source samples | 15/15 Star Asia but 1,900 s/doc → sampling only |
| 7 | Chart harvest | Every image + bbox + heading + dhash series ID | dhash recurrence proven |
| — | ~~camelot-lattice~~ | Wrong flavor | 0-33% cell recall vs stream's 87-100% |
| — | ~~pymupdf-layout~~ | Demoted to opt-in (`--layout`) | fired 0% on 100 probed pages; 2.4% segfault rate |
| — | ~~local VLM~~ | Rejected | 3B hallucinated rows; 7B won't fit 8.3 GB RAM |

**Known image-only tables** (OCR/VLM queue, deferred): Seabrokers OSV rates
(0% from all six engines), Alibra dry/tanker charter tables.

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
