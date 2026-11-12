# P4b flagged-extraction sample (C1 review packet)

Seed 15063620 (`seed_for("P4B_FLAGGED")`), 30 of 304 flagged reference records ({'keep': 273, 'drop': 31, 'unadjudicated': 0}). Flagged = exactly one reference model extracted it; the third-family adjudicator (nvidia/nemotron-3-ultra-550b-a55b) decided keep/drop.

Review question per item: does the quote support the record as written? Mark `ok / over-claim / wrong entity / wrong number / missing (should have been extraced)`.

### 1. KEEP -> Intermodal Shipbrokers 2021-09-21 (broker_weekly)

- chunk `12d737bf1e550b84d87c840194e0f280` doc `dd5a0b7266a4db6c` ord-packed gold item; source data/extracted/md/intermodal/2021/intermodal_2021_W37_Intermodal-Report-Week-37-2021.md
- flagged by `glm-5.3`: `state_facts` type `LISTED_AS`, entities ['company:new:trafigura_group', 'publisher:new:singapore_stock_exchange']
- quote: "The notes will be listed on the Singapore Stock Exchange, with Trafigura aiming to redeem the debt within six years."
- record: `{"type": "LISTED_AS", "src": "company:new:trafigura_group", "dst": "publisher:new:singapore_stock_exchange", "attrs_printed": [{"key": "exchange", "value_as_printed": "Singapore Stock Exchange"}], "valid_from_printed": "", "valid_to_printed": "", "chunk": "c2", "sids": [4], "confidence": 0.8}`
- adjudicator: keep - Sentence 4 explicitly states notes listed on Singapore Stock Exchange

### 2. KEEP -> Intermodal Shipbrokers 2023-11-14 (broker_weekly)

- chunk `c57c67f2470c95d97f330b8c16be5642` doc `2067584eb105858a` ord-packed gold item; source data/extracted/md/intermodal/2023/intermodal_2023_W45_Intermodal-Report-Week-45-2023.md
- flagged by `glm-5.3`: `claims` type `forecast`, entities []
- quote: "Given the typical surge in U.S. soybean exports from September to November, such activity from China may lead to an increase in demand for Kamsarmax and Ultramax/Supramax vessels, which is likely to support their rates at least in the grain trade."
- record: `{"kind": "forecast", "subjects": [], "direction": "up", "horizon_printed": "September to November", "chunk": "c5", "sids": [6], "confidence": 0.75}`
- adjudicator: keep - Forecast claim matches quoted sentence about soybean export surge supporting vessel rates.

### 3. KEEP -> Seabrokers Chartering 2026-08-01 (broker_monthly)

- chunk `fd14f7db2b053bcf7638de2aea7e7cae` doc `476b408c93849d36` ord-packed gold item; source data/extracted/md/seabrokers/2026/2026-08-01_market-report-august-2026.md
- flagged by `glm-5.3`: `state_facts` type `RENAMED`, entities ['vessel:new:ocean_pearl']
- quote: "The Swissco Pearl AHTS vessel has been renamed as the Ocean Pearl following her recent acquisition by the J M Baxi Group in India."
- record: `{"type": "RENAMED", "src": "vessel:new:ocean_pearl", "dst": "vessel:new:ocean_pearl", "attrs_printed": [{"key": "from", "value_as_printed": "Swissco Pearl"}, {"key": "to", "value_as_printed": "Ocean Pearl"}], "valid_from_printed": "", "valid_to_printed": "", "chunk": "c3", "sids": [0], "confidence": 0.9}`
- adjudicator: keep - Renaming explicitly stated in sentence 0.

### 4. KEEP -> GMS Inc. 2025-02-28 (broker_weekly)

- chunk `e9c5c7f17ccadadda3fd2b4ed2d080f2` doc `d20bbf57ac036473` ord-packed gold item; source data/extracted/md/hellenic/demolition/gms/2025/gms_2025-02-28_week-09_dwindling-surge.md
- flagged by `glm-5.3`: `claims` type `view`, entities []
- quote: "Fundamentals continue afflict their pricing strategy as well as subdued import and local steel plate prices that continue face weekly jitters, all while the Lira remains in freefall as it collapsed another 20 basis points to end the week at TRY 36.53. Certainly not an even playing field for Aliaga recyclers under the current environment.

