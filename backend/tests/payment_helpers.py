"""Batch payments for the E-06 tests: the bill books of E-02 (GST-registered Ontario
organisation, two suppliers) with a chequing account, approved bills awaiting payment and a
batch builder."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.banking.services import create_bank_account
from numo9.orgsettings.models import TaxRegistration
from numo9.purchases.bill_posting import approve
from numo9.purchases.models import Bill, BillPayment, PaymentBatch
from numo9.tenancy.context import org_context
from tests.bill_helpers import DAY, bill, bill_books

__all__ = ["DAY", "add_payment", "batch", "payment_books", "posted_bill"]


def payment_books(name: str = "Refined Interiors Inc.") -> dict[str, Any]:
    books = bill_books(name)
    org = books["org"]
    with org_context(org):
        TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
    books["bank"] = create_bank_account(
        org, type="chequing", display_name="Operating chequing", institution="RBC"
    )
    return books


def posted_bill(books: dict[str, Any], amount: str, number: str, **fields: Any) -> Bill:
    """An approved bill awaiting payment for ``amount`` (no tax)."""
    return approve(
        bill(books, [("1", amount)], supplier_invoice_no=number, **fields), books["owner"]
    )


def batch(books: dict[str, Any], method: str = "cheque", **fields: Any) -> PaymentBatch:
    org = books["org"]
    with org_context(org):
        made = PaymentBatch(
            organisation=org,
            bank_account=fields.pop("bank_account", books["bank"]),
            method=method,
            payment_date=fields.pop("payment_date", DAY + dt.timedelta(days=10)),
            **fields,
        )
        made.save()
    return made


def add_payment(
    made: PaymentBatch, paid: Bill, amount: str, discount: str = "0", **fields: Any
) -> BillPayment:
    with org_context(made.organisation):
        row = BillPayment(
            organisation=made.organisation,
            batch=made,
            bill=paid,
            contact=paid.contact,
            bank_account=made.bank_account,
            method=made.method,
            date=made.payment_date,
            amount=Decimal(amount),
            discount=Decimal(discount),
            **fields,
        )
        row.save()
    return row
