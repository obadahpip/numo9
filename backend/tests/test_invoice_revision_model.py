"""D-03b-T02 — ``InvoiceRevision``: number shown ("101", "101-1"), the snapshot and totals, the
reason (required from revision 1), the two journals, ``superseded_at``; unique per invoice."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.sales.models import InvoiceRevision
from numo9.sales.posting import approve
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    books["invoice"] = approve(draft(books, [("1", "100.00", "sales.ON.standard")]), books["owner"])
    return books


def revision(books: dict[str, Any], n: int, **fields: Any) -> InvoiceRevision:
    invoice = books["invoice"]
    row = InvoiceRevision(
        organisation=books["org"],
        invoice=invoice,
        revision=n,
        number_display=f"{invoice.number}-{n}" if n else invoice.number,
        **fields,
    )
    row.save()
    return row


def test_fields_and_unique_per_invoice(books: dict[str, Any]) -> None:
    invoice = books["invoice"]
    with org_context(books["org"]):
        # Start clean of revision 0 (made at approval, D-03b-T03).
        type(invoice)._base_manager.filter(pk=invoice.pk).update(current_revision=None)
        made = InvoiceRevision._base_manager.filter(invoice=invoice)
        made._raw_delete(made.db)
        first = revision(books, 0, total=Decimal("113.00"), tax_total=Decimal("13.00"))
        second = revision(
            books,
            1,
            reason="Wrong quantity",
            journal_post=invoice.journal_entry,
            total=Decimal("1"),
        )
        first.superseded_at = timezone.now()
        first.save()
        assert (str(first), str(second)) == (invoice.number, f"{invoice.number}-1")
        assert (first.is_current, second.is_current) == (False, True)
        assert second.journal_post == invoice.journal_entry and second.journal_reversal is None
        with pytest.raises(IntegrityError), transaction.atomic():
            revision(books, 1, reason="Again")
        with pytest.raises(IntegrityError), transaction.atomic():
            revision(books, 2)  # revision 1 and after need a reason
