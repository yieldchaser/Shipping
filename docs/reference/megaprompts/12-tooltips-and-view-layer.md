# PROMPT 12 — FINISH THE TWO HALF-BUILT SYSTEMS: TOOLTIPS & VIEW LAYER

> Read `docs/megaprompts/00-GUARDRAILS.md` first.
> Ledger: `docs/megaprompts/LEDGER-12-tooltips-views.md`
> Depends on: Prompt 10.

Phase 1.5 claimed 100% tooltip coverage. Phase 08 self-reported 5%. Independent
measurement on the live DOM found worse. Phase 1.3 claimed the three-tier view layer;
it is roughly half-built. Both are foundations other work sits on, so finish them properly.

---

## PART A — TOOLTIPS

### Measured reality (live DOM, 2026-09-10)

- **18 tooltips total on the mounted DOM.** Before the rebuild there were 1,908 rich +
  2,353 `title` attributes. Lazy mounting explains some of the drop, but not this much.
- **0 of 15 sampled tooltips carried a source or a date.**
- Sampled content is UI mechanics, exactly what GUARDRAILS bans:
  `"Click to view historical price settlement chart for Supramax 58 TC FFA…"` ×4
- **One tooltip renders a raw SHA-256 hash to the user:**
  `1c6ad53f75bf8247ec1725deb8e72e8e6abf4a0bbc7e565e21bad09f19ed9036`
  Find it, and find why an internal digest reached a user-facing attribute.

### The standard (unchanged, from Prompt 01 §1.5)

The **INTELLIGENCE tab** is the reference implementation. Three beats, 60–160 characters:
**what the number is → its source and span → why it matters to a dry bulk / tanker trader.**

### Work

1. **Fix the hash leak first.** It is a data-handling bug, not a copy problem.
2. **Coverage: every plotted number, axis, legend entry, badge, chip, filter and control.**
   Because tabs lazy-mount, measure per tab after opening it, not on the boot DOM.
3. **Provenance is mandatory in every data tooltip** — source name + `data_through` from the
   manifest (Prompt 10). This is the fabrication control, not decoration.
4. **Delete UI-mechanics text.** "Click to view…" describes the interaction, which the
   cursor already communicates. Replace with what the series *is*.
5. **Contract specs** — Prompt 09 §F wired `data/rulebooks/` into FFA and iron-ore tooltips.
   Verify that actually happened; hovering a contract should show lot size, tick, settlement.

### Acceptance
Per tab, after mounting: **≥95% of data-bearing elements have a tooltip**, and a random
20-tooltip sample scores **≥90%** on: three beats present · 60–160 chars · no UI mechanics ·
source + `data_through` present. Record the per-tab table in the ledger.

---

## PART B — VIEW LAYER

### Measured reality

Cold boot is genuinely excellent and the agent under-reported it:

| Metric | Baseline | Claimed | **Measured** |
|---|---|---|---|
| Transfer | 80.1 MB | 6.2 MB | **0.22 MB** |
| Requests | 129 | 18 | **12** |
| Canvases at load | 96 | 2 | **2** |
| DOM nodes | 16,838 | 5,187 | **4,789** |
| Load | 4,503 ms | 866 ms | **1,152 ms** |

**Tier 2 (lazy mount) works. Tier 1 and Tier 3 do not.**

### Problem 1 — view manifests blow the budget
Prompt 01 set **≤250 KB per view**. Four exceed it, badly:

| File | Size | Over budget |
|---|---|---|
| `data/views/signal/vessel_lookup.json` | **5.6 MB** | 22× |
| `data/views/signal/vessel_voyages_lookup.json` | 1.4 MB | 5.7× |
| `data/views/signal/live_fleet_positions.json` | 952 KB | 3.8× |
| `data/views/signal/routing_ports.json` | 800 KB | 3.2× |

These are lookup tables, not views. Shard them: an index manifest with the searchable
fields only (name, IMO, class, port), and per-record detail fetched on drill-down.
A user searching a vessel needs the index, not 67,256 full records.

### Problem 2 — raw CSVs still load on tab open
After visiting two tabs, transfer reaches **13.41 MB**. Worst offenders:

| File | Loaded |
|---|---|
| `portwatch_port_congestion.csv` | **7.8 MB** |
| `commodity_flow_matrix.json` | 1.4 MB |
| `vessel_valuations.csv` | 816 KB |
| `sgx_panamax_futures.csv` | 583 KB |
| `sgx_handysize_futures.csv` | 573 KB |
| `sgx_cape_futures.csv` | 501 KB |

Every one of these should be a ≤250 KB view manifest, with the raw file reserved for
drill-down (Tier 3).

### Problem 3 — the Cargo tab has no views at all
28 manifests exist; **none are for CARGO**. The newest and most data-hungry tab fetches
raw CSVs directly, including `usda_grain_vessel_loading_queues.csv` and
`us_eia_weekly_crude_exports.csv`.

### Acceptance
- **No file under `data/views/` exceeds 250 KB.**
- **No raw CSV over 250 KB is fetched on tab open** — only on drill-down.
- Cumulative transfer after visiting **all 12 tabs ≤ 8 MB**.
- Cold boot metrics do not regress from the measured baseline above.

Record cumulative transfer after each tab, in order, in the ledger.

---

## PART C — small corrections found in audit

1. **Cargo tab title overstates span** — *"USDA Grain Vessel Loading & Port Queues (31-Year
   History 1995–2026)"* over a file ending 2020. Prompt 10 makes titles generate from
   `date_span`; verify this one specifically.
2. **`portwatch_port_congestion.csv` (7.8 MB)** has no provenance entry visible in the
   manifest sample — check and register.
3. The **seasonal envelope component is correct** — verified rendering W1–W52 with 5Y range
   band, 5Y mean, and toggleable prior years. **Do not change it.** Reuse it for any module
   still rendering a bare line.

---

## Verify and stop

```
git commit -m "fix(ui): complete tooltip coverage to standard; shard oversized view manifests

- fix SHA-256 hash leaking into a user-facing tooltip
- tooltips: three-beat standard with source + data_through, >=95% coverage per tab
- shard vessel_lookup (5.6MB) and 3 other oversized manifests into index + drilldown
- move portwatch_port_congestion and 5 SGX/valuation CSVs behind view manifests
- build the missing CARGO view manifests

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP.** Print: per-tab tooltip coverage and sample score; view manifests over budget
(must be zero); cumulative transfer across all 12 tabs.
