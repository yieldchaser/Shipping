# Phase 2c edit set: KB insertion, tooltip rewrites, jargon purge, em-dash purge.
# Bottom-up line-range edits on CRLF-light LF file; then em-dash pass inside fn bounds.
import io, re, sys

P = r"C:\Users\Dell\Github\Shipping\index.html"
src = io.open(P, encoding="utf-8", newline="").read()
lines = [l[:-1] if l.endswith("\r") else l for l in src.split("\n")]
orig = len(lines)
print("start lines:", orig)

def rep(lineno_1based, new_text, marker):
    """Replace one line (1-based) with new_text (may be multi-line). Marker must be in old line."""
    i = lineno_1based - 1
    old = lines[i]
    assert marker in old, f"L{lineno_1based} marker miss: {marker!r} vs {old[:120]!r}"
    lines[i:i+1] = new_text.split("\n")

def rep_block(a, b, new_text, marker):
    """Replace inclusive 1-based range with new_text."""
    i, j = a - 1, b  # slice end exclusive
    old = "\n".join(lines[i:j])
    assert marker in old, f"L{a}-{b} marker miss: {marker!r} vs {old[:200]!r}"
    lines[i:j] = new_text.split("\n")

_pos = [0]
def rep_span(start_marker, end_marker, new_text, _unused=None):
    """Replace from the line containing start_marker (first hit at/after _pos)
    up to (exclusive) the first line index i>=si+1 whose 1-3 line window joined
    by \n contains end_marker. Advances _pos."""
    si = next(i for i in range(_pos[0], len(lines)) if start_marker in lines[i])
    ei = None
    for i in range(si + 1, len(lines)):
        for w in (1, 2, 3):
            if end_marker in "\n".join(lines[i:i + w]):
                ei = i
                break
        if ei is not None:
            break
    if ei is None:
        print(f"END MARKER MISS after line {si+1}: {end_marker!r}")
        for k in range(si, min(si + 14, len(lines))):
            print(f"  {k+1}: {lines[k][:100]}")
        raise SystemExit(3)
    _pos[0] = si + new_text.count("\n") + 1
    lines[si:ei] = new_text.split("\n")

# ---------------- 1. dry archived append line (L43340)
rep(43340,
    "      if (dryArchived > 0) note.textContent = note.textContent + ' \\u00b7 ' + dryArchived + ' archived route series not shown: the source published no values in these branches; the USD/WS twins of these routes are shown.';",
    "archived route series not shown")

# ---------------- 2. dry note (L43339)
rep(43339,
    "      note.textContent = 'Daily dry route benchmarks from Fearnleys, launch dates differ per series (shown per tile), never averaged away \\u00b7 ' + series.length + ' series \\u00b7 data to ' + (FDESK_DRY_META.dateTo || 'n/a');",
    "as published on")

# ---------------- 3. dry chart.js label (L43389)
rep(43389,
    "            label: function (it) { var v = it.parsed.y; return ' ' + s.label + ': ' + (v == null ? 'n/a' : fearnFmtVal(v)) + ' ' + fearnUnitName(s.unit) + ', daily print, no interpolation'; }",
    "daily print, no interpolation")

# ---------------- 4. tank chart.js label (L43268)
rep(43268,
    "            label: function (it) { var v = it.parsed.y; return ' ' + s.label + ': ' + (v == null ? 'n/a' : fearnFmtVal(v)) + ' ' + fearnUnitName(s.unit) + ', daily print, no interpolation'; }",
    "daily print, no interpolation")

# ---------------- 5. tank archived footer (L43225)
rep(43225,
    "        archEl.textContent = archived + ' archived route series not shown: the source published no values in these branches; the USD/WS twins of these routes are shown.';",
    "archived route series not shown")

# ---------------- 6. tank note (L43217)
rep(43217,
    "      note.textContent = 'Daily points, uninterpolated, gaps stay gaps \\u00b7 ' + series.length + ' series in ' + FDESK.tankKlass + ' \\u00b7 data to ' + (FDESK_TANKER_META.dateTo || 'n/a');",
    "gaps stay gaps")

# ---------------- 7. fearnSeriesTooltip tail L43092-43096 (insert KB rows + plain source line)
rep_block(43092, 43096, """  rows.forEach(function (r) { if (r[1] !== '' && r[1] != null) h += '<div class="rt-row"><span class="rt-label">' + r[0] + '</span><span class="rt-val">' + escapeHtml(String(r[1])) + '</span></div>'; });
  var kb = (window.FDESK_ROUTE_KB && FDESK_ROUTE_KB[(s.klass || '') + '|' + (s.route || '')]) || null;
  if (kb) h += '<div class="rt-row"><span class="rt-label">What it is</span><span class="rt-val">' + escapeHtml(kb.what) + '</span></div>';
  if (kb) h += '<div class="rt-row"><span class="rt-label">What moves it</span><span class="rt-val">' + escapeHtml(kb.drivers) + '</span></div>';
  if (kb) h += '<div class="rt-row"><span class="rt-label">What it feeds</span><span class="rt-val">' + escapeHtml(kb.affects) + '</span></div>';
  if (s.derivation) h += '<div class="rt-row"><span class="rt-label">Derivation</span><span class="rt-val">' + escapeHtml(String(s.derivation)) + '</span></div>';
  var built = (FDESK_TANKER_META.builtUtc || FDESK_DRY_META.builtUtc || '');
  if (built) h += '<div class="rt-note">Fearnleys daily assessments \\u00b7 fetched ' + escapeHtml(built) + '</div>';
  else h += '<div class="rt-note">Fearnleys daily assessments \\u00b7 fetch timestamp not yet loaded</div>';""",
    "rows.forEach")

# ---------------- 8. fearnFrozenReason (L43056)
rep(43056,
    "  return FDESK_TANKER_META.notes || 'frozen: source stopped publishing, history preserved';",
    "FDESK_TANKER_META.notes ||")

# ---------------- 9. fearnBadgeState comment (L43067-43068)
rep_block(43067, 43068, """  // Badge semantics split: LIVE = real values still publishing today;
  // FROZEN = real values whose last print predates the live cutoff (the""",
    "Badge semantics split")

