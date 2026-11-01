# China imports by partner country — what is missing and where it lives

Written 2026-11-02 for the owner. Everything else in the Cargo & Trade Flows tab is automated; this is the one
dataset that is not.

## What we need

For every month from **2026-09** onward, China's **imports** by **trading partner country**, for these HS codes,
with both **quantity** (as declared, first unit: kg / tonnes) and **value in USD**:

| Dashboard line | HS code(s) | Stored series key |
|---|---|---|
| Iron ore | 2601 (all 8-digit lines under it) | `2601` |
| Coal | 2701 | `2701` |
| Crude oil | 2709 | `2709` |
| Natural gas incl. LNG | 2711 (271111 LNG, 271121 pipeline gas) | `2711` |
| Soybeans | 1201 | `1201` |
| Nitrogen fertilizers | 3102 | `3102` |
| Mixed fertilizers | 3105 | `3105` |
| Steel (chapter) | 72 | `72` |
| Bauxite | 26060000 | `26060000` |
| Alumina | 28182000 | `28182000` |

One row per (month, HS code, partner country): `month, hs_code, partner, quantity, quantity_unit, value_usd`.
The dashboard uses it for the "Who feeds China" panel (partner shares) and the Guinea/Australia bauxite split.
History up to 2026-09 is already stored in `data/commodities/china_customs_monthly_imports.csv` and
`china_customs_partners_summary.json` (September 2026 was ingested via `china_partner_imports_2026-09.csv`);
only future new months (2026-10 onward) are needed.

## Where it is published (all free)

| Source | What it has | Why the pipeline cannot read it |
|---|---|---|
| **stats.customs.gov.cn** — GACC "海关统计数据在线查询平台" (online statistics query), `http://stats.customs.gov.cn/` | The official source: monthly, HS 8-digit, by partner, quantity + USD/CNY. Free; the 2026-09-17 export you supplied came from here. Released around the 20th of the following month. | Every scripted request gets HTTP 412 and a JavaScript challenge page (a dynamic-cookie bot check); only a real browser session passes. |
| **www.customs.gov.cn** — GACC Chinese site, 统计快讯 / 统计数据 monthly tables | Monthly commodity tables (quantity + value), but not split by country. | Same 412 JavaScript challenge. Not needed now: the English bulletin covers the same totals. |
| **chinadata.live** — product pages such as `/china-trade/hs/260600/` | GACC data republished: monthly by partner. | Its trade API was retired in 2026-10 (404) and the HTML pages now sit behind a Cloudflare challenge. |
| **UN Comtrade** — `comtradeapi.un.org/public/v1/preview/C/M/HS?reporterCode=156` | Same data, free API, no key. | Not blocked, but China's monthly data there ends at 2024-12. Worth re-checking: if China's 2025-26 months appear, this becomes the fully automated source. |
| **english.customs.gov.cn** (GACC English bulletin) | Monthly totals by commodity (already automated: `fetch_gacc_monthly_bulletin.py`). Total trade by country (table 4). | Not blocked, but it has no commodity-by-country table. |

## How to hand it to the pipeline

Any CSV with the columns above, dropped at `data/commodities/inbox/china_partner_imports_<YYYY-MM>.csv`, is enough;
the column names can follow the GACC export headers. Tell me the file is there and the import step will join it to
the stored series (same partner names and USD units as the 2026-09-17 export).

## What is automated meanwhile (no gap)

- China totals by commodity, quantity and value: GACC English bulletin, monthly.
- Guinea / Australia bauxite and alumina by origin, tonnes: SMM's text prints of the GACC data (monthly sitemaps).
- Brazil's exports to China and every other destination (iron ore, soybeans, crude, sugar), tonnes: Brazil
  ComexStat API, monthly.
