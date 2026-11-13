# C1 review — extraction bake-off, label flags, merge sample, gold packet

Hard stop per `docs/GRAPHRAG_AGENT_TASK.md` §5. Owner rules on the items below in chat; nothing here
is approved until then. Branch `kb-build`, P4b commit on top of the gold-set commit, tripwire clean,
82 tests pass. Spend so far $4.7543 of the $82 pipeline cap; agent spine
(enclave) $66.04/$66.00 — over cap, unchanged, no paid agent calls since P2.

## 1. Bake-off table (plan §10.2, gates P4b)

| gate | measured | required | verdict |
|---|---|---|---|
| `extraction_gold_chunks` | 120 | 120 | PASS |
| `reference_models_distinct_families` | 2 | 2 | PASS |
| `chosen_bulk_gate_pass_rate` | 1.0 | 0.95 | PASS |
| `chosen_bulk_precision` | 0.9222 | 0.92 | PASS |
| `chosen_bulk_f1_within_best` | 0.0 | 0.03 | PASS |

Gold set: 120 stratified chunks / 29 packs / 9 doc types / 12 years / 19 publishers, mean pack depth
4.14. References: `deepseek-v4-pro` + `glm-5.3` (different
families), coverage 120/120 each. Their 304 disagreements
adjudicated by `nvidia/nemotron-3-ultra-550b-a55b` (third family, free NIM): keep
273 / drop 31.
Reference union = 342 records; two references fully agree on only
38, and the record counts are glm 381 vs pro 176, so the
reference is glm-shaped.

| model | role | coverage | P | P 95% CI | R | F1 | gate pass | call success | bake-off cost | projected full scope |
|---|---|---|---|---|---|---|---|---|---|---|
| `deepseek-v4-pro` | reference | 120/120 | 1.0000 | 0.9704-1.0000 | 0.3684 | 0.5385 | 0.8920 | 1.0000 | $0.7533 | $543.68 |
| `glm-5.3` | reference | 120/120 | 1.0000 | 0.9867-1.0000 | 0.8333 | 0.9091 | 0.9003 | 1.0000 | $2.3607 | $1703.81 |
| `deepseek-v4-flash` | candidate | 120/120 | 0.9174 | 0.8746-0.9465 | 0.4763 | 0.6270 | 0.8921 | 1.0000 | $0.0932 | $67.26 |
| `deepseek-v4.1-flash` | candidate | 119/120 | 0.7801 | 0.7162-0.8330 | 0.3548 | 0.4877 | 0.8034 | 0.8966 | $0.2208 | $160.67 |
| `glm-5.3-flash` | candidate | 120/120 | 0.8721 | 0.8214-0.9100 | 0.4401 | 0.5850 | 0.6787 | 1.0000 | $0.1447 | $104.43 |
| `gpt-oss-120b` | candidate | 109/120 | 0.9427 | 0.8947-0.9696 | 0.3356 | 0.4950 | 0.9075 | 0.6800 | $0.1494 | $118.75 |
| `nvidia/nemotron-3-ultra-550b-a55b` | candidate | 120/120 | 0.8556 | 0.7981-0.8988 | 0.3678 | 0.5145 | 0.5882 | 0.8621 | $0.0000 | $0.00 |
| `deepseek-v4.1-flash-1017-ultrafast` | candidate | 119/120 | 0.9222 | 0.8829-0.9491 | 0.5362 | 0.6781 | 0.9077 | 1.0000 | $0.0000 | $0.00 |

Caveats (also in `p4b.md`): absolute F1 is relative to the glm-shaped reference union, not truth;
precision point estimates sit inside their own 95% sampling interval; the 120-chunk sample cannot
certify precision above its CI, which matters for the 0.92 gate; three candidates have coverage holes
(gpt-oss-120b 109/120, ultrafast 119/120, v4.1-flash 119/120) filled by a same-model hole-fill pass.

## 2. Models I chose, and what I need approved

| role | model | family | why | cost basis |
|---|---|---|---|---|
| bulk extraction | `DeepSeek-V4.1-Flash` on the 8-account AMD Token Lab pool (owner amendment 2026-11-13 to the ultrafast pick below) | deepseek | same 1017 weights as the F1 leader `deepseek-v4.1-flash-1017-ultrafast` (P4b F1 0.6781, precision 0.9222, call success 1.00); Ultrafast excluded as congested | **paid**: $0.00134/accepted pack ($0.28/M in, $0.0056/M cached, $0.56/M out); ≈$31.5 booked at $31.25 |
| escalation (gate-failing chunks) | approved: `glm-5.3`, one free same-model retry first, ordered by doc value | glm | owner decision 3; kept inside the escalation line by cap-prioritised partial coverage (D12); plan §10.2's "ref with higher agreement" is the same model at $0.0197/chunk = $511 worst case for 30% escalation, which busts the cap | $11 booked |
| judge / auditor (P4c audit + failure queue) | approved: `glm-5.3` | glm (≠ deepseek extractor) | satisfies `judge_family_differs_from_extractor`; judged 285 gold records at P4b; per-record calls ≈ $0.002 | ≈ $5 for ~1.9k judged records |
| label adjudicator (already used at P4b) | `nvidia/nemotron-3-ultra-550b-a55b` | nvidia | third family, not a reference, free | $0.05 spent |