# ---------------- 10. KB + klass notes insertion after fearnUnitName (insert at L43047 -> after L43046)
KB = r'''var FDESK_ROUTE_KB = {
  'VLCC|MEG/FEAST': { what: "VLCCs hauling crude from the Middle East Gulf to the Far East, the world's highest volume crude trade and the flagship route for the biggest tankers", drivers: "OPEC output and export programmes, Chinese and Indian refiner buying, and how many VLCCs are open in the Gulf versus fixed to Asia", affects: "The headline VLCC market brokers and tanker owners quote first; feeds TCE screens, fixture decisions and tanker equity earnings models" },
  'VLCC|MEG/USG': { what: "VLCCs running crude from the Middle East Gulf to the US Gulf Coast, one of the longest crude voyages afloat", drivers: "US crude import appetite, the tonnage balance between Atlantic and Pacific, and Suez transit economics for the shorter routing", affects: "Sets the interbasin VLCC arbitrage and feeds long haul TCE screens and fleet positioning decisions" },
  'VLCC|CEYHAN/FEAST': { what: "VLCCs carrying Azeri BTC pipeline crude from Ceyhan on Turkey's Mediterranean coast to the Far East", drivers: "BTC pipeline flows, Far East refiner demand for Azeri grades, and the premium Ceyhan tonnage earns against the Gulf benchmark", affects: "The USD assessment feeds Mediterranean based VLCC TCE screens and owner choices between Ceyhan and Gulf employment" },
  'VLCC|CEYHAN/USG': { what: "VLCCs carrying Azeri BTC crude from Ceyhan across the Atlantic to the US Gulf", drivers: "BTC availability, US demand for Azeri barrels, and West African competition for the same Atlantic tonnage", affects: "Feeds Worldscale comparisons against NSEA/USG and WAFR/USG for owners weighing Atlantic VLCC employment" },
  'VLCC|NSEA/FEAST': { what: "VLCCs lifting North Sea crude for the very long haul to the Far East, the premium Atlantic export voyage", drivers: "North Sea loading programmes, Far East demand for Atlantic grades, and the earnings gap that keeps tonnage east or west", affects: "The USD assessment feeds long haul TCE screens and the decision on whether Atlantic tonnage stays or goes east" },
  'VLCC|NSEA/USG': { what: "VLCCs moving North Sea crude across the North Atlantic to the US Gulf Coast", drivers: "North Sea and US export programmes, transatlantic tonnage supply, and northern weather at the loading end", affects: "Feeds Atlantic VLCC earnings screens and the choice between short transatlantic runs and longer eastbound voyages" },
  'VLCC|NSEA/WCI': { what: "VLCCs carrying North Sea crude to the West Coast of India", drivers: "Indian refiner demand for Atlantic grades, competing Middle East supply, and Atlantic tonnage positioning", affects: "Feeds USD TCE screens for Atlantic VLCCs and Indian refiner freight budgets" },
  'VLCC|USG/THAILAND': { what: "VLCCs lifting US Gulf Coast crude for Thailand, one of the ultra long haul US export trades", drivers: "US crude export volumes, Thai refiner demand, and Pacific side VLCC availability", affects: "Feeds US export TCE screens and owner decisions on positioning Gulf tonnage for Pacific discharge" },
  'VLCC|WAFR/FEAST': { what: "VLCCs hauling West African crude to the Far East, the classic long haul out of Nigeria and Angola", drivers: "Nigerian and Angolan loading programmes, Far East refiner demand for sweet crude, and the ballast balance between Africa and Asia", affects: "Feeds east of Suez Worldscale screens and the Africa to Asia share of tanker earnings models" },
  'VLCC|WAFR/THAILAND': { what: "VLCCs carrying West African crude to Thai refiners", drivers: "West African output, Thai import programmes, and Pacific VLCC availability; Thai stems compete with Far East discharge for the same ships", affects: "Feeds West African Worldscale screens and Thai refiner freight budgets" },
  'VLCC|WAFR/UKC': { what: "VLCCs running West African crude to refineries of the UK Continent in Northwest Europe", drivers: "African grade premiums for European refiners, North Sea supply, and Atlantic tonnage supply", affects: "Feeds Atlantic VLCC Worldscale screens and the Europe versus Asia destination arbitrage for African barrels" },
  'VLCC|WAFR/USG': { what: "VLCCs moving West African crude across the Atlantic to the US Gulf", drivers: "US refiners' sweet crude appetite, Nigerian and Angolan exports, and the tonnage balance between Africa, the US Gulf and Europe", affects: "Feeds transatlantic VLCC screens and Atlantic tonnage positioning decisions" },
  'VLCC|EAST DEMURRAGE': { what: "The assessed daily compensation owners earn when a VLCC is delayed loading or discharging east of Suez", drivers: "Port congestion and berth queues, weather, and cargo stems running late against charterparty windows", affects: "Feeds owner claims planning and charterer exposure estimates; a rising assessment signals worsening port delays" },
  'VLCC|WEST DEMURRAGE': { what: "The assessed daily compensation owners earn when a VLCC is delayed loading or discharging west of Suez", drivers: "US Gulf, Northwest European and West African port congestion, plus Atlantic weather delays", affects: "Feeds Atlantic voyage cost models and charterer demurrage exposure west of Suez" },
  'Suezmax|BLSEA/MED': { what: "Suezmaxes carrying Black Sea crude through the Turkish Straits to Mediterranean refineries", drivers: "CPC and Russian Black Sea loadings, Turkish Strait transit delays, and Mediterranean refiner demand", affects: "Feeds the Black Sea to Med Worldscale screen; strait congestion can move the rate sharply day to day" },
  'Suezmax|BLSEA/USG': { what: "Suezmaxes moving Black Sea crude across the Atlantic to the US Gulf", drivers: "Transatlantic tonnage supply, US refiner demand for medium sour grades, and how Black Sea cargoes price against Atlantic alternatives", affects: "Feeds transatlantic Suezmax screens and US refiner freight budgets" },
  'Suezmax|BOT(H)/UKCM': { what: "Suezmaxes running Brazilian crude to the UK Continent; the H twin tracks the heavy grade stream", drivers: "Brazilian pre salt export programmes, European demand for heavier grades, and South Atlantic tonnage supply", affects: "Feeds Worldscale screens for South Atlantic crude and European refiner import costs" },
  'Suezmax|BOT(L)/UKCM': { what: "Suezmaxes running Brazilian crude to the UK Continent; the L twin tracks the light grade stream", drivers: "Brazilian export mix, European demand for lighter sweet grades, and Atlantic tonnage supply", affects: "Feeds Worldscale screens for South Atlantic crude and the heavy versus light spread European refiners watch" },
  'Suezmax|CEYHAN/UKC': { what: "Suezmaxes carrying Azeri BTC crude from Ceyhan to the UK Continent", drivers: "BTC pipeline flows, Northwest European refiner demand, and the tonnage balance between the Med and Northern Europe", affects: "Feeds Mediterranean to North Europe Worldscale screens and BTC cargo marketing" },
  'Suezmax|CEYHAN/USG': { what: "Suezmaxes moving Azeri BTC crude from Ceyhan across the Atlantic to the US Gulf", drivers: "BTC flows, US demand for Azeri barrels, and transatlantic Suezmax supply", affects: "Feeds transatlantic Suezmax screens; competes with NSEA/USG for the same tonnage" },
  'Suezmax|CEYHAN/WCI': { what: "Suezmaxes hauling Azeri BTC crude from Ceyhan to India's west coast", drivers: "Indian refiner demand for Atlantic grades, Med tonnage positioning, and competing Middle East supply", affects: "The USD assessment feeds eastbound TCE screens for Med positioned Suezmaxes" },
  'Suezmax|CROSS MED': { what: "Intra Mediterranean Suezmax runs, crude and dirty products between Mediterranean loading and discharge ports", drivers: "Med refinery activity, North African export programmes, and how many Suezmaxes stay in the basin versus being drawn out", affects: "Feeds Med Worldscale screens and refiner voyage cost budgets" },
  'Suezmax|CROSS NSEA': { what: "Suezmax runs inside the North Sea area, crude between North Sea terminals and Northwest European refineries", drivers: "North Sea field loadings, refinery runs, and Baltic and Mediterranean competition for the same ships", affects: "Feeds North Sea Worldscale screens and short haul tanker earnings" },
  'Suezmax|EAST DEMURRAGE': { what: "Assessed daily compensation for Suezmaxes delayed east of Suez", drivers: "Asian and Gulf port congestion, cargo stem delays, and weather", affects: "Feeds owner demurrage exposure and charterer claims budgets east of Suez" },
  'Suezmax|WEST DEMURRAGE': { what: "Assessed daily compensation for Suezmaxes delayed west of Suez", drivers: "Atlantic port congestion, berth queues, and late cargo stems", affects: "Feeds Atlantic voyage cost models and demurrage claims exposure" },
  'Suezmax|MEG/EAST (+15 YR)': { what: "Suezmaxes aged over 15 years carrying Middle East Gulf crude to Asia, the older ship slice of the Gulf trade", drivers: "Gulf export volumes, trading patterns for older tonnage, and the discount older ships earn against modern units", affects: "Feeds age segmented Worldscale screens and fleet age earnings analysis" },
  'Suezmax|MEG/EAST (MODERN)': { what: "Modern Suezmaxes carrying Middle East Gulf crude to Asia, the younger ship slice of the Gulf trade", drivers: "Gulf export programmes, Asian refiner demand, and how much modern tonnage competes for Gulf stems", affects: "Feeds the modern tonnage Worldscale screen owners and charterers benchmark period and spot decisions against" },
  'Suezmax|NOVO/USG': { what: "Suezmaxes loading Novorossiysk crude on the Black Sea for the US Gulf", drivers: "Russian Black Sea exports, sanctions and price cap trading patterns, and transatlantic tonnage supply", affects: "Feeds transatlantic Suezmax screens and tracks how far the Russian barrel reaches into the Atlantic" },
  'Suezmax|NSEA/USG': { what: "Suezmaxes moving North Sea crude across the Atlantic to the US Gulf", drivers: "North Sea loading programmes, US refiner demand, and transatlantic tonnage balance", affects: "Feeds Atlantic Suezmax Worldscale screens and crude destination arbitrage" },
  'Suezmax|NSEA/WCI': { what: "Suezmaxes carrying North Sea crude to India's west coast", drivers: "Indian demand for Atlantic grades, eastbound Suezmax supply, and competing Gulf barrels", affects: "Feeds USD TCE screens for Atlantic Suezmaxes going east" },
  'Suezmax|WAFR/THAILAND': { what: "Suezmaxes carrying West African crude to Thailand", drivers: "West African exports, Thai import programmes, and the Suezmax versus VLCC split on African stems", affects: "Feeds Worldscale screens on Africa to Asia runs for midsize tonnage" },
  'Suezmax|WAFR/UKC': { what: "Suezmaxes running West African crude to Northwest Europe", drivers: "Nigerian and Angolan programmes, European demand for sweet grades, and Atlantic tonnage supply", affects: "Feeds Atlantic Suezmax screens and the Europe versus Asia arbitrage for African barrels" },
  'Suezmax|WAFR/USG': { what: "Suezmaxes hauling West African crude to the US Gulf", drivers: "US refiners' sweet crude intake, West African export pace, and the Aframax versus Suezmax split of that trade", affects: "Feeds transatlantic Suezmax screens and US import freight budgets" },
  'Suezmax|WAFR/WCI': { what: "Suezmaxes moving West African crude to India's west coast", drivers: "Indian refiner demand, African export programmes, and how much tonnage stays in the Atlantic versus ballasting east", affects: "Feeds USD TCE screens for African Suezmaxes heading east" },
  'Aframax|BLSEA/MED': { what: "Aframaxes carrying Black Sea crude through the Turkish Straits to Mediterranean refineries", drivers: "Russian and Kazakh Black Sea loadings, strait transit delays, and Med refiner demand", affects: "Feeds the core Black Sea Med Worldscale screen for smaller tankers; strait queues can move it sharply" },
  'Aframax|BLSEA/USG': { what: "Aframaxes taking Black Sea crude across the Atlantic to the US Gulf", drivers: "US refiner demand, transatlantic Aframax supply, and competition from Atlantic cargoes", affects: "Feeds transatlantic Aframax screens and US import cost models" },
  'Aframax|CBS/USG': { what: "Aframaxes on the Caribbean to US Gulf short haul, the workhorse run moving Caribbean basin crude and products to Gulf refineries", drivers: "Regional export programmes, US Gulf refinery runs, and how many Aframaxes drift between the Caribbean and Europe", affects: "Feeds the benchmark short haul Worldscale screen for the Americas and US Gulf import freight budgets" },
  'Aframax|CEYHAN/MED': { what: "Aframaxes carrying Azeri BTC crude from Ceyhan to Mediterranean refineries", drivers: "BTC pipeline flows, Med refinery runs, and Med tonnage supply", affects: "Feeds Med crude Worldscale screens and BTC cargo marketing" },
  'Aframax|CEYHAN/UKC': { what: "Aframaxes moving BTC crude from Ceyhan north to the UK Continent", drivers: "BTC flows, European refiner demand, and tonnage positioning between the Med and Northern Europe", affects: "Feeds Med to Continent screens for Aframax crude runs" },
  'Aframax|CEYHAN/USG': { what: "Aframaxes hauling Azeri BTC crude across the Atlantic to the US Gulf", drivers: "BTC availability, US refiner demand for Azeri grades, and transatlantic tonnage", affects: "Feeds transatlantic Aframax screens and destination arbitrage for BTC cargoes" },
  'Aframax|KOZMINO/NORTH CHINA': { what: "Aframaxes loading ESPO blend crude at Kozmino on Russia's Pacific coast for North China", drivers: "ESPO pipeline and rail feed to Kozmino, Chinese independent refiner demand, and Pacific side tonnage", affects: "The USD assessment feeds Russian crude freight screens and the ESPO premium chain" },
  'Aframax|MINA AL AHMADI/SINGAPORE': { what: "Aframaxes on the assessed Middle East Gulf to Singapore run, moving Kuwaiti crude into Asia's largest refining hub", drivers: "Kuwaiti export programmes, Singapore refining activity, and Gulf tonnage availability", affects: "Feeds Gulf to Asia USD screens used in voyage estimates around the region" },
  'Aframax|PRIMORSK/MED': { what: "Aframaxes carrying Russian Baltic crude from Primorsk through the Danish straits to the Mediterranean", drivers: "Russian Baltic loadings, Danish strait transits, and Mediterranean demand for Urals", affects: "Feeds the Baltic outbound Worldscale screen that tracks where Russian barrels flow" },
  'Aframax|PRIMORSK/UKC': { what: "Aframaxes running Primorsk Baltic crude to Northwest European refineries", drivers: "Baltic loadings, Baltic to UKC tonnage, and North European refiner demand", affects: "Feeds short haul Baltic Worldscale screens and European import costs" },
  'Aframax|PRIMORSK/USAC': { what: "Aframaxes carrying Primorsk Baltic crude across the Atlantic to the US Atlantic coast", drivers: "Russian export patterns, US East Coast refiner demand, and transatlantic Aframax supply", affects: "Feeds transatlantic Aframax screens and tracks the Atlantic reach of Baltic barrels" },
  'Aframax|SERIA/GEELONG': { what: "Aframaxes running crude and condensate from Seria in Brunei to Geelong in southern Australia, a key intra Asia Pacific crude run", drivers: "Brunei output, Australian refinery demand, and Asia Pacific tonnage availability", affects: "Feeds the USD benchmark for intra Asia Pacific crude runs used in Australian import freight budgets" },
  'Aframax|UKC/WCI': { what: "Aframaxes taking UK Continent area crude to India's west coast", drivers: "North Sea grades offered east, Indian refiner demand, and the ballast balance of Europe to Asia tonnage", affects: "Feeds USD TCE screens for Europe to India crude runs" },
  'Aframax|USG/UKCM': { what: "Aframaxes moving US Gulf crude and dirty products to the UK Continent", drivers: "US export programmes, European demand for US grades, and transatlantic Aframax supply", affects: "Feeds the core transatlantic Worldscale screen for Aframax export economics" },
  'Aframax|WAF/UKCM': { what: "Aframaxes carrying West African crude to the UK Continent", drivers: "Nigerian and Angolan programmes, European sweet crude demand, and Atlantic tonnage", affects: "Feeds Atlantic Aframax screens and the Europe versus Asia arbitrage for African barrels" },
  'Aframax|WAF/USG': { what: "Aframaxes hauling West African crude across the Atlantic to the US Gulf", drivers: "US refiners' sweet crude appetite, West African export pace, and the Caribbean and Atlantic tonnage balance", affects: "Feeds the transatlantic Aframax screen underpinning US import freight budgets" },
  'Aframax|WCN/MED': { what: "Aframaxes moving crude from the west coast of Norway to Mediterranean refineries", drivers: "Norwegian loading programmes, Med refiner demand, and Northern European tonnage supply", affects: "Feeds North Sea to Med Worldscale screens for short long haul crude runs" },
  'Aframax|WCN/UKC': { what: "Aframaxes on the North Sea short haul, west coast Norway crude to UK Continent refineries", drivers: "Norwegian field loadings, UKC refinery runs, and intra North Sea tonnage", affects: "Feeds intra North Sea Worldscale screens" },
  'Aframax|WCN/USG': { what: "Aframaxes carrying west coast Norway crude across the Atlantic to the US Gulf", drivers: "US refiner demand for North Sea grades, and transatlantic Aframax availability", affects: "Feeds transatlantic Aframax screens and North Sea destination arbitrage" },
  'Aframax|FEAST/THAILAND': { what: "Aframaxes running stems from the Far East to Thailand, an intra Asia cargo marker", drivers: "Thai demand for regional crude and products, Asian trade flows, and intra Asia tonnage", affects: "Feeds the intra Asia USD screen used in regional voyage estimates" },
  'Aframax|DEMURRAGE BALTIC': { what: "Assessed daily demurrage compensation for Aframax delays in the Baltic loading region", drivers: "Baltic port congestion, ice seasons, and cargo stem delays", affects: "Feeds owner claim planning and charterer exposure on Baltic crude stems" },
  'Aframax|DEMURRAGE BSEA': { what: "Assessed demurrage for Aframax delays in the Black Sea", drivers: "Loading port congestion at CPC and Novorossiysk, plus queue spillover from the Turkish Straits", affects: "Feeds Black Sea voyage risk models; strait queues show up here first" },
  'Aframax|DEMURRAGE CBS/USG': { what: "Assessed demurrage for Aframax delays on the Caribbean and US Gulf trades", drivers: "US Gulf port congestion, berth queues, and late cargo stems", affects: "Feeds US import voyage cost models and demurrage claims exposure" },
  'Aframax|DEMURRAGE EAST': { what: "Assessed demurrage for Aframax delays east of Suez", drivers: "Asian port congestion, weather, and cargo timing slips", affects: "Feeds intra Asia voyage risk and charterer demurrage budgets" },
  'Aframax|DEMURRAGE MED': { what: "Assessed demurrage for Aframax delays in the Mediterranean", drivers: "Med terminal congestion, load port delays, and refinery scheduling", affects: "Feeds Med voyage models and owner claim planning" },
  'Aframax|DEMURRAGE NSEA': { what: "Assessed demurrage for Aframax delays in the North Sea area", drivers: "North Sea weather windows, terminal availability, and cargo stem delays", affects: "Feeds North Sea voyage risk; winter weather shows up directly here" },
  'Dirty|Caribs/USG': { what: "Worldscale assessment for smaller dirty tankers moving Caribbean crude and fuel oil to the US Gulf", drivers: "Regional export programmes, US Gulf refinery demand, and short haul tonnage supply", affects: "Feeds dirty Worldscale screens for the Americas and refiner freight budgets" },
  'Dirty|MEG/Japan': { what: "Dirty tanker assessment on the Middle East Gulf to Japan run, Japan's core seaborne crude supply lane", drivers: "Gulf export programmes, Japanese refinery runs, and big tanker availability in the Gulf", affects: "Feeds Gulf to Japan freight screens behind Japanese import costs and tanker earnings models" },
  'Dirty|MEG/Singapore': { what: "Dirty assessment on the Middle East Gulf to Singapore run into Asia's largest refining and storage hub", drivers: "Gulf crude exports and Singapore hub throughput demand", affects: "Feeds Gulf to Asia dirty screens used across Asian refiner freight budgets" },
  'Dirty|MEG/WEST': { what: "Dirty assessment for Middle East Gulf crude headed to destinations west of Suez", drivers: "The crude arbitrage between east and west: whether Gulf barrels outbid Atlantic grades in Europe and the Americas, plus Suez transit economics", affects: "Feeds the interbasin comparison screens that steer tonnage between east and west of Suez" },
  'Dirty|N. Afr/Euromed': { what: "Dirty assessment from North Africa to the Euro Med refining belt", drivers: "North African export stability, Med refinery runs, and short haul tonnage", affects: "Feeds Med dirty screens and European import costs" },
  'Dirty|Sidi Kerir/W Med': { what: "Dirty assessment from Sidi Kerir, Egypt's Mediterranean terminal, to the western Mediterranean", drivers: "Gulf barrels stored and re-exported through Sidi Kerir, W Med refinery demand, and strait transit conditions", affects: "Feeds the Med dirty benchmark that reacts fastest to Suez transit disruptions" },
  'Dirty|UK/Cont': { what: "Dirty assessment for the UK to Continent short sea run, North Sea crude and fuel oil across the Channel", drivers: "North Sea loadings, Channel refinery demand, and short haul tonnage", affects: "Feeds intra North Europe dirty screens" },
  'Dirty|WAF/FEAST': { what: "Dirty assessment from West Africa to the Far East, African crude on the long haul to Asian refineries", drivers: "Nigerian and Angolan programmes, Asian refiner demand, and the ballast balance between Africa and Asia", affects: "Feeds Africa to Asia dirty screens and long haul dirty tanker earnings" },
  'Dirty|WAF/USAC': { what: "Dirty assessment from West Africa to the US Atlantic coast", drivers: "US East Coast refiner demand for African grades, and Atlantic tonnage supply", affects: "Feeds Atlantic dirty screens and US import freight budgets" },
  '1 Year T/C|VLCC': { what: "The assessed one year timecharter rate for a VLCC, what owners earn per day letting a ship out for a year", drivers: "Expected spot earnings over the year, orderbook deliveries, and owners choosing period cover versus staying on spot", affects: "Feeds period coverage decisions, asset values, and tanker equity earnings guidance" },
  '1 Year T/C|Suezmax': { what: "The assessed one year timecharter rate for a Suezmax, the yearly earnings marker for midsize crude tankers", drivers: "Expected spot earnings over the year, Suezmax orderbook deliveries, and period appetite on both sides", affects: "Feeds period coverage decisions and midsize tanker asset valuations" },
  '1 Year T/C|Aframax': { what: "The assessed one year timecharter rate for an Aframax, the yearly earnings marker for the smaller crude classes", drivers: "Regional spot earnings expectations, newbuilding deliveries, and owners' period versus spot choices", affects: "Feeds period coverage decisions and regional tanker asset valuations" },
  'Fuel Oil|CBS-USG/SPORE': { what: "The assessed price gap between fuel oil at the Caribbean and US Gulf and fuel oil in Singapore, in USD per tonne", drivers: "Regional fuel oil balances, Singapore hub demand, and the cost of moving parcels between the two markets", affects: "Feeds fuel oil arbitrage screens and bunker purchasing decisions on both ends" },
  'Fuel Oil|SKAW/SPORE': { what: "The assessed price gap between fuel oil at Skaw in northern Europe and Singapore, in USD per tonne", drivers: "European and Asian fuel oil balances, east to west arbitrage economics, and parcel freight", affects: "Feeds the east to west fuel oil arbitrage screens bunker desks watch" },
  'Fuel Oil|USG/UKC': { what: "The assessed price gap between US Gulf and UK Continent fuel oil, in USD per tonne", drivers: "Atlantic fuel oil balances, European refiner output, and short haul parcel economics", affects: "Feeds intra Atlantic fuel oil arbitrage screens" },
  'WEEKLY VLCC|VLCCs available in MEG next 30 days': { what: "A weekly count of VLCCs expected open in the Gulf over the next 30 days, the supply side of the MEG market", drivers: "Ballast arrivals from Asia and the Atlantic, and how fast ships are fixed out of the Gulf", affects: "Feeds the tonnage supply half of the VLCC rate picture: more open ships, softer rates" },
  'WEEKLY VLCC|VLCCs fixed in all areas last week': { what: "A weekly count of VLCCs fixed worldwide the previous week, the demand pulse of the fleet", drivers: "Cargo programmes from OPEC and other exporters, and charterer fixing urgency", affects: "Feeds the demand half of the VLCC picture; read against open ship counts to gauge tightness" },
  'Counters|MEG Fixture Count': { what: "A weekly count of reported Middle East Gulf crude fixtures, how many cargoes found ships", drivers: "OPEC export volumes, tender activity, and charterer fixing pace", affects: "Feeds Gulf activity gauges; a high count with falling availability tightens the market" },
  'Capesize|Australia / China': { what: "The per tonne freight cost of shipping iron ore from Western Australia to China, the physical benchmark of the Cape trade", drivers: "Chinese steel mill activity and ore restocking, West Australian mine output and cyclone disruption, and Cape tonnage supply in the Pacific", affects: "Feeds iron ore trade economics and, via implied TCE, the earnings headline of the whole Capesize market" },
  'Capesize|Pacific Round Voyage': { what: "The assessed daily TCE for a Capesize round voyage inside the Pacific, typically Australian or South African cargo to China with the ballast leg back", drivers: "Chinese iron ore demand, coal programmes into North Asia, Pacific tonnage supply, and cyclone disruption", affects: "Feeds Capesize earnings screens for the Pacific and the route economics miners fix against" },
  'Capesize|Cont / Far East': { what: "The assessed daily TCE for a Capesize fronthaul from Northern Europe to the Far East, a loaded long haul with a long ballast back", drivers: "European export cargo such as coal and minerals, Far East demand, and how many Capesizes stay positioned in the Atlantic", affects: "Feeds fronthaul screens that tell owners whether to keep tonnage in the Atlantic or reposition east" },
  'Panamax|Cont / Far East': { what: "The assessed daily TCE for a Panamax fronthaul from Northern Europe to the Far East, typically grain, coal or minerals", drivers: "European export programmes, Far East demand, and Atlantic Panamax tonnage supply", affects: "Feeds fronthaul earnings screens and the Atlantic versus Pacific positioning call for Panamax owners" },
  'Panamax|Far East / Cont': { what: "The assessed daily TCE for a Panamax voyage loading in the Far East for discharge in Northern Europe", drivers: "Pacific export cargo going beyond Asia, European import demand, and the backhaul discount owners accept to reposition", affects: "Feeds backhaul screens: cheap east to west legs that reset the Atlantic tonnage balance" },
  'Panamax|Far East Round Voyage': { what: "The assessed daily TCE for a Panamax round voyage inside the Pacific, the core Asia employment loop", drivers: "North Pacific grain, Australian and Indonesian coal, Pacific tonnage counts, and weather", affects: "Feeds the Pacific Panamax earnings headline and index linked period negotiations" },
  'Panamax|Transatlantic Round Voyage': { what: "The assessed daily TCE for a Panamax round voyage in the Atlantic, US Gulf or South American grain and coal with the ballast loop back", drivers: "US Gulf and South Atlantic export pace, European demand, and Atlantic tonnage supply", affects: "Feeds the Atlantic Panamax earnings headline and the Atlantic versus Pacific spread owners watch" },
  'Supramax|South China / Indonesia RV': { what: "The assessed daily TCE for a Supramax round voyage between Indonesia and South China, mostly coal and minor bulks", drivers: "Indonesian coal export volumes, regional buying, and intra Asia Supramax supply", affects: "Feeds the intra Asia Supramax earnings benchmark for Asian operators" },
  'Supramax|Transatlantic Round Voyage': { what: "The assessed daily TCE for a Supramax round voyage across the Atlantic, grains, fertilisers and minor bulks between the Americas, Europe and Africa", drivers: "US Gulf and South American export programmes, European and African demand, and Atlantic Supramax supply", affects: "Feeds the Atlantic Supramax earnings benchmark; the published series averages the source's two raw assessments" },
  'Supramax|US Gulf / China-South Japan': { what: "The assessed daily TCE for a Supramax fronthaul from the US Gulf to China or South Japan, typically grain and minor bulks", drivers: "US Gulf export pace, Asian demand for US bulk cargoes, and how many Supramaxes ballast to the Gulf", affects: "Feeds the US Gulf Supramax earnings screen and fronthaul freight budgets for Asian importers" }
};

var FDESK_KLASS_NOTES = {
  'VLCC': 'Very Large Crude Carriers of around 300,000 dwt, the biggest crude tankers, hauling the long haul Middle East to Asia trades that set the tanker market tone',
  'Suezmax': 'Midsize crude tankers of around 155,000 dwt, the largest ships that can transit the Suez Canal fully laden',
  'Aframax': 'Smaller crude tankers of around 100,000 dwt, the workhorses of short haul and regional trades',
  'Dirty': 'Dirty tanker benchmarks on regional runs, smaller tankers carrying crude and heavy fuel oil between nearby hubs',
  '1 Year T/C': 'One year timecharter assessments, what a day of ownership earns on a yearly contract for each class',
  'Fuel Oil': 'Fuel oil price assessments, the gap between fuel oil at two hubs in USD per tonne, the arbitrage bunker and fuel oil desks watch',
  'WEEKLY VLCC': 'Weekly counts around the VLCC fleet, how many ships are open in the Gulf and how many were fixed last week',
  'Counters': 'Fixture count gauges, how many cargoes were actually fixed, a direct read of market activity',
  'Capesize': 'The largest dry bulk ships, built for iron ore and coal, the Australian to China ore run is their benchmark cargo',
  'Panamax': 'Midsize dry bulk ships sized for the Panama Canal historically, grain and coal are their core cargoes',
  'Supramax': 'Handy midsize dry bulk ships lifting grains, minor bulks and coal on regional trades'
};
'''
rep(43047, KB + "\nfunction fearnDeltaOf(s) {", "function fearnDeltaOf(s) {")

