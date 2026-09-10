# TOOLTIP STANDARD — MARITIME INTELLIGENCE TERMINAL

> **Status**: HOUSE STANDARD (MANDATORY REPO-WIDE)  
> **Enforcement**: Phase 1.5 Foundation; verified per-tab in Phases 03–07  
> **Preamble**: This document defines the terminal-wide standard for all tooltips across `index.html`. Every plotted number, axis tick, status badge, filter chip, table cell, and control element must provide informative, high-signal hover intelligence.

---

## 1. Core Principles & Philosophy

A new user, dry bulk charterer, or tanker trader must be able to explore and understand the entire terminal from hover alone. Tooltips in this application are **market intelligence annotations**, not UI manual excerpts or apology spaces for missing data.

### The 5 Golden Rules

1. **Every Plotted Metric, Axis, Badge, Chip, and Control Gets a Tooltip**  
   Zero uncontexted numbers. If a number is rendered on the screen, a user hovering over it must immediately learn what it measures, who published it, its observation window, and why it moves freight markets.

2. **The 3-Beat Standard (60–160 Characters Total)**  
   Every data tooltip must answer three distinct beats in crisp, professional financial prose:
   - **Beat 1: What it is** — Clear, standardized naming of the metric or contract.
   - **Beat 2: Source & Span** — Explicit source attribution, exact observation date span, and dataset `as_of` date.
   - **Beat 3: Market Meaning / Trading Impact** — 60 to 160 characters explaining what this reading means for a dry bulk or tanker desk (supply absorption, chartering arbitrage, bunker hedging, or vessel asset values).

3. **Never Describe UI Mechanics**  
   Delete all developer-centric implementation phrases:
   - ❌ BANNED: `"re-renders from cache"`, `"switches this section's view"`, `"one click — no separate fetch"`, `"runs client-side"`.  
   - ✅ REQUIRED: Describe what the control *selects* or *models* in the physical shipping market (e.g. `"Switches benchmark to Atlantic basin iron ore corridors (C3 Tubarão→Qingdao)"`).

4. **Never Put a Data Caveat in a Tooltip**  
   A tooltip is opt-in; a data gap or methodology boundary is an objective fact about the chart.
   - **Never apologize in hover text.** Do not write:
     - ❌ `"null — no verified indication (never 0-filled)"`
     - ❌ `"No monthly history"`
     - ❌ `"Δ source: month-over-month VLSFO change (fallback, not a 7-day reading)"`
     - ❌ `"PortWatch does not publish LNG port calls."`
   - **Design around the gap**:
     - If PortWatch has no LNG calls, label the chip **"fixtures only"** on its visible face.
     - If monthly bunker history is absent, leave the sparkline empty or display an informative range badge.
     - If a rate is a monthly average instead of a 7-day print, badge it directly on the table cell as `MoM*`.
     - If an indication is missing, render `—` and explain universe coverage in the section subhead/caption.

5. **Provenance is Mandatory (Fabrication Control)**  
   Every data tooltip must cite its authentic source name and latest `as_of` timestamp matching `data/provenance/manifest.json` and the pre-aggregated view manifest header in `data/views/`.

---

## 2. The 3-Beat Structure: Anatomy & Architecture

Every tooltip rendered by the shared component adheres to the following DOM layout:

```html
<div class="rt-title">[BEAT 1: Metric Name / Identification]</div>
<div class="rt-row">
  <span class="rt-label">Current / Value</span>
  <span class="rt-val">[Observed Value with units]</span>
</div>
<div class="rt-row">
  <span class="rt-label">Source &amp; Span</span>
  <span class="rt-val">[BEAT 2: Authentic Source · Date Window · As-Of Date]</span>
</div>
<div class="rt-note">
  [BEAT 3: Market Meaning / Economic Impact for freight traders (60–160 chars)]
</div>
```

### Visual Layout & Typography Tokens
- **Container**: `#global-tooltip` — backdrop blur, dark navy translucent background (`rgba(13, 17, 23, 0.98)`), subtle accent glow, z-index 10000.
- **Title (`.rt-title`)**: 12px uppercase, letter-spacing 0.5px, bold, border-bottom divider.
- **Data Rows (`.rt-row`)**: 11px (`var(--fs-micro)` floor), tabular figures, right-aligned values with positive (`#3fb950`) and negative (`#f85149`) semantic color coding.
- **Trader Impact (`.rt-note` / `.rt-impact`)**: 11px, italic, subtle top border. Provides the 60–160 character economic impact.

---

## 3. Shared Component API

The tooltip engine provides two implementation paths: **Declarative HTML attributes** and the **Programmatic JavaScript API**.

### 3.1 Declarative Attribute API

For static or inline-rendered HTML elements, attach data attributes directly:

