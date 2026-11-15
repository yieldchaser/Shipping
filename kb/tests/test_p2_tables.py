"""The P2 broker-table price read must be a real finite float or nothing (pytest)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import p2_known_values as K  # noqa: E402
import p2_report as RP  # noqa: E402
import p2_series as S  # noqa: E402
import p2_tables as T  # noqa: E402

_OVERFLOW_CELL = "1" + "0" * 400  # numeric-looking, but `float()` returns `inf` without raising


def test_printed_price_cells_parse_exactly_as_before():
    """The string arm is unchanged: `$`, thousands separators and `()`-negatives still normalise."""
    assert T._num("1,521") == 1521.0
    assert T._num("$17.6") == 17.6
    assert T._num("(250)") == -250.0
    assert T._num(12.5) == 12.5
    assert T._num(1521) == 1521.0
    assert T._num(None) is None
    assert T._num("") is None
    assert T._num("n/a") is None


def test_a_bool_or_non_finite_price_cell_is_not_a_price():
    """`isinstance(True, int)` is True, so `float(v)` booked a `true` cell as a `$1` sale price.

    That value does not stay local: it becomes the claim's `price_val`, its dedupe key and the
    number the D9 clusterer groups on, so a fabricated `$1` outlives the read that invented it.
    `nan` is worse - it is not equal to itself, so a `price_val` of `nan` silently fails every
    downstream equality check instead of raising. Live sidecars hold 0 bool and 0 NaN among 176,043
    price cells, i.e. this closes a latent fabrication rather than an observed one.
    """
    for bad in (True, False, float("nan"), float("inf"), float("-inf"), [], {}, object()):
        assert T._num(bad) is None, bad


def test_an_overflowing_printed_cell_is_not_a_price():
    """Every printed-cell parser must reject a *numeric-looking* cell that overflows to `inf`.

    `float("1" + "0"*400)` does not raise, so a 400-digit cell (a typo, or a unit error) enters the
    money path as an infinite price. Each parser owns its own copy of this read; all three are pinned
    here because fixing one and missing another would leave the same fabrication reachable by a
    different caller.
    """
    assert S.to_number(_OVERFLOW_CELL) is None
    assert RP.to_number(_OVERFLOW_CELL) is None
    assert K.to_number(_OVERFLOW_CELL) is None
    # the literal `"inf"` spellings, which reach `float()` directly rather than via digits
    for parser in (S.to_number, RP.to_number, K.to_number):
        for spelling in ("inf", "-inf", "Infinity"):
            assert parser(spelling) is None, (parser, spelling)
    # and the ordinary cells still parse, so the guard is not a blanket rejection
    assert S.to_number("1,521") == 1521.0
    assert RP.to_number("$17.6") == 17.6
    assert K.to_number("12.5") == 12.5