# ---------------- 11. fearn-route-state branch L41178-41189
rep_span("fearn-route-state", "fearn-tank-tile", """        else if (type === 'fearn-route-state') {
          const live = target.getAttribute('data-tt-live') === '1';
          const lastD = target.getAttribute('data-tt-last') || '';
          const metaNotes = (window.FDESK_TANKER_META && FDESK_TANKER_META.notes) || (window.FDESK_DRY_META && FDESK_DRY_META.notes) || '';
          html = `<div class="rt-title">${live ? 'Live Series' : 'Frozen Series'}</div>`;
          html += `<div class="rt-row"><span class="rt-label">State</span><span class="rt-val" style="color:${live ? 'var(--green)' : 'var(--text-muted)'};">${live ? 'LIVE' : 'FROZEN'}</span></div>`;
          if (lastD) html += `<div class="rt-row"><span class="rt-label">Last Print</span><span class="rt-val">${escapeHtml(lastD)}</span></div>`;
          if (!live && metaNotes) html += `<div class="rt-note">${escapeHtml(String(metaNotes).slice(0, 320))}</div>`;
          else html += `<div class="rt-note">${live ? 'Live: assessed daily, still publishing.' : 'Frozen: the source stopped publishing this series; the cache keeps its real history and never backfills it.'}</div>`;
        }""",
    "fearn-route-state")

