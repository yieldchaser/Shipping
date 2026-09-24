# AFFINITY TANKER WEEKLY - verdict (source 6, COMPLETE)

250 PDFs (`corpus/01-brokers/affinity/`), years 2021:26 2022:47 2023:50 2024:50
2025:42 2026:35. Pipeline `scripts/extract/publishers/run_affinity.py`. Output
`data/extracted/md/affinity/` (`.md` + `.tables.json` + `.charts.json`).

## Result (measured)

| metric | value |
|---|---|
| run_state | done **250** / failed **0** |
| files | 250 `.md`, 250 `.tables.json`, 250 `.charts.json` |
| `.md` size | min 11,108 B / median 15,858 B / max 19,352 B - **0 files under 3 KB** |
| card rows typed | 5,327 |
| panel values seen on page 0 | 10,590 |
| panel values not accounted for | **0** (0 docs affected) |
| `.md` missing one of the 4 card headings or the route-table header | **0** |

## Independent verification (not the pipeline's own reconcile)

`scratch/affinity/verify_independent.py` re-reads all 250 PDFs with pymupdf,
takes every numeric token whose span starts at x >= 590 (the card panel), strips
separators, and tests membership in that document's `.md`:

* **250/250 docs checked, 0 unaccounted panel values.**
* panel rect measured as `[596.8, 94.6, 832.0, 561.4]` in **250/250** - the
  survey's claim that the panel is the only stable separator holds corpus-wide.

## Hand-read control (same document rendered and read)

`affinity_2021_Affinity-Tanker-Weekly-01.10.2021-HSN.pdf`, page 0, card panel
span dump vs the typed rows:

| page says | extracted |
|---|---|
| BDTI 626 / BCTI 496, `Δ W-O-W` both ↑Firmer | 626 / 496 / ↑Firmer / ↑Firmer |
| BDA `This week` 591.6 / 597.0 / 595.8 | 591.6 / 597.0 / 595.8 |
| BDA `Δ W-O-W` -1.3 / -2.0 / -2.2 | -1.3 / -2.0 / -2.2 |
| TD1 `ME Gulf / US Gulf` 280,000 **-15,692** ↑Firmer | TD1 / ME Gulf / US Gulf / 280,000 / -15,692 / ↑Firmer |
| TD3C 270,000 3,272, TD6 135,000 -6,023, TD8 80,000 -505, TD9 70,000 -3,155 | all match |
| TC6 `WS 130.63` ↑Firmer (one span, value + arrow fused) | 130.63 / ↑Firmer |

Numbers are ISO/US here (`280,000` = 280,000), NOT the European convention.

## The one real caveat, and it is the PUBLISHER's, not ours

The BALTIC TCE CLEAN card header says **`$ / WS`** in 68 documents (all 26 of
2021, 42 of 2022) and **`$ / Day`** in the other 182 (5 of 2022, all of
2023-2026). Inside those 68 WS-header documents the card is internally
inconsistent - it mixes explicit Worldscale cells with $/day-magnitude cells on
the same page:

```
2021-10-01  header: $ / WS
  TC1  75,000   8,565     <- magnitude is $/day, not WS
  TC6  30,000   WS 130.63 <- explicit WS, written with the unit
  TC9  30,000   WS 130.71
```

Measured across the corpus: **68 docs carry both shapes** (explicit-`WS` rows
AND >1000-magnitude header-labelled rows), 0 docs carry only one. The typed
layer copies the header, so those rows read `unit: "WS"` with a $/day
magnitude - which is exactly what the page prints. `unit_source` is recorded per
row (`header` 3,910 / `explicit-ws` 161 / none 6), so a consumer can tell an
explicitly-written `WS 130.63` from a header-inherited unit, and should treat
`unit: WS` + `|value| > 1000` in 2021-2022 as **$/day**.

Consequence: the CLEAN card in 2021-2022 must not be charted as a Worldscale
series without that rule. This is disclosed, not fixed - the page itself is the
ambiguity and there is nothing to correct on our side.

## Other findings

* **No charts.** 14-20 vector drawings per page 0 are all panel-wide rules plus
  two teal section underlines; images are the logo. `.charts.json` is emitted
  empty with that reason recorded. Verified by dumping every drawing's geometry.
* **84/250 docs carry a second page** that is the legal disclaimer only
  (3,110-3,143 chars, no numbers). Page count varies WITHIN a year, so it is not
  an era marker - routed by content, not by page count.
* **5 output files contain `nan` in the name**
  (`affinity_2026_nan_Affinity-Tanker-Weekly-*.md`). That mirrors the SOURCE
  filenames on disk (`corpus/01-brokers/affinity/2026/affinity_2026_nan_...pdf`,
  a scraper artefact), not a defect introduced here. Left as-is so the output
  stem matches its PDF 1:1.
* Layout traps that a fixed-geometry extractor would have hit (all measured, all
  handled): modal card font 9.0 / 9.7 / 8.6 / 8.3 / 8.0 across eras; 4/250 docs
  print card titles NOT bold; a header date wraps across spans
  (`18/09/202` + `6`); cells wrap vertically around their own data row; the 2021
  first header cell is literally `#####` (Excel column-too-narrow).

## Deliverable

`.md` is the primary artefact (two-column prose + the four cards as markdown
tables). `.tables.json` is best-effort typed and is labelled as such inside the
file (`typed_confidence`). Source 6 of the source-by-source programme: DONE.
