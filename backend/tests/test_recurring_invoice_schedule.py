"""D-04-T02 — recurring invoice schedule (the C-04-T05 engine, month-end clamp) + due-date rule."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from numo9.sales import recurring_invoices as schedule

D = dt.date
JAN_31 = D(2026, 1, 31)


def t(
    rule: str = "FREQ=MONTHLY", start: dt.date = JAN_31, end: Any = None, terms: Any = None
) -> Any:
    return SimpleNamespace(
        rrule=rule, start_date=start, end_date=end, terms=terms, contact=None, organisation=None
    )


def test_month_end_clamp_including_february() -> None:
    assert schedule.occurrences(t(), limit=5) == [
        D(2026, 1, 31),
        D(2026, 2, 28),
        D(2026, 3, 31),
        D(2026, 4, 30),
        D(2026, 5, 31),
    ]
    leap = t(start=D(2028, 1, 30))
    assert schedule.occurrences(leap, limit=3) == [D(2028, 1, 30), D(2028, 2, 29), D(2028, 3, 30)]
    assert schedule.occurrences(t(rule="FREQ=YEARLY", start=D(2028, 2, 29)), limit=2) == [
        D(2028, 2, 29),
        D(2029, 2, 28),
    ]


def test_end_date_next_and_first() -> None:
    template = t(end=D(2026, 3, 30))
    assert schedule.occurrences(template) == [D(2026, 1, 31), D(2026, 2, 28)]
    assert schedule.first_run(template) == D(2026, 1, 31)
    assert schedule.next_after(template, D(2026, 2, 28)) is None
    assert schedule.next_after(t(rule="FREQ=WEEKLY", start=D(2026, 3, 2)), D(2026, 3, 2)) == D(
        2026, 3, 9
    )


def test_period_of_an_occurrence() -> None:
    assert schedule.period_of(t(), D(2026, 1, 31)) == (D(2026, 1, 31), D(2026, 2, 27))
    assert schedule.period_of(t(start=D(2026, 1, 1)), D(2026, 2, 1)) == (
        D(2026, 2, 1),
        D(2026, 2, 28),
    )
    assert schedule.period_of(
        t(rule="FREQ=MONTHLY;COUNT=2", start=D(2026, 1, 1)), D(2026, 2, 1)
    ) == (D(2026, 2, 1), D(2026, 2, 28))


@pytest.mark.parametrize(
    ("terms_type", "days", "day", "due"),
    [
        ("days_after_document", 30, D(2026, 1, 31), D(2026, 3, 2)),
        ("days_after_month_end", 0, D(2026, 2, 28), D(2026, 2, 28)),
        ("day_of_following_month", 31, D(2026, 1, 31), D(2026, 2, 28)),
        ("day_of_current_month", 15, D(2026, 2, 28), D(2026, 3, 15)),
    ],
)
def test_due_date_rule(terms_type: str, days: int, day: dt.date, due: dt.date) -> None:
    term = SimpleNamespace(terms_type=terms_type, days=days, discount_pct=0, discount_days=0)
    assert schedule.due_for(t(terms=term), day) == due


def test_invalid_schedule() -> None:
    with pytest.raises(ValidationError):
        schedule.validate_schedule(t(rule="FREQ=SECONDLY"))
    with pytest.raises(ValidationError):
        schedule.validate_schedule(t(end=D(2025, 1, 1)))


@pytest.mark.django_db
def test_default_terms_from_the_organisation() -> None:
    from numo9.tenancy.context import org_context
    from tests.sales_helpers import sales_books

    books = sales_books()
    template = t()
    template.contact, template.organisation = books["customers"]["ON"], books["org"]
    with org_context(books["org"]):
        due = schedule.due_for(template, D(2026, 1, 31))
    assert due >= D(2026, 1, 31)
