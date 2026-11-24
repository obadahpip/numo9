"""E-01-T02 — PO numbering PO-0001 and approval with the A-03 purchase-order limits: a buyer with
a 5,000 limit approves 5,000 but not 5,001 (403 naming who may); the PO goes to Awaiting
approval instead and someone within their limit approves it — never its author; approval takes
the next number, keeps the approved total and is audited; no limit → no approval.
"""

from __future__ import annotations

from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.purchases.approvals import PurchaseOrderRefused, approve, submit_or_approve
from numo9.rbac.approvals import ApprovalLimitExceeded
from numo9.tenancy.context import org_context
from tests.purchase_helpers import po, purchase_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return purchase_books()


def test_limit_5000_approves_5000_not_5001(books: dict[str, Any]) -> None:
    at_limit = po(books, [("1", "5000.00")], user=books["buyer"])
    approved = approve(at_limit, books["buyer"])
    assert (approved.status, approved.number, approved.approved_total) == (
        "approved",
        "PO-0001",
        approved.total,
    )
    assert approved.approved_by == books["buyer"]
    over = po(books, [("1", "5001.00")], user=books["buyer"])
    with pytest.raises(ApprovalLimitExceeded) as refused:
        approve(over, books["buyer"])
    assert refused.value.get_codes() == "approval.limit_exceeded"
    assert [a.name for a in refused.value.next_approvers] == ["Owner"]
    with org_context(books["org"]):
        over.refresh_from_db()
        assert (over.status, over.number) == ("draft", "")  # the number went back


def test_over_the_limit_waits_for_an_approver(books: dict[str, Any]) -> None:
    order = po(books, [("2", "3000.00")], user=books["buyer"])
    waiting = submit_or_approve(order, books["buyer"])
    assert (waiting.status, waiting.submitted_by) == ("awaiting_approval", books["buyer"])
    with pytest.raises(PurchaseOrderRefused) as own:
        approve(waiting, books["buyer"])
    assert own.value.code == "purchases.po.self_approval"
    approved = approve(waiting, books["owner"])
    assert (approved.status, approved.number) == ("approved", "PO-0001")
    with org_context(books["org"]):
        assert AuditEvent.objects.filter(action="purchases.purchaseorder.approved").count() == 1
    within = submit_or_approve(po(books, [("1", "100.00")], user=books["buyer"]), books["buyer"])
    assert (within.status, within.number) == ("approved", "PO-0002")


def test_no_limit_means_no_approval(books: dict[str, Any]) -> None:
    order = po(books, [("1", "10.00")], user=books["buyer"])
    with pytest.raises(ApprovalLimitExceeded) as refused:
        approve(order, books["clerk"])
    assert refused.value.get_codes() == "approval.no_limit"
    assert submit_or_approve(order, books["clerk"]).status == "awaiting_approval"


def test_empty_po_is_refused(books: dict[str, Any]) -> None:
    with pytest.raises(PurchaseOrderRefused) as refused:
        approve(po(books, []), books["owner"])
    assert refused.value.code == "purchases.po.empty"


def test_taxed_po_totals(books: dict[str, Any]) -> None:
    order = po(books, [("10", "25.00")], tax="purchase.ON.standard")
    assert (order.subtotal, order.tax_total, order.total) == (250, 32.5, 282.5)
