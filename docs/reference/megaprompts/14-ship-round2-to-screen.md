# 14 — PUT ROUND 2 ON SCREEN

**Read `00-GUARDRAILS.md` first.** This replaces the withdrawn 13D. Run order:
**`… 13C → 14 → 10 → 12`**.

---

## Why this prompt exists

Prompts 13, 13B and 13C acquired and cleaned seven new datasets. **None of them are
visible in the terminal.** `index.html` has zero references to China customs, Indonesia
coal, Argentina grain, world steel, minor bulks or fleet supply. This prompt's job is what
the user sees.

**When this prompt is done, the user opens the site and sees:**

| Tab | New |
|---|---|
| CARGO & TRADE FLOWS | 6 new modules: **Who Feeds China** (imports by origin) · **Indonesia Coal** · **Argentina Grain by Port** · **World Crude Steel** · **Minor Bulks** (7 flows) · **Guinea Bauxite** (monthly + producer ledger) |
| CARGO & TRADE FLOWS | **Port Hedland** updated from 2024-05 to 2026-07 with destination split |
| BROKER DESK | **Fleet Supply & Orderbook** module |
| BROKER DESK | Bunker series showing the **correct** port (Singapore/Rotterdam are currently swapped) |
| TRACKING | The **synthesized port-queue layer removed** — it's hash-generated, not observed |

### Work in this order — if time runs short, the top items are the ones that matter

1. **Part A** — stop showing wrong things (small, do first)
2. **Part B1** — load Hedland (the data is already found)
3. **Part C** — build the modules (the main deliverable)
4. **Part B2–B3** — China customs tonnage, Guinea 2025–26
5. **Part D** — commit, screenshots

### What NOT to do in this prompt
No new meta-tests, no report-generator work, no audit tooling beyond what's listed. The
existing gate (detector, full `pytest tests/ -q`, 12-tab regression) is enough. Every
item below either removes something false from the screen or puts something real on it.

---

## PART A — Stop showing wrong things

### A1. Remove the synthesized port queues from Tracking
`scripts/geospatial/build_geospatial_tracker.py:359-395` generates
`data/geospatial/port_lineups_active.csv`:
```python
status_hash = zlib.crc32(f"{imo}_{locode}".encode("utf-8")) % 100
if status_hash < 40: status = "Waiting at anchor"
```
Wait status, days waiting, position (a point on a circle around the port) and arrival time
(always 08:00) are all hash-generated. A dry-bulk Kamsarmax at Fujairah is shown
"carrying Murban Crude".
- Remove the fetch at `index.html:~39698` and every `DATA.portLineups` consumer,
  including the position fallback at `~40235`.
- Delete the synthesis block from the builder.
- In `tests/test_tracking_tu.py`, put `port_lineups_active` and `portLineups` back in the
  banned list, and correct the comment that called them authentic.

Real vessel positions (`liveFleetPositions`) and voyage history stay; they're observed.

### A2. Fix the Singapore/Rotterdam swap on four bunker series
Fearnpulse's own page nests **Singapore → 306 (380 CST), 307 (MGO)** and
**Rotterdam → 303 (380 CST), 304 (MGO)**. Our CSV says the reverse. A value check against
our independent Ship & Bunker history confirms the bundle: tsId 306 is within $7.8 of
Singapore IFO380 (303 is $24.9 off), 307 within $13.7 of Singapore MGO, 304 within $11.0
of Rotterdam MGO.
- Relabel in `fearnleys_benchmark_rates_continuous.csv` / `.json`, the registry, and
  anything in `index.html` that reads them.
- In `fearnpulse_titles.json`, the four entries are all titled "Spread MGO/380 CST":
  the spread pairs overwrote the single-series titles. Take a tsId's title from its own
  entry.

### A3. Zeros are turning into blanks
In the port-congestion loader 13C rewrote, `parseInt(x, 10) || null` and
`parseFloat(x) || null` convert a real **0** into `null`. Replace with
`(v === '' || v == null) ? null : Number(v)` for every field.

### A4. Manifest row counts are stale
Brazil is 557 in the manifest and 575 in the file; Guinea is 107 and 130. Every script that
writes a data file updates its manifest entry (`row_count`, `date_span`,
`last_fetched_utc`) in the same run. Fix these two and check the rest.

---

## PART B — Finish the data