# ---------------- 12. fearn-tank-tile / fearn-dry-tile branch L41191-41220
rep_span("fearn-tank-tile", "fearn-tank-klass-tab", """        else if (type === 'fearn-tank-tile' || type === 'fearn-dry-tile') {
          const j = type === 'fearn-tank-tile' ? (window.DATA && DATA.fearnleysTankerRoutesDaily) : (window.DATA && DATA.fearnleysDryRoutesDaily);
          const code = target.getAttribute('data-tt-code');
          const s = (j && j.series && j.series[code]) ? Object.assign({ code: code }, j.series[code]) : null;
          if (s) {
            const pts = s.pts || [];
            const n = pts.length;
            const last = n ? pts[n - 1] : null;
            const prev = n > 1 ? pts[n - 2] : null;
            const iso = (ms) => new Date(ms).toISOString().slice(0, 10);
            const fmt = (v) => (v == null ? '\\u2014' : (v % 1 === 0 ? Number(v).toLocaleString('en-US') : Number(v).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 2 })));
            const unitName = (u) => u === 'ws' ? 'Worldscale points' : (u === 'tce' ? 'USD/day TCE' : (u === 'usd/day' ? 'USD/day' : (u === 'usd/tonne' ? 'USD/tonne' : (u === 'count' ? 'fixtures (count)' : (u === 'usd' ? 'USD' : String(u))))));
            const live = (s.last || '') >= '2026-08-01';
            const kb = (window.FDESK_ROUTE_KB && FDESK_ROUTE_KB[(s.klass || '') + '|' + (s.route || '')]) || null;
            const built = type === 'fearn-tank-tile' ? (window.FDESK_TANKER_META && FDESK_TANKER_META.builtUtc) : (window.FDESK_DRY_META && FDESK_DRY_META.builtUtc);
            html = `<div class="rt-title">${escapeHtml(s.label)}</div>`;
            if (last) html += `<div class="rt-row"><span class="rt-label">Last</span><span class="rt-val">${fmt(last[1])} \\u00b7 ${iso(last[0])}</span></div>`;
            if (prev) { const d = last[1] - prev[1]; html += `<div class="rt-row"><span class="rt-label">Day Delta</span><span class="rt-val ${d > 0 ? 'pos' : (d < 0 ? 'neg' : '')}">${d > 0 ? '+' : ''}${fmt(d)} vs ${fmt(prev[1])} (${iso(prev[0])})</span></div>`; }
            html += `<div class="rt-row"><span class="rt-label">First Obs</span><span class="rt-val">${escapeHtml(String(s.first || '\\u2014'))}</span></div>`;
            html += `<div class="rt-row"><span class="rt-label">Last Obs</span><span class="rt-val">${escapeHtml(String(s.last || '\\u2014'))}</span></div>`;
            if (s.n != null) html += `<div class="rt-row"><span class="rt-label">Observations</span><span class="rt-val">${Number(s.n).toLocaleString('en-US')} pts</span></div>`;
            if (s.cadence) html += `<div class="rt-row"><span class="rt-label">Cadence</span><span class="rt-val">${escapeHtml(String(s.cadence))}</span></div>`;
            if (s.unit) html += `<div class="rt-row"><span class="rt-label">Unit</span><span class="rt-val">${escapeHtml(unitName(s.unit))}</span></div>`;
            html += `<div class="rt-row"><span class="rt-label">State</span><span class="rt-val" style="color:${live ? 'var(--green)' : 'var(--text-muted)'};">${live ? 'Live: assessed daily, still publishing' : 'Frozen: source stopped publishing, history preserved'}</span></div>`;
            if (s.derivation) html += `<div class="rt-row"><span class="rt-label">Derivation</span><span class="rt-val">${escapeHtml(String(s.derivation))}</span></div>`;
            if (s.klass) html += `<div class="rt-row"><span class="rt-label">Group</span><span class="rt-val">${escapeHtml(String(s.klass))}</span></div>`;
            if (kb) {
              html += `<div class="rt-row"><span class="rt-label">What it is</span><span class="rt-val">${escapeHtml(kb.what)}</span></div>`;
              html += `<div class="rt-row"><span class="rt-label">What moves it</span><span class="rt-val">${escapeHtml(kb.drivers)}</span></div>`;
              html += `<div class="rt-row"><span class="rt-label">What it feeds</span><span class="rt-val">${escapeHtml(kb.affects)}</span></div>`;
            }
            html += `<div class="rt-note">Fearnleys daily assessments${built ? ' \\u00b7 fetched ' + escapeHtml(String(built)) : ''}</div>`;
          } else {
            html = `<div class="rt-title">Route Tile</div><div class="rt-note">Daily data still loading: hover again in a moment; nothing is estimated.</div>`;
          }
        }""",
    "fearn-tank-tile")

