# Drewry WCI - pv15: the ORIGIN-INFERENCE lane recovery (2026-02-12)

Ran offline: `--fetch --refresh` re-parsed the 230 cached Wayback captures, no
network buy, no API spend. Branch only. Displayed rows **117 -> 118**.

## The shape that was dropped

`2026-02-12` page (cached capture `20260217042251.html`), verbatim:

> Spot rates from Shanghai to major US destinations declined slightly due to low
> cargo volume, with spot rates to Los Angeles and New York falling 1% to $2,214
> and $2,800 per 40ft container, respectively.

Measured on that sentence: `ROUTE_PATTERNS` matches NOTHING in it (it names no
`X to Y` port pair - the "destination" of its opening lane is the lowercase group
phrase "major US destinations"), and `label_rx` matches NOTHING either. So the
sentence never entered the lane logic at all and **both printed levels were
dropped** while the other three lanes parsed fine (composite 1,933 / Rotterdam
2,127 / Genoa 2,965). The print then failed the `complete` gate and was withheld
as one of the 91 incomplete captures. The values were ON the page the whole time.

## The rule (pv15, additive and monotone)

An ORIGIN printed in the sentence's OPENING lane now seeds the destination list.
The origin comes from the module's own `elided_rx` ("rates **from Shanghai**"),
the destinations from `elided_rx` + `cont_rx`; the pass runs ONLY when the
sentence contains "respectively", names no route, and `ROUTE_PATTERNS` matches
nothing in it; it fills EMPTY columns only, and only when the number of printed
levels equals the number of destinations. It cannot move or overwrite a value
another rule found. `PARSER_VERSION` 14 -> 15.

## Controls (each measured separately)

| control | measured |
|---|---|
| read-only trial over all cached captures (`scratch/wci/pv15c/trial.py`) | 230 pages parsed, **0 parser errors**, value differences **2** - both on `20260217042251.html`, both `None -> value` |
| through the real checkpoint, pv14 vs pv15 per snapshot | 230 snapshots in both; **MOVED 1**; `(1933, 2127, 2965, None, None, None) -> (1933, 2127, 2965, 2214, 2800, None)`. No value changed, no page_date changed |
| stage re-stack vs the pre-bump stage | **116 -> 117 prints**, incomplete **91 -> 90**, diff = exactly ONE added line |
| display merge | **CELL CORRECTIONS 0**, ROWS ADDED 1, md-tier (>= 2026-08-01) untouched, diff = exactly ONE added line |
| displayed file | dates unique, strictly increasing, **all Thursdays**, 2021-05-20 .. 2026-09-24; 0 blank core cells; 0 rows with a duplicate value-group |
| the new row against its own page | all five values verbatim as `$X,XXX`; page prints `assessment for Thursday, 12 Feb 2026`; page headline `$1,933`; the lane sentence read by eye gives **LA $2,214 / NY $2,800 in that order**, which is the order the parser assigns |
| repo tests | `pytest tests/test_loader_contracts.py tests/test_question_routing_and_grounding.py` = **34 passed** |

No vision tool in this session; the substitute is the same-document
reconciliation above (page text located, every value matched verbatim, the
attribution sentence quoted and read).

## Still open, freshly measured from the checkpoint

Incomplete captures: **90**, by print year `2021:30 2022:19 2023:21 2024:11
2025:9` - **2026 now has none**. Missing-lane histogram: `shanghai_ny` alone 15,
`rotterdam+genoa` 14, `shanghai_la` alone 12, all four 11, `genoa` alone 9,
`rotterdam` alone 7, rest 1-5.

NOTE: the previous verdict's histogram summed to 97 against its own census of
91; the numbers printed here are recomputed from `checkpoint.jsonl`, all 90 with
a page_date.

Also open (unchanged): the 4 numeric-gated prints, the 1 never-fetched capture
(`20251006233302`, HTTP 404), the 2021-07-01 "k labels, 2k numbers" print, and
`upsert_wci_rows()`'s date-only dedupe (a Thursday assertion would stop a
dropped print from ever reappearing silently).

## Display path, probed headlessly (not asserted)

`python312 -m http.server 8777` + Playwright/Chromium on
`index.html?test=1` (the app's own test bypass), then driving the app's OWN
functions - no re-implementation:

* `window.loadSignalsData()` fetches `data/indices/drewry_wci_historical.csv`
  -> **HTTP 200**, and `DATA.drewry_wci` holds **118** rows,
  `2021-05-20 .. 2026-09-24`;
* the app's own parsed row for the print:
  `{dateStr: '2026-02-12', composite: 1933, rm: 2127, gn: 2965, la: 2214, ny: 2800}`;
* clicking the real `Cargo & Trade Flows` tab builds **32 canvases** with no
  page errors. Screenshots: `scratch/wci/pv15d/display_probe_indices.png`.

**FINDING while probing, measured and worth knowing:** nothing in `index.html`
READS `DATA.drewry_wci` / `DATA.wciTracker` - the only mentions are the
declaration (`wciTracker: []`), the fetch, and
`window.renderDrewryChart = renderContainerIndexChart`, which plots **CLCI and
FBX**, never the WCI lanes (its datasets are CLCI/FBX; the WCI canvas
`wciChart` is only a fallback target that does not exist in the DOM). So this
series reaches the USER through **`scripts/generate_brief.py`** section 10a (it
reads the file's LAST row) and through `gap_matrix` / `audit_manifest_staleness`
/ `build_provenance_manifest` - not through a chart. Adding a row is therefore
correct and useful, but it is not pixel-visible in the current UI.

No vision tool in this session: the look-substitute is the headless drive above
plus the verbatim page reconciliation in the controls table.