**NO MARKET SALES REPORTED**"
- record: `{"kind": "view", "subjects": [], "direction": "na", "horizon_printed": "", "chunk": "c6", "sids": [2], "confidence": 0.6}`
- adjudicator: keep - Quote matches chunk sentence 2 exactly with all numbers and text present

### 5. KEEP -> Frontline plc 2026-02-27 (sec_6k)

- chunk `80d1c9037f0ab5b3d7f368272d36c4c2` doc `0c23f8501d1bf20d` ord-packed gold item; source corpus/10-companies/FRO/6-K/FRO_6-K_2026-02-27_0000919574-26-001430.md
- flagged by `glm-5.3`: `events` type `other`, entities ['company:cik0000913290']
- quote: "As of today, six of the vessels have been delivered to the new owner with the remaining two vessels scheduled to be delivered during March 2026. After commissions and repayment of existing debt on the vessels, the transaction is expected to generate net cash proceeds of approximately \$477.2 million and the Company expects to record a gain in the first quarter of 2026 of approximately \$212.0 mill"
- record: `{"type": "other", "summary": "Six of the eight sold VLCCs have been delivered to the new owner, remaining two scheduled for delivery during March 2026; transaction expected to generate net cash proceeds of approximately $477.2 million and a Q1 2026 gain of approximately $212.0 million", "roles": [{"role": "owner", "entity": "company:cik0000913290"}], "when_printed": "As of today", "magnitude_printed": "$477.2 million", "chunk": "c5", "sids": [8], "confidence": 0.85}`
- adjudicator: keep - All numbers, dates, and details match the quoted sentence exactly.

### 6. KEEP -> Gibson Shipbrokers 2026-10-02 (broker_weekly)

- chunk `189b6d9be8efa0af25056589b0743665` doc `4b79d075d26b4051` ord-packed gold item; source data/extracted/md/gibson/2026/gibson_2026-10-02_running-out-of-room.md
- flagged by `glm-5.3`: `events` type `production_guidance`, entities ['country:US']
- quote: "According to Kpler data, exports peaked at around 5.2 mbd in Q2, when releases from the US SPR lifted volumes by close to 1.3 mbd, or more than 30%, on the previous quarter."
- record: `{"type": "production_guidance", "summary": "US crude exports peaked at around 5.2 mbd in Q2, with SPR releases lifting volumes by close to 1.3 mbd or more than 30% on the previous quarter", "roles": [{"role": "subject", "entity": "country:US"}], "when_printed": "Q2", "magnitude_printed": "5.2 mbd", "chunk": "c2", "sids": [2], "confidence": 0.8}`
- adjudicator: keep - Record accurately reflects Kpler data on US crude export peak and SPR impact in Q2.

### 7. DROP -> Gibson Shipbrokers 2026-10-02 (broker_weekly)

- chunk `1d20b71b21b159b7b28bc6b3629e5ad0` doc `4b79d075d26b4051` ord-packed gold item; source data/extracted/md/gibson/2026/gibson_2026-10-02_running-out-of-room.md
- flagged by `glm-5.3`: `events` type `market_move`, entities []
- quote: "The market opened with cross-UKC rates around WS430, owners benefiting from the substantial tightening seen over previous weeks.  Consequently, rates only softened modestly, ending the week around WS410-420 for UKC business."
- record: `{"type": "market_move", "summary": "North Sea cross-UKC rates opened around WS430 and ended the week around WS410-420, softening modestly", "roles": [], "when_printed": "ending the week", "magnitude_printed": "WS410-420", "chunk": "c3", "sids": [1, 4], "confidence": 0.8}`
- adjudicator: drop - Name "North Sea" not in quoted sentences; evidence lacks that term

### 8. DROP -> Intermodal Shipbrokers 2023-11-14 (broker_weekly)