### B1. Load Port Hedland 2024-06 → 2026-07 (already found)
13C found 26 monthly PDFs and parsed them into `scratch/hedland_live_parsed.json`, but
the CSV still ends at 2024-05. I fetched one to confirm it's real:
```
https://www.pilbaraports.com.au/pilbaraportsauthority/media/documents/port%20of%20port%20hedland/about%20the%20port%20of%20port%20hedland/port%20statistics%20and%20reports/cargo%20by%20destination/2026/cargo-stats-by-destination_origin_july2026.pdf
→ HTTP 200, contains total 44,224,980 t and China 37,856,534 t
```
Add the filename pattern
`cargo%20by%20destination/{yyyy}/cargo-stats-by-destination_origin_{month}{yyyy}.pdf`
to `scripts/scrapers/fetch_ppa_iron_ore.py` (the existing pipeline — don't write a second
parser). Re-fetch from the PDFs; `scratch/` isn't a source. Match the existing row schema:
3-decimal Mt, `destinations_t` dict, `provenance: live_ppa_archive`.

### B2. China customs in tonnes — the most valuable data still missing
`chinadata.live` (Target 5) gives **USD value only**. For a freight terminal we need
**tonnes by origin**: iron ore Australia vs Brazil (the C5 vs C3 split), bauxite from
Guinea, coal by origin, soybeans Brazil vs US.

