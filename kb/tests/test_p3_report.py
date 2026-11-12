"""Unit tests for the P3 gate helpers and tagger primitives (no DB access)."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import p3_report as R  # noqa: E402
import p3_tag as T  # noqa: E402


def test_largest_remainder_is_proportional_and_exact():
    counts = {"a": 600, "b": 300, "c": 100}
    alloc = R.largest_remainder(counts, 300)
    assert sum(alloc.values()) == 300
    assert alloc["a"] == 180
    assert alloc["b"] == 90
    assert alloc["c"] == 30


def test_largest_remainder_handles_small_pools():
    counts = {"a": 2, "b": 500}
    alloc = R.largest_remainder(counts, 300)
    assert sum(alloc.values()) == 300
    assert 1 <= alloc["a"] <= 2 and alloc["b"] == 300 - alloc["a"]
    assert R.largest_remainder({"a": 3}, 300) == {"a": 3}
    assert R.largest_remainder({}, 10) == {}


def test_precision_counts_unsure_as_wrong():
    assert R.precision_from_verdicts(["same"] * 30) == 1.0
    assert R.precision_from_verdicts(["same"] * 294 + ["different"] * 6) == 0.98
    assert R.precision_from_verdicts(["same", "unsure"]) == 0.5
    assert R.precision_from_verdicts([]) == 0.0


def test_imo_conflict_only_when_both_present_and_different():
    assert R.imo_conflict("9744398", "9744398") is False
    assert R.imo_conflict("9744398", "9339181") is True
    assert R.imo_conflict(None, "9339181") is False
    assert R.imo_conflict("", "") is False


def test_pair_key_is_stable():
    a = R.pair_key("vessel", "vessel:prov:aa", "vessel:imo:1")
    b = R.pair_key("vessel", "vessel:prov:aa", "vessel:imo:1")
    assert a == b and len(a) == 24


def test_norm_text_is_case_and_punctuation_insensitive():
    assert T.norm_text("M/T  STENA-IMPERIAL") == "m t stena imperial"
    assert T.norm_text("  ") == ""


def test_aho_corasick_finds_overlapping_and_reports_end():
    ac = T.AhoCorasick()
    ac.add("new horizon", 0)
    ac.add("horizon", 1)
    ac.build()
    hits = sorted(ac.search("the new horizon ship"))
    assert (0, len("the new horizon") - 1) in hits
    assert (1, len("the new horizon") - 1) in hits


def _patterns():
    return {
        0: {"norm": "stena imperial", "type": "vessel", "eids": ["vessel:imo:1"],
            "corroborate": False},
        1: {"norm": "ocean", "type": "vessel", "eids": ["vessel:prov:1"], "corroborate": True},
    }


def _tagger(patterns):
    ac = T.AhoCorasick()
    for pid, p in patterns.items():
        ac.add(p["norm"], pid)
    ac.build()
    return ac


def test_tag_chunk_tags_unique_multitoken_name_without_corroboration():
    st = Counter()
    tags = T.tag_chunk("STENA IMPERIAL arrived at Rotterdam", _tagger(_patterns()),
                       _patterns(), {}, {}, st)
    assert tags == ["vessel:imo:1"]
    assert st["hits"] == 1


def test_single_token_vessel_needs_corroboration():
    st = Counter()
    attrs = {"vessel:prov:1": {"dwt": 50000, "built": 2012}}
    tags = T.tag_chunk("the ocean was calm", _tagger(_patterns()), _patterns(), attrs, {}, st)
    assert tags == []
    assert st["ambiguous_skipped"] == 1
    st = Counter()
    tags = T.tag_chunk("the ocean (dwt 50,000) sailed", _tagger(_patterns()), _patterns(),
                       attrs, {}, st)
    assert tags == ["vessel:prov:1"]
    assert st["ambiguous_corroborated"] == 1


def test_printed_imo_tags_identity_even_when_names_differ():
    st = Counter()
    imo = {"9744398": "vessel:imo:999"}
    tags = T.tag_chunk("some ship IMO 9744398 delivered", _tagger(_patterns()), _patterns(),
                       {}, imo, st)
    assert tags == ["vessel:imo:999"]
    assert st["imo_tags"] == 1


def test_no_tag_on_word_boundary_partial_match():
    st = Counter()
    tags = T.tag_chunk("STENA IMPERIALIZATION", _tagger(_patterns()), _patterns(), {}, {}, st)
    assert tags == []


def test_load_patterns_rules():
    """Cross-type and >3-candidate names are dropped; single-token vessels corroborate."""
    class FakeCon:
        def execute(self, sql):
            class Rows:
                def fetchall(self):
                    if "SELECT entity_id, attrs" in sql:
                        return [("company:int:new", '{"merged_into":"company:cik:1"}'),
                                ("company:int:keep", "{}")]
                    if "FROM entity" in sql and "SELECT entity_id, type" in sql:
                        return [("vessel:imo:1", "vessel"), ("vessel:prov:1", "vessel"),
                                ("company:cik:1", "company"), ("port:1", "port"),
                                ("vessel:prov:2", "vessel"), ("vessel:prov:3", "vessel"),
                                ("vessel:prov:4", "vessel"),
                                ("company:int:new", "company"),
                                ("company:int:each", "company"),
                                ("company:int:keep", "company")]
                    return [("STENA IMPERIAL", "stena imperial", "vessel:imo:1", "x"),
                            ("OCEAN", "ocean", "vessel:prov:1", "x"),
                            ("OCEAN", "ocean", "port:1", "x"),
                            ("BLUE STAR", "blue star", "vessel:prov:2", "x"),
                            ("BLUE STAR", "blue star", "vessel:prov:3", "x"),
                            ("BLUE STAR", "blue star", "vessel:prov:4", "x"),
                            ("FLEET 7", "fleet 7", "vessel:prov:2", "x"),
                            ("FLEET 7", "fleet 7", "vessel:prov:3", "x"),
                            ("FLEET 7", "fleet 7", "vessel:prov:4", "x"),
                            ("OF THE", "of the", "vessel:prov:1", "x"),
                            ("81 000 DWT", "81 000 dwt", "vessel:prov:2", "x"),
                            ("RED SEA", "red sea", "vessel:prov:3", "x"),
                            ("NEW SHIPPING", "new shipping", "company:int:new", "x"),
                            ("EACH", "each", "company:int:each", "x"),
                            ("MAERSK TANKERS", "maersk tankers", "company:int:keep", "x")]
            return Rows()

    patterns, stats = T.load_patterns(FakeCon())
    norms = {p["norm"]: p for p in patterns.values()}
    assert "stena imperial" in norms and norms["stena imperial"]["corroborate"] is False
    assert "ocean" not in norms and stats["skipped_cross_type"] == 1
    assert norms["blue star"]["corroborate"] is True
    assert len(norms["blue star"]["eids"]) == 3
    assert "fleet 7" in norms and norms["fleet 7"]["corroborate"] is True
    # parse debris is never a pattern; generic company words are dropped
    assert "of the" not in norms and "81 000 dwt" not in norms and "red sea" not in norms
    assert stats["skipped_implausible_vessel"] == 3
    assert "each" not in norms and stats["skipped_generic_company"] == 1
    # a provisional company resolved to a SEC CIK is tagged as the SEC identity
    assert norms["new shipping"]["eids"] == ["company:cik:1"]
    assert norms["maersk tankers"]["eids"] == ["company:int:keep"]


def test_vessel_name_ok():
    assert T.vessel_name_ok("stena imperial")
    assert T.vessel_name_ok("ocean")
    assert not T.vessel_name_ok("of the")
    assert not T.vessel_name_ok("were reported")
    assert not T.vessel_name_ok("81 000 dwt")
    assert not T.vessel_name_ok("red sea")
    assert not T.vessel_name_ok("the strong")
    assert not T.vessel_name_ok("1234567")


def test_company_pattern_ok():
    assert T.company_pattern_ok("maersk line", False)
    assert T.company_pattern_ok("any name", True)  # SEC trusted
    assert not T.company_pattern_ok("new shipping", False)
    assert not T.company_pattern_ok("management sa", False)
    assert not T.company_pattern_ok("each", False)
    assert not T.company_pattern_ok("s korea", False)
