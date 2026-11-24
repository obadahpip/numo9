"""G-03a-T06 — holiday calendar (federal and provincial statutory holidays, 2026 loaded) and the
business-day roll: Saturday → Monday, a long weekend → Tuesday, Quebec's own holidays for QST."""

from __future__ import annotations

import datetime as dt

from numo9.tax.holidays import calendar, jurisdictions_for

day = dt.date


def test_2026_and_2027_are_loaded() -> None:
    cal = calendar()
    assert cal.known(2026) and cal.known(2027) and not cal.known(2031)
    federal = cal.holidays(2026)
    assert federal[day(2026, 7, 1)] == "canada_day"
    assert federal[day(2026, 9, 30)] == "truth_and_reconciliation"
    assert day(2026, 12, 28) in federal  # Boxing Day on a Saturday, observed Monday
    assert len(federal) == 11
    assert cal.holidays(2026, ["QC"])[day(2026, 6, 24)] == "fete_nationale"
    assert day(2026, 2, 16) in cal.holidays(2026, ["ON"])


def test_roll() -> None:
    cal = calendar()
    assert cal.roll(day(2026, 10, 31)) == day(2026, 11, 2)  # Saturday → Monday
    assert cal.roll(day(2026, 11, 30)) == day(2026, 11, 30)  # a business day stays
    assert cal.roll(day(2026, 4, 3)) == day(2026, 4, 7)  # Good Friday, weekend, Easter Monday
    assert cal.roll(day(2026, 12, 25)) == day(2026, 12, 29)
    assert cal.roll(day(2026, 6, 24)) == day(2026, 6, 24)
    assert cal.roll(day(2026, 6, 24), jurisdictions_for("qst")) == day(2026, 6, 25)
    assert cal.roll(day(2031, 1, 4)) == day(2031, 1, 6)  # unknown year: weekends only
