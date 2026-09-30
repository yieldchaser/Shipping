# Drewry WCI: the ELIDED-SECOND-LANE shapes recovered, and what they shipped (2026-09-30)

Three lane-list shapes were invisible to the parser. Each was fixed on its own
measured control, and the effect is **displayed WCI rows 105 -> 117** with
**0 previously displayed rows changed**.

The defect is always the same family: the publisher names a lane once and then
refers to a SECOND lane without repeating the origin, so `label_rx` (which needs
a separator between two ports) never sees it. The sentence then counts ONE lane
where the page prints two, the ordinal/`respectively` rule cannot fire, and the
second lane's level is silently dropped **while every recall check passes** -
the value IS on the page.

## pv12 - a bare port after a conjunction

`"Spot rates on the Transpacific trade ... with rates from Shanghai to New York
and Los Angeles increasing 9% to $9,507 and $6,802 per 40ft container,
respectively."` (2026-08-20)

A continuation is now taken only when it starts IMMEDIATELY after the label, and
not when the captured words are themselves the origin of a new pair
(`"...and Shanghai to Rotterdam"` keeps its own label). Colour: the second lane's
column is **derived from `ROUTE_PATTERNS`** by reconstructing `"<origin> to
<dest>"` - no lane is hardcoded.

**CONTROL (all 230 cached pages re-parsed in process, nothing written): 220
unchanged, 10 moved, and ALL 10 are `None -> value`** - no value changed to
another value, no value lost, 0 parse errors. Each recovery read back against its
own page sentence:

| print | recovered | that print's own sentence |
|---|---|---|
| 2024-02-22 | `shanghai_ny` = $5,976 | "from Shanghai to Genoa and New York dropped by 3% to $5,042 and $5,976 per feu respectively" |
| 2024-08-29 | `shanghai_genoa` = $6,611 | "from Shanghai to Rotterdam and Genoa decreased 3% to $7,204 and $6,611 ... respectively" |
| 2025-06-12 | `shanghai_genoa` = $4,054 | "from Shanghai to Rotterdam and Genoa remained stable ... at $2,837 and $4,054 ... respectively" |
| 2025-11-27 (x2) | `shanghai_rotterdam` = $2,165 | "from Shanghai to Genoa and Rotterdam falling 1% ... to $2,300 and $2,165" |
| 2026-04-16 (x2) | `shanghai_la` = $2,810 | "from Shanghai to New York and Los Angeles decreased 3% to $3,552 and $2,810, respectively" |
| 2026-04-30 | `shanghai_rotterdam` = $2,127 | "from Shanghai to Genoa and Rotterdam fell 1% to $3,039 and $2,127 ... respectively" |
| 2026-08-20 (x2) | `shanghai_la` = $6,802 | "from Shanghai to New York and Los Angeles increasing 9% to $9,507 and $6,802 ... respectively" |

## pv13 - the origin elided as `"rates to <port>"`

`"...rates from Shanghai to New York falling 6% to $2,735 per 40ft container and
rates to Los Angeles reducing 4% to $2,089."` (2025-11-27)

Implemented as a **monotone fallback**: it runs after the whole sentence's own
logic and fills only a lane that is still EMPTY, so it can never move or
overwrite an assignment another rule made. Its value is the level of the elided
mention's OWN clause, taken nearest to it.

