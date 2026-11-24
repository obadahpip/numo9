"""G-03a-T07 — the pure period generator: quarterly with a 31 Dec year end gives Jan–Mar,
Apr–Jun…; fiscal quarters for a 31 Mar year end; stubs for a mid-period start or switch;
custom periods realign the regular ones; no gaps, no overlaps."""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.tax.filing import Cycle, Period, Span, generate_periods

day = dt.date


def spans(periods: list[Period]) -> list[tuple[str, str, str]]:
    return [(p.start.isoformat(), p.end.isoformat(), p.kind) for p in periods]


def covered(periods: list[Period], start: dt.date, end: dt.date) -> None:
    assert periods[0].start == start and periods[-1].end == end
    for a, b in zip(periods, periods[1:], strict=False):
        assert b.start == a.end + dt.timedelta(days=1)


def test_quarterly_calendar_year() -> None:
    periods = generate_periods(
        [Cycle("quarterly", day(2026, 1, 1))], 12, 31, day(2026, 1, 1), day(2026, 12, 31)
    )
    assert spans(periods) == [
        ("2026-01-01", "2026-03-31", "regular"),
        ("2026-04-01", "2026-06-30", "regular"),
        ("2026-07-01", "2026-09-30", "regular"),
        ("2026-10-01", "2026-12-31", "regular"),
    ]


def test_fiscal_quarters_and_years_for_a_31_march_year_end() -> None:
    q = generate_periods(
        [Cycle("quarterly", day(2026, 1, 1))], 3, 31, day(2026, 1, 1), day(2026, 12, 31)
    )
    assert spans(q)[:2] == [
        ("2026-01-01", "2026-03-31", "regular"),
        ("2026-04-01", "2026-06-30", "regular"),
    ]
    a = generate_periods(
        [Cycle("annual", day(2026, 4, 1))], 3, 31, day(2026, 4, 1), day(2028, 3, 31)
    )
    assert spans(a) == [
        ("2026-04-01", "2027-03-31", "regular"),
        ("2027-04-01", "2028-03-31", "regular"),
    ]


def test_registration_starting_mid_month_and_monthly_february() -> None:
    periods = generate_periods(
        [Cycle("monthly", day(2028, 1, 15))], 12, 31, day(2028, 1, 15), day(2028, 3, 31)
    )
    assert spans(periods) == [
        ("2028-01-15", "2028-01-31", "stub"),
        ("2028-02-01", "2028-02-29", "regular"),  # leap year
        ("2028-03-01", "2028-03-31", "regular"),
    ]


def test_annual_to_quarterly_mid_year_and_a_switch_back() -> None:
    cycles = [
        Cycle("annual", day(2026, 1, 1)),
        Cycle("quarterly", day(2026, 8, 15)),
        Cycle("annual", day(2027, 1, 1)),
    ]
    periods = generate_periods(cycles, 12, 31, day(2026, 1, 1), day(2027, 12, 31))
    assert spans(periods) == [
        ("2026-01-01", "2026-08-14", "stub"),
        ("2026-08-15", "2026-09-30", "stub"),
        ("2026-10-01", "2026-12-31", "regular"),
        ("2027-01-01", "2027-12-31", "regular"),
    ]
    assert [p.frequency for p in periods] == ["annual", "quarterly", "quarterly", "annual"]


def test_custom_period_realigns_the_regular_ones() -> None:
    periods = generate_periods(
        [Cycle("quarterly", day(2027, 1, 1))],
        12,
        31,
        day(2027, 1, 1),
        day(2027, 12, 31),
        custom=[Span(day(2027, 1, 1), day(2027, 3, 15))],
    )
    assert spans(periods) == [
        ("2027-01-01", "2027-03-15", "custom"),
        ("2027-03-16", "2027-06-15", "regular"),
        ("2027-06-16", "2027-09-15", "regular"),
        ("2027-09-16", "2027-12-15", "regular"),
        ("2027-12-16", "2027-12-31", "stub"),
    ]
    covered(periods, day(2027, 1, 1), day(2027, 12, 31))


def test_invalid_input() -> None:
    with pytest.raises(ValueError):
        generate_periods([], 12, 31, day(2026, 1, 1), day(2026, 12, 31))
    with pytest.raises(ValueError):
        generate_periods(
            [Cycle("monthly", day(2026, 1, 1))],
            12,
            31,
            day(2026, 1, 1),
            day(2026, 12, 31),
            custom=[Span(day(2026, 2, 1), day(2026, 3, 1)), Span(day(2026, 3, 1), day(2026, 4, 1))],
        )
