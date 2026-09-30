# Documentation & Governance Architecture (`docs/`)

This directory houses the governance documentation, forensic research verdicts, master operational registers, regulatory SEC prospectuses, and active automated pipeline targets for the `yieldchaser/Shipping` project.

---

## 1. Active Production Pipeline Targets (DO NOT MOVE OR PURGE)

These directories/files are active automated data ingestion targets connected to GitHub Actions workflows. Modifying their paths will break automated production updates:

| Path | Responsible Workflow | Scraper / Script | Description |
| :--- | :--- | :--- | :--- |
| `docs/alibra_data/` | `.github/workflows/alibra_poller.yml` | `scripts/alibra_poller.py`<br>`scripts/integrate_alibra_feed.py` | Runs 2x daily (07:00 & 16:00 UTC). Stores forward curves, time charter archives, and transaction logs. |
| `docs/data/flows/all_flows_summary.json` | `.github/workflows/daily_update.yml` | `scripts/fetch_flows_shipping.py` | Updated daily during master pipeline sync. Consolidates capital flows across shipping ETFs. |

---

## 2. Regulatory SEC Filings & Fund Prospectuses

These PDFs provide legal contract specifications and audited investment holdings. Referenced by `scripts/contract_spec_registry.py`, `scripts/cross_check_cftc_10q.py`, and `scripts/verify_acquisition_manifests.py`:

- `BDRY-BWET_Form10-Q_March-31-2026.pdf`: Form 10-Q Quarterly Report for Breakwave ETF series.
- `Amplify_BDRY_FactSheet.pdf` & `Amplify_BDRY_Prospectus.pdf`: Amplify Breakwave Dry Bulk ETF disclosures.
- `Amplify_BWET_FactSheet.pdf` & `Amplify_BWET_Prospectus.pdf`: Amplify Breakwave Tanker ETF disclosures.
- `Global Maritime Intelligence Sources.pdf`: Global maritime data landscape documentation.

---

## 3. Master Operational Registers & Manuals

Authoritative manuals guiding data acquisition, broker extraction, and verification:

- `EXTRACTION_REGISTER.md`: Master ledger of all 25 publishers, document counts, extraction status, and series CSVs.
- `MASTER_EXTRACTION_MANUAL.md`: Operating procedures for LiteParse, PyMuPDF, and LlamaParse extractions.
- `MASTER_HANDOFF.md`: Comprehensive engineering state, known publisher layout anomalies, and recovery routines.
- `OVERNIGHT_STATE.md`: Log of supervisor sweeps and background extraction runs.
- `DATASETS.md`: Data catalog detailing tables, feeds, and update cadences.

---

## 4. Forensic Research Verdicts & Publisher Surveys

Over 50 deep-dive technical evaluations and audits across maritime brokers and indices:

### Broker Evaluations
- `advanced_shipping`: `docs/prose_merge_verdict.md`
- `affinity`: `docs/affinity_tanker_verdict.md`
- `agora`: `docs/agora_survey.md`, `docs/agora_verdict.md`
- `banchero_costa`: `docs/banchero_cipher_forensics.md`, `docs/banchero_verdict.md`, `docs/bancosta_*`
- `clarksons`: `docs/clarksons_verdict.md`
- `fearnleys`: `docs/fearnleys_survey.md`, `docs/fearnleys_verdict.md`, `docs/fearnleys_extraction_record.md`
- `hellenic`: `docs/hellenic_coverage_verdict.md`
- `intermodal`: `docs/intermodal_verdict.md`, `docs/intermodal_indicative_verdict.md`, `docs/intermodal_charts_STATE.md`
- `ism`: `docs/ism_survey.md`, `docs/ism_verdict.md`, `docs/ism_residual_verdict.md`
- `lion`: `docs/lion_survey.md`, `docs/lion_verdict.md`
- `poten`: `docs/poten_survey.md`
- `star_asia`: `docs/star_asia_survey.md`, `docs/star_asia_verdict.md`, `docs/star_asia_deals_dates_verdict.md`
- `xclusiv`: `docs/xclusiv_survey.md`, `docs/xclusiv_verdict.md`, `docs/xclusiv_charts_*`

### Commodity & Port Logistics
- `ppa`: `docs/ppa_survey.md`, `docs/ppa_verdict.md`, `docs/PPA_ALREADY_EXTRACTED_FINDING.md`
- `cargo`: `docs/cargo_trade_flows_audit.md`, `docs/CARGO_TAB_AUDIT_2026-09-17.md`

### Container Indices
- `drewry_wci`: `docs/drewry_wci_composite_verdict.md`, `docs/drewry_wci_era2021_verdict.md`, `docs/drewry_wci_fabrication_verdict.md`

---

## 5. Subdirectories

- `alibra_data/`: Active poller target (see Section 1).
- `data/flows/`: Active flow target (see Section 1).
- `Newest Data/`: Data discovery documentation, implementation plans, and Excel references from August 2026.
- `gap_fill/`: Audit trail and transition scripts from September 2026.
- `reference/`: Reference materials and API guides (UN Comtrade, TrackInsight).
- `research/`: Research notes and prompts.
- `screenshots/`: Visual verification screenshots.
