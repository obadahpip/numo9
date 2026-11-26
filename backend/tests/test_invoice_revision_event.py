"""D-03b-T17 — every saved revision stores the event ``invoice.revised`` in the outbox, once per
revision (its key is the revision's id: emitting it again stores nothing new), with what W-01
webhooks and the mobile app need; a revision that fails leaves no event."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.jobs.models import OutboxEvent
from numo9.jobs.outbox import emit, mark_dispatched, pending
from numo9.sales.models import InvoiceRevision
from numo9.sales.posting import approve
from numo9.sales.revise import REVISED_EVENT, emit_revised, revise
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
    )
    return books


def opened(books: dict[str, Any], quantity: str, reason: str) -> Any:
    with org_context(books["org"]):
        books["invoice"].refresh_from_db()
        draft_ = build_revision(books["invoice"])
    draft_.lines[0]["quantity"] = D(quantity)
    draft_.reason = reason
    return draft_


def events(books: dict[str, Any]) -> list[OutboxEvent]:
    with org_context(books["org"]):
        return list(OutboxEvent.objects.filter(event_type=REVISED_EVENT).order_by("pk"))


def test_one_event_per_revision(books: dict[str, Any]) -> None:
    invoice = books["invoice"]
    first = revise(invoice, opened(books, "9", "Nine hours"), books["owner"])
    second = revise(invoice, opened(books, "8", "Eight hours"), books["owner"])
    stored = events(books)
    assert [e.key for e in stored] == [
        f"invoice.revised:{first.public_id}",
        f"invoice.revised:{second.public_id}",
    ]
    event = stored[0]
    assert (event.aggregate_type, event.aggregate_id) == ("sales.invoice", str(invoice.public_id))
    assert event.payload["number_display"] == f"{invoice.number}-1"
    assert event.payload["supersedes"] == invoice.number
    assert (event.payload["total"], event.payload["previous_total"]) == ("1017.00", "1130.00")
    assert event.payload["reason"] == "Nine hours"
    assert event.payload["journal_post"] == str(first.journal_post.public_id)
    assert stored[1].payload["supersedes"] == f"{invoice.number}-1"

    with org_context(books["org"]):
        invoice.refresh_from_db()
        previous = InvoiceRevision.objects.get(invoice=invoice, revision=0)
        again = emit_revised(invoice, first, previous)  # a replay of the same revision
    assert again.pk == event.pk and len(events(books)) == 2


def test_a_failed_revision_leaves_no_event(
    books: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from numo9.ledger import services

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("disk full")

    monkeypatch.setattr(services, "post_journal", broken)
    with pytest.raises(RuntimeError):
        revise(books["invoice"], opened(books, "9", "Nine hours"), books["owner"])
    assert events(books) == []


def test_outbox_is_idempotent_and_relayed(books: dict[str, Any]) -> None:
    org = books["org"]
    made = emit(org, "test.event", key="k-1", aggregate=("x", "1"), payload={"a": 1})
    same = emit(org, "test.event", key="k-1", aggregate=("x", "1"), payload={"a": 2})
    assert same.pk == made.pk and same.payload == {"a": 1}
    assert made in pending()
    mark_dispatched(made)
    assert made not in pending()
