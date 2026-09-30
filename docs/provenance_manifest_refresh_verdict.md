# Provenance manifest refresh — the WCI registry entry was 37 rows and 2 years stale

Run 2026-09-30 ~20:2x IST. Branch off `main`. No extraction re-run, no data file
touched: one derived registry regenerated with its own documented builder.

## The defect, measured

`data/provenance/manifest.json` is the registry of every `data/` file `index.html`
fetches. For `indices_drewry_wci_historical` it declared:

| field | declared | actual on disk |
|---|---|---|
| `row_count` | **80** | **117** |
| `date_span` | `2023-01-05 .. 2026-09-24` | `2021-05-20 .. 2026-09-24` |

`data/indices/drewry_wci_historical.csv` is 118 lines (117 data rows), mtime
`2026-09-30 16:40:53 IST`, and `index.html` fetches that exact path.

Cause: the 15:3x-17:4x WCI run grew the displayed index 105 -> 117 rows by
recovering the 2021-2022 prints. The registry was generated at
`2026-09-30T10:58:40Z`, i.e. **before** that growth, and nothing regenerates it
automatically.

## Census BEFORE the fix (112 entries)

`scripts/verify/audit_manifest_staleness.py` (added by this run; reuses the
generator's own `inspect_file()` so the comparison is apples-to-apples):

- AGREE on `row_count` AND `date_span`: **111 / 112**
- STALE `row_count`: **1** (`indices_drewry_wci_historical`, 80 -> 117)
- STALE `date_span`: **1** (same entry)
- `output_file` missing on disk: **0**
- entries with no `output_file`: **0**

So the registry is otherwise healthy — this was a single hand-off miss, not a
systemic rot.

## Fix

`python3 scripts/verify/build_provenance_manifest.py` — the documented builder,
never a hand-edit. It rebuilds `series` from disk and preserves `datasets`.

## Control (before -> after, field-level)

- `series` set identical: 112 -> 112, **added [] removed []**, order identical.
- `datasets` preserved: 4 -> 4. `unregistered_count` unchanged: 3 -> 3.
- `row_count` changed on **exactly 1** entry: `indices_drewry_wci_historical` 80 -> 117.
- `date_span` changed on **exactly 1** entry: -> `['2021-05-20','2026-09-24']`.
- `missing_fields`: 0 (audit).

## Audit control (`scripts/verify/audit_provenance_manifest.py`)

| | before manifest | after manifest |
|---|---|---|
| Disk discrepancies | **7** | **5** |
| incl. WCI flags | `row_count_mismatch (80 vs 117)`, `date_span_mismatch` | **gone** |
| Clustered identical timestamps (>=20) | 2 | **1** |

The two WCI flags are exactly what disappeared. The 5 that remain are
**pre-existing heuristic disagreements, not staleness**: `audit_provenance_manifest.py`
counts `len(dict)` while the generator picks the meaningful sub-key.
Verified on `data/derived/fearnleys_dry_routes_daily.json` — top-level keys are
`meta`/`series` (len 2), and `series` holds **14** entries; the generator's 14 is
the right number and the audit's 2 is the artifact. Same shape for
`fearnleys_nb_prices` (17), `fearnleys_tanker_routes_daily` (135),
`views_dashboard_master` (1544) and the manifest itself (112 vs 6).

## One field did churn, and it is honest

`last_fetched_utc` changed on all 112 entries, because the generator defines it as
the file's **mtime**. The before-registry held only **10 distinct** timestamps
across 112 series (a fake batch stamp from a mass tree write); the after-registry
holds **42 distinct**, and each was verified equal to the file's true mtime after
IST -> UTC conversion (4/4 spot-checked: `australia_ppa_iron_ore` 2026-09-21 00:43:46 IST
= `2026-09-20T19:13:46Z`; `brazil_comexstat_exports`; `bdiy_historical`;
`drewry_wci_historical` 16:40:53 IST = `2026-09-30T11:10:53Z`).

Caveat worth carrying forward: the tree was re-materialised at `11:04:41Z`, so 31
series legitimately share that mtime, and the audit still flags one cluster. That
is a property of the tree, not of the builder. The project rule stands —
**derive ages from FILENAMES, not mtime** — so treat `last_fetched_utc` as a weak
field by construction.

## State after

`scripts/verify/audit_manifest_staleness.py` -> `AGREE rows+span: 112`, 0 stale,
0 missing, exit 0. `sha256(manifest.json)` restored-and-rechecked identical to the
generated file (`f7a56629f021519b6f4f44278374dca77ad20d48c61448999355bd272cd02f60`).

## Not done (named)

- Still open from the WCI ledger: the **2026-02-12** print (no origin anywhere in
  the sentence, so the elided-lane fallback cannot fire; the values ARE printed);
  91 captures still incomplete; `upsert_wci_rows()` still dedupes by date only, so
  a Thursday assertion would be needed to make this class unable to reappear.
- Nothing regenerates this registry after a data rewrite. A CI step that runs
  `audit_manifest_staleness.py` and fails on a non-zero exit would close the class.

## Deliberately NOT committed: the regenerated audit report

Running the audit rewrites `data/provenance/phase8_provenance_audit.json`, which
embeds the full on-disk unregistered list. That list grew from **1,478** entries in
the committed report to **26,722** now (the tree gained data files since it was
last written), so the report goes from 110 KB / 1,602 lines to **2.7 MB / 26,832
lines** — 25x, for a file nothing reads (only the audit itself writes it). That is
payload drift, not evidence, so the report is left at its committed revision.
Regenerate it on demand: `python3 scripts/verify/audit_provenance_manifest.py`.
