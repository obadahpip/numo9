"""E-01-T15 — purchase orders in the approvals inbox: an approver sees a PO awaiting approval only
when it is within their purchase-order limit; its buyer sees it flagged "self"; someone without a
limit or the approve permission sees only their own; approving from the inbox's id works.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.purchases.approvals import approve, submit_or_approve
from numo9.rbac.inbox import approvables
from tests.purchase_helpers import member, po, purchase_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = purchase_books()
    books["lead"] = member(books["org"], "lead@refined.ca", "admin", "20000")
    buyer = books["clerk"]  # no limit: everything goes for approval
    books["small"] = submit_or_approve(po(books, [("1", "4000.00")], user=buyer), buyer)
    books["large"] = submit_or_approve(po(books, [("1", "15000.00")], user=buyer), buyer)
    return books


def inbox(books: dict[str, Any], user: User) -> list[dict[str, Any]]:
    client = Client()
    client.force_login(user)
    body = client.get(
        f"/api/v1/o/{books['org'].public_id}/approvals", {"kind": "purchase_order"}
    ).json()
    return [r for r in body["results"] if r["kind"] == "purchase_order"]


def amounts(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(r["amount"] for r in rows)


def test_registered() -> None:
    registered = approvables.get("purchase_order")
    assert registered is not None and registered.permission == "purchases.orders.approve"


def test_approvers_see_only_what_is_within_their_limit(books: dict[str, Any]) -> None:
    assert amounts(inbox(books, books["buyer"])) == ["4000.00"]  # limit 5 000
    assert amounts(inbox(books, books["lead"])) == ["15000.00", "4000.00"]  # limit 20 000
    [row] = inbox(books, books["buyer"])
    assert row["can_approve"] is True and row["title"] == "Cedar Supply Co."
    assert row["url"].endswith(f"/purchases/orders/{books['small'].public_id}")


def test_the_buyer_sees_their_own_flagged_self(books: dict[str, Any]) -> None:
    rows = inbox(books, books["clerk"])
    assert amounts(rows) == ["15000.00", "4000.00"]
    assert {(r["can_approve"], r["blocked"]) for r in rows} == {(False, "self")}


def test_approved_po_leaves_the_inbox(books: dict[str, Any]) -> None:
    approve(books["small"], books["buyer"])
    assert inbox(books, books["buyer"]) == []
