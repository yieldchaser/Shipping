"""P3 identity helpers: normalisation + key parsing (plan §6.2, §6.4, D8).

Pure functions only — unit-tested in kb/tests/test_p3.py. No I/O, no DB.
Identity rule (plan D8): keys decide identity, names never create or merge a
vessel on their own; a name match needs corroborating DWT / built-year / yard.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# ----------------------------------------------------------------------------- text
_LEGAL_SUFFIXES = {
    "INC", "INCORPORATED", "LTD", "LIMITED", "LLC", "L L C", "PLC", "CORP",
    "CORPORATION", "CO", "COMPANY", "SA", "S A", "NV", "BV", "AB", "ASA", "GMBH",
    "SE", "AG", "SRL", "PTE", "PT", "LP", "LLP", "HOLDINGS", "HOLDING", "GROUP",
    "THE",
}
# Vessel-class and business words (TANKERS, BULKERS, SHIPPING, MARITIME, LINES, ...)
# are NOT legal suffixes: they discriminate between sister companies ("Scorpio
# Tankers" vs "Scorpio Bulkers"), so stripping them would merge distinct entities.
_NON_NAME_TOKENS = {"UNDISCLOSED", "UNKNOWN", "NONE", "N A", "NA", "TBA", "TBN", "VARIOUS"}
# words that never identify a vessel by themselves
_VESSEL_STOP = {
    "STAR", "SEA", "OCEAN", "MARINE", "PACIFIC", "ATLANTIC", "GLORY", "LUCKY",
    "HAPPY", "GREAT", "NEW", "BLUE", "GOLDEN", "SILVER", "DIAMOND", "PEARL",
    "PRINCESS", "QUEEN", "KING", "LADY", "SPIRIT", "HARMONY", "UNITY", "FORTUNE",
    "VICTORY", "TRIUMPH", "HORIZON", "SUNRISE", "SUNSET", "WIND", "WAVE", "ISLAND",
    "BAY", "PORT", "CARRIER", "TRADER", "SHIPPING", "MARITIME", "TANKER", "BULKER",
    "VESSEL", "M V", "MV", "MT", "SS", "PIONEER", "DISCOVERY", "EXPLORER", "ADVENTURE",
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_text(s: str | None) -> str:
    """Uppercase, accent-free, punctuation-free, single-spaced."""
    if not s:
        return ""
    s = strip_accents(str(s)).upper().replace("&", " AND ")
    s = re.sub(r"\bM\s*/\s*[VT]\b", " ", s)          # M/V, M/T
    s = re.sub(r"\bM\.?V\.?\b", " ", s)               # MV, M.V.
    s = re.sub(r"\bM\.?T\.?\b", " ", s)               # MT
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_VESSEL_NOISE = {"M V", "MV", "MT", "SS", "VESSEL", "SHIP", "TBN", "TBA", "UNKNOWN", "N A", "NA"}


def norm_vessel_name(s: str | None) -> str:
    """Normalised vessel name: no prefixes, no trailing hull numbers removed (they matter)."""
    t = norm_text(s)
    toks = [w for w in t.split() if w not in _VESSEL_NOISE]
    return " ".join(toks)


def name_tokens(s: str | None) -> tuple[str, ...]:
    return tuple(norm_vessel_name(s).split())


def is_distinctive_vessel_name(norm: str) -> bool:
    """A name may not be trusted on its own when it is a single generic word (plan D8)."""
    toks = norm.split()
    if len(toks) >= 2:
        return True
    return bool(toks) and len(toks[0]) >= 6 and toks[0] not in _VESSEL_STOP


ALIAS_MAX_IMOS = 3  # a registry name shared by more IMOs than this is a hull/yard placeholder


def vessel_alias_ok(name_norm: str, n_distinct_imos: int) -> bool:
    """May this registry name become a text alias? (plan §6.2 / D8)

    Numeric hull numbers are not names; a name used by many IMOs is a shipyard or
    "new building" placeholder, so it can never carry identity on its own.
    """
    if not name_norm or name_norm.isdigit() or len(name_norm) < 3:
        return False
    if name_norm in _VESSEL_STOP:
        return False
    return n_distinct_imos <= ALIAS_MAX_IMOS


_YARD_NOISE = {
    "SHIPYARD", "SHIPBUILDING", "SHIPBUILDERS", "SHBLDG", "SHBLDG", "SHB", "SHYD", "SHIPYARD",
    "SHIPYARDS", "SHBLD", "SHB", "SHPBLDG", "SHPYRD", "IND", "INDUSTRIES", "INDUSTRY", "CO",
    "LTD", "INTL", "INT", "INTERNATIONAL", "HEAVY", "HI", "YARD", "DOCKYARD", "GROUP", "THE",
    "CORP", "INC", "COMPANY", "FACTORY", "WORKS", "NO", "NR",
}


def norm_yard(s: str | None) -> str:
    toks = [w for w in norm_text(s).split() if w not in _YARD_NOISE and not w.isdigit()]
    return " ".join(toks)


def token_set(s: str | None, min_len: int = 2) -> frozenset[str]:
    return frozenset(t for t in norm_yard(s).split() if len(t) >= min_len)


def yard_similar(a: str | None, b: str | None) -> float:
    """Jaccard over yard tokens; 0.0 when either side is empty."""
    ta, tb = token_set(a), token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def norm_company(s: str | None) -> str:
    """Normalised company name: nationality/domicile words and legal suffixes removed."""
    t = norm_text(s)
    _, t = strip_nationality(t)
    toks = [w for w in t.split() if w not in _LEGAL_SUFFIXES]
    return " ".join(toks)


def company_slug(s: str | None) -> str:
    n = norm_company(s)
    return re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")


def is_undisclosed(s: str | None) -> bool:
    t = norm_text(s)
    return (not t) or any(t == w or t.startswith(w + " ") for w in _NON_NAME_TOKENS)


# ------------------------------------------------------------------ nationality
# Demonyms / domicile words that appear as prefixes in broker counterparty columns.
# Value = ISO-3166-1 alpha-2. Only unambiguous words, no guesses.
NATIONALITY: dict[str, str] = {
    "AFGHAN": "AF", "AMERICAN": "US", "US": "US", "USA": "US", "U S": "US",
    "UAE": "AE", "EMIRATI": "AE", "DUBAI": "AE", "SAUDI": "SA", "QATARI": "QA",
    "KUWAITI": "KW", "OMANI": "OM", "BAHRAINI": "BH", "IRANIAN": "IR", "IRAQI": "IQ",
    "GREEK": "GR", "GREECE": "GR", "HELLENIC": "GR",
    "CHINESE": "CN", "CHINA": "CN", "PRC": "CN", "HONG KONG": "HK", "TAIWANESE": "TW",
    "JAPANESE": "JP", "KOREAN": "KR", "SOUTH KOREAN": "KR", "S KOREAN": "KR",
    "INDIAN": "IN", "INDIA": "IN", "PAKISTANI": "PK", "BANGLADESHI": "BD", "BANGLADESH": "BD",
    "SINGAPOREAN": "SG", "SINGAPORE": "SG", "MALAYSIAN": "MY", "INDONESIAN": "ID",
    "THAI": "TH", "VIETNAMESE": "VN", "FILIPINO": "PH", "PHILIPPINE": "PH",
    "NORWEGIAN": "NO", "DANISH": "DK", "SWEDISH": "SE", "FINNISH": "FI", "ICELANDIC": "IS",
    "GERMAN": "DE", "DUTCH": "NL", "BELGIAN": "BE", "FRENCH": "FR", "ITALIAN": "IT",
    "SPANISH": "ES", "PORTUGUESE": "PT", "TURKISH": "TR", "CYPRUS": "CY", "CYPRIOT": "CY",
    "MALTESE": "MT", "BRITISH": "GB", "UK": "GB", "ENGLISH": "GB", "SCOTTISH": "GB",
    "IRISH": "IE", "SWISS": "CH", "AUSTRIAN": "AT", "POLISH": "PL", "CROATIAN": "HR",
    "RUSSIAN": "RU", "UKRAINIAN": "UA", "ESTONIAN": "EE", "LATVIAN": "LV", "LITHUANIAN": "LT",
    "BRAZILIAN": "BR", "ARGENTINIAN": "AR", "CHILEAN": "CL", "MEXICAN": "MX",
    "CANADIAN": "CA", "AUSTRALIAN": "AU", "NEW ZEALAND": "NZ", "SOUTH AFRICAN": "ZA",
    "EGYPTIAN": "EG", "NIGERIAN": "NG", "MOROCCAN": "MA", "LIBYAN": "LY", "ALGERIAN": "DZ",
    "BERMUDIAN": "BM", "BERMUDA": "BM", "PANAMANIAN": "PA", "LIBERIAN": "LR",
    "MARSHALL ISLANDS": "MH", "MARSHALLESE": "MH", "HONGKONG": "HK",
    "EUROPEAN": "EU", "ASIAN": "AS", "FAR EASTERN": "FE", "MIDDLE EASTERN": "ME",
}
_DOMICILE_WORDS = {"BASED", "BUYERS", "BUYER", "SELLERS", "SELLER", "OWNERS", "OWNER",
                   "INTERESTS", "INTEREST", "CONTROLLED", "BACKED", "HEADQUARTERED", "OWNED"}


def strip_nationality(text: str | None) -> tuple[str | None, str]:
    """Split a broker counterparty string into (iso2|None, remainder).

    'GREEK NG M' -> ('GR', 'NG M'); 'UAE BASED' -> ('AE', ''); 'MSC' -> (None, 'MSC').
    Multi-word demonyms are matched longest-first. Deterministic, no guessing.
    """
    t = norm_text(text)
    if not t:
        return None, ""
    iso = None
    changed = True
    words = t.split()
    while changed and words:
        changed = False
        for key in sorted(NATIONALITY, key=lambda k: -len(k.split())):
            kt = key.split()
            if words[: len(kt)] == kt:
                iso = iso or NATIONALITY[key]
                words = words[len(kt):]
                changed = True
                break
        if words and words[-1] in _DOMICILE_WORDS:
            words = words[:-1]
            changed = True
        if words and words[0] in _DOMICILE_WORDS:
            words = words[1:]
            changed = True
    return iso, " ".join(words)


# ------------------------------------------------------------------------ keys
IMO_RE = re.compile(r"\b(\d{7})\b")


def imo_checksum_ok(imo: str | int) -> bool:
    """IMO number check digit (7 digits): sum(d_i*(7-i) for first 6) % 10 == d_7."""
    s = re.sub(r"\D", "", str(imo))
    if len(s) != 7:
        return False
    total = sum(int(s[i]) * (7 - i) for i in range(6))
    return total % 10 == int(s[6])


def find_imo(text: str | None) -> str | None:
    """First valid IMO number in text, else None."""
    if not text:
        return None
    for m in IMO_RE.finditer(str(text)):
        if imo_checksum_ok(m.group(1)):
            return m.group(1)
    return None


_NUM_RE = re.compile(r"(\d[\d,.\s]*)")


def parse_dwt(value) -> int | None:
    """Printed deadweight -> int tonnes. '261,838' -> 261838; 'DWT 180,000' -> 180000."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    m = _NUM_RE.search(s)
    if not m:
        return None
    raw = m.group(1).replace(",", "").replace(" ", "").rstrip(".")
    try:
        v = float(raw)
    except ValueError:
        return None
    if v < 20:             # implausible as deadweight even in thousands
        return None
    if v < 1000:           # thousands convention, e.g. '180' for 180,000 dwt
        v *= 1000
    v = int(round(v))
    return v if 200 <= v <= 700_000 else None


