"""D-06-T01 — CreditNote, CreditNoteLine and CreditApplication: migrate, statuses, the credited
invoice, credit used never more than the total, a posted credit note needs its number and
journal, applications are positive."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.sales.models import (
    CreditApplication,
    CreditNote,
    CreditNoteLine,
    CreditNoteStatus,
)
from numo9.tenancy.context import org_context
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return sales_books()


def _credit(books: dict[str, Any], **fields: Any) -> CreditNote:
    org = books["org"]
    with org_context(org):
        note = CreditNote(organisation=org, contact=books["customers"]["ON"], date=DAY, **fields)
        note.save()
        CreditNoteLine(
            organisation=org,
            document=note,
            position=0,
            description="Returned chair",
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            account=books["revenue"],
        ).save()
        return note


def test_a_draft_credit_note_for_an_invoice(books: dict[str, Any]) -> None:
    invoice = draft(books, [("1", "100.00", "")])
    note = _credit(books, invoice=invoice, total=Decimal("100.00"))
    assert (note.status, note.number, str(note)) == (
        CreditNoteStatus.DRAFT,
        "",
        "Draft credit note",
    )
    with org_context(books["org"]):
        assert note.lines.count() == 1
        assert list(invoice.credit_notes.all()) == [note]
    assert note.remaining == Decimal("100.00")


def test_credit_used_never_exceeds_the_total(books: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _credit(
            books,
            total=Decimal("50.00"),
            amount_applied=Decimal("40.00"),
            amount_refunded=Decimal("20.00"),
        )


def test_a_posted_credit_note_needs_number_and_journal(books: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _credit(books, status=CreditNoteStatus.APPROVED)


def test_applications_are_positive(books: dict[str, Any]) -> None:
    invoice = draft(books, [("1", "100.00", "")])
    note = _credit(books, total=Decimal("100.00"))
    org = books["org"]
    with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
        CreditApplication(
            organisation=org, credit_note=note, invoice=invoice, amount=Decimal("0"), date=DAY
        ).save()
    with org_context(org):
        CreditApplication(
            organisation=org, credit_note=note, invoice=invoice, amount=Decimal("10"), date=DAY
        ).save()
        assert note.applications.count() == 1
