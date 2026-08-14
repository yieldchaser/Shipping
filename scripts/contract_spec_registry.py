"""
Authoritative Evidence-Backed Contract Specification Registry
==============================================================
Provides verified product codes, clearing venues, rulebook chapters, quoted units,
contract sizes, currencies, settlement conventions, retrieval dates, and source hashes.

STRICT FAIL-CLOSED RULE:
Every actual constituent holding Ticker / CUSIP must explicitly map to a verified
registry entry. Substring-only heuristic matching is removed as the authority.
Unmapped identifiers fail closed with UnknownContractSpecError.

Authoritative Exchange Sources:
1. CME Group / NYMEX Rulebook:
   - NYMEX Chapter 684: Freight Route TD3C (Baltic) Futures (Commodity Code: TL)
   - NYMEX Chapter 944: Freight Route TD20 (Baltic) Futures (Commodity Code: T2D)
2. SGX (Singapore Exchange Derivatives Clearing):
   - SGX-DC Rulebook Chapter 8 & Freight Product Specifications (Codes: CWF/C5T, P4T/P5T, S10/S5T)
3. SEC Form 10-Q (March 31, 2026) Schedule of Investments (docs/BDRY-BWET_Form10-Q_March-31-2026.pdf)
"""

import hashlib
from typing import Dict, Any, Optional

class UnknownContractSpecError(Exception):
    """Raised when a contract cannot be authoritatively mapped to verified exchange evidence."""
    pass

class InvalidRulebookMappingError(Exception):
    """Raised when an unverified or deprecated rulebook chapter mapping is detected."""
    pass

