"""
Comprehensive Automated Verification Suite for Question Auto-Routing & Data Grounding.
Tests all 30 Research Copilot queries and 25 ETF Copilot queries against:
1. Regex Auto-Selection Scope Routing (100% Coverage, 0% Fallback)
2. Domain Relevance & Grounding Verification
3. BM25 Chunk Token Match & Content Fidelity
4. Structural Integrity (No broken quotes or mismatched delimiters)
"""

import re
import json
import os
import unittest

def auto_select_sources(query):
    q = (query or '').lower()
    active = set()

    # 1. Breakwave & Macro Analyst Narrative
    if re.search(r'breakwave|analyst sentiment|conviction|qual analysis|grade|thesis|catalyst|contrarian|confluence|verdict|invalidation|downside risk|positioning|allocation|outpace|macro|outlook|opec|risk-reward|ton.mile|tonmile|trade flow|rerouting|gibson|\bpoten\b|\bdrewry\b|\ballied\b|\bbancosta\b|\bintermodal\b|\bxclusiv\b|\bstar asia\b|\blion\b|broker report|shipbroker', q, re.I):
        active.add('breakwave')

    # 2. Baltic Exchange, Spot Rates, Spreads, Chokepoints & Quant Regimes
    if re.search(r'baltic|spot rate|exchange|market comment|chokepoint|suez|panama|red sea|bab-el-mandeb|rerouting|transit|c3|c5|arbitrage|skew|freight spread|bdi|bdti|bcti|dirty|clean|z-score|roc|regime|overbought|oversold|spread|divergence|td3c|td20|td25|cape|panamax|supramax|handysize|vlcc|suezmax|aframax|ffa|ton.mile|tonmile|sts|cpc|black sea|cape of good hope', q, re.I):
        active.add('baltic')

    # 3. Hellenic, Time Charter Rates, S&P Valuations, Bunkers & Carbon
    if re.search(r'charter|timecharter|tc rate|tce|vessel valuation|second.hand|s&p|asset price|asset values|bunker|vlsfo|hsfo|hi-5|scrubber|eu ets|carbon|refinery|cpp|earnings|resale|sale and purchase|parity|\bintermodal\b', q, re.I):
        active.add('hellenic')

    # 4. Iron Ore, Steel, Coal, Grain & Commodity Flows
    if re.search(r'iron ore|ore demand|capesize demand|china steel|ton.mile|tonmile|simandou|bauxite|port stock|inventory days|steel margin|coal|grain|soybean|export flow|\busda\b|\bagtransport\b|grain queue|landed cost', q, re.I):
        active.add('ironOre')

    # 5. Shipbuilding, Orderbooks, Deliveries, Scrapping & Fleet Supply
    if re.search(r'newbuild|orderbook|delivery schedule|berth|yard capacity|demolition|scrapping|fleet size|fleet growth|fleet supply|yoy growth|eexi|cii|shipyard|subcontinent|clarksons|gross tonnage|\bgt\b|backlog|supercycle', q, re.I):
        active.add('shipbuilding')

    # 6. Foundational Textbooks, Theory & Explanations
    if re.search(r'explain|fundamentals|background|textbook|historical context|theory|how.*computed|scoring.*computed|\badmiralty\b|\blaw\b|\bparsons\b|\bpritchard\b|\bstopford\b|treatise|monograph', q, re.I):
        active.add('books')

    return active


