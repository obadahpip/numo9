"""G-03a-T09 — an annual filer gets four quarterly instalment dates (one month after each fiscal
quarter end, rolled), amounts left for G-09; other frequencies get none."""

from __future__ import annotations

import datetime as dt

from numo9.tax.filing import Period, instalments

day = dt.date


def test_annual_filer_gets_four_instalments() -> None:
    year = Period(day(2026, 1, 1), day(2026, 12, 31), "regular", "annual")
    dates = instalments(year)
    assert [i.due_date for i in dates] == [
        day(2026, 4, 30),
        day(2026, 7, 31),
        day(2026, 11, 2),  # 31 Oct 2026 is a Saturday
        day(2027, 2, 1),  # 31 Jan 2027 is a Sunday
    ]
    assert [i.quarter_end for i in dates][-1] == day(2026, 12, 31)
    assert all(i.amount is None for i in dates)


def test_fiscal_year_ending_31_march() -> None:
    year = Period(day(2026, 4, 1), day(2027, 3, 31), "regular", "annual")
    assert [i.due_date for i in instalments(year)] == [
        day(2026, 7, 31),
        day(2026, 11, 2),  # quarter to 30 Sep: 31 Oct is a Saturday
        day(2027, 2, 1),  # quarter to 31 Dec: 31 Jan is a Sunday
        day(2027, 4, 30),
    ]


def test_quarterly_filers_have_none() -> None:
    assert instalments(Period(day(2026, 1, 1), day(2026, 3, 31), "regular", "quarterly")) == []