- chunk `3cff270a0f753c92af06e56241102a22` doc `2067584eb105858a` ord-packed gold item; source data/extracted/md/intermodal/2023/intermodal_2023_W45_Intermodal-Report-Week-45-2023.md
- flagged by `glm-5.3`: `events` type `market_move`, entities []
- quote: "In terms of fundamentals, the local currency continues its rapid depreciation against the USD, currently trading at 283. In Turkey, steel prices are rising modestly, while offer prices remain broadly unchanged."
- record: `{"type": "market_move", "summary": "Pakistani rupee continues rapid depreciation against USD, currently trading at 283", "roles": [], "when_printed": "currently", "magnitude_printed": "283", "chunk": "c1", "sids": [9], "confidence": 0.75}`
- adjudicator: drop - Currency not explicitly named as Pakistani rupee in quote.

### 9. DROP -> Baltic Exchange 2016-12-30 (broker_weekly)

- chunk `3fcf8b568d6f5cba027fca760bd5b72e` doc `1417cb2f50e134dc` ord-packed gold item; source data/extracted/md/baltic/tanker/2016/2016_tanker-report-week52016_tanker.md
- flagged by `deepseek-v4-pro`: `state_facts` type `FIXED`, entities ['company:new:vitol', 'vessel:imo:9890989']
- quote: "In West Africa, the market has held steady at WS 65 for China discharge, while in the North Sea, the *Nave Electron* is said to have gone to Vitol from Hound Point to South Korea at $6.725 million."
- record: `{"type": "FIXED", "src": "vessel:imo:9890989", "dst": "company:new:vitol", "attrs_printed": [{"key": "rate", "value_as_printed": "$6.725 million"}], "valid_from_printed": "", "valid_to_printed": "", "chunk": "c2", "sids": [4], "confidence": 0.7}`
- adjudicator: drop - Vessel IMO 9890989 not mentioned in chunk

### 10. DROP -> Affinity Shipbrokers 2024-10-04 (broker_weekly)

- chunk `9c23e9d27146fa831b02eeb112108faf` doc `348bdb30de415bd4` ord-packed gold item; source data/extracted/md/affinity/2024/affinity_2024_Affinity-Tanker-Weekly-04.10.2024-HSN.md
- flagged by `glm-5.3`: `events` type `market_move`, entities ['country:AE', 'port:SAJUB', 'port:SARTA']
- quote: "LR2s and MRs offering better flexibility and efficiency on USD/T and rate perspectives have naturally softened distinctly, finally leading to some public testing with USD 375,000 on subs for UAE/Kuwait - a notable change from the USD 600,000 fixed last week for Jubail/Ras Tanura!"
- record: `{"type": "market_move", "summary": "LR1 public testing with USD 375,000 on subs for UAE/Kuwait, change from USD 600,000 fixed last week for Jubail/Ras Tanura", "roles": [{"role": "country", "entity": "country:AE"}, {"role": "port", "entity": "port:SAJUB"}, {"role": "port", "entity": "port:SARTA"}], "when_printed": "this week", "magnitude_printed": "USD 375,000 on subs, USD 600,000 fixed last week", "chunk": "c1", "sids": [6], "confidence": 0.85}`
- adjudicator: drop - Record misidentifies LR2/MR testing as LR1; entities include UAE/Kuwait not in record

### 11. KEEP -> The Signal Group 2023-05-22 (broker_weekly)

- chunk `689ca25014b97ecb9aad195823f6373f` doc `bf1f56a9ccec4df5` ord-packed gold item; source data/extracted/md/signal/newsroom/2023/the-signal-ocean-platform-port-congestion.md
- flagged by `glm-5.3`: `events` type `port_congestion`, entities ['port:new:black_sea']
- quote: "As depicted in Image 2, a few days prior to late April, the number of congested vessels in the Black Sea reached its highest point since the beginning of this year, surpassing the levels observed in 2022. The ongoing grain geopolitical conflicts between Russia and Ukraine have contributed to critical port congestion issues for small bulker vessels that have yet to be resolved."
- record: `{"type": "port_congestion", "summary": "Black Sea small bulker congestion reached its highest point since the beginning of the year before late April, surpassing 2022 levels", "roles": [{"role": "entity", "entity": "port:new:black_sea"}], "when_printed": "a few days prior to late April", "magnitude_printed": "highest point since the beginning of this year", "chunk": "c2", "sids": [7], "confidence": 0.85}`
- adjudicator: keep - All record fields match chunk sentence 7 exactly.

