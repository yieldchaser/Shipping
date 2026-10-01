# Independent verification of `corpus/CORPUS_REGISTRY_AND_CADENCE_AUDIT.md` (published 2026-10-01 14:46)

Measured 2026-10-01 ~15:1x, unattended. Read-only: no file was moved, edited or fetched.
Method: enumerate the filesystem; never re-read the doc's own numbers. Reproduce with
`python3 scratch/audit_registry_counts.py` and the one-liners recorded below.

## 1. Coverage claim — VERIFIED, no unbuilt source

Every publisher with a corpus has Markdown output on disk. Measured md counts under
`data/extracted/md/`: advanced_shipping 253 · affinity 255 · agora 216 · baltic 2,218 ·
banchero_costa 252 · breakwave 3,485 · carriers 137 · clarksons 180 · drewry 846 ·
fearnleys 524 · fearnleys_cleaned 257 · fearnleys-md 181 · hellenic 5,755 · intermodal 256 ·
ism 230 · lion 47 · lion_shipbrokers 2 · poten 1,087 · seabrokers 97 · signal 442 ·
ssy 532 · star_asia 200 · xclusiv 271. **No corpus group has zero md output.**
(PDFs per corpus group, same run: 01-brokers 2,970 · 02-hellenic 8,004 · 03-breakwave 304 ·
04-poten 1,087 · 05-seabrokers 97 · 06-drewry 288 · 07-signal 10 · 09-ppa 493 · archive 724 ·
books 12.)

## 2. Headline format inventory — DOES NOT REPRODUCE

| the doc says | measured (plain census of `corpus/`) | delta |
|---|---|---|
| **6,639 PDFs** | **13,989** | doc is **2.1x LOW** |
| 9,678 HTML files | 10,005 `.html` + 2 `.htm` = **10,007** | +329 (close) |
| 26,451 JPG/PNG images | 14,457 png + 11,354 jpg + 463 jpeg = **26,274** | -177 (close) |
| 18,290 Markdown files | **9,599** md inside `corpus/`; **17,723** md under `data/extracted/md`; **23,006** md anywhere under `data/` | matches neither |
| "Over 54,000 documents" | **60,351** files in `corpus/` | doc is 11% low |

The image and HTML figures are close enough to be the same measurement with a slightly
different directory set. The **PDF figure is not**: 13,989 PDFs exist in `corpus/`, and no
sub-population of the obvious kind (excluding `02-hellenic` = 5,985; excluding `02-hellenic`
+ `archive` = 5,261) lands on 6,639. **I did not test a content-dedupe hypothesis** (that
would need 14k SHA-256s), so this is reported as *not reproducible*, not as *wrong by X*.
Anyone quoting "6,639 PDFs" should re-derive it first.

## 3. The Clarksons row names a directory that does not hold its own inventory

The row in the doc reads `**Clarksons / Clarksons Hellas** … 180 PDF … corpus/01-brokers/clarksons`.
Measured:

* `corpus/01-brokers/clarksons/` holds **9 PDFs**, all in `2026/`, spanning
  `7th-August-2026` .. `25th-Sept-2026`.
* **180** is the md count in `data/extracted/md/clarksons/` — not a PDF count.
* The publishing history is filed elsewhere: **345 clarkson-named PDFs corpus-wide**, of
  which **168 sit under `corpus/02-hellenic/shipbuilding/pdfs/`** (2021/2022/2023/2025/2026
  sub-dirs).

So the doc's Clarksons corpus directory and its PDF count describe two different populations.
The **latest-issue date `2026-09-25` is CORRECT** — `clarksons_2026_Weekly-Sales-25th-Sept-2026.pdf`
exists on disk. Everything else in the row (cadence, md path, "CURRENT") is consistent.

## 4. Per-publisher latest-issue dates — spot-checked, correct where checked

Derived from **filenames** (not mtime, per the ledger's rule). Two verified by locating the
named file: **fearnleys 2026-10-01** (`fearnleys_01_10_2026_…week_40_2026.pdf` on disk) and
**clarksons 2026-09-25** (above). Both match the doc.

A filename-only sweep also flags apparent gaps (clarksons 2026-09-18, lion 2026-09-21,
star_asia 2026-09-28 vs the doc's 09-25, fearnleys-md 2026-09-24 vs 09-30) — but **the
sweep's parser is the suspect**: it cannot read ordinal-month names (`25th-Sept-2026`), so
it under-reports the latest date for exactly those rows and I am **not** reporting them as
defects. Re-derive per source from the publisher's own cover line before believing any of them.

## 5. What this does and does not establish

* Established: coverage is complete; the doc's PDF headline count does not reproduce; the
  Clarksons row points at a 9-PDF directory while quoting a 180-file count.
* Not established: which population produced 6,639 / 18,290, and therefore whether those
  numbers are "wrong" or "measured on a different (e.g. deduplicated) set". No content
  hashing was performed.

## 6. Hunt for the population behind 6,639 / 18,290 (all measured, none matches)

| candidate population | measured |
|---|---|
| PDFs in `corpus/` | 13,989 |
| PDFs in `corpus/` excluding `02-hellenic` | 5,985 |
| PDFs **tracked by git** in `corpus/` (bulk PDFs are git-untracked) | **4,399** |
| PDFs in `data/` | 301 |
| distinct PDF **basenames** in `corpus/` | 10,021 |
| md in `corpus/` | 9,599 |
| md under `data/extracted/md` (all tracked) | 17,723 |
| md anywhere under `data/` | 23,006 |

**None equals 6,639 or 18,290.** The two figures are therefore not reproducible from the
filesystem by any of the obvious counts, and the audit's own method is not stated in the doc.
