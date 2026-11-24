"""D-03a-T17 — invoices in the global search: found by number (a code), contact, reference and
amount; a draft says so and gets its number when approved; results follow the invoice
permission.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.sales.posting import approve
from numo9.search.reindex import drift
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db
KIND = "sales.invoice"


def member(org: Organisation, email: str, role: str) -> User:
    user = User.objects.create_user(email, name=email.split("@")[0])
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


def search(org: Organisation, user: User, q: str) -> list[dict[str, Any]]:
    client = Client()
    client.force_login(user)
    body = client.get(f"/api/v1/o/{org.public_id}/search", {"q": q}).json()
    return [r for r in body["records"] if r["type"] == KIND]


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books["owner"] = member(books["org"], "owner@refined.ca", "owner")
    return books


def test_found_by_number_contact_reference_and_amount(books: dict[str, Any]) -> None:
    org, owner = books["org"], books["owner"]
    invoice = draft(books, [("2", "150.00", "sales.ON.standard")], reference="PO-77812")
    (hit,) = search(org, owner, "PO-77812")
    assert search(org, owner, "77812")
    assert hit["title"] == "Draft invoice — ON Customer Ltd" and "Draft" in hit["subtitle"]
    approved = approve(invoice, owner)
    (hit,) = search(org, owner, "INV-0001")
    assert hit["title"] == "INV-0001 — ON Customer Ltd"
    assert hit["code"] == "INV-0001" and hit["match"] == "code"
    assert hit["url"] == f"/o/{org.public_id}/sales/invoices/{approved.public_id}/email"
    assert search(org, owner, "INV-00")  # number prefix
    assert search(org, owner, "ON Customer")
    (by_amount,) = search(org, owner, "$339.00")
    assert by_amount["match"] == "amount"
    with org_context(org):
        assert drift(org).consistent


def test_results_need_the_invoice_permission(books: dict[str, Any]) -> None:
    org = books["org"]
    draft(books, [("1", "10.00", "sales.ON.standard")], reference="PO-1")
    assert search(org, books["owner"], "PO-1")
    nobody = member(org, "employee@refined.ca", "employee")
    assert search(org, nobody, "PO-1") == []
