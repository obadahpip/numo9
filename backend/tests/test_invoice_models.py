"""D-03a-T01 — Invoice and InvoiceLine on the document base: a draft has no number and shows
"Draft"; a posted status needs a number and a journal (database check); numbers are unique per
organisation (empty ones aren't); statuses are checked; lines inherit the D-01 line rules; the
invoice is audited; ``current_revision`` is empty until D-03b.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.audit.models import AuditEvent
from numo9.ledger.services import post_journal
from numo9.sales.models import Invoice, InvoiceLine, InvoiceStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        customer = contact(org, "Maple Leaf Ltd", roles=["customer"])
    return {"org": org, "customer": customer, **accounts}


def invoice(books: dict[str, Any], **fields: Any) -> Invoice:
    item = Invoice(
        organisation=books["org"], contact=books["customer"], date=dt.date(2026, 6, 15), **fields
    )
    item.save()
    return item


def test_draft_has_no_number_and_lines_attach(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        draft = invoice(books)
        assert (draft.status, draft.number, str(draft)) == ("draft", "", "Draft invoice")
        assert draft.current_revision is None and not draft.is_posted
        InvoiceLine(
            organisation=books["org"],
            document=draft,
            description="Design consultation",
            quantity=Decimal("2"),
            unit_price=Decimal("150.00"),
            account=books["sales"],
        ).save()
        assert draft.lines.count() == 1
        assert AuditEvent.objects.filter(
            object_type="sales.Invoice", object_id=str(draft.public_id)
        ).exists()
        # Two drafts both without a number are fine.
        invoice(books)


def test_posted_needs_number_and_journal(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        draft = invoice(books)
        with pytest.raises(IntegrityError), transaction.atomic():
            Invoice._base_manager.filter(pk=draft.pk).update(status=InvoiceStatus.APPROVED)
        entry = post_journal(pay(books["ar"], books["sales"], "300.00"), user=None)
        Invoice._base_manager.filter(pk=draft.pk).update(
            status=InvoiceStatus.APPROVED, number="INV-0001", journal_entry=entry
        )
        draft.refresh_from_db()
        assert draft.is_posted and draft.amount_due == draft.total


def test_numbers_unique_and_statuses_checked(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        first = invoice(books)
        second = invoice(books)
        Invoice._base_manager.filter(pk=first.pk).update(number="INV-0007")
        with pytest.raises(IntegrityError), transaction.atomic():
            Invoice._base_manager.filter(pk=second.pk).update(number="INV-0007")
        with pytest.raises(IntegrityError), transaction.atomic():
            Invoice._base_manager.filter(pk=second.pk).update(status="lost")
        with pytest.raises(IntegrityError), transaction.atomic():
            Invoice._base_manager.filter(pk=second.pk).update(due_date=dt.date(2026, 1, 1))
    other = Organisation.objects.create(name="Other Co.")
    with org_context(other):
        buyer = contact(other, "Someone", roles=["customer"])
        mine = Invoice(
            organisation=other, contact=buyer, date=dt.date(2026, 6, 15), number="INV-0007"
        )
        mine.save()  # the same number in another organisation is fine: unique per organisation