_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def parse_year(value) -> int | None:
    if value is None:
        return None
    m = _YEAR_RE.search(str(value))
    if not m:
        return None
    y = int(m.group(1))
    return y if 1900 <= y <= 2035 else None


def dwt_close(a: int | None, b: int | None, rel: float = 0.02, abs_floor: int = 100) -> bool:
    """True when both known and within max(abs_floor, rel*max)."""
    if not a or not b:
        return False
    return abs(a - b) <= max(abs_floor, rel * max(a, b))


def year_close(a: int | None, b: int | None, tol: int = 1) -> bool:
    if not a or not b:
        return False
    return abs(a - b) <= tol


def corroboration(dwt_a, dwt_b, built_a, built_b, yard_a, yard_b,
                  name_sim: float, name_exact: bool) -> tuple[int, dict]:
    """Count corroborating attributes for a candidate vessel pair (plan §6.2, §6.4).

    Name similarity alone never corroborates (D8). Returns (count, detail).
    Attributes: DWT ±2%, built year ±1, yard token-Jaccard >= 0.5, IMO equality
    (only possible when both sides print an IMO; handled by caller).
    """
    detail = {
        "dwt_close": dwt_close(dwt_a, dwt_b),
        "year_close": year_close(built_a, built_b),
        "yard_match": yard_similar(yard_a, yard_b) >= 0.5,
        "name_exact": bool(name_exact),
        "name_sim": round(float(name_sim), 3),
        # explicit contradictions: both sides carry the attribute but it disagrees
        "dwt_conflict": bool(dwt_a and dwt_b and not dwt_close(dwt_a, dwt_b)),
        "year_conflict": bool(built_a and built_b and not year_close(built_a, built_b)),
    }
    n = int(detail["dwt_close"]) + int(detail["year_close"]) + int(detail["yard_match"])
    return n, detail


