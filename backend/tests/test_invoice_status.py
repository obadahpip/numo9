"""D-05-T07 — the invoice status updater: Partially paid / Paid from the current revision's total
against what payments, credits and credit notes cover, after every payment, removal and
revision combination."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.banking.services import create_bank_account
from numo9.sales.allocations import unallocate
from numo9.sales.invoice_status import payment_status, refresh_status
from numo9.sales.models import Invoice, PaymentAllocation
from numo9.sales.posting import approve
from numo9.sales.receipts import receive_payment
from numo9.sales.revise import revise
from numo9.sales.revisions import build_revision
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    books["bank"] = create_bank_account(books["org"], type="chequing", display_name="TD Chequing")
    books["invoice"] = approve(
        draft(books, [("10", "100.00", "sales.ON.standard")]), books["owner"]
    )  # 1,130.00
    return books


def status(books: dict[str, Any]) -> str:
    with org_context(books["org"]):
        return str(Invoice.objects.get(pk=books["invoice"].pk).status)


def pay(books: dict[str, Any], amount: str) -> None:
    receive_payment(books["invoice"].contact, books["bank"], DAY + dt.timedelta(days=3), D(amount))


def revise_to(books: dict[str, Any], quantity: str) -> None:
    with org_context(books["org"]):
        books["invoice"].refresh_from_db()
        opened = build_revision(books["invoice"])
    opened.lines[0]["quantity"] = D(quantity)
    opened.reason = f"{quantity} hours"
    revise(books["invoice"], opened, books["owner"])


def test_payments_move_it_to_partially_paid_then_paid(books: dict[str, Any]) -> None:
    assert status(books) == "approved"
    pay(books, "500.00")
    assert status(books) == "partially_paid"
    pay(books, "630.00")
    assert status(books) == "paid"


def test_raising_a_paid_invoice_makes_it_partially_paid_again(books: dict[str, Any]) -> None:
    pay(books, "1130.00")
    assert status(books) == "paid"
    revise_to(books, "11")  # 1,243.00
    assert status(books) == "partially_paid"
    pay(books, "113.00")
    assert status(books) == "paid"


def test_lowering_to_what_is_paid_makes_it_paid(books: dict[str, Any]) -> None:
    pay(books, "1017.00")
    assert status(books) == "partially_paid"
    revise_to(books, "9")  # 1,017.00 — the current revision is what counts
    assert status(books) == "paid"


def test_a_revision_without_payment_keeps_approved_or_sent(books: dict[str, Any]) -> None:
    revise_to(books, "9")
    assert status(books) == "approved"
    with org_context(books["org"]):
        Invoice.objects.filter(pk=books["invoice"].pk).update(sent_at=dt.datetime.now(dt.UTC))
    revise_to(books, "8")
    assert status(books) == "sent"


def test_removing_an_allocation_goes_back(books: dict[str, Any]) -> None:
    pay(books, "1130.00")
    with org_context(books["org"]):
        (allocation,) = PaymentAllocation.objects.filter(invoice=books["invoice"])
    unallocate(allocation)
    assert status(books) == "approved"


def test_draft_and_void_are_left_alone(books: dict[str, Any]) -> None:
    from numo9.sales.posting import void

    other = draft(books, [("1", "100.00", "sales.ON.standard")])
    with org_context(books["org"]):
        assert payment_status(other) == "draft"
    void(books["invoice"], books["owner"], reason="Twice")
    assert refresh_status(books["invoice"]) == "void"
