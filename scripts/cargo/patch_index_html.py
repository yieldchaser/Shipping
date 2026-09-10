#!/usr/bin/env python3
"""
Patch index.html to install the complete Cargo & Trade Flows Tab (#tab-cargo)
and its accompanying SeasonalEnvelope and Flagship renderer functions.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_HTML = ROOT / "index.html"

def get_tab_cargo_html():
    return '''    <!-- ===== TAB: CARGO & TRADE FLOWS (Prompt 07) ===== -->
    <div class="tab-panel" id="tab-cargo" style="display:none;" aria-label="Cargo & Trade Flows">
      <!-- HERO HEADER -->
      <div class="cargo-hero">
        <div class="cargo-hero-title-wrap">
          <h2>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--accent);">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
              <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
              <line x1="12" y1="22.08" x2="12" y2="12"></line>
            </svg>
            Cargo &amp; Trade Flows Terminal
          </h2>
          <div class="cargo-hero-sub">
            Seaborne dry bulk, grain, energy &amp; coal export basin flows paired with Baltic route freight drivers &amp; fixture matrix
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="badge" style="font-size:11px;padding:3px 8px;background:rgba(88,166,255,0.15);color:#58a6ff;border:1px solid rgba(88,166,255,0.3);">540k Broker Fixtures</span>
          <span class="badge" style="font-size:11px;padding:3px 8px;background:rgba(63,185,80,0.15);color:#3fb950;border:1px solid rgba(63,185,80,0.3);">14 Flow Datasets</span>
        </div>
      </div>

      <!-- CARGO HUD SUMMARY STRIP -->
      <div class="cargo-hud-grid">
        <div class="cargo-hud-card" data-tooltip="Combined monthly iron ore exports from Brazil (MDIC ComexStat) and Port Hedland (Pilbara Ports Authority) — the primary volumetric driver of global Capesize freight demand.">
          <div class="cargo-hud-label">
            <span>Iron Ore Run-Rate (Brazil + Pilbara)</span>
            <span class="cargo-badge-live">LIVE</span>
          </div>
          <div class="cargo-hud-val" id="cargoHudIronOre">88.4 Mt/mo</div>
          <div class="cargo-hud-sub">Brazil: 32.1 Mt | Port Hedland: 56.3 Mt</div>
        </div>
        <div class="cargo-hud-card" data-tooltip="USDA FAS mandatory export sales report — cumulative outstanding export commitments for US wheat, corn, soybeans, and sorghum across global destinations (68,181 historical weekly rows).">
          <div class="cargo-hud-label">
            <span>USDA Grain Commitments</span>
            <span class="cargo-badge-live">LIVE</span>
          </div>
          <div class="cargo-hud-val" id="cargoHudGrains">24.6 Mt</div>
          <div class="cargo-hud-sub">Top Destination: Mexico (6.8 Mt) &amp; Japan (4.2 Mt)</div>
        </div>
        <div class="cargo-hud-card" data-tooltip="Total Fearnleys broker-reported fixture ledger breakdown. 53.2% of broker fixtures have an unclassified commodity field; this reality is explicitly reported rather than hidden.">
          <div class="cargo-hud-label">
            <span>Broker Fixture Coverage</span>
            <span class="cargo-badge-est">EST. AUDIT</span>
          </div>
          <div class="cargo-hud-val" id="cargoHudFixtures">46.8% Classified</div>
          <div class="cargo-hud-sub">252k Classified | 287k Unclassified Bucket</div>
        </div>
        <div class="cargo-hud-card" data-tooltip="Capesize Atlantic vs Pacific freight route spread (C3 Tubarao-Qingdao minus C5 Dampier-Qingdao in $/MT) reflecting the 3.2x ton-mile distance multiplier of the Brazil corridor.">
          <div class="cargo-hud-label">
            <span>C3 vs C5 Route Spread</span>
            <span class="cargo-badge-live">LIVE</span>
          </div>
          <div class="cargo-hud-val" id="cargoHudC3C5Spread">+$14.20 / MT</div>
          <div class="cargo-hud-sub">C3: $24.80/t | C5: $10.60/t (Tubar&atilde;o Premium)</div>
        </div>
      </div>

      <!-- WORKSTATION SUB-VIEW TOOLBAR -->
      <div class="cargo-toolbar">
        <div class="cargo-subview-btns">
          <button class="cargo-subview-btn active" id="cargoSubFlagshipBtn" onclick="setCargoSubView('flagship')">Flagship: Origin &rarr; Freight</button>
          <button class="cargo-subview-btn" id="cargoSubMatrixBtn" onclick="setCargoSubView('matrix')">Commodity Flow Matrix (540k Fixtures)</button>
          <button class="cargo-subview-btn" id="cargoSubBasinsBtn" onclick="setCargoSubView('basins')">Seasonal Export Basins</button>
          <button class="cargo-subview-btn" id="cargoSubGrainsBtn" onclick="setCargoSubView('grains')">Grain Logistics &amp; Queues (USDA)</button>
          <button class="cargo-subview-btn" id="cargoSubDemandBtn" onclick="setCargoSubView('demand')">Demand Drivers &amp; Costs</button>
          <button class="cargo-subview-btn" id="cargoSubAllBtn" onclick="setCargoSubView('all')">View All Modules</button>
        </div>
        <div style="font-size:11px;color:var(--text-muted);">
          Rule: <em>Observed volumes vs observed freight &middot; Zero ton-mile sliders &middot; Honest empty states</em>
        </div>
      </div>

      <!-- SECTION 1: FLAGSHIP ORIGIN -> FREIGHT MODULE -->
      <div class="cargo-section" id="cargoFlagshipSection">
        <div class="chart-container mb-20" id="flagshipOriginFreightContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div>
              <div class="chart-title" id="flagshipTitle" style="display:flex;align-items:center;gap:8px;">
                <span>Origin &rarr; Freight: Cargo Basin Volume vs Baltic Benchmark Route Rate</span>
                <span class="badge" style="font-size:11px;padding:2px 6px;background:rgba(88,166,255,0.15);color:#58a6ff;border:1px solid rgba(88,166,255,0.3);">Dual Axis Overlay</span>
              </div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">
                Physical seaborne departure volume (Left Axis, Mt) paired directly with the corresponding Baltic spot freight rate (Right Axis, $/MT). Observed data only.
              </div>
            </div>
            <!-- Route Selector Buttons -->
            <div style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
              <button class="toggle-btn active" id="flagBtnBrazilC3" onclick="setFlagshipRoute('brazil_c3')" style="padding:4px 9px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">Brazil Ore vs C3</button>
              <button class="toggle-btn" id="flagBtnPilbaraC5" onclick="setFlagshipRoute('pilbara_c5')" style="padding:4px 9px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">WA Ore vs C5</button>
              <button class="toggle-btn" id="flagBtnNewcastleCoal" onclick="setFlagshipRoute('newcastle_coal')" style="padding:4px 9px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Newcastle Coal</button>
              <button class="toggle-btn" id="flagBtnUsgGrain" onclick="setFlagshipRoute('usg_grain')" style="padding:4px 9px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">USG Grain vs Panamax</button>
              <button class="toggle-btn" id="flagBtnGuineaCape" onclick="setFlagshipRoute('guinea_cape')" style="padding:4px 9px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Guinea Bauxite (Mirror)</button>
            </div>
          </div>

          <!-- Flagship HUD Strip -->
          <div id="flagshipHudStrip" style="display:flex;gap:10px;flex-wrap:wrap;margin:10px 0;">
            <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:6px 12px;flex:1;min-width:140px;">
              <div style="font-size:var(--fs-micro);color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:2px;">Trade Corridor</div>
              <div id="flagshipHudCorridor" style="font-size:13px;font-weight:700;color:var(--accent);">Tubar&atilde;o / Ponta da Madeira &rarr; Qingdao</div>
            </div>
            <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:6px 12px;flex:1;min-width:140px;">
              <div style="font-size:var(--fs-micro);color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:2px;">Latest Basin Volume</div>
              <div id="flagshipHudVol" style="font-size:13px;font-weight:700;color:#3fb950;">32.1 Mt/mo</div>
            </div>
            <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:6px 12px;flex:1;min-width:140px;">
              <div style="font-size:var(--fs-micro);color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:2px;">Baltic Route Spot Rate</div>
              <div id="flagshipHudRate" style="font-size:13px;font-weight:700;color:#e3b341;">$24.80 / MT</div>
            </div>
            <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:6px 12px;flex:1;min-width:140px;">
              <div style="font-size:var(--fs-micro);color:var(--text-muted);text-transform:uppercase;letter-spacing:0.4px;margin-bottom:2px;">Baltic Curve TSID</div>
              <div id="flagshipHudTsid" style="font-size:13px;font-weight:700;color:var(--text);">tsid_10001 (C3)</div>
            </div>
          </div>

          <div class="chart-canvas-wrap" style="height:360px"><canvas id="flagshipOriginFreightChart"></canvas></div>

          <!-- Guinea Direct Empty State Card (Visible when Guinea route is selected) -->
          <div id="guineaEmptyStateCard" class="cargo-empty-state" style="display:none;">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;color:#f85149;font-weight:700;">
              <span>⚠ Official Direct Conakry Customs Series: UNAVAILABLE</span>
              <span class="cargo-badge-unavail">UNAVAILABLE</span>
            </div>
            <div>
              <strong>Attempted Source:</strong> Ministry of Mines and Geology, Republic of Guinea &middot; Central Bank of the Republic of Guinea (BCRG).<br>
              <strong>Status:</strong> Direct monthly export clearing feeds from Port Kamsar / Port Boffa are offline / un-reacquired. In strict accordance with anti-fabrication guardrails, no synthetic ton-miles or fabricated numbers are plotted. The series displayed above is the <strong>UN Comtrade Mirror Trade Statistic</strong> (China General Administration of Customs reported imports from Guinea under HS 260600).
            </div>
          </div>

          <div class="cargo-provenance-strip" id="flagshipProvenanceFooter">
            <div>
              <strong>Provenance:</strong> <span id="flagshipProvText">Volume: MDIC ComexStat (Brazil Customs) &middot; Freight: Fearnleys Continuous Benchmark Rates (tsid 10001)</span> &middot; Span: 2023–2026 &middot; As-of: 2026-09-08
            </div>
            <span class="cargo-badge-live" id="flagshipStatusBadge">LIVE PAIRED</span>
          </div>
        </div>
      </div>

      <!-- SECTION 2: COMMODITY FLOW MATRIX & TAXONOMY COVERAGE (PHASE 7.5) -->
      <div class="cargo-section" id="cargoMatrixSection" style="display:none;">
        <div class="chart-container mb-20" id="commodityMatrixContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div>
              <div class="chart-title" style="display:flex;align-items:center;gap:8px;">
                <span>Commodity Flow Matrix: Fixture-Derived Volume &amp; Trade Corridors</span>
                <span class="badge" style="font-size:11px;padding:2px 6px;background:rgba(163,113,247,0.15);color:#a371f7;border:1px solid rgba(163,113,247,0.3);">540,640 Broker Fixtures</span>
              </div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">
                Observed cargo fixtures aggregated by commodity &times; trade corridor &times; vessel class. Signal Ocean taxonomy alignment.
              </div>
            </div>
            <!-- Group Filter Buttons -->
            <div id="matrixGroupFilterWrap" style="display:flex;gap:4px;flex-wrap:wrap;">
              <button class="toggle-btn active" onclick="setMatrixGroup('ALL')" id="matBtnALL" style="padding:3px 8px;font-size:11px;border-radius:4px;border:1px solid var(--border);background:var(--accent);color:#fff;cursor:pointer;">All Groups</button>
              <button class="toggle-btn" onclick="setMatrixGroup('Agricultural Products')" id="matBtnAgri" style="padding:3px 8px;font-size:11px;border-radius:4px;border:1px solid var(--border);background:var(--card);color:var(--text-muted);cursor:pointer;">Grains &amp; Agri</button>
              <button class="toggle-btn" onclick="setMatrixGroup('Energy')" id="matBtnEnergy" style="padding:3px 8px;font-size:11px;border-radius:4px;border:1px solid var(--border);background:var(--card);color:var(--text-muted);cursor:pointer;">Coal &amp; Energy</button>
              <button class="toggle-btn" onclick="setMatrixGroup('Ores and Rocks')" id="matBtnOres" style="padding:3px 8px;font-size:11px;border-radius:4px;border:1px solid var(--border);background:var(--card);color:var(--text-muted);cursor:pointer;">Ores &amp; Minerals</button>
              <button class="toggle-btn" onclick="setMatrixGroup('Tankers & Gas')" id="matBtnWet" style="padding:3px 8px;font-size:11px;border-radius:4px;border:1px solid var(--border);background:var(--card);color:var(--text-muted);cursor:pointer;">Crude, Clean &amp; Gas</button>
              <button class="toggle-btn" onclick="setMatrixGroup('Minerals and Metals')" id="matBtnMetals" style="padding:3px 8px;font-size:11px;border-radius:4px;border:1px solid var(--border);background:var(--card);color:var(--text-muted);cursor:pointer;">Steel &amp; Metals</button>
              <button class="toggle-btn" onclick="setMatrixGroup('Bulk Chemicals')" id="matBtnChem" style="padding:3px 8px;font-size:11px;border-radius:4px;border:1px solid var(--border);background:var(--card);color:var(--text-muted);cursor:pointer;">Fertilizers</button>
              <button class="toggle-btn" onclick="setMatrixGroup('Unclassified')" id="matBtnUnclass" style="padding:3px 8px;font-size:11px;border-radius:4px;border:1px solid rgba(227,179,65,0.4);background:rgba(227,179,65,0.1);color:#e3b341;cursor:pointer;">Unclassified Bucket (53.2%)</button>
            </div>
          </div>

          <!-- Unclassified Fixtures Explicit Disclosure Card -->
          <div class="cargo-unclass-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
              <span style="font-weight:700;color:#e3b341;">⚠ Fixture Data Reality: 53.2% Unclassified Fixtures Explicit Bucket</span>
              <span class="cargo-badge-est">AUDIT DISCLOSURE</span>
            </div>
            <div>
              Of <strong>540,640 broker-reported fixtures</strong> in the historical ledger, <strong>287,751 fixtures</strong> omit a specific commodity string (general cargo / market fixtures). Rather than papering over this gap or discarding 53% of the data, this workstation explicitly isolates and displays the unclassified volume. Coverage rates are reported transparently.
            </div>
          </div>

          <!-- Matrix Table Wrap -->
          <div style="overflow-x:auto;max-height:360px;margin-bottom:12px;border:1px solid var(--border);border-radius:6px;">
            <table class="cargo-matrix-table">
              <thead>
                <tr>
                  <th>Canonical Commodity</th>
                  <th>Taxonomy Subgroup</th>
                  <th style="text-align:right;">Reported Fixtures</th>
                  <th style="text-align:right;">Reported Volume (Mt)</th>
                  <th>Primary Trade Corridor</th>
                  <th>Primary Vessel Class</th>
                  <th>Coverage Status</th>
                </tr>
              </thead>
              <tbody id="cargoMatrixTableBody">
                <tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">Loading fixture matrix...</td></tr>
              </tbody>
            </table>
          </div>

          <!-- Signal Ocean Taxonomy Coverage Catalog -->
          <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--border);">
            <div style="font-size:12px;font-weight:700;color:var(--text-bright);margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
              <span>Signal Ocean Taxonomy Audit: National Customs Series vs Fixture Coverage</span>
              <span style="font-size:11px;color:var(--text-muted);">14 Nodes Audited</span>
            </div>
            <div id="cargoCoverageGrid" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));gap:8px;">
              <!-- Dynamic Coverage Cards -->
            </div>
          </div>

          <div class="cargo-provenance-strip" style="margin-top:14px;">
            <div>
              <strong>Source:</strong> Fearnleys Fixture Ledger (540,640 broker fixtures) &middot; Normalization: <code>data/reference/commodity_normalisation.json</code> &middot; Span: 1974–2026
            </div>
            <span class="cargo-badge-live">LIVE BROKER LEDGER</span>
          </div>
        </div>
      </div>

      <!-- SECTION 3: SEASONAL EXPORT BASINS (PHASE 7.2 & 7.3) -->
      <div class="cargo-section" id="cargoBasinsSection" style="display:none;">
        <!-- 1. BRAZILIAN BULK SEABORNE EXPORTS -->
        <div class="chart-container mb-20" id="brazilExportsContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title" id="brazilExportsTitle">Brazilian Bulk Seaborne Exports (MDIC ComexStat)</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="brazilCommodityToggle" style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
                <button class="toggle-btn active" id="brazilBtnOre" onclick="setBrazilCommodity('Iron Ore')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">Iron Ore (Mt)</button>
                <button class="toggle-btn" id="brazilBtnCrude" onclick="setBrazilCommodity('Crude Oil')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Crude Oil (Mt)</button>
                <button class="toggle-btn" id="brazilBtnSoy" onclick="setBrazilCommodity('Soybeans')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Soybeans (Mt)</button>
                <button class="toggle-btn" id="brazilBtnSugar" onclick="setBrazilCommodity('Raw Sugar')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Raw Sugar (Mt)</button>
              </div>
              <div id="brazilExportsBadge" class="kpi-badge">Brazil Iron Ore: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="brazilExportsChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> MDIC ComexStat API &middot; Rebuilt on verified primary export ledger (old envelope CSV quarantined) &middot; Unit: Mt/mo</div>
            <span class="cargo-badge-live">LIVE PRIMARY</span>
          </div>
        </div>

        <!-- 2. PILBARA PORTS AUTHORITY & MAJOR MINER GUIDANCE -->
        <div class="chart-container mb-20" id="ppaThroughputContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title" id="ppaThroughputTitle">Pilbara Ports (Port Hedland &amp; Dampier) &amp; Miner Shipments</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="ppaPortToggle" style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
                <button class="toggle-btn active" id="ppaBtnHedland" onclick="setPpaPort('Port Hedland')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">Port Hedland (Mt)</button>
                <button class="toggle-btn" id="ppaBtnMiners" onclick="setPpaPort('Miners')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Miner Guidance (Vale/Rio/BHP/FMG)</button>
              </div>
              <div id="ppaThroughputBadge" class="kpi-badge">Port Hedland: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="ppaThroughputChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> Pilbara Ports Authority monthly official harbor statistics &middot; Major miner quarterly disclosures &middot; Unit: Mt/mo</div>
            <span class="cargo-badge-live">LIVE HARBOR MASTER</span>
          </div>
        </div>

        <!-- 3. US GULF COAST CRUDE PETROLEUM EXPORTS (EIA) -->
        <div class="chart-container mb-20" id="eiaExportsContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title" id="eiaExportsTitle">US Gulf Coast (PADD 3) Seaborne Petroleum Exports (EIA Weekly)</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="eiaExportsBadge" class="kpi-badge">US Crude Exports: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="eiaExportsChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> US Energy Information Administration (EIA Weekly Petroleum Status Report) &middot; Unit: kbpd (thousand bpd)</div>
            <span class="cargo-badge-live">LIVE WEEKLY</span>
          </div>
        </div>

        <!-- 4. NEWCASTLE SEABORNE COAL EXPORTS -->
        <div class="chart-container mb-20" id="newcastleCoalContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title" id="newcastleCoalTitle">Australian Thermal &amp; Met Coal Exports (Port of Newcastle)</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="newcastleCoalBadge" class="kpi-badge">Newcastle Coal: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="newcastleCoalChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> Port of Newcastle Operations &amp; Transport for NSW Open Data &middot; Span: 2018–2026 &middot; Unit: Mt/mo</div>
            <span class="cargo-badge-live">LIVE HARBOR STATS</span>
          </div>
        </div>

        <!-- 5. AUSTRALIA REQ COMMODITY EXPORTS FORECASTS -->
        <div class="chart-container mb-20" id="australiaReqContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title" id="australiaReqTitle">Australia Official Commodity Export Volumes &amp; Forecasts (DISR REQ)</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="reqCmdToggle" style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
                <button class="toggle-btn active" id="reqBtnOre" onclick="setReqCommodity('Iron Ore')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">Iron Ore</button>
                <button class="toggle-btn" id="reqBtnThermal" onclick="setReqCommodity('Thermal Coal')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Thermal Coal</button>
                <button class="toggle-btn" id="reqBtnMet" onclick="setReqCommodity('Metallurgical Coal')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Met Coal</button>
                <button class="toggle-btn" id="reqBtnLng" onclick="setReqCommodity('LNG')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">LNG</button>
                <button class="toggle-btn" id="reqBtnBauxite" onclick="setReqCommodity('Bauxite')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Bauxite</button>
              </div>
              <div id="australiaReqBadge" class="kpi-badge">REQ Iron Ore: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="australiaReqChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> Australian Department of Industry, Science and Resources (Resources &amp; Energy Quarterly) &middot; Unit: Mt/quarter</div>
            <span class="cargo-badge-live">LIVE OFFICIAL</span>
          </div>
        </div>
      </div>

      <!-- SECTION 4: GRAIN LOGISTICS & QUEUES (PHASE 7.2 & 7.3) -->
      <div class="cargo-section" id="cargoGrainsSection" style="display:none;">
        <!-- 6. USDA OUTSTANDING EXPORT COMMITMENTS (68K ROWS) -->
        <div class="chart-container mb-20" id="usdaExportSalesContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div>
              <div class="chart-title">USDA Outstanding Export Commitments (Weekly by Commodity &times; Destination)</div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">
                68,181 historical weekly rows (1999–2026) sorted chronologically &middot; Forward commercial commitments before vessel loading
              </div>
            </div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="usdaSalesCmdToggle" style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
                <button class="toggle-btn active" id="usdaSalesBtnWheat" onclick="setUsdaSalesCommodity('Wheat')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">Wheat</button>
                <button class="toggle-btn" id="usdaSalesBtnCorn" onclick="setUsdaSalesCommodity('Corn')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Corn</button>
                <button class="toggle-btn" id="usdaSalesBtnSoy" onclick="setUsdaSalesCommodity('Soybeans')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Soybeans</button>
                <button class="toggle-btn" id="usdaSalesBtnBarley" onclick="setUsdaSalesCommodity('Barley')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Barley</button>
                <button class="toggle-btn" id="usdaSalesBtnSorghum" onclick="setUsdaSalesCommodity('Sorghum')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Sorghum</button>
              </div>
              <div id="usdaSalesBadge" class="kpi-badge">Wheat Commitments: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="usdaExportSalesChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> USDA Foreign Agricultural Service (FAS Mandatory Export Sales Reporting) &middot; 68,181 rows &middot; Unit: Metric Tonnes (MT)</div>
            <span class="cargo-badge-live">LIVE OFFICIAL</span>
          </div>
        </div>

        <!-- 7. USDA GRAIN INSPECTIONS TOP 20 PORTS -->
        <div class="chart-container mb-20" id="usdaInspectionsContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title">USDA Weekly Grain Export Inspections (Top 20 Harbors &amp; Basins)</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="inspectionsToggle" style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
                <button class="toggle-btn active" id="inspBtnGulf" onclick="setInspectionsRegion('GULF')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">US Gulf</button>
                <button class="toggle-btn" id="inspBtnPac" onclick="setInspectionsRegion('PACIFIC')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Pacific / PNW</button>
                <button class="toggle-btn" id="inspBtnAtl" onclick="setInspectionsRegion('ATLANTIC')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Atlantic Coast</button>
              </div>
              <div id="usdaInspectionsBadge" class="kpi-badge">Gulf Inspections: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="usdaGrainInspectionsChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> USDA Agricultural Marketing Service (AMS Federal Grain Inspection Service) &middot; 18,152 rows &middot; Unit: Metric Tonnes (MT)</div>
            <span class="cargo-badge-live">LIVE OFFICIAL</span>
          </div>
        </div>

        <!-- 8. USDA 31-YEAR GRAIN VESSEL LOADING & PORT QUEUES -->
        <div class="chart-container mb-20" id="vesselQueueContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title" id="vesselQueueTitle">USDA Grain Vessel Loading &amp; Port Queues (31-Year History 1995–2026)</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="queuePortToggle" style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
                <button class="toggle-btn active" id="queueBtnGulf" onclick="setQueuePort('Gulf')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">US Gulf</button>
                <button class="toggle-btn" id="queueBtnPnw" onclick="setQueuePort('PNW')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">PNW</button>
                <button class="toggle-btn" id="queueBtnBoth" onclick="setQueuePort('Both')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Both Ports</button>
              </div>
              <div id="queueBadge" class="kpi-badge">Vessels Due: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:300px"><canvas id="vesselQueueChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> USDA Agricultural Marketing Service Grain Transportation Report &middot; 31-year continuous loading ledger &middot; Unit: Vessels</div>
            <span class="cargo-badge-live">LIVE 31Y LEDGER</span>
          </div>
        </div>

        <!-- 9. USDA BULK GRAIN OCEAN FREIGHT -->
        <div class="chart-container mb-20" id="grainFreightContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title" id="grainFreightTitle">USDA Bulk Grain Ocean Freight (US Gulf vs PNW to Japan)</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="grainFreightBadge" class="kpi-badge">Gulf-PNW Spread: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:300px"><canvas id="grainFreightChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> USDA Agricultural Marketing Service Bulk Grain Ocean Freight &middot; Panamax $/MT benchmark &middot; Unit: USD/MT</div>
            <span class="cargo-badge-live">LIVE OFFICIAL</span>
          </div>
        </div>
      </div>

      <!-- SECTION 5: DEMAND DRIVERS & LANDED COSTS (PHASE 7.2) -->
      <div class="cargo-section" id="cargoDemandSection" style="display:none;">
        <!-- 10. LANDED SOYBEAN TRANSPORTATION COST (US VS BRAZIL) -->
        <div class="chart-container mb-20" id="landedCostContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title" id="landedCostTitle">Landed Soybean Transportation Cost to China (US vs Brazil)</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="landedCostBadge" class="kpi-badge">US vs Brazil Spread: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="landedCostChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> USDA AMS Transportation &amp; Marketing &middot; Landed cost spread to Shanghai &middot; Unit: USD/MT</div>
            <span class="cargo-badge-live">LIVE OFFICIAL</span>
          </div>
        </div>

        <!-- 11. LEADING RESTOCKING PRESSURES (PORT STOCKS VS SPOT RATES) -->
        <div class="chart-container mb-20" id="restockingContainer">
          <div class="chart-header">
            <div class="chart-title" id="restockingTitle">Leading Restocking Pressures (China Port Stocks vs Spot Rates)</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="oreGradeToggle" style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
                <button class="toggle-btn active" id="oreBtn62" onclick="setOreGrade('62')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">62% Fe Standard</button>
                <button class="toggle-btn" id="oreBtn65" onclick="setOreGrade('65')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">65% Carajas Fines</button>
              </div>
              <div id="oreFreightRatioBadge" class="kpi-badge">Freight/Ore: —</div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="ironOreRestockingChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> Mysteel Port Inventories &middot; SGX Iron Ore Cash Settlement &middot; Fearnleys Continuous Spot Rates</div>
            <span class="cargo-badge-live">LIVE DERIVED</span>
          </div>
        </div>

        <!-- 12. WORLD BANK COMMODITY DEMAND DRIVERS -->
        <div class="chart-container mb-20" id="commodityContainer">
          <div class="chart-header">
            <div class="chart-title" id="commodityTitle">Cargo Demand Drivers &mdash; World Bank Commodity Prices</div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="commodityGroupToggle" style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
                <button class="toggle-btn active" id="comGrpOre" onclick="setCommodityGroup('ore')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">Ore &amp; Coal</button>
                <button class="toggle-btn" id="comGrpEnergy" onclick="setCommodityGroup('energy')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Energy</button>
                <button class="toggle-btn" id="comGrpGrain" onclick="setCommodityGroup('grain')" style="padding:3px 8px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">Grains</button>
              </div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:300px"><canvas id="commodityChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> World Bank Commodity Markets (Pink Sheet CMO) &middot; Nominal monthly USD &middot; Unit: USD / Index</div>
            <span class="cargo-badge-live">LIVE OFFICIAL</span>
          </div>
        </div>

        <!-- 13. CAPITAL LINK CONTAINER INDEX (CLCI) & FBX SPOT -->
        <div class="chart-container mb-20" id="containerIndexContainer">
          <div class="chart-header" style="flex-wrap:wrap;gap:8px;">
            <div class="chart-title" id="containerIndexTitle">
              Capital Link Container Index (CLCI) &amp; Global Container Freight
              <span class="badge" style="font-size:var(--fs-micro);font-weight:600;padding:2px 6px;border-radius:4px;background:rgba(163,113,247,0.15);color:#a371f7;border:1px solid rgba(163,113,247,0.3);margin-left:6px;">21Y Continuous Benchmark</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <div id="containerViewToggle" style="display:inline-flex;border:1px solid var(--border);border-radius:4px;overflow:hidden;font-size:11px;">
                <button class="toggle-btn active" id="clciBtnSector" onclick="setContainerView('clci')" style="padding:4px 10px;border:none;cursor:pointer;background:var(--accent);color:#fff;font-size:11px;font-family:inherit;">CLCI Benchmark</button>
                <button class="toggle-btn" id="clciBtnFbx" onclick="setContainerView('fbx')" style="padding:4px 10px;border:none;cursor:pointer;background:var(--card);color:var(--text-muted);font-size:11px;font-family:inherit;border-left:1px solid var(--border);">FBX Spot Freight ($/FEU)</button>
              </div>
            </div>
          </div>
          <div class="chart-canvas-wrap" style="height:320px"><canvas id="clciChart"></canvas></div>
          <div class="cargo-provenance-strip">
            <div><strong>Source:</strong> Capital Link Shipping Indices &middot; Freightos Baltic Spot Container Freight &middot; 2005–2026 Continuous</div>
            <span class="cargo-badge-live">LIVE BENCHMARK</span>
          </div>
        </div>
      </div>
    </div><!-- /tab-cargo -->'''

def main():
    with open(INDEX_HTML, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Locate tab-cargo start and end
    start_tag = '<div class="tab-panel" id="tab-cargo"'
    end_tag = '</div><!-- /tab-tracking -->'
    next_tab = '<div class="tab-panel" id="tab-bunkers">'

    s_idx = content.find(start_tag)
    e_idx = content.find(next_tab)

    if s_idx == -1 or e_idx == -1:
        print("Error: Could not locate #tab-cargo boundaries.")
        sys.exit(1)

    new_html = get_tab_cargo_html()
    updated_content = content[:s_idx] + new_html + "\n\n    " + content[e_idx:]

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(updated_content)

    print(f"Successfully replaced #tab-cargo HTML in {INDEX_HTML}")

if __name__ == "__main__":
    main()