# ---------------- 13. fearn-tank-klass-tab branch L41222-41246
rep_span("fearn-tank-klass-tab", "fearn-tank-chart'", """        else if (type === 'fearn-tank-klass-tab') {
          const k = target.getAttribute('data-tt-klass') || '';
          const j = window.DATA && DATA.fearnleysTankerRoutesDaily;
          const kk = (j && j.index && j.index.klasses && j.index.klasses[k]) || null;
          // shown = series the tab grid actually renders (all-zero excluded);
          // archived = the branches the source never published values in.
          let shown = 0, archived = 0;
          if (j && j.series) {
            Object.keys(j.series).forEach((code) => {
              const s = j.series[code];
              if (s.klass !== k) return;
              const pts = s.pts || [];
              const allZero = pts.length > 0 && pts.every((p) => p[1] === 0);
              if (allZero) archived++; else shown++;
            });
          }
          const klassNote = (window.FDESK_KLASS_NOTES && FDESK_KLASS_NOTES[k]) || ('Vessel group ' + k);
          html = `<div class="rt-title">Route Group: ${escapeHtml(k)}</div>`;
          html += `<div class="rt-row"><span class="rt-label">Series</span><span class="rt-val">${Number(shown).toLocaleString('en-US')} shown</span></div>`;
          if (archived > 0) html += `<div class="rt-row"><span class="rt-label">Archived</span><span class="rt-val">${Number(archived).toLocaleString('en-US')} not shown: source published no values; USD/WS twins carry the routes</span></div>`;
          if (kk) {
            html += `<div class="rt-row"><span class="rt-label">Points</span><span class="rt-val">${Number(kk.pts).toLocaleString('en-US')}</span></div>`;
            html += `<div class="rt-row"><span class="rt-label">Span</span><span class="rt-val">${escapeHtml(String(kk.first || '\\u2014'))} \\u2192 ${escapeHtml(String(kk.last || '\\u2014'))}</span></div>`;
          }
          html += `<div class="rt-note">${escapeHtml(klassNote)}. Switches the tile grid to this group.</div>`;
        }""",
    "fearn-tank-klass-tab")

