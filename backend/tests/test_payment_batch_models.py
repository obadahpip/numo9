"""E-06-T01 — PaymentBatch and BillPayment: migrate; method, status and file reference; the batch
total = Σ its payments (void ones out); a payment settles amount + discount; the CPA 005 file
creation number is unique per bank account unless the batch is cancelled; one payment per bill
in a batch; posted payments have their journal."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.banking.services import create_bank_account
from numo9.purchases.models import (
    BillPayment,
    BillPaymentStatus,
    PaymentBatch,
    PaymentBatchStatus,
    PaymentMethod,
)
from numo9.tenancy.context import org_context
from tests.payment_helpers import add_payment, batch, payment_books, posted_bill

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    books = payment_books()
    books["bill1"] = posted_bill(books, "1000.00", "A-1")
    books["bill2"] = posted_bill(books, "250.00", "A-2", supplier="other")
    return books


def test_batch_with_payments_totals_and_settles(books: dict[str, Any]) -> None:
    made = batch(books, PaymentMethod.CHEQUE)
    assert (made.status, made.method, made.total) == (PaymentBatchStatus.DRAFT, "cheque", D("0"))
    one = add_payment(made, books["bill1"], "980.00", discount="20.00")
    add_payment(made, books["bill2"], "100.00")  # part of the bill
    with org_context(books["org"]):
        assert made.recalculate() == D("1080.00")
        assert one.settled == D("1000.00")
        assert one.status == BillPaymentStatus.PENDING and one.journal_entry_id is None
        BillPayment.objects.filter(pk=one.pk).update(status=BillPaymentStatus.VOID)
        assert made.recalculate() == D("100.00")
        assert list(books["bill1"].payments.all()) == [one]


def test_file_creation_number_unique_per_bank_account_unless_cancelled(
    books: dict[str, Any],
) -> None:
    def eft(number: int, **fields: Any) -> PaymentBatch:
        return batch(
            books,
            PaymentMethod.EFT,
            file_creation_number=number,
            file_sha256="ab" * 32,
            status=fields.pop("status", PaymentBatchStatus.GENERATED),
            **fields,
        )

    first = eft(1)
    with pytest.raises(IntegrityError), transaction.atomic():
        eft(1)
    with org_context(books["org"]):
        PaymentBatch.objects.filter(pk=first.pk).update(status=PaymentBatchStatus.CANCELLED)
    assert eft(1).file_creation_number == 1  # the cancelled batch freed the number
    savings = create_bank_account(books["org"], type="savings", display_name="Payroll account")
    assert eft(2, bank_account=savings) and eft(2)  # another bank account: its own numbers


def test_eft_file_reference_required_once_generated(books: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        batch(books, PaymentMethod.EFT, status=PaymentBatchStatus.GENERATED)
    with pytest.raises(IntegrityError), transaction.atomic():
        batch(books, PaymentMethod.EFT, file_creation_number=10000)


def test_payment_rules(books: dict[str, Any]) -> None:
    made = batch(books)
    with pytest.raises(IntegrityError), transaction.atomic():
        add_payment(made, books["bill1"], "0")
    with pytest.raises(IntegrityError), transaction.atomic():
        add_payment(made, books["bill1"], "10", discount="-1")
    add_payment(made, books["bill1"], "10")
    with pytest.raises(IntegrityError), transaction.atomic():
        add_payment(made, books["bill1"], "5")  # one row per bill in a batch
    with pytest.raises(IntegrityError), transaction.atomic():
        add_payment(made, books["bill2"], "5", status=BillPaymentStatus.POSTED)  # no journal
