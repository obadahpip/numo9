"""D-05-T04 — overpayment and prepayment become a customer credit, applied to an invoice later:
paying 226.00 on a 113.00 invoice pays it and leaves a 113.00 overpayment credit, applicable to
the next invoice; a payment with no open invoice is a prepayment; the payment posts Dr bank /
Cr accounts receivable, so the customer's AR balance is the invoices less the credit."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum

from numo9.banking.services import create_bank_account
from numo9.ledger.models import JournalLine
from numo9.sales.allocations import AllocationRefused, open_balance
from numo9.sales.models import CustomerCredit
from numo9.sales.posting import approve
from numo9.sales.receipts import apply_credit, receive_payment
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
    books["customer"] = books["customers"]["ON"]
    return books


def invoice(books: dict[str, Any], price: str = "100.00") -> Any:
    return approve(draft(books, [("1", price, "sales.ON.standard")]), books["owner"])


def ar_balance(books: dict[str, Any]) -> Decimal:
    with org_context(books["org"]):
        rows = JournalLine.objects.filter(
            account__system_role="ar", contact=books["customer"]
        ).aggregate(net=Sum("debit") - Sum("credit"))
    return D(rows["net"] or 0)


def test_overpayment_becomes_a_credit_applied_later(books: dict[str, Any]) -> None:
    first = invoice(books)  # 113.00
    paid = receive_payment(books["customer"], books["bank"], DAY, D("226.00"), books["owner"])
    with org_context(books["org"]):
        first.refresh_from_db()
        (credit,) = CustomerCredit.objects.filter(contact=books["customer"])
        assert open_balance(first) == D("0.00")
        assert (credit.source, credit.amount, credit.remaining) == (
            "overpayment",
            D("113.00"),
            D("113.00"),
        )
        assert credit.payment == paid and paid.journal_entry is not None
    assert ar_balance(books) == D("-113.00")  # the customer's credit on AR
    second = invoice(books)  # 113.00
    apply_credit(credit, second, D("113.00"), books["owner"], date=dt.date(2026, 6, 20))
    with org_context(books["org"]):
        second.refresh_from_db()
        credit.refresh_from_db()
        assert (open_balance(second), credit.remaining) == (D("0.00"), D("0.00"))
    assert ar_balance(books) == D("0.00")
    with pytest.raises(AllocationRefused) as spent:
        apply_credit(credit, invoice(books), D("1.00"), books["owner"])
    assert spent.value.code == "sales.allocation.over_source"


def test_a_payment_without_open_invoices_is_a_prepayment(books: dict[str, Any]) -> None:
    receive_payment(books["customer"], books["bank"], DAY, D("500.00"), books["owner"])
    with org_context(books["org"]):
        (credit,) = CustomerCredit.objects.all()
        assert (credit.source, credit.amount) == ("prepayment", D("500.00"))
    later = invoice(books, "200.00")  # 226.00
    apply_credit(credit, later, D("226.00"), books["owner"])
    with org_context(books["org"]):
        credit.refresh_from_db()
        assert credit.remaining == D("274.00")


def test_a_manual_plan_keeps_the_rest_as_credit(books: dict[str, Any]) -> None:
    owed = invoice(books)
    paid = receive_payment(
        books["customer"],
        books["bank"],
        DAY,
        D("113.00"),
        books["owner"],
        allocations=[(owed, D("50.00"))],
    )
    with org_context(books["org"]):
        owed.refresh_from_db()
        assert open_balance(owed) == D("63.00") and paid.allocated == D("50.00")
        assert CustomerCredit.objects.get().amount == D("63.00")