**CONTROL: 226 unchanged, 4 moved, ALL 4 `None -> value`**, each read back:
2025-11-13 `shanghai_la` $2,328 ("...to New York falling 15% to $3,254 ... and
rates to Los Angeles dropping 12% to $2,328"), 2025-11-27 `shanghai_la` $2,089
(x2), 2026-03-26 `shanghai_rotterdam` $2,552 ("Shanghai-Genoa increased 12% to
$3,474 ... while rates to Rotterdam rose 3% to $2,552").

## pv14 - the elided mention written as `"those to <port>"`

`"...rates from Shanghai to New York jumped 3% to $3,393 per 40ft container,
while those to Los Angeles increased 4% to $2,686."` (2026-03-26)

One measured word added to the same fallback (`rates|those`).

**CONTROL: 224 unchanged, 6 moved, ALL 6 `None -> value`**: 2025-10-23
`shanghai_ny` $3,420, 2025-10-30 $3,568, 2025-11-06 $3,837, 2025-12-04 $2,895,
2025-12-11 $2,756 (each "...to Los Angeles ... and those to New York rose 4-8% to
$X"), and 2026-03-26 `shanghai_la` $2,686.

## What it shipped (measured end to end)

`PARSER_VERSION` 11 -> 14; all 230 locally cached captures re-parsed offline (the
1 snapshot with no cached page, `20251006233302`, still needs the network).

| measure | before | after |
|---|---|---|
| captures leaving a lane unparsed | 107 (the ledger count) | **91** |
| stacked SHIPPABLE prints (`data/audit/drewry_wci_real_rows_from_wayback.csv`) | 103 | **116** |
| **displayed rows (`data/indices/drewry_wci_historical.csv`)** | **105** | **117** |
| rows LOST / previously displayed rows CHANGED / cell corrections at merge | - | **0 / 0 / 0** |
| blank core cells / duplicate value-groups | 0 | **0 / 0** |
| dates unique, strictly increasing, all Thursdays | yes | **yes** (2021-05-20 .. 2026-09-24) |

Gate census after the change: `{"snapshots": 231, "fetch_failed": 1, "incomplete":
91, "numeric": 4, "composite": 0, "contam": 0, "fused": 0, "pre_era": 0}`.

Every one of the 12 added rows was verified **against its own cached page**: the
page's printed date == the row's date, the row's five values == the current
parse, and **all five appear verbatim as `$X,XXX` in that page's own text**
(12/12 rows, 60/60 values). Repo tests: `pytest tests/test_loader_contracts.py
tests/test_question_routing_and_grounding.py` = **34 passed**.
No network, no API spend, no vision tool in this session (substituted by the
same-document reconciliation above).

## Still open, named and measured

1. **`2026-02-12`** - `"Spot rates from Shanghai to major US destinations
   declined slightly ... with spot rates to Los Angeles and New York falling 1%
   to $2,214 and $2,800 per 40ft container, respectively."` **No origin at all**
   in the sentence, so the elided-origin fallback cannot fire (it requires a lane
   already matched in the same sentence). Recovering this needs an origin
   INFERENCE (e.g. the page's only origin), which is a new class of rule and must
   be trialed before it ships - the value ($2,214 / $2,800) IS printed.
2. **91 captures still incomplete**, and the lane histogram says why:
   `shanghai_ny` alone 20, `rotterdam+genoa` 14, `shanghai_la` 13, all four 11
   (`by year: 2021: 30, 2023: 21, 2022: 19, 2025: 14, 2024: 11, 2026: 2`).
   Sampled and READ, not assumed: **2025-06-12 prints NO level for Los Angeles**
   ("spot rates to Los Angeles increased 1% in the past week and 89% in the past
   four weeks") - that missing value is the publisher's, not ours.
3. The 4 numeric-gated prints and the 1 never-fetched capture
   (`20251006233302`) stand.
4. **`data/provenance/manifest.json` is now stale for this series**:
   `row_count: 108`, `date_span: ["2021-06-24", ...]`, `last_fetched_utc:
   2026-09-30T04:10:46Z` - the file holds **117** rows starting **2021-05-20**.
   Regenerate with `python3 scripts/verify/build_provenance_manifest.py`
   (never hand-edit); not run here because it rewrites the WHOLE registry.
5. The 2021-07-01 `"k labels, 2k numbers"` print and `upsert_wci_rows()`'s
   date-only dedupe (a Thursday assertion would make this whole class unable to
   reappear silently) remain.
