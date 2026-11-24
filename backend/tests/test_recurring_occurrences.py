"""C-04-T05 — recurrence generator: dateutil rules with the month-end clamp.

Acceptance: 31 Jan monthly → 28/29 Feb, 31 Mar (never a skipped month); property tests: every
date is on or after the start, strictly increasing, one per period for monthly rules, on the
start's day or the month's last day when shorter; ``after`` / ``until`` / ``limit`` cut the list.
"""

from __future__ import annotations

import calendar
import datetime as dt

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from numo9.ledger.recurring import occurrences

D = dt.date


def test_31_january_monthly_clamps_to_the_month_end() -> None:
    assert occurrences("FREQ=MONTHLY", D(2026, 1, 31), limit=5) == [
        D(2026, 1, 31),
        D(2026, 2, 28),
        D(2026, 3, 31),
        D(2026, 4, 30),
        D(2026, 5, 31),
    ]
    # Leap year: 29 February.
    assert occurrences("FREQ=MONTHLY", D(2028, 1, 31), limit=2)[1] == D(2028, 2, 29)


def test_30th_and_29th_clamp_in_february_and_come_back() -> None:
    assert occurrences("FREQ=MONTHLY", D(2026, 1, 30), limit=3) == [
        D(2026, 1, 30),
        D(2026, 2, 28),
        D(2026, 3, 30),
    ]
    assert occurrences("FREQ=MONTHLY;INTERVAL=1", D(2026, 1, 29), limit=2)[1] == D(2026, 2, 28)


def test_quarterly_yearly_weekly_daily() -> None:
    assert occurrences("FREQ=MONTHLY;INTERVAL=3", D(2026, 1, 31), limit=4) == [
        D(2026, 1, 31),
        D(2026, 4, 30),
        D(2026, 7, 31),
        D(2026, 10, 31),
    ]
    assert occurrences("FREQ=YEARLY", D(2024, 2, 29), limit=3) == [
        D(2024, 2, 29),
        D(2025, 2, 28),
        D(2026, 2, 28),
    ]
    assert occurrences("FREQ=WEEKLY;BYDAY=FR", D(2026, 6, 1), limit=2) == [
        D(2026, 6, 5),
        D(2026, 6, 12),
    ]
    assert occurrences("FREQ=DAILY;INTERVAL=10", D(2026, 6, 1), limit=3) == [
        D(2026, 6, 1),
        D(2026, 6, 11),
        D(2026, 6, 21),
    ]


def test_rules_with_their_own_day_are_left_alone() -> None:
    # BYMONTHDAY=-1: the last day of every month, from the rule itself.
    assert occurrences("FREQ=MONTHLY;BYMONTHDAY=-1", D(2026, 1, 15), limit=3) == [
        D(2026, 1, 31),
        D(2026, 2, 28),
        D(2026, 3, 31),
    ]


def test_end_after_until_limit_count() -> None:
    rule, start = "FREQ=MONTHLY", D(2026, 1, 31)
    assert occurrences(rule, start, D(2026, 3, 31)) == [
        D(2026, 1, 31),
        D(2026, 2, 28),
        D(2026, 3, 31),
    ]
    assert occurrences(rule, start, D(2026, 3, 30)) == [D(2026, 1, 31), D(2026, 2, 28)]
    assert occurrences(rule, start, after=D(2026, 2, 28), limit=2) == [
        D(2026, 3, 31),
        D(2026, 4, 30),
    ]
    assert occurrences(rule, start, until=D(2026, 2, 28)) == [D(2026, 1, 31), D(2026, 2, 28)]
    assert occurrences("FREQ=MONTHLY;COUNT=2", start) == [D(2026, 1, 31), D(2026, 2, 28)]
    assert occurrences("FREQ=MONTHLY;UNTIL=20260415", start) == [
        D(2026, 1, 31),
        D(2026, 2, 28),
        D(2026, 3, 31),
    ]


@settings(max_examples=150, deadline=None)
@given(
    start=st.dates(min_value=D(2000, 1, 1), max_value=D(2090, 12, 31)),
    interval=st.integers(min_value=1, max_value=12),
    count=st.integers(min_value=1, max_value=30),
)
def test_monthly_property(start: dt.date, interval: int, count: int) -> None:
    dates = occurrences(f"FREQ=MONTHLY;INTERVAL={interval}", start, limit=count)
    assert len(dates) == count
    assert dates[0] == start
    assert all(a < b for a, b in zip(dates, dates[1:], strict=False))
    for n, day in enumerate(dates):
        months = start.year * 12 + start.month - 1 + n * interval
        assert (day.year, day.month) == (months // 12, months % 12 + 1)  # one per period
        last = calendar.monthrange(day.year, day.month)[1]
        assert day.day == min(start.day, last)


@settings(max_examples=80, deadline=None)
@given(
    start=st.dates(min_value=D(2000, 1, 1), max_value=D(2090, 12, 31)),
    freq=st.sampled_from(["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]),
    after_days=st.integers(min_value=0, max_value=800),
)
def test_after_is_strict_and_dates_never_precede_start(
    start: dt.date, freq: str, after_days: int
) -> None:
    after = start + dt.timedelta(days=after_days)
    dates = occurrences(f"FREQ={freq}", start, after=after, limit=5)
    assert dates and all(day > after and day >= start for day in dates)


@pytest.mark.parametrize("rule", ["FREQ=MONTHLY", "FREQ=YEARLY"])
def test_limit_is_capped(rule: str) -> None:
    assert len(occurrences(rule, D(2000, 1, 31), limit=5000)) == 1000
