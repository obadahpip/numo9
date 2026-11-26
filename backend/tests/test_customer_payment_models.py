"""D-05-T01 — ``CustomerPayment``, ``PaymentAllocation`` and ``CustomerCredit``: a payment's
allocated / unallocated amounts, a credit's applied / remaining amounts (refunds count), and the
database rules — positive amounts, an allocation from exactly one source (a payment or a credit),
a refund never above the credit."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.banking.services import create_bank_account
from numo9.sales.models import (
    CreditSource,
    CustomerCredit,
    CustomerPayment,
    PaymentAllocation,
)
from numo9.sales.posting import approve
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
    books["invoice"] = approve(draft(books, [("1", "100.00", "sales.ON.standard")]), books["owner"])
    return books


def payment(books: dict[str, Any], amount: str = "150.00") -> CustomerPayment:
    with org_context(books["org"]):
        row = CustomerPayment(
            organisation=books["org"],
            contact=books["customers"]["ON"],
            bank_account=books["bank"],
            date=DAY,
            amount=D(amount),
        )
        row.save()
    return row


def test_payment_allocated_and_unallocated(books: dict[str, Any]) -> None:
    paid = payment(books)
    with org_context(books["org"]):
        PaymentAllocation(
            organisation=books["org"],
            payment=paid,
            invoice=books["invoice"],
            amount=D("113.00"),
            date=DAY,
        ).save()
        assert (paid.allocated, paid.unallocated) == (D("113.00"), D("37.00"))
        assert paid.status == "posted" and str(paid).endswith("150.00")


def test_credit_applied_refunded_and_remaining(books: dict[str, Any]) -> None:
    paid = payment(books)
    with org_context(books["org"]):
        credit = CustomerCredit(
            organisation=books["org"],
            contact=books["customers"]["ON"],
            source=CreditSource.OVERPAYMENT,
            payment=paid,
            date=DAY,
            amount=D("37.00"),
        )
        credit.save()
        PaymentAllocation(
            organisation=books["org"],
            credit=credit,
            invoice=books["invoice"],
            amount=D("10.00"),
            date=dt.date(2026, 7, 1),
        ).save()
        credit.amount_refunded = D("5.00")
        credit.save()
        assert (credit.applied, credit.remaining) == (D("10.00"), D("22.00"))


def test_database_rules(books: dict[str, Any]) -> None:
    paid = payment(books)
    with org_context(books["org"]):
        both = PaymentAllocation(
            organisation=books["org"], invoice=books["invoice"], amount=D("1.00"), date=DAY
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            both.save()  # neither a payment nor a credit
        with pytest.raises(IntegrityError), transaction.atomic():
            PaymentAllocation(
                organisation=books["org"],
                payment=paid,
                invoice=books["invoice"],
                amount=D("0.00"),
                date=DAY,
            ).save()
        credit = CustomerCredit(
            organisation=books["org"],
            contact=books["customers"]["ON"],
            source=CreditSource.PREPAYMENT,
            date=DAY,
            amount=D("20.00"),
            amount_refunded=D("25.00"),
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            credit.save()  # refunded more than the credit
        with pytest.raises(IntegrityError), transaction.atomic():
            payment(books, "-5.00")