Owner rulings on the two open choices: (i) escalation = `glm-5.3` (not nemotron), one free retry
first, cap-prioritised inside the escalation line; (ii) judge = `glm-5.3` (paid, strong). The judge
stays a different family from the extractor. Owner ruling 4 (the ~$40 glm-5.3 second extractor) is
**booked at $0**: the AMD bulk pass over every pack now IS the second extractor, and the honest AMD
tariff consumes the budget that ruling 4 was premised on being spare.

## 3. Projected full-build cost

Bulk pass shape on the frozen prose-only scope (86,607 chunks, 16,945 docs): 20,920 packed calls,
26,961,696 output tokens, 5.62 wall days on the free daily cap (4,800,000
output tok/day) **if the route were a free daily cap — the chosen AMD route has no daily cap; it has
a shared concurrency ceiling of 144 and a real per-token tariff**. Three run shapes, not self-approved:

| shape | bulk cost | wall time | total booked incl. spent $4.75 | fits $82 cap? |
|---|---|---|---|---|
| (a) `DeepSeek-V4.1-Flash` on the 8-account AMD Token Lab pool, ultrafast excluded | **$31.25 booked** ($0.00134/pack measured) | ~5.62 days at free-tier pacing; ~2 days at measured AMD concurrency | $39.75 | yes, after rebooking ruling 4 to $0 |
| (b) paid `deepseek-v4-flash` alone | $67.26 | hours | $107.01 | no |
| (c) mixed one-day pool: primary + flash overflow (82.2% of chunks paid) | $55.29 | 1.0 day | $60.04 + remaining phase budgets = $95.04 | no (bulk alone fits, the rest of the build does not) |

So (a) is the only shape that fits the frozen $82 cap. The honest correction the owner should note:
this table was drafted while the bulk route was believed to be free; AMD Token Lab reports a real
`usage.cost`, so the $31.25 line is now a **measured** charge, not zero. It is funded by rebooking the
owner's ruling-4 second extractor to $0 (the AMD pass IS that second extractor) and trimming
`escalation_plus_gleaning` from $17 to $11 — an amendment to D10's provider choice that lowers no
gate. (c) would need either a cap raise of ~$15 or dropping later-phase budgets. (b) additionally
lands at F1
0.6270 (chosen minus 0.051)
and precision 0.9174, under the 0.92 gate, so it is
worse on quality too. Remaining pipeline budget right now: $77.25.

## 4. Thirty flagged gold-label items to rule on

Each item is a reference record the two reference families disagreed on, sampled across both
adjudicator verdicts. Rule each as `ok` / `over-claim` / `wrong entity` / `wrong number` /
`missing (should have been extracted)`; the non-sampled 274
keep their adjudicator verdict unless you say otherwise. Full 600-char quotes and record JSON:
`kb/reports/p4b_flagged.md`.

Source: `kb/reports/p4b_flagged.md` (machine copy `kb/reports/p4b_flagged.json`). 30 of 304 flagged reference records, seed 15063620, pool keep 273 / drop 31.

1. **KEEP** — `state_facts/LISTED_AS` [company:new:trafigura_group, publisher:new:singapore_stock_exchange] — Intermodal Shipbrokers, 2021-09-21 (broker_weekly) — path `data/extracted/md/intermodal/2021/intermodal_2021_W37_Intermodal-Report-Week-37-2021.md`
   - quote:   The notes will be listed on the Singapore Stock Exchange, with Trafigura aiming to redeem the debt within six years.
   - adjudicator why: Sentence 4 explicitly states notes listed on Singapore Stock Exchange
2. **KEEP** — `claims/forecast` [-] — Intermodal Shipbrokers, 2023-11-14 (broker_weekly) — path `data/extracted/md/intermodal/2023/intermodal_2023_W45_Intermodal-Report-Week-45-2023.md`
   - quote:  Given the typical surge in U.S. soybean exports from September to November, such activity from China may lead to an increase in demand for Kamsarmax and Ultramax/Supramax vessels, which is likely to support their rates 
   - adjudicator why: Forecast claim matches quoted sentence about soybean export surge supporting vessel rates.
3. **KEEP** — `state_facts/RENAMED` [vessel:new:ocean_pearl] — Seabrokers Chartering, 2026-08-01 (broker_monthly) — path `data/extracted/md/seabrokers/2026/2026-08-01_market-report-august-2026.md`
   - quote:  The Swissco Pearl AHTS vessel has been renamed as the Ocean Pearl following her recent acquisition by the J M Baxi Group in India.
   - adjudicator why: Renaming explicitly stated in sentence 0.
