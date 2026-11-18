"""B-02-T08 — supplier reconciliation matcher (by invoice number, then amount + date ±3 days) and
the difference report (gap-23).

Acceptance (fixture): two unmatched items are listed with their amounts. Number matching ignores
case, spaces and dashes and reports an amount difference; amount + date matches within 3 days but
not 4; a hand match wins; their total, ours and the difference.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest

from numo9.contacts import subledger
from numo9.contacts.reconciliation import reconcile
from numo9.contacts.subledger import FixtureDocument, FixtureSource
from numo9.contacts.supplier_statements import add_line, create_manual_statement
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
def bills() -> Iterator[FixtureSource]:
    made = FixtureSource("payables")
    subledger.register_source(made)
    yield made
    subledger.unregister_source(made)


def test_matching_and_the_difference_report(org: Organisation, bills: FixtureSource) -> None:
    supplier = contact(org, "Maple Leaf Supply Ltd.", roles=["supplier"])
    bills.add(FixtureDocument(supplier.pk, "INV-0042", day(2026, 3, 2), D("1000.00")))
    bills.add(FixtureDocument(supplier.pk, "B-77", day(2026, 3, 10), D("250.00")))
    bills.add(FixtureDocument(supplier.pk, "B-80", day(2026, 3, 12), D("90.00")))
    bills.add(FixtureDocument(supplier.pk, "B-81", day(2026, 3, 20), D("60.00")))  # ours only

    statement = create_manual_statement(supplier, day(2026, 3, 31))
    add_line(statement, day(2026, 3, 2), D("1050.00"), invoice_number="inv 0042")  # number, +50
    add_line(statement, day(2026, 3, 12), D("250.00"), invoice_number="77031")  # amount, 2 days
    add_line(statement, day(2026, 3, 16), D("90.00"), invoice_number="S-9")  # 4 days: no match
    add_line(statement, day(2026, 3, 25), D("40.00"), invoice_number="S-10")  # theirs only

    report = reconcile(statement)
    how = sorted((p.ours.document, p.how, p.difference) for p in report.pairs)
    assert how == [("B-77", "amount_date", D("0")), ("INV-0042", "number", D("50.00"))]
    assert sorted(line.amount for line in report.unmatched_theirs) == [D("40.00"), D("90.00")]
    assert sorted(item.document for item in report.unmatched_ours) == ["B-80", "B-81"]
    assert (report.their_total, report.our_total, report.difference) == (
        D("1430.00"),
        D("1400.00"),
        D("30.00"),
    )

    nine = next(line for line in report.unmatched_theirs if line.amount == D("90.00"))
    nine.manual_ref = "B-80"
    nine.save()
    again = reconcile(statement)
    assert ("B-80", "manual") in [(p.ours.document, p.how) for p in again.pairs]
    assert [line.amount for line in again.unmatched_theirs] == [D("40.00")]