### 12. KEEP -> Frontline plc 2026-02-27 (sec_6k)

- chunk `b5044bb3bd7672dcfc1c5cb337db3626` doc `0c23f8501d1bf20d` ord-packed gold item; source corpus/10-companies/FRO/6-K/FRO_6-K_2026-02-27_0000919574-26-001430.md
- flagged by `glm-5.3`: `events` type `newbuilding_wave`, entities ['company:cik0000913290']
- quote: "The overall tanker order book for the asset classes Frontline owns is now 22.2% of the existing global fleet, with 163,123, and 165 vessels on order for VLCCs, Suezmax tankers and LR2 tankers, respectively."
- record: `{"type": "newbuilding_wave", "summary": "The overall tanker order book for Frontline's asset classes is 22.2% of the existing global fleet, with 163, 123 and 165 vessels on order for VLCCs, Suezmax and LR2 tankers respectively", "roles": [{"role": "entity", "entity": "company:cik0000913290"}], "when_printed": "now", "magnitude_printed": "22.2%", "chunk": "c4", "sids": [9], "confidence": 0.85}`
- adjudicator: keep - Order book data matches chunk sentence 9 exactly

### 13. DROP -> Affinity Shipbrokers 2024-10-04 (broker_weekly)

- chunk `9453b056d9a059790b17abae27f453ad` doc `348bdb30de415bd4` ord-packed gold item; source data/extracted/md/affinity/2024/affinity_2024_Affinity-Tanker-Weekly-04.10.2024-HSN.md
- flagged by `deepseek-v4-pro`: `claims` type `view`, entities ['route:TC14']
- quote: "A lack of volume coupled with a sufficient tonnage list has left rates grounded around WS 90 for TC2."
- record: `{"kind": "view", "subjects": ["route:TC14"], "direction": "down", "horizon_printed": "", "chunk": "c3", "sids": [1], "confidence": 0.9}`
- adjudicator: drop - Evidence quote references TC2, not TC14.

### 14. DROP -> The Signal Group 2023-05-22 (broker_weekly)

- chunk `87a1495a1223b632e779a8266afff1c6` doc `bf1f56a9ccec4df5` ord-packed gold item; source data/extracted/md/signal/newsroom/2023/the-signal-ocean-platform-port-congestion.md
- flagged by `glm-5.3`: `claims` type `causal`, entities []
- quote: "**What vessel types does the Signal Ocean Port Congestion API cover?** The API covers dry bulk and tanker vessels, including Capesize, VLOC, Panamax, Supramax, Handysize, Suezmax, and MR vessel classes.

**How far back does the historical data go?** Signal Ocean's Port Congestion API provides ten years of historical data, enabling trend analysis and benchmarking against prior congestion cycles.

*"
- record: `{"kind": "causal", "subjects": [], "direction": "up", "horizon_printed": "", "chunk": "c3", "sids": [0], "confidence": 0.6}`
- adjudicator: drop - Evidence lacks explicit causal statement

### 15. KEEP -> Affinity Shipbrokers 2024-10-04 (broker_weekly)

- chunk `d8ad69fd7bbd37fba6126fd3a0111f3f` doc `348bdb30de415bd4` ord-packed gold item; source data/extracted/md/affinity/2024/affinity_2024_Affinity-Tanker-Weekly-04.10.2024-HSN.md
- flagged by `glm-5.3`: `claims` type `view`, entities []
- quote: "Tonnage lists are getting dangerously thin with owners very much in the driving seat to push rates further north, especially when considering that regional tensions remain on a knife’s edge."
- record: `{"kind": "view", "subjects": [], "direction": "up", "horizon_printed": "", "chunk": "c2", "sids": [9], "confidence": 0.75}`
- adjudicator: keep - Quote matches sentence 9 exactly

