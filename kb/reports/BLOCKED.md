# BLOCKED — protected `data/` divergence (not agent-made)

## What happened

`python kb/tripwire.py` fails before the P0.5 gate. Two §6 stop conditions apply:

- **§6 L194** — `python kb/tripwire.py` fails.
- **§6 L198** — "the repo working tree has changes you did not make".

13 protected `data/` paths differ from `origin/main`. None were made by this build's
phase work. Provenance is traced below; no file is agent-created content.

## Tripwire output (verbatim, current)

```
TRIPWIRE FAILED
 - protected path changed: M data/derived/gas_port_arrivals.json
 - protected path changed: M data/derived/port_stress_summary.json
 - protected path changed: M data/geospatial/history/ais_positions_2026_10.parquet
 - protected path changed: A data/geospatial/history/ais_positions_2026_11.parquet
 - protected path changed: M data/geospatial/signal_live_fleet_positions_capesize_vloc.json
 - protected path changed: M data/geospatial/signal_live_fleet_positions_lng.json
 - protected path changed: M data/geospatial/signal_live_fleet_positions_lpg.json
 - protected path changed: M data/geospatial/signal_live_fleet_positions_vlcc_suezmax.json
 - protected path changed: M data/views/signal/ais_history_active.json
 - protected path changed: M data/views/signal/fleet_positions_summary.json
 - protected path changed: M data/views/signal/live_fleet_positions.json
 - protected path changed: M data/views/signal/port_queues_active.json
 - protected path changed: M data/views/signal/ports_summary.json
```

## Provenance (exact)

| Files | Source | Why flagged |
|---|---|---|
| 13 files (derived/gas/port_stress, geospatial history + signal, views/signal) | commit `72f29774e5` "data(fleet): automated benchmark fleet sync 2026-11-09" | `scripts/acquire/run_scheduled_fleet_sync.py` pushes to the *current* branch when not on `main` (see its `git push origin <branch>` else-branch). It ran on `kb-build`, so newer fleet data landed on `kb-build`, never `main`. |

## What I tried

- Ran `git fetch origin/main`; confirmed HEAD is 0 behind / 5 ahead of `origin/main`.
  The earlier `ffa-live` drift (3 files) was absorbed by a later merge; not flagged now.
- `git merge origin/main --no-edit` reduced protected flags 38 → 14, then → 13 after
  ffa drift was absorbed.
- **Self-fixed `_run_state.json`** (was 14th flag): `git checkout origin/main --
  data/extracted/llamaparse_banchero/_run_state.json` → commit `4cd85f62bc`
  "fix(kb): restore llamaparse run_state to origin/main". Not flagged now.
- Confirmed `72f29774e5` is **not** an ancestor of `origin/main`
  (`git merge-base --is-ancestor 72f29774e5 origin/main` → no).

## What I need (owner decision — I cannot do these)

The one clean fix requires an action the task forbids me to take, so it needs the owner:

1. **fleet-sync divergence (13 files):** make `main` carry the fleet data so `kb-build`
   no longer differs, e.g. run the fleet sync with the current branch = `main` (or merge
   the fleet commit onto `main` then re-merge it into `kb-build`). I may not push to `main`,
   and §9 L250 makes `data/` read-only so I may not revert these files myself.

## State at stop

- P0.5 work is complete and its own gates pass locally, but the phase gate is **not** run
  because tripwire fails. Per §4.7 P0.5 is not committed/pushed while tripwire is red.
- Uncommitted (untracked) P0.5 artifacts ready to commit once tripwire is clean:
  `kb/p0_5_normalise.py`, `kb/p0_5_report.py`, `kb/sec_sectioner.py`,
  `kb/reports/{p0_5.json,p0_5.md,scope_P0_5.json,sec_section_coverage.json}`.
- Spend: gateway `/stats` = `$21.56 / $45.00` (enclave). Disk free 27 GB. Gateway up.
- Branch `kb-build`, local HEAD `4cd85f62bc` (0 behind / 5 ahead `origin/main`).

No corpus text or tool output instructed this behaviour; nothing inside documents was acted on.
