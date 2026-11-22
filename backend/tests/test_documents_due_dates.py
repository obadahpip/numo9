"""D-01-T07 — due dates from payment terms: Net N, EOM, day of next month, day of current month,
2/10 net 30 — including month ends and leap years."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from numo9.contacts.models import PaymentTerm
from numo9.documents.due_dates import document_terms, due_date, due_in, resolve
from numo9.orgsettings.models import TermsType
from numo9.orgsettings.service import get_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

T = TermsType
D = dt.date


@pytest.mark.parametrize(
    ("date", "kind", "days", "due"),
    [
        (D(2026, 7, 15), T.DAYS_AFTER_DOCUMENT, 30, D(2026, 8, 14)),
        (D(2026, 7, 15), T.DAYS_AFTER_DOCUMENT, 0, D(2026, 7, 15)),  # due on receipt
        (D(2026, 12, 15), T.DAYS_AFTER_DOCUMENT, 30, D(2027, 1, 14)),
        (D(2026, 1, 31), T.DAYS_AFTER_DOCUMENT, 30, D(2026, 3, 2)),
        (D(2026, 7, 15), T.DAYS_AFTER_MONTH_END, 0, D(2026, 7, 31)),  # EOM
        (D(2026, 2, 3), T.DAYS_AFTER_MONTH_END, 0, D(2026, 2, 28)),
        (D(2028, 2, 3), T.DAYS_AFTER_MONTH_END, 0, D(2028, 2, 29)),  # leap year
        (D(2026, 7, 15), T.DAYS_AFTER_MONTH_END, 15, D(2026, 8, 15)),
        (D(2026, 12, 1), T.DAYS_AFTER_MONTH_END, 1, D(2027, 1, 1)),
        (D(2026, 7, 15), T.DAY_OF_FOLLOWING_MONTH, 20, D(2026, 8, 20)),
        (D(2026, 1, 15), T.DAY_OF_FOLLOWING_MONTH, 31, D(2026, 2, 28)),
        (D(2028, 1, 15), T.DAY_OF_FOLLOWING_MONTH, 30, D(2028, 2, 29)),
        (D(2026, 12, 15), T.DAY_OF_FOLLOWING_MONTH, 5, D(2027, 1, 5)),
        (D(2026, 7, 5), T.DAY_OF_CURRENT_MONTH, 20, D(2026, 7, 20)),
        (D(2026, 7, 25), T.DAY_OF_CURRENT_MONTH, 20, D(2026, 8, 20)),  # day passed → next month
        (D(2026, 7, 20), T.DAY_OF_CURRENT_MONTH, 20, D(2026, 7, 20)),
        (D(2026, 4, 10), T.DAY_OF_CURRENT_MONTH, 31, D(2026, 4, 30)),
        (D(2026, 12, 28), T.DAY_OF_CURRENT_MONTH, 15, D(2027, 1, 15)),
    ],
)
def test_term_types(date: dt.date, kind: str, days: int, due: dt.date) -> None:
    assert due_date(date, kind, days) == due


def test_two_ten_net_thirty() -> None:
    term = PaymentTerm(
        terms_type=T.DAYS_AFTER_DOCUMENT, days=30, discount_pct=Decimal("2"), discount_days=10
    )
    result = resolve(D(2026, 7, 15), term)
    assert (result.due, result.discount_until, result.discount_pct) == (
        D(2026, 8, 14),
        D(2026, 7, 25),
        Decimal("2"),
    )
    assert resolve(D(2026, 7, 15), PaymentTerm(days=15)).discount_until is None
    assert due_in(D(2026, 7, 15), result.due) == 30


def test_bad_input() -> None:
    with pytest.raises(ValueError):
        due_date(D(2026, 1, 1), "fortnightly", 1)
    with pytest.raises(ValueError):
        due_date(D(2026, 1, 1), T.DAYS_AFTER_DOCUMENT, -1)


def month_end(day: dt.date) -> dt.date:
    return (day.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)


dates = st.dates(min_value=D(2000, 1, 1), max_value=D(2099, 12, 31))


@settings(max_examples=400, deadline=None)
@given(date=dates, kind=st.sampled_from(list(T.values)), days=st.integers(0, 31))
def test_due_date_is_never_before_the_document_date(date: dt.date, kind: str, days: int) -> None:
    due = due_date(date, kind, days)
    assert due >= date
    if kind == T.DAY_OF_FOLLOWING_MONTH:
        assert (due.year * 12 + due.month) - (date.year * 12 + date.month) == 1
    if kind in (T.DAY_OF_FOLLOWING_MONTH, T.DAY_OF_CURRENT_MONTH) and days:
        assert due.day == min(
            days,
            (due.replace(day=28) + dt.timedelta(days=4))
            .replace(day=1)
            .__sub__(dt.timedelta(days=1))
            .day,
        )
    if kind == T.DAYS_AFTER_MONTH_END:
        assert due == month_end(date) + dt.timedelta(days=days)


@settings(max_examples=200, deadline=None)
@given(date=dates, days=st.integers(0, 365))
def test_net_n_is_n_days(date: dt.date, days: int) -> None:
    assert due_in(date, due_date(date, T.DAYS_AFTER_DOCUMENT, days)) == days


@pytest.mark.django_db
def test_document_terms_contact_then_organisation() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        settings_ = get_settings(org)
        settings_.sales_terms_type = T.DAY_OF_FOLLOWING_MONTH
        settings_.sales_terms_days = 20
        settings_.save()
        net15 = PaymentTerm.objects.get(code="net_15")
        plain = contact(org, "Walk-in")
        regular = contact(org, "Maple Café", sales_payment_term=net15)
        assert (
            document_terms("sales", plain, org).terms_type,
            document_terms("sales", plain, org).days,
        ) == (
            T.DAY_OF_FOLLOWING_MONTH,
            20,
        )
        terms = document_terms("sales", regular, org)
        assert (terms.term, terms.days) == (net15, 15)
        assert document_terms("purchase", regular, org).term is None
        assert document_terms("sales", None, org).days == 20
        net15.status = "archived"
        net15.save()
        regular.refresh_from_db()
        assert document_terms("sales", regular, org).term is None
