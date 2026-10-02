# Stashed Redundant and Misleading Sources Ledger

**Stash Timestamp:** 2026-10-02 17:01:12
**Purpose:** Quarantine legacy, unpartitioned, truncated, or misleading source files and preview extractions so that no automated scanning tool, knowledge graph, or assistant mistakenly references them over the authoritative ground truth sources.

> **CRITICAL POLICY:**
> None of these files have been deleted. Everything is preserved here in this quarantine directory for complete auditability.

---

## 1. Hellenic Iron Ore HTML Web Previews
- **Stashed Count:** 6 items
- **Quarantine Path:** `data/stashed_redundant_sources/hellenic_iron_ore_html_previews/`
- **Why Stashed:** These were short (~20-40 line) HTML web article summaries scraped from the Hellenic news website. Because the folder was named `iron_ore`, agents and scripts routinely mistook them for the primary extracted data, ignoring the true multi-page reports.
- **Active Authoritative Path:** [`data/extracted/md/hellenic/iron_ore_pdf/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/iron_ore_pdf) (1,188 full-fidelity Markdown reports + `.tables.json` sidecars across 2021-2026, plus 21 stacked master series CSVs).

---

## 2. Poten Legacy Scraped Markdown
- **Stashed Count:** 2183 files
- **Quarantine Path:** `data/stashed_redundant_sources/poten_legacy_scraped_md/`
- **Why Stashed:** These were old markdown files dumped directly into `corpus/04-poten/` with truncated text (`... Read More" />`) and broken dates (`unknown-01-01`). Their presence in the corpus directory caused confusion with the real PDF corpus.
- **Active Authoritative Paths:**
  - **Corpus PDFs:** [`corpus/04-poten/pdfs/`](file:///c:/Users/Dell/Github/Shipping/corpus/04-poten/pdfs) (1,087 authoritative PDFs)
  - **Extracted Markdown:** [`data/extracted/md/poten/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md/poten) (1,087 full cover-to-cover Markdown reports)

---

## 3. Shipbroker Unpartitioned Root Duplicate Files
- **Stashed Counts:**
  - `banchero_costa`: 499 files
  - `carriers`: 272 files
  - `fearnleys`: 522 files
  - `ism`: 231 files
  - `ssy`: 1061 files
  - `xclusiv`: 809 files
  - `advanced_shipping`: 1 files
  - `affinity`: 4 files
  - `agora`: 1 files
  - `clarksons`: 1 files
  - `lion`: 1 files
  - `star_asia`: 1 files
- **Quarantine Path:** `data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/`
- **Why Stashed:** Early extractor runs placed markdown and sidecar files directly into `data/extracted/md/<broker>/`. Subsequent improvements partitioned the corpus into `<year>/` subdirectories (`2021/` to `2026/`). The loose files in the root folder were 100% duplicate copies of the year-partitioned files, creating clutter and risking stale file references.
- **Active Authoritative Paths:** [`data/extracted/md/<broker>/<year>/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md)
