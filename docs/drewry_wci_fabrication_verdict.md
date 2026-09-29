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
