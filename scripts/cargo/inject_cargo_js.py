#!/usr/bin/env python3
"""
Inject complete Cargo & Trade Flows JavaScript renderers into index.html:
- renderSeasonalEnvelope (reusable 5Y envelope component)
- renderFlagshipOriginFreightChart (dual axis paired module)
- renderCommodityFlowMatrix (540k fixtures + coverage catalog)
- Rebuilt flow modules (Brazil ComexStat, Pilbara Ports, US EIA, Newcastle Coal, REQ, USDA 68k, Inspections, Queues)
- Master renderCargoTab
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_HTML = ROOT / "index.html"

def get_cargo_js():
    return '''    // =====================================================================
    // CARGO & TRADE FLOWS TERMINAL & SEASONAL ENVELOPE ENGINE (PROMPT 07)
    // =====================================================================

    // 1. REUSABLE SEASONAL ENVELOPE COMPONENT
    function renderSeasonalEnvelope(canvasId, options) {
      var canvas = typeof canvasId === 'string' ? document.getElementById(canvasId) : canvasId;
      if (!canvas) return;
      if (typeof Chart === 'undefined') return;

      var labels = options.labels || (options.frequency === 'W' ?
        Array.from({length: 52}, function(_, i) { return 'W' + (i + 1); }) :
        ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      );

      var datasets = [];
      // Invisible baseline for fill
      if (options.min && options.min.length) {
        datasets.push({
          label: '5Y Min',
          data: options.min,
          borderColor: 'transparent',
          backgroundColor: 'transparent',
          pointRadius: 0,
          fill: false
        });
      }
      // Shaded 5Y min/max band
      if (options.max && options.max.length) {
        datasets.push({
          label: '5Y Historical Range (Min-Max)',
          data: options.max,
          borderColor: 'rgba(148, 163, 184, 0.3)',
          borderWidth: 1,
          backgroundColor: 'rgba(148, 163, 184, 0.15)',
          fill: '-1',
          pointRadius: 0
        });
      }
      // 5Y Historical Mean line (orange/amber dashed)
      if (options.mean && options.mean.length) {
        datasets.push({
          label: '5Y Historical Mean',
          data: options.mean,
          borderColor: '#f59e0b',
          borderWidth: 2,
          borderDash: [5, 5],
          pointRadius: 0,
          fill: false
        });
      }
      // Prior Year (slate secondary line)
      var priorYear = options.priorYear || (options.latestYear ? String(Number(options.latestYear) - 1) : '2025');
      if (options.years && options.years[priorYear]) {
        datasets.push({
          label: priorYear + ' (Prior)',
          data: options.years[priorYear],
          borderColor: '#94a3b8',
          borderWidth: 1.5,
          borderDash: [3, 3],
          pointRadius: 2,
          fill: false
        });
      }
      // Current Year (bold blue/teal line)
      var latestYear = options.latestYear || '2026';
      if (options.years && options.years[latestYear]) {
        datasets.push({
          label: latestYear + ' (Current)',
          data: options.years[latestYear],
          borderColor: '#38bdf8',
          borderWidth: 2.5,
          pointRadius: 3,
          pointBackgroundColor: '#38bdf8',
          fill: false
        });
      }
      // Older Years (click-toggleable in legend)
      if (options.years) {
        Object.keys(options.years).sort().reverse().forEach(function(yr) {
          if (yr !== latestYear && yr !== priorYear) {
            datasets.push({
              label: yr,
              data: options.years[yr],
              borderColor: '#64748b',
              borderWidth: 1,
              pointRadius: 0,
              fill: false,
              hidden: true
            });
          }
        });
      }

      var unitStr = options.unit || 'Mt';
      destroyChart(canvas.id);
      updateOrCreateChart(canvas.id, canvas, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: {
              position: 'top',
              labels: {
                usePointStyle: true,
                font: { size: 11 },
                filter: function(item) {
                  return item.text !== '5Y Min';
                }
              }
            },
            tooltip: {
              callbacks: {
                label: function(c) {
                  if (c.dataset.label === '5Y Min') return null;
                  if (c.parsed.y === null || isNaN(c.parsed.y)) return null;
                  return ' ' + c.dataset.label + ': ' + c.parsed.y.toLocaleString() + ' ' + unitStr;
                }
              }
            }
          },
          scales: {
            x: { grid: { color: '#151a22' }, ticks: { color: '#8b949e', font: { size: 11 }, maxTicksLimit: 14 } },
            y: { grid: { color: '#151a22' }, ticks: { color: '#8b949e', font: { size: 11 }, callback: function(v) { return v + ' ' + unitStr; } } }
          }
        }
      });
    }
    window.renderSeasonalEnvelope = renderSeasonalEnvelope;

    // 2. SUBVIEW NAVIGATION
    var _cargoSubView = 'flagship';
    function setCargoSubView(viewKey) {
      window.setCargoSubView = setCargoSubView;
      _cargoSubView = viewKey;

      ['flagship', 'matrix', 'basins', 'grains', 'demand', 'all'].forEach(function(k) {
        var idMap = {
          'flagship': 'cargoSubFlagshipBtn',
          'matrix': 'cargoSubMatrixBtn',
          'basins': 'cargoSubBasinsBtn',
          'grains': 'cargoSubGrainsBtn',
          'demand': 'cargoSubDemandBtn',
          'all': 'cargoSubAllBtn'
        };
        var btn = document.getElementById(idMap[k]);
        if (btn) {
          var active = (k === viewKey);
          btn.classList.toggle('active', active);
          btn.style.background = active ? 'var(--accent)' : 'var(--bg)';
          btn.style.color = active ? '#fff' : 'var(--text-muted)';
          btn.style.borderColor = active ? 'var(--accent)' : 'var(--border)';
        }
      });

      var secFlagship = document.getElementById('cargoFlagshipSection');
      var secMatrix = document.getElementById('cargoMatrixSection');
      var secBasins = document.getElementById('cargoBasinsSection');
      var secGrains = document.getElementById('cargoGrainsSection');
      var secDemand = document.getElementById('cargoDemandSection');

      if (viewKey === 'all') {
        if (secFlagship) secFlagship.style.display = 'block';
        if (secMatrix) secMatrix.style.display = 'block';
        if (secBasins) secBasins.style.display = 'block';
        if (secGrains) secGrains.style.display = 'block';
        if (secDemand) secDemand.style.display = 'block';
      } else {
        if (secFlagship) secFlagship.style.display = (viewKey === 'flagship') ? 'block' : 'none';
        if (secMatrix) secMatrix.style.display = (viewKey === 'matrix') ? 'block' : 'none';
        if (secBasins) secBasins.style.display = (viewKey === 'basins') ? 'block' : 'none';
        if (secGrains) secGrains.style.display = (viewKey === 'grains') ? 'block' : 'none';
        if (secDemand) secDemand.style.display = (viewKey === 'demand') ? 'block' : 'none';
      }

      if (viewKey === 'flagship' || viewKey === 'all') renderFlagshipOriginFreightChart();
      if (viewKey === 'matrix' || viewKey === 'all') renderCommodityFlowMatrix();
      if (viewKey === 'basins' || viewKey === 'all') {
        renderBrazilExportsChart();
        renderPpaThroughputChart();
        renderEiaExportsChart();
        renderNewcastleCoalChart();
        renderAustraliaReqChart();
      }
      if (viewKey === 'grains' || viewKey === 'all') {
        renderUsdaExportSalesChart();
        renderUsdaGrainInspectionsChart();
        renderVesselQueueChart();
        renderGrainFreightChart();
      }
      if (viewKey === 'demand' || viewKey === 'all') {
        renderLandedCostChart();
        renderIronOreRestockingChart(window.currentProduct || 'cape');
        renderCommodityChart();
        renderContainerIndexChart();
      }
    }
    window.setCargoSubView = setCargoSubView;

    // 3. FLAGSHIP ORIGIN -> FREIGHT ROUTE MODULE
    var _cargoFlagshipRoute = 'brazil_c3';
    function setFlagshipRoute(routeKey) {
      window.setFlagshipRoute = setFlagshipRoute;
      _cargoFlagshipRoute = routeKey;
      ['brazil_c3', 'pilbara_c5', 'newcastle_coal', 'usg_grain', 'guinea_cape'].forEach(function(k) {
        var idMap = {
          'brazil_c3': 'flagBtnBrazilC3',
          'pilbara_c5': 'flagBtnPilbaraC5',
          'newcastle_coal': 'flagBtnNewcastleCoal',
          'usg_grain': 'flagBtnUsgGrain',
          'guinea_cape': 'flagBtnGuineaCape'
        };
        var btn = document.getElementById(idMap[k]);
        if (btn) {
          var active = (k === routeKey);
          btn.classList.toggle('active', active);
          btn.style.background = active ? 'var(--accent)' : 'var(--card)';
          btn.style.color = active ? '#fff' : 'var(--text-muted)';
        }
      });
      renderFlagshipOriginFreightChart();
    }
    window.setFlagshipRoute = setFlagshipRoute;

    function renderFlagshipOriginFreightChart() {
      var canvas = document.getElementById('flagshipOriginFreightChart');
      if (!canvas) return;
      if (!DATA || !DATA.cargoSummary || !DATA.cargoSummary.flagship_pairs) return;

      var pairData = DATA.cargoSummary.flagship_pairs[_cargoFlagshipRoute];
      if (!pairData) return;

      var corridorEl = document.getElementById('flagshipHudCorridor');
      var volEl = document.getElementById('flagshipHudVol');
      var rateEl = document.getElementById('flagshipHudRate');
      var tsidEl = document.getElementById('flagshipHudTsid');
      var provEl = document.getElementById('flagshipProvText');
      var badgeEl = document.getElementById('flagshipStatusBadge');
      var guineaBox = document.getElementById('guineaEmptyStateCard');

      if (corridorEl) corridorEl.textContent = pairData.origin + ' → ' + pairData.destination;
      var lastVol = pairData.volume_data.filter(function(v) { return v !== null; }).slice(-1)[0];
      var lastRate = pairData.freight_data.filter(function(v) { return v !== null; }).slice(-1)[0];
      if (volEl && lastVol != null) volEl.textContent = lastVol + ' ' + pairData.volume_unit + '/mo';
      if (rateEl && lastRate != null) rateEl.textContent = '$' + lastRate + ' / MT';
      if (tsidEl) tsidEl.textContent = pairData.route_code;
      if (provEl) provEl.textContent = 'Volume: ' + pairData.provenance.volume_source + ' · Freight: ' + pairData.provenance.freight_source;
      if (badgeEl) {
        badgeEl.textContent = pairData.provenance.status === 'LIVE_MIRROR' ? 'MIRROR STATISTIC' : 'LIVE PAIRED';
        badgeEl.className = pairData.provenance.status === 'LIVE_MIRROR' ? 'cargo-badge-mirror' : 'cargo-badge-live';
      }
      if (guineaBox) {
        guineaBox.style.display = (_cargoFlagshipRoute === 'guinea_cape') ? 'block' : 'none';
      }

      destroyChart('flagshipOriginFreightChart');
      updateOrCreateChart('flagshipOriginFreightChart', canvas, {
        type: 'line',
        data: {
          labels: pairData.months,
          datasets: [
            {
              label: pairData.volume_label,
              data: pairData.volume_data,
              borderColor: '#38bdf8',
              backgroundColor: 'rgba(56, 189, 248, 0.12)',
              borderWidth: 2,
              pointRadius: 2,
              fill: true,
              yAxisID: 'yLeft'
            },
            {
              label: pairData.freight_label,
              data: pairData.freight_data,
              borderColor: '#f59e0b',
              backgroundColor: 'transparent',
              borderWidth: 2.5,
              pointRadius: 2.5,
              fill: false,
              yAxisID: 'yRight'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { position: 'top', labels: { usePointStyle: true, font: { size: 11 } } },
            tooltip: {
              callbacks: {
                label: function(c) {
                  return ' ' + c.dataset.label + ': ' + c.parsed.y;
                }
              }
            }
          },
          scales: {
            x: { grid: { color: '#151a22' }, ticks: { color: '#8b949e', font: { size: 11 }, maxTicksLimit: 14 } },
            yLeft: {
              type: 'linear',
              position: 'left',
              grid: { color: '#151a22' },
              ticks: { color: '#38bdf8', font: { size: 11 }, callback: function(v) { return v + ' ' + pairData.volume_unit; } },
              title: { display: true, text: 'Physical Volume (' + pairData.volume_unit + ')', color: '#38bdf8', font: { size: 11 } }
            },
            yRight: {
              type: 'linear',
              position: 'right',
              grid: { drawOnChartArea: false },
              ticks: { color: '#f59e0b', font: { size: 11 }, callback: function(v) { return '$' + v; } },
              title: { display: true, text: 'Baltic Route Freight Rate', color: '#f59e0b', font: { size: 11 } }
            }
          }
        }
      });
    }
    window.renderFlagshipOriginFreightChart = renderFlagshipOriginFreightChart;

    // 4. COMMODITY FLOW MATRIX & COVERAGE AUDIT
    var _cargoMatrixGroup = 'ALL';
    function setMatrixGroup(groupKey) {
      window.setMatrixGroup = setMatrixGroup;
      _cargoMatrixGroup = groupKey;
      var btns = {
        'ALL': 'matBtnALL',
        'Agricultural Products': 'matBtnAgri',
        'Energy': 'matBtnEnergy',
        'Ores and Rocks': 'matBtnOres',
        'Tankers & Gas': 'matBtnWet',
        'Minerals and Metals': 'matBtnMetals',
        'Bulk Chemicals': 'matBtnChem',
        'Unclassified': 'matBtnUnclass'
      };
      Object.keys(btns).forEach(function(k) {
        var el = document.getElementById(btns[k]);
        if (el) {
          var active = (k === groupKey);
          el.classList.toggle('active', active);
          el.style.background = active ? 'var(--accent)' : 'var(--card)';
          el.style.color = active ? '#fff' : 'var(--text-muted)';
        }
      });
      renderCommodityFlowMatrix();
    }
    window.setMatrixGroup = setMatrixGroup;

    function renderCommodityFlowMatrix() {
      var tbody = document.getElementById('cargoMatrixTableBody');
      if (!tbody) return;
      if (!DATA || !DATA.commodityFlowMatrix) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">Awaiting fixture ledger data...</td></tr>';
        return;
      }

      var matrix = DATA.commodityFlowMatrix;
      var commodities = matrix.commodities || {};

      var rows = Object.values(commodities);
      if (_cargoMatrixGroup !== 'ALL') {
        rows = rows.filter(function(r) { return r.group === _cargoMatrixGroup; });
      }

      rows.sort(function(a, b) { return b.fixture_count - a.fixture_count; });

      var html = '';
      rows.slice(0, 30).forEach(function(r) {
        var topLane = (r.top_trade_lanes && r.top_trade_lanes.length) ? r.top_trade_lanes[0].lane : 'Global Diversified';
        var topVc = (r.top_vessel_classes && r.top_vessel_classes.length) ? r.top_vessel_classes[0].class : 'General Bulker';
        var isUnclass = r.canonical.indexOf('Unclassified') >= 0;
        var badge = isUnclass ? '<span class="cargo-badge-est">UNCLASSIFIED BUCKET</span>' :
                    (r.fixture_count > 2000 ? '<span class="cargo-badge-live">HIGH COVERAGE</span>' : '<span class="cargo-badge-live" style="background:rgba(88,166,255,0.15);color:#58a6ff;border-color:rgba(88,166,255,0.3);">BROKER REPORTED</span>');

        html += '<tr' + (isUnclass ? ' style="background:rgba(227,179,65,0.06);font-weight:600;"' : '') + '>';
        html += '<td style="font-family:\'IBM Plex Mono\',monospace;color:var(--text-bright);">' + r.canonical + '</td>';
        html += '<td>' + (r.subgroup || r.group) + '</td>';
        html += '<td style="text-align:right;font-family:\'IBM Plex Mono\',monospace;font-weight:700;">' + r.fixture_count.toLocaleString() + '</td>';
        html += '<td style="text-align:right;font-family:\'IBM Plex Mono\',monospace;color:var(--accent);">' + (r.total_qty_mt > 0 ? (r.total_qty_mt / 1000.0).toFixed(1) + ' Mt' : '—') + '</td>';
        html += '<td style="font-size:11px;color:var(--text-muted);">' + topLane + '</td>';
        html += '<td><span class="badge" style="font-size:11px;padding:1px 5px;background:var(--bg);border:1px solid var(--border);">' + topVc + '</span></td>';
        html += '<td>' + badge + '</td>';
        html += '</tr>';
      });

      tbody.innerHTML = html || '<tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text-muted);">No matching commodities in this category.</td></tr>';

      var covGrid = document.getElementById('cargoCoverageGrid');
      if (covGrid && matrix.coverage_catalog) {
        var cHtml = '';
        matrix.coverage_catalog.forEach(function(c) {
          var isNat = c.status.indexOf('NATIONAL') >= 0;
          var isMirror = c.status.indexOf('MIRROR') >= 0;
          var isGap = c.status.indexOf('GAP') >= 0;
          var statusBadge = isNat ? '<span class="cargo-badge-live">NATIONAL CUSTOMS SERIES</span>' :
                            (isMirror ? '<span class="cargo-badge-mirror">MIRROR TRADE FLOW</span>' :
                            (isGap ? '<span class="cargo-badge-unavail">DATA GAP</span>' : '<span class="cargo-badge-est" style="background:rgba(88,166,255,0.15);color:#58a6ff;border-color:rgba(88,166,255,0.3);">FIXTURE DERIVED</span>'));

          cHtml += '<div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px 12px;">';
          cHtml += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">';
          cHtml += '<strong style="font-size:11px;color:var(--text);">' + c.node + '</strong>';
          cHtml += statusBadge;
          cHtml += '</div>';
          cHtml += '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">Source: ' + c.source + '</div>';
          cHtml += '<div style="font-size:11px;font-family:\'IBM Plex Mono\',monospace;color:var(--accent);">' + c.fixtures.toLocaleString() + ' broker fixtures</div>';
          cHtml += '</div>';
        });
        covGrid.innerHTML = cHtml;
      }
    }
    window.renderCommodityFlowMatrix = renderCommodityFlowMatrix;

    // 5. REBUILT FLOW MODULES (ENVELOPES & UNUSED DATASETS)

    // A. Brazil Seaborne Exports
    function renderBrazilExportsChart() {
      var canvas = document.getElementById('brazilExportsChart');
      if (!canvas) return;
      if (DATA && DATA.cargoSummary && DATA.cargoSummary.brazil_exports) {
        var bz = DATA.cargoSummary.brazil_exports;
        var env = bz.envelopes && bz.envelopes[_brazilCommodity];
        if (env) {
          renderSeasonalEnvelope(canvas, {
            labels: env.months,
            min: env.min,
            max: env.max,
            mean: env.mean,
            years: env.years,
            latestYear: env.latest_year,
            unit: 'Mt',
            frequency: 'M'
          });
          var badge = document.getElementById('brazilExportsBadge');
          if (badge && env.years && env.years[env.latest_year]) {
            var lastV = env.years[env.latest_year].filter(function(v) { return v !== null; }).slice(-1)[0];
            if (lastV != null) badge.innerHTML = _brazilCommodity + ': <strong>' + lastV + ' Mt/mo</strong> (' + env.latest_year + ')';
          }
          return;
        }
      }
      // Fallback to raw rows if cache not yet populated
      var rows = DATA.brazilExports || DATA.brazil_exports || [];
      if (!rows || !rows.length) return;
      var dates = [...new Set(rows.map(r => r.dateStr))].sort().slice(-36);
      var datasets = [];
      var oreMap = {}, crudeMap = {}, soyMap = {}, sugarMap = {};
      rows.forEach(function(r) {
        var mt = (r.metricTonnes || 0) / 1000000.0;
        if (r.commodity === 'Iron Ore') oreMap[r.dateStr] = mt;
        if (r.commodity === 'Crude Oil') crudeMap[r.dateStr] = mt;
        if (r.commodity === 'Soybeans') soyMap[r.dateStr] = mt;
        if (r.commodity === 'Raw Sugar') sugarMap[r.dateStr] = mt;
      });
      if (_brazilCommodity === 'Iron Ore' || _brazilCommodity === 'All') {
        datasets.push({ label: 'Iron Ore (Mt/mo)', data: dates.map(d => oreMap[d] || null), borderColor: '#58a6ff', backgroundColor: 'rgba(88,166,255,0.15)', fill: true, borderWidth: 2 });
      }
      if (_brazilCommodity === 'Crude Oil' || _brazilCommodity === 'All') {
        datasets.push({ label: 'Crude Oil (Mt/mo)', data: dates.map(d => crudeMap[d] || null), borderColor: '#ff7b72', backgroundColor: 'rgba(255,123,114,0.15)', fill: true, borderWidth: 2 });
      }
      destroyChart('brazilExportsChart');
      updateOrCreateChart('brazilExportsChart', canvas, {
        type: 'line',
        data: { labels: dates, datasets: datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { grid: { color: '#151a22' }, ticks: { color: '#8b949e', font: { size: 11 } } },
            y: { grid: { color: '#151a22' }, ticks: { color: '#8b949e', font: { size: 11 }, callback: v => v + ' Mt' } }
          }
        }
      });
    }
    window.renderBrazilExportsChart = renderBrazilExportsChart;

    // B. Pilbara Ports & Miner Guidance
    var _ppaPort = 'Port Hedland';
    function setPpaPort(port) {
      _ppaPort = port;
      var btnHedland = document.getElementById('ppaBtnHedland');
      var btnDampier = document.getElementById('ppaBtnDampier');
      var btnMiners = document.getElementById('ppaBtnMiners');
      if (btnHedland) {
        btnHedland.style.background = (port === 'Port Hedland') ? 'var(--accent)' : 'var(--card)';
        btnHedland.style.color = (port === 'Port Hedland') ? '#fff' : 'var(--text-muted)';
      }
      if (btnDampier) {
        btnDampier.style.background = (port === 'Dampier') ? 'var(--accent)' : 'var(--card)';
        btnDampier.style.color = (port === 'Dampier') ? '#fff' : 'var(--text-muted)';
      }
      if (btnMiners) {
        btnMiners.style.background = (port === 'Miners') ? 'var(--accent)' : 'var(--card)';
        btnMiners.style.color = (port === 'Miners') ? '#fff' : 'var(--text-muted)';
      }
      renderPpaThroughputChart();
    }
    window.setPpaPort = setPpaPort;

    function renderPpaThroughputChart() {
      var canvas = document.getElementById('ppaThroughputChart');
      if (!canvas) return;
      if (_ppaPort === 'Miners') {
        var miners = (DATA.cargoSummary && DATA.cargoSummary.pilbara_iron_ore && DATA.cargoSummary.pilbara_iron_ore.miners_quarterly) || DATA.minerShipments || [];
        if (!miners || !miners.length) return;
        var quarters = miners.map(m => m.quarter);
        destroyChart('ppaThroughputChart');
        updateOrCreateChart('ppaThroughputChart', canvas, {
          type: 'bar',
          data: {
            labels: quarters,
            datasets: [
              { label: 'Vale (Mt)', data: miners.map(m => m.vale_mt), backgroundColor: '#58a6ff' },
              { label: 'Rio Tinto (Mt)', data: miners.map(m => m.rio_tinto_mt), backgroundColor: '#3fb950' },
              { label: 'BHP (Mt)', data: miners.map(m => m.bhp_mt), backgroundColor: '#f59e0b' },
              { label: 'Fortescue (Mt)', data: miners.map(m => m.fmg_mt), backgroundColor: '#a371f7' }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: { grid: { color: '#151a22' }, ticks: { color: '#8b949e', font: { size: 11 } } },
              y: { grid: { color: '#151a22' }, ticks: { color: '#8b949e', font: { size: 11 }, callback: v => v + ' Mt' } }
            }
          }
        });
        return;
      }
      if (DATA && DATA.cargoSummary && DATA.cargoSummary.pilbara_iron_ore) {
        var ppa = DATA.cargoSummary.pilbara_iron_ore;
        var env = (_ppaPort === 'Dampier') ? ppa.dampier_envelope : ppa.hedland_envelope;
        var portLabel = (_ppaPort === 'Dampier') ? 'Port of Dampier' : 'Port Hedland';
        if (env) {
          renderSeasonalEnvelope(canvas, {
            labels: env.months,
            min: env.min,
            max: env.max,
            mean: env.mean,
            years: env.years,
            latestYear: env.latest_year,
            unit: 'Mt',
            frequency: 'M'
          });
          var badge = document.getElementById('ppaThroughputBadge');
          if (badge && env.years && env.years[env.latest_year]) {
            var lastV = env.years[env.latest_year].filter(v => v !== null).slice(-1)[0];
            if (lastV != null) badge.innerHTML = portLabel + ': <strong>' + lastV + ' Mt/mo</strong> (' + env.latest_year + ')';
          }
        }
      }
    }
    window.renderPpaThroughputChart = renderPpaThroughputChart;

    // C. US EIA Weekly Crude Exports
    function renderEiaExportsChart() {
      var canvas = document.getElementById('eiaExportsChart');
      if (!canvas) return;
      if (DATA && DATA.cargoSummary && DATA.cargoSummary.us_crude_exports) {
        var env = DATA.cargoSummary.us_crude_exports.envelope;
        if (env) {
          renderSeasonalEnvelope(canvas, {
            labels: env.weeks ? env.weeks.map(w => 'W' + w) : null,
            min: env.min,
            max: env.max,
            mean: env.mean,
            years: env.years,
            latestYear: env.latest_year,
            unit: 'kbpd',
            frequency: 'W'
          });
          var badge = document.getElementById('eiaExportsBadge');
          if (badge && env.years && env.years[env.latest_year]) {
            var lastV = env.years[env.latest_year].filter(v => v !== null).slice(-1)[0];
            if (lastV != null) badge.innerHTML = 'US Crude Exports: <strong>' + Math.round(lastV).toLocaleString() + ' kbpd</strong>';
          }
        }
      }
    }
    window.renderEiaExportsChart = renderEiaExportsChart;

    // D. Newcastle Seaborne Coal Exports
    function renderNewcastleCoalChart() {
      var canvas = document.getElementById('newcastleCoalChart');
      if (!canvas) return;
      if (DATA && DATA.cargoSummary && DATA.cargoSummary.newcastle_coal) {
        var env = DATA.cargoSummary.newcastle_coal.envelope;
        if (env) {
          renderSeasonalEnvelope(canvas, {
            labels: env.months,
            min: env.min,
            max: env.max,
            mean: env.mean,
            years: env.years,
            latestYear: env.latest_year,
            unit: 'Mt',
            frequency: 'M'
          });
          var badge = document.getElementById('newcastleCoalBadge');
          if (badge && env.years && env.years[env.latest_year]) {
            var lastV = env.years[env.latest_year].filter(v => v !== null).slice(-1)[0];
            if (lastV != null) badge.innerHTML = 'Newcastle Coal: <strong>' + lastV + ' Mt/mo</strong> (' + env.latest_year + ')';
          }
        }
      }
    }
    window.renderNewcastleCoalChart = renderNewcastleCoalChart;

    // E. Australia REQ Official Commodity Forecasts
    var _reqCommodity = 'Iron Ore';
    function setReqCommodity(cmd) {
      window.setReqCommodity = setReqCommodity;
      _reqCommodity = cmd;
      ['Ore', 'Thermal', 'Met', 'Lng', 'Bauxite'].forEach(function(k) {
        var map = { 'Ore': 'Iron Ore', 'Thermal': 'Thermal Coal', 'Met': 'Metallurgical Coal', 'Lng': 'LNG', 'Bauxite': 'Bauxite' };
        var btn = document.getElementById('reqBtn' + k);
        if (btn) {
          var active = (map[k] === cmd);
          btn.classList.toggle('active', active);
          btn.style.background = active ? 'var(--accent)' : 'var(--card)';
          btn.style.color = active ? '#fff' : 'var(--text-muted)';
        }
      });
      renderAustraliaReqChart();
    }
    window.setReqCommodity = setReqCommodity;

    function renderAustraliaReqChart() {
      var canvas = document.getElementById('australiaReqChart');
      if (!canvas) return;
      if (DATA && DATA.cargoSummary && DATA.cargoSummary.australia_req) {
        var req = DATA.cargoSummary.australia_req;
        var series = req.commodities && req.commodities[_reqCommodity];
        if (series && series.length) {
          var labels = series.map(s => s.quarter);
          var vols = series.map(s => s.volume_mt);
          var vals = series.map(s => s.value_aud_b);

          var badge = document.getElementById('australiaReqBadge');
          if (badge && vols.length) {
            badge.innerHTML = _reqCommodity + ': <strong>' + vols[vols.length - 1] + ' Mt</strong> | Value: <strong>A$' + vals[vals.length - 1] + 'B</strong>';
          }

          destroyChart('australiaReqChart');
          updateOrCreateChart('australiaReqChart', canvas, {
            type: 'bar',
            data: {
              labels: labels,
              datasets: [
                {
                  label: _reqCommodity + ' Export Volume (Mt/quarter)',
                  data: vols,
                  backgroundColor: '#38bdf8',
                  yAxisID: 'yLeft'
                },
                {
                  label: 'Export Value (AUD Billions)',
                  data: vals,
                  type: 'line',
                  borderColor: '#f59e0b',
                  backgroundColor: 'transparent',
                  borderWidth: 2,
                  yAxisID: 'yRight'
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              scales: {
                x: { grid: { color: '#151a22' }, ticks: { color: '#8b949e', font: { size: 11 }, maxTicksLimit: 12 } },
                yLeft: { position: 'left', grid: { color: '#151a22' }, ticks: { color: '#38bdf8', font: { size: 11 }, callback: v => v + ' Mt' } },
                yRight: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#f59e0b', font: { size: 11 }, callback: v => 'A$' + v + 'B' } }
              }
            }
          });
        }
      }
    }
    window.renderAustraliaReqChart = renderAustraliaReqChart;

    // F. USDA Outstanding Export Commitments (68k rows)
    var _usdaSalesCmd = 'Wheat';
    function setUsdaSalesCommodity(cmd) {
      window.setUsdaSalesCommodity = setUsdaSalesCommodity;
      _usdaSalesCmd = cmd;
      ['Wheat', 'Corn', 'Soy', 'Barley', 'Sorghum'].forEach(function(k) {
        var map = { 'Wheat': 'Wheat', 'Corn': 'Corn', 'Soy': 'Soybeans', 'Barley': 'Barley', 'Sorghum': 'Sorghum' };
        var btn = document.getElementById('usdaSalesBtn' + k);
        if (btn) {
          var active = (map[k] === cmd);
          btn.classList.toggle('active', active);
          btn.style.background = active ? 'var(--accent)' : 'var(--card)';
          btn.style.color = active ? '#fff' : 'var(--text-muted)';
        }
      });
      renderUsdaExportSalesChart();
    }
    window.setUsdaSalesCommodity = setUsdaSalesCommodity;

    function renderUsdaExportSalesChart() {
      var canvas = document.getElementById('usdaExportSalesChart');
      if (!canvas) return;
      if (DATA && DATA.cargoSummary && DATA.cargoSummary.usda_export_commitments) {
        var envs = DATA.cargoSummary.usda_export_commitments.envelopes;
        var env = envs && envs[_usdaSalesCmd];
        if (env) {
          renderSeasonalEnvelope(canvas, {
            labels: env.weeks ? env.weeks.map(w => 'W' + w) : null,
            min: env.min,
            max: env.max,
            mean: env.mean,
            years: env.years,
            latestYear: env.latest_year,
            unit: 'MT',
            frequency: 'W'
          });
          var badge = document.getElementById('usdaSalesBadge');
          if (badge && env.years && env.years[env.latest_year]) {
            var lastV = env.years[env.latest_year].filter(v => v !== null).slice(-1)[0];
            if (lastV != null) badge.innerHTML = _usdaSalesCmd + ' Commitments: <strong>' + Math.round(lastV).toLocaleString() + ' MT</strong>';
          }
        }
      }
    }
    window.renderUsdaExportSalesChart = renderUsdaExportSalesChart;

    // G. USDA Grain Inspections
    var _inspectionsRegion = 'GULF';
    function setInspectionsRegion(reg) {
      window.setInspectionsRegion = setInspectionsRegion;
      _inspectionsRegion = reg;
      ['Gulf', 'Pac', 'Atl'].forEach(function(k) {
        var map = { 'Gulf': 'GULF', 'Pac': 'PACIFIC', 'Atl': 'ATLANTIC' };
        var btn = document.getElementById('inspBtn' + k);
        if (btn) {
          var active = (map[k] === reg);
          btn.classList.toggle('active', active);
          btn.style.background = active ? 'var(--accent)' : 'var(--card)';
          btn.style.color = active ? '#fff' : 'var(--text-muted)';
        }
      });
      renderUsdaGrainInspectionsChart();
    }
    window.setInspectionsRegion = setInspectionsRegion;

    function renderUsdaGrainInspectionsChart() {
      var canvas = document.getElementById('usdaGrainInspectionsChart');
      if (!canvas) return;
      if (DATA && DATA.cargoSummary && DATA.cargoSummary.usda_grain_inspections) {
        var envs = DATA.cargoSummary.usda_grain_inspections.region_envelopes;
        var env = envs && envs[_inspectionsRegion];
        if (env) {
          renderSeasonalEnvelope(canvas, {
            labels: env.weeks ? env.weeks.map(w => 'W' + w) : null,
            min: env.min,
            max: env.max,
            mean: env.mean,
            years: env.years,
            latestYear: env.latest_year,
            unit: 'MT',
            frequency: 'W'
          });
          var badge = document.getElementById('usdaInspectionsBadge');
          if (badge && env.years && env.years[env.latest_year]) {
            var lastV = env.years[env.latest_year].filter(v => v !== null).slice(-1)[0];
            if (lastV != null) badge.innerHTML = _inspectionsRegion + ' Inspections: <strong>' + Math.round(lastV).toLocaleString() + ' MT/wk</strong>';
          }
        }
      }
    }
    window.renderUsdaGrainInspectionsChart = renderUsdaGrainInspectionsChart;

    // MASTER TAB RENDERER
    function renderCargoTab() {
      var dead = function () { return window.currentTab !== 'cargo'; };
      try { renderFlagshipOriginFreightChart(); } catch (e) { console.error('[Cargo Flagship]', e); }
      if (dead()) return;
      try { renderCommodityFlowMatrix(); } catch (e) { console.error('[Cargo Matrix]', e); }
      try { renderBrazilExportsChart(); } catch (e) { console.error('[Cargo Brazil]', e); }
      try { renderPpaThroughputChart(); } catch (e) { console.error('[Cargo PPA]', e); }
      if (dead()) return;
      try { renderEiaExportsChart(); } catch (e) { console.error('[Cargo EIA]', e); }
      try { renderNewcastleCoalChart(); } catch (e) { console.error('[Cargo Coal]', e); }
      try { renderAustraliaReqChart(); } catch (e) { console.error('[Cargo REQ]', e); }
      if (dead()) return;
      try { renderUsdaExportSalesChart(); } catch (e) { console.error('[Cargo USDA Sales]', e); }
      try { renderUsdaGrainInspectionsChart(); } catch (e) { console.error('[Cargo Inspections]', e); }
      try { renderVesselQueueChart(); } catch (e) { console.error('[Cargo Queue]', e); }
      try { renderGrainFreightChart(); } catch (e) { console.error('[Cargo GrainFreight]', e); }
      if (dead()) return;
      try { renderLandedCostChart(); } catch (e) { console.error('[Cargo LandedCost]', e); }
      try { renderIronOreRestockingChart(window.currentProduct || 'cape'); } catch (e) { console.error('[Cargo Restocking]', e); }
      try { renderCommodityChart(); } catch (e) { console.error('[Cargo Commodity]', e); }
      try { renderContainerIndexChart(); } catch (e) { console.error('[Cargo Container]', e); }
    }
    window.renderCargoTab = renderCargoTab;
'''

def main():
    with open(INDEX_HTML, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Find the old renderCargoTab
    old_target = """    // =====================================================================
    // CARGO & TRADE FLOWS TAB RENDERER (9 FLOW MODULES)
    // =====================================================================
    function renderCargoTab() {
      var dead = function () { return window.currentTab !== 'cargo'; };
      try { renderIronOreRestockingChart(window.currentProduct || 'cape'); } catch (e) { console.error('[Cargo Restocking]', e); }
      if (dead()) return;
      try { renderCommodityChart(); } catch (e) { console.error('[Cargo Commodity]', e); }
      try { renderContainerIndexChart(); } catch (e) { console.error('[Cargo Container]', e); }
      if (dead()) return;
      try { renderGrainFreightChart(); } catch (e) { console.error('[Cargo Grain]', e); }
      try { renderVesselQueueChart(); } catch (e) { console.error('[Cargo Queue]', e); }
      try { renderLandedCostChart(); } catch (e) { console.error('[Cargo LandedCost]', e); }
      if (dead()) return;
      try { renderBrazilExportsChart(); } catch (e) { console.error('[Cargo Brazil]', e); }
      try { renderPpaThroughputChart(); } catch (e) { console.error('[Cargo PPA]', e); }
      try { renderEiaExportsChart(); } catch (e) { console.error('[Cargo EIA]', e); }
    }
    window.renderCargoTab = renderCargoTab;"""

    if old_target not in content:
        print("Error: Could not locate old renderCargoTab target block.")
        sys.exit(1)

    new_js = get_cargo_js()
    updated_content = content.replace(old_target, new_js)

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(updated_content)

    print(f"Successfully injected complete Cargo JS into {INDEX_HTML}")

if __name__ == "__main__":
    main()
