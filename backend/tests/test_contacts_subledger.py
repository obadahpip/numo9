"""B-02-T03 — ``SubLedgerSource`` interface + fixture implementation (the contract Phase 1 D/E
sources reuse).

Acceptance: the fixture source returns items. Open items as at a date are the documents dated
on or before it minus the payments up to it (fully paid ones left out, a credit note negative);
activity in a range lists documents positive and payments negative; sources register per side and
their items are merged in date order.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest

from numo9.contacts import subledger
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
    made = subledger.register_source(FixtureSource("receivables"))
    yield made  # type: ignore[misc]
    subledger.unregister_source(made)


def test_contract(org: Organisation, source: FixtureSource) -> None:
    maple = contact(org, "Maple Leaf Supply Ltd.")
    other = contact(org, "Birch Bakery Co.")
    source.add(
        FixtureDocument(
            maple.pk,
            "INV-1",
            day(2026, 2, 1),
            D("500.00"),
            day(2026, 3, 3),
            payments=[(day(2026, 3, 10), D("200.00"), "PMT-1")],
        )
    )
    source.add(
        FixtureDocument(
            maple.pk,
            "INV-2",
            day(2026, 3, 5),
            D("120.00"),
            day(2026, 4, 4),
            payments=[(day(2026, 3, 20), D("120.00"), "PMT-2")],
        )
    )
    source.add(FixtureDocument(maple.pk, "CN-1", day(2026, 3, 15), D("-30.00")))
    source.add(FixtureDocument(other.pk, "INV-9", day(2026, 3, 1), D("999.00")))

    as_at = {
        i.document: i.outstanding
        for i in subledger.open_items("receivables", maple, day(2026, 3, 12))
    }
    assert as_at == {"INV-1": D("300.00"), "INV-2": D("120.00")}
    at_end = {
        i.document: i.outstanding
        for i in subledger.open_items("receivables", maple, day(2026, 3, 31))
    }
    assert at_end == {"INV-1": D("300.00"), "CN-1": D("-30.00")}  # INV-2 fully paid

    moves = subledger.activity("receivables", maple, day(2026, 3, 1), day(2026, 3, 31))
    assert [(m.document, m.amount) for m in moves] == [
        ("INV-2", D("120.00")),
        ("PMT-1", D("-200.00")),
        ("CN-1", D("-30.00")),
        ("PMT-2", D("-120.00")),
    ]
    assert subledger.open_items("payables", maple, day(2026, 3, 31)) == []
