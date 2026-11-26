"""D-03b-T07 — posting a revision: the previous revision's journal is reversed and the new one
posted in one transaction, both linked to the revision; invoice 101 at 1,130.00 revised to
1,017.00 changes AR by exactly −113.00 and the GL shows the two linked journals; a failure while
posting (fault injection) leaves no partial state — no reversal, no revision, rows unchanged."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum

from numo9.audit.models import AuditEvent
from numo9.ledger.models import JournalEntry, JournalLine
from numo9.sales import revise as revise_module
from numo9.sales.models import InvoiceRevision
from numo9.sales.posting import approve
from numo9.sales.revise import RevisionConflict, revise
from numo9.sales.revisions import build_revision
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    books["invoice"] = approve(
        draft(books, [("10", "100.00", "sales.ON.standard")]), books["owner"]
    )  # 1,000.00 + HST 130.00 = 1,130.00
    return books


def ar(books: dict[str, Any]) -> Decimal:
    with org_context(books["org"]):
        net = JournalLine.objects.filter(account__system_role="ar").aggregate(
            net=Sum("debit") - Sum("credit")
        )["net"]
    return D(net or 0)


def opened(books: dict[str, Any], quantity: str = "9", reason: str = "Nine hours, not ten") -> Any:
    with org_context(books["org"]):
        books["invoice"].refresh_from_db()
        draft_ = build_revision(books["invoice"])
    draft_.lines[0]["quantity"] = D(quantity)
    draft_.reason = reason
    return draft_


def test_reverse_and_repost_linked_to_the_revision(books: dict[str, Any]) -> None:
    invoice = books["invoice"]
    assert (invoice.total, ar(books)) == (D("1130.00"), D("1130.00"))
    first_journal = invoice.journal_entry
    revision = revise(invoice, opened(books), books["owner"])
    with org_context(books["org"]):
        invoice.refresh_from_db()
        zero = InvoiceRevision.objects.get(invoice=invoice, revision=0)
        assert (revision.revision, revision.number_display) == (1, f"{invoice.number}-1")
        assert (revision.total, revision.tax_total) == (D("1017.00"), D("117.00"))
        assert revision.reason == "Nine hours, not ten"
        assert revision.journal_reversal.reversal_of == first_journal
        assert revision.journal_post == invoice.journal_entry != first_journal
        assert zero.superseded_at is not None and revision.superseded_at is None
        assert invoice.current_revision == revision and invoice.total == D("1017.00")
        assert invoice.lines.get().quantity == D("9")
        sources = JournalEntry.objects.filter(source_id=str(invoice.public_id))
        assert sources.count() == 3  # the approval, its reversal and the revision's posting
        event = AuditEvent.objects.get(action="sales.invoice.revised")
        assert event.meta["journal_reversal"]["id"] == str(revision.journal_reversal.public_id)
        assert event.meta["journal_post"]["id"] == str(revision.journal_post.public_id)
    assert ar(books) == D("1017.00")  # AR changed by exactly −113.00

    second = revise(invoice, opened(books, "8", "Eight hours"), books["owner"])
    assert (second.revision, second.number_display) == (2, f"{invoice.number}-2")
    assert second.journal_reversal.reversal_of == revision.journal_post
    assert ar(books) == D("904.00")


def test_a_stale_draft_is_a_conflict(books: dict[str, Any]) -> None:
    stale = opened(books)
    revise(books["invoice"], opened(books, "8", "Eight"), books["owner"])
    with pytest.raises(RevisionConflict):
        revise(books["invoice"], stale, books["owner"])
    assert ar(books) == D("904.00")


def test_a_failure_while_posting_leaves_nothing(
    books: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from numo9.ledger import services

    invoice = books["invoice"]
    before_version = invoice.version

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("disk full")

    monkeypatch.setattr(services, "post_journal", broken)  # after the reversal succeeded
    with pytest.raises(RuntimeError):
        revise(invoice, opened(books), books["owner"])
    with org_context(books["org"]):
        invoice.refresh_from_db()
        assert invoice.version == before_version and invoice.total == D("1130.00")
        assert invoice.lines.get().quantity == D("10")
        assert not InvoiceRevision.objects.filter(invoice=invoice, revision=1).exists()
        assert not JournalEntry.objects.filter(reversal_of=invoice.journal_entry).exists()
        assert InvoiceRevision.objects.get(invoice=invoice, revision=0).superseded_at is None
    assert ar(books) == D("1130.00")
    assert revise_module.REVISABLE  # the module stays importable after the injected fault