**Primary source:** China Customs' own query platform, `http://stats.customs.gov.cn/`.
It returns **HTTP 412** to scripts: that's an anti-bot JavaScript challenge, not a block.
You have a headless browser (it's how you beat Pilbara). Open the site in it, run a query
(HS 2601 imports, by country, monthly), and in DevTools find the XHR that returns the
table. Replay that request with the browser's cookies. Fetch HS 2601, 2606, 2701, 1201,
2709 from 2018 onward.

If the challenge beats the headless browser, **stop and tell the operator**. He has
offered network-inspector tooling for exactly this, and it's worth it here. Don't fall
back to guessing.

**Secondary source,** for cross-checks or if GACC stays blocked: SMM publishes monthly
China-imports-by-origin articles, e.g.
`https://news.metal.com/newscontent/100986372-Update:-Chinas-bauxite-imports-fell-2-months-as-Guinea-in-rainy-season`
(fetches clean with `requests`). Cite each article per row with a verbatim quote.

Output: `data/commodities/china_customs_imports_tonnes.csv`
(`date, hs_code, commodity, origin, tonnes, value_usd, source_url, method`).
Keep the USD file; never blend the two into one line.

### B3. Guinea 2025–2026
- The Comtrade mirror ends 2024-12; Comtrade has no 2025 data yet (checked). **B2's China
  imports from Guinea continue the mirror monthly** — same measure, direct from China
  Customs. Append as `method: GACC China import from Guinea`.
- The ministry's national totals are reported in real articles. These URLs exist; 13's
  invented slugs did not:
  - `https://www.miningweekly.com/article/guineas-bauxite-exports-jump-25-to-183-million-tons-in-2025-on-chinese-demand-2026-01-26`
  - `https://www.miningweekly.com/article/guinea-first-half-bauxite-exports-hit-record-high-on-chinese-demand-2026-07-23`
  - `https://www.mining-technology.com/news/guinea-bauxite-exports-surge-q3/`

  Add quarterly/half-year national rows with verbatim quotes, `granularity: quarterly_national`.

### B4. Indonesia coal via the BPS API — key is live, endpoint verified (updated 2026-09-11)
The operator registered a key. It's stored as **GitHub repository secret `BPS_API_KEY`**,
and I verified it with a GitHub Actions run:
```
GET https://webapi.bps.go.id/v1/api/dataexim/?sumber=1&periode=1&jenishs=2&tahun={YYYY}
    &kodehs=27011100;27011210;27011290;27011900;27012000;27021000;27022000&key={BPS_API_KEY}
→ {"status":"OK","data":[{"tahun","bulan":"[07] Juli","kodehs":"[27011900] ...","pod":"TARAHAN",
   "ctr":"JAPAN","value":<USD>,"netweight":<kg>}, ...]}
```
Monthly, **by loading port (`pod`) × destination (`ctr`)**, value in USD and net weight in
**kg**. 2026 runs through **July** (28 ports, 24 destinations). `sumber=2` gives imports.
The 4-digit `kodehs=2701` returns "Data tidak tersedia" — use the 8-digit codes.

**Definition — this is why earlier figures disagreed:**

| | Jan 2026 | Apr 2026 |
|---|---|---|
| HS 2701 only (what BPS / Katadata call "coal exports") | 29.54 Mt | 28.67 Mt |
| + lignite 27021000 | 39.56 Mt | 37.33 Mt |

Both figures match the published numbers exactly. Lignite is 8–15 Mt/month of seaborne
thermal coal. **Chart the total, stacked by code group (bituminous / other coal /
lignite), and state that the official headline excludes lignite.**

Build `scripts/acquire/fetch_bps_exim.py`, reading `BPS_API_KEY` from the environment. Pull
**2018 → latest**, sum per month, and keep the port × destination detail (a "top loading
ports" and "top destinations" view in C2). It replaces the Comtrade + Katadata patchwork
for Indonesia; keep Comtrade as the cross-check.

**The key is a GitHub secret, so your local shell doesn't have it.** Either the operator
sets it locally (`setx BPS_API_KEY ...`), or you add a workflow
`.github/workflows/bps_monthly.yml` (monthly cron + `workflow_dispatch`) that runs the
fetcher with `secrets.BPS_API_KEY` and commits the CSV. **Do both:** the local run for now,
the workflow for ongoing refresh. Never print or commit the key.

---

## PART C — Put it on screen (the main deliverable)

### How Cargo modules are built here — follow the existing pattern
Each Cargo module is: a key in `data/cargo/cargo_frontend_summary.json` built by
`scripts/cargo/build_cargo_cache.py` → a renderer in `scripts/cargo/inject_cargo_js.py` →
markup in `scripts/cargo/patch_index_html.py`. Copy the structure of **"Brazilian Bulk
Seaborne Exports (MDIC ComexStat)"**: seasonal envelope (5-year min/max band + 5-year mean
+ current year + toggleable prior years), a YoY figure, a source + `data_through` badge,
and a one-line "why this matters for freight" note.

Every new module has: a tooltip on the title and each control, a provenance badge from the
manifest, and units in the axis label.

### C1. Who Feeds China (Cargo)
Monthly China imports by origin, one selector per commodity: iron ore (Australia /
Brazil / other → C5 vs C3 demand), bauxite (Guinea / Australia), coal (Indonesia /
Australia / Russia / Mongolia — mark Mongolia as overland, not seaborne), soybeans
(Brazil / US / Argentina — the seasonal flip). Stacked area plus an origin-share line.
Uses B2 tonnes. **If B2 isn't done, ship it on chinadata.live values, clearly labelled
"USD value — not tonnage"**, and swap in tonnes when B2 lands.

### C2. Indonesia Coal (Cargo)
Monthly exports 2020 → latest, seasonal envelope, YoY. Annotate **January 2022 — export
ban** on the chart. Destination split for months that have it (Jan and Apr 2026).
Freight note: the Indonesia → India/China Panamax/Supramax lanes.

### C3. Argentina Grain by Port (Cargo)
Monthly total by grain (corn, wheat, soybeans, soymeal, barley, sorghum, sunflower),
stacked. An up-river Paraná share line (draft-restricted → smaller parcels, Handy/Panamax
top-off). A port table for the latest month.

### C4. World Crude Steel (Cargo)
Monthly production: China vs rest of world, YoY bars. If you add a raw-materials-per-tonne
freight note, take the figures from worldsteel's own raw-materials fact sheet and cite
it. Otherwise leave the ratio out.

### C5. Minor Bulks (Cargo)
Small multiples, one per flow (sugar, urea, NPK, alumina, nickel ore, scrap, cement), each
with a seasonal envelope and its vessel-class tag (Handy / Supra / Ultra).

### C6. Guinea Bauxite (Cargo)
The monthly line (Comtrade mirror + B3 GACC continuation) with the `LIVE_MIRROR` badge;
the ministry annual and quarterly totals as bars; the 2025 per-company producer ledger
(SMB, Chalco, CBG…) as a table.

### C7. Port Hedland update (Cargo)
The existing Pilbara module shows the B1 data through 2026-07, with the destination
split (China share) for the latest month.

### C8. Fleet Supply & Orderbook (Broker Desk)
From `data/supply/fleet_orderbook_and_age_profile.csv`: one row per class — in-service
count and DWT, orderbook count and % of fleet, deliveries by year, age brackets, the 20+
year overage pool, scrubber %. Label it "as recorded by Signal Ocean" and note that the
status mapping is inferred. Sort by orderbook %.

### C9. Deep freight history (Broker Desk)
C3 runs from 1998, C5 and Newcastle coal from 1999 — Target 1's biggest win. Make sure the
Broker Desk freight charts expose it: a MAX range button that actually reaches 1998, and a
seasonal envelope for C3/C5.

---

## PART D — Deliver

1. The global gate — detector, whole `pytest tests/ -q`, 12-tab regression — green.
2. Commit the staged 13C work plus this prompt's work, staging only your own files.
   Leave out incidental test-run changes to `data/etf/snapshots/provenance_manifest.json`
   and similar.
3. **Boundary report = screenshots.** One screenshot of each new or changed module (C1–C9,
   A1's Tracking map), saved to `docs/screenshots/14/`. Then a short list: module · data
   source · `data_through` · row count (from the manifest). Anything skipped, with the
   reason and the attempt made.
4. If B2 needed operator help, say so at the top.
