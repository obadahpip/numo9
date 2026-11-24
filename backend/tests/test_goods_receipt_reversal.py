"""E-01-T06 — receipt reversal: outstanding restored, the sink gets −quantity, the PO's status
follows (Received → Partially received → Approved), the receipt is kept with when, who and why;
a receipt is reversed once and needs a reason.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest import mock

import pytest

from numo9.audit.models import AuditEvent
from numo9.items.models import Item
from numo9.purchases.approvals import PurchaseOrderRefused, approve
from numo9.purchases.receipts import receive, reverse_receipt
from numo9.purchases.stock import RecordingSink, use_sink
from numo9.tenancy.context import org_context
from tests.purchase_helpers import po, purchase_books

pytestmark = pytest.mark.django_db
TRACKED = mock.patch("numo9.purchases.stock.tracked", lambda line: line.item_id is not None)


@pytest.fixture
def books() -> dict[str, Any]:
    books = purchase_books()
    with org_context(books["org"]):
        item = Item(organisation=books["org"], code="OAK-1", name="Oak boards")
        item.save()
    order = po(books, [("10", "25.00")], user=books["buyer"])
    with org_context(books["org"]):
        line = order.lines.get()
        line.item = item
        line.save()
    books.update(order=approve(order, books["buyer"]), line=line, item=item)
    return books


def state(books: dict[str, Any]) -> tuple[Decimal, Decimal, str]:
    with org_context(books["org"]):
        books["line"].refresh_from_db()
        books["order"].refresh_from_db()
        return (
            books["line"].quantity_received,
            books["line"].outstanding,
            books["order"].status,
        )


def test_reversal_restores_outstanding_and_stock(books: dict[str, Any]) -> None:
    order, line = books["order"], books["line"]
    with TRACKED, use_sink(RecordingSink()) as double:
        first = receive(order, books["clerk"], [(line, Decimal("6"))]).receipt
        second = receive(order, books["clerk"], [(line, Decimal("4"))]).receipt
        assert state(books) == (Decimal("10"), Decimal("0"), "received")
        reverse_receipt(second, books["owner"], "Wrong pallet counted")
        assert state(books) == (Decimal("6"), Decimal("4"), "partially_received")
        reverse_receipt(first, books["owner"], "Returned to supplier")
        assert state(books) == (Decimal("0"), Decimal("10"), "approved")
    assert [m.quantity for m in double.movements] == [6, 4, -4, -6]
    assert double.on_hand == {books["item"].pk: Decimal("0")}
    with org_context(books["org"]):
        second.refresh_from_db()
        assert second.reversed_by == books["owner"] and second.reversal_reason == (
            "Wrong pallet counted"
        )
        assert AuditEvent.objects.filter(action="purchases.goodsreceipt.reversed").count() == 2


def test_reversed_once_with_a_reason(books: dict[str, Any]) -> None:
    receipt = receive(books["order"], books["clerk"], [(books["line"], Decimal("6"))]).receipt
    with pytest.raises(PurchaseOrderRefused) as no_reason:
        reverse_receipt(receipt, books["owner"], " ")
    assert no_reason.value.code == "purchases.receipt.reason"
    reverse_receipt(receipt, books["owner"], "Damaged")
    with pytest.raises(PurchaseOrderRefused) as twice:
        reverse_receipt(receipt, books["owner"], "Damaged again")
    assert twice.value.code == "purchases.receipt.reversed"
