# PROJECT STATE — handoff snapshot

**Last updated: 2026-09-11 (after the Prompt 13B audit).** Update this file at every prompt boundary.

---

## Where we are

| | |
|---|---|
| Round 1 (Prompts 01–09) | **Shipped**, main checkout HEAD `3820c1a47` |
| Round 2 running order | **`13 → 13B → 13C → 14 → 10 → 12`** · `11` ⛔ superseded · `13D` withdrawn |
| Prompt 13 | ✅ Done — agent HEAD `c76890d12` |
| Prompt 13B | ✅ Done — agent HEAD `637bc180a`. Audited: most corrections real (see 13C header) |
| Prompt 13C | ✅ Done — audited |
| 13D | **Withdrawn** — mostly audit hygiene; its on-screen items folded into 14 |
| **Prompt 14** | ✅ **Done** — Round 2 live on screen (C1–C9, A1). 249 tests green (100%). |
| Next up | **Prompt 10** — data currency and truth in labelling |

## The honest progress check (2026-09-11)
Round 2 so far (13, 13B, 13C) acquired and cleaned 7 datasets and 28 years of freight
history — **and put none of it on screen.** `index.html` references zero of: China
customs, Indonesia coal, Argentina grain, world steel, minor bulks, fleet supply. 13B/13C
mostly fixed errors that 13 introduced. **From now on, every prompt must name what the user
will see when it finishes.**

## Folded into Prompt 14
Synthesized port lineups (CRC32) removed from Tracking · bunker 303/304/306/307
Singapore↔Rotterdam swap · zero→null loader bug · stale manifest counts · Hedland ingest.
**Dropped as not worth a run:** report-generator literals, two tooltip assertions, tests
writing tracked files. Revisit only if they bite.

## Operator asks outstanding
- **Network inspector for `stats.customs.gov.cn`** (HTTP 412 anti-bot) — only if the
  agent's headless browser fails. Unlocks China imports in **tonnes** by origin.
- **BPS API key** — register free at `webapi.bps.go.id`, set `BPS_API_KEY`.

⚠ **Nothing from Round 1 or Round 2 is pushed.** Main checkout is ~32 commits ahead of
`origin/main`. **Do not push until 13C passes the full suite** (`pytest tests/ -q` is at
24 failures; S4A/S4B are swapped on screen).

## 13B audit — defects carried into 13C
| § | Defect |
|---|---|
| D1 | **120132 is S4A, 120133 is S4B** — repo has them swapped. Evidence: Fearnleys report text (S4A late-2023 peak >40k ↔ 120132 max 41,214; "35kpd" on 2025-10-01 ↔ 34,757) |
| D2 | Registry `fearnpulse_name` unsourced for tsIds 1–9,11,13; tsId 5 is wired as USD/JPY in Fearnpulse's bundle |
| D3 | `BDI` and a made-up `TD3/TD3C` code added to the taxonomy authority file |
| D4 | 18 real Guinea data-hub rows deleted as "page has no data" — page has plain-HTML chart tables |
| D5 | Brazil: 18 months silently dropped (Comtrade total `netWgt: null`, `except → continue`) |
| D6 | Report generator hand-types the "before" column (wrong: "92 Hedland" vs real 42); per-series spans wrong |
| D7 | Full `pytest tests/ -q` = 24 failed since Round 1; Guinea lost `LIVE_MIRROR` in 13 Target 2 |
| D8 | Citation checker skips URL-only rows (MAGyP unchecked) |
| D9 | Hedland DevTools step and GMI enumeration never attempted, but absence declared |

---

## Prompt 13 audit — 2026-09-11, by execution

### Passed
Fearnpulse depth (C3 7,085 / C5 6,877 / Panamax 2,169) · `bdiy_historical.csv` untouched ·
9 series DORMANT · pre-1980 sentinel dropped · TD3/TD3C flagged · S1B removed (but S4A/S4B then swapped — see D1) ·
tsIds 7/8/9/11/13 hedged · **USDA GTR xlsx** (parsed cell-for-cell correctly) ·
**worldsteel** (31 real pages) · Argentina MAGyP · Guinea Comtrade mirror (exact) ·
Guinea Mining Insights Jan 2026 · Katadata Jan/Apr · BPS key via env var.

