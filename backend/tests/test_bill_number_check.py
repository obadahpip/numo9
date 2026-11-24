"""E-02-T02 — live supplier-invoice-number check (gap-24): a number already on another bill of
the same supplier is refused at entry with the bill it is on; the same number from another
supplier, the bill being edited itself and a void or deleted bill don't count."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    client = Client()
    client.force_login(books["owner"])
    return {
        **books,
        "client": client,
        "url": f"/api/v1/o/{books['org'].public_id}/bills/check-number",
    }


def check(books: dict[str, Any], number: str, supplier: str = "supplier", **extra: str) -> Any:
    answer = books["client"].get(
        books["url"],
        {"supplier": str(books[supplier].public_id), "number": number, **extra},
    )
    assert answer.status_code == 200, answer.json()
    return answer.json()


@pytest.mark.gap("gap-24")
def test_a_used_number_is_blocked_at_entry_with_its_bill(books: dict[str, Any]) -> None:
    first = bill(books, [("1", "10.00")], supplier_invoice_no="INV-7")
    assert check(books, "INV-8") == {"number": "INV-8", "available": True, "conflict": None}
    taken = check(books, " inv-7 ")
    assert taken["available"] is False
    assert taken["conflict"]["id"] == str(first.public_id)
    assert (
        taken["conflict"]["url"] == f"/o/{books['org'].public_id}/purchases/bills/{first.public_id}"
    )
    assert taken["conflict"]["message"] == "Already used on a draft bill (15 Jun 2026)"
    assert check(books, "INV7")["available"] is True  # another format, another number
    assert check(books, "INV-7", supplier="other")["available"] is True
    assert check(books, "INV-7", exclude=str(first.public_id))["available"] is True
    with org_context(books["org"]):
        first.soft_delete()
    assert check(books, "INV-7")["available"] is True


def test_empty_number_and_permissions(books: dict[str, Any]) -> None:
    assert check(books, "")["available"] is True
    clerk = Client()
    clerk.force_login(books["clerk"])
    assert clerk.get(books["url"], {"number": "x"}).status_code == 200  # admins see bills
    other = Client()
    from tests.purchase_helpers import member

    other.force_login(member(books["org"], "hr@refined.ca", "hr"))
    assert other.get(books["url"], {"number": "x"}).status_code == 403
