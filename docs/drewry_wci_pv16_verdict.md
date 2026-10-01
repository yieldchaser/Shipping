# Drewry WCI - pv16: the BARE (un-$'d) LEVEL, and the last never-fetched capture

Ran offline off the 230-page local Wayback cache: `--fetch --refresh` then
`--stack --era-from 2021-01-01` then `merge_display.py --apply`. No paid API.
Branch only. **Displayed rows 118 -> 120.**

## The defect

The publisher sometimes prints a LEVEL with **no dollar sign**:

> Freight rates from New York to Rotterdam increased 4% or $28 to $710 per FEU.
> Likewise, rates from Shanghai to Rotterdam rose 3% or $219 to $8,267 per 40ft
> box. Similarly, rates from Shanghai to New York spiked 2% or $225 to $9,612 per
> 40ft container. Rates from Shanghai to Genoa inched up 1% or $113 to $7,727 per
> FEU. Conversely, rates from Shanghai to Los Angeles fell 3% or $224 to **7,288**
> per 40ft box. (cached capture `20240722012524.html`, 2024-07-18)

`value_rx` (`\$\s*([\d,]+(?:\.\d+)?)`) requires a `$`, so `7,288` was not a
candidate at all and the Los Angeles lane took the CHANGE (`$224`). The four
tracked lanes then read `8267 / 7727 / 224 / 9612` (spread 27x), so the
**numeric gate correctly rejected the print** and it never reached the display.
The level was on the page the whole time.

## The rule (pv16, additive)

A bare number joins the candidates ONLY when all three hold:

1. the level introducer (`to|at|reach|touch|a new high|low of`) ends immediately
   before it (`to_rx`, the same anchored look-back the `$` levels use);
2. a price unit follows (`per|feu|/|40ft|container|box|for`);
3. it carries a thousands comma or is >= 4 digits - so a week number, a
   percentage or a year cannot qualify.

The rule adds candidates; it cannot by itself move an existing assignment, and
the existing clause/ordinal/`to`-anchored pool logic then picks the level.

### The trap hit while building it (report it - it cost the first trial)

The first trial measured **0 differences**: the rule fired on nothing. Cause:
`\b` written in a NON-raw outer string became a literal `0x08` BACKSPACE in the
generated module, so `BARE_UNIT_RX` was `per\x08|feu\x08|...` and the unit guard
matched nothing. This is the **same trap `COMPOSITE_AVG_RX` already carries a
comment about in this file.** Fix: write the boundaries inside an r-string, and
assert `'\x08' not in src` in the patch. A silent no-op detector would have
shipped as "the publisher's page, not our parse" - the fifth-wrong-detector
family the state file warns about.

## Controls (each measured separately, nothing written during the trial)

| control | measured |
|---|---|
| read-only trial, all 230 cached captures, cur vs pv16 in process (`scratch/wci/pv16c/trial.py`) | 230 pages parsed, **0 parser errors**, **1 value difference**: `(20240722012524, 2024-07-18, shanghai_la, 224.0 -> 7288.0)`; **229/230 unchanged** |
| the moved value against its own page | the page prints `to 7,288 per 40ft box` verbatim (`scratch/wci/read_full.py`) |
| refresh pass | 231 snapshots, 231 lacked a v16 parse, 231 re-parsed (230 from the local cache, 1 network) -> 141 complete |
| stack vs the pv15 stage | staged 118 -> **119** shippable prints; gate census `{snapshots 231, fetch_failed 1 -> 0, incomplete 90, numeric 4 -> 3, composite 0, contam 0, fused 0}`; stage diff = **exactly 2 added lines** |
| display merge | stage 119, displayed 118 -> **120**; **CELL CORRECTIONS 0**, ROWS ADDED 2, md-tier untouched; file diff = **exactly 2 added lines** |
| displayed file | 120 rows, dates unique, strictly increasing, **all Thursdays**, 2021-05-20 .. 2026-09-24; **0 blank CORE cells**; **0 duplicate value-groups** |
| repo tests | `pytest tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py` = **34 passed** (Python312) |

## The second recovered row was a FETCH, not a parse

The census had carried **`fetch_failed: 1`** - the capture `20251006233302`,
recorded for several runs as "the 1 never-fetched capture (HTTP 404)". This run
it fetched **successfully** (115,772 bytes of HTML, valid `<DOC` head) and
parsed a complete print for **2025-10-02**. Values read verbatim off that page:

> Our detailed assessment for Thursday, 02 Oct 2025. The Drewry World Container
> Index (WCI) fell 5% to **$1,669** per 40ft container ...
> Spot rates from Shanghai to Los Angeles decreased 5% to **$2,196** ... while
> those from Shanghai to New York decreased 2% to **$3,200** ...
> Asia-Europe spot rates fell ... declined 7% (**$1,613**) on Shanghai-Rotterdam
> and 9% (**$1,804**) on Shanghai-Genoa.

All five values and the date match the row that shipped. `2025-10-02` sits
between the shipped `2025-09-25` and `2025-10-23`, so it fills a real weekly
slot; the census's `fetch_failed` is now **0**.

## Provenance manifest regenerated (it was stale by 3 rows)

`python3 scripts/verify/build_provenance_manifest.py` (never hand-edited):
`indices_drewry_wci_historical` `row_count` **117 -> 120**. The regeneration also
picked up **32 further measured fields** from other pipelines whose files
advanced since the last regen (lpg charter/spot, tanker forward curves, time
charter rates, ffa_live, etc.) - those are disk measurements, not hand edits.

## Still open (measured from the checkpoint, not estimates)

* **3 numeric-gated prints**, all with the publisher's level ON the page:
  * **2024-12-19** (two snapshots) - the TWO-PARALLEL-`respectively`-LISTS shape:
    *"rates from Shanghai to Genoa and Rotterdam to Shanghai decreased 2% to
    $5,424 per feu and $508 per feu, respectively, and those from New York to
    Rotterdam and Shanghai to Rotterdam shrank 1% to $824 per feu and $4,819 per
    feu, respectively"*. Parser: genoa 5424 (right), **rotterdam_shanghai 5424
    (should be 508)**, **shanghai_rotterdam 824 (should be 4,819)** - each lane
    got its own list's FIRST value.
  * **2025-03-06** - parser gave **genoa 845**; the page says *"rates from
    Shanghai to Genoa and Los Angeles to Shanghai remained stable"*, so genoa has
    NO level that week and the print is correctly withheld. The 845 is New
    York->Rotterdam's level, one sentence earlier.
* **90 incomplete captures** by print year `2021:30 2022:19 2023:21 2024:11
  2025:9` (2026 has none left) - mostly the publisher printing no number.
* `upsert_wci_rows()` still dedupes by date only (a Thursday assertion would stop
  a dropped print from reappearing silently).

No vision tool in this session; the substitute is the same-document
reconciliation above (each value located in the page text and read verbatim).
