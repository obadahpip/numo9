"""D-03b-T03 — revision 0: approving an invoice creates it (the snapshot of the document and
the PDF, the totals, the approval journal) and sets ``current_revision``; the data migration
gives one to every posted invoice that has none, and only to those."""

from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps

from numo9.sales.models import Invoice, InvoiceRevision
from numo9.sales.posting import approve
from numo9.sales.revisions import backfill_revision_zero, restore
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    return books


def test_approval_creates_revision_zero(books: dict[str, Any]) -> None:
    invoice = approve(draft(books, [("2", "50.00", "sales.ON.standard")]), books["owner"])
    with org_context(books["org"]):
        (zero,) = InvoiceRevision.objects.filter(invoice=invoice)
        invoice.refresh_from_db()
        assert invoice.current_revision == zero
        assert (zero.revision, zero.number_display, zero.reason) == (0, invoice.number, "")
        assert (zero.total, zero.tax_total) == (invoice.total, invoice.tax_total)
        assert zero.journal_post == invoice.journal_entry and zero.journal_reversal is None
        document = restore(zero.snapshot["document"])
        assert document["header"]["contact_id"] == invoice.contact_id
        assert [line["quantity"] for line in document["lines"]] == [invoice.lines.get().quantity]
        assert document["totals"]["total"] == invoice.total
        assert zero.snapshot["pdf"]["total"]["__decimal"] == f"{invoice.total:.2f}"


def test_the_backfill_covers_every_posted_invoice(books: dict[str, Any]) -> None:
    posted = [approve(draft(books, [("1", "10.00", "sales.ON.standard")]), books["owner"])]
    posted.append(approve(draft(books, [("1", "20.00", "sales.ON.standard")]), books["owner"]))
    still_draft = draft(books, [("1", "30.00", "sales.ON.standard")])
    with org_context(books["org"]):
        # As before D-03b: posted invoices without a revision.
        Invoice._base_manager.filter(pk__in=[p.pk for p in posted]).update(current_revision=None)
        gone = InvoiceRevision._base_manager.filter(invoice__in=posted)
        gone._raw_delete(gone.db)
    assert backfill_revision_zero(apps) == 2
    assert backfill_revision_zero(apps) == 0  # once
    with org_context(books["org"]):
        for invoice in posted:
            invoice.refresh_from_db()
            zero = invoice.current_revision
            assert zero is not None and zero.revision == 0
            assert zero.journal_post_id == invoice.journal_entry_id
            assert restore(zero.snapshot["document"])["totals"]["total"] == invoice.total
        still_draft.refresh_from_db()
        assert still_draft.current_revision is None
        assert not InvoiceRevision.objects.filter(invoice=still_draft).exists()
