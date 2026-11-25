"""D-02-T04 — the quote lifecycle: send, view tracking, accept, decline, expire, invoice with
guarded transitions (the state table: every illegal transition raises); accepting twice is
idempotent; a view after a decision is ignored; audit events."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.sales import quotes as q
from numo9.sales.models import Quote
from numo9.tenancy.context import org_context
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
NOW = dt.datetime(2026, 6, 16, 15, tzinfo=dt.UTC)
STATUSES = ["draft", "sent", "viewed", "accepted", "declined", "expired", "invoiced"]
ACTIONS = ["send", "view", "accept", "decline", "expire", "invoice"]
# The legal moves (status, action) → new status; everything else must raise (view: ignored).
LEGAL = {
    ("draft", "send"): "sent",
    ("sent", "send"): "sent",
    ("viewed", "send"): "sent",
    ("sent", "view"): "viewed",
    ("viewed", "view"): "viewed",
    ("sent", "accept"): "accepted",
    ("viewed", "accept"): "accepted",
    ("accepted", "accept"): "accepted",
    ("sent", "decline"): "declined",
    ("viewed", "decline"): "declined",
    ("sent", "expire"): "expired",
    ("viewed", "expire"): "expired",
    ("accepted", "invoice"): "invoiced",
}


@pytest.fixture
def books() -> dict[str, Any]:
    return sales_books()


def run(item: Quote, action: str, books: dict[str, Any]) -> Quote:
    if action == "send":
        return q.send(item, now=NOW)
    if action == "view":
        return q.mark_viewed(item, now=NOW)
    if action == "accept":
        return q.accept(item, now=NOW)
    if action == "decline":
        return q.decline(item, "Too expensive", now=NOW)
    if action == "expire":
        return q.expire(item, now=NOW)
    from tests.sales_helpers import draft

    return q.mark_invoiced(item, draft(books, [("1", "10", "")]))


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("action", ACTIONS)
def test_state_table(books: dict[str, Any], status: str, action: str) -> None:
    item = quote(books, [("1", "100", "")])
    with org_context(books["org"]):
        extra: dict[str, Any] = {}
        if status == "invoiced":
            from tests.sales_helpers import draft

            extra["invoice"] = draft(books, [("1", "10", "")])
        Quote._base_manager.filter(pk=item.pk).update(status=status, **extra)
        item.refresh_from_db()
    expected = LEGAL.get((status, action))
    if expected is None and action == "view":
        assert run(item, action, books).status == status  # tracked, no transition
    elif expected is None:
        with pytest.raises(q.QuoteRefused) as err:
            run(item, action, books)
        assert err.value.code == "sales.quote.transition"
    else:
        assert run(item, action, books).status == expected


def test_full_flow_dates_and_audit(books: dict[str, Any]) -> None:
    item = quote(books, [("1", "100", "sales.ON.standard")])
    item = q.send(item, now=NOW)
    item = q.mark_viewed(item, now=NOW + dt.timedelta(hours=1))
    first_view = item.viewed_at
    item = q.mark_viewed(item, now=NOW + dt.timedelta(hours=2))
    assert item.viewed_at == first_view  # the first view is kept
    item = q.accept(item, now=NOW + dt.timedelta(hours=3))
    again = q.accept(item, now=NOW + dt.timedelta(hours=4))
    assert again.accepted_at == item.accepted_at  # idempotent
    with org_context(books["org"]):
        actions = list(
            AuditEvent.objects.filter(object_id=str(item.public_id)).values_list(
                "action", flat=True
            )
        )
    assert {"sales.quote.sent", "sales.quote.viewed", "sales.quote.accepted"} <= set(actions)
    empty = quote(books, [])
    with pytest.raises(q.QuoteRefused) as err:
        q.send(empty, now=NOW)
    assert err.value.code == "sales.quote.empty"


def test_decline_keeps_the_reason(books: dict[str, Any]) -> None:
    item = q.decline(q.send(quote(books, [("1", "5", "")]), now=NOW), "  Too expensive ", now=NOW)
    assert (item.status, item.decline_reason) == ("declined", "Too expensive")
