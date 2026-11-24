"""D-03a-T05 — optional invoice approval rule: a threshold (organisation setting) or a person's
invoice approval limit (A-03) routes the invoice to Awaiting approval instead of posting; the
approver can't be its submitter or author and must be within their own limit; below the rule it
posts at once. Never product-gated: it uses only the invoices feature.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.i18n.errors import CatalogueError
from numo9.orgsettings.service import get_settings
from numo9.rbac.models import ApprovalLimit
from numo9.sales.approvals import approval_needed, approve_waiting, submit_or_approve
from numo9.sales.posting import InvoiceRefused
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    org = books["org"]
    for name, role in (("clerk", "sales"), ("boss", "owner"), ("lead", "admin")):
        user = User.objects.create_user(f"{name}@refined.ca", name=name.title())
        OrganisationMember.objects.create(organisation=org, user=user, role=role)
        books[name] = user
    return books


def threshold(books: dict[str, Any], amount: str | None) -> None:
    with org_context(books["org"]):
        settings = get_settings(books["org"])
        settings.invoice_approval_threshold = Decimal(amount) if amount else None
        settings.save()


def test_below_the_rule_posts_at_once(books: dict[str, Any]) -> None:
    threshold(books, "5000.00")
    invoice = draft(books, [("1", "100.00", "sales.ON.standard")])
    assert approval_needed(invoice, books["clerk"]) is None
    assert submit_or_approve(invoice, books["clerk"]).status == "approved"


def test_threshold_routes_to_awaiting_then_an_approver_posts(books: dict[str, Any]) -> None:
    threshold(books, "1000.00")
    invoice = draft(books, [("1", "1000.00", "sales.ON.standard")])
    assert approval_needed(invoice, books["clerk"]) == "threshold"
    waiting = submit_or_approve(invoice, books["clerk"])
    assert (waiting.status, waiting.number, waiting.submitted_by) == (
        "awaiting_approval",
        "",
        books["clerk"],
    )
    with pytest.raises(InvoiceRefused) as caught:
        approve_waiting(waiting, books["clerk"])
    assert caught.value.code == "sales.invoice.self_approval"
    approved = approve_waiting(waiting, books["boss"])
    assert (approved.status, approved.number) == ("approved", "INV-0001")


def test_a_personal_limit_routes_and_is_enforced_for_approvers(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        ApprovalLimit.objects.create(
            user=books["clerk"], doc_type="invoice", max_amount=Decimal("500")
        )
        ApprovalLimit.objects.create(
            user=books["lead"], doc_type="invoice", max_amount=Decimal("800")
        )
    small = draft(books, [("1", "400.00", "sales.ON.standard")])  # 452.00 with HST
    assert submit_or_approve(small, books["clerk"]).status == "approved"
    large = draft(books, [("1", "900.00", "sales.ON.standard")])  # 1,017.00
    assert approval_needed(large, books["clerk"]) == "limit"
    waiting = submit_or_approve(large, books["clerk"])
    assert waiting.status == "awaiting_approval"
    with pytest.raises(CatalogueError):
        approve_waiting(waiting, books["lead"])  # 1,017.00 > the lead's 800.00
    assert approve_waiting(waiting, books["boss"]).status == "approved"  # no limit set: free


def test_only_waiting_invoices_are_approved_this_way(books: dict[str, Any]) -> None:
    invoice = draft(books, [("1", "10.00", "sales.ON.standard")])
    with pytest.raises(InvoiceRefused) as caught:
        approve_waiting(invoice, books["boss"])
    assert caught.value.code == "sales.invoice.not_awaiting"