### 16. DROP -> Alfred A. Knopf 2013-01-01 (book)

- chunk `e75b15e0bb6c33ef356ab7ce2ddd140f` doc `b08cda40d686f030` ord-packed gold item; source corpus/books/sea_and_civilization_paine.md
- flagged by `deepseek-v4-pro`: `state_facts` type `RENAMED`, entities ['vessel:imo:5122750']
- quote: "The inaugural run of Fulton's forty-five-meter-long side-wheel steamer, the North River Steam Boat, took place on the Hudson River between New York and Albany in 1807; after that there was no looking back."
- record: `{"type": "RENAMED", "src": "vessel:imo:5122750", "dst": "vessel:imo:5122750", "attrs_printed": [{"key": "from", "value_as_printed": "North River Steam Boat"}, {"key": "to", "value_as_printed": "North River Steam Boat"}], "valid_from_printed": "", "valid_to_printed": "", "chunk": "c2", "sids": [1], "confidence": 0.3}`
- adjudicator: drop - Record claims RENAMED with same name; no rename evidence in chunk.

### 17. DROP -> EuroDry Ltd. 2019-04-30 (sec_20f)

- chunk `2fc8a302588abf1834eb35cbb69d0fb1` doc `0818fc861f0f4ba9` ord-packed gold item; source corpus/10-companies/EDRY/20-F/EDRY_20-F_2019-04-30_0000919574-19-003068.md
- flagged by `glm-5.3`: `events` type `other`, entities ['company:new:eurobulk', 'company:new:eurochart', 'person:new:aristides_j_pittas']
- quote: "Aristides J. Pittas is currently the Chairman of each of Eurochart and Eurobulk, all of which are our affiliates."
- record: `{"type": "other", "summary": "Aristides J. Pittas is currently the Chairman of each of Eurochart and Eurobulk, all of which are affiliates of EuroDry", "roles": [{"role": "entity", "entity": "person:new:aristides_j_pittas"}, {"role": "entity", "entity": "company:new:eurochart"}, {"role": "entity", "entity": "company:new:eurobulk"}], "when_printed": "currently", "magnitude_printed": "", "chunk": "c1", "sids": [7], "confidence": 0.8}`
- adjudicator: drop - Adds "EuroDry" affiliation not in source; only says "our affiliates"

### 18. KEEP -> Intermodal Shipbrokers 2021-09-21 (broker_weekly)

- chunk `019dbcec5f3e9b3b9bc73c76790262fc` doc `dd5a0b7266a4db6c` ord-packed gold item; source data/extracted/md/intermodal/2021/intermodal_2021_W37_Intermodal-Report-Week-37-2021.md
- flagged by `glm-5.3`: `claims` type `view`, entities []
- quote: "The overall picture remains depressed in the crude carrier market, as all sectors reported T/C earnings well below their OPEX levels while any increase in demand cannot provide meaningful support at the time of writing."
- record: `{"kind": "view", "subjects": [], "direction": "down", "horizon_printed": "", "chunk": "c1", "sids": [3], "confidence": 0.8}`
- adjudicator: keep - Evidence quote matches sentence 3 exactly.

### 19. KEEP -> Breakwave Advisors 2023-07-04 (broker_daily)

- chunk `57523f8b2628d11b353ab70e45074a5a` doc `cb0e4073325e5c29` ord-packed gold item; source data/extracted/md/breakwave/insights/2023/2023-07-04_shipfix-global-market-update.md
- flagged by `glm-5.3`: `events` type `market_move`, entities ['commodity:new:copper', 'commodity:new:zinc']
- quote: "The copper and zinc three-month futures listed on the LME recorded weekly gains of 0.3 and 1.0 per cent, respectively."
- record: `{"type": "market_move", "summary": "LME copper and zinc three-month futures recorded weekly gains of 0.3 and 1.0 per cent respectively", "roles": [{"role": "commodity", "entity": "commodity:new:copper"}, {"role": "commodity", "entity": "commodity:new:zinc"}], "when_printed": "week", "magnitude_printed": "0.3 and 1.0 per cent", "chunk": "c2", "sids": [12], "confidence": 0.85}`
- adjudicator: keep - Quote matches sentence 12 exactly.

