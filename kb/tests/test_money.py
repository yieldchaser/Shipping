"""Defect-17 class, third instance: a real nonzero spend rendered as `$0.0000`.

`None` (unmeasured) and `0.0` (measured zero) were already kept apart. The third state was hiding
inside the second: a real, nonzero, tiny amount that a fixed `:.4f` flattens to the exact string
used for measured zero. P6's entire phase spend is `$0.000013`; one P7 judge call is `$0.000019`.
Both printed as `$0.0000`, which reads as "free" — a false statement in an owner-facing artefact,
from the opposite direction to the unreadable-ledger bug.

Three states, three distinct strings; and the pipeline artefact must not launder the value at
*storage* time either, because `round(1.3e-05, 4) == 0.0` destroys it before any renderer sees it.
"""
from __future__ import annotations

import sys
from pathlib import Path

KB = Path(__file__).resolve().parents[1]
for p in (str(KB), str(KB.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import money as M  # noqa: E402


def test_three_states_are_three_distinct_strings():
    unmeasured = M.fmt_usd(None)
    measured_zero = M.fmt_usd(0.0)
    real_tiny = M.fmt_usd(1.3e-05)
    assert unmeasured == "UNMEASURED"
    assert measured_zero == "$0.0000"
    assert real_tiny == "$0.00001"
    assert len({unmeasured, measured_zero, real_tiny}) == 3
    assert real_tiny != measured_zero, "a real spend must never render as the measured-zero string"


def test_tiny_spend_is_never_flattened_to_zero():
    # Every value the P6/P7 phases actually produce must survive rendering.
    for v in (1.3e-05, 1.9e-05, 4.3e-05, 5.4e-05, 1.0e-09):
        s = M.fmt_usd(v)
        assert float(s.lstrip("$")) != 0.0, (v, s)
        assert s != "$0.0000", (v, s)


def test_measured_zero_still_reads_as_measured_zero():
    # The fix must not turn a genuinely free phase into "unmeasured".
    assert M.fmt_usd(0.0) == "$0.0000"
    assert M.fmt_usd(0) == "$0.0000"
    assert M.fmt_usd(-0.0) == "$0.0000"
    assert "UNMEASURED" not in M.fmt_usd(0.0)


def test_nan_is_unmeasured_not_zero():
    # A broken measurement is not a measurement of zero.
    assert M.fmt_usd(float("nan")) == "UNMEASURED"
    assert M.fmt_usd("not a number") == "UNMEASURED"


def test_normal_amounts_keep_four_places():
    # The widening is a fallback, not the default: readable amounts must not churn format.
    assert M.fmt_usd(24.7385) == "$24.7385"
    assert M.fmt_usd(0.0001) == "$0.0001"
    assert M.fmt_usd(82.0) == "$82.0000"
    assert M.fmt_usd(11.0) == "$11.0000"


def test_round_usd_does_not_launder_a_nonzero_value_to_zero():
    # The storage-side half: 4 dp turned the real P6/P7 spends into a literal 0.0.
    assert M.round_usd(1.3e-05) not in (0.0, None)
    assert M.round_usd(1.9e-05) not in (0.0, None)
    assert M.round_usd(24.7385) == 24.7385
    assert M.round_usd(0.0) == 0.0
    assert M.round_usd(None) is None
    # The old behaviour, kept as the counterexample this fix exists for:
    assert round(1.3e-05, 4) == 0.0


def test_custom_unmeasured_label_is_respected():
    assert M.fmt_usd(None, unmeasured="UNMEASURED (ledger unreadable)") == \
        "UNMEASURED (ledger unreadable)"
