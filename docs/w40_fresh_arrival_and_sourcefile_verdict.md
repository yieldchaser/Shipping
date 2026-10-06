# Fresh W40 arrivals: content verification + md `source_file` audit (2026-10-06 18:xx)

Run: scheduled source-by-source job. Rule obeyed: SOURCE BY SOURCE, no generic runner.
Nothing was left to EXTRACT (re-verified, not a re-statement); this run spent its time on
CONTENT verification of the newest arrivals and an audit of md provenance pointers.

## 1. Nothing to extract (independently re-verified vs DISK)
- Working tree CLEAN at run start (0 files); no extraction/ingest process of ours.
- Register gate GREEN: `python3 scripts/extract/verify_registers.py` = ALL CHECKS PASSED
  (disk 175 CSVs / **630,357** logical rows == JSON == MD; 0 mismatches; 0 control chars/emoji).
- Newest PDF arrivals in `01-brokers` (2026-10-04..06: advanced_shipping W40, affinity W40,
  agora W40, lion W40, clarksons 2-Oct, star_asia W40, banchero_costa W39) ALL already have
  md at the canonical stem. Nothing new to run.

## 2. CONTENT verification of the fresh W40 arrivals (the primary check this run)
Method (no vision tool in cron - say so): reconcile EVERY value-shaped token in each md BODY
against the document's OWN PDF text layer (`pymupdf page.get_text()`). Canonicalise to digits,
normalising a trailing `.0` (md stores floats: `3148.0` where the PDF prints `3,148`).

| source | md numeric values | present verbatim | recall | pdf text chars |
|---|---|---|---|---|
| star_asia W40 | 418 | 418 | **100.0%** | 31,134 |
| advanced_shipping W40 | 385 | 385 | **100.0%** | 19,132 |
| affinity W40 | 72 | 72 | **100.0%** | 11,745 |
| lion W40 | 278 | 277 | 99.6% | 9,956 |
| agora W40 | 184 | 183 | 99.5% | 9,302 |
| banchero_costa W39 | 1,258 | 1,190 | 94.6% | 56,616 |

- advanced_shipping read 89.0% on the FIRST pass; the whole gap was the float-format artifact
  above (all 44 "misses" were `NNNN.0` for a printed `N,NNN`) - a metric artifact, not a defect.
  Normalised, it is 100.0%. (Skill: a broken metric reads exactly like a broken tool.)
- lion's 1 miss = `9,855` (a value carried in a chart, not the text layer). NOT a fabrication.
- agora's 1 miss = `697.263.4347` (a concatenated contact/phone-shaped token, not a market value).
- banchero_costa's 5.4% miss = its KNOWN glyph-ciphered text layer, consistent with prior runs.

Verdict: the fresh W40/W39 arrivals are FAITHFUL to their source pages. No re-run needed.

## 3. md `source_file` audit - found and FIXED 12 broken pointers (kind-2 exact-path field)
The skill's migration rule: `.md` frontmatter `source_file` is an EXPLICIT PATH FIELD (kind 2) -
"an index pointing at a moved path silently 404s" - fix = repoint. Swept every md tier
(28,484 md across `data/extracted/md/**`):

- **clarksons - 11 md** recorded `corpus/02-hellenic/shipbuilding/pdfs/<name>.pdf` for PDFs that
  actually live in `corpus/01-brokers/clarksons/2026/`. Cause: an EARLIER `run_clarksons.py`
  hardcoded that hellenic prefix; the runner ALREADY ingests BOTH dirs (lines 586/592) and now
  computes the true repo-relative path, so these 11 were pre-fix artifacts never regenerated.
  1 more (`2023-07-24_...cebb0332bb75.md`) held a bare filename. **Repointed all 11.**
- **carriers - 1 md** (`carriers_2026_W28_CARRIERS_WEEK_28`) held a bare filename where 135/137
  carriers md use the full path. **Repointed** the md AND its `.tables.json`.
- Re-verified: clarksons **184/188 resolve, 0 stale**; carriers 0 stale.

## 4. MEASURED, deliberately NOT fixed
- **hellenic - 448 md carry a BARE filename** `source_file` (by the builder's convention:
  `scripts/extract/publishers/run_athenian_demolition.py:366` writes the bare basename).
  427 of the 448 basenames are AMBIGUOUS (multiple files share that name under `corpus/`; the
  corpus has 64,729 files / 58,825 unique names), 21 unique. `scripts/audit/validate_extracted_md_quality.py`
  only checks PRESENCE, so these PASS the validator. Not safely machine-repointable (which copy?)
  and a hand-edit would revert on the next builder run. **Recommended durable fix (user's call):
  write the repo-relative path in the builder, then regenerate.**
- **`_nan_` acquisition naming artifact - NOT a gap.** 17 corpus PDFs carry a literal `nan` in the
  filename (a prior downloader's failed date-parse). The 5 `affinity_2026_nan_*` are BYTE-IDENTICAL
  (md5) to their non-`nan` counterparts, whose md already exists under the good stem; the ssy (8)
  and xclusiv (4) `_nan_` PDFs each have their own md. Content is fully held.
- **4 orphan md** `data/extracted/md/clarksons/2026/clarksons_2026_nan_Weekly-Sales-*.md` have NO
  frontmatter and are superseded partial duplicates (53-65% line overlap with the good md, their
  `_nan_` source PDF no longer present). Left in place (deleting derived artifacts is the user's call).

## Measured totals
- md swept: 28,484 across 25 tiers.
- stale `source_file` before this run: 460 (clarksons 11, carriers 1, hellenic 448).
- FIXED this run: 12. Remaining 448 = the hellenic bare-name convention (documented, ambiguous).