### Failed → Prompt 13B
| § | Defect |
|---|---|
| C1 | **Pilbara: 30 fabricated rows** — literal `MONTHLY_UPDATES` list tagged `live_ppa_archive`; Aug 2026 copied from Jul 2026 |
| C2 | **Guinea: 6 rows cite dead URLs** (404 / 404 / 403); slugs constructed |
| C3 | **Fleet: 543 scrapped Capesizes counted active** — ignored `orderBookStatusID`; UNCTAD figures are script literals |
| C4 | **Comtrade parser takes first `motCode==0` row** — Türkiye scrap 6,944 t vs true 1.84 Mt |
| C5 | **Brazil splice: HS4 (with pellets) joined to NCM8** — ~8% false step at 2024-01; no source column |
| C6 | **Indonesia: `"India (~25-28%)"` stamped on 72 rows** with no partner data behind it |
| C7 | **Taxonomy test toothless** — 5 of 5 planted wrong codes pass |
| C8 | **Detector at 0 via 33 whole-file exemptions**; blind to list-of-records literals |
| C9 | **Boundary report's 34-row tsId table invented** — ledger was correct, report was not |

---

## Known open items (not yet fixed)

- **Tooltips ~5%**, not the 100% claimed in Phase 1.5. → Prompt 12.
- **4 view manifests over the 250 KB budget** — `vessel_lookup.json` is **5.6 MB**. CARGO tab
  has no view manifests at all. Cumulative transfer hits 13.41 MB after two tabs. → Prompt 12.
- **Bunker prices disagree with their registered source** — ours match BunkerIndex, the
  manifest says Ship & Bunker. Mechanism undetermined. → Prompt 10 §10.25.
- **`status: LIVE` still encodes fetch-time, not data currency.** → Prompt 10.
- **Fabrication detector** — allowlist rewrite is now 13B §C8 (was Prompt 10 §10.4).
- **tsIds 11 and 13** (values 145,000 / 110,000) remain unidentified and correctly hedged.

---

## Parked by the product owner

**Infinity Shipbrokers** — daily "Rate Stipulations" sheet (Non-Eco/Eco/Scrubber TCE per
route, WS→TCE bridge). We hold nothing from them. **He has another approach in mind and
will explain — do not push.**

---

## Standing corrections — do not re-inherit these

| Claim | Truth |
|---|---|
| "Fearnpulse unlocks 41 years of BDI" | We already hold 10,513 rows from 1985 — deeper |
| "Barchart `KW3J26` for C3 history" | Expired contract, no data; site is bot-protected |
| "tsId 10013 = P6_82" | It is **P4_82**; P6_82 is Dely Singapore RV via Atlantic |
| "Fearnleys tanker columns run 2018→2026" | tsIds 1,2,3,5,6,7,8,9 **dead since 2023-05-22**; tsId 4 alive |
| "chinadata.live gives volume and value" | Free tier is **value_usd only** |
| "Bunker off-by-one date bug, four ports exact" | Circular reasoning; real finding is narrower |
| `signal_map_ports_master.json` is the master | It is byte-identical to the LNG file |
| "USDA AMS is 403-gated" | **Wrong — my tool was blocked.** Plain `requests` gets the xlsx (HTTP 200) |
| "worldsteel is JS-rendered" | Press-release pages are static HTML and fetch fine |
| "120132 = S4B (delivery Cont), 120133 = S4A" | **Backwards.** "Delivery Cont/USG" was invented in 13 Target 1A; I accepted it. 120132 = **S4A** (value-anchored), 120133 = S4B (inferred) |
| "Fearnleys bunker tsId 303 = Singapore, 306 = Rotterdam" | **Backwards.** 306/307 = Singapore, 303/304 = Rotterdam |
| "Port lineups are authentic Signal Ocean data" (13C agent) | CRC32-hash synthesized — status, wait days, positions, arrival time |
| "GMI data-hub has no data" (13B agent) | It has plain-HTML chart data tables: annual 2015–2025, per-company 2025, destination shares |

Every row count in these prompts is a **2026-09-10/11 snapshot**. Re-measure; never hardcode.
