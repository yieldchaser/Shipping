# 13B — PROMPT 13 CORRECTIONS

**Read `00-GUARDRAILS.md` first. It governs this prompt.** Run this prompt **before**
Prompt 10. Run order is now: **`13B → 10 → 12`**.

---

## Why this prompt exists

Prompt 13 was audited on 2026-09-11 by **executing** every source it cited, not by
reading its report. Most of the work is real and good. But the audit found fabricated
rows, invented citations, a parser bug that corrupted three trade series, a fleet table
built on scrapped ships, a coherence test that catches nothing, and a detector that
passes because 33 whole files were exempted from it.

The boundary report also contained a **34-row tsId table that does not exist in the
repo**. It said tsIds 10, 12 and 15–27 are "ALIVE, 1,079 points" with labels like C2,
Brent and bunker prices. Those tsIds return **empty** from Fearnpulse. It said tsIds
1–9 are ALIVE through 2026; eight of them died on 2023-05-22. Your own ledger had the
correct numbers. The report was written freehand instead of copied from the ledger.
**§C9 makes that structurally impossible from now on.**

### What passed the audit — do not touch these

| Item | Evidence |
|---|---|
| Fearnpulse depth backfill | C3 7,085 rows from 1998-05-06, C5 6,877, Panamax 2,169 each — execution-matched |
| `bdiy_historical.csv` untouched | `git diff 3820c1a47 HEAD` on it is empty |
| DORMANT marking | 9 series DORMANT in the catalog JSON |
| Pre-1980 sentinel rejected | tsId 11 starts 2017-07-10 in the CSV |
| TD3/TD3C straddle flagged | tsId 1 header says `TD3/TD3C transition` |
| S4B / S4A corrected | tsIds 120132 / 120133 |
| tsIds 7, 8, 9, 11, 13 hedged | Header text says `Unverified` / `mislabelled` |
| **USDA GTR Table 19** | Live xlsx, parsed cell-for-cell correctly (Gulf 2026-08-13: 9 / 29 / 31) |
| **worldsteel** | 31 real press-release pages cached; June 2026 page says 155.7 Mt |
| Argentina MAGyP | Real per-month `.php` sources with per-row URLs |
| Guinea Comtrade mirror | 2023-12 = 8,188,600 t, exact match to Comtrade |
| Guinea Mining Insights Jan 2026 | Page contains 20.26 Mt and 6.57 Mt |
| Katadata Jan / Apr 2026 | Pages contain 29,53 and 28,67 |
| BPS key via env var | Not registered by the agent; operator handoff documented |

Everything below is a defect. Fix all of it. Work straight through; stop only on a
§0.5 HARD STOP.

---

## C1 — Pilbara: 30 fabricated rows

### The defect
`scripts/acquire/fetch_pilbara_ports.py` contains `MONTHLY_UPDATES`, a **literal list
of 30 dated records** (27 Port Hedland 2024-06 → 2026-08, 3 Dampier 2026-06 → 2026-08).
Nothing is fetched. The one `requests.get` only logs the Incapsula status. Each row is
tagged `provenance: "live_ppa_archive"` — which is false.

Tells:
- Real PPA rows carry 3-decimal values and per-destination tonnage
  (`46.477`, `{"China": 39720902.0, ...}`). The literal rows are 1-decimal with no
  destinations.
- **August 2026 is a copy of July 2026** on both ports (Hedland 45.0 / 44.2, Dampier
  14.7 / 13.5), each with `mom_pct 0.0`.
- The FY2027 Dampier PDFs that would carry July/August 2026 **do not exist yet**
  (HTTP 404 on 2026-09-11). Those rows have no possible source.

No real rows were overwritten — the literal dates do not overlap the real ones. Keep
it that way.

### The fix
1. Delete `MONTHLY_UPDATES` and everything that merges it. Remove the 30 rows from
   `data/commodities/australia_ppa_iron_ore.csv`. That is removing **your own**
   fabricated rows, not F6.
2. The repo already has the real pipeline: **`scripts/scrapers/fetch_ppa_iron_ore.py`**
   (Wayback CDX for Hedland PDFs, direct HTTPS for Dampier PDFs). Use it. Do not write
   a second one.
