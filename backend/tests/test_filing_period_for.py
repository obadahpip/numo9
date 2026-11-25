"""G-03a-T14 — ``period_for(registration, date)``: every document date of a registration falls
into exactly one period; none before it starts, after it stops, or without a frequency; a date
past the stored periods extends them; boundaries belong to the right side of a switch."""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.tax.filing_service import (
    add_custom_period,
    period_for,
    periods_for,
    switch_frequency,
)
from numo9.tax.models import FilingPeriod
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

pytestmark = pytest.mark.django_db
day = dt.date
TODAY = day(2026, 6, 1)


def test_every_date_has_exactly_one_period() -> None:
    reg = registration(start=day(2026, 1, 15), stop=day(2027, 12, 31))
    switch_frequency(reg, "quarterly", day(2026, 1, 15), today=TODAY)
    switch_frequency(reg, "monthly", day(2026, 7, 1), approval_ref="A-1", today=TODAY)
    add_custom_period(reg, day(2027, 1, 1), day(2027, 3, 15), today=TODAY)
    cursor = day(2026, 1, 15)
    days = []
    while cursor <= day(2027, 12, 31):
        days.append(cursor)
        cursor += dt.timedelta(days=1)
    found = periods_for(reg, days, today=TODAY)
    assert all(p is not None and p.start <= d <= p.end for d, p in found.items())
    with org_context(reg.organisation):
        for probe in (day(2026, 1, 15), day(2026, 6, 30), day(2026, 7, 1), day(2027, 3, 16)):
            rows = FilingPeriod.objects.filter(registration=reg, start__lte=probe, end__gte=probe)
            assert rows.count() == 1 and rows.get() == found[probe]


def test_boundaries_of_a_switch_and_a_custom_period() -> None:
    reg = registration(stop=day(2027, 12, 31))
    switch_frequency(reg, "quarterly", day(2026, 1, 1), today=TODAY)
    switch_frequency(reg, "monthly", day(2026, 7, 1), approval_ref="A-1", today=TODAY)
    add_custom_period(reg, day(2027, 1, 1), day(2027, 3, 15), today=TODAY)

    def span(d: dt.date) -> tuple[dt.date, dt.date, str]:
        period = period_for(reg, d, today=TODAY)
        assert period is not None
        return period.start, period.end, period.kind

    assert span(day(2026, 6, 30)) == (day(2026, 4, 1), day(2026, 6, 30), "regular")
    assert span(day(2026, 7, 1)) == (day(2026, 7, 1), day(2026, 7, 31), "regular")
    assert span(day(2027, 3, 15)) == (day(2027, 1, 1), day(2027, 3, 15), "custom")
    assert span(day(2027, 3, 16)) == (day(2027, 3, 16), day(2027, 4, 15), "regular")


def test_outside_the_registration_there_is_no_period() -> None:
    reg = registration(start=day(2026, 3, 10), stop=day(2026, 12, 31))
    assert period_for(reg, day(2026, 5, 1), today=TODAY) is None  # no frequency yet
    switch_frequency(reg, "quarterly", day(2026, 3, 10), today=TODAY)
    assert period_for(reg, day(2026, 3, 9), today=TODAY) is None
    assert period_for(reg, day(2027, 1, 1), today=TODAY) is None
    first = period_for(reg, day(2026, 3, 10), today=TODAY)
    assert first is not None and (first.start, first.end) == (day(2026, 3, 10), day(2026, 3, 31))
    no_start = registration("No start Ltd.", start=None)
    assert period_for(no_start, day(2026, 5, 1), today=TODAY) is None


def test_a_date_past_the_horizon_extends_the_periods() -> None:
    reg = registration()  # open-ended: periods to 24 months from today
    switch_frequency(reg, "quarterly", day(2026, 1, 1), today=TODAY)
    with org_context(reg.organisation):
        last = FilingPeriod.objects.filter(registration=reg).order_by("-end")[0]
        assert last.end == day(2028, 6, 30)
        far = period_for(reg, day(2030, 2, 14), today=TODAY)
        assert far is not None and (far.start, far.end) == (day(2030, 1, 1), day(2030, 3, 31))
        rows = list(FilingPeriod.objects.filter(registration=reg).order_by("start"))
        assert rows[-1] == far and far.due_date == day(2030, 4, 30)
        for a, b in zip(rows, rows[1:], strict=False):
            assert b.start == a.end + dt.timedelta(days=1)
        assert [p.sequence_no for p in rows] == list(range(1, len(rows) + 1))
        count = len(rows)
        assert period_for(reg, day(2030, 2, 14), today=TODAY) == far  # idempotent
        assert FilingPeriod.objects.filter(registration=reg).count() == count
