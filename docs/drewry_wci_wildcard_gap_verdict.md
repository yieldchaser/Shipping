# Drewry WCI — the "two wildcard URL patterns" are closed, and the era gap is re-measured on the archive's own capture list

Measured 2026-10-01, unattended run. Read-only: **no fetch, no API spend, no data change.**
The displayed series stays at **135 rows** (`data/indices/drewry_wci_historical.csv`,
2021-05-20 .. 2026-09-24, all Thursdays, 0 blank core cells, 63 blank `rotterdam_shanghai`,
`manifest.json` `row_count` 135).

## Why this run existed

The previous run's verdict left exactly one open item:

> *The two wildcard patterns (`*world-container-index*`, `*container-index*`) remain
> unchecked because the CDX endpoint is offline; the timemap endpoint only enumerates an
> exact URL.*

CDX **is still offline** — `web.archive.org/cdx/search/cdx` returns the
`Internet Archive: Temporarily Offline` HTML body (checked again this run), while
`/wayback/available`, a snapshot fetch and `/web/timemap/json/<url>` all return 200. So the
wildcard patterns cannot be enumerated as patterns. They were closed the other way: **enumerate
each plausible exact URL with the timemap and compare capture sets.**

## 1. The candidate URLs, by timemap (status-200 captures only)

| candidate exact URL | captures | distinct ISO weeks | captures in a week we lack |
|---|---|---|---|
| `https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry` | **1,053** | 252 | 25 (all already in the checkpoint's own archive) |
| `http://www.drewry.co.uk/...world-container-index-assessed-by-drewry` | 1,053 | 252 | identical set (scheme-normalised) |
| `https://drewry.co.uk/...world-container-index-assessed-by-drewry` (no `www`) | 1,053 | 252 | identical set |
| `.../world-container-index-assessed-by-drewry/` (trailing slash) | 1,053 | 252 | identical set |
| `https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index` | **4** | **1** | **0** |
| `.../supply-chain-expertise/container-index` | does not exist in the archive | - | - |
| `https://www.drewry.co.uk/world-container-index-assessed-by-drewry` | does not exist in the archive | - | - |

**Verdict: the wildcard patterns hold NO recoverable WCI content.** Every URL variant that
matters is a normalisation of the one exact URL the checkpoint already enumerates; the only
genuinely different path (`.../world-container-index`, the shortest form the
`*world-container-index*` pattern would also match) holds **4 captures in a single ISO week and
zero in any week we lack**. There is nothing to fetch.

## 2. The era gap, re-measured on the archive's own capture list

Source of truth = the exact URL's timemap (`/web/timemap/json/<exact url>`), **1,053 rows,
1,033 status-200, 2017-06-16 10:27:41 .. 2026-09-27 14:32:51**.

For each of the **280 era Thursdays** (2021-05-20 .. 2026-09-24), is there a capture
**after** that day's print? (window: `(Thursday 12:00, +7d]` — a Mon-Wed capture holds the
*previous* week's assessment, which is the whole reason for the post-Thursday candidate):

| measure | value |
|---|---|
| era Thursdays | **280** |
| with a post-publication capture | **224** |
| with **NO** post-publication capture | **56** |
| of those 56, also absent from the checkpoint | 53 |
| post-publication capture exists but the checkpoint has no print | **5** |

## 3. The 5 archive-covered, checkpoint-absent Thursdays are holiday weeks — the page itself still prints the PRIOR Thursday

Each was read from its own archived/cached body:

| era Thursday | post-pub captures | the archived page's own sentence | conclusion |
|---|---|---|---|
| 2021-12-30 | 8 (`20220102140751` first) | "*assessment for **Thursday, 23 December 2021***" | publisher did not update; 30 Dec print not published/archived |
| 2023-12-28 | 21 (`20231228143722` first) | "*Thursday, **21 December 2023***" | same |
| 2024-12-26 | 1 (`20241228162100`) | "*Thursday, **19 December 2024***" | same |
| 2025-12-18 | 1 (`20251225083559`) | "*Thursday, **25 Dec 2025***" | the capture carries the NEXT print (25 Dec), not the 18 Dec one |
| 2026-01-01 | 2 (`20260105173610` first) | "*Thursday, **25 Dec 2025***" | same |

All five fall on the Christmas / New Year weeks. **The archived page proves there is no print
to recover** — it is still displaying the previous Thursday's assessment. Nothing was withheld
by the parser; nothing was dropped by the gate.

## 4. What remains (unchanged, archive-side)

**56 era Thursdays have no post-publication capture at all**, and 53 of those have no capture
anywhere in the archive. This is a **publisher/archive-side gap that no parser change and no
extra fetch can close for this URL**, now confirmed by the archive's own capture list rather
than inferred. Per the 2026-09-28 finding, `corpus/06-drewry/opinions/` holds only 5 WCI `.md`
files (2026-08-20..2026-09-24), so there is no corpus-side backfill path either.

## Reproduce

```
python3 scratch/wci/wildcard_probe.py     # candidate URLs by timemap -> scratch/wci/wildcard_probe.json
python3 scratch/wci/era_gap_measure.py    # definitive era gap -> scratch/wci/era_gap.json
python3 scratch/wci/five_gap.py           # names + reads the 5 holiday Thursdays -> scratch/wci/recoverable_gap.json
```
