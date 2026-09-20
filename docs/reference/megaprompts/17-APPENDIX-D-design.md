# 17 — APPENDIX D: design direction and the Tracking rebuild

Reference images live in `Inspiration/` (34 files). The ones this appendix is drawn from:
`Screenshot (9232).png` (Signal Ocean — port Live View: table + map), `Screenshot (9248).png`
(Signal Ocean — Distance Calculator: map + right detail rail), `HN-0BL4awAAh6c5.jpg` (Kpler —
wheat flows: left control panel, one big chart, grey 5-year range band, orange 5-year average),
`Screenshot (9259).png` (dark AIS dashboard: thin KPI strip above a chart + map),
`Screenshot (9240).png` (Ship & Bunker — dense price tables). **Look at them before starting.**

## D1 — What those products do that we don't

1. **One job per screen.** A screen is a table plus a map, or a control panel plus one chart. Ours
   stacks 10+ unrelated modules in a column and the user scrolls for 7,000 px.
2. **Controls live in one bar**, at the top of the panel they affect — not floating over the map,
   not repeated per module.
3. **No decoration.** No glow, no glass, no coloured left edges, no all-caps status pills. Status is
   a word in the corner of the module footer, in muted grey.
4. **Numbers are the loudest thing on screen.** Everything else (labels, chrome, borders) recedes.
5. **The map is a work surface**, not a hero image: it fills its half, the legend is small and
   bottom-left, and selecting a row highlights the map and vice-versa.
6. **Density is deliberate**: 28–32 px table rows, 12–13 px labels, tabular numerals, values
   right-aligned, one accent colour.

## D2 — Tokens (dark theme, adapt the existing palette rather than inventing a new one)

| Token | Value |
|---|---|
| `--bg` page | `#0b0f14` |
| `--surface` module | `#111820` |
| `--surface-2` inset (table header, KPI tile) | `#151d27` |
| `--border` hairline | `#1e2730` (1 px, never thicker) |
| `--text` primary | `#e6edf3` |
| `--text-2` labels | `#9fb0c0` |
| `--text-3` muted / provenance | `#6b7d8f` |
| `--accent` (active state, current-year line) | `#4d9aff` — one accent only |
| `--pos` / `--neg` | `#3fb950` / `#f85149`, for numbers only, never as backgrounds |
| `--band` seasonal range | `rgba(159,176,192,0.14)` fill, no border |
| `--mean` 5-year mean line | `#e3b341`, 1.5 px dashed |

Type: page title 18 px/600 · module title 13 px/600 uppercase-off · label 12 px/500 `--text-2` ·
table 12.5 px · KPI value 26 px/600 tabular · provenance 11.5 px `--text-3`.
Spacing scale 4/8/12/16/24. Radius 6 px. **No shadows at all.**

Charts: series 1.75 px; gridlines `#1a222c` 1 px, horizontal only; axis labels 11 px `--text-3`;
no point markers on dense daily series; current year in `--accent`, prior year `--text-3` dotted,
5-year band `--band`, 5-year mean `--mean` dashed. Legend: one row, 11.5 px, above the plot, left.

## D3 — Components

- **Module card**: title row (title left, controls right) → body → footer. Footer is one muted line:
  `Source · through 2026-08` (from the manifest; amber if stale, red if dormant). No badges, no
  "why this matters" box with a coloured bar — if a note is worth keeping it is one muted sentence
  under the title.
- **KPI strip**: up to 6 tiles, each `label` (12 px `--text-2`) over `value` (26 px). One optional
  sub-line of 11.5 px. No icons, no coloured borders, no pills.
- **Table**: 30 px rows, header `--surface-2`, hairline row separators, numbers right-aligned with
  tabular numerals, text left. Sort on header click. No zebra striping.
- **Segmented control / chips**: 28 px tall, 12 px text, `--surface-2` background, active = `--accent`
  text on `#16283d`, 1 px border. Never more than one active row of them per panel.
- **Tooltip**: 12 px, max 320 px wide, three beats — what it is · source and date · why it matters.
- **Empty state**: one muted line saying what is missing and when it is next expected. Never
  "Loading…" left on screen, never a bare dash in a KPI.

## D4 — Tracking, rebuilt (the tab the operator called out)

Today: a small chart in a narrow left column with ~1,000 px of empty space under it, sector chips
floating over the map and clipping under the zoom control, a dangling "WINDOW:" label, the
chokepoint panel far below the map, and the whole primary view needing several screens of scroll.

Target at 1920×1080 — **no page scroll for the primary view**:

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ tab bar (12 tabs, fits)                                                                  │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ KPI strip: Port calls · 7d avg · Chokepoints under baseline · Active disruptions · …     │  72px
├───────────────────────────────┬──────────────────────────────────────────────────────────┤
│ FILTER BAR (one row):         │                                                          │
│  sector ▾ | window ▾ | search │                                                          │
├───────────────────────────────┤                                                          │
│ Ports | Calls | Chokepoints   │                  MAP (fills)                             │
│ Disruptions | Vessels         │   markers sized by YTD calls; selection syncs both ways   │
│ ───────────────────────────── │   legend bottom-left, 3 lines, 11.5px                    │
│ ▸ list / table of the active  │                                                          │
│   sub-view, virtualised,      │                                                          │
│   30px rows, fills height     │                                                          │
│                               │                                                          │
│ 460px                         │                              1460px                      │
├───────────────────────────────┴──────────────────────────────────────────────────────────┤
│ DETAIL DRAWER (opens under the map when a row is selected; 320px; closes with Esc)        │
│  port / chokepoint name · its series chart · 4 facts · source line                        │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Rules for it:
- The left panel is **never empty**: each sub-view has a default selection (e.g. Ports opens on the
  busiest hub, Chokepoints on the one furthest below baseline).
- Sub-view tabs sit inside the left panel and **must not scroll horizontally** — shorten the labels
  ("Ports", "Calls", "Chokepoints", "Disruptions", "Vessels") and drop the counts from the labels.
- Sector chips move out of the map into the filter bar.
- Chokepoint milestones become a plain table (date · event · source link), not cards with accent bars.
- At 1366×768 the same layout holds with the left panel at 380 px; the drawer becomes an overlay.

## D5 — Never (checked by the design lint)

Coloured left-edge accent bars · glow `box-shadow: 0 0 …` · `backdrop-filter: blur` · emoji or
dingbats in the UI · all-caps status pills · count badges beside titles · gradient text ·
values with more than 4 decimals on screen · module titles that state a span or a number ·
"why this matters" boxes with a coloured bar (keep the sentence, drop the box).