4. **KEEP** — `claims/view` [-] — GMS Inc., 2025-02-28 (broker_weekly) — path `data/extracted/md/hellenic/demolition/gms/2025/gms_2025-02-28_week-09_dwindling-surge.md`
   - quote:  Fundamentals continue afflict their pricing strategy as well as subdued import and local steel plate prices that continue face weekly jitters, all while the Lira remains in freefall as it collapsed another 20 basis poin
   - adjudicator why: Quote matches chunk sentence 2 exactly with all numbers and text present
5. **KEEP** — `events/other` [company:cik0000913290] — Frontline plc, 2026-02-27 (sec_6k) — path `corpus/10-companies/FRO/6-K/FRO_6-K_2026-02-27_0000919574-26-001430.md`
   - quote:  As of today, six of the vessels have been delivered to the new owner with the remaining two vessels scheduled to be delivered during March 2026. After commissions and repayment of existing debt on the vessels, the trans
   - adjudicator why: All numbers, dates, and details match the quoted sentence exactly.
6. **KEEP** — `events/production_guidance` [country:US] — Gibson Shipbrokers, 2026-10-02 (broker_weekly) — path `data/extracted/md/gibson/2026/gibson_2026-10-02_running-out-of-room.md`
   - quote:  According to Kpler data, exports peaked at around 5.2 mbd in Q2, when releases from the US SPR lifted volumes by close to 1.3 mbd, or more than 30%, on the previous quarter.
   - adjudicator why: Record accurately reflects Kpler data on US crude export peak and SPR impact in Q2.
7. **DROP** — `events/market_move` [-] — Gibson Shipbrokers, 2026-10-02 (broker_weekly) — path `data/extracted/md/gibson/2026/gibson_2026-10-02_running-out-of-room.md`
   - quote:  The market opened with cross-UKC rates around WS430, owners benefiting from the substantial tightening seen over previous weeks.  Consequently, rates only softened modestly, ending the week around WS410-420 for UKC busi
   - adjudicator why: Name "North Sea" not in quoted sentences; evidence lacks that term
8. **DROP** — `events/market_move` [-] — Intermodal Shipbrokers, 2023-11-14 (broker_weekly) — path `data/extracted/md/intermodal/2023/intermodal_2023_W45_Intermodal-Report-Week-45-2023.md`
   - quote:  In terms of fundamentals, the local currency continues its rapid depreciation against the USD, currently trading at 283. In Turkey, steel prices are rising modestly, while offer prices remain broadly unchanged.
   - adjudicator why: Currency not explicitly named as Pakistani rupee in quote.
9. **DROP** — `state_facts/FIXED` [company:new:vitol, vessel:imo:9890989] — Baltic Exchange, 2016-12-30 (broker_weekly) — path `data/extracted/md/baltic/tanker/2016/2016_tanker-report-week52016_tanker.md`
   - quote:   In West Africa, the market has held steady at WS 65 for China discharge, while in the North Sea, the *Nave Electron* is said to have gone to Vitol from Hound Point to South Korea at $6.725 million.
   - adjudicator why: Vessel IMO 9890989 not mentioned in chunk
10. **DROP** — `events/market_move` [country:AE, port:SAJUB, port:SARTA] — Affinity Shipbrokers, 2024-10-04 (broker_weekly) — path `data/extracted/md/affinity/2024/affinity_2024_Affinity-Tanker-Weekly-04.10.2024-HSN.md`
   - quote:  LR2s and MRs offering better flexibility and efficiency on USD/T and rate perspectives have naturally softened distinctly, finally leading to some public testing with USD 375,000 on subs for UAE/Kuwait - a notable chang
   - adjudicator why: Record misidentifies LR2/MR testing as LR1; entities include UAE/Kuwait not in record
11. **KEEP** — `events/port_congestion` [port:new:black_sea] — The Signal Group, 2023-05-22 (broker_weekly) — path `data/extracted/md/signal/newsroom/2023/the-signal-ocean-platform-port-congestion.md`
   - quote:  As depicted in Image 2, a few days prior to late April, the number of congested vessels in the Black Sea reached its highest point since the beginning of this year, surpassing the levels observed in 2022. The ongoing gr
   - adjudicator why: All record fields match chunk sentence 7 exactly.
12. **KEEP** — `events/newbuilding_wave` [company:cik0000913290] — Frontline plc, 2026-02-27 (sec_6k) — path `corpus/10-companies/FRO/6-K/FRO_6-K_2026-02-27_0000919574-26-001430.md`
   - quote:   The overall tanker order book for the asset classes Frontline owns is now 22.2% of the existing global fleet, with 163,123, and 165 vessels on order for VLCCs, Suezmax tankers and LR2 tankers, respectively.
   - adjudicator why: Order book data matches chunk sentence 9 exactly