3. **Dampier June 2026 is available.** Executed 2026-09-11:
   ```
   GET https://www.pilbaraports.com.au/pilbaraportsauthority/media/documents/port%20of%20dampier/about%20the%20port%20of%20dampier/port%20statistics/2026/klein-stats-july-2025-to-june-2026-ytd.pdf
   → HTTP 200, 132,507 bytes, %PDF
   ```
   Add it to `DAMPIER_SOURCES` and parse it with the existing `parse_dampier_ytd_pdf`.
4. **Hedland after 2024-05.** The `/pilbaraportsauthority/media/documents/` path is
   **not** behind Incapsula — bad filenames return a genuine 404 page, not a challenge.
   Only the HTML pages are gated. So the PDFs are reachable once you know their
   filenames. Work §0.66: open the Port Hedland port-statistics page in a real browser,
   read the PDF `href`s from DevTools (rung 7), then fetch those PDFs with `requests`.
   Do **not** transcribe numbers from the screen — only filenames.
5. If a month cannot be sourced, it is absent. Hedland may honestly end at 2024-05.
   The manifest then says so, and Prompt 10's staleness state will mark it.
6. Fix the manifest: `commodities_australia_ppa_dampier_throughput.notes` currently
   says "through August 2026 (14.7 Mt total throughput, +3% YoY)". Any number in
   `notes` must be computed from the data, never typed.

### Acceptance
- `grep -n "MONTHLY_UPDATES" scripts/` → no matches
- Every PPA row has a `provenance` tag whose source file or URL is recorded in the ledger
- No two consecutive months are identical on both total and iron-ore columns
- `data_through` for each port equals the latest month in the file

---

## C2 — Guinea: six rows cite pages that do not exist

### The defect
Six "Trade Press Mirror" rows in `data/commodities/guinea_bauxite_exports.csv`
(2024-03-31, 2025-03-31, 2025-06-30, 2025-09-30, 2026-03-31, 2026-06-30) cite:

| Cited URL | 2026-09-11 result |
|---|---|
| `miningweekly.com/article/guinea-bauxite-exports-hit-record-1148m-tons-in-first-half-of-2026` | **404** |
| `mysteel.net/news/guinea-bauxite-export-q3-2025` | **404** |
| `mining-technology.com/news/guinea-bauxite-exports-q1-2025/` | **403** |

The Q1 **2024** row cites the Q1 **2025** URL. The slugs look constructed, not copied.
A citation you did not open is an F3 violation.

### The fix
1. For each of the six rows: find a **live** page whose text contains the number, and
   have the script **fetch it and assert the number is present** (§C8.4 does this for
   the whole repo). If no such page exists, delete the row.
2. **The bigger win is sitting in front of you.** Guinea Mining Insights republishes the
   Ministry's release **every month** (`news-insights-{n}`). You parsed only #82.
   Enumerate the range, find every monthly ministry release, and build the real monthly
   **per-company tonnage + vessel-count** series. That is the direct source, and it
   makes the quarterly trade-press rows unnecessary.
3. The Comtrade mirror ends 2024-12. Query 2025-01 onward. Where Comtrade has not
   published, the series ends — say so in the manifest.
4. Rows of different granularity (monthly company rows, quarterly national rows, annual
   data-hub rows) must not feed one chart line. Keep a `granularity` column and make
   `build_cargo_cache.py` filter on it explicitly.

### Acceptance
- Every non-API `source_url` in the file passes §C8.4
- Monthly ministry rows exist for every month GMI has published
- `granularity` column present; the flagship chart reads exactly one granularity

---

## C3 — Fleet supply: scrapped ships counted as active

### The defect
`scripts/acquire/fetch_fleet_supply.py` splits "active" from "orderbook" by
`yearBuilt < 2026`. The Signal Ocean records carry **`orderBookStatusID`**, which the
script ignores. Distribution in `data/geospatial/signal_vessels_dry_bulk.json`:

| `orderBookStatusID` | n | median `yearBuilt` | Inferred meaning |
|---|---|---|---|
| 7 | 26,181 | 2011 | in service |
| 8 | 5,425 | 1984 | **scrapped / dead** |
| 1 | 444 | 2027 | on order |
| 2 | 882 | 2027 | on order / under construction |
| 4 | 521 | 2017 | unresolved |
| 5 | 64 | 2027 | unresolved |
| 6 | 42 | 2026 | unresolved |

