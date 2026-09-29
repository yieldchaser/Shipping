# CLOSED 2026-09-29 11:5x IST - bancosta branches 7/8: chart tables published as container indices

State-file target #1: `freightos_index` 502 of 2,271 rows and `vhss_contex` 1,713 of 3,427 rows
had a `unit` cell that is neither a unit token nor a period label (e.g. `segment=Jul-20, unit=8000`).

## Root cause: a table-level gate with a fixed column index

Branches 7 (VHSS ConTex) and 8 (Freightos) of
`scripts/extract/publishers/run_banchero_world_class_llama.py` gated on the HEADING only
(`"VHSS" in ctx` / `"FREIGHTOS" in ctx`) and then read a FIXED index
(`r[0]=segment, r[1]=unit, r[2]=current, r[3]=previous`).

The container **CHARTS** sit under the same heading as markdown tables:

```
| GEARLESS - 1 YR TC PERIOD (USD/DAY) |       |       |       |   |
| ----------------------------------- | ----- | ----- | ----- | - |
| Date                                | 4250  | 3500  | 2700  |   |
| Jul-20                              | 8000  | 8000  | 8000  |   |
```

so their chart points were published as container-index rows
(`segment="Jul-20", unit="8000", current="8000", previous="8000"`), and the Freightos
block banners (`Services:`) were published as routes with empty values.

## Fix: require a real unit token (content anchor), let charts fall through

`_INDEX_UNITS = {index, idx, points, usd/day, usd/feu, usd/mt, usd/t, usd, $, ws}`.
A real VHSS/Freightos row carries one of these in the unit column; a chart point carries a
NUMBER there. Both branches now (a) gate on `any(row has a unit token)` and (b) append only
rows whose unit cell is a token. A pure-chart table therefore falls through to branch 12
(`"date" in header_str`) and lands in `chart_series` - where it belongs - instead of being
published as a bogus container index.

## Measured

| measure | before | after |
|---|---|---|
| `vhss_contex` rows | 3,427 | **1,714** |
| `freightos_index` rows | 2,271 | **1,769** |
| non-unit `unit` rows in either | 2,215 | **0** |
| `chart_series` rows | 39,425 | **42,403** |
| container-chart rows now in `chart_series` | 44 | **1,352** |
| `bancosta_vhss_series.csv` rows | 3,427 | **1,714** |

## Controls

1. Cache-only rebuild reproduces all 10 series CSVs byte-exact BEFORE the patch (see the
   companion verdict) - so any change is the patch, not drift.
2. Diff of the sidecars: **vhss_contex removed 1,698 distinct rows / 0 added**;
   **freightos_index removed 502 / 0 added**; **chart_series removed 0 / +2,970 added**.
   Every removed vhss/freightos row is a chart point or a banner.
3. **0 of the removed rows carried a unit token** - i.e. the 1,714 real index rows are
   exactly the 1,714 that survive. No real row lost.
4. **All 1,714 vhss and 1,769 freightos `value_current` values verbatim on the page**
   (publisher PDF text layer or LlamaParse read): 3,483/3,483, 0 misses.
5. **All 2,970 newly-added `chart_series` rows verified**: every value and date verbatim on
   the page, 2,970/2,970, 0 misses.
6. Series-CSV control: **8 of 10 byte-identical**; only `freight_rates` (the companion
   branch-11 fix from the same run) and `vhss` differ.

Rebuilt from the **cached** markdown - **no API spend**. `chart_series` is a sidecar-only
artefact (it is not one of the 10 stacked series CSVs), so the delivered-series effect of
this fix is: 1,713 chart points and 502 banner rows leave `bancosta_vhss_series.csv`, and the
chart points are preserved in `chart_series` instead of being published as container indices.

## Note on method

There is NO image/vision tool in the cron session. Verification substituted the same-document
text reconciliation against BOTH the publisher's own PDF text layer and the LlamaParse
pixel-read markdown, and every removed row was classified rather than assumed.