```html
<!-- Example: Plotted KPI or Table Cell -->
<div 
  data-tt-title="Capesize C5 West Australia → Qingdao Freight Rate"
  data-tt-val="$11.45 / wmt"
  data-tt-source="Baltic Exchange (BCI)"
  data-tt-span="2018–2026"
  data-tt-asof="2026-09-08"
  data-tt-impact="Primary Pacific iron ore voyage benchmark. Rates above $12/wmt absorb prompt dry tonnage across Singapore and the Far East.">
  $11.45
</div>
```

For custom rich metrics, use `data-tt-type`:
```html
<span data-tt-type="zscore" data-tt-val="1.85" data-tt-pctl1y="94" data-tt-zwin="252 trading days">
  +1.85σ
</span>
```

### 3.2 Programmatic JavaScript API: `window.renderStandardTooltip`

In dynamic table renderers, canvas hover listeners, and Chart.js callbacks:

```javascript
const tooltipHtml = window.renderStandardTooltip({
  title: 'Global VLSFO Bunker Composite',
  rows: [
    { label: 'Composite Benchmark', val: '$612.50 / MT', cls: 'pos' },
    { label: 'Singapore Spread', val: '+$14.20 / MT' }
  ],
  source: 'Ship & Bunker / OilPriceAPI',
  asOf: '2026-09-08',
  span: 'Trailing 30 days',
  impact: 'Global bunker fuel pricing index. A $20/MT jump in VLSFO increases Capesize daily voyage operating cost by ~$600/day.'
});
```

#### Signature Specification:
```typescript
interface StandardTooltipSpec {
  title: string;              // Beat 1: What it is (e.g. 'Pilbara Port Throughput')
  rows?: Array<{              // Intermediate data rows
    label: string;
    val: string | number;
    cls?: 'pos' | 'neg' | '';
    color?: string;
  }>;
  source: string;             // Beat 2: Authentic source (e.g. 'Pilbara Ports Authority')
  asOf?: string;              // Beat 2: As-of date from view manifest header
  span?: string;              // Beat 2: Historical span (e.g. '2017–2026')
  impact: string;             // Beat 3: Market meaning (60–160 characters)
}
```

---

## 4. Good vs. Bad Examples Catalog

| Aspect | ❌ Bad (Legacy / Forbidden) | ✅ Good (Standard Compliant) |
|---|---|---|
| **Caveat in Hover** | `title="null — no verified indication (never 0-filled)"` | Renders `—` in cell. Section caption specifies: `Verified alt-fuel indications (LNG, MEOH, EUA). Null = no quote.` |
| **Data Gap Apology** | `data-tooltip="PortWatch does not publish LNG port calls. This mode shows broker-reported fixture legs only..."` | Button face: `LNG (fixtures only)`. Tooltip: **LNG Fixture Activity** · Fearnleys Fixtures (2024–2026) · *Tracks long-haul cryogenic carrier fixtures across major export terminals.* |
| **Fallback Labeling** | `title="Δ source: month-over-month VLSFO change (fallback, not a 7-day reading)"` | Table cell badge: `+12.50 MoM*`. Tooltip: **Monthly VLSFO Delta** · Ship & Bunker · *Month-over-month price change reflecting structural bunker cost trajectory.* |
| **Missing History** | `title="No monthly history"` | Omit title or render: **Trailing Trend** · *Historical monthly price series pending scheduled archive integration.* |
| **UI Mechanics** | `data-tooltip="Switches this section's view/parameter and re-renders from cache."` | `data-tooltip="Toggle Between Clean & Dirty Tankers · Baltic Exchange · Switches fleet focus between refined product carriers (MR/LR) and crude tankers (VLCC/Suezmax)."` |
| **Missing Provenance** | `data-tooltip="China Iron Ore Imports: 102.5 Mt. Great for Capesize."` | `data-tooltip="China Monthly Iron Ore Imports · General Administration of Customs (2018–2026, as-of 2026-08) · High import volumes (>100Mt/mo) drive long-haul C3/C5 Capesize ton-mile demand."` |

---

## 5. Audit Checklist for Phases 03–07

When rebuilding individual tabs in Phases 03 through 07, apply this verification checklist:

- [ ] **1. Hover Coverage**: Does every single KPI card, table header, table cell with data, and chart control trigger a tooltip?
- [ ] **2. Beat 1 Verified**: Does the title clearly identify the metric without generic placeholders?
- [ ] **3. Beat 2 Verified**: Are the source name, date span, and dataset as-of date explicitly stated?
- [ ] **4. Beat 3 Verified**: Does the note deliver 60–160 characters explaining the economic/freight trading significance?
- [ ] **5. Zero UI Mechanics**: Are words like "cache", "re-render", "pipeline", and "switches" strictly absent from user hover text?
- [ ] **6. Zero Apologies**: Are caveats moved to axis labels, table captions, or status badges?
- [ ] **7. Anti-Fabrication**: Does every quoted source correspond to an authentic registered record in `data/provenance/manifest.json`?