Your Capesize "active fleet" of 2,256 hulls at avg age 17.4 y includes **543 scrapped
ships**. Status-7 Capesizes only: **1,702 hulls, avg age 12.4 y** — which is realistic.
Every class in the table is wrong the same way.

Second defect: the UNCTAD figures (`~116,000 vessels`, `2.50 billion DWT`, `69.2%`,
`91.4%`, `80.2%`) are **literals** in the script (lines 7–10, 183) written into
`merchant_fleet_summary.json` as if fetched. Both UNCTAD URLs returned the same
43,708-byte JavaScript app shell. That shell contains none of those numbers.

### The fix
1. Classify by `orderBookStatusID`: 7 → fleet; 1, 2 → orderbook; 8 → excluded.
   4, 5, 6 → report in their own `status_unresolved` bucket, excluded from both.
2. The status mapping is **inferred**, not documented by Signal Ocean. Write it to
   `data/reference/signal_orderbook_status_map.json` with the evidence table above and
   `"confidence": "inferred from yearBuilt distribution"`. Label the UI accordingly.
3. Call it "orderbook **as recorded by Signal Ocean**", not "confirmed orderbook". Their
   coverage of unbuilt hulls is unknown.
4. Remove the UNCTAD literals. If you want those benchmarks, fetch a real UNCTAD
   document (e.g. the *Review of Maritime Transport* PDF), extract the figures, and
   assert each appears in the fetched text. Otherwise leave them out.

### Acceptance
- Capesize fleet count and average age are recomputed from status 7 only
- No number in `merchant_fleet_summary.json` exists as a literal in the script
- `grep -nE "116,?000|2\.50 billion" scripts/acquire/fetch_fleet_supply.py` → no matches

---

## C4 — Comtrade row-selection bug (corrupts minor bulks)

### The defect
`scripts/acquire/fetch_minor_bulks.py:165-166`:
```python
mot_zero = [x for x in data if x.get("motCode") == 0]
rec = mot_zero[0] if mot_zero else data[0]
```
Comtrade returns **many rows** per query: one per customs regime (`customsCode`) and
secondary partner (`partner2Code`). The total is the row with **`motCode == 0` AND
`customsCode == "C00"` AND `partner2Code == 0`**. The script takes whichever
`motCode == 0` row comes first.

Executed 2026-09-11, period 202403:

| Series | Repo value | True Comtrade total | Error |
|---|---|---|---|
| Türkiye scrap imports, HS 7204 | 6,944 t | 1,837,205 t | the row the script took is `partner2Code = 422` — one slice of 165 rows |
| India nitrogenous fert imports, HS 3102 | 2.40 t | 447,746 t | |
| Türkiye cement/clinker exports, HS 2523 | 0.01 t ($4) | 1,894,618 t | |
| China alumina imports, HS 2818 | 309,109 t | 309,109 t | correct — Comtrade returned 1 row |
| Philippines nickel ore exports, HS 2604 | 2,298,945 t | 2,298,945 t | correct — 1 row |

It is right only when Comtrade happens to return a single row. **The same pattern is in
`fetch_indonesia_coal.py:92-103` and `fetch_brazil_comexstat_full.py:120-129`.** They
were correct on the months I sampled, but by luck, not by design.

### The fix
1. Create **one** shared client, `scripts/acquire/comtrade_client.py`, with
   `select_total(rows)` that returns the unique row matching all three conditions and
   **raises** if there are zero or more than one. No fallback to `data[0]`. That is F2.
2. Refactor minor bulks, Indonesia, Brazil and Guinea to use it.
3. Cache the **raw** Comtrade JSON per query so the test below can re-derive values.
4. Re-pull every Comtrade series.

### Acceptance
- `tests/test_comtrade_selection.py`: for every cached raw response, the value in the
  CSV equals `select_total(raw)`
- Re-confirm the three corrupted values above against a live call; do not hardcode them
- Plausibility floor: no minor-bulk monthly row below 1,000 t unless `select_total`
  returned that value. If one does, it is reported, not deleted.

---

## C5 — Brazil: two different bases spliced into one line

### The defect
`data/commodities/brazil_comexstat_exports.csv` joins 2017–2023 rows from **Comtrade
at HS 4-digit** onto 2024–2026 rows from **ComexStat at NCM 8-digit**. They measure
different things, and every row is labelled with the NCM code.

Executed for 2024-01, Brazil iron ore exports:

| Query | Tonnes |
|---|---|
| Comtrade HS 2601 (what the backfill used) | 29,264,442 |
| Comtrade HS 260111 | **26,908,947** |
| ComexStat NCM 26011100 (existing repo row) | **26,908,945** |
| Comtrade HS 260112 (pellets) | 2,355,494 |

The backfill includes pellets; the ComexStat rows do not. That inflates 2017–2023 by
about 8% and puts a **false step-down at 2024-01**. Sugar has the same risk: HS 1701
includes refined sugar; NCM 17011300 + 17011400 is raw only.

Also: the file has **no `source` or `method` column**. After the backfill, nobody can
tell which rows came from where.

### The fix
1. Re-pull the backfill at the HS 6-digit code that matches each NCM:
   iron ore `260111` · soybeans `120110` + `120190` · raw sugar `170113` + `170114` ·
   crude `270900` · corn `100590`. Where the NCM is narrower than any HS6 (crude
   `27090010`, corn `10059010`), state the residual in the manifest.
2. Add `source` and `method` columns to every row.
3. **Seam test**: for every month where both sources have data (2024-01 onward), pull
   Comtrade too and compare. Within ±0.5%, the splice is valid. Outside, it is a HARD
   STOP finding — report it.

### Acceptance
- 2024-01 iron ore Comtrade HS 260111 matches ComexStat within 0.5%
- `source` and `method` columns present and non-empty on all rows
- No commodity shows a step change at 2024-01 larger than its own month-on-month σ

---

## C6 — Indonesia: an invented annotation on 72 rows

### The defect
72 of 76 rows in `indonesia_coal_exports_monthly.csv` carry the constant string
**`"India (~25-28%)"`** in `top_destination_1`, written by
`fetch_indonesia_coal.py:217`. Those rows come from a Comtrade query with
`partnerCode=0` — which returns **no partner breakdown at all**. The range is invented.

The May 2026 and July 2026 rows cite `https://www.bps.go.id/id/publication` — a
generic index page, not the release — with an **English** "source_quote" for an
Indonesian-language publisher. That is not a verbatim quote.

**Do not touch January 2022 (10.92 Mt).** It is real — Indonesia banned coal exports
that month. Annotate it; never smooth it.

### The fix
1. Either fetch the real partner split (Comtrade `partnerCode` = all, per month, via
   `select_total` per partner) or leave the destination columns blank. No constants.
2. May / July 2026: find the specific release page (Katadata published Jan and Apr —
   look for May and Jul) and assert the number is in the fetched text. Otherwise delete.
3. `source_quote` must be a **verbatim** substring of the fetched page, in its original
   language. §C8.4 enforces this.

### Acceptance
- No destination value contains `~`
- Every `source_quote` is a substring of its fetched `source_url` page

---

## C7 — The taxonomy coherence test has no teeth

### The defect
I planted five wrong codes into a copy of the CSV and ran `test_taxonomy_coherence`.
**All five passed:**

| Planted error | Result |
|---|---|
| `C3` → `C5` on tsid_10001 | passed |
| `P2A_82` → `P3A_82` on tsid_10011 | passed |
| `P4_82` → `P6_82` (the exact error this project already made once) | passed |
| bogus code `C99` | passed |
| `S1C` → `S1B` on tsid_120129 | passed |

Why: the generic check only asserts the **vessel-class word** is in the header. Any
Panamax code on any Panamax header passes. Unknown codes are skipped
(`if code in routes`). The only real checks are hardcoded to the two errors already
caught. That is testing for yesterday's bug.

### The fix
1. Create **`data/reference/fearnleys_tsid_registry.json`** — one entry per tsId:
   ```json
   "10013": {
     "code": "P4_82",
     "fearnpulse_name": "<the series name as Fearnpulse publishes it>",
     "taxonomy_description": "<copied from baltic_route_taxonomy.json>",
     "evidence": "<why these two describe the same route>",
     "confidence": "verified | inferred | unverified"
   }
   ```
   Tanker codes on tsIds 2, 3, 4, 6 (`TD2`, `TD15`, `TD20`, `TD19`) need the same
   evidence. If you cannot evidence one, set `"code": null` and hedge the header (§0.5
   HARD STOP 5).