# --------------------------------------------------------------------- tiers
AUTO_MIN_CORROBORATION = 2
AUTO_MIN_NAME_SIM = 0.90


def decide_tier(n_corroborating: int, name_sim: float, name_exact: bool,
                n_candidates: int, weight: float) -> str:
    """Tier a candidate pair: 'auto' (merge), 'llm' (adjudicate), 'separate'.

    Precision-first (gate: merge precision >= 0.98):
      auto   = EXACT normalised name AND >= 2 corroborating attributes AND unique
               candidate; near-miss spellings ("Grace Leo" / "Grace Leon") are two
               letters from a different ship, so they always need adjudication.
      llm    = name close enough AND (>= 1 corroborating attribute or ambiguity)
      separate = everything else
    Name similarity alone never merges (plan D8).
    """
    name_ok = name_exact or name_sim >= AUTO_MIN_NAME_SIM
    if not name_ok:
        return "separate"
    if name_exact and n_corroborating >= AUTO_MIN_CORROBORATION and n_candidates == 1:
        return "auto"
    if n_corroborating >= 1 or n_candidates > 1:
        return "llm"
    return "separate"


# A merge is only retained when the evidence actually distinguishes the ship: the
# name must be (nearly) identical and at least one hard attribute must agree. A judge
# "same" on a bare name with no comparable attribute is not enough — that is exactly
# the "same name, different ship" trap the gate audits for.
MERGE_MIN_NAME_SIM = 0.95
MERGE_MIN_CORROBORATION = 1


def merge_sufficient(name_sim: float, name_exact: bool, n_corroborating: int,
                     detail: dict | None = None) -> bool:
    """True when a candidate pair carries enough evidence to be merged (plan §6.4)."""
    if not (name_exact or name_sim >= MERGE_MIN_NAME_SIM):
        return False
    if bool((detail or {}).get("dwt_conflict")) or bool((detail or {}).get("year_conflict")):
        return False
    return n_corroborating >= MERGE_MIN_CORROBORATION


def precision_ok(agree: int, total: int, minimum: float = 0.98) -> bool:
    return total > 0 and agree / total >= minimum
