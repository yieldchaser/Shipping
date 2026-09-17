// TurkStat (TÜİK) monthly HS4 quantity + USD by trade flow – run in DevTools console on
// https://bi.tuik.gov.tr/extensions/tuik-mashup/index.html?report_type=1 (general trade).
// Server-side engine refuses cloud/CI IPs (HTTP 503), so this is a manual monthly step.
// Fields: MIKTAR_1 = kg, DOLAR = USD, IHRITH_FLAG 1 = exports, 2 = imports. General trade system (= Comtrade). Special-trade app: 8db826a9-59f2-4a33-a91e-88ca417dddf9
// Change CODES to pull other HS4 codes. Output: tuik_by_flow.csv (1996 → latest month).
(async () => {
  const ID = 'bd4b4757-a3c9-45ba-b4fb-5c8d7e2d2c42'; // GENERAL trade (report_type=1) – matches Comtrade exactly
  const CODES = ['2523', '7204'];
  const qlik = await new Promise(r => require(['js/qlik'], r));
  const app = qlik.openApp(ID);
  const M = [];
  for (const c of CODES) for (const m of ['MIKTAR_1', 'DOLAR'])
    M.push({ qDef: { qDef: `Sum({<[TARIFE4]={'${c}'}>} [${m}])`, qLabel: `${c}_${m}` } });
  const dims = ['YIL', 'AY', 'IHRITH_FLAG'].map(x => ({ qDef: { qFieldDefs: [x] } }));
  const width = dims.length + M.length, height = Math.floor(10000 / width);
  const hc = await new Promise((res, rej) => {
    const t = setTimeout(() => rej('timeout'), 120000);
    app.createCube({ qDimensions: dims, qMeasures: M,
      qInitialDataFetch: [{ qTop: 0, qLeft: 0, qWidth: width, qHeight: height }] },
      rep => { clearTimeout(t); res(rep.qHyperCube); app.destroySessionObject(rep.qInfo.qId); });
  });
  const head = ['YIL', 'AY', 'IHRITH_FLAG', ...M.map(m => m.qDef.qLabel)];
  const rows = hc.qDataPages[0].qMatrix.map(r => r.map(c => c.qIsNull ? '' :
    (typeof c.qNum === 'number' && !isNaN(c.qNum) && /^[\d.,-]+$/.test(c.qText || '') ? c.qNum : c.qText)));
  if (rows.length < hc.qSize.qcy) console.warn('PARTIAL', rows.length, 'of', hc.qSize.qcy, '– reduce CODES');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([[head, ...rows].map(r => r.join(',')).join('\n')], { type: 'text/csv' }));
  a.download = 'tuik_by_flow.csv'; a.click();
  console.log('DOWNLOADED', rows.length, 'of', hc.qSize.qcy);
})().catch(e => console.error('TUIK error:', e));
