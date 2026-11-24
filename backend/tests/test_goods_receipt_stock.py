"""E-01-T05 — the StockMovementSink: a receipt of a tracked item records +6 in the sink (the
Phase 1 test double; H-04 keeps this contract); untracked items record the quantity on the PO and
move no stock; a failing sink rolls the receipt back.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest import mock

import pytest

from numo9.items.models import Item
from numo9.purchases.approvals import approve
from numo9.purchases.receipts import receive
from numo9.purchases.stock import Movement, RecordingSink, sink, use_sink
from numo9.tenancy.context import org_context
from tests.purchase_helpers import po, purchase_books

pytestmark = pytest.mark.django_db
#: Every item counts as tracked (the database refuses tracked items until H-01).
TRACKED = mock.patch("numo9.purchases.stock.tracked", lambda line: line.item_id is not None)


@pytest.fixture
def books() -> dict[str, Any]:
    books = purchase_books()
    with org_context(books["org"]):
        books["item"] = Item(organisation=books["org"], code="OAK-1", name="Oak boards")
        books["item"].save()
    return books


def ordered(books: dict[str, Any]) -> tuple[Any, Any]:
    order = po(books, [("10", "25.00")], user=books["buyer"])
    with org_context(books["org"]):
        line = order.lines.get()
        line.item = books["item"]
        line.save()
    return approve(order, books["buyer"]), line


def test_tracked_item_receipt_records_plus_six(books: dict[str, Any]) -> None:
    order, line = ordered(books)
    # A tracked item fixture: Phase 1 items can't be tracked yet (H-01 lifts the constraint).
    with TRACKED, use_sink(RecordingSink()) as double:
        result = receive(order, books["clerk"], [(line, Decimal("6"))])
    [movement] = double.movements
    assert movement == Movement(
        item_id=books["item"].pk,
        quantity=Decimal("6"),
        date=result.receipt.date,
        po_line_id=line.pk,
        receipt_id=result.receipt.pk,
        organisation_id=books["org"].pk,
    )
    assert double.on_hand == {books["item"].pk: Decimal("6")}


def test_untracked_item_moves_no_stock(books: dict[str, Any]) -> None:
    order, line = ordered(books)
    with use_sink(RecordingSink()) as double:
        receive(order, books["clerk"], [(line, Decimal("6"))])
    assert double.movements == []
    with org_context(books["org"]):
        line.refresh_from_db()
        assert line.quantity_received == Decimal("6")


def test_failing_sink_rolls_the_receipt_back(books: dict[str, Any]) -> None:
    order, line = ordered(books)

    class Broken:
        def record(self, movements: Any) -> None:
            raise RuntimeError("inventory down")

    with TRACKED, use_sink(Broken()), pytest.raises(RuntimeError):
        receive(order, books["clerk"], [(line, Decimal("6"))])
    with org_context(books["org"]):
        line.refresh_from_db()
        order.refresh_from_db()
        assert (line.quantity_received, order.status, order.receipts.count()) == (
            Decimal("0"),
            "approved",
            0,
        )
    assert type(sink()).__name__ == "NullSink"  # the default is back