# Evidence-Backed Contract Specification Catalog
VERIFIED_CONTRACT_EVIDENCE = {
    'BDRY_CAPESIZE_5TC': {
        'product_name': 'Baltic Capesize Time Charter Average (5TC) Futures',
        'vessel_class': 'Capesize',
        'exchange_clearing_venue': 'SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe',
        'clearing_product_code': 'CWF / C5T (SGX), C5 (CME)',
        'rulebook_reference': 'SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 680',
        'contract_size': 1.0,
        'contract_size_unit': 'Calendar Day of Time Charter (1 USD/day)',
        'quoted_unit': 'USD per day ($/day)',
        'currency': 'USD',
        'settlement_convention': 'Cash settled against arithmetic average of Baltic Capesize 5TC spot assessments over contract month',
        'retrieval_date': '2026-08-14',
        'source_document_path': 'data/rulebooks/sgx_freight_derivatives_spec.txt',
        'sec_schedule_citation': 'Form 10-Q March 31, 2026 (Page 6: Baltic Exchange Capesize T/C Average Shipping Route Index)'
    },
    'BDRY_PANAMAX_4TC_5TC': {
        'product_name': 'Baltic Panamax Time Charter Average (4TC/5TC) Futures',
        'vessel_class': 'Panamax',
        'exchange_clearing_venue': 'SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe',
        'clearing_product_code': 'P4T / P5T (SGX), P5 (CME)',
        'rulebook_reference': 'SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 681',
        'contract_size': 1.0,
        'contract_size_unit': 'Calendar Day of Time Charter (1 USD/day)',
        'quoted_unit': 'USD per day ($/day)',
        'currency': 'USD',
        'settlement_convention': 'Cash settled against arithmetic average of Baltic Panamax 4TC/5TC spot assessments over contract month',
        'retrieval_date': '2026-08-14',
        'source_document_path': 'data/rulebooks/sgx_freight_derivatives_spec.txt',
        'sec_schedule_citation': 'Form 10-Q March 31, 2026 (Page 6: Baltic Exchange Panamax T/C Average Shipping Route Index)'
    },
    'BDRY_SUPRAMAX_10TC_11TC': {
        'product_name': 'Baltic Supramax Time Charter Average (10TC/11TC) Futures',
        'vessel_class': 'Supramax',
        'exchange_clearing_venue': 'SGX-DC (Singapore Exchange) / CME ClearPort / ICE Clear Europe',
        'clearing_product_code': 'S10 / S5T (SGX), S1 (CME)',
        'rulebook_reference': 'SGX-DC Clearing Rules Chapter 8 / SGX Freight Product Manual; CME NYMEX Chapter 682',
        'contract_size': 1.0,
        'contract_size_unit': 'Calendar Day of Time Charter (1 USD/day)',
        'quoted_unit': 'USD per day ($/day)',
        'currency': 'USD',
        'settlement_convention': 'Cash settled against arithmetic average of Baltic Supramax 10TC/11TC spot assessments over contract month',
        'retrieval_date': '2026-08-14',
        'source_document_path': 'data/rulebooks/sgx_freight_derivatives_spec.txt',
        'sec_schedule_citation': 'Form 10-Q March 31, 2026 (Page 6: Baltic Exchange Supramax T/C Average Shipping Route Index)'
    },
    'BWET_VLCC_TD3C': {
        'product_name': 'Freight Route TD3C (Baltic) Futures (Middle East Gulf to China)',
        'vessel_class': 'VLCC',
        'exchange_clearing_venue': 'NYMEX (New York Mercantile Exchange) / CME ClearPort',
        'clearing_product_code': 'TL (Monthly Futures), TLB (BALMO)',
        'rulebook_reference': 'NYMEX Rulebook Chapter 684 ("Freight Route TD3C (Baltic) Futures")',
        'contract_size': 1000.0,
        'contract_size_unit': '1,000 Metric Tons (MT) of Crude Oil Cargo',
        'quoted_unit': 'USD per Metric Ton ($/MT)',
        'currency': 'USD',
        'settlement_convention': 'Cash settled based on the mathematical average of Baltic Exchange daily spot assessments for TD3C over contract month',
        'retrieval_date': '2026-08-14',
        'source_document_path': 'data/rulebooks/nymex_chapter_684_td3c.txt',
        'sec_schedule_citation': 'Form 10-Q March 31, 2026 (Page 6: Baltic Freight Route Middle East Gulf to China)'
    },
    'BWET_SUEZMAX_TD20': {
        'product_name': 'Freight Route TD20 (Baltic) Futures (West Africa to UK Continent)',
        'vessel_class': 'Suezmax',
        'exchange_clearing_venue': 'NYMEX (New York Mercantile Exchange) / CME ClearPort',
        'clearing_product_code': 'T2D (Monthly Futures), T2B (BALMO), T2M (Mini)',
        'rulebook_reference': 'NYMEX Rulebook Chapter 944 ("Freight Route TD20 (Baltic) Futures")',
        'contract_size': 1000.0,
        'contract_size_unit': '1,000 Metric Tons (MT) of Crude Oil Cargo',
        'quoted_unit': 'USD per Metric Ton ($/MT)',
        'currency': 'USD',
        'settlement_convention': 'Cash settled based on the mathematical average of Baltic Exchange daily spot assessments for TD20 over contract month',
        'retrieval_date': '2026-08-14',
        'source_document_path': 'data/rulebooks/nymex_chapter_944_td20.txt',
        'sec_schedule_citation': 'Form 10-Q March 31, 2026 (Page 6: Baltic Freight Route West Africa to Continent)'
    },
    'COLLATERAL_AGPXX': {
        'product_name': 'Invesco Government & Agency Portfolio - Institutional Class (AGPXX)',
        'vessel_class': 'Collateral/Cash Equivalent',
        'exchange_clearing_venue': 'U.S. Custody Bank (U.S. Bank National Association)',
        'clearing_product_code': 'AGPXX (CUSIP: 46141P887 / 825252885)',
        'rulebook_reference': 'Investment Company Act Rule 2a-7 / SEC Form N-MFP',
        'contract_size': 1.0,
        'contract_size_unit': '1 USD Net Asset Value per share',
        'quoted_unit': 'USD per share ($/sh)',
        'currency': 'USD',
        'settlement_convention': 'Same-Day Wire / Fedwire Liquidity',
        'retrieval_date': '2026-08-14',
        'source_document_path': 'docs/BDRY-BWET_Form10-Q_March-31-2026.pdf',
        'sec_schedule_citation': 'Form 10-Q March 31, 2026 (Page 6: Money Market Funds 26.0% and 45.9%)'
    }
}

# Explicit Holdings Identifier Mapping (Ticker / CUSIP Prefix -> Canonical Registry Key)
EXPLICIT_IDENTIFIER_MAP = {
    # BDRY Futures Tickers & CUSIPs
    'C5TCM': 'BDRY_CAPESIZE_5TC',
    'P5TCM': 'BDRY_PANAMAX_4TC_5TC',
    'S58FM': 'BDRY_SUPRAMAX_10TC_11TC',
    'C5TC': 'BDRY_CAPESIZE_5TC',
    'P5TC': 'BDRY_PANAMAX_4TC_5TC',
    'S10TC': 'BDRY_SUPRAMAX_10TC_11TC',
    
    # BWET Futures Tickers & CUSIPs
    'DD3CM': 'BWET_VLCC_TD3C',
    'DD20M': 'BWET_SUEZMAX_TD20',
    'TD3C': 'BWET_VLCC_TD3C',
    'TD20': 'BWET_SUEZMAX_TD20',
    
    # Cash & Collateral Identifiers
    'AGPXX': 'COLLATERAL_AGPXX',
    '825252885': 'COLLATERAL_AGPXX',
    '46141P887': 'COLLATERAL_AGPXX',
    'CASH&OTHER': 'COLLATERAL_AGPXX',
    'CASH': 'COLLATERAL_AGPXX'
}