# ---------------- 14. fearn-tank-chart / fearn-dry-chart branch L41248-41275
rep_span("type === 'fearn-tank-chart' || type === 'fearn-dry-chart'", "fearn-tank-chart-select", """        else if (type === 'fearn-tank-chart' || type === 'fearn-dry-chart') {
          const isTank = type === 'fearn-tank-chart';
          const j = isTank ? (window.DATA && DATA.fearnleysTankerRoutesDaily) : (window.DATA && DATA.fearnleysDryRoutesDaily);
          const code = isTank ? (window.FDESK && FDESK.tankRoute) : (window.FDESK && FDESK.dryRoute);
          const s = (j && j.series && j.series[code]) ? j.series[code] : null;
          if (s) {
            const pts = s.pts || [];
            const last = pts.length ? pts[pts.length - 1] : null;
            const fmt = (v) => (v == null ? '\\u2014' : (v % 1 === 0 ? Number(v).toLocaleString('en-US') : Number(v).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 2 })));
            const kb = (window.FDESK_ROUTE_KB && FDESK_ROUTE_KB[(s.klass || '') + '|' + (s.route || '')]) || null;
            const built = isTank ? (window.FDESK_TANKER_META && FDESK_TANKER_META.builtUtc) : (window.FDESK_DRY_META && FDESK_DRY_META.builtUtc);
            html = `<div class="rt-title">${escapeHtml(s.label)}: Daily Chart</div>`;
            html += `<div class="rt-row"><span class="rt-label">Plotted</span><span class="rt-val">${pts.length ? Number(pts.length).toLocaleString('en-US') + ' daily observations' : '\\u2014'}</span></div>`;
            if (pts.length) html += `<div class="rt-row"><span class="rt-label">Span</span><span class="rt-val">${escapeHtml(String(s.first))} \\u2192 ${escapeHtml(String(s.last))}</span></div>`;
            if (last) html += `<div class="rt-row"><span class="rt-label">Latest print</span><span class="rt-val">${fmt(last[1])} \\u00b7 ${new Date(last[0]).toISOString().slice(0, 10)}</span></div>`;
            if (kb) html += `<div class="rt-row"><span class="rt-label">What it is</span><span class="rt-val">${escapeHtml(kb.what)}</span></div>`;
            html += `<div class="rt-note">Hover the line for exact date and value. Points pass through uninterpolated: gaps stay gaps.${kb ? ' ' + escapeHtml(kb.drivers) : ''}${built ? ' Fearnleys daily assessments \\u00b7 fetched ' + escapeHtml(String(built)) : ''}</div>`;
          } else {
            html = `<div class="rt-title">Daily Chart</div><div class="rt-note">Pick a route tile above: the chart opens once its data loads; nothing simulated is plotted.</div>`;
          }
        }""",
    "fearn-tank-chart")