13. **DROP** — `claims/view` [route:TC14] — Affinity Shipbrokers, 2024-10-04 (broker_weekly) — path `data/extracted/md/affinity/2024/affinity_2024_Affinity-Tanker-Weekly-04.10.2024-HSN.md`
   - quote:  A lack of volume coupled with a sufficient tonnage list has left rates grounded around WS 90 for TC2.
   - adjudicator why: Evidence quote references TC2, not TC14.
14. **DROP** — `claims/causal` [-] — The Signal Group, 2023-05-22 (broker_weekly) — path `data/extracted/md/signal/newsroom/2023/the-signal-ocean-platform-port-congestion.md`
   - quote:  **What vessel types does the Signal Ocean Port Congestion API cover?** The API covers dry bulk and tanker vessels, including Capesize, VLOC, Panamax, Supramax, Handysize, Suezmax, and MR vessel classes.  **How far back 
   - adjudicator why: Evidence lacks explicit causal statement
15. **KEEP** — `claims/view` [-] — Affinity Shipbrokers, 2024-10-04 (broker_weekly) — path `data/extracted/md/affinity/2024/affinity_2024_Affinity-Tanker-Weekly-04.10.2024-HSN.md`
   - quote:  Tonnage lists are getting dangerously thin with owners very much in the driving seat to push rates further north, especially when considering that regional tensions remain on a knife’s edge.
   - adjudicator why: Quote matches sentence 9 exactly
16. **DROP** — `state_facts/RENAMED` [vessel:imo:5122750] — Alfred A. Knopf, 2013-01-01 (book) — path `corpus/books/sea_and_civilization_paine.md`
   - quote:  The inaugural run of Fulton's forty-five-meter-long side-wheel steamer, the North River Steam Boat, took place on the Hudson River between New York and Albany in 1807; after that there was no looking back.
   - adjudicator why: Record claims RENAMED with same name; no rename evidence in chunk.
17. **DROP** — `events/other` [company:new:eurobulk, company:new:eurochart, person:new:aristides_j_pittas] — EuroDry Ltd., 2019-04-30 (sec_20f) — path `corpus/10-companies/EDRY/20-F/EDRY_20-F_2019-04-30_0000919574-19-003068.md`
   - quote:   Aristides J. Pittas is currently the Chairman of each of Eurochart and Eurobulk, all of which are our affiliates.
   - adjudicator why: Adds "EuroDry" affiliation not in source; only says "our affiliates"
18. **KEEP** — `claims/view` [-] — Intermodal Shipbrokers, 2021-09-21 (broker_weekly) — path `data/extracted/md/intermodal/2021/intermodal_2021_W37_Intermodal-Report-Week-37-2021.md`
   - quote:  The overall picture remains depressed in the crude carrier market, as all sectors reported T/C earnings well below their OPEX levels while any increase in demand cannot provide meaningful support at the time of writing.
   - adjudicator why: Evidence quote matches sentence 3 exactly.
19. **KEEP** — `events/market_move` [commodity:new:copper, commodity:new:zinc] — Breakwave Advisors, 2023-07-04 (broker_daily) — path `data/extracted/md/breakwave/insights/2023/2023-07-04_shipfix-global-market-update.md`
   - quote:  The copper and zinc three-month futures listed on the LME recorded weekly gains of 0.3 and 1.0 per cent, respectively.
   - adjudicator why: Quote matches sentence 12 exactly.
20. **KEEP** — `events/market_move` [commodity:coke] — Metals Market Index (MMi), 2025-11-04 (broker_daily) — path `data/extracted/md/hellenic/iron_ore_pdf/2025/2025-11-04_mmi-daily-iron-ore-index-report-november-04-2025_20251104180538_005d7c73d5c5.md`
   - quote:  In terms of news, the third round of coke price increase has been implemented, squeezing the profits of steel mills; and the consumption of steel has not increased significantly, the market has a strong expectation for 
   - adjudicator why: Coke price increase mentioned in sentence 8
21. **KEEP** — `claims/view` [route:TD6] — Gibson Shipbrokers, 2026-10-02 (broker_weekly) — path `data/extracted/md/gibson/2026/gibson_2026-10-02_running-out-of-room.md`
   - quote:  TD6 had stayed relatively constant despite the activity in the Atlantic, but on Friday we saw this market catch up, with WS900 paid for TD6.
   - adjudicator why: Sentence 0 explicitly states TD6 caught up on Friday with WS900 paid, supporting the upward view.
