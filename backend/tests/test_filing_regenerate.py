"""G-03a-T10 — regeneration: quarterly → monthly from 1 Jul keeps the filed Q1/Q2 untouched and
makes Jul…Dec; a switch inside an open period splits it; custom periods and filed periods are
kept; periods are renumbered and dated."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.tax.filing_service import regenerate
from numo9.tax.models import FilingCycle, FilingPeriod, PeriodStatus
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

pytestmark = pytest.mark.django_db
day = dt.date
TODAY = day(2026, 6, 1)


def cycle(reg: Any, frequency: str, start: dt.date, **fields: Any) -> None:
    with org_context(reg.organisation):
        FilingCycle.objects.create(
            organisation=reg.organisation,
            registration=reg,
            frequency=frequency,
            effective_from=start,
            **fields,
        )


def rows(reg: Any) -> list[tuple[str, str, str, int]]:
    with org_context(reg.organisation):
        return [
            (p.start.isoformat(), p.end.isoformat(), p.kind, p.sequence_no)
            for p in FilingPeriod.objects.filter(registration=reg).order_by("start")
        ]


def test_quarterly_to_monthly_keeps_filed_quarters() -> None:
    reg = registration(stop=day(2026, 12, 31))
    cycle(reg, "quarterly", day(2026, 1, 1))
    periods = regenerate(reg, today=TODAY)
    assert [(p.start, p.end) for p in periods][:2] == [
        (day(2026, 1, 1), day(2026, 3, 31)),
        (day(2026, 4, 1), day(2026, 6, 30)),
    ]
    assert periods[2].due_date == day(2026, 11, 2)  # Q3: 31 Oct is a Saturday
    assert [p.status for p in periods] == ["closed", "open", "open", "open"]
    with org_context(reg.organisation):
        filed = list(FilingPeriod.objects.filter(registration=reg).order_by("start")[:2])
        for p in filed:
            p.status = PeriodStatus.FILED
            p.save()
    cycle(reg, "monthly", day(2026, 7, 1), approval_ref="2026-GST-48812")
    regenerate(reg, day(2026, 7, 1), today=TODAY)
    after = rows(reg)
    assert after[:2] == [
        ("2026-01-01", "2026-03-31", "regular", 1),
        ("2026-04-01", "2026-06-30", "regular", 2),
    ]
    ends = ["07-31", "08-31", "09-30", "10-31", "11-30", "12-31"]
    assert [r[:2] for r in after[2:]] == [
        (f"2026-{m:02d}-01", f"2026-{end}") for m, end in zip(range(7, 13), ends, strict=True)
    ]
    with org_context(reg.organisation):
        kept = FilingPeriod.objects.filter(registration=reg).order_by("start")[:2]
        assert [p.pk for p in kept] == [p.pk for p in filed]


def test_switch_inside_an_open_period_splits_it() -> None:
    reg = registration(stop=day(2026, 12, 31))
    cycle(reg, "quarterly", day(2026, 1, 1))
    regenerate(reg, today=TODAY)
    cycle(reg, "monthly", day(2026, 8, 15), approval_ref="X-1")
    regenerate(reg, day(2026, 8, 15), today=TODAY)
    after = rows(reg)
    assert after[2:5] == [
        ("2026-07-01", "2026-08-14", "stub", 3),
        ("2026-08-15", "2026-08-31", "stub", 4),
        ("2026-09-01", "2026-09-30", "regular", 5),
    ]
    assert after[-1][:2] == ("2026-12-01", "2026-12-31")


def test_registration_needs_a_cycle_and_a_start() -> None:
    from numo9.tax.models import TaxError

    reg = registration()
    with pytest.raises(TaxError):
        regenerate(reg, today=TODAY)
    no_start = registration("No Start Ltd.", start=None)
    cycle(no_start, "monthly", day(2026, 1, 1))
    with pytest.raises(TaxError):
        regenerate(no_start, today=TODAY)


def test_open_ended_registration_runs_24_months_ahead() -> None:
    reg = registration()
    cycle(reg, "monthly", day(2026, 1, 1))
    periods = regenerate(reg, today=TODAY)
    assert periods[-1].end == day(2028, 6, 30)
    assert len(periods) == 30
