"""D-02-T06 — public quote link: signed, works without signing in, counts views and moves a sent
quote to Viewed; a tampered token is 404, a revoked link 410; an expired quote can't be accepted
(reason ``expired``); a revised quote shows ``superseded``."""

from __future__ import annotations

import datetime as dt

import pytest
from django.test import Client

from numo9.sales import quotes as q
from numo9.sales.models import QuoteLink
from numo9.sales.quote_links import issue_link, revoke_link
from numo9.tenancy.context import org_context
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
TODAY = dt.date.today()


def test_link_without_login_views_and_revoke() -> None:
    books = sales_books()
    item = q.send(
        quote(
            books,
            [("1", "100", "sales.ON.standard"), {"price": "40", "is_optional": True}],
            date=TODAY,
            expiry=TODAY + dt.timedelta(days=30),
            title="Kitchen renovation",
        )
    )
    link, token = issue_link(item)
    client = Client()  # anonymous
    first = client.get(f"/api/v1/q/{token}")
    assert first.status_code == 200, first.content
    body = first.json()
    assert (body["number"], body["title"], body["status"]) == (
        "QU-0001",
        "Kitchen renovation",
        "viewed",
    )
    assert body["can_accept"] is True and body["reason"] is None
    assert [(line["is_optional"], line["counted"]) for line in body["lines"]] == [
        (False, True),
        (True, False),
    ]
    assert body["total"] == "113.00"
    client.get(f"/api/v1/q/{token}")
    with org_context(books["org"]):
        link.refresh_from_db()
    assert link.views == 2 and link.last_viewed_at is not None
    assert client.get(f"/api/v1/q/{token[:-2]}xx").status_code == 404
    revoke_link(link)
    gone = client.get(f"/api/v1/q/{token}")
    assert gone.status_code == 410 and gone.json()["code"] == "sales.quote.link_revoked"


def test_expired_and_superseded_reasons() -> None:
    books = sales_books()
    old = q.send(
        quote(
            books,
            [("1", "100", "")],
            date=TODAY - dt.timedelta(days=40),
            expiry=TODAY - dt.timedelta(days=10),
        )
    )
    _link, token = issue_link(old)
    body = Client().get(f"/api/v1/q/{token}").json()
    assert (body["can_accept"], body["reason"]) == (False, "expired")
    current = q.send(
        quote(books, [("1", "100", "")], date=TODAY, expiry=TODAY + dt.timedelta(days=5))
    )
    _l, current_token = issue_link(current)
    quote(
        books, [("1", "90", "")], date=TODAY, expiry=TODAY + dt.timedelta(days=5), revises=current
    )
    body = Client().get(f"/api/v1/q/{current_token}").json()
    assert body["reason"] == "superseded"
    with org_context(books["org"]):
        assert QuoteLink.objects.count() == 2