22. **DROP** — `events/market_move` [-] — Intermodal Shipbrokers, 2023-11-14 (broker_weekly) — path `data/extracted/md/intermodal/2023/intermodal_2023_W45_Intermodal-Report-Week-45-2023.md`
   - quote:  By Friday, rates had decreased by 37.81 points, ending at WS 219.69.  VLCC T/C earnings averaged \$28,324/day, down - \$3,479/day w-o-w, and closed off the week at the -\$26,666/day mark.
   - adjudicator why: Evidence quote includes USG Aframax rate (sentence 13) not in record_json; record_json cites only sid 13 but quote spans sentences 13 and 14
23. **DROP** — `claims/forecast` [country:BM] — Golden Ocean Group Ltd, 2025-03-20 (sec_20f) — path `corpus/10-companies/GOGL/20-F/GOGL_20-F_2025-03-20_0001029145-25-000012.md`
   - quote:  We do not expect Undertaxed Profit rules to be implemented before 2025 for either Singapore or Norway.
   - adjudicator why: Bermuda not mentioned in evidence quote
24. **KEEP** — `claims/forecast` [-] — GMS Inc., 2025-02-28 (broker_weekly) — path `data/extracted/md/hellenic/demolition/gms/2025/gms_2025-02-28_week-09_dwindling-surge.md`
   - quote:  Recent alarming news concerning a potential ban on Chinese built / owned tonnage calling U.S. ports also stands to devastate the U.S. economy in turn, eventually sending prices skyrocketing even further as U.S. inflatio
   - adjudicator why: Quote matches chunk sentence 8 exactly
25. **DROP** — `events/sanction_policy` [-] — Banchero Costa, 2023-05-14 (broker_weekly) — path `data/extracted/md/banchero_costa/2023/banchero_costa_2023_W19_Bancosta-Weekly-2023-19.md`
   - quote:  Turkish Foreign Minister Mevlut Cavusoglu said on Wednesday he thought the Ukraine Black Sea grain deal could be extended for at least two more months, as officials from the parties involved held the first day of talks 
   - adjudicator why: Record mentions "Turkey" which does not appear verbatim in the source sentences
26. **DROP** — `events/market_move` [-] — Banchero Costa, 2024-07-29 (broker_weekly) — path `data/extracted/md/banchero_costa/2024/banchero_costa_2024_W30_Bancosta-Weekly-2024-30.md`
   - quote:  On the other side of the Atlantic rates fell to WS155 level on the 70,000 mt trade from USG to Europe. **Suezmax** rates softened further, down to WS87.5 ex W Africa and to WS77.5 ex USG to Europe.
   - adjudicator why: Record misattributes Suezmax rate to Aframax
27. **KEEP** — `state_facts/ORDERED_AT` [company:new:namura_yard, company:new:taiwanese_owner] — Intermodal Shipbrokers, 2023-11-14 (broker_weekly) — path `data/extracted/md/intermodal/2023/intermodal_2023_W45_Intermodal-Report-Week-45-2023.md`
   - quote:  Furthermore, a Taiwanese owner has placed an order for two 40,000dwt vessels to be built at Namura yard.
   - adjudicator why: Sentence 6 explicitly states Taiwanese owner ordered two 40,000dwt vessels at Namura yard
28. **DROP** — `events/other` [company:new:dorian_shanghai_lpg_transport_llc, vessel:imo:9702003] — Dorian LPG Ltd., 2022-06-02 (sec_10k) — path `corpus/10-companies/LPG/10-K/LPG_10-K_2022-06-02_0001596993-22-000028.md`
   - quote:  We expect to pay \$99.7 million on or about June 2, 2022 and the remaining \$0.6 million will be deferred until certain shares of restricted stock vest.  ***Cougar Japanese Financing***  On May 19, 2022, we refinanced a
   - adjudicator why: Vessel IMO 9702003 not mentioned in chunk
29. **DROP** — `state_facts/SUBSIDIARY_OF` [company:cik0001679049, company:new:international_seaways_operating_corporation] — International Seaways, Inc., 2023-10-02 (sec_8k) — path `corpus/10-companies/INSW/8-K/INSW_8-K_2023-10-02_0001104659-23-105914.md`
   - quote:   On September 27, 2023, International Seaways, Inc. (the “ ***Company*** ”), International Seaways Operating Corporation (the “ ***Borrower*** ”) and certain of their subsidiaries entered into a \$160 million revolving 
   - adjudicator why: No explicit subsidiary relationship stated
30. **DROP** — `state_facts/FIXED` [company:new:ara, port:new:us_gulf] — Baltic Exchange, 2016-12-30 (broker_weekly) — path `data/extracted/md/baltic/tanker/2016/2016_tanker-report-week52016_tanker.md`
   - quote:  However with the onset of delays in Houston slowing the availability of potential ballasters, brokers feel the market may now have bottomed out at WS 122.5 for 55,000 tonnes from ARA back to US Gulf. 
   - adjudicator why: ARA is a region not company

## 5. Twenty-five sampled gold questions

