# QUEUE-17 — work queue for `17-finish-line.md`

Phase 0 commit: `b3ccc2866` · Appendices: A (loaders) · B (UI baseline) · C (freshness) · D (design)

`ID | STATUS | proof (test → result) | note`  ·  STATUS ∈ TODO · DONE · BLOCKED · no prose.

## Phase 0 — proof machinery (must FAIL now; record found-vs-appendix counts)
Q-001 | DONE | test_loader_contracts → found 27+SGX / appendix 27+SGX |
Q-002 | DONE | test_no_console_errors → found 5 tabs failing / appendix 5 |
Q-003 | DONE | test_no_failed_requests → found 0 |
Q-004 | DONE | test_no_empty_states → found 5 items / appendix 5 items |
Q-005 | DONE | test_no_dash_kpis → found 45 / appendix 9 |
Q-006 | DONE | test_charts_have_data → found 8 dead modules / appendix 8 dead modules |
Q-007 | DONE | test_ui_copy_lint → found 22 / appendix ~25 terms + pills |
Q-008 | DONE | test_no_typed_numbers → found 138 nodes / appendix 30 nodes |
Q-009 | DONE | test_design_lint → accents 13/13 glows 49/63 blurs 12/16 emoji 11/11 |
Q-010 | DONE | test_tooltip_coverage → worst tab 23.9% (bunkers) & 52.2% (fearnleys) / appendix 12/65 (Broker Desk) |
Q-011 | DONE | test_layout → nav 1366 hidden · 1920 hidden · clipped 25/20 · 2-col left-heavy |
Q-012 | DONE | test_ui_sweep → found 10 / appendix 10 click failures |
Q-013 | DONE | test_views_fresh → found 28 / appendix 28 frozen views |
Q-014 | DONE | test_workflow_wiring → found 35 / appendix 35 |
Q-015 | DONE | test_single_writer → found 1 / appendix 1 (USDA queues) |
Q-016 | DONE | test_manifest_matches_files → found 37 |
Q-017 | DONE | test_perf_budget → boot 10.58 MB · cumulative 62.0 MB · worst warm 1506 ms |
Q-018 | DONE | allowlist seeded with reasons only for App B/C-approved exceptions |
Q-019 | DONE | commit test(phase0): proof machinery (expected to fail); hash b3ccc2866 |

## Phase 1 — nothing blank (Appendix A + C6)
Q-030 | TODO | SGX 7 files settlement→price (App A §A0) |
Q-031 | TODO | sgx_iron_ore_forward_curve.csv (fef_settle/m65f_settle/lpf) |
Q-032 | TODO | time_charter_rates.csv |
Q-033 | TODO | iron_ore_restocking.csv |
Q-034 | TODO | vessel_valuations.csv (long format) |
Q-035 | TODO | scrappage_prices.csv |
Q-036 | TODO | time_charter_rates_fearnleys.csv + intermodal_tc_rates.csv |
Q-037 | TODO | lpg_spot_rates / lpg_charter_rates / lng_charter_rates |
Q-038 | TODO | tanker_forward_curves (+ history) |
Q-039 | TODO | drewry_wci_historical / fbx_historical |
Q-040 | TODO | usda_grain_vessel_rates_japan / usda_us_vs_brazil_landed_costs / usda_bunker_fuel_daily |
Q-041 | TODO | usda_grain_vessel_loading_queues |
Q-042 | TODO | brazil_comexstat_exports (pivot on commodity) |
Q-043 | TODO | australia_ppa_iron_ore (pivot on port) + major_miners_quarterly_shipments (pivot on miner) |
Q-044 | TODO | us_eia_weekly_crude_exports / eu_ets_carbon_daily / ton_mile_utilization_matrix |
Q-045 | TODO | newcastle_coal_exports / australia_req_commodity_exports |
Q-046 | TODO | portwatch_port_congestion aliases verified (App A §A4) |
Q-047 | TODO | Signals: FFA term structure BDRY + BWET |
Q-048 | TODO | Signals: BDI daily-change contribution |
Q-049 | TODO | Signals: lead-lag correlation |
Q-050 | TODO | Signals: ETF premium/discount z-score |
Q-051 | TODO | Signals: ETF fund flow signals |
Q-052 | TODO | Broker Desk overview "cache unavailable" (renderFearnOverview) |
Q-053 | TODO | Broker Desk TC Rates: 5 n/a KPIs + missing 1Y TC and ratio series |
Q-054 | TODO | Broker Desk S&P & Assets: 2 blank charts, 4 dash KPIs, stuck Loading |
Q-055 | TODO | Tracking: renderTrackingHUDRefreshNote ReferenceError |
Q-056 | TODO | Tracking: disruptions feed empty + hudDisruptionsActive dash |
Q-057 | TODO | tests: loader_contracts + no_empty_states + charts_have_data + ui_sweep green on tabs and sub-views |

