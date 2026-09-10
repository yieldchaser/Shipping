# PROMPT 05 — TRACKING: FROM PORT STATISTICS TO A VESSEL TERMINAL

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-05-tracking.md`
> Depends on: Prompts 01, 02, 03 complete.

This is the largest rebuild in the series. Budget accordingly and use the phase stops.

---

## Context: the core problem in one line

**We hold Signal Ocean's commercial fleet database and we are rendering IMF's summary
statistics.**

`index.html` currently references exactly **two** of the ~35 Signal Ocean / Clarksons
files. 67,256 vessels, 12,060 routing ports, 7,937 live positions and every asset-class
port split sit unused on disk while the tab shows aggregate port-call counts.

The product owner has **approved full publication** of the Signal Ocean layer. There is no
permission question remaining. Build it.

---

## Design reference — study before building

The folder `Inspiration/` (34 images, repo root, untracked) contains the target. Open them.
The relevant ones for this tab:

- **Signal Ocean port Live View** (`Screenshot (9232).png`) — the model for the port queue:
  a table of `ETA · Vessel Name · Vessel Class · Commercial Operator · Purpose (Load/Disch)
  · Status (Operating/Waiting)` with a running `Total: 99`, filters for Vessel Class DWT
  range / Status / Purpose / Cargo Type, a split map pane with directional vessel markers,
  and port tabs along the bottom for switching between watched ports.
- **Signal Ocean Distance Calculator** (`Screenshot (9237/9247/9249/9250/9252).png`) —
  multi-leg route chips, `DURATION 60.5 d / DISTANCE 18,877 NM`, an `(S)ECA 1.8d 573NM`
  pill, speed and sea-margin steppers, a per-leg schedule (`21.8d | 6,796 NM`), a
  `via Panama` routing choice, and a per-port hover card with arrival time, cumulative
  distance and weather. Screenshot 9249/9252 additionally show a **Sea Margin panel** with
  a 3-year historical monthly average chart and a 7-day forecast table decomposing
  waves / current / wind into a total percentage.
- **Braemar chokepoint charts** (`photo_2026-09-10_14-00-45/47.jpg`) — Suez daily bulker
  transits with a 5-day moving average and **annotated event callouts drawn on the chart**
  ("First Houthi attack on merchant shipping"). This is how a chokepoint chart should read.
- **Braemar Brazil queue** (`photo_..._14-00-47 (2).jpg`) — Panamaxes waiting off Brazil's
  terminals, one line per year 2019–2024, current year in bold red. Year-over-year overlay,
  not a single line.
- **AIS fleet HUD** (`Screenshot (9259).png`) — `Total Tonnage 322.7M · Avg Speed 11.6 ·
  % Laden 9.3% · No. Vessels 225` over a daily ballast-count bar chart and a position dot
  map. Also a sub-region matrix (Europe/Med, North America, South America, West Africa ×
  week) with Matrix/Table toggle.
- **Vessel detail panel** (`HN4mwEZawAAFOsY.jpg`) — vessel card with DWT, heading-to,
  last-seen, speed, laden bar; tabs for Voyages / Port calls / Trades / **Raw signals** /
  Charters / Compliance / Info, where Raw signals is an AIS destination-string log with
  ETA, updated timestamp and source.

**What to take:** the information density, the queue-as-first-class-object idea, the
year-over-year overlay, on-chart annotation.
**What not to take:** their exact visual style. This is a dark terminal; keep it.

---

## PHASE 5.1 — Fix the layout bug first

Measured today, Chokepoints Ledger view:
```
tracking-workstation  1360 × 1283
├ tracking-left-pane    560 × 1283   ← height-locked to sibling
│ └ chokepoint-dir-list 558 ×  700  (content 2500)  ← clipped, 546px dead below
└ tracking-right-pane   784 × 1283
  ├ leaflet map         782 ×  558  (content 768)   ← also clipped
  └ chokepoint-drawer   784 ×  707