### 20. KEEP -> Metals Market Index (MMi) 2025-11-04 (broker_daily)

- chunk `87f155f7f3ea70ea6cb745adcef42f32` doc `653520558ce022b5` ord-packed gold item; source data/extracted/md/hellenic/iron_ore_pdf/2025/2025-11-04_mmi-daily-iron-ore-index-report-november-04-2025_20251104180538_005d7c73d5c5.md
- flagged by `glm-5.3`: `events` type `market_move`, entities ['commodity:coke']
- quote: "In terms of news, the third round of coke price increase has been implemented, squeezing the profits of steel mills; and the consumption of steel has not increased significantly, the market has a strong expectation for the reduction of molten iron in the future, and the sentiment is weak."
- record: `{"type": "market_move", "summary": "The third round of coke price increase has been implemented, squeezing the profits of steel mills", "roles": [{"role": "subject", "entity": "commodity:coke"}], "when_printed": "", "magnitude_printed": "third round of coke price increase", "chunk": "c1", "sids": [8], "confidence": 0.8}`
- adjudicator: keep - Coke price increase mentioned in sentence 8

### 21. KEEP -> Gibson Shipbrokers 2026-10-02 (broker_weekly)

- chunk `2084e924dee61ce51b789a83550d380c` doc `4b79d075d26b4051` ord-packed gold item; source data/extracted/md/gibson/2026/gibson_2026-10-02_running-out-of-room.md
- flagged by `deepseek-v4-pro`: `claims` type `view`, entities ['route:TD6']
- quote: "TD6 had stayed relatively constant despite the activity in the Atlantic, but on Friday we saw this market catch up, with WS900 paid for TD6."
- record: `{"kind": "view", "subjects": ["route:TD6"], "direction": "up", "horizon_printed": "", "chunk": "c4", "sids": [0], "confidence": 0.8}`
- adjudicator: keep - Sentence 0 explicitly states TD6 caught up on Friday with WS900 paid, supporting the upward view.

### 22. DROP -> Intermodal Shipbrokers 2023-11-14 (broker_weekly)

- chunk `3feeba4d2df95633529c31bda1745d66` doc `2067584eb105858a` ord-packed gold item; source data/extracted/md/intermodal/2023/intermodal_2023_W45_Intermodal-Report-Week-45-2023.md
- flagged by `glm-5.3`: `events` type `market_move`, entities []
- quote: "By Friday, rates had decreased by 37.81 points, ending at WS 219.69.

VLCC T/C earnings averaged \$28,324/day, down - \$3,479/day w-o-w, and closed off the week at the -\$26,666/day mark."
- record: `{"type": "market_move", "summary": "VLCC T/C earnings averaged $28,324/day, down $3,479/day w-o-w", "roles": [], "when_printed": "w-o-w", "magnitude_printed": "$28,324/day, -$3,479/day", "chunk": "c3", "sids": [13], "confidence": 0.9}`
- adjudicator: drop - Evidence quote includes USG Aframax rate (sentence 13) not in record_json; record_json cites only sid 13 but quote spans sentences 13 and 14

### 23. DROP -> Golden Ocean Group Ltd 2025-03-20 (sec_20f)

- chunk `ca1674b395f4db5d23b9e123c1183b16` doc `3645fd56f7d93973` ord-packed gold item; source corpus/10-companies/GOGL/20-F/GOGL_20-F_2025-03-20_0001029145-25-000012.md
- flagged by `deepseek-v4-pro`: `claims` type `forecast`, entities ['country:BM']
- quote: "We do not expect Undertaxed Profit rules to be implemented before 2025 for either Singapore or Norway."
- record: `{"kind": "forecast", "subjects": ["country:BM"], "direction": "na", "horizon_printed": "2025", "chunk": "c2", "sids": [8], "confidence": 0.7}`
- adjudicator: drop - Bermuda not mentioned in evidence quote

### 24. KEEP -> GMS Inc. 2025-02-28 (broker_weekly)

