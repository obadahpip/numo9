"""B-02-T04 — statement engine (outstanding and activity, opening balance, aging buckets).

Acceptance: total = sum of the open items (the AR aging basis). Outstanding: open items as at the
date oldest first with running balances, aging by days past due; activity: opening balance from
everything before the start, documents and payments in the range, closing balance = amount due.
Property (Hypothesis): for random documents and payments, the activity statement's closing balance
equals the outstanding statement's total at the same date, and the aging buckets add up to it.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.contacts import subledger
from numo9.contacts.models import Contact
from numo9.contacts.statement_engine import build_statement, statement_due
from numo9.contacts.subledger import FixtureDocument, FixtureSource
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db
D, day = Decimal, dt.date


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


@pytest.fixture
def source() -> Iterator[FixtureSource]:
    made = FixtureSource("receivables")
    subledger.register_source(made)
    yield made
    subledger.unregister_source(made)


def test_outstanding_and_activity(org: Organisation, source: FixtureSource) -> None:
    maple = contact(org, "Maple Leaf Supply Ltd.")
    source.add(
        FixtureDocument(
            maple.pk,
            "INV-1",
            day(2026, 1, 10),
            D("500.00"),
            day(2026, 2, 9),
            payments=[(day(2026, 3, 10), D("200.00"), "PMT-1")],
        )
    )
    source.add(FixtureDocument(maple.pk, "INV-2", day(2026, 3, 5), D("120.00"), day(2026, 4, 4)))
    as_at = day(2026, 3, 31)

    outstanding = build_statement(maple, "outstanding", as_at)
    assert [(line.document, line.amount, line.balance) for line in outstanding.lines] == [
        ("INV-1", D("300.00"), D("300.00")),
        ("INV-2", D("120.00"), D("420.00")),
    ]
    assert outstanding.amount_due == D("420.00") == outstanding.total()
    assert outstanding.aging["days_31_60"] == D("300.00")  # 50 days past due
    assert outstanding.aging["current"] == D("120.00")
    assert outstanding.contact.legal_name == "Maple Leaf Supply Ltd."

    activity = build_statement(maple, "activity", as_at, start=day(2026, 3, 1))
    assert activity.opening_balance == D("500.00")
    assert [(line.document, line.balance) for line in activity.lines] == [
        ("INV-2", D("620.00")),
        ("PMT-1", D("420.00")),
    ]
    assert activity.amount_due == outstanding.amount_due
    assert statement_due(maple, as_at) is True
    with pytest.raises(ValueError, match="start"):
        build_statement(maple, "activity", as_at)


documents = st.lists(
    st.tuples(
        st.integers(min_value=0, max_value=80),  # day offset
        st.integers(min_value=-5000, max_value=50_000),  # cents (negative = credit note)
        st.integers(min_value=0, max_value=60),  # terms
        st.lists(st.tuples(st.integers(0, 90), st.integers(0, 50_000)), max_size=3),  # payments
    ),
    max_size=8,
)


@settings(
    max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(docs=documents, cut=st.integers(min_value=0, max_value=100))
def test_property_activity_closing_equals_outstanding_total(
    org: Organisation, source: FixtureSource, docs: list[Any], cut: int
) -> None:
    source.documents.clear()
    maple = Contact.objects.filter(display_name="Maple Leaf Supply Ltd.").first() or contact(
        org, "Maple Leaf Supply Ltd."
    )
    base = day(2026, 1, 1)
    for n, (offset, cents, terms, payments) in enumerate(docs):
        start = base + dt.timedelta(days=offset)
        source.add(
            FixtureDocument(
                maple.pk,
                f"INV-{n}",
                start,
                D(cents) / 100,
                start + dt.timedelta(days=terms),
                payments=[
                    (start + dt.timedelta(days=p), D(c) / 100, f"PMT-{n}-{i}")
                    for i, (p, c) in enumerate(payments)
                ],
            )
        )
    as_at = base + dt.timedelta(days=cut)
    outstanding = build_statement(maple, "outstanding", as_at)
    activity = build_statement(maple, "activity", as_at, start=base + dt.timedelta(days=cut // 2))
    assert activity.amount_due == outstanding.amount_due == outstanding.total()
    assert sum(outstanding.aging.values(), D("0")) == outstanding.amount_due
