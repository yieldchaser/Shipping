# upstream_commodity_flows.yml – additions

```yaml
      - name: Install headless browser for PPA (Imperva bot wall)
        run: |
          pip install playwright
          python -m playwright install --with-deps chromium
          sudo apt-get install -y poppler-utils

      - name: PPA Hedland + Dampier
        run: python scripts/scrapers/fetch_australia_ppa.py

      # previously ORPHANED
      - name: Minor bulks
        run: python scripts/acquire/fetch_minor_bulks.py
      - name: World Steel
        run: python scripts/acquire/fetch_world_steel_production.py
      - name: China customs demand
        run: python scripts/acquire/fetch_china_customs_demand.py
      - name: Argentina grain
        run: python scripts/acquire/fetch_argentina_grain.py
```

# usda_weekly.yml – additions
```yaml
      - name: FGIS gap backfill (current year only)
        run: python scripts/scrapers/backfill_fgis_inspections.py $(date +%Y)
```

# Code bugs that caused "gaps" (fix in code, no data to fetch)
1. `build_cargo_cache.py` ~L1110: pilbara_c5 uses `hedland_vol.get(m)` only – after the PPA backfill Hedland is complete except Jul-21 / Jun-22 (unpublished).
2. `build_cargo_cache.py` ~L1160: `len(gulf_weeks[m]) >= 4` drops real months. Use `>= 3`, or prorate: `t / n_weeks * weeks_in_month`.
3. `fetch_usda_fas_exports.py`: Socrata paging ordered by non-unique `date DESC` can repeat/skip rows across pages. Order by `date DESC, :id`.
4. `fetch_china_customs_demand.py:203`: month written without year (HS72 rows dated `1-01`, `10-01`).
5. USDA vessel-loading `%Y-%W` week-00 parse: use the date column from GTRTable19 directly.
6. Minor-bulks sugar: 2022 rows are all NCM 1701, 2026 rows are raw sugar only (17011300+17011400). Pick one definition and restate history.
7. Fearnleys fixtures max date 2026-12-18 is in the future – a date-parse bug in the sync.

# National-source replacements for Comtrade (added 2026-09-17)
```yaml
      - name: Philippines nickel ore (PSA OpenSTAT)
        run: python scripts/scrapers/fetch_psa_nickel.py
      - name: India HS3102 imports (Commerce TradeStat)
        run: python scripts/scrapers/fetch_india_tradestat.py $(date -d "-2 month" +%Y) $(date -d "-2 month" +%-m)
```
- Türkiye (TurkStat): the old biruni export tool redirects to a Qlik dashboard (bi.tuik.gov.tr). Its engine
  websocket returned HTTP 503 from this environment; try from GitHub Actions or export by hand
  (Ürün/Ürün Grubu-Ülke → Ürün/Ülke → Harmonize Sistem → HS4 → 2523 / 7204, İhracat/İthalat, USD).
- China (GACC): CAPTCHA-gated – see GACC_MANUAL_EXPORT.md.

# Türkiye (TurkStat) – solved via browser pull
- `scripts/tuik_browser_pull.js`: paste into DevTools on bi.tuik.gov.tr/…?report_type=1 (manual, monthly; engine blocks CI IPs).
- Uses the GENERAL trade app (bd4b4757…), which equals the Comtrade series exactly (cement 35 mo, scrap 47 mo).
- Optional: replace both series with `minor_bulks_turkiye_TURKSTAT_GENERAL_2013_2026.csv` (no gaps, ~2 months fresher than Comtrade).
