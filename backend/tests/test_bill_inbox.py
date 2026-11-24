"""E-02-T14 — bills in the approvals inbox: a bill awaiting approval appears for the people of
the role it is routed to (within their bill approval limit) with the routing explanation, not for
others; its writer sees it as theirs, never approvable; with no rule, the approval limit decides."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.purchases.models import ApprovalRoutingRule
from numo9.purchases.routing import submit
from numo9.rbac.inbox import approvables
from numo9.rbac.models import ApprovalLimit, Role, RoleAssignment
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books, member

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    org = books["org"]
    finance = Role.objects.create(scope="organisation", organisation=org, name="Finance", key="")
    controller = member(org, "controller@refined.ca", "admin")
    RoleAssignment.objects.create(role=finance, user=controller, organisation=org)
    with org_context(org):
        ApprovalLimit.objects.create(user=controller, doc_type="bill", max_amount=Decimal("50000"))
        ApprovalRoutingRule(
            organisation=org, name="Large", min_amount=Decimal("2000"), approver_role=finance
        ).save()
    clerk = books["clerk"]
    books["large"] = submit(
        bill(books, [("1", "3000.00")], user=clerk, supplier_invoice_no="I-1"), clerk
    )
    books["small"] = submit(
        bill(books, [("1", "100.00")], user=clerk, supplier_invoice_no="I-2"), clerk
    )
    return {**books, "controller": controller}


def inbox(books: dict[str, Any], user: User) -> list[dict[str, Any]]:
    client = Client()
    client.force_login(user)
    body = client.get(f"/api/v1/o/{books['org'].public_id}/approvals", {"kind": "bill"}).json()
    return [r for r in body["results"] if r["kind"] == "bill"]


def test_registered() -> None:
    registered = approvables.get("bill")
    assert registered is not None and registered.permission == "purchases.bills.approve"


def test_a_routed_bill_appears_for_its_group_only(books: dict[str, Any]) -> None:
    controller = {r["id"]: r for r in inbox(books, books["controller"])}
    assert set(controller) == {str(books["large"].public_id), str(books["small"].public_id)}
    large = controller[str(books["large"].public_id)]
    assert large["can_approve"] is True
    assert large["subtitle"] == "I-1 · Routed to Finance approvers (amount over $2,000.00)"
    assert large["url"].endswith(f"/purchases/bills/{books['large'].public_id}")
    owner = {r["id"] for r in inbox(books, books["owner"])}  # limit 100,000, but not in Finance
    assert owner == {str(books["small"].public_id)}  # no rule on the small one: the limit decides
    buyer = {r["id"] for r in inbox(books, books["buyer"])}  # limit 5,000, not in Finance
    assert buyer == {str(books["small"].public_id)}


def test_the_writer_sees_theirs_never_approvable(books: dict[str, Any]) -> None:
    rows = inbox(books, books["clerk"])
    assert len(rows) == 2 and all(r["can_approve"] is False for r in rows)
