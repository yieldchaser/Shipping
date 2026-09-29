# Drewry WCI: 138 of 145 displayed rows were FABRICATED - purged

**Date:** 2026-09-29 (cron, unattended) · Branch `benchmark/extraction-comparison`
**Artefact:** `data/indices/drewry_wci_historical.csv` - the file `index.html` fetches
(`fetch('data/indices/drewry_wci_historical.csv')`), i.e. a series the user SEES.

## How it started

The WCI file's route columns were fused on the 7 newest rows (reported in
`docs/drewry_wci_display_verdict.md`, fixed). While repairing from the publisher's own markdown,
the rest of the file was measured - and the equality signature `open/high/low == close` in the
neighbouring Capital Link files prompted a look at the WCI file's own provenance. The
`generate_canonical_wci_history()` stub in `scripts/scrapers/fetch_drewry_wci.py` carries the
comment *"Build F: synthetic baseline removed... it NEVER synthesizes values"*. It does not
anymore - but the rows it had already written were still in the file. This is that finding.

## The fabrication

Commit `22c0a870a` *added* a synthesizer and wired it into the failure path:

```python
def generate_canonical_wci_history():
    dates = pd.date_range(start="2024-01-04", end="2026-08-20", freq="7D")
    ...
    spike = 2800.0 * np.exp(-((i - 28) ** 2) / 60.0)   # "Red Sea crisis spike in mid-2024"
    base_comp = 2100.0 + (t * 1800.0) + spike + np.sin(i * 0.4) * 200.0
    sh_rot = round(comp * 1.12 + np.sin(i * 0.3) * 80.0, 1)
    ...
# main():
    if not primary:                      # live page unparseable (HTTP 429, JS-rendered, ...)
        csv_path = update_csv()          # -> generate_canonical_wci_history()
```

A later commit reduced it to a stub that returns an empty frame (*"no values synthesized"*), so no
new fabricated row can be written - **but nothing removed the 138 it had already written.** All
138 survived in the file, in the app, and in every downstream build.

## Proof 1 - the rows reproduce the formula exactly

Reproduced the removed generator verbatim (grid `2024-01-04 .. 2026-08-20`, `freq="7D"`,
`n = 138`) and compared all six columns of every row on that grid:

**138 of 138 rows reproduce the synthesizer exactly (tolerance 0.051, i.e. the publisher's
rounding to 1 dp).** 138 of the file's 145 rows. The remaining 7 were the genuinely scraped
2026-08-25..2026-09-20 prints.

## Proof 2 - the publisher disagrees, and the CSV matches the FORMULA (decisive)

Parsed the publisher's own archived pages with the fixed parser (Wayback `id_` raw snapshots):

| the page's assessment | publisher's printed composite | the CSV's value | the synthesizer's value |
|---|---|---|---|
| 2024-07-04 | **5,868** | 4,893.0 | 4,893.0 |
| 2025-07-10 | **2,672** | 3,167.0 | 3,167.0 |
| 2026-03-05 | **1,958** | 3,761.6 | 3,761.6 |

Three independently captured pages, three outright disagreements, and in every case the CSV holds
exactly the number the formula produces. The same check on the route values (2024-07-04:
Rotterdam 8,056, Genoa 7,573, LA 7,472, NY 9,158 printed) matches the archived page, not the CSV.

## Action taken

* The 138 synthetic rows were **moved** (not deleted) to
  **`data/audit/drewry_wci_synthetic_quarantine.csv`** - committed evidence, 138 rows, the exact
  rows that reproduce the formula.
* `data/indices/drewry_wci_historical.csv` now holds **7 rows** - the only ones actually scraped
  from the publisher - each verified against the publisher's own markdown
  (`docs/drewry_wci_display_verdict.md`).
* **No fabricated value remains in a displayed artefact.** The chart renders 7 honest points
  instead of 145 where 95% were invented.
* Reproduce: `python3 scratch/purge_wci_synthetic.py` (idempotent). Detector used:
  exact reproduction of the generator, so it cannot mis-fire on real data.

## Repopulating with REAL history (in progress)

`scripts/scrapers/backfill_wci_history.py` (new, committed) rebuilds the series from the
publisher's own archived pages: one capture per ISO week (the earliest in that week, since the page
prints that week's assessment), append-only JSONL checkpoint for `--resume`, one HTTP fetch at a
time, and no row written unless all five core values were parsed from the page. `--stack` then
emits `data/audit/drewry_wci_real_rows_from_wayback.csv`.

### The parser had to be fixed for the OLDER page eras first - and this is why the trial mattered

Repairing the 7 rows only exercised the 2026 prose (`...rose 2% to $7,352 per 40ft container`).
The archived pages from 2021-2024 use two further constructions, and both broke the parser:

1. **change before level**: *"rates from Shanghai to New York increased 17% **or $1,331 to $9,158**
   per 40ft container"* - the number nearest the label is the CHANGE, so the parse said
   Shanghai-Rotterdam was **734** instead of **8,056** (a 10x-class error, in the plausible
   direction). Fixed: a value introduced by `to` outranks a nearer value that is not.
2. **positional "respectively" list**: *"rates on Shanghai to Los Angeles, Rotterdam to Shanghai
   and Los Angeles to Shanghai increased by 6% to $2,100, 3% to $466 and 1% to $774 per feu
   respectively"* - labels and values are clustered in the same order, so proximity gave Los
   Angeles the $466 that belongs to Rotterdam-Shanghai. Fixed: k-th label -> k-th value.

Trialed on snapshots from four different years, each checked against the sentence printed on that
page:

| snapshot | parsed | matches the page? |
|---|---|---|
| 2023-12-21 | R 1,667 · G 1,956 · LA 2,100 · NY 3,074 · comp 1,661 | yes |
| 2024-07-04 | R 8,056 · G 7,573 · LA 7,472 · NY 9,158 · comp 5,868 | yes |
| 2025-01-10 | R 4,375 · G 5,210 · LA 5,476 · NY 7,085 · comp 3,986 | yes |
| 2026-09-12 | R 3,997 · G 4,216 · LA 7,352 · NY 9,726 · comp 4,476 | yes |

The 2026 control is the strongest: it reproduces the same four values as the publisher's own
markdown that the 7 surviving rows came from.

## Lesson

**A "synthetic baseline" left in a shipped file is a fabrication, and a later commit that neuters
the generator does not clean up after it.** The row count was stable, the CSV was well-formed,
every schema check passed, and the numbers were plausible - 2024's fake composite peak of 4,893
against a real 5,868 is exactly the kind of value nobody eyeballs. The only things that caught it
were (a) reading the file's own history and (b) parsing the publisher's pages and DISAGREEING.
This source also showed the two-era prose trap the skill warns about: the same publisher's layout
changed between 2024 and 2026 in a way that silently turned a level into a change.

## Status of the backfill

Launched 2026-09-29 14:49 as a background job (checkpoint
`data/extracted/wci_backfill/checkpoint.jsonl`, log `scratch/wci_backfill.log`). It is resumable -
re-running `--fetch` skips completed snapshots - and `--stack` is safe to run at any time. Judge it
by the advancing checkpoint line count, never by `ps`.

---

## Backfill result (measured, completed this run)

`backfill_wci_history.py --fetch` ran to completion: **231 archived captures** (one per ISO week,
2021-2026), **81 of which yielded all five values**. Then `--stack` applied the gates.

| | capture rows |
|---|---|
| archived captures fetched | 231 |
| all five values parsed from the page | 81 |
| passed the numeric + contamination gates | 30 |
| **shipped into the displayed CSV (2026)** | **10** |
| withheld as an unverified era (2021-2025) | 71 |

`data/indices/drewry_wci_historical.csv` is now **17 rows, all 2026** - the 7 publisher-markdown
verified prints plus 10 backfilled ones. Controls on the merged file: **0** fused
`rotterdam == genoa`, **0** rows where the composite equals a route value, **0** two-decimal
values (all three counts were also 0 on the 7-row file).

### The 2026 rows are trialed; the 2024-2025 rows are NOT, and that is measured

Four 2026 captures were re-parsed and read against the sentence printed on their own page:

| capture | printed sentence | parsed | verdict |
|---|---|---|---|
| 2026-03-12 | "Shanghai–Rotterdam increased 19% to **$2,443** … Shanghai–Genoa increased 10% to **$3,120**" | R 2,443 · G 3,120 | matches |
| 2026-05-21 | "Shanghai to Rotterdam surged 15% to **$2,773** … Shanghai to Genoa jumped 10% to **$4,082**" | R 2,773 · G 4,082 | matches |
| 2026-07-30 | "Shanghai to Los Angeles declined 2% to **$5,739** … Shanghai to New York held steady at **$7,578**" | LA 5,739 · NY 7,578 | matches |
| 2026-09-12 | (see the earlier table) | R 3,997 · G 4,216 · LA 7,352 · NY 9,726 | matches |

Plus the strongest control available: **3/3 staged captures within a week of a publisher-markdown
snapshot equal that markdown on ALL FIVE values** (the 2026-09-03 capture reproduces the md's
4,465 / 4,092 / 4,368 / 7,185 / 9,587 exactly).

The 2024 and 2025 eras were sampled the same way and are **not yet reliable**:

| capture | printed sentence | parsed | verdict |
|---|---|---|---|
| 2024-02-29 | "Rotterdam decreased 7% or $277 to **$3,944** … Genoa dropped 6% or $285 to **$4,757** … LA declined 4% or $197 to **$4,486**" | R 3,944 · G 4,757 · LA 4,486 | matches |
| 2025-01-23 | "Rotterdam decreased 19% or $797 to **$3,434** … Genoa fell 10% or $524 to **$4,562** … LA reduced 8% or $415 to **$4,813**" | R 3,434 · G 4,562 · LA 4,813 | matches |
| **2024-04-18** | "rates on Shanghai to Rotterdam and Shanghai to Genoa declined 2% to **$2,989 and $3,577** per feu respectively" | R 2,989 · **G 2,291** | **WRONG** - Genoa is off by a third |

So 3 of 4 sampled 2023-2025 rows are right and one is wrong - a per-row error rate far too high to
put in a displayed series, which is why the era gate withholds them instead of shipping them.
The 2024-04-18 failure has a specific cause worth the next run's time: `assign_route_values()`
assigns each route to the FIRST line that mentions it, so a stray earlier mention of a route on a
different line blocks the correct later assignment. A global best-assignment (score every line,
then pick) is the fix.

### Honest status

* Displayed file: **17 real 2026 rows**, no fabricated and no unverified row.
* Withheld: **71 complete captures (2021-2025)** in the checkpoint, plus the 138 synthetic rows in
  `data/audit/drewry_wci_synthetic_quarantine.csv`. Nothing was deleted.
* Resumable: `python3 scripts/scrapers/backfill_wci_history.py --fetch` skips completed captures;
  `--stack` regenerates the staging file. The checkpoint is the durable artefact.
* The live Drewry site returns **HTTP 429** from this box, so the scraper's own refresh path is
  currently Wayback-only.
