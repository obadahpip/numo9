"""D-03a-T06 — invoices and the customer's credit limit: approved invoices make the exposure;
warn mode posts with a warning; block mode refuses without an override and posts with an
approved override for that invoice (used once); the check for the editor changes nothing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.contacts.credit import (
    CreditLimitBlocked,
    approve_override,
    exposure,
    request_override,
)
from numo9.sales.credit import invoice_credit
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


def limit(books: dict[str, Any], amount: str, mode: str) -> Any:
    customer = books["customers"]["ON"]
    with org_context(books["org"]):
        customer.credit_limit = Decimal(amount)
        customer.credit_mode = mode
        customer.save()
    return customer


def test_exposure_counts_posted_invoices_only(books: dict[str, Any]) -> None:
    customer = books["customers"]["ON"]
    approve(draft(books, [("1", "100.00", "sales.ON.standard")]), books["clerk"])  # 113.00
    draft(books, [("1", "999.00", "sales.ON.standard")])  # a draft: not owed
    with org_context(books["org"]):
        assert exposure(customer) == Decimal("113.00")


def test_warn_posts_with_the_warning(books: dict[str, Any]) -> None:
    limit(books, "100.00", "warn")
    invoice = draft(books, [("1", "100.00", "sales.ON.standard")])
    check = invoice_credit(invoice)
    assert check.outcome == "warn" and "ON Customer Ltd" in check.message
    approved = approve(invoice, books["clerk"])
    assert approved.status == "approved" and approved.credit_warning  # type: ignore[attr-defined]


def test_block_refuses_then_an_approved_override_lets_it_post_once(books: dict[str, Any]) -> None:
    customer = limit(books, "200.00", "block")
    approve(draft(books, [("1", "100.00", "sales.ON.standard")]), books["clerk"])  # owes 113.00
    invoice = draft(books, [("1", "100.00", "sales.ON.standard")])  # +113.00 → 226.00
    assert invoice_credit(invoice).outcome == "block"
    with pytest.raises(CreditLimitBlocked):
        approve(invoice, books["clerk"])
    with org_context(books["org"]):
        invoice.refresh_from_db()
        assert (invoice.status, invoice.number) == ("draft", "")
        override = request_override(
            customer,
            Decimal("113.00"),
            user=books["clerk"],
            reason="Long-standing customer, cheque in the mail",
            document_type="invoice",
            document_ref=str(invoice.public_id),
        )
        approve_override(override, books["boss"])
    assert invoice_credit(invoice).outcome == "override"
    assert approve(invoice, books["clerk"]).status == "approved"
    another = draft(books, [("1", "10.00", "sales.ON.standard")])
    with pytest.raises(CreditLimitBlocked):  # the override was for one invoice, used once
        approve(another, books["clerk"])
