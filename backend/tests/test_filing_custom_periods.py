"""G-03a-T12 — custom (out-of-cycle) periods: 1 Jan–15 Mar then quarters from 16 Mar; a custom
period may not overlap a filed one; a crossing open period is cut to a stub; deleting an unfiled
custom period regenerates the regular periods."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.tax.filing_service import add_custom_period, delete_custom_period, switch_frequency
from numo9.tax.models import FilingPeriod, PeriodStatus, TaxError
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

pytestmark = pytest.mark.django_db
day = dt.date
TODAY = day(2026, 6, 1)


def quarterly() -> Any:
    start = day(2027, 1, 1)
    reg = registration(start=start, stop=day(2027, 12, 31))
    switch_frequency(reg, "quarterly", start, today=TODAY)
    return reg


def spans(periods: list[FilingPeriod]) -> list[tuple[str, str, str]]:
    return [(p.start.isoformat(), p.end.isoformat(), p.kind) for p in periods]


def test_stub_then_quarters_from_the_next_day() -> None:
    reg = quarterly()
    periods = add_custom_period(
        reg, day(2027, 1, 1), day(2027, 3, 15), note="FY change", today=TODAY
    )
    assert spans(periods) == [
        ("2027-01-01", "2027-03-15", "custom"),
        ("2027-03-16", "2027-06-15", "regular"),
        ("2027-06-16", "2027-09-15", "regular"),
        ("2027-09-16", "2027-12-15", "regular"),
        ("2027-12-16", "2027-12-31", "stub"),
    ]
    assert [p.sequence_no for p in periods] == [1, 2, 3, 4, 5]
    assert periods[0].due_date == day(2027, 4, 15) and periods[0].note == "FY change"


def test_crossing_period_is_cut_and_filed_ones_refuse() -> None:
    reg = quarterly()
    periods = add_custom_period(reg, day(2027, 2, 10), day(2027, 4, 30), today=TODAY)
    assert spans(periods)[:3] == [
        ("2027-01-01", "2027-02-09", "stub"),
        ("2027-02-10", "2027-04-30", "custom"),
        ("2027-05-01", "2027-07-31", "regular"),
    ]
    with org_context(reg.organisation):
        first = FilingPeriod.objects.filter(registration=reg).order_by("start").first()
        assert first is not None
        first.status = PeriodStatus.FILED
        first.save()
    with pytest.raises(TaxError) as error:
        add_custom_period(reg, day(2027, 1, 15), day(2027, 1, 31), today=TODAY)
    assert error.value.code == "tax.filing.custom_overlaps_filed"
    with pytest.raises(TaxError) as error:
        add_custom_period(reg, day(2027, 4, 1), day(2027, 5, 31), today=TODAY)
    assert error.value.code == "tax.filing.custom_overlap"


def test_deleting_a_custom_period_regenerates() -> None:
    reg = quarterly()
    periods = add_custom_period(reg, day(2027, 1, 1), day(2027, 3, 15), today=TODAY)
    after = delete_custom_period(periods[0], today=TODAY)
    assert spans(after)[:2] == [
        ("2027-01-01", "2027-03-31", "regular"),
        ("2027-04-01", "2027-06-30", "regular"),
    ]