- chunk `26c1232d1c656b5c51ce5f9a6bff1439` doc `d20bbf57ac036473` ord-packed gold item; source data/extracted/md/hellenic/demolition/gms/2025/gms_2025-02-28_week-09_dwindling-surge.md
- flagged by `deepseek-v4-pro`: `claims` type `forecast`, entities []
- quote: "Recent alarming news concerning a potential ban on Chinese built / owned tonnage calling U.S. ports also stands to devastate the U.S. economy in turn, eventually sending prices skyrocketing even further as U.S. inflation starts to rise once again and the Feds cancel their recently intended interest rate cut."
- record: `{"kind": "forecast", "subjects": [], "direction": "up", "horizon_printed": "", "chunk": "c1", "sids": [8], "confidence": 0.6}`
- adjudicator: keep - Quote matches chunk sentence 8 exactly

### 25. DROP -> Banchero Costa 2023-05-14 (broker_weekly)

- chunk `d8043179e70fbf5ef519a6805c24d340` doc `b7457aa3cd979b97` ord-packed gold item; source data/extracted/md/banchero_costa/2023/banchero_costa_2023_W19_Bancosta-Weekly-2023-19.md
- flagged by `glm-5.3`: `events` type `sanction_policy`, entities []
- quote: "Turkish Foreign Minister Mevlut Cavusoglu said on Wednesday he thought the Ukraine Black Sea grain deal could be extended for at least two more months, as officials from the parties involved held the first day of talks on an extension in Istanbul.  Russia has said it would not extend the pact beyond May 18 unless a list of demands is met to remove obstacles to its own grain and fertilizer exports"
- record: `{"type": "sanction_policy", "summary": "Turkey said the Ukraine Black Sea grain deal could be extended for at least two more months; Russia said it would not extend the pact beyond May 18 unless demands are met", "roles": [], "when_printed": "beyond May 18", "magnitude_printed": "at least two more months", "chunk": "c1", "sids": [0, 1], "confidence": 0.8}`
- adjudicator: drop - Record mentions "Turkey" which does not appear verbatim in the source sentences

### 26. DROP -> Banchero Costa 2024-07-29 (broker_weekly)

- chunk `1cde27e864567fae55c353c131279d28` doc `695b804723a77efa` ord-packed gold item; source data/extracted/md/banchero_costa/2024/banchero_costa_2024_W30_Bancosta-Weekly-2024-30.md
- flagged by `glm-5.3`: `events` type `market_move`, entities []
- quote: "On the other side of the Atlantic rates fell to WS155 level on the 70,000 mt trade from USG to Europe. **Suezmax** rates softened further, down to WS87.5 ex W Africa and to WS77.5 ex USG to Europe."
- record: `{"type": "market_move", "summary": "Aframax rates fell to WS155 level on the 70,000 mt trade from USG to Europe", "roles": [], "when_printed": "", "magnitude_printed": "WS155", "chunk": "c3", "sids": [1], "confidence": 0.85}`
- adjudicator: drop - Record misattributes Suezmax rate to Aframax

### 27. KEEP -> Intermodal Shipbrokers 2023-11-14 (broker_weekly)

- chunk `3d94992a317eb2c699f3649ed9516564` doc `2067584eb105858a` ord-packed gold item; source data/extracted/md/intermodal/2023/intermodal_2023_W45_Intermodal-Report-Week-45-2023.md
- flagged by `deepseek-v4-pro`: `state_facts` type `ORDERED_AT`, entities ['company:new:namura_yard', 'company:new:taiwanese_owner']
- quote: "Furthermore, a Taiwanese owner has placed an order for two 40,000dwt vessels to be built at Namura yard."
- record: `{"type": "ORDERED_AT", "src": "company:new:taiwanese_owner", "dst": "company:new:namura_yard", "attrs_printed": [{"key": "units", "value_as_printed": "two 40,000dwt vessels"}], "valid_from_printed": "", "valid_to_printed": "", "chunk": "c2", "sids": [6], "confidence": 0.8}`
- adjudicator: keep - Sentence 6 explicitly states Taiwanese owner ordered two 40,000dwt vessels at Namura yard

