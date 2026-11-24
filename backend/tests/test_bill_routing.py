"""E-02-T07 — approval routing rules: amount bands × department → approver role, first match in
order, with the explanation string; approval is refused to people outside the routed role;
submit sends a draft to Awaiting approval."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.purchases.bill_posting import BillRefused, approve
from numo9.purchases.models import ApprovalRoutingRule, BillStatus
from numo9.purchases.routing import may_approve, route, submit
from numo9.rbac.models import ApprovalLimit, Role, RoleAssignment
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books, member

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    org = books["org"]
    finance = Role.objects.create(scope="organisation", organisation=org, name="Finance", key="")
    ops = Role.objects.create(scope="organisation", organisation=org, name="Operations", key="")
    controller = member(org, "controller@refined.ca", "admin")
    RoleAssignment.objects.create(role=finance, user=controller, organisation=org)
    with org_context(org):
        ApprovalLimit.objects.create(user=controller, doc_type="bill", max_amount=Decimal("50000"))
        rules = [
            ApprovalRoutingRule(
                name="Ops small",
                position=1,
                max_amount=Decimal("2000"),
                department="Operations",
                approver_role=ops,
            ),
            ApprovalRoutingRule(
                name="Finance large", position=2, min_amount=Decimal("2000"), approver_role=finance
            ),
        ]
        for rule in rules:
            rule.organisation = org
            rule.save()
    return {**books, "finance": finance, "ops": ops, "controller": controller}


@pytest.mark.parametrize(
    ("amount", "department", "expected", "explanation"),
    [
        (
            "1999.99",
            "Operations",
            "Ops small",
            "Routed to Operations approvers (amount up to $2,000.00, department Operations)",
        ),
        (
            "2000.00",
            "Operations",
            "Ops small",
            "Routed to Operations approvers (amount up to $2,000.00, department Operations)",
        ),
        (
            "2000.01",
            "Operations",
            "Finance large",
            "Routed to Finance approvers (amount over $2,000.00)",
        ),
        ("2000.00", "Sales", None, ""),
        ("15000.00", "", "Finance large", "Routed to Finance approvers (amount over $2,000.00)"),
        (
            "150.00",
            "operations",
            "Ops small",
            "Routed to Operations approvers (amount up to $2,000.00, department Operations)",
        ),
    ],
)
def test_thresholds_and_explanation(
    books: dict[str, Any], amount: str, department: str, expected: str | None, explanation: str
) -> None:
    draft = bill(books, [("1", amount)], department=department)
    routing = route(draft)
    assert (routing.rule.name if routing.rule else None) == expected
    assert routing.explanation == explanation


def test_only_the_routed_role_approves(books: dict[str, Any]) -> None:
    big = bill(books, [("1", "3000.00")], supplier_invoice_no="R-1")
    assert not may_approve(big, books["owner"])  # an owner, but not in Finance
    with pytest.raises(BillRefused) as refused:
        approve(big, books["owner"])
    assert refused.value.code == "purchases.bill.not_routed_to_you"
    assert "Routed to Finance approvers" in str(refused.value.messages[0])
    assert approve(big, books["controller"]).status == BillStatus.AWAITING_PAYMENT
    small = bill(books, [("1", "100.00")], supplier_invoice_no="R-2", department="Sales")
    assert may_approve(small, books["owner"])  # no rule: the approval limit decides


def test_submit_sends_a_draft_to_awaiting_approval(books: dict[str, Any]) -> None:
    draft = bill(books, [("1", "3000.00")], supplier_invoice_no="R-3", user=books["buyer"])
    sent = submit(draft, books["buyer"])
    assert (sent.status, sent.submitted_by) == (BillStatus.AWAITING_APPROVAL, books["buyer"])
    with pytest.raises(BillRefused):
        submit(sent, books["buyer"])
    assert approve(sent, books["controller"]).status == BillStatus.AWAITING_PAYMENT


def test_inactive_rules_are_skipped(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        ApprovalRoutingRule.objects.filter(name="Finance large").update(is_active=False)
    assert route(bill(books, [("1", "9000.00")])).rule is None
