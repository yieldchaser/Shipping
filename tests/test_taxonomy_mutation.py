"""
tests/test_taxonomy_mutation.py

Mutation test suite for taxonomy coherence per Prompt 13B §C7.
Asserts that each of the 5 planted mutations into Fearnleys continuous rate headers
is caught decisively by check_taxonomy_coherence.
"""

import pytest
from tests.test_fearnleys_labels_and_ranges import load_data, check_taxonomy_coherence


def test_mutation_c3_to_c5_fails():
    """Mutation 1: C3 -> C5 on tsid_10001 must fail coherence check."""
    headers, _ = load_data()
    mutated = [h.replace("(C3)", "(C5)") if "tsid_10001" in h else h for h in headers]
    with pytest.raises(AssertionError) as exc_info:
        check_taxonomy_coherence(mutated)
    assert "C3" in str(exc_info.value) or "tsid_10001" in str(exc_info.value) or "C5" in str(exc_info.value)


def test_mutation_p2a_to_p3a_fails():
    """Mutation 2: P2A_82 -> P3A_82 on tsid_10011 must fail coherence check."""
    headers, _ = load_data()
    mutated = [h.replace("(P2A_82)", "(P3A_82)") if "tsid_10011" in h else h for h in headers]
    with pytest.raises(AssertionError) as exc_info:
        check_taxonomy_coherence(mutated)
    assert "P2A_82" in str(exc_info.value) or "tsid_10011" in str(exc_info.value) or "P3A_82" in str(exc_info.value)


def test_mutation_p4_to_p6_fails():
    """Mutation 3: P4_82 -> P6_82 on tsid_10013 must fail coherence check."""
    headers, _ = load_data()
    mutated = [h.replace("(P4_82)", "(P6_82)") if "tsid_10013" in h else h for h in headers]
    with pytest.raises(AssertionError) as exc_info:
        check_taxonomy_coherence(mutated)
    assert "P4_82" in str(exc_info.value) or "tsid_10013" in str(exc_info.value) or "P6_82" in str(exc_info.value)


def test_mutation_bogus_c99_fails():
    """Mutation 4: Bogus code C99 must fail coherence check (unknown code)."""
    headers, _ = load_data()
    mutated = [h.replace("(C3)", "(C99)") if "tsid_10001" in h else h for h in headers]
    with pytest.raises(AssertionError) as exc_info:
        check_taxonomy_coherence(mutated)
    assert "C99" in str(exc_info.value)


def test_mutation_s1c_to_s1b_fails():
    """Mutation 5: S1C -> S1B on tsid_120129 must fail coherence check."""
    headers, _ = load_data()
    mutated = [h.replace("(S1C)", "(S1B)") if "tsid_120129" in h else h for h in headers]
    with pytest.raises(AssertionError) as exc_info:
        check_taxonomy_coherence(mutated)
    assert "S1C" in str(exc_info.value) or "tsid_120129" in str(exc_info.value) or "S1B" in str(exc_info.value)
