# Data Layer Reorganisation — Design & Execution Plan

**Goal:** one canonical, taxonomy-arranged, to-be-processed corpus containing EVERY
raw source artifact (PDF, HTML, image, markdown, JSON) — arranged so the next
processing pass can walk it source-by-source. Zero deletions. Zero broken scripts.

Status: DESIGN — awaiting go/no-go before any file moves.

---

## 1. Governing constraints (from the owner)

1. **No deletion of any source**, whether live or stopped. Stopped publishers are
   still valuable for historical knowledge extraction.
2. **Do not break any script.** Scripts that write new reports as they arrive must
   keep working; update them to the new paths where needed.
3. **Everything raw must be present** — all PDFs, all HTML, literally everything
   that will be processed.
4. **Archive section** for publishers that stopped, since they are not useful on an
   ongoing basis but are useful historically.
5. **A `books/` folder** for the foundational textbooks.
6. Design (sort by source / year / cadence / combination) is my call.
7. Liveness gates usefulness: a stopped publisher cannot extend a series forward,
   so it does not belong in the live processing path.

---

## 2. Current state (verified, not assumed)

| # | source | current location(s) | scale | cadence | state |
|---|---|---|---|---|---|
| 1 | Shipbroker weeklies (18 firms) | `reports/shipbrokers/<broker>/<year>/` | ~3,600 PDFs | weekly | live |
| 2 | Broker digests (.md) | `reports/broker_reports/<year>/<broker>/` | 138 md | weekly | live |
| 3 | Hellenic iron ore (MMi) | `reports/hellenic/iron_ore/` | 2,240 PDFs | **daily** | live |
| 4 | Hellenic demolition | `reports/hellenic/demolition/` | 1,050 PDFs | ~daily | live |
| 5 | Hellenic shipbuilding | `reports/hellenic/shipbuilding/` | 675 PDFs | ~weekly | live |
| 6 | Hellenic dry/tanker charter, vessel valuations | `reports/hellenic/*/` | ~530 PDFs | weekly | live |
| 7 | Hellenic companion assets | `reports/hellenic/*/assets/` | 6,585 jpg + 3,201 html + 326 png | — | live |
| 8 | Breakwave insights | `reports/breakwave/<year>/` | 3,190 html + 15,150 charts | near-daily | live |
| 9 | Breakwave dry bulk | `reports/drybulk/<year>/` | 210 PDFs (2018–2026) | weekly | live, newest 2026-09-15 |
| 10 | Breakwave tankers | `reports/tankers/<year>/` | 79 PDFs (2023–2026) | weekly | live, newest 2026-09-08 |
| 11 | Poten tanker opinions | `reports/poten/` | 1,085 PDFs + 1,094 md | weekly | live |
| 12 | Seabrokers offshore | `reports/seabrokers/` **and** `data/reports/seabrokers/` | 97 PDFs + 97 md | monthly | live (duplicated) |
| 13 | Drewry AIS | `scripts/drewry_ais_pdfs/` | 276 PDFs | weekly | live — **misplaced in scripts/** |
| 14 | Drewry opinions | `reports/drewry/` | 547 md | weekly | live |
| 15 | Signal Group | `reports/signal/` | 2,369 files | weekly | live |
| 16 | Baltic Exchange | `reports/baltic/` | 3,038 html | weekly | live |
| 17 | PPA port throughput | `scratch/ppa_pdf/` + `scratch/` | 492 PDFs | monthly | live — **in scratch/** |
| 18 | CFTC statements | `data/cftc_statements/raw_pdf/` | 138 PDFs | monthly | provenance-only |
| 19 | Fearnleys circulars | `reports/fearnleys/<year>/` | 176 md | weekly | live |
| 20 | Textbooks | `reports/*.pdf` | 12 books (118 MB) | — | reference |

**Stopped publishers (from the liveness sweep, >180d):**
`golden_destiny` 2024-11-25 · `allied` 2024-02-12 · `gibson` 2023-09-29 ·
`anchor` 2022-12-26 · `other` 2024-05-06 · `signal/pdfs` 2025-01-01 · `breakwave/pdfs` 2026-07-26

---

## 3. Proposed taxonomy

Sort key: **source → stream → year**, with cadence recorded in the manifest rather
than in the path (cadence changes over time and would otherwise force renames).

```
corpus/                                   # the to-be-processed layer
├── _MANIFEST.json                        # every source: cadence, liveness, paths, wiring, first/last date
├── _MANIFEST.csv                         # same, flat, for grepping
├── 01-brokers/                           # LIVE shipbroker weeklies
│   ├── ssy/<year>/  xclusiv/<year>/  fearnleys/<year>/  intermodal/<year>/
│   ├── affinity/<year>/  advanced-shipping/<year>/  banchero-costa/<year>/
│   ├── agora/<year>/  star-asia/<year>/  carriers/<year>/  ism/<year>/
│   ├── lion/<year>/  clarksons/<year>/
│   └── _digests/<year>/<broker>/         # the 138 normalised .md circulars
├── 02-hellenic/
│   ├── iron-ore/<year>/        (+ assets/)
│   ├── demolition/<year>/
│   ├── shipbuilding/<year>/
│   ├── dry-charter/<year>/   tanker-charter/<year>/   vessel-valuations/<year>/
│   └── _other/
├── 03-breakwave/
│   ├── insights/<year>/        # near-daily html + charts
│   ├── dry-bulk/<year>/        # weekly PDF
│   └── tankers/<year>/         # weekly PDF
├── 04-poten/<year>/            # pdf + md pairs kept together
├── 05-seabrokers/<year>/       # monthly; de-duplicated from the two current copies
├── 06-drewry/
│   ├── ais/<year>/             # moved OUT of scripts/
│   └── opinions/<year>/
├── 07-signal/{monitors,newsroom,images,html,pdfs}/
├── 08-baltic/<year>/
├── 09-ppa/<year>/              # moved OUT of scratch/
├── 10-cftc/<year>/             # provenance-only
├── archive/                    # STOPPED publishers - historical extraction only
│   ├── golden-destiny/<year>/  ├── allied/<year>/  ├── gibson/<year>/
│   ├── anchor/<year>/          └── other/<year>/
└── books/                      # 12 foundational textbooks
```

Rationale for the choices:
- **Numbered top-level groups** so the processing walk order is explicit and stable.
- **Year as the leaf** — every source is a time series, and year-partitioning is what
  already works in this repo (`reports/fearnleys/<year>/`, `reports/seabrokers/<year>/`).
- **Cadence in the manifest, not the path** — `golden_destiny` was weekly then died;
  encoding "weekly" in a folder name would be a lie after it stops.
- **Archive is a sibling of the live groups, not a subfolder of them** — so a
  processing walk of `01-`..`10-` never touches stopped publishers unless asked.
- **`books/` flat** — 12 files, no time dimension.

---

## 4. Execution sequence (reversible at every step)

1. **Freeze + branch.** Work on a dedicated branch; do not touch `main`.
2. **`git mv` only** (never `rm`), so history and content are preserved and the whole
   change is one revertable commit.
3. **Order:** books → archive split → misplaced sources (Drewry out of `scripts/`,
   PPA out of `scratch/`) → source groups → digests.
4. **Update all 51 referencing scripts in the same change** — path constants only, no
   logic changes.
5. **Update the 23 workflows** that read these paths.
6. **Verify per source:** import-check each script, then run its dry-run/idempotent
   path, then confirm the newest file is still discovered.
7. **Dry-run ingestion of one fresh report per live source** and confirm it lands in
   the new location.
8. **Post-move integrity:** re-count every source against the pre-move inventory
   documented in section 2 — totals must match exactly, with the only permitted
   differences being de-duplication of the seabrokers copies.

---

## 5. Risks and mitigations

| risk | mitigation |
|---|---|
| A path reference is missed → source silently stops ingesting | exhaustive grep for every path form (quoted, f-string, glob, config, YAML, manifest JSON) before moving; re-grep after |
| Workflows write to old paths in CI (not visible locally) | update workflows in the same change; list every workflow touched |
| Duplicate seabrokers copies get counted twice | verify the two trees differ only by the PDFs, then keep one and record the decision |
| `scratch/` content is conventionally disposable → PPA could be cleaned by someone | move PPA out of `scratch/` first, as its own commit |
| Large git churn stalls the push (repo already needs retries) | commit in per-source increments, push each separately |
| Silent data loss during a move | never delete; compare counts before/after; keep the pre-move inventory in this file |

---

## 6. Open decision

The plan above **moves** files (one revertable commit per source). The alternative is
to leave every file in place and add a canonical manifest + index that points at
them — zero breakage risk, but it does not give a physically arranged tree.

Recommendation: **move**, in per-source increments, because the owner asked for a
physically arranged, ready-to-process tree and explicitly accepted updating scripts.
