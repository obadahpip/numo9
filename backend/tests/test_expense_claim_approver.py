"""E-04-T11 — the approver's view: an expense claim awaiting approval is in the approvals inbox of
someone with the approve permission and a high enough limit, and as "yours" (never approvable) for
its claimant; the claim API says ``can_approve`` false for the claimant; approve and reject."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.purchases import expense_claims as flow
from numo9.rbac.models import ApprovalLimit
from numo9.tenancy.context import org_context
from tests.expense_helpers import add_line, add_trip, make_claim
from tests.journal_helpers import document
from tests.purchase_helpers import member, purchase_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = purchase_books()
    org = books["org"]
    with org_context(org):
        for user, limit in ((books["owner"], "1000"), (books["buyer"], "50")):
            ApprovalLimit.objects.create(
                user=user, doc_type="expense_claim", max_amount=Decimal(limit)
            )
        receipt = document(org, "bistro.jpg", sha256="ef" * 32)
    claimant = books["clerk"]
    claim = make_claim(org, claimant, created_by=claimant, title="Kingston client visit")
    add_line(
        claim,
        merchant="Bistro 21",
        account=books["expense"],
        amount=Decimal("56.50"),
        receipt=receipt,
    )
    add_trip(claim, "100")
    books["claim"] = flow.submit(claim, claimant)
    books["base"] = f"/api/v1/o/{org.public_id}"
    return books


def client(user: User) -> Client:
    c = Client()
    c.force_login(user)
    return c


def inbox(books: dict[str, Any], user: User) -> list[dict[str, Any]]:
    body = client(user).get(f"{books['base']}/approvals", {"kind": "expense_claim"}).json()
    return [r for r in body["results"] if r["kind"] == "expense_claim"]


def test_inbox_registration(books: dict[str, Any]) -> None:
    rows = inbox(books, books["owner"])
    assert len(rows) == 1 and rows[0]["can_approve"] is True
    assert rows[0]["subtitle"] == "EXP-0001 · Kingston client visit"
    assert rows[0]["url"].endswith(f"/purchases/expense-claims/{books['claim'].public_id}")
    assert rows[0]["amount"] == "129.50"
    assert inbox(books, books["buyer"]) == []  # above their 50.00 limit
    own = inbox(books, books["clerk"])
    assert len(own) == 1 and own[0]["can_approve"] is False and own[0]["blocked"] == "self"


def test_detail_for_claimant_and_approver(books: dict[str, Any]) -> None:
    url = f"{books['base']}/expense-claims/{books['claim'].public_id}"
    mine = client(books["clerk"]).get(url).json()
    assert (mine["can_approve"], mine["blocked"]) == (False, "self")
    theirs = client(books["owner"]).get(url).json()
    assert theirs["can_approve"] is True and theirs["number"] == "EXP-0001"
    receipt, trip = theirs["lines"]
    assert receipt["split"]["gross"] == "56.50" and receipt["receipt"]["name"] == "bistro.jpg"
    assert trip["rate_detail"][0]["rate"] == "0.73"
    assert client(books["buyer"]).get(url).json()["blocked"] == "limit"


def test_approve_and_reject_through_the_api(books: dict[str, Any]) -> None:
    url = f"{books['base']}/expense-claims/{books['claim'].public_id}"
    refused = client(books["clerk"]).post(f"{url}/approve", content_type="application/json")
    assert (
        refused.status_code == 400 and refused.json()["code"] == "purchases.expense.self_approval"
    )
    rejected = client(books["owner"]).post(
        f"{url}/reject", {"reason": "Folio missing"}, content_type="application/json"
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    flow.submit(books["claim"], books["clerk"])
    done = client(books["owner"]).post(f"{url}/approve", content_type="application/json")
    assert done.status_code == 200 and done.json()["status"] == "approved"
    assert done.json()["can_approve"] is False


def test_other_organisation_cannot_see_the_claim(books: dict[str, Any]) -> None:
    from numo9.tenancy.models import Organisation

    elsewhere = Organisation.objects.create(name="Elsewhere Inc.")
    stranger = member(elsewhere, "stranger@else.ca", "owner")
    url = f"/api/v1/o/{elsewhere.public_id}/expense-claims/{books['claim'].public_id}"
    assert client(stranger).get(url).status_code in (403, 404)