## Phase 2 — self-updating (before 2026-09-17)
Q-070 | TODO | pages.yml builds all views/caches before upload (App C §C1) |
Q-071 | TODO | usda_weekly.yml: single writer for the queue file (§C4) |
Q-072 | TODO | verify true writer of each of the 35 files; schedule them (§C2) |
Q-073 | TODO | monthly_trade_flows.yml (Prompt 15 Part A) |
Q-074 | TODO | incremental Fearnleys continuous refresh in the daily job |
Q-075 | TODO | generate_stable_imo() removed + F7 rule + mutation test |
Q-076 | TODO | fetch_braemar_strip.py + daily schedule + dated history |
Q-077 | TODO | Braemar intraday probe result: live mark / daily close = ___ |
Q-078 | TODO | Braemar on Overview only, with SGX comparison |
Q-079 | TODO | static snapshots labelled with as-of (Signal positions etc.) |
Q-080 | TODO | test_views_fresh + test_workflow_wiring + test_single_writer green |

## Phase 3 — trader-facing copy
Q-090 | TODO | test_ui_copy_lint green (every instance in App B) |
Q-091 | TODO | provenance footer line replaces all pills/badges |
Q-092 | TODO | Cargo: reality/audit block + taxonomy audit block deleted |
Q-093 | TODO | "Canonical Commodity" → "Commodity"; unclassified row renamed |
Q-094 | TODO | Braemar header text rewritten |
Q-095 | TODO | file paths / tsid removed from visible text |

## Phase 4 — wrong or typed numbers
Q-100 | TODO | chokepoint_transit_metrics.csv built by script + registered, or deleted |
Q-101 | TODO | Cape delay computed from distances; formula in tooltip |
Q-102 | TODO | tonne-mile expansion KPI removed |
Q-103 | TODO | transit count sourced from PortWatch |
Q-104 | TODO | Cargo HUD tiles render from data; test_no_typed_numbers green |
Q-105 | TODO | "+53.9% vs baseline" sign fixed + consistency test |
Q-106 | TODO | flow matrix: fixtures-with-qty + median parcel + sanity band |
Q-107 | TODO | "Other Minor Cargoes 3,269.6 Mt" unit error found |
Q-108 | TODO | corridor column + coverage badges removed |
Q-109 | TODO | LNG Desk default series + plausibility bands |
Q-110 | TODO | route tiles show full name + Baltic code where evidenced |
Q-111 | TODO | number formatting (no >4 decimals) |

## Phase 5 — layout & design
Q-120 | TODO | tab renamed "Cargo"; nav fits 1366 + 1920 |
Q-121 | TODO | Tracking rebuilt to App D §D4; no page scroll at 1920×1080; screenshots 1920 + 1366 |
Q-122 | TODO | tracking left panel: no horizontal scroll; sub-view defaults always selected |
Q-123 | TODO | sector chips out of the map; legend bottom-left; dangling "WINDOW:" label fixed |
Q-124 | TODO | milestones become a table (no accent-bar cards) |
Q-125 | TODO | design tokens applied; test_design_lint green |
Q-126 | TODO | clipped text fixed (Bunkers 20, LPG labels, route tiles) |
Q-127 | TODO | tooltip coverage ≥95% every tab; three-beat standard; hash-leak tooltip fixed |

## Phase 6 — speed
Q-140 | TODO | ETFs: no re-render on revisit (2.1 s → <50 ms) |
Q-141 | TODO | Tracking: 18.7 MB voyage CSV behind an index + per-vessel shard |
Q-142 | TODO | duplicate port_stress_summary.json fetch removed |
Q-143 | TODO | boot ≤0.5 MB (bunker summary 4.4 MB off boot) |
Q-144 | TODO | cumulative ≤8 MB over 12 tabs; test_perf_budget green |

## Phase 7 — complete & current data (Prompt 15 B–D)
Q-160 | TODO | ComexStat Aug 2026 |
Q-161 | TODO | data_through + staleness_state on all 112 series; 42 unknown spans resolved |
Q-162 | TODO | GACC bulletin tonnes 2018→latest → Who Feeds China |
Q-163 | TODO | JODI tanker flows module |
Q-164 | TODO | EIA LNG exports module |
Q-165 | TODO | India TradeStat coal imports |
Q-166 | TODO | ABS MERCH_EXP Australia |
Q-167 | TODO | docs/DATA_COVERAGE.md generated |

## Phase 8 — final
Q-180 | TODO | full pytest + detector + citations green |
Q-181 | TODO | git diff <phase0> -- tests/ additions only |
Q-182 | TODO | screenshots: 12 tabs + every sub-view → docs/screenshots/17/ |
Q-183 | TODO | totals: DONE __ / BLOCKED __ · final commit __ |
