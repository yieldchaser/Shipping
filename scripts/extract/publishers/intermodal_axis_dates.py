"""intermodal x-axis dates: the labels are OUTLINED VECTOR GLYPHS, not text.

Measured 2026 W35: `page.get_text()` over the x-axis band returns only
'Average T/C Rates' - the twelve date labels are drawn as filled paths, so there is no
text to read. The rendered crop shows them as 30/Sep/25 ... 31/Aug/26, month-end
labels rotated 45 degrees, twelve of them.

So the dates are DERIVED from the window's structure, and the structure is verified
against the render rather than assumed:

  - the x axis spans a rolling TWELVE month-ENDs, ending at the last month-end on or
    before the report date;
  - the report date is the Friday of the ISO week in the filename (intermodal publishes
    weekly, and the assessment date is already parsed by intermodal_v2 from the printed
    table header, which is the better source - this module is given it, not guessed).

Verification: for report 2026 W35 the Friday is 2026-08-28, the last month-end on or
before it is 2026-08-31, and twelve month-ends back is 2025-09-30. That is exactly what
the rendered axis reads.
"""
from __future__ import annotations

import calendar
import datetime as dt


def month_end(y: int, m: int) -> dt.date:
    return dt.date(y, m, calendar.monthrange(y, m)[1])


def window(report_date):
    """The twelve month-end dates on the x axis, oldest first.

    The axis ENDS AT THE REPORT'S OWN MONTH, even when the report is published earlier in
    that month. Measured: the 2026 W35 report is dated 28 Aug 2026 and the rendered axis
    reads 30/Sep/25 ... 31/Aug/26.

    A report published on the 5th of a month still charts that whole month, so the window
    is anchored on the report's month, not on the day. An earlier version ended at the
    last month-end on or BEFORE the report date, which produced 31/Aug/25 ... 31/Jul/26:
    right in shape, one month short at both ends, and only the render showed it.

    Returns [] if the input is not a usable date, so a caller can fall back rather than
    emit invented dates.
    """
    if isinstance(report_date, str):
        try:
            report_date = dt.date.fromisoformat(report_date)
        except ValueError:
            return []
    if not isinstance(report_date, dt.date):
        return []
    end = month_end(report_date.year, report_date.month)
    out = [end]
    for _ in range(11):
        d = out[0]
        y, m = (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
        out.insert(0, month_end(y, m))
    return out


def to_label(d: dt.date) -> str:
    """The publisher's own label shape: '30/Sep/25', '31/Aug/26'."""
    mon = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.month]
    return f"{d.day:02d}/{mon}/{d.year % 100:02d}"


def verify(report_date):
    """The window as publisher-style labels, for checking against a render."""
    return [to_label(d) for d in window(report_date)]


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        print(arg, "->", verify(arg))
    # the case that established the rule
    print("2026-08-28 ->", verify("2026-08-28"))
