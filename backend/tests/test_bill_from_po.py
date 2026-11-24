"""E-02-T08 — bill from a PO or a receipt: prefilled quantity = received − billed, PO prices and
accounts, linked lines; billed quantities move at approval and the PO becomes Billed; the match
panel per line (green / amber / red against received quantity and PO price, with the receipt
tolerance); a variance needs "approve with variance"."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.orgsettings.service import get_settings
from numo9.purchases.approvals import approve as approve_po
from numo9.purchases.bill_from_po import (
    BillFromOrderRefused,
    bill_from_purchase_order,
    line_status,
    match_panel,
)
from numo9.purchases.bill_posting import BillRefused, approve
from numo9.purchases.models import BillLine, PurchaseOrderStatus
from numo9.purchases.receipts import receive
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill_books
from tests.purchase_helpers import po

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    with org_context(books["org"]):
        settings = get_settings(books["org"])
        settings.po_receipt_tolerance_percent = Decimal("5")
        settings.bill_requires_supplier_invoice_no = False
        settings.save()
    return books


def ordered(books: dict[str, Any]) -> Any:
    order = approve_po(po(books, [("10", "25.00"), ("4", "80.00")]), books["owner"])
    with org_context(books["org"]):
        first, second = list(order.lines.order_by("position"))
    return order, first, second


def test_prefilled_quantity_is_received_minus_billed(books: dict[str, Any]) -> None:
    order, first, second = ordered(books)
    receive(order, books["owner"], [(first, Decimal("6"))])
    draft = bill_from_purchase_order(order, books["owner"])
    with org_context(books["org"]):
        lines = list(draft.lines.order_by("position"))
    assert [(line.po_line_id, line.quantity, line.unit_price) for line in lines] == [
        (first.pk, Decimal("6.0000"), Decimal("25.0000"))
    ]  # nothing received on the second line yet
    assert (draft.purchase_order_id, draft.reference, draft.total) == (
        order.pk,
        order.number,
        Decimal("150.00"),
    )
    approve(draft, books["owner"])
    with org_context(books["org"]):
        first.refresh_from_db()
    assert first.quantity_billed == Decimal("6")
    receive(order, books["owner"], [(first, Decimal("4")), (second, Decimal("4"))])
    rest = bill_from_purchase_order(order, books["owner"])
    with org_context(books["org"]):
        assert [line.quantity for line in rest.lines.order_by("position")] == [
            Decimal("4"),
            Decimal("4"),
        ]
    approve(rest, books["owner"])
    with org_context(books["org"]):
        order.refresh_from_db()
    assert order.status == PurchaseOrderStatus.BILLED
    with pytest.raises(BillFromOrderRefused):
        bill_from_purchase_order(order, books["owner"])


def test_match_panel_and_approve_with_variance(books: dict[str, Any]) -> None:
    order, first, second = ordered(books)
    receive(order, books["owner"], [(first, Decimal("10")), (second, Decimal("4"))])
    draft = bill_from_purchase_order(order, books["owner"])
    assert [row["status"] for row in match_panel(draft)] == ["green", "green"]
    with org_context(books["org"]):
        a, b = list(draft.lines.order_by("position"))
        BillLine.objects.filter(pk=a.pk).update(quantity=Decimal("12"))  # 12 billed vs 10 received
        BillLine.objects.filter(pk=b.pk).update(unit_price=Decimal("82.00"))  # 2.5 % over the PO
    panel = match_panel(draft)
    assert [
        (row["status"], row["quantity_over"], row["price_difference_pct"]) for row in panel
    ] == [
        ("red", "2.0000", "0.00"),
        ("amber", "0.0000", "2.50"),
    ]
    with pytest.raises(BillRefused) as refused:
        approve(draft, books["owner"])
    assert refused.value.code == "purchases.bill.variance"
    assert approve(draft, books["owner"], with_variance=True).status == "awaiting_payment"


@pytest.mark.parametrize(
    ("over", "price", "expected"),
    [
        ("0", "0", "green"),
        ("-5", "0", "green"),
        ("5", "0", "amber"),
        ("0", "5", "amber"),
        ("5.01", "0", "red"),
        ("0", "7", "red"),
    ],
)
def test_line_status(over: str, price: str, expected: str) -> None:
    assert line_status(Decimal(over), Decimal(price), Decimal("5")) == expected
