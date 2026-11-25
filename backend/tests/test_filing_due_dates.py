"""G-03a-T08 — due dates: monthly and quarterly one month after the end (month end to month end),
annual three months, an individual's 15 June / 30 April rule from the data, the holiday roll."""

from __future__ import annotations

import datetime as dt

from numo9.tax.filing import due_dates

day = dt.date


def test_quarterly_and_monthly() -> None:
    # Q3 2026 ends 30 Sep: due 31 Oct 2026, a Saturday → Monday 2 Nov.
    assert due_dates(day(2026, 9, 30), "quarterly", rolled=False) == (day(2026, 10, 31),) * 2
    assert due_dates(day(2026, 9, 30), "quarterly") == (day(2026, 11, 2),) * 2
    assert due_dates(day(2026, 2, 28), "monthly") == (day(2026, 3, 31),) * 2
    assert due_dates(day(2026, 1, 31), "monthly", rolled=False) == (day(2026, 2, 28),) * 2
    # A realigned period ending mid-month: one month later, same day.
    assert due_dates(day(2027, 6, 15), "quarterly") == (day(2027, 7, 15),) * 2


def test_annual() -> None:
    assert due_dates(day(2026, 12, 31), "annual") == (day(2027, 3, 31),) * 2
    assert due_dates(day(2027, 3, 31), "annual", fye=(3, 31)) == (day(2027, 6, 30),) * 2
    assert due_dates(day(2026, 12, 31), "annual", structure="sole_proprietorship") == (
        day(2027, 6, 15),
        day(2027, 4, 30),
    )
    # The individual rule is for a 31 Dec year end only.
    assert (
        due_dates(day(2027, 3, 31), "annual", structure="sole_proprietorship", fye=(3, 31))
        == (day(2027, 6, 30),) * 2
    )


def test_qst_rolls_on_quebec_holidays() -> None:
    # A period ending 24 May 2026 is due 24 Jun 2026 (Fête nationale) → 25 Jun for QST.
    assert due_dates(day(2026, 5, 24), "monthly")[0] == day(2026, 6, 24)
    assert due_dates(day(2026, 5, 24), "monthly", jurisdictions=("CA", "QC"))[0] == day(2026, 6, 25)
