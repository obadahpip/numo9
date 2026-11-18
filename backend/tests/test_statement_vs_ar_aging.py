"""B-02-T13 — data validation: a customer's statement total equals that customer's AR aging total.

Activated with D (Phase 1 sales invoices): until then the AR aging side is computed here straight
from the fixture sub-ledger's documents and payments — independently of the statement engine — so
the two code paths can disagree. When D's aged-receivables report lands, ``ar_aging`` is swapped
for it and the fixture for real invoices; the assertions stay.

Checks, for every contact and several dates: outstanding statement amount due = AR aging row
total, bucket by bucket; the activity statement's closing balance = the same total; the sum over
contacts = the AR aging grand total. Hypothesis widens it to random documents, payments and credit
notes.
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
from numo9.contacts.statement_engine import build_statement
from numo9.contacts.statements import AGING_BUCKETS
from numo9.contacts.subledger import FixtureDocument, FixtureSource
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = [pytest.mark.django_db, pytest.mark.data_validation]
D, day = Decimal, dt.date
ZERO = D("0.00")


def ar_aging(source: FixtureSource, as_at: dt.date) -> dict[int, dict[str, Decimal]]:
    """Aged receivables by contact, from the documents themselves (the report's own arithmetic)."""
    report: dict[int, dict[str, Decimal]] = {}
    for doc in source.documents:
        if doc.date > as_at:
            continue
        left = doc.total - sum((a for paid_on, a, _r in doc.payments if paid_on <= as_at), ZERO)
        if left == ZERO:
            continue
        overdue = max((as_at - doc.due_date).days, 0) if doc.due_date else 0
        row = report.setdefault(doc.contact_id, {key: ZERO for key, _l, _h in AGING_BUCKETS})
        for key, low, high in AGING_BUCKETS:
            if overdue >= low and (high is None or overdue <= high):
                row[key] += left
                break
    return report


def total(row: dict[str, Decimal]) -> Decimal:
    return sum(row.values(), ZERO)


def assert_agrees(contacts: list[Contact], source: FixtureSource, as_at: dt.date) -> None:
    aging = ar_aging(source, as_at)
    grand = ZERO
    for who in contacts:
        row = aging.get(who.pk, {key: ZERO for key, _l, _h in AGING_BUCKETS})
        outstanding = build_statement(who, "outstanding", as_at, side="receivables")
        assert outstanding.amount_due == total(row), (who.display_name, as_at)
        assert dict(outstanding.aging) == row, (who.display_name, as_at)
        activity = build_statement(
            who, "activity", as_at, start=day(2020, 1, 1), side="receivables"
        )
        assert activity.amount_due == total(row), (who.display_name, as_at)
        grand += outstanding.amount_due
    assert grand == sum((total(r) for r in aging.values()), ZERO)


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


def test_statement_total_equals_ar_aging_on_the_fixture(
    org: Organisation, source: FixtureSource
) -> None:
    maple = contact(org, "Maple Leaf Supply Ltd.", roles=["customer"])
    birch = contact(org, "Birch Bakery Co.", roles=["customer"])
    cedar = contact(org, "Cedar Café", roles=["customer"])
    for doc in [
        FixtureDocument(
            maple.pk,
            "INV-1",
            day(2026, 1, 10),
            D("500.00"),
            day(2026, 2, 9),
            payments=[(day(2026, 3, 10), D("200.00"), "PMT-1")],
        ),
        FixtureDocument(maple.pk, "INV-2", day(2026, 3, 5), D("120.00"), day(2026, 4, 4)),
        FixtureDocument(maple.pk, "CN-1", day(2026, 4, 1), D("-20.00")),
        FixtureDocument(birch.pk, "INV-3", day(2025, 10, 1), D("1130.00"), day(2025, 10, 31)),
        FixtureDocument(
            birch.pk,
            "INV-4",
            day(2026, 5, 1),
            D("75.50"),
            day(2026, 5, 31),
            payments=[(day(2026, 5, 15), D("75.50"), "PMT-2")],
        ),
        FixtureDocument(cedar.pk, "INV-5", day(2026, 6, 30), D("42.00"), None),
    ]:
        source.add(doc)
    for as_at in [day(2025, 12, 31), day(2026, 3, 31), day(2026, 5, 10), day(2026, 7, 31)]:
        assert_agrees([maple, birch, cedar], source, as_at)
    # The fixture is not trivially empty: on 31 July three customers owe something.
    july = ar_aging(source, day(2026, 7, 31))
    assert total(july[maple.pk]) == D("400.00")
    assert total(july[birch.pk]) == D("1130.00")
    assert total(july[cedar.pk]) == D("42.00")


amounts = st.decimals(min_value=D("-200"), max_value=D("2000"), places=2).filter(lambda a: a != 0)
dates = st.dates(min_value=day(2025, 1, 1), max_value=day(2026, 12, 31))
documents = st.lists(
    st.tuples(
        st.integers(0, 2),
        dates,
        amounts,
        st.one_of(st.none(), st.integers(0, 120)),
        st.lists(st.tuples(st.integers(0, 200), st.integers(1, 100)), max_size=2),
    ),
    max_size=12,
)


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(documents=documents, as_at=dates)
def test_statement_total_equals_ar_aging_property(
    org: Organisation, source: FixtureSource, documents: list[Any], as_at: dt.date
) -> None:
    people = [
        Contact.objects.filter(display_name=name).first() or contact(org, name, roles=["customer"])
        for name in ("Alder Ltd.", "Beech Inc.", "Cherry Co.")
    ]
    source.documents.clear()
    for n, (who, issued, amount, terms, payments) in enumerate(documents):
        due = issued + dt.timedelta(days=terms) if terms is not None else None
        paid = [
            (issued + dt.timedelta(days=after), (amount * pct / 100).quantize(D("0.01")), f"P{n}")
            for after, pct in payments
        ]
        source.add(FixtureDocument(people[who].pk, f"D-{n}", issued, amount, due, payments=paid))
    assert_agrees(people, source, as_at)