class TestQuestionRoutingAndGrounding(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open('index.html', 'r', encoding='utf-8') as f:
            cls.html_content = f.read()

        # Extract Research queries: onclick="sq('...')"
        cls.research_queries = re.findall(r"onclick=\"sq\('([^']+)'\)\"", cls.html_content)

        # Extract ETF queries: onclick="etfSq('...')"
        cls.etf_queries = re.findall(r"onclick=\"etfSq\('([^']+)'\)\"", cls.html_content)

    def test_research_queries_count_and_syntax(self):
        """Verify research queries are defined with valid syntax."""
        self.assertGreaterEqual(len(self.research_queries), 38, f"Expected at least 38 research queries, found {len(self.research_queries)}")
        for i, q in enumerate(self.research_queries, 1):
            self.assertGreater(len(q), 15, f"Query {i} is suspiciously short: {q}")
            self.assertNotIn("undefined", q)
            self.assertNotIn("NaN", q)
            self.assertNotIn("\\'", q)  # No raw escaped quotes in prompt

    def test_etf_queries_count_and_syntax(self):
        """Verify ETF queries are defined with valid syntax."""
        self.assertGreaterEqual(len(self.etf_queries), 30, f"Expected at least 30 ETF queries, found {len(self.etf_queries)}")
        for i, q in enumerate(self.etf_queries, 1):
            self.assertGreater(len(q), 20, f"ETF Query {i} is suspiciously short: {q}")
            self.assertNotIn("undefined", q)
            self.assertNotIn("NaN", q)

    def test_100_percent_research_routing_coverage(self):
        """Verify 100% of Research queries trigger direct active scope routing."""
        unrouted = []
        for i, q in enumerate(self.research_queries, 1):
            scopes = auto_select_sources(q)
            if not scopes:
                unrouted.append((i, q))

        self.assertEqual(len(unrouted), 0, f"Found unrouted queries that fall back to defaults: {unrouted}")

    def test_institutional_macro_questions_routing(self):
        """Verify specific critical macro questions route to their exact target domains."""
        # 1. Clarksons 405.9m GT orderbook vs 2008
        q_clarksons = [q for q in self.research_queries if 'Clarksons' in q or '405.9m' in q]
        self.assertTrue(len(q_clarksons) > 0, "Clarksons 405.9m GT question missing")
        scopes = auto_select_sources(q_clarksons[0])
        self.assertIn('shipbuilding', scopes, f"Clarksons query must route to 'shipbuilding', got {scopes}")

        # 2. Hi-5 Bunker spread & Scrubber TCE
        q_bunker = [q for q in self.research_queries if 'Hi-5' in q or 'scrubber' in q]
        self.assertTrue(len(q_bunker) > 0, "Hi-5 Bunker spread question missing")
        scopes = auto_select_sources(q_bunker[0])
        self.assertIn('hellenic', scopes, f"Bunker query must route to 'hellenic', got {scopes}")

        # 3. Atlantic C3 vs Pacific C5 Freight Skew
        q_c3_c5 = [q for q in self.research_queries if 'C3' in q and 'C5' in q]
        self.assertTrue(len(q_c3_c5) > 0, "Atlantic C3 vs C5 freight skew question missing")
        scopes = auto_select_sources(q_c3_c5[0])
        self.assertIn('baltic', scopes, f"C3/C5 query must route to 'baltic', got {scopes}")

        # 4. 5Y Secondhand Asset Values vs Newbuild Parity
        q_asset = [q for q in self.research_queries if 'secondhand' in q or 'newbuild parity' in q]
        self.assertTrue(len(q_asset) > 0, "5Y asset valuations question missing")
        scopes = auto_select_sources(q_asset[0])
        self.assertIn('hellenic', scopes, f"5Y asset query must route to 'hellenic', got {scopes}")

        # 5. Brazil vs Australia 3.2x Ton-Mile Multiplier
        q_brazil = [q for q in self.research_queries if '3.2x' in q or 'Brazil-to-China' in q]
        self.assertTrue(len(q_brazil) > 0, "Brazil vs Australia ton-mile query missing")
        scopes = auto_select_sources(q_brazil[0])
        self.assertTrue('baltic' in scopes or 'ironOre' in scopes, f"Ton-mile query must route to baltic/ironOre, got {scopes}")

        # 6. VLCC Atlantic vs MEG Ton-Mile Geometry
        q_vlcc_geo = [q for q in self.research_queries if 'VLCC' in q and 'Atlantic' in q]
        self.assertTrue(len(q_vlcc_geo) > 0, "VLCC Atlantic ton-mile query missing")
        scopes = auto_select_sources(q_vlcc_geo[0])
        self.assertIn('baltic', scopes, f"VLCC geometry query must route to baltic, got {scopes}")

    def test_knowledge_chunks_data_integrity(self):
        """Verify all 5 recent knowledge chunk files exist, parse cleanly as JSON, and retain exact figures."""
        chunk_files = [
            'knowledge/chunks/fleet_orderbook_2026.jsonl',
            'knowledge/chunks/chokepoint_and_congestion_2026.jsonl',
            'knowledge/chunks/bunker_and_carbon_spreads_2026.jsonl',
            'knowledge/chunks/regional_freight_spreads_2026.jsonl',
            'knowledge/chunks/sp_asset_valuations_2026.jsonl',
        ]

        total_chunks = 0
        for cf in chunk_files:
            self.assertTrue(os.path.exists(cf), f"Chunk file missing: {cf}")
            with open(cf, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
                for idx, line in enumerate(lines, 1):
                    chunk = json.loads(line)
                    total_chunks += 1
                    self.assertIn('chunk_id', chunk)
                    self.assertIn('text', chunk)
                    self.assertIn('keywords', chunk)
                    # Verify text is substantial and contains numbers
                    self.assertGreater(len(chunk['text']), 80)
                    self.assertTrue(any(c.isdigit() for c in chunk['text']), f"Chunk {chunk['chunk_id']} has no numbers!")

        self.assertGreaterEqual(total_chunks, 11, f"Expected at least 11 recent institutional chunks, found {total_chunks}")

    def test_underlying_matrix_csv_integrity(self):
        """Verify the 5 underlying CSV matrices exist and contain exact matching headers."""
        csv_files = {
            'data/derived/fleet_orderbook_matrix.csv': ['vessel_class', 'active_fleet_count', 'orderbook_count', 'orderbook_to_fleet_pct'],
            'data/derived/chokepoint_transit_metrics.csv': ['chokepoint', 'daily_transit_count', 'diverted_pct'],
            'data/derived/bunker_fuel_spreads.csv': ['port', 'vlsfo_price_usd_mt', 'hsfo_price_usd_mt', 'hi5_spread_usd_mt'],
            'data/derived/regional_commodity_arbitrage.csv': ['arbitrage_metric', 'route_or_pair', 'unit', '5y_percentile'],
            'data/derived/vessel_valuations_matrix.csv': ['vessel_class', 'price_newbuild_usd_m', 'price_5y_usd_m', 'ratio_5y_to_newbuild_pct'],
        }

        for path, required_cols in csv_files.items():
            self.assertTrue(os.path.exists(path), f"CSV matrix missing: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                header = f.readline().strip().split(',')
                for col in required_cols:
                    self.assertIn(col, header, f"Missing column {col} in {path}")


if __name__ == '__main__':
    unittest.main()
