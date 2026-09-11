# 13C — PROMPT 13B FOLLOW-UPS

**Read `00-GUARDRAILS.md` first.** Run this before Prompt 10. Run order:
**`13 → 13B → 13C → 10 → 12`**.

---

## Result of the 13B audit (2026-09-11, by execution)

13B was a large step forward. Most corrections are **real and verified**:

| § | Verified by |
|---|---|
| C1 Pilbara purge | 30 literal rows gone; Dampier June 2026 = 15.429 / 13.561 (3-decimal, real PDF parse) |
| C3 Fleet | Capesize 1,702 hulls / 12.4 y, by `orderBookStatusID` |
| C4 Comtrade | Türkiye scrap 1,837,205 t · India HS3102 447,746 t · Türkiye cement 1,894,618 t — exact live match; `select_total` raises on 0 or >1 |
| C5 Brazil seam | 2024-01 iron ore 26,908,945 t on both sides; `source`/`method` on every row |
| C6 Indonesia | constant fill gone; unverifiable May/Jul rows removed |
| C7 test teeth | I planted 7 mutations (incl. 2 new ones) — **all 7 caught** |
| C8 detector | Run against the *real* historical files: catches the original chart-transcribed Guinea/Brazil dicts, the Pilbara list and the Indonesia list |
| C10 USDA | loading / waiting_to_load / 4-yr averages match the xlsx cell-for-cell |

What follows is what the audit found wrong. D1 and D4 are the serious ones.

---

## D1 — S4A and S4B are swapped (and the registry calls it "verified")

### Evidence
Fearnpulse's own front-end bundle defines every series it shows. Fetch
`https://fearnpulse.com/fearnleys-weekly-report`, read the `/_next/static/chunks/*.js`
files it loads, and search for `tsId:`. The chunk that calls `/api/marketapi/TS` contains
entries like:
```js
iw,{title:"Transatlantic RV",tsId1:120132,tsId2:120133, ...}
iP,{title:"TCE Far East/Cont",tsId:10013, ...}
```
The component `iw` **averages the two series into one number**. Fearnpulse never labels
the legs separately. The original pre-Round-2 headers were
`Transatlantic RV (Panamax)` and `Transatlantic RV Round 2 (Panamax)`. The
"Delivery Cont" / "Delivery USG" wording was introduced in Target 1A without a source —
and my own 13B review accepted it. Both of us were wrong.

Fearnleys' weekly report text (`data/raw/fearnleys/reports_raw.json`) gives two anchors:

| Report text | 120132 | 120133 |
|---|---|---|
| "In late 2023, S4A peaked at over 40kpd" (reports 2025-10-01 / 10-08) | **max 41,214** (Sep 2023–Jan 2024) | max 20,675 |
| "Currently, we are at 35kpd" (report dated 2025-10-01) | **34,757** on 2025-10-01 | 15,132 |

**120132 is S4A.** 120133 is therefore S4B — by elimination, so `confidence: "inferred"`.
S4A (US Gulf → Skaw-Passero, grain/petcoke fronthaul) paying about double S4B is also the
normal market structure.

### Fix
1. Relabel: `tsid_120132` → S4A, `tsid_120133` → S4B. Update the registry, the CSV
   headers, the JSON catalog, and every consumer in `index.html`.
2. Each registry entry records the anchors above as its evidence: report date, the quote,
   and the matching value.
3. Update `test_taxonomy_coherence` / `test_taxonomy_mutation` so they enforce the
   corrected registry. Planting the old (swapped) labels must fail.

---

## D2 — Registry "evidence" is unsourced

### The defect
`data/reference/fearnleys_tsid_registry.json` marks tsIds 2, 3, 4, 6 `verified` with
`fearnpulse_name` values ("MEG/Singapore", "WAF/FEAST", "Cross Med") and evidence that
just restates the claim ("Fearnpulse publishes MEG/Singapore…"). **None of tsIds 1–4,
6–9, 11, 13 appear in the Fearnpulse bundle.** Those names came from the legacy harvester
header, not from Fearnpulse.

Also: the bundle wires **tsId 5 as `USD/JPY`**. Our CSV calls it
`Market Brief (Dirty Tanker) [worldscale]`. Its values (median 82.5, half-point steps,
dead since 2023-05-22) don't look like USD/JPY either. It stays unresolved — but it is
not evidenced as a tanker series.

