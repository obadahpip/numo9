"""E-01-T04 — goods receipts with tolerance rules: receiving 6 of 10 leaves 4 outstanding and
the PO Partially received; the rest makes it Received; within the tolerance nothing is said;
beyond it, warn mode asks for confirmation and then receives with the warning, block mode
refuses; drafts can't be received; a re-approved PO keeps its receipt status.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.orgsettings.service import get_settings
from numo9.purchases.approvals import PurchaseOrderRefused, approve, revise
from numo9.purchases.receipts import OverReceiptRefused, receive
from numo9.tenancy.context import org_context
from tests.purchase_helpers import po, purchase_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return purchase_books()


def approved(books: dict[str, Any], quantity: str = "10") -> Any:
    return approve(po(books, [(quantity, "25.00")], user=books["buyer"]), books["buyer"])


def line_of(books: dict[str, Any], order: Any) -> Any:
    with org_context(books["org"]):
        return order.lines.get()


def tolerance(books: dict[str, Any], percent: str, mode: str) -> None:
    with org_context(books["org"]):
        settings = get_settings(books["org"])
        settings.po_receipt_tolerance_percent = Decimal(percent)
        settings.po_over_receipt = mode
        settings.save()


def test_receive_6_of_10_then_the_rest(books: dict[str, Any]) -> None:
    order = approved(books)
    line = line_of(books, order)
    result = receive(order, books["clerk"], [(line, Decimal("6"))], notes="First pallet")
    assert result.warnings == []
    with org_context(books["org"]):
        order.refresh_from_db()
        line.refresh_from_db()
        assert (line.quantity_received, line.outstanding, order.status) == (
            Decimal("6"),
            Decimal("4"),
            "partially_received",
        )
        assert result.receipt.received_by == books["clerk"]
        assert AuditEvent.objects.filter(action="purchases.goodsreceipt.received").count() == 1
    receive(order, books["clerk"], [(line, Decimal("4"))])
    with org_context(books["org"]):
        order.refresh_from_db()
        assert order.status == "received" and order.receipts.count() == 2


def test_tolerance_warn_and_block(books: dict[str, Any]) -> None:
    tolerance(books, "10", "warn")
    order = approved(books)
    line = line_of(books, order)
    receive(order, books["clerk"], [(line, Decimal("11"))])  # within 10 %: silent
    with pytest.raises(OverReceiptRefused) as asked:
        receive(order, books["clerk"], [(line, Decimal("1"))])  # 12 of 10
    assert asked.value.code == "purchases.receipt.over_tolerance_confirm"
    assert asked.value.over[0].received == Decimal("12")
    result = receive(order, books["clerk"], [(line, Decimal("1"))], confirm_over=True)
    assert [w.received for w in result.warnings] == [Decimal("12")]
    tolerance(books, "0", "block")
    other = approved(books, "5")
    with pytest.raises(OverReceiptRefused) as blocked:
        receive(other, books["clerk"], [(line_of(books, other), Decimal("6"))], confirm_over=True)
    assert blocked.value.code == "purchases.receipt.over_tolerance"


def test_only_approved_orders_and_real_quantities(books: dict[str, Any]) -> None:
    draft = po(books, [("10", "25.00")])
    with pytest.raises(PurchaseOrderRefused) as refused:
        receive(draft, books["clerk"], [(line_of(books, draft), Decimal("1"))])
    assert refused.value.code == "purchases.receipt.not_receivable"
    order = approved(books)
    with pytest.raises(PurchaseOrderRefused) as empty:
        receive(order, books["clerk"], [(line_of(books, order), Decimal("0"))])
    assert empty.value.code == "purchases.receipt.empty"
    other = approved(books)
    with pytest.raises(PurchaseOrderRefused) as foreign:
        receive(order, books["clerk"], [(line_of(books, other), Decimal("1"))])
    assert foreign.value.code == "purchases.receipt.foreign_line"


def test_reapproved_po_keeps_its_receipt_status(books: dict[str, Any]) -> None:
    order = approved(books)
    line = line_of(books, order)
    receive(order, books["clerk"], [(line, Decimal("6"))])
    with org_context(books["org"]):
        line.refresh_from_db()
        line.quantity = Decimal("400")  # 10 000 > the buyer's 5 000: approval again
        line.save()
        order.refresh_from_db()
    revised = revise(order, books["buyer"])
    assert revised.status == "awaiting_approval"
    assert approve(revised, books["owner"]).status == "partially_received"
