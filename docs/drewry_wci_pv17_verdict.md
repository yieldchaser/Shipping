# Drewry WCI - pv17: TWO PARALLEL `respectively` LISTS in ONE sentence

Offline off the 231-capture local Wayback cache. No paid API, no network for the
re-parse (all 231 came from `scratch/wci/raw/`). **Displayed rows 120 -> 121.**
Branch only; `main` was NOT committed to.

## The defect (2024-12-19, 2 snapshots, one print)

> On the other hand, rates from Shanghai to Genoa and Rotterdam to Shanghai
> decreased 2% to **$5,424** per feu and **$508** per feu, **respectively**, and
> those from New York to Rotterdam and Shanghai to Rotterdam shrank 1% to
> **$824** per feu and **$4,819** per feu, **respectively**, whereas those from
> Los Angeles to Shanghai remained stable.

The sentence holds TWO `respectively` lists, and each lane must take the value
at ITS OWN ordinal inside its own list. The parser gave:

| lane | parsed | printed on the page |
|---|---|---|
| shanghai_genoa | 5,424 | 5,424 OK |
| rotterdam_shanghai | **5,424** | **508** |
| shanghai_rotterdam | **824** | **4,819** |

i.e. each lane got its own list's FIRST value. The four tracked lanes then read
`5424 / 5424 / 4499 / 824` (spread 6.58x) and the **numeric spread gate correctly
rejected the print** (max/min > 5.0), so it never reached the display. The levels
were on the page the whole time.

WHY the existing pools all failed: the sentence yields **5 labels against 4
values** - one label is the untracked `New York to Rotterdam`, one is the
value-less tail lane `Los Angeles to Shanghai` ("remained stable"). Every pool in
the `respectively` branch (`to_vals`, `free`, `cands`, `tail`) is matched against
`len(all_labels)`, so none of them matched and the code fell through to the
CLAUSE fallback, which saw one label per clause and picked the nearest
`to`-introduced value in that clause.

## The rule (pv17, additive)

Each `respectively` marker **CLOSES** a list, so the ordinal mapping is scoped to
the part BEFORE that marker, never to the whole sentence:

1. split the sentence at every `respectively` end offset; the part after the LAST
   marker is a tail (often a different clause) and is ignored;
2. for each list part, the labels found in it (tracked OR untracked - dropping an
   untracked lane shifts every ordinal) must number the same as the values in it;
3. map them positionally, then fill **EMPTY** columns only.

It fires **only when the pool logic above returned nothing** (`vals is None`) and
bails the whole sentence if any list part mismatches, so it cannot disturb a
sentence the older rules already read.

## Controls (each measured separately)

| control | measured |
|---|---|
| read-only trial over all 231 cached captures, pre-change module vs patched (`scratch/wci/pv17/trial.py`) | 231 pages parsed, **0 parser errors**, **4 value differences**, all on the 2 snapshots of the one print 2024-12-19: `shanghai_rotterdam 824 -> 4819`, `rotterdam_shanghai 5424 -> 508`; **227 pages byte-identical** |
| same control re-run against the module now on disk vs the pre-patch backup (`scratch/wci/pv17/control.py`) | identical result: 231 parsed, 0 errors, 4 values, same 2 lanes |
| the corrected values against their own page | each lane's value read verbatim in the page's own sentence, at its own ordinal in its own list; the same assessment is printed identically by BOTH snapshots (`20241225092213`, `20250102151042`) |
| re-parse pass | 231 snapshots, 231 lacked a v17 parse, 231 re-parsed **from the local cache**, 141 complete, 0 network fetches, 29 s |
| stack vs the pv16 stage | staged 119 -> **120** shippable prints; gate census `{snapshots 231, fetch_failed 0, incomplete 90, numeric 3 -> 1, composite 0, contam 0, fused 0}`; stage diff = **exactly 1 added line** |
| display merge | stage 120, displayed 120 -> **121**; **CELL CORRECTIONS 0**, ROWS ADDED 1, md-tier (>= 2026-08-01) untouched; file diff = **exactly 1 added line** |
| displayed file | 121 rows, dates unique, **strictly increasing**, **all Thursdays**, 2021-05-20 .. 2026-09-24; **0 blank cells in the five core lanes** (composite + the 4 WCI lanes) - the 59 blanks in `rotterdam_shanghai` are pre-existing and unchanged (59 before, 59 after); **0 duplicate value-groups** |
| repo tests | `pytest tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py` = **34 passed** (Python312) |
| provenance | `data/provenance/manifest.json` rebuilt with the repo builder (never hand-edited): `indices_drewry_wci_historical` `row_count` **120 -> 121** (5 lines changed, 3 of them unrelated disk measurements) |

NOTE, measured while doing it: the repo's `conftest` **restores `data/provenance/
manifest.json` from git** at the end of a test run ("[conftest] restored 1 data
file(s)"). A regeneration performed BEFORE pytest is silently discarded, which is
how a run can believe it regenerated the manifest and ship a stale one. Regenerate
after the tests, then verify `row_count` on disk.

## Scoping the shape (measured)

A corpus scan over the 231 cached pages finds **exactly 4 pages carrying a
sentence with two `respectively` markers = 2 distinct prints**: 2024-12-19 (2
snapshots) and 2025-03-20 (2 snapshots). pv17 was trialled over all of them and
**only 2024-12-19 moved**: 2025-03-20 was already correct (`shanghai_rotterdam
2463`, `rotterdam_shanghai 484`, `shanghai_genoa 3286`) because its label and
value counts happen to align, so the pool branch caught it and pv17 never fired.

## Still open (measured from the checkpoint, not estimates)

* **1 numeric-gated print**: **2025-03-06** - the parser gives `genoa 845`; the
  page says *"rates from Shanghai to Genoa and Los Angeles to Shanghai remained
  stable"*, so Genoa has NO level that week and the print is **correctly
  withheld**. The 845 is New York->Rotterdam's level, one sentence earlier. This
  one is the publisher's, not our parse.
* **90 incomplete captures** by print year `2021:30 2022:19 2023:21 2024:11
  2025:9` (2026 has none left) - mostly the publisher printing no number.
* `upsert_wci_rows()` still dedupes by date only (a Thursday assertion would stop
  a dropped print from reappearing silently).

No vision tool in this session and this source is HTML (no PDF page to render);
the substitute is the same-document reconciliation above - every value located in
the page's own text and read verbatim, in the list and at the ordinal that the
publisher printed it.