# ---------------- 15. select branches L41277-41287
rep_span("fearn-tank-chart-select", "html = '';\n        }", """        else if (type === 'fearn-tank-chart-select') {
          const j = window.DATA && DATA.fearnleysTankerRoutesDaily;
          const n = j && j.series ? Object.keys(j.series).length : 0;
          const code = target.value || (window.FDESK && FDESK.tankRoute);
          const s = (j && j.series && j.series[code]) ? j.series[code] : null;
          html = `<div class="rt-title">Route Picker</div>`;
          if (n) html += `<div class="rt-row"><span class="rt-label">Routes</span><span class="rt-val">${Number(n).toLocaleString('en-US')}</span></div>`;
          if (s) html += `<div class="rt-row"><span class="rt-label">Active</span><span class="rt-val">${escapeHtml(String(s.label))}</span></div>`;
          html += `<div class="rt-note">Pick any route to replot its daily chart on the tanker panel.</div>`;
        }
        else if (type === 'fearn-dry-chart-select') {
          const j = window.DATA && DATA.fearnleysDryRoutesDaily;
          const n = j && j.series ? Object.keys(j.series).length : 0;
          const code = target.value || (window.FDESK && FDESK.dryRoute);
          const s = (j && j.series && j.series[code]) ? j.series[code] : null;
          html = `<div class="rt-title">Benchmark Picker</div>`;
          if (n) html += `<div class="rt-row"><span class="rt-label">Benchmarks</span><span class="rt-val">${Number(n).toLocaleString('en-US')}</span></div>`;
          if (s) html += `<div class="rt-row"><span class="rt-label">Active</span><span class="rt-val">${escapeHtml(String(s.label))}</span></div>`;
          html += `<div class="rt-note">Pick any dry route benchmark to replot its daily chart.</div>`;
        }""",
    "fearn-tank-chart-select")

