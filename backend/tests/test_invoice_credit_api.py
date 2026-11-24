"""D-03a-T16 — the editor's credit-limit banner reads the credit check from the API: within /
warn / block with the figures and the warning; "Request override" on a blocked invoice notifies
the approvers and shows as waiting; a request on an invoice within the limit is refused.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.contacts.models import CreditOverride
from numo9.sales.posting import approve
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    for name, role in (("clerk", "admin"), ("boss", "owner")):
        user = User.objects.create_user(f"{name}@refined.ca", name=name.title())
        OrganisationMember.objects.create(organisation=books["org"], user=user, role=role)
        books[name] = user
    return books


def limit(books: dict[str, Any], amount: str, mode: str) -> None:
    customer = books["customers"]["ON"]
    with org_context(books["org"]):
        customer.credit_limit = Decimal(amount)
        customer.credit_mode = mode
        customer.save()


def client_for(user: User) -> Client:
    client = Client()
    client.force_login(user)
    return client


def url(books: dict[str, Any], invoice: Any, tail: str = "credit") -> str:
    return f"/api/v1/o/{books['org'].public_id}/invoices/{invoice.public_id}/{tail}"


def test_within_and_warn(books: dict[str, Any]) -> None:
    invoice = draft(books, [("1", "100.00", "sales.ON.standard")])
    clerk = client_for(books["clerk"])
    body = clerk.get(url(books, invoice)).json()
    assert body["outcome"] == "no_limit" and body["message"] == ""
    limit(books, "100.00", "warn")
    body = clerk.get(url(books, invoice)).json()
    assert (body["outcome"], body["limit"], body["projected"], body["over_by"]) == (
        "warn",
        "100.00",
        "113.00",
        "13.00",
    )
    assert "ON Customer Ltd" in body["message"] and body["pending_override"] is None


def test_block_then_request_override(books: dict[str, Any]) -> None:
    limit(books, "200.00", "block")
    approve(draft(books, [("1", "100.00", "sales.ON.standard")]), books["clerk"])  # owes 113.00
    invoice = draft(books, [("1", "100.00", "sales.ON.standard")])
    clerk = client_for(books["clerk"])
    body = clerk.get(url(books, invoice)).json()
    assert (body["outcome"], body["exposure"], body["amount"]) == ("block", "113.00", "113.00")
    refused = clerk.post(
        url(books, invoice, "credit/override"), {"reason": ""}, content_type="application/json"
    )
    assert refused.status_code == 400
    asked = clerk.post(
        url(books, invoice, "credit/override"),
        {"reason": "Long-standing customer, cheque in the mail"},
        content_type="application/json",
    )
    assert asked.status_code == 201, asked.json()
    assert asked.json()["pending_override"]["amount"] == "113.00"
    with org_context(books["org"]):
        override = CreditOverride.objects.get()
        assert override.document_ref == str(invoice.public_id) and override.status == "pending"
    assert clerk.get(url(books, invoice)).json()["pending_override"] is not None


def test_override_on_an_invoice_within_the_limit_is_refused(books: dict[str, Any]) -> None:
    limit(books, "1000.00", "block")
    invoice = draft(books, [("1", "100.00", "sales.ON.standard")])
    answer = client_for(books["clerk"]).post(
        url(books, invoice, "credit/override"),
        {"reason": "Just in case"},
        content_type="application/json",
    )
    assert (
        answer.status_code == 400 and answer.json()["code"] == "sales.invoice.override_not_needed"
    )
