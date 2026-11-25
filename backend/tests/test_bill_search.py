"""E-02-T16 — bills in the global search: found by the supplier invoice number (and its parts),
the bill number once approved (a code), the supplier and the amount; drafts say "Draft bill";
the result opens the bill; people without the bills permission don't see it."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.purchases.bill_posting import approve
from numo9.tenancy.models import Organisation
from tests.bill_helpers import bill, bill_books, member

pytestmark = pytest.mark.django_db


def search(org: Organisation, user: User, q: str) -> list[dict[str, Any]]:
    client = Client()
    client.force_login(user)
    body = client.get(f"/api/v1/o/{org.public_id}/search", {"q": q}).json()
    return [r for r in body["records"] if r["type"] == "purchases.bill"]


@pytest.fixture
def books() -> dict[str, Any]:
    return bill_books()


def test_bill_found_by_supplier_invoice_number(books: dict[str, Any]) -> None:
    org, owner = books["org"], books["owner"]
    draft = bill(books, [("1", "339.00")], supplier_invoice_no="CS-77812")
    (hit,) = search(org, owner, "CS-77812")
    assert hit["title"] == "Draft bill — Cedar Supply Co."
    assert hit["url"] == f"/o/{org.public_id}/purchases/bills/{draft.public_id}"
    assert search(org, owner, "77812")
    assert search(org, owner, "Cedar Supply")
    approve(draft, owner)
    (numbered,) = search(org, owner, "BILL-0001")
    assert numbered["title"] == "BILL-0001 — Cedar Supply Co."
    assert "CS-77812" in numbered["subtitle"]
    assert search(org, owner, "BILL-00")
    assert search(org, owner, "$339.00")


def test_hidden_without_the_permission(books: dict[str, Any]) -> None:
    bill(books, [("1", "10.00")], supplier_invoice_no="Z-9")
    hr = member(books["org"], "hr@refined.ca", "hr")
    assert search(books["org"], hr, "Z-9") == []
