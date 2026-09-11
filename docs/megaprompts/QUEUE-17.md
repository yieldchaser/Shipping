# QUEUE-17 — work queue for `17-finish-line.md`

Phase 0 commit: `<fill in>`

Format: `ID | STATUS | proof (test or command → result) | note`
STATUS ∈ TODO · DONE · BLOCKED. Work top to bottom. Update in place. No prose.

## Phase 0 — proof machinery (must FAIL on current code; write baseline counts)
Q-001 | TODO | tests/test_loader_contracts.py → baseline fails: ___ | 
Q-002 | TODO | tests/test_no_empty_modules.py → baseline fails: ___ |
Q-003 | TODO | tests/test_ui_copy_lint.py → baseline fails: ___ |
Q-004 | TODO | tests/test_design_lint.py → baseline fails: ___ |
Q-005 | TODO | tests/test_layout.py → baseline fails: ___ |
Q-006 | TODO | tests/test_perf_budget.py → baseline fails: ___ |
Q-007 | TODO | tests/test_tooltip_coverage.py → baseline fails: ___ |
Q-008 | TODO | commit phase 0; hash recorded above |

## Phase 1 — blank modules
Q-010 | TODO | SGX futures x7: settlement→price (restore from 253691965) |
Q-011 | TODO | SGX iron-ore forward curve: fef_settle/m65f_settle/lpf |
Q-012 | TODO | time_charter_rates.csv mapping |
Q-013 | TODO | iron_ore_restocking.csv mapping |
Q-014 | TODO | vessel_valuations.csv mapping |
Q-015 | TODO | scrappage_prices.csv mapping |
Q-016 | TODO | time_charter_rates_fearnleys.csv + intermodal_tc_rates.csv |
Q-017 | TODO | lpg_spot_rates / lpg_charter_rates / lng_charter_rates |
Q-018 | TODO | tanker_forward_curves (+ _history) |
Q-019 | TODO | drewry_wci_historical / fbx_historical |
Q-020 | TODO | usda_grain_vessel_rates_japan / usda_us_vs_brazil_landed_costs / usda_bunker_fuel_daily |
Q-021 | TODO | usda_grain_vessel_loading_queues (new columns) |
Q-022 | TODO | brazil_comexstat_exports (long format → pivot) |
Q-023 | TODO | australia_ppa_iron_ore (long format → pivot) / major_miners_quarterly_shipments |
Q-024 | TODO | us_eia_weekly_crude_exports / eu_ets_carbon_daily / ton_mile_utilization_matrix |
Q-025 | TODO | newcastle_coal_exports / australia_req_commodity_exports |
Q-026 | TODO | portwatch_port_congestion (verify aliases are real) |
Q-027 | TODO | every remaining loader flagged by Q-001 |
Q-028 | TODO | Broker Desk Overview "cache unavailable" (renderFearnOverview) |
Q-029 | TODO | Signals lead-lag "Insufficient overlapping data" |
Q-030 | TODO | Signals ETF premium/discount z-score stuck "Loading..." |
Q-031 | TODO | test_loader_contracts + test_no_empty_modules green; screenshots Signals + Broker Desk overview |

## Phase 2 — self-updating (before 2026-09-17)
Q-040 | TODO | usda_weekly.yml no longer overwrites usda_grain_vessel_loading_queues.csv; calls fetch_usda_grain_queues.py |
Q-041 | TODO | monthly_trade_flows.yml wiring all 11 fetchers + build_cargo_cache + build_provenance_manifest |
Q-042 | TODO | incremental Fearnleys continuous refresh in daily job |
Q-043 | TODO | generate_stable_imo() removed; F7 rule + mutation test |
Q-044 | TODO | fetch_braemar_strip.py + daily schedule ~17:45 UTC |
Q-045 | TODO | Braemar intraday 30-min poll for one London session → result: live mark / daily close |
Q-046 | TODO | Braemar shown once (Broker Desk Overview) with SGX comparison; removed from other sub-tabs |
Q-047 | TODO | gh workflow run monthly_trade_flows.yml → run URL: ___ (after operator pushes) |

## Phase 3 — trader-facing copy
Q-050 | TODO | test_ui_copy_lint green |
Q-051 | TODO | provenance line "Source · through <date>" replaces all status pills |
Q-052 | TODO | Flow matrix: remove reality/audit block, "Canonical", corridor column, coverage badges |
Q-053 | TODO | Flow matrix volume: fixtures-with-qty + median parcel; parcel sanity filter; find "Other Minor Cargoes 3,269.6 Mt" unit error |
Q-054 | TODO | remove "Signal Ocean Taxonomy Audit" block |
Q-055 | TODO | count badges next to titles removed |

## Phase 4 — wrong / typed numbers
Q-060 | TODO | chokepoint_transit_metrics.csv: built by script + registered, or deleted |
Q-061 | TODO | Cape delay computed from distances + stated speed; formula in tooltip |
Q-062 | TODO | Tonne-mile expansion KPI removed |
Q-063 | TODO | transit count from PortWatch, not the CSV |
Q-064 | TODO | "+53.9% vs baseline" sign bug fixed; test that box and KPI agree |
Q-065 | TODO | "editorial estimate" milestone text removed |
Q-066 | TODO | Baltic code suffix + tooltip on every evidenced route series; none on unverified |

## Phase 5 — layout & design
Q-070 | TODO | "Cargo & Trade Flows" → "Cargo"; tab bar fits at 1366 and 1920 |
Q-071 | TODO | Tracking rebuilt on Signal Ocean pattern; no page scroll for primary view at 1920×1080; screenshots 1920 + 1366 |
Q-072 | TODO | test_design_lint green (left-border accents, glows, blur, emoji) |
Q-073 | TODO | test_layout (b) column balance green on every tab |

## Phase 6 — speed & tooltips (Prompt 16 A+B)
Q-080 | TODO | test_perf_budget green; before/after table |
Q-081 | TODO | test_tooltip_coverage ≥95% every tab |
Q-082 | TODO | SHA-256 hash tooltip leak fixed |

## Phase 7 — data complete & current (Prompt 15 B–D)
Q-090 | TODO | ComexStat Aug 2026 (2024→latest via ComexStat) |
Q-091 | TODO | data_through / staleness_state on every manifest entry; 42 unknown spans resolved |
Q-092 | TODO | GACC bulletin tonnes 2018→Aug 2026 → Who Feeds China |
Q-093 | TODO | JODI tanker flows module |
Q-094 | TODO | EIA LNG exports module |
Q-095 | TODO | India TradeStat coal imports |
Q-096 | TODO | ABS MERCH_EXP Australia by state/destination |
Q-097 | TODO | docs/DATA_COVERAGE.md generated |

## Phase 8 — final
Q-100 | TODO | full pytest + detector + citations green |
Q-101 | TODO | git diff <phase0> -- tests/ additions only |
Q-102 | TODO | 12 tab screenshots → docs/screenshots/17/ |
Q-103 | TODO | totals: DONE __ / BLOCKED __ · final commit __ |
