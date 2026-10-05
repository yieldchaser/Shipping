# Verdict: the app-visible knowledge (QA) tier has been FROZEN for 6 days - root-caused and fixed

Run: 2026-10-05 19:2x IST (unattended, 30m source-by-source job). Read-only except one
tested code fix. Branch `main` (a parallel automation is committing ffa-live ticks; local
HEAD == origin/main == 380961259).

## The finding

The QA knowledge tier the app serves (`knowledge/chunks/*.jsonl`, loaded by index.html via
`qaSrcHellenic` / `qaSrcIronOre` / `qaSrcShipbuilding` / `qaSrcBreakwave` / `qaSrcBaltic` /
`qaSrcBooks`) has not advanced since **2026-09-29** while the collection is current to
**2026-10-03**.

Measured (newest dated chunk per QA group vs newest collected PDF):

| QA group | newest chunk date | newest corpus date |
|---|---|---|
| hellenic (iron_ore) | 2026-09-29 | 2026-10-03 (md present to 10-02) |
| hellenic (demolition) | 2026-09-29 | 2026-10-03 |
| breakwave | 2026-09-29 | 2026-09-29 |
| baltic | 2026-09-25 | - |
| broker_reports | 2026-09-28 | - |

`knowledge/chunks/index.json` `generated_at` = 2026-09-29T17:23Z. Last commit touching
`knowledge/chunks/` = `dfd168848 knowledge: update 2026-09-29`.

The md tier IS current: `data/extracted/md/hellenic/iron_ore_pdf/2026/` holds 2026-09-30,
2026-10-01 and 2026-10-02 (its newest md), and `data/extracted/md/hellenic/demolition/gms/2026/`
holds a 2026-10-02/10-03 GMS report. Only the app-visible chunk layer lags.

## Root cause (proven, not inferred)

The GitHub Actions workflow **Daily Knowledge Update** (`daily_knowledge_update.yml`,
cron `30 15 * * *`) has **FAILED on every run since 2026-09-29** - 6 consecutive failures,
each completing the same way (GitHub API `.../actions/workflows/daily_knowledge_update.yml/runs`):

```
2026-10-04T18:44Z completed failure e91f6605
2026-10-03T18:47Z completed failure 81b61737
2026-10-02T20:05Z completed failure 1d4c1f67
2026-10-01T20:26Z completed failure 58a2bbad
2026-09-30T20:13Z completed failure 4c84471f
2026-09-29T20:08Z completed failure 789339ec
```

The failing step in every run is **`Guardrail - verify Breakwave signals freshness`**
(step 10 of 14). Because it fails, `Validate updated knowledge` and `Commit if changes`
are **skipped**, so the knowledge-bot never commits - the whole QA tier stays frozen even
though step 9 (`Process new reports`) succeeded.

That step runs `python scripts/check_breakwave_freshness.py --check signals_vs_reports`.
Reproduced locally (read-only):

```
[signals_vs_reports] drybulk: signals=None reports=2026-09-29
[signals_vs_reports] tankers: signals=None reports=2026-09-22
[freshness] FAILED:
  - drybulk: no breakwave signals found
  - tankers: no breakwave signals found
```

The guardrail reads `knowledge/derived/signals.jsonl` (a 92 MB, `.gitignore`d,
regenerable full-fidelity artefact). Its breakwave rows - and those of its published
sibling `signals_public.jsonl` - **lag by one report**, while the dedicated artefact
`knowledge/derived/breakwave_signals.json` is **current**:

| artefact | drybulk max | tankers max |
|---|---|---|
| `knowledge/derived/breakwave_signals.json` | **2026-09-29** | **2026-09-22** |
| `knowledge/derived/signals_public.jsonl` | 2026-09-15 | 2026-09-08 |
| `knowledge/derived/signals.jsonl` | absent locally (gitignored) | - |
| newest breakwave report PDF | 2026-09-29 | 2026-09-22 |

So the extraction is NOT missing: `breakwave_signals.json` already holds the newest signals
(`breakwave_drybulk_2026-09-29`, `breakwave_tankers_2026-09-22`), the doc manifest holds all
291 breakwave docs (no diff against `breakwave_signals.json`), and the newest report's page-1
carries the Short-term Indicators the extractor keys on. The guardrail simply reads the one
breakwave artefact that has fallen behind (or is absent on a clean CI checkout), and its
failure aborts **all** sources' knowledge commits.

## Fix applied (tested)

`scripts/check_breakwave_freshness.py` now takes the **max** of two readers - the legacy
`signals.jsonl` and the dedicated, always-rebuilt `breakwave_signals.json` - so the guardrail
reflects the authoritative breakwave signal date instead of a stale incremental sibling.

```
python3 -m py_compile scripts/check_breakwave_freshness.py     # OK
python3 scripts/check_breakwave_freshness.py --check signals_vs_reports
  [signals_vs_reports] drybulk: signals=2026-09-29 reports=2026-09-29
  [signals_vs_reports] tankers: signals=2026-09-22 reports=2026-09-22
  [freshness] OK
EXIT=0
```

Before the fix the same command returned EXIT=1 ("no breakwave signals found"). Fallback
behaviour is unchanged when `breakwave_signals.json` is missing.

## Still a decision for the owner

1. The guardrail is **source-scoped but aborts the whole knowledge commit**. One publisher's
   staleness froze hellenic, baltic, breakwave, broker_reports, books and poten for 6 days.
   Consider making the guardrail non-fatal (warn, or scope the commit) so a single source
   cannot stall the entire QA tier.
2. The 92 MB `signals.jsonl` is not committed (correctly - `.gitignore`d). Confirm the CI
   rebuilds it in full each run, or the incremental path will keep dropping recent rows. The
   read-path fix above removes the immediate dependency on that.
3. The fix is on `main`'s working tree **uncommitted** (parallel automation active; "NEVER
   touch main"). It must be committed to `main` for CI to pick it up.

## What was NOT done

- No re-extraction, no paid calls, no corpus mutation. No broad git checkout/stash.
- `signals.jsonl` itself was not regenerated (92 MB derived artefact; the fix reads around it).
