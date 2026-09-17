# TurkStat (TÜİK) Ingestion Architecture & Self-Hosted Runner Guide

## Overview

Türkiye seaborne bulk commodity trade flows:
- **HS 2523**: Cement & Clinker Exports (Handysize dry bulk)
- **HS 7204**: Ferrous Scrap Steel Imports (Supramax / Handysize dry bulk)

TurkStat publishes trade statistics via its Qlik Sense BI mashup application:
- **URL**: `https://bi.tuik.gov.tr/extensions/tuik-mashup/index.html?report_type=1`
- **App ID**: `bd4b4757-a3c9-45ba-b4fb-5c8d7e2d2c42` (General Trade System)

---

## Cloud IP Blocking & HTTP 503

The TurkStat BI mashup gateway sits behind state-level / institutional firewalls and Akamai / Cloudflare edge protection that systematically blocks public cloud IP ranges (including AWS, Azure, GCP, and GitHub-hosted Actions runners `ubuntu-latest`).

When automated headless browsers (Playwright Chromium) on GitHub Actions attempt to access `bi.tuik.gov.tr`, the server returns:
- **HTTP 503 Service Unavailable** (or HTTP 403 Forbidden)
- Handshake drops before loading Qlik JavaScript libraries (`js/qlik`)

### Zero-Touch Policy: Empty Month Over Synthetic Flatline

Per the project's data integrity policy:
1. **Cement**: When TurkStat is blocked and no newer verified extract exists, the latest month is **intentionally left empty / null**. It is **never** filled with synthetic flatlines, UN Comtrade estimates (which suffer from 3-month lag and special trade distortion), or old scratch files.
2. **Freshness Alerting**: An empty month correctly registers in `check_data_freshness.py` when it exceeds the expected reporting lag, ensuring full visibility.
3. **Scrap Fallback**: Scrap steel has an automated secondary fallback via SteelOrbis news reports quoting official TÜİK figures (`fetch_steelorbis_scrap_fallback()`), which derive monthly figures from cumulative YTD reports with provenance `SteelOrbis/TUIK`.

---

## Deploying a Self-Hosted GitHub Actions Runner

To achieve fully automated, unblocked ingestion of TurkStat Cement and Scrap data without cloud IP blocks, configure a self-hosted runner on an IP address not flagged as a commercial data center (e.g. residential or corporate Turkish/European IP):

### 1. Requirements
- Linux (Ubuntu 22.04+), macOS, or Windows host
- Python 3.12+ with `playwright` installed:
  ```bash
  pip install playwright pandas
  playwright install --with-deps chromium
  ```
- Network access to `bi.tuik.gov.tr` (test with `curl -I https://bi.tuik.gov.tr/extensions/tuik-mashup/index.html?report_type=1`)

### 2. Register Runner in GitHub Repository
1. In the GitHub repository, navigate to **Settings** -> **Actions** -> **Runners** -> **New self-hosted runner**.
2. Download and configure the runner package:
   ```bash
   mkdir actions-runner && cd actions-runner
   curl -o actions-runner-linux-x64-2.319.1.tar.gz -L https://github.com/actions/runner/releases/download/v2.319.1/actions-runner-linux-x64-2.319.1.tar.gz
   tar xzf ./actions-runner-linux-x64-2.319.1.tar.gz
   ./config.sh --url https://github.com/yieldchaser/Shipping --token <REGISTRATION_TOKEN> --labels turkstat-runner
   ./run.sh
   ```

### 3. Workflow Configuration
In `.github/workflows/upstream_commodity_flows.yml` or a dedicated `turkstat_monthly.yml`:
```yaml
jobs:
  turkstat-ingest:
    runs-on: [self-hosted, turkstat-runner]
    steps:
      - uses: actions/checkout@v4
      - name: Ingest TurkStat General Trade
        run: |
          python scripts/scrapers/fetch_turkstat_bulk.py
          python scripts/cargo/build_cargo_cache.py
```

With `runs-on: [self-hosted]`, Playwright navigates the Qlik app, evaluates the `tuik_browser_pull.js` mashup query, and writes the latest month directly into `minor_bulks_monthly.csv`.