Full set: 250 questions, seed 2888775339, 250 verified,
{"a_single_number": 50, "b_window_aggregate": 25, "c_multihop_entity": 35, "d_event_market": 25, "e_sec_section": 35, "f_summary_trend": 25, "g_as_known_on_date": 15, "h_unanswerable": 40}. The rest stays unapproved until C2.

### C1 sample packet (25 questions)

For the C1 checkpoint review: these are the questions proposed for the held-out set. Approve or flag; the rest of the set stays unapproved until C2.

G-001	a_single_number	What was the % of freight costs in CFR price for Handysize/Supramax / Ukrainian corn, CFR Egypt, Handy lot on 2026-04-06? Give the exact number and its unit.	=> 12.30 %
G-051	b_window_aggregate	What was the average 2023 year for Handysize/Supramax / Wheat / corn, 5-6,000t, Izmail / Odesa - Bari / Ortona (1500x/1500x), $/t over the 4 periods from 2023-02-20 to 2023-03-13? Give the exact number and its unit.	=> 53.50 $/t
G-116	c_multihop_entity	The vessel ROSCO POPLAR was reported sold on 2024-08-26 at 17.60 usd_m. Which publications reported it, and in how many documents? List the publication names.	=> ROSCO POPLAR: 17.60 usd_m on 2024-08-26; publishers Banchero Costa across 2 documents
G-151	d_event_market	After the 2026-03-07 report of the vessel sale (reported by Seasure Shipbroking (Blue Report, valuations by VesselsValue)), how did the Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD move over the following month? Give the value on 2026-03-03 and on 2026-03-31 and the percentage change.	=> Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD: 13.30 -> 6.90 % (-48.12%)
G-176	e_sec_section	In Ardmore Shipping Corp's SEC 20F filed 2016-04-06, which section (Item 9) discusses Dilution? Give the section heading.	=> 'The Offer and Listing'
G-076	f_summary_trend	How did the Value for Aframax / Crude Tankers / Tonne-miles index (base: week 1, 2024 =100) / seasonal change between 2025-03-16 and 2025-06-01? State the start value, the end value and the percentage change.	=> 95.07 -> 91.33 index (-3.93%)
G-101	g_as_known_on_date	As known on 2022-06-13, what was the latest 2022 year for Coaster / Fertilizers, 4,000t, Klaipeda - ARA (2000c/2000x), €/t and for which period? Give the exact number and its unit.	=> 28 EUR/t (period ending 2022-06-13)
G-211	h_unanswerable	What was the TD27X spot TCE on 2025-05-14? Give the exact number.	=> The corpus has a gap here: no series or document in the corpus mentions route code TD27X
G-002	a_single_number	What was the 2021 year for Handysize/Supramax / Scrap (sf 55-58`), 25-30,000t, Damietta - Santos (8000x/7000c), $/t on 2021-08-30? Give the exact number and its unit.	=> 35 $/t
G-052	b_window_aggregate	What was the average 2023 year for Handysize/Supramax / Wheat/corn (sf 47-49`), 25-30,000t, Odesa - EgyptMed (8000x/5000x), $/t over the 4 periods from 2023-03-13 to 2023-04-03? Give the exact number and its unit.	=> 35.05 $/t
G-117	c_multihop_entity	The vessel Western Fedora was reported sold on 2025-02-24 at 14 usd_m. Which publications reported it, and in how many documents? List the publication names.	=> Western Fedora: 14 usd_m on 2025-02-24; publishers Seasure Shipbroking (Blue Report, valuations by VesselsValue) across 2 documents
G-152	d_event_market	After the 2025-12-15 report of the vessel sale (reported by Seasure Shipbroking (Blue Report, valuations by VesselsValue)), how did the Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD move over the following month? Give the value on 2025-12-09 and on 2026-01-13 and the percentage change.	=> Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD: 1 -> 14.90 % (+1390.00%)
G-177	e_sec_section	In SFL Corporation Ltd's SEC 20F filed 2016-04-01, which section (Item 10) discusses Publicly-Traded? Give the section heading.	=> 'ADDITIONAL INFORMATION'
G-077	f_summary_trend	How did the Laden for LR2 / Product Tankers / Days at anchor, global- 4 week moving average / weekly change between 2026-04-26 and 2026-07-12? State the start value, the end value and the percentage change.	=> 0.26 -> 0.31 days (+17.62%)
G-102	g_as_known_on_date	As known on 2026-09-30, what was the latest Change pct for Mac Fines 60.8% / port_stock_cny / Fines / yuan/wmt and for which period? Give the exact number and its unit.	=> 0.30 % (period ending 2026-09-30)
G-212	h_unanswerable	What was the TC5L spot TCE on 2025-05-14? Give the exact number.	=> The corpus has a gap here: no series or document in the corpus mentions route code TC5L
G-003	a_single_number	What was the Tce usd per day for TC2 / Cont / USAC / ↑ Firmer on 2022-11-25? Give the exact number and its unit.	=> 45,890 USD/day
G-053	b_window_aggregate	What was the average Ukrainian corn, CFR Egypt, Handy lot for Handysize/Supramax / Ukrainian corn, CFR Egypt, Handy lot over the 4 periods from 2026-04-20 to 2026-05-11? Give the exact number and its unit.	=> 266.12 $/t
G-118	c_multihop_entity	The vessel Miao Xiang was reported sold on 2025-12-15 at 16 usd_m. Which publications reported it, and in how many documents? List the publication names.	=> Miao Xiang: 16 usd_m on 2025-12-15; publishers Seasure Shipbroking (Blue Report, valuations by VesselsValue) across 2 documents
G-153	d_event_market	After the 2025-07-28 report of the vessel sale (reported by Banchero Costa), how did the Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD move over the following month? Give the value on 2025-07-22 and on 2025-08-26 and the percentage change.	=> Change pct for TSAKOS ENERGY NAVIGATION / NYSE / USD: -8.20 -> 4.70 % (+157.32%)
G-178	e_sec_section	In DHT Holdings, Inc.'s SEC 20F filed 2015-03-19, which section (Item 15) discusses Sponsoring? Give the section heading.	=> 'CONTROLS AND PROCEDURES'
G-078	f_summary_trend	How did the Value for Handysize / Dry Bulk / Ballast tonnage at anchor in Oceania / seasonal change between 2022-04-03 and 2022-06-19? State the start value, the end value and the percentage change.	=> 1.06 -> 1.07 mdwt (+1.13%)
G-103	g_as_known_on_date	As known on 2021-10-15, what was the latest Change pct for VLCC / 310k / 5 years and for which period? Give the exact number and its unit.	=> 0 % (period ending 2021-10-15)
G-213	h_unanswerable	What was the MR14J spot TCE on 2025-05-14? Give the exact number.	=> The corpus has a gap here: no series or document in the corpus mentions route code MR14J
G-004	a_single_number	What was the 2024 year for Coaster / Urea, 5-6,000t, Damietta - Sevilla (2500x/2500x), $/t on 2024-10-14? Give the exact number and its unit.	=> 30.50 $/t