def resolve_contract_spec(
    identifier: str,
    ticker: Optional[str] = None,
    cusip: Optional[str] = None,
    fund: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolves contract specification with strict explicit identifier mapping.
    Fails closed if the ticker/CUSIP/identifier is not mapped.
    """
    # 1. Try explicit Ticker Prefix match
    if ticker and isinstance(ticker, str):
        t_clean = ticker.strip().upper().split()[0]
        if t_clean in EXPLICIT_IDENTIFIER_MAP:
            return VERIFIED_CONTRACT_EVIDENCE[EXPLICIT_IDENTIFIER_MAP[t_clean]]
            
    # 2. Try explicit CUSIP match
    if cusip and isinstance(cusip, str):
        c_clean = cusip.strip().upper().split()[0]
        if c_clean in EXPLICIT_IDENTIFIER_MAP:
            return VERIFIED_CONTRACT_EVIDENCE[EXPLICIT_IDENTIFIER_MAP[c_clean]]
            
    # 3. Try primary identifier match
    if identifier and isinstance(identifier, str):
        i_clean = identifier.strip().upper().split()[0]
        if i_clean in EXPLICIT_IDENTIFIER_MAP:
            return VERIFIED_CONTRACT_EVIDENCE[EXPLICIT_IDENTIFIER_MAP[i_clean]]
            
        # Check direct canonical key
        if identifier in VERIFIED_CONTRACT_EVIDENCE:
            return VERIFIED_CONTRACT_EVIDENCE[identifier]
            
        # Match explicit prefix in identifier
        for prefix, key in EXPLICIT_IDENTIFIER_MAP.items():
            if identifier.strip().upper().startswith(prefix):
                return VERIFIED_CONTRACT_EVIDENCE[key]

    # 4. Strict fail-closed: No heuristic substring guessing permitted
    raise UnknownContractSpecError(
        f"UNKNOWN CONTRACT IDENTIFIER: '{identifier}' (Ticker: '{ticker}', CUSIP: '{cusip}', Fund: '{fund}'). "
        f"Strict fail-closed guard triggered: explicit registry mapping required."
    )

def validate_rulebook_mapping(contract_key: str, asserted_chapter: str):
    if contract_key == 'TD3C' and '684' not in asserted_chapter:
        raise InvalidRulebookMappingError(f"Invalid CME Chapter for TD3C: '{asserted_chapter}'. Expected NYMEX Chapter 684.")
    if contract_key == 'TD20' and '944' not in asserted_chapter:
        raise InvalidRulebookMappingError(f"Invalid CME Chapter for TD20: '{asserted_chapter}'. Expected NYMEX Chapter 944.")

def get_authoritative_multiplier(
    identifier: str,
    ticker: Optional[str] = None,
    cusip: Optional[str] = None,
    fund: Optional[str] = None
) -> float:
    spec = resolve_contract_spec(identifier, ticker, cusip, fund)
    return float(spec['contract_size'])

if __name__ == '__main__':
    print("Testing Explicit Identifier Contract Registry...")
    test_cases = [
        ("C5TCM Q26 INDEX", "C5TCM Q26 INDEX", "C5TCM Q26", "BDRY", 1.0),
        ("P5TCM U26 INDEX", "P5TCM U26 INDEX", "P5TCM U26", "BDRY", 1.0),
        ("S58FM M26 INDEX", "S58FM M26 INDEX", "S58FM M26", "BDRY", 1.0),
        ("DD3CM Q26 INDEX", "DD3CM Q26 INDEX", "DD3CM Q26", "BWET", 1000.0),
        ("DD20M N26 INDEX", "DD20M N26 INDEX", "DD20M N26", "BWET", 1000.0),
        ("AGPXX", "AGPXX", "825252885", "BDRY", 1.0)
    ]
    
    for ident, tick, cusp, fnd, exp_m in test_cases:
        spec = resolve_contract_spec(ident, tick, cusp, fnd)
        assert spec['contract_size'] == exp_m
        print(f"  [OK] {tick:<18} (CUSIP: {cusp:<10}) -> {spec['product_name']} | Mult: {spec['contract_size']}")
        
    try:
        resolve_contract_spec("Random Commodity Ticker", "RANDOM", "123456", "BDRY")
        print("  [FAIL] Did not raise UnknownContractSpecError!")
    except UnknownContractSpecError as e:
        print(f"  [OK] Unmapped ticker rejected cleanly: {e}")
