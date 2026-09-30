# Collection vs extraction freshness - every source, measured (2026-09-30)

**Why this exists.** All 23 publishers are marked CLOSED/current in
`docs/EXTRACTION_REGISTER.md`, and that register is the file a future run reads first. A
register records INTENT. This audit measures the collected corpus, the way
`docs/EXTRACTION_REGISTER.md` cannot: dates taken from **FILENAMES**, per source, across
**all** formats, with the population stated before any conclusion.

## Method

* **Dates come from filenames**, never mtime. Measured on this box: `corpus/04-poten/2004/*.md`
  carries an mtime of 2026-09 while its content is from 2004 (a bulk copy stamped it). mtime is
  actively misleading here.
* Per source: every `*.pdf/*.md/*.html` under the source root, the maximum filename-derived
  date, and the median gap between its last 14 distinct issue dates.
* **"Overdue" is a DERIVED signal, not a verdict.** `DUE` only means `today > last + 1.6 x gap`;
  it must be confirmed against the publisher's own site before it is called a gap. Three of the
  four `DUE` rows below were false alarms, and one of them was a bug in this very script.
* Source: `scratch/cadence_audit3.py` (read-only). Publisher-side checks:
  `scratch/hsn_coverage.py`, `scratch/live2.py`, `scratch/live3.py`, `scratch/source_live_check.py`.

## The table (2026-09-30, cadence from each source's own dates)

| source | files | newest issue | median gap | verdict | confirmation |
|---|---|---|---|---|---|
| advanced_shipping | 253 | 2026-09-26 | 7 d | current | W39 digest present |
| affinity | 254 | 2026-09-26 | 7 d | current | — |
| agora | 215 | 2026-09-18 | 7 d | **DUE by 5 d - PUBLISHER-SIDE** | HSN's newest agora is week 38; `...week-39-2026` and `...week-40-2026` both **404**; site search returns week 38 only |
| banchero_costa | 246 | 2026-09-14 (PDF tier) | 7 d | current | W39 collected 2026-09-30 as a digest (`_digests/bancosta/...week_39_2026.md`) |
| carriers | 135 | 2026-09-21 | 7 d | current | W39 digest present |
| clarksons | 13 | 2026-09-25 | 7 d | current | **was a false alarm** - see below |
| fearnleys | 261 | 2026-09-24 | 7 d | current | W39 digest |
| intermodal | 256 | 2026-09-30 | 7 d | current | W39 digest |
| ism | 115 | 2026-09-28 | 7 d | current | W39 digest |
| lion | 46 | 2026-09-25 | 7 d | current | W39 digest |
| ssy | 530 | 2026-09-28 | 7 d | current | 2 indexes/week |
| star_asia | 199 | 2026-09-28 | 7 d | current | W39 digest |
| xclusiv | 271 | 2026-09-29 | 7 d | current | W40 issue |
| hellenic | 18,183 | 2026-09-29 | 1 d | current | another live session owns it |
| breakwave | 21,806 | 2026-09-29 | 1 d | current | — |
| seabrokers | 194 | 2026-08-01 | 31 d | DUE by 29 d - **publisher-side** | seabrokers.no's own market-analysis page lists nothing newer than `markedsrapport-juli-2026` |
| poten | 3,270 | 2026-09-18 | 7 d | **DUE - REAL GAP** | publisher's feed lists 2026-09-26; see `docs/poten_collection_outage_verdict.md` |
| drewry | 1,366 | 2026-09-25 | 2 d | current | insights publish ~2 days apart |
| corpus/archive: allied | 203 | 2024-02-12 | 7 d | **dead, 961 d** | BACKFILL_ONLY confirmed |
| corpus/archive: golden_destiny | 252 | 2024-11-25 | 7 d | **dead, 674 d** | BACKFILL_ONLY confirmed |
| corpus/archive: gibson | 109 | 2023-09-29 | 7 d | **dead, 1,097 d** | 146 later items are web articles, not editions |
| corpus/archive: other | 130 | 2023-10-09 | 7 d | **dead, 1,087 d** | BACKFILL_ONLY confirmed |
| corpus/archive: anchor | 30 | 2022-12-26 | 7 d | **dead, 1,374 d** | BACKFILL_ONLY confirmed |

**Extraction lag: 0 days on 16 of 17 broker sources** - the newest `.md`/sidecar in
`data/extracted/md/<source>` carries the same issue date as the newest collected PDF. The two
exceptions are explained: `banchero_costa` (md tier newer, because W39 arrived as a digest
today) and `hellenic` (4 days; owned by another session, not touched).

## The clarksons false alarm - the lesson of this audit

`clarksons_2026_Weekly-Sales-25th-Sept-2026.pdf` sits in `corpus/01-brokers/clarksons/2026/`,
but the first two versions of this script read the source as 12 days stale. Cause: the filename
parser required `25-Sept-2026`, and the file says **`25th-Sept-2026`** - the ordinal suffix was
not stripped, so the date fell through to a year-only match. Fixed
(`re.sub(r"(?<=\d)(st|nd|rd|th)(?=[-_ .])", "", s)`), after which clarksons reads 2026-09-25 and
`current`. **This is the fourth detector in this project that was confidently wrong**; the
`DUE` verdict is only ever a pointer to look at the source, never a finding.

## The stale pointer this audit retires: the ism "median-preferring pick"

`docs/OVERNIGHT_STATE.md` (2026-09-30 11:4x) ended with: *"trial a median-preferring pick,
re-measure the gate before/after"*, because the pooled value sits at the cluster edge on 71% of
rows. Measured today (`scratch/ism_edge_baseline.py`, `scratch/ism_edge_attrib.py`):

| file | rows (n>=2, spread>2%) | at edge | arithmetic baseline `E[2/n]` | excess |
|---|---|---|---|---|
| ism_handy | 1,601 | 71.3% | **44.7%** | +26.6 pp |
| ism_coaster | 970 | 65.6% | **52.4%** | +13.2 pp |

So the edge-dwelling is real (a random pick among the readings would sit at the edge far less
often), and it is NOT a defect in choosing among restatements: split by the age of the report
the value came from, **100% of "own week" rows are at the edge by construction**, and the
largest bucket is "report published >28 days after the observation week" (79% edge) - i.e. the
effect is the documented first-print/nearest-issue policy (`pick_observation`), plus the fact
that with n=2 every value is trivially an edge.

Changing it would not repair anything: every one of the 29,948 values is **verbatim from the
named issue** (`docs/ism_series_value_provenance_verdict.md`, 29,948/29,948), and the
restatement band is published in `min_value` / `max_value` / `value_sd` / `n_reports`. A
median-preferring pick is a **pooling policy choice with the cross-report agreement gate as its
objective** - measuring that gate before/after such a change is circular. Recorded here so no
future run "fixes" it silently. If a canonical value is wanted downstream, filter on
`value_sd` and record the dissenting reports; do not re-pick the stored value.

## Reproduce

```bash
python3 scratch/cadence_audit3.py        # the table above
python3 scratch/hsn_coverage.py          # what the HSN collection checkpoint actually saw
python3 scratch/live3.py                 # publisher-side: poten feed, seabrokers report slugs
python3 scratch/ism_edge_baseline.py     # the edge-vs-baseline measurement
python3 scratch/ism_edge_attrib.py       # the split by report age
```