```
Replace the fixed-height twin panes with CSS Grid; each pane sizes to its own content with
independent internal scrolling. Map gets its own height, not a clipped remainder.
**No pane may end with more than 48px of empty space.** Measure and record.

Also in this phase: the chokepoint detail blurb currently renders as a 9px unstyled
paragraph. Replace with a proper spec strip — region, connects, alternative routing,
baseline — at `--fs-body`.

---

## PHASE 5.2 — Subview architecture

Keep and rebuild: **Port Call History · Port Universe · Disruptions Feed · Vessel Voyages ·
Chokepoints Ledger · Distance & Routing · Port Squeeze & Stress**

**Remove: Port Bunkers.** It duplicates the entire BUNKERS tab. Delete it here; BUNKERS
owns fuel.

**Receive from SIGNALS:** Global Port Activity Monitor (IMF PortWatch) — merge into
Port Call History, do not add a second panel.

---

## PHASE 5.3 — Wire the Signal Ocean fleet layer ★ the main event

| File | Content | Renders as |
|---|---|---|
| `signal_vessels_dry_bulk.json` (13.5 MB) | 33,559 bulkers | fleet registry, searchable by name/IMO/class/operator |
| `signal_vessels_tankers.json` (8.4 MB) | 19,862 tankers | same |
| `signal_vessels_lpg.json` / `_lng.json` | 2,464 + 1,371 | same |
| `signal_live_fleet_positions_*.json` ×4 | **7,937 live positions** | the map layer |
| `signal_map_ports_{dry_bulk,tankers,lng,lpg}.json` | 118 / 113 / 73 / 150 terminals | **asset-class port picker** |
| `signal_ports_by_asset_class.csv` | pre-flattened | the picker's index |
| `signal_distance_ports.json` (2.7 MB) | 12,060 routing ports | Distance & Routing engine |
| `signal_map_ports_master.json` | 2,752 terminals + GIS polygons | port boundaries on map |
| `signal_charterers` / `_commercial_operators` / `_operational_statuses` / `_cargo_types_*` | taxonomies | filter vocabularies |

**Build these four surfaces:**

### A. Asset-class port picker
The product owner asked for this explicitly: ports organised **by tanker / dry bulk / LNG /
LPG**, not one undifferentiated list. Use the four `signal_map_ports_*` files. A user picks
a segment, then a port, and lands on that port's queue.

### B. Port queue (the Live View pattern)
For the selected port: every vessel with `ETA · Name · Class · Commercial Operator ·
Purpose · Status · DWT · days waiting`, a running total, and filters on DWT band, status,
purpose and cargo type.
Source: `data/geospatial/port_lineups_active.csv` (740 hulls: 434 at berth, 306 at anchor)
enriched against the Signal vessel registries for operator and particulars.
**Note:** `port_lineups_active.csv` has no commercial-operator column — join it from
`signal_vessels_*.json` on IMO. If the join fails for a hull, show "—", never a guess.

### C. Vessel drill-down
Click any vessel → particulars (DWT, built, yard, class, operator), voyage history from
`vessel_voyage_tracks_master.csv` (24,434 legs) and `voyage_history_fixturegrounded.csv`
(354,332 rows), current position, and its track on the map. Follow the tabbed pattern from
the reference screenshot: Voyages / Port calls / Particulars.

### D. Live position map
Leaflet, 7,937 cached positions, filterable by asset class and laden/ballast status. Add
the HUD strip from the reference: total tonnage, average speed, % laden, vessel count —
**computed from the data, never hardcoded.**

**Performance is mandatory here.** 22 MB of vessel JSON must never hit the browser on load.
Prompt 01 Tier 1 gives you view manifests; the registries are drill-down only. Cluster map
markers. If a view manifest exceeds 250 KB, aggregate further.

Optional refresh path, documented in `docs/MARITIME_INTELLIGENCE_MASTER_DISCOVERY.md` §1:
`POST /api/distanceTool/vessels/positions` with `{"imoList":[...]}`, 100 IMOs per call,
no search-quota deduction. Build it as a scheduled GitHub Action, rate-limited politely.
Never call it from the browser.

---

## PHASE 5.4 — Distance & Routing

Build on `signal_distance_ports.json` (12,060 routing ports). Match the reference:
- multi-leg route chips (add/remove/reorder ports)
- total duration + distance, per-leg breakdown (`21.8d | 6,796 NM`)
- speed stepper, sea-margin stepper
- canal routing choice (via Panama / via Suez / via Cape) with the delta shown
- ECA distance and days within the route

Weather overlay is **out of scope** — we have no weather source and must not invent one.
If you want the sea-margin panel, it may only show margin the user sets manually. Do not
fabricate a historical weather average.

---

## PHASE 5.5 — Chokepoints and Port Stress

**Chokepoints (28 passages).** Data: `chokepoint_transits_daily.csv` — 78,372 rows,
2019-01-01 → 2026-08-30, verified real.
- Add **year-over-year overlay** (one line per year, current year bold) — Braemar pattern.
- Add **on-chart event annotations**: Houthi attacks, Panama drought restrictions, Suez
  blockage. Store annotations in a small versioned JSON with source URLs; these are
  editorial facts and must be citable.
- Keep the baseline comparison, but **the `-73.1%` currently shown may be a hardcoded
  fallback** (`build_chokepoint_cache.py` line 446, fixed in Prompt 02). Verify the
  displayed number is computed and record the proof.

**Port Squeeze & Stress.** Already good — 50 hubs, ±1.5σ banding, seasonal envelopes from
`port_stress_matrix.csv` (20,000 rows, 2019-01 → 2026-08). This is already the pattern the
rest of the app should copy. Preserve it; only restyle to the new type scale.

---

## PHASE 5.6 — Tooltips and honesty

Tracking is the worst offender: **365 rich tooltips + 2,216 `title` attributes, averaging
46 characters**, many describing our rendering pipeline. Rewrite all of them to the
Prompt 01 §1.5 standard.

Specifically remove and redesign around these:
- `"PortWatch does not publish LNG port calls."` — **delete the LNG/LPG PortWatch chips
  entirely** or relabel them "fixtures only" on their face. Do not ship a filter that
  leads nowhere and explain it in hover text.
- `"Δ source: month-over-month VLSFO change (fallback, not a 7-day reading)"` ×9 — move to
  the axis label or the series badge.
- `"null — no verified indication (never 0-filled)"` ×10 — this is correct behaviour;
  express it as an empty state, not a tooltip.

---

## PHASE 5.7 — Verify and stop

```js
const t=document.getElementById('tab-tracking');
({panes:[...t.querySelectorAll('[class*=pane]')].map(p=>({cls:p.className,h:p.getBoundingClientRect().height,content:p.scrollHeight})),
  tiny:[...t.querySelectorAll('*')].filter(e=>e.innerText&&!e.children.length&&parseFloat(getComputedStyle(e).fontSize)<11).length})
// tiny must be 0; no pane content/height mismatch > 48px
```

Ledger must show: initial payload for this tab, vessel count rendered, port count by asset
class, and proof the -73.1 figure is computed.

```
git commit -m "feat(tracking): signal ocean fleet terminal - 67k vessels, asset-class ports, live positions

- asset-class port picker (118 dry bulk / 113 tanker / 73 LNG / 150 LPG terminals)
- port queue with operator join, ETA, status, days waiting
- vessel drill-down: particulars, voyage history, position track
- live map from 7,937 cached positions with computed fleet HUD
- distance & routing on 12,060-port graph, multi-leg, canal choice, ECA
- chokepoints: YoY overlay + sourced event annotations
- remove Port Bunkers subview (duplicates BUNKERS tab)
- grid panes replace fixed-height twins; all tooltips rewritten

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print surfaces built, files wired with row counts, payload before/after.