### 28. DROP -> Dorian LPG Ltd. 2022-06-02 (sec_10k)

- chunk `3b4fe09279b3382daa7f5d2bb1e0060f` doc `a8f32dca3fdc7313` ord-packed gold item; source corpus/10-companies/LPG/10-K/LPG_10-K_2022-06-02_0001596993-22-000028.md
- flagged by `glm-5.3`: `events` type `other`, entities ['company:new:dorian_shanghai_lpg_transport_llc', 'vessel:imo:9702003']
- quote: "We expect to pay \$99.7 million on or about June 2, 2022 and the remaining \$0.6 million will be deferred until certain shares of restricted stock vest.

***Cougar Japanese Financing***

On May 19, 2022, we refinanced a 2015-built VLGC, the *Cougar* , pursuant to a memorandum of agreement and a bareboat charter agreement.  In connection therewith, we transferred the *Cougar* to the buyer for \$70."
- record: `{"type": "other", "summary": "Dorian LPG transferred the 2015-built VLGC Cougar to the buyer for $70.0 million and bareboat chartered the vessel back via wholly-owned subsidiary Dorian Shanghai LPG Transport LLC for 10 years with purchase options from end of year 3 onwards through a mandatory buyout by 2032", "roles": [{"role": "entity", "entity": "vessel:imo:9702003"}, {"role": "owner", "entity": "company:new:dorian_shanghai_lpg_transport_llc"}], "when_printed": "May 19, 2022", "magnitude_printed": "$70.0 million", "chunk": "c2", "sids": [2, 3], "confidence": 0.85}`
- adjudicator: drop - Vessel IMO 9702003 not mentioned in chunk

### 29. DROP -> International Seaways, Inc. 2023-10-02 (sec_8k)

- chunk `8a380d7c71c8398cc432eff21acfa7f0` doc `c523052d01242f34` ord-packed gold item; source corpus/10-companies/INSW/8-K/INSW_8-K_2023-10-02_0001104659-23-105914.md
- flagged by `glm-5.3`: `state_facts` type `SUBSIDIARY_OF`, entities ['company:cik0001679049', 'company:new:international_seaways_operating_corporation']
- quote: "On September 27, 2023, International Seaways, Inc. (the “ ***Company*** ”), International Seaways Operating Corporation (the “ ***Borrower*** ”) and certain of their subsidiaries entered into a \$160 million revolving credit agreement (the “ ***Revolving Credit Agreement*** ”) with Nordea Bank Abp, New York Branch (“ ***Nordea*** ”), ING Bank N.V., London Branch (“ ***ING*** ”), Crédit Agricole Co"
- record: `{"type": "SUBSIDIARY_OF", "src": "company:new:international_seaways_operating_corporation", "dst": "company:cik0001679049", "attrs_printed": [], "valid_from_printed": "September 27, 2023", "valid_to_printed": "", "chunk": "c1", "sids": [1], "confidence": 0.7}`
- adjudicator: drop - No explicit subsidiary relationship stated

### 30. DROP -> Baltic Exchange 2016-12-30 (broker_weekly)

- chunk `43d54ed0a1353e1931a0b9dc0afe171d` doc `1417cb2f50e134dc` ord-packed gold item; source data/extracted/md/baltic/tanker/2016/2016_tanker-report-week52016_tanker.md
- flagged by `deepseek-v4-pro`: `state_facts` type `FIXED`, entities ['company:new:ara', 'port:new:us_gulf']
- quote: "However with the onset of delays in Houston slowing the availability of potential ballasters, brokers feel the market may now have bottomed out at WS 122.5 for 55,000 tonnes from ARA back to US Gulf."
- record: `{"type": "FIXED", "src": "company:new:ara", "dst": "port:new:us_gulf", "attrs_printed": [{"key": "qty", "value_as_printed": "55,000 tonnes"}, {"key": "rate", "value_as_printed": "WS 122.5"}], "valid_from_printed": "", "valid_to_printed": "", "chunk": "c3", "sids": [1], "confidence": 0.6}`
- adjudicator: drop - ARA is a region not company
