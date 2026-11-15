"""Money rendering for owner-facing reports.

Design note (D21, Defect-17 class, third instance):

Two states must never look alike in a report the owner reads:

    None      -> the amount could not be measured (ledger missing/locked)
    0.0       -> the amount *was* measured, and it is exactly zero

`p7_report` and `p6_summary` already keep those apart. What broke next was a third state hiding
inside the second: a real, nonzero, *tiny* spend that a fixed `:.4f` renders as the string
`$0.0000`. P6's whole phase spend is `$0.000013` and a single P7 judge call is `$0.000019`; both
printed as `$0.0000`, i.e. "free" — the same false claim as an unreadable ledger, arriving from the
other direction. `f"{v:.4f}"` cannot express "not zero", so the renderer must widen the decimals
until the value is visible instead of silently flattening it.

`fmt_usd` therefore promotes the decimal places only when 4 dp would hide a nonzero value, and
returns `$0.0000` *only* for a measured exact zero.
"""
from __future__ import annotations

MAX_PLACES = 9


def fmt_usd(v, places: int = 4, unmeasured: str = "UNMEASURED") -> str:
    """Render a spend amount without ever flattening a nonzero value to `$0.0000`.

    None/NaN  -> `UNMEASURED` (not measured — must not read as a measurement)
    exact 0.0 -> `$0.0000` (measured zero — legitimately free)
    otherwise -> `$X.XXXX`, widened to more decimals if 4 dp would round it away
    """
    if v is None:
        return unmeasured
    try:
        f = float(v)
    except (TypeError, ValueError):
        return unmeasured
    if f != f:  # NaN: a broken measurement, not a zero
        return unmeasured
    if f == 0.0:
        return f"${0.0:.{places}f}"
    for p in range(places, MAX_PLACES + 1):
        s = f"{f:.{p}f}"
        if float(s) != 0.0:
            return f"${s}"
    return f"${f:.3e}"


def round_usd(v, places: int = 6) -> float | None:
    """Round a spend for storage without laundering a nonzero value into a measured `0.0`.

    Kept separate from `fmt_usd` because a report field can be rounded to zero *before* it is ever
    rendered — that is how p7_report first lost a tiny spend: `round(1.3e-05, 4) == 0.0`.
    """
    if v is None:
        return None
    return round(float(v), places)
