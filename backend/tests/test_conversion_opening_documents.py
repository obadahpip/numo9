"""C-05-T03 — opening invoices and bills: stored as ``Invoice`` / ``Bill`` with
``is_opening=True``, linked to the conversion by an ``OpeningDocument``.

Acceptance: an opening invoice appears among the customer's open invoices (what aging, statements
and payment allocation read) and posts nothing until finalise; a partly paid one opens Partially
paid for what was owed; documents dated on or after the conversion date, totals of zero, more
owed than the total and taken numbers are refused; an opening document can't be voided; removing
one from a draft conversion frees its number.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from numo9.conversion.documents import (
    add_opening_bill,
    add_opening_invoice,
    opening_documents,
    remove_opening_document,
)
from numo9.conversion.models import OpeningDocument
from numo9.ledger.models import JournalEntry, LedgerError
from numo9.purchases.bill_posting import void as void_bill
from numo9.purchases.models import Bill
from numo9.sales.allocations import open_balance, open_invoices
from numo9.sales.models import Invoice
from numo9.sales.posting import void as void_invoice
from numo9.tenancy.context import org_context
from tests.conversion_helpers import BEFORE, CONVERSION_DATE, conversion_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return conversion_books()


def codes(error: ValidationError) -> set[str]:
    if hasattr(error, "error_dict"):
        return {e.code for items in error.error_dict.values() for e in items if e.code}
    return {e.code for e in error.error_list if e.code}


def test_opening_invoice_is_open_and_posts_nothing(books: dict[str, Any]) -> None:
    org, customer = books["org"], books["customers"]["ON"]
    invoice = add_opening_invoice(
        books["session"],
        contact=customer,
        number="INV-0950",
        date=BEFORE,
        due_date=BEFORE.replace(day=30),
        total="2260.00",
        user=books["owner"],
    )
    with org_context(org):
        invoice.refresh_from_db()
        assert invoice.is_opening and invoice.journal_entry is None
        assert (invoice.status, invoice.number, invoice.total) == (
            "approved",
            "INV-0950",
            Decimal("2260.00"),
        )
        assert [i.pk for i in open_invoices(customer)] == [invoice.pk]  # aging / allocation
        assert open_balance(invoice) == Decimal("2260.00")
        assert not JournalEntry.objects.exists()  # nothing posted until finalise
        link = OpeningDocument.objects.get(invoice=invoice)
        assert (link.session_id, link.kind, link.outstanding) == (
            books["session"].pk,
            "invoice",
            Decimal("2260.00"),
        )
        line = invoice.lines.get()
        assert line.account is None and line.tax_code is None
        assert str(CONVERSION_DATE.isoformat()) in line.description


def test_partly_paid_invoice_opens_for_what_was_owed(books: dict[str, Any]) -> None:
    invoice = add_opening_invoice(
        books["session"],
        contact=books["customers"]["ON"],
        number="INV-0951",
        date=BEFORE,
        total="1000.00",
        outstanding="400.00",
    )
    with org_context(books["org"]):
        invoice.refresh_from_db()
        assert invoice.status == "partially_paid"
        assert invoice.amount_paid == Decimal("600.00")
        assert open_balance(invoice) == Decimal("400.00")


def test_opening_bill_is_awaiting_payment_with_own_number(books: dict[str, Any]) -> None:
    first = add_opening_bill(
        books["session"],
        contact=books["supplier"],
        supplier_invoice_no="C-7781",
        date=BEFORE,
        total="565.00",
    )
    second = add_opening_bill(
        books["session"],
        contact=books["supplier"],
        supplier_invoice_no="C-7790",
        date=BEFORE,
        total="300.00",
        outstanding="100.00",
    )
    with org_context(books["org"]):
        first.refresh_from_db()
        second.refresh_from_db()
        assert (first.number, first.status, first.amount_due) == (
            "OB-0001",
            "awaiting_payment",
            Decimal("565.00"),
        )
        assert (second.number, second.status, second.amount_due) == (
            "OB-0002",
            "partially_paid",
            Decimal("100.00"),
        )
        assert first.journal_entry is None and first.is_opening
        assert not JournalEntry.objects.exists()
    assert [d.pk for d in opening_documents(books["session"], "bill")] == [first.pk, second.pk]


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"date": CONVERSION_DATE}, "conversion.document.date"),
        ({"total": "0.00"}, "conversion.document.total"),
        ({"total": "abc"}, "conversion.document.amount"),
        ({"total": "10.005"}, "conversion.document.amount"),
        ({"outstanding": "120.00"}, "conversion.document.outstanding"),
        ({"outstanding": "0"}, "conversion.document.outstanding"),
        ({"number": " "}, "conversion.document.number_required"),
        ({"due_date": BEFORE.replace(day=1)}, "conversion.document.due_date"),
    ],
)
def test_refusals(books: dict[str, Any], fields: dict[str, Any], code: str) -> None:
    values: dict[str, Any] = {
        "contact": books["customers"]["ON"],
        "number": "INV-1",
        "date": BEFORE,
        "total": "100.00",
        **fields,
    }
    with pytest.raises(ValidationError) as caught:
        add_opening_invoice(books["session"], **values)
    assert code in codes(caught.value)


def test_number_taken(books: dict[str, Any]) -> None:
    session, customer = books["session"], books["customers"]["ON"]
    add_opening_invoice(session, contact=customer, number="INV-7", date=BEFORE, total="1.00")
    with pytest.raises(ValidationError) as caught:
        add_opening_invoice(session, contact=customer, number="inv-7", date=BEFORE, total="2.00")
    assert "conversion.document.number_taken" in codes(caught.value)
    add_opening_bill(
        session, contact=books["supplier"], supplier_invoice_no="A1", date=BEFORE, total="1.00"
    )
    with pytest.raises(ValidationError) as caught:
        add_opening_bill(
            session, contact=books["supplier"], supplier_invoice_no="a1", date=BEFORE, total="1.00"
        )
    assert "conversion.document.number_taken" in codes(caught.value)


def test_opening_documents_cannot_be_voided(books: dict[str, Any]) -> None:
    invoice = add_opening_invoice(
        books["session"],
        contact=books["customers"]["ON"],
        number="INV-9",
        date=BEFORE,
        total="50.00",
    )
    bill = add_opening_bill(
        books["session"],
        contact=books["supplier"],
        supplier_invoice_no="S-9",
        date=BEFORE,
        total="50.00",
    )
    with pytest.raises(LedgerError) as caught:
        void_invoice(invoice, books["owner"])
    assert caught.value.code == "sales.invoice.not_voidable"
    with pytest.raises(LedgerError) as caught:
        void_bill(bill, books["owner"])
    assert caught.value.code == "purchases.bill.not_voidable"


def test_database_refuses_an_opening_document_with_its_own_journal(books: dict[str, Any]) -> None:
    invoice = add_opening_invoice(
        books["session"],
        contact=books["customers"]["ON"],
        number="INV-10",
        date=BEFORE,
        total="50.00",
    )
    with org_context(books["org"]):
        with pytest.raises(IntegrityError), transaction.atomic():
            Invoice._base_manager.filter(pk=invoice.pk).update(is_opening=False)
        with pytest.raises(IntegrityError), transaction.atomic():  # one target per link
            OpeningDocument._base_manager.filter(invoice=invoice).update(kind="bill")


def test_remove_frees_the_number(books: dict[str, Any]) -> None:
    session, customer = books["session"], books["customers"]["ON"]
    invoice = add_opening_invoice(
        session, contact=customer, number="INV-11", date=BEFORE, total="80.00"
    )
    bill = add_opening_bill(
        session, contact=books["supplier"], supplier_invoice_no="S-11", date=BEFORE, total="80.00"
    )
    with org_context(books["org"]):
        for link in OpeningDocument.objects.all():
            remove_opening_document(link)
        invoice.refresh_from_db()
        assert invoice.is_deleted and invoice.status == "draft" and invoice.number == ""
        assert Bill._base_manager.get(pk=bill.pk).is_deleted
    assert opening_documents(session) == []
    again = add_opening_invoice(
        session, contact=customer, number="INV-11", date=BEFORE, total="80.00"
    )
    assert again.number == "INV-11"
    add_opening_bill(
        session, contact=books["supplier"], supplier_invoice_no="S-11", date=BEFORE, total="80.00"
    )