# ---------------- 16. two loading notes inside the branches (now shifted; do by marker later)
# ---------------- 17. phKpi chip L36800
rep(36800,
    "      chips += '<div class=\"ph-kpi-chip\"><div class=\"k\">' + escapeHtml(port.portname) + '</div><div class=\"v\">\\u2014</div><div class=\"s\" style=\"color:var(--text-muted);\">No ' + measure.toLowerCase() + ' readings in the shown window</div></div>';",
    "No ' + measure.toLowerCase()")

# ---------------- 18. static dry grid title L13690
rep(13690,
    '            <div class="chart-title" data-tooltip="Daily dry route benchmarks from Fearnleys: Capesize, Panamax and Supramax daily points. Each tile carries its own launch date because the source started these assessments at different dates; per-series depth is shown, never averaged away. Click a tile for its full daily chart.">Dry Route Benchmarks <span id="fearnDryCount" style="font-size:11px;color:var(--text-muted);font-weight:400;"></span></div>',
    "Baltic dry-route assessments")

out = "\n".join(lines)
print("pass 1 done, lines now:", len(lines), "(was", orig, ")")

# ================= EM DASH PASS (after pass-1 rewrites; bounds recomputed) =================
EMD = chr(0x2014)
txt2 = "\n".join(lines)

# fn bounds recompute
hdr = txt2.find("function getCalculatedTooltip(")
assert hdr > 0
hend = txt2.find("\n      }\n", hdr)
assert hend > 0

fnb = txt2.find("function getCalculatedTooltip(")
fne = txt2.find("\n      }\n", fnb)
assert fnb > 0 and fne > fnb

region = txt2[fnb:fne]
EMD = chr(0x2014)
n_sp = region.count(" " + EMD + " ")
region2 = region.replace(" " + EMD + " ", ": ")
n_ph = region2.count("'" + EMD + "'")
region2 = region2.replace("'" + EMD + "'", "'n/a'")
# any stray em dash without surrounding spaces (e.g. '—x' or 'x—')
n_stray = region2.count(EMD)
region2 = region2.replace(EMD, ", ")
print("fn-region: space-pairs", n_sp, "| placeholders", n_ph, "| stray", n_stray)
txt2 = txt2[:fnb] + region2 + txt2[fne:]

hdr = txt2.find("function getCalculatedTooltip(")
hend = txt2.find("\n      }\n", hdr)
rem = txt2[hdr:hend].count(EMD)
print("EM DASH REMAINING IN FN:", rem)
assert rem == 0, "em dashes remain in getCalculatedTooltip"

io.open(P, "w", encoding="utf-8", newline="").write("\r\n".join(txt2.split("\n")))
print("em pass written; final lines:", txt2.count("\n") + 1)
