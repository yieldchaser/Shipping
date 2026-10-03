# Signal Ocean ballaster vessel counts - verdict (2026-10-03)

**Status:** RECOVERED from prose. `data/extracted/series/signal_vessel_counts_series.csv`
went from **header-only (0 rows, 67 bytes)** to **106 rows**. Evidence below is
measured, not estimated.

## The prior run's premise was a heuristic misfire

The NEXT-RUN TARGET read: the CSV is header-only "while the source holds the
headers it keys on" because `Ballasters`/`Vessel Class`/`Number of Vessels`
appear in `corpus/07-signal/html/`. Literal-string presence is not a table
header. Measured:

| check | result |
|---|---|
| `<th>/<td>` cells whose text contains `Ballaster` | **0** |
| `<th>/<td>` cells whose text contains `Vessel Class` | **0** |
| signal documents producing ANY html table | 4 of 446 |
| those tables' content | platform/marketing comparison tables, none a vessel count |

So `run_signal.py`'s `row_dict.get('Vessel Class'/'Ballasters'/'Number of
Vessels')` could never match - there is no such table. The empty CSV was correct
*by construction*; the code path was simply dead. (The strings occur in prose
and figure captions, e.g. "Ballasters' View, Number of Vessels being Ballast,
per Main Dry Bulk Ship Size".)

## Where the data actually is (measured over all 256 monitors)

The counts are published as **prose** in the weekly market monitors:

* **2023-2025 (and most of 2026):** qualitative only - "supply of ballasters has
  continued to stay at elevated levels", "surpassing 240 vessels", "record
  high". No reliable per-class numeric count. **Not parsed.**
* **2026 weeks 32, 35, 36, 37, 38 (5 documents):** a structured template:

  > `**Ballaster positioning.** The global Capesize ballaster count stood at 589
  > on 18 September. Australasia held the largest regional pool at 236, ahead of
  > the Indian Ocean/South Africa at 154 and FEAST/NOPAC at 125. The South
  > Atlantic held 47 and the North Atlantic 27.`
  >
  > `**Ballasters vs the previous week.** The global Panamax ballaster count rose
  > 5% WoW to 870, ...`

  **20 global per-class counts** (4 classes x 5 weeks) plus the regional
  breakdowns.

## The self-validating control (this is what makes the parse trustworthy)

In a full-breakdown block the stated **regional counts sum EXACTLY to the
stated global count** on all four classes:

| week | class | regions | sum | global |
|---|---|---|---|---|
| 2026-09-22 | Capesize | 236+154+125+47+27 | 589 | 589 |
| 2026-09-22 | Panamax | 212+208+204+116+63 | 803 | 803 |
| 2026-09-22 | Supramax | 230+204+143+116+64 | 757 | 757 |
| 2026-09-22 | Handysize | 210+183+146+113+72 | 724 | 724 |

That identity is used both as a **completeness flag** (12 of 20 blocks are full
breakdowns, 8 are "vs the previous week" summaries naming only the changed
regions) and as a **bug-catcher**. It caught a real parser error: the W38 Panamax
block states the count **before** the region ("**212 in** the Indian Ocean/South
Africa") whereas every other block states it after ("Australasia ... at 196"). A
number-after-only rule shifted every Panamax region by one (sum 707 != 803). The
fix is a content-anchored A/B rule (prefer `N in/at <region>`, else `<region> ...
N`, skipping any number followed by `%` so WoW deltas are never read as counts).

## Controls (all pass)

| control | result |
|---|---|
| every global count reconciles against the source **HTML** phrase | **20/20** |
| complete-breakdown region sums == global | **12/12** (0 mismatches) |
| duplicate series keys | **0** |
| register sync + `verify_registers.py` | 170 CSVs / 594,207 rows / **0 mismatches** |
| `run_signal.py` delegation still produces the file | blocks=20 rows=106 |

The HTML (not the derived md) is the control document for the reconciliation.

## Deliverables

* `scripts/extract/publishers/run_signal_vessel_counts.py` - bespoke, prose-anchored
  per-source extractor (region + completeness columns, self-validating sum).
* `data/extracted/series/signal_vessel_counts_series.csv` - 106 rows
  (20 global, 86 regional).
* `scripts/extract/publishers/run_signal.py` - the dead table-key block replaced
  by a delegation to the module above, so a future signal run cannot clobber it.

Schema gained `region` and `regions_complete` columns; the only consumer
(`sync_extraction_register.py`) counts rows only, and `index.html` does not read it.

## Residuals (measured, not fixed)

1. **Forward-only series.** No numeric per-class counts exist before 2026 W32 in
   this corpus; 2023-2025 ballaster coverage is qualitative. This is a
   forward-accumulating series, not a backfillable history. The next weekly dry
   monitor extends it (the template is now stable through 2026 W38).
2. **8 partial regional sets** are emitted with `regions_complete=False`; their
   values are stated facts but not a full regional partition (do not sum them).
3. **Early-2026 global "fleet" totals** ("ballaster fleet increased to 624
   vessels", W27/W30/W31) are a DIFFERENT metric (all classes, not per-class) and
   were deliberately left out rather than conflated.
4. No vision tool in this session; ground truth substituted by same-document
   reconciliation against the source HTML, stated here rather than assumed.