### Fix
1. Write `scripts/reference/extract_fearnpulse_titles.py`. It fetches the page, discovers
   the chunk that contains `tsId:` (the hash in its filename changes — don't hardcode it),
   and emits `data/reference/fearnpulse_titles.json` = `{tsId: title, section, paired_with}`.
2. Registry `fearnpulse_name` must come **only** from that file. tsIds not in the bundle
   get `fearnpulse_name: null` and a `legacy_label` field holding the old header text.
3. `confidence` rules:
   - `verified` = title from the bundle **and** matches the taxonomy description, **or** a
     value anchor from report text (as in D1)
   - `inferred` = matches by elimination or by market structure
   - `unverified` = anything else

   Tanker codes on 1–4 and 6 become `unverified` unless you find value anchors.
   `reports_raw.json` mentions tanker routes with values; try the D1 method.
4. tsId 5: `code: null`, note the USD/JPY wiring and why the values contradict it.

---

## D3 — The taxonomy authority was edited

`data/reference/baltic_route_taxonomy.json` gained two entries in 13B: `BDI` and
`TD3/TD3C`. **`TD3/TD3C` is not a Baltic code.** That file is a scrape of the Baltic
page and is the authority the tests check against. Editing it so labels pass is F6.

### Fix
1. Remove both entries. The file must equal what the scraper produces from the Wayback
   snapshot. Add a test: re-parse the cached snapshot and assert equality.
2. BDI belongs in the file's existing **indices** section. Make the coherence test look
   codes up in routes **or** indices.
3. Model the TD3/TD3C straddle in the **registry**
   (`"code": "TD3C", "historical_code": "TD3", "straddle": true`), and have the test
   accept registry straddles. Note that TD3 (MEG→Japan) is not in the current taxonomy
   because the Baltic retired it.

---

## D4 — Real Guinea data deleted with a false justification

### The defect
13B purged 18 rows citing `https://www.guineamininginsights.com/data-hub`. The report
says that page is "a high-level portal landing page containing no historical data tables".

**False.** Fetched 2026-09-11, the page's plain HTML contains accessible chart data tables:
```
Guinea Bauxite Export Growth — Data table for Chart:
  Year Export Rate 2015 18 2016 20.9 2017 43 2018 54.15 2019 64.45 2020 82.4
  2021 85.66 2022 103 2023 127 2024 145 2025 183
Bauxite Export per Company (2025):
  CBG 17.4  Chalco 22.1  SMB 70  AGB2A/SDM 17  GAC 16  CBK 3.1  Other 37.4
Top Export Destinations: China 72.1  Singapore 10.3  UAE 6.8  Malaysia 4.1  Others 6.7
```
The rows were real. The likely cause: their `source_quote`s were not verbatim, the
citation check failed, and the rows were deleted instead of fixed. **That is F6.** When
a check fails on real data, fix the citation — never delete the data.

### Fix
1. Restore them from a fresh fetch. Parse the `Data table for Chart` blocks — don't retype
   the numbers above; they're here only so you can confirm your parse. Use
   `granularity: annual_national` / `annual_company` / `annual_destination_share` and
   verbatim `source_quote`s that pass `check_source_citations.py`.
2. Keep them off the monthly chart line (`granularity` filter already exists).
3. Ledger entry: what was deleted in 13B, why that was wrong, what was restored.

---

## D5 — Brazil drops 18 months silently

### The defect
Missing months in `brazil_comexstat_exports.csv`: iron ore 11 (2017-03, 2019-08,
2020-07, 2020-09, 2020-10, 2021-03, 2021-06, 2021-08, 2021-11, 2022-10, 2023-03), crude 5,
corn 2. The boundary report declares none of them.

Cause, checked for 2020-07 (Brazil, HS 260111, exports): Comtrade's total row
(`motCode 0, C00, partner2 0`) has **`netWgt: null`**, while mode rows exist
(`motCode 2100` sea: 32,067,074,900 kg; `motCode 2000`: 254,422,000 kg).
`select_total` correctly refuses. Then `fetch_brazil_comexstat_full.py:135`
`except → continue` drops the month without a trace.

### Fix
1. Never skip silently. Every failed or refused query becomes a row in a
   `_skipped_queries.json` sidecar (period, commodity, reason). The boundary report prints
   that list. This applies to **every** acquisition script that loops over periods.
2. For null-weight totals: first **test** whether, in months where the total is present,
   total = sum of the mode rows (within 0.1% over ≥20 months). If the identity holds, fill
   the gap months with the sum and set `method: "sum_of_transport_modes (total netWgt
   null in source)"`. If it doesn't hold, leave the month absent and declare it.
3. Check the `qty` field on the total row before concluding it is null.

---

## D6 — The report generator contains typed numbers

`scripts/verify/generate_boundary_report.py:341-342` hardcodes the "Before Audit" column:
"92 rows in Hedland (30 fabricated), 3 Dampier" — actually **42** Hedland and **253**
Dampier; "Guinea 120 rows" — actually **131**. Moving typed numbers from the report into
an f-string does not satisfy §C9. It just hides them.

Section 3's "CSV Date Span" shows `1985-01-04 -> 2026-09-10` for **all 34 series** —
it prints the file's date range, not each column's first/last non-null date.

### Fix
1. The generator takes `--base <commit>` and computes "before" values with
   `git show <base>:<file>`. No literal counts, dates or descriptions of change.
2. Per-series span = first and last non-null row of that column.
3. The generator runs the **full** gate itself (D7) and prints the counts. It does not
   accept results passed in.

---

## D7 — The full test suite has been red since Round 1

`python -m pytest tests/ -q` → **24 failed, 223 passed**. §0.5 requires it green before
every commit. Every ledger since Round 1 reports "gates pass", because only selected test
files were run. 13B's report lists 4 test files.

| Failures | Likely origin |
|---|---|
| `test_speed_budget.py` ×9, `test_tracking_tu.py` ×6, `test_tracking_wave1`, `test_tracking_rebuild`, `test_stale_guard`, `test_offshore_and_port_stress`, `test_fearnleys_pipeline` | index.html restructured in Round 1 (Prompts 03–07); Round 2 changed only 4 lines of index.html |
| `test_broker_desk_daily_routes.py` ×3 | Gibson 9 routes wired in Round 1 phase 4.2 with no KB entries / plain notes |
| `test_cargo_frontend.py` | **Prompt 13 Target 2 (`d0d121ac5`) changed `guinea_bauxite.provenance.status` from `LIVE_MIRROR` to `LIVE`** |

### Fix
1. Triage every failure into exactly one bucket, written in the ledger:
   - **Regression** → fix the code.
   - **Test obsolete** because a prompt deliberately changed the behaviour → update the
     test, citing the prompt and phase that made the change.
   Never delete a test. Never loosen an assertion without that citation.
2. **Guinea status:** the mirror series is `LIVE_MIRROR`; the ministry company rows are
   direct. The badge the operator asked for must come back. The test's
   `direct_source_status == "UNAVAILABLE"` is now outdated — make it `PARTIAL`
   (what the ministry covers, and since when), computed, not typed.
3. Gibson routes: write the KB entries and plain-language notes the test expects.
4. From now on the gate is the **full** suite plus the 12-tab regression, run by the
   generator. A subset is not the gate.

---

## D8 — Citation checker skips rows without a quote

`check_source_citations.py:105` skips any row lacking `source_quote`. So rows that carry
only a `source_url` — Argentina's MAGyP rows, for example — are never checked.

### Fix
For every non-API `source_url`: fetch it (cached), require HTTP 200, and require the row's
number to appear in the page (locale variants). The quote check applies when a quote
exists. For multi-value rows (MAGyP has one total per month), check the total.

---

## D9 — Absences declared without an attempt

- **Hedland after 2024-05:** 13B §C1.4 asked you to open the Port Hedland statistics
  page in a real browser and read the PDF `href`s from DevTools (rung 7). The ledger shows
  no attempt, just "honestly ends at 2024-05-01". **An absence is only honest after the
  ladder has been worked.** Do the DevTools step. Record the filenames you find and fetch
  them with `requests` — the media path isn't WAF-gated.
- **GMI monthly releases:** 13B §C2.2 asked for enumeration of `news-insights-{n}`. I
  sampled every 3rd page from 60 to 99 and found no further ministry releases, so they may
  be sparse — but sample-of-14 is my evidence, not yours. Enumerate every `n` from 1 to the
  latest, match release headlines/text (e.g. `million tonnes of bauxite`), and report the
  count found. Zero is an acceptable answer once it's measured.

**New rule (GUARDRAILS):** an `UNAVAILABLE` or "left absent" declaration must name the
rungs attempted and their results. No attempt log, no absence.

---

## D10 — Small

1. `scripts/bunkers/build_bunker_cache.py:603` now sets the modelled curve's `as_of` to
   `now()`. `as_of` means the data date, not the run date. Use the date of the latest
   BunkerIndex observation the curve is built on. (A fixed literal was F5; `now()` is the
   wrong meaning.)
2. The manifest's minor-bulks `date_span` is `202201 -> 202607`. Use ISO dates like every
   other series.

---

## Gate and boundary

The full gate — `pytest tests/ -q` all green, the detector, `check_source_citations.py`,
and the 12-tab regression — is run **by `generate_boundary_report.py --base 637bc180a`**
(the last 13B commit).
Paste its output. Every absence lists the rungs tried.