## 6. Thirty sampled entity merges

From `kb/reports/p3_owner_sample.json` (seed 2726325733); rule `same` / `different`; P3 is
committed and its merge precision gate already passed at 0.99, so this is a spot check for systematic
over-merging.

| a | b | method | verdict | model reason |
|---|---|---|---|---|
| `ATLANTIC DRAGON` (vessel:1c15375cc87a) | `Atlantic Dragon` (vessel:9874600) | splink_auto | same | {"decision":"same","reason":"Name identical, DWT and built match, IMO missing on one side is normal"} |
| `PS SYDNEY` (vessel:5358fe9bfff2) | `PS Sydney` (vessel:9829459) | splink_auto | same | {"decision":"same","reason":"Name identical, DWT and built match, IMO missing on one side allowed"} |
| `WOOYANG CLES` (vessel:3a9090c0bd0d) | `Wooyang Cles` (vessel:9638147) | splink_auto | same | {"decision":"same","reason":"Names match case-insensitively; DWT and built year identical; IMO missing in A is not a contradiction."} |
| `Nordic Nanjing` (vessel:fb006ed56109) | `Nordic Nanjing` (vessel:9647291) | splink_auto | same | {"decision":"same","reason":"Name identical, built same, IMO on one side only, DWT diff 1.1% <2%"} |
| `Isa Star` (vessel:0c9589edbd3b) | `ISA Star` (vessel:9210270) | splink_auto | same | {"decision":"same","reason":"Name identical, DWT and built match, IMO on one side only"} |
| `Bellight` (vessel:01a256cdccba) | `Bellight` (vessel:9724776) | splink_auto | same | {"decision":"same","reason":"Same name, built year; DWT diff 0.04%; IMO on one side only"} |
| `MBA ROSARIA` (vessel:0cb31f3bbc18) | `MBA Rosaria` (vessel:9591765) | splink_auto | same | {"decision":"same","reason":"Name matches case-insensitively; DWT and built year identical; IMO missing in A is not a contradiction."} |
| `Hai Heng` (vessel:6069bd9bc910) | `Hai Heng` (vessel:9186716) | splink_auto | same | {"decision":"same","reason":"Identical name, DWT, built year; IMO missing in A is normal per policy."} |
| `Kazan` (vessel:c95e32ca37bc) | `Kazan` (vessel:9258002) | splink_auto | same | {"decision":"same","reason":"Identical name, DWT, built year; IMO missing on one side is normal"} |
| `SINAR BUSAN` (vessel:909aca8ccc05) | `Sinar Busan` (vessel:9346483) | splink_auto | same | {"decision":"same","reason":"Name identical, DWT and built match, IMO missing on one side allowed"} |
| `Harbour Well` (vessel:fcfae093810a) | `Harbour Well` (vessel:9170262) | splink_auto | same | {"decision":"same","reason":"Identical name, DWT, built year; IMO missing on one side is normal"} |
| `C. Challenger` (vessel:24a8f2fbbd14) | `C. Challenger` (vessel:9595620) | splink_auto | same | {"decision":"same","reason":"Identical name, DWT, built year; IMO missing on one side is normal"} |
| `PEACEFUL SEAS` (vessel:f484d71c211b) | `Peaceful Seas` (vessel:9707584) | splink_auto | same | {"decision":"same","reason":"Name identical, DWT and built match, IMO only on one side"} |
| `Frontline` (company:frontline) | `Frontline plc` (company:cik000091329) | company_exact_name | same | {"decision":"same","reason":"Legal suffix 'plc' added; core name 'Frontline' identical"} |
| `Mandarin Noble` (vessel:1145b39443b2) | `Mandarin Noble` (vessel:9533323) | splink_auto | same | {"decision":"same","reason":"Identical name, DWT, built year; IMO missing in A only"} |
| `GOLDEN POPLAR` (vessel:aa400341fc1f) | `Golden Poplar` (vessel:1080916) | splink_auto | same | {"decision":"same","reason":"Names match case-insensitively; DWT and built year identical; IMO missing in A is not a contradiction."} |
| `DL LILY` (vessel:e7c624125aea) | `Dl Lily` (vessel:9519688) | splink_auto | same | {"decision":"same","reason":"Normalized names match; DWT and built year identical; IMO missing on one side is not a contradiction."} |
| `ANGLO ALEXANDRIA` (vessel:721583f99368) | `Anglo Alexandria` (vessel:9451044) | splink_auto | same | {"decision":"same","reason":"Name identical, DWT and built match, IMO missing on one side is normal"} |
| `HL SAMARINDA` (vessel:d1cc2fb82ad0) | `HL Samarinda` (vessel:9537551) | splink_auto | same | {"decision":"same","reason":"Names match case-insensitively; DWT and built year identical; IMO missing in A is not a contradiction."} |
| `Aurora Borealis` (vessel:f7db9e5663d8) | `Aurora Borealis` (vessel:9957608) | judge_same | same | {"decision":"same","reason":"Identical name, DWT, built year; IMO missing in A only"} |
| `Fairchem Kiso` (vessel:babc46e9ed3d) | `Fairchem Kiso` (vessel:9527075) | splink_auto | same | {"decision":"same","reason":"Identical name, DWT, built year; IMO missing on one side is normal"} |
| `Overseas Long Beac` (vessel:aaff677684d6) | `Overseas Long Beach` (vessel:9353527) | judge_same | same | {"decision":"same","reason":"Name one-letter variant, DWT/built match, IMO on one side only"} |
| `STI BRONX` (vessel:d134024803d0) | `STI Bronx` (vessel:9706839) | splink_auto | same | {"decision":"same","reason":"Name matches case-insensitively; DWT and built year identical; IMO missing on one side is not a contradiction."} |
| `XIN DONG GUAN 7` (vessel:a92710e00dd4) | `Xin Dong Guan 7` (vessel:9597056) | splink_auto | same | {"decision":"same","reason":"Name matches, DWT and built identical, IMO missing on one side only"} |
| `Afra Rossi` (vessel:c12b723fe598) | `Afra Rossi` (vessel:9431381) | splink_auto | same | {"decision":"same","reason":"Name identical, built year same, DWT diff 0.001%, IMO missing on A only"} |
| `Dukhan` (vessel:69d34d8a8017) | `Dukhan` (vessel:9265500) | splink_auto | same | {"decision":"same","reason":"Identical name, DWT, built year; IMO missing in A only"} |
| `Carmencita` (vessel:6eef1840d8bc) | `Carmencita` (vessel:9403176) | splink_auto | same | {"decision":"same","reason":"Name, DWT, built match; IMO missing on A is normal"} |
| `High Navigator` (vessel:36cba42e73d3) | `High Navigator` (vessel:9814143) | splink_auto | same | {"decision":"same","reason":"Identical name, DWT, built year; IMO missing in A only"} |
| `CONTRACT II` (vessel:434fe2dcfbb7) | `Contract II` (vessel:9105085) | splink_auto | same | {"decision":"same","reason":"Name identical, DWT and built match, IMO missing on one side only"} |
| `Agia Trias` (vessel:5f675a68f57a) | `Agia Trias` (vessel:9241657) | splink_auto | same | {"decision":"same","reason":"Name, DWT, built match; IMO missing on A is normal"} |

## 7. What happens on your reply

Write `kb/reports/C1_APPROVED.md` with your message verbatim under `owner_message:`, apply any model or
label overrides, then continue P4c (bulk extraction on the frozen scope) → P5 → P6 → P7 → C2. I stop
here until you reply.
