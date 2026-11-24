"""E-01-T03 — re-approval when an approved PO's total increases: raising a line takes it back to
Awaiting approval with its number kept (audited), and it is approved again within a limit;
lowering it, or leaving the total as it was, keeps it approved.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.purchases.approvals import approve, reapproval_needed, revise
from numo9.tenancy.context import org_context
from tests.purchase_helpers import po, purchase_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return purchase_books()


def change_quantity(books: dict[str, Any], order: Any, quantity: str) -> None:
    with org_context(books["org"]):
        line = order.lines.get()
        line.quantity = Decimal(quantity)
        line.save()


def test_increase_goes_back_to_awaiting_approval(books: dict[str, Any]) -> None:
    order = approve(po(books, [("10", "100.00")], user=books["buyer"]), books["buyer"])
    assert order.approved_total == Decimal("1000.00")
    change_quantity(books, order, "12")
    revised = revise(order, books["buyer"])
    assert (revised.status, revised.number, revised.total) == (
        "awaiting_approval",
        "PO-0001",
        Decimal("1200.00"),
    )
    with org_context(books["org"]):
        event = AuditEvent.objects.get(action="purchases.purchaseorder.reapproval")
        assert event.meta["approved_total"] == "1000.00" and event.meta["total"] == "1200.00"
    again = approve(revised, books["owner"])
    assert (again.status, again.number, again.approved_total) == (
        "approved",
        "PO-0001",
        Decimal("1200.00"),
    )


def test_decrease_or_same_total_stays_approved(books: dict[str, Any]) -> None:
    order = approve(po(books, [("10", "100.00")], user=books["buyer"]), books["buyer"])
    change_quantity(books, order, "8")
    lower = revise(order, books["buyer"])
    assert (lower.status, lower.total) == ("approved", Decimal("800.00"))
    assert not reapproval_needed(lower)
    change_quantity(books, order, "10")  # back to the approved total: not above it
    same = revise(order, books["buyer"])
    assert same.status == "approved"
