"""D-02-T14 (gap-05) — one Quote status vocabulary and one count: the list's ``counts`` are
``quotes.status_counts()`` (the overview card's source), its ``tabs`` are summed from them (Sent
covers sent and viewed), and each tab and each status filter lists exactly as many quotes as it
counts."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client

from numo9.sales import quotes as q
from numo9.sales.models import QuoteStatus
from numo9.sales.quote_invoicing import convert_to_invoice
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
TODAY = dt.date.today()


def made(books: dict[str, Any], status: str) -> Any:
    item = quote(books, [("1", "100", "sales.ON.standard")], date=TODAY)
    if status == "draft":
        return item
    item = q.send(item)
    steps: dict[str, list[Any]] = {
        "viewed": [q.mark_viewed],
        "accepted": [q.accept],
        "declined": [q.decline],
        "expired": [q.expire],
        "invoiced": [q.accept, lambda x: convert_to_invoice(x) and x],
    }
    for step in steps.get(status, []):
        item = step(item) or item
    return item


def test_tabs_counts_and_filters_agree() -> None:
    books = sales_books()
    wanted = {"draft": 2, "sent": 1, "viewed": 2, "accepted": 1, "declined": 1, "expired": 3}
    wanted["invoiced"] = 1
    for status, n in wanted.items():
        for _ in range(n):
            made(books, status)
    client = Client()
    client.force_login(people(books["org"])["owner"])
    base = f"/api/v1/o/{books['org'].public_id}/quotes"
    body = client.get(base).json()
    with org_context(books["org"]):
        overview = q.status_counts()
    assert list(body["counts"]) == list(QuoteStatus.values)
    assert body["counts"] == overview == wanted
    assert body["tabs"] == {
        "all": 11,
        "draft": 2,
        "sent": 3,
        "accepted": 1,
        "declined": 1,
        "expired": 3,
        "invoiced": 1,
    }
    for tab, n in body["tabs"].items():
        assert client.get(base, {"tab": tab}).json()["count"] == n, tab
    for status, n in body["counts"].items():
        assert client.get(base, {"status": status}).json()["count"] == n, status
    assert body["tabs"] == q.tab_counts(overview)
