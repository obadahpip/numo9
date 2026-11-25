"""D-02-T16 — quotes in the global search: found by number (a code, prefix), contact, title and
amount; the result opens the quote; results follow ``sales.quotes.view``."""

from __future__ import annotations

from typing import Any

import pytest

from numo9.search.reindex import drift
from numo9.tenancy.context import org_context
from tests.quote_helpers import quote, sales_books
from tests.test_invoice_search import member, search

pytestmark = pytest.mark.django_db
KIND = "sales.quote"


def hits(org: Any, user: Any, q: str) -> list[dict[str, Any]]:
    import tests.test_invoice_search as invoice_search

    previous = invoice_search.KIND
    invoice_search.KIND = KIND
    try:
        return search(org, user, q)
    finally:
        invoice_search.KIND = previous


def test_found_by_number_contact_title_amount_and_permission() -> None:
    books = sales_books()
    org = books["org"]
    owner = member(org, "owner@refined.ca", "owner")
    item = quote(books, [("2", "150.00", "sales.ON.standard")], title="Boardroom tables")
    (hit,) = hits(org, owner, "QU-0001")
    assert hit["title"] == "QU-0001 — ON Customer Ltd" and hit["match"] == "code"
    assert "Draft" in hit["subtitle"] and "Boardroom tables" in hit["subtitle"]
    assert hit["url"] == f"/o/{org.public_id}/sales/quotes/{item.public_id}"
    assert hits(org, owner, "QU-00")
    assert hits(org, owner, "ON Customer")
    assert hits(org, owner, "Boardroom")
    assert hits(org, owner, "$339.00")
    nobody = member(org, "employee@refined.ca", "employee")
    assert hits(org, nobody, "QU-0001") == []
    with org_context(org):
        assert drift(org).consistent
