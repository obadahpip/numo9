"""E-01-T07 — the 3-way match engine: per PO line, PO quantity and price against received and
billed, with the quantity and price tolerances of the organisation settings; a bill for 12
against a PO for 10 is flagged; bill before receipt is allowed (received later, match pending);
the PO's match view lists every line with its bills."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.orgsettings.service import get_settings
from numo9.purchases.approvals import approve as approve_po
from numo9.purchases.bill_from_po import bill_from_purchase_order, match_panel
from numo9.purchases.bill_posting import approve
from numo9.purchases.matching import (
    OVER_ORDERED,
    OVER_RECEIVED,
    PRICE,
    RECEIVED_LATER,
    Figures,
    Tolerance,
    evaluate,
    match_order,
    tolerance_for,
)
from numo9.purchases.models import BillLine
from numo9.purchases.receipts import receive
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill_books
from tests.purchase_helpers import po

D = Decimal
FIVE = Tolerance(quantity=D("5"), price=D("2"))


@pytest.mark.parametrize(
    ("ordered", "received", "billed", "po_price", "price", "received_any", "status", "flags"),
    [
        # the deliverable's case: a bill for 12 against a PO for 10
        ("10", "10", "12", "25", "25", True, "red", (OVER_ORDERED, OVER_RECEIVED)),
        ("10", "12", "12", "25", "25", True, "red", (OVER_ORDERED,)),  # over-receipt confirmed
        ("10", "0", "12", "25", "25", False, "red", (OVER_ORDERED, RECEIVED_LATER)),
        # exact match, partial bill of what was received
        ("10", "10", "10", "25", "25", True, "green", ()),
        ("10", "6", "6", "25", "25", True, "green", ()),
        ("10", "6", "4", "25", "25", True, "green", ()),
        # more than received, within the quantity tolerance (5 %)
        ("100", "100", "105", "1", "1", True, "amber", (OVER_ORDERED, OVER_RECEIVED)),
        ("100", "100", "105.01", "1", "1", True, "red", (OVER_ORDERED, OVER_RECEIVED)),
        ("10", "6", "7", "25", "25", True, "red", (OVER_RECEIVED,)),
        # price: 2 % tolerance, either way
        ("10", "10", "10", "100", "102", True, "amber", (PRICE,)),
        ("10", "10", "10", "100", "98", True, "amber", (PRICE,)),
        ("10", "10", "10", "100", "102.50", True, "red", (PRICE,)),
        ("1", "1", "1", "0", "5", True, "red", (PRICE,)),
        ("1", "1", "1", "0", "0", True, "green", ()),
        # bill before receipt: allowed, the receipt check waits
        ("10", "0", "10", "25", "25", False, "green", (RECEIVED_LATER,)),
        ("10", "0", "4", "25", "25", False, "green", (RECEIVED_LATER,)),
    ],
)
def test_evaluate(
    ordered: str,
    received: str,
    billed: str,
    po_price: str,
    price: str,
    received_any: bool,
    status: str,
    flags: tuple[str, ...],
) -> None:
    result = evaluate(
        Figures(D(ordered), D(received), D(billed), D(po_price), D(price), received_any), FIVE
    )
    assert (result.status, result.flags) == (status, flags)
    assert result.variance is (status != "green")


def test_bill_12_against_po_10_reports_the_quantity_over() -> None:
    result = evaluate(Figures(D(10), D(10), D(12), D(25), D(25)), Tolerance())
    assert (result.status, result.quantity_over, result.quantity_over_pct) == ("red", D(2), D(20))


pytestmark_db = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    with org_context(books["org"]):
        settings = get_settings(books["org"])
        settings.bill_requires_supplier_invoice_no = False
        settings.save()
    return books


def _tolerance(books: dict[str, Any], **fields: Any) -> None:
    with org_context(books["org"]):
        settings = get_settings(books["org"])
        for name, value in fields.items():
            setattr(settings, name, value)
        settings.save()


@pytestmark_db
def test_tolerance_falls_back_to_the_receipt_tolerance(books: dict[str, Any]) -> None:
    _tolerance(books, po_receipt_tolerance_percent=D("3"))
    assert tolerance_for(books["org"]) == Tolerance(D("3"), D("3"))
    _tolerance(books, po_match_quantity_tolerance_percent=D("0"))
    _tolerance(books, po_match_price_tolerance_percent=D("1.5"))
    assert tolerance_for(books["org"]) == Tolerance(D("0"), D("1.5"))


@pytestmark_db
def test_bill_for_12_against_po_for_10_is_flagged(books: dict[str, Any]) -> None:
    order = approve_po(po(books, [("10", "25.00")]), books["owner"])
    with org_context(books["org"]):
        line = order.lines.get()
    receive(order, books["owner"], [(line, D("12"))], confirm_over=True)
    draft = bill_from_purchase_order(order, books["owner"])
    with org_context(books["org"]):
        assert draft.lines.get().quantity == D("12")
    (row,) = match_panel(draft)
    assert (row["status"], row["quantity_over"], row["flags"]) == ("red", "2.0000", [OVER_ORDERED])
    shown = match_order(order)
    assert shown["status"] == "red"
    assert shown["lines"][0]["bills"][0]["match"] == "red"


@pytestmark_db
def test_match_order_lines_bills_and_pending(books: dict[str, Any]) -> None:
    _tolerance(books, po_match_price_tolerance_percent=D("5"))
    order = approve_po(po(books, [("10", "25.00"), ("4", "80.00")]), books["owner"])
    with org_context(books["org"]):
        first, second = list(order.lines.order_by("position"))
    receive(order, books["owner"], [(first, D("6"))])
    posted = bill_from_purchase_order(order, books["owner"])
    approve(posted, books["owner"])
    receive(order, books["owner"], [(first, D("4")), (second, D("4"))])
    pending = bill_from_purchase_order(order, books["owner"])
    with org_context(books["org"]):
        BillLine.objects.filter(document=pending, po_line=second).update(unit_price=D("82.00"))
    shown = match_order(order)
    one, two = shown["lines"]
    assert (one["ordered"], one["received"], one["outstanding"], one["billed"]) == (
        "10.0000",
        "10.0000",
        "0.0000",
        "6.0000",
    )
    assert (one["pending"], one["to_bill"], one["status"]) == ("0.0000", "4.0000", "green")
    assert [b["match"] for b in one["bills"]] == ["green", "green"]  # posted 6, draft 4
    assert (two["billed"], two["status"], two["flags"]) == ("0.0000", "amber", [PRICE])
    assert two["bills"][0]["price_difference_pct"] == "2.50"
    assert shown["status"] == "amber"
    assert shown["tolerance"] == {"quantity": "0.00", "price": "5.00"}


@pytestmark_db
def test_bill_before_receipt_is_pending_not_a_variance(books: dict[str, Any]) -> None:
    order = approve_po(po(books, [("10", "25.00")]), books["owner"])
    draft = bill_from_purchase_order(order, books["owner"])  # nothing received: ordered − billed
    (row,) = match_panel(draft)
    assert (row["status"], row["received_later"]) == ("green", True)
    assert approve(draft, books["owner"]).status == "awaiting_payment"
    shown = match_order(order)
    assert shown["lines"][0]["flags"] == [RECEIVED_LATER] and shown["status"] == "green"