2. Rewrite `test_taxonomy_coherence` to assert, for every header:
   - its code **equals** the registry code for its tsId
   - every code in parentheses **exists** in the taxonomy — unknown codes fail
   - the vessel class matches
3. Add **`tests/test_taxonomy_mutation.py`**: apply each of the five mutations above to
   an in-memory copy of the headers and assert that **each one fails** the coherence
   check. A test that cannot fail is not a test.

### Acceptance
- `pytest tests/test_taxonomy_mutation.py` → 5 passed (i.e. 5 mutations caught)

---

## C8 — The detector passed by exempting 33 files

### The defect
Gate 1 went from 56 violations to 0 through `scripts/verify/fabrication_allowlist.txt`,
which exempts **33 whole scripts** as "Legacy", including
`scripts/bunkers/build_bunker_cache.py` and `scripts/generate_brief.py`. Any new
violation added to those files is now invisible.

The detector also has two blind spots that let C1 and C6 through:
- **F1 catches dicts keyed by year or month only.** A list of `{"date": ..., value}`
  records — exactly the Pilbara shape — is not detected.
- **F3 is satisfied by any network call in the file.** One logging-only `requests.get`
  exempts a file full of literal data.

### The fix
1. **Allowlist entries become `path:line:rule`, never a bare path.** Re-run the detector
   on `3820c1a47` to get the original 56, and for each one either fix it or allowlist
   that single line with a reason. A new violation in the same file must still fail.
2. **F1b** — flag any list or tuple literal holding ≥3 dicts that each contain a
   date-like string and ≥2 numeric values.
3. **F3b** — a network call does not exempt a file that also contains an F1/F1b table.
4. **`scripts/verify/check_source_citations.py`** (new): for every data file with
   row-level `source_url` + `source_quote`, fetch each distinct non-API URL (cache the
   result), and assert HTTP 200 **and** that `source_quote` is a substring of the page
   text. Also assert the row's numeric value appears in the text, allowing locale
   variants (`29.53` / `29,53`). Add it to the global gate.
5. **Detector mutation test**: copy `fetch_pilbara_ports.py` from commit `845095005`
   into a temp directory, run the detector on it, and assert it **fails**. Same for the
   Indonesia constant-fill shape.

### Acceptance
- No bare-path lines in the allowlist
- Detector exits non-zero on the Pilbara and Indonesia mutation fixtures
- `check_source_citations.py` exits 0 on the corrected repo

---

## C9 — The boundary report must be generated, not written

### The defect
The Prompt 13 boundary report's tsId table was invented. Its Target 4 span says
"1998-01-01"; your own ledger says 1995-01-04. The ledger was right both times.

### The fix
Create **`scripts/verify/generate_boundary_report.py`**. It reads the manifest, the
data files, the ledger and the gate output, and prints the boundary report: per-target
before/after rows, `data_through`, and gate results. It computes every number.

**New rule (added to GUARDRAILS §0.5):** the boundary report you give the operator is
the verbatim output of that script, plus prose. **Any number you type by hand into the
report is a violation.** If you want to show something the script does not compute,
extend the script.

---

## C10 — Small fixes

1. **worldsteel**: `fetch_world_steel_production.py:236-242` hardcodes a
   `june_2026_benchmark` block and says `"Exact match to Prompt 13 specification"`.
   Checking a parse against a number in the prompt is circular — the prompt could be
   wrong (§0.65). Compute the block from the parsed DataFrame; delete the prompt reference.
2. **USDA**: the source has **Loading** and **Waiting to load** columns for Gulf and PNW,
   and 4-year averages. You dropped them. *Waiting to load* is the congestion signal —
   the whole reason this series is in a freight terminal. Add them. Also, the ledger says
   "Gulf, PNW and Vancouver"; Vancouver is `n/a` in the source.
3. **Guinea column naming**: `import_volume_mt` holds tonnes (8,188,600), not Mt.
   Rename to `import_volume_t`, or divide. Update every reader.

---

## Global gate for this prompt

Before every commit, everything in §0.5, plus:
```bash
python scripts/verify/check_source_citations.py   # new, must exit 0
python -m pytest tests/test_taxonomy_mutation.py tests/test_comtrade_selection.py -q
```

## Boundary

When C1–C10 are done, print the output of `generate_boundary_report.py` and stop.
Hedged items, deletions, and anything left absent go in the report — absence is a
correct answer; invention is not.
