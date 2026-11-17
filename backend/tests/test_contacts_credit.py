"""Credit limit check service (B-01-T13, gap-20). Acceptance: block mode requires an approver.

Covers: no limit, within, exactly at the limit, warn (allowed + message), block (refused with
the approvers in the body), exposure from registered sources (and ``exclude`` for a revised
document), override request (reason required, nobody to approve, approvers notified), approval
(permission, never the requester, once only, expiry), the approval used once for its document
and amount, decline, French message, input validation.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.utils import timezone, translation

from numo9.accounts.models import User
from numo9.contacts import credit
from numo9.contacts.credit import (
    CreditLimitBlocked,
    approve_override,
    assert_credit,
    check_credit,
    register_exposure,
    reject_override,
    request_override,
)
from numo9.contacts.models import Contact, CreditOverride, CreditOverrideStatus
from numo9.i18n.errors import CatalogueError
from numo9.notifications.models import Notification
from numo9.rbac.duties import SelfApprovalRefused
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

from .contact_helpers import contact

pytestmark = pytest.mark.django_db

INVOICE = "invoice"
OWED: dict[int, Decimal] = {}


def _owed(item: Contact, *, exclude: str = "") -> Decimal:
    return OWED.get(item.pk, Decimal("0")) - (Decimal("100") if exclude == "INV-9" else 0)


@pytest.fixture(autouse=True)
def receivables() -> Iterator[None]:
    OWED.clear()
    register_exposure("test.invoices", _owed)
    yield
    credit.unregister_exposure("test.invoices")


def member(org: Organisation, role: str, email: str, name: str) -> User:
    user = User.objects.create_user(email=email, password="x" * 12, name=name)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def owner(org: Organisation) -> User:
    return member(org, "owner", "olivia@refined.ca", "Olivia Tremblay")


@pytest.fixture
def clerk(org: Organisation) -> User:
    return member(org, "sales", "sam@refined.ca", "Sam Patel")


def customer(org: Organisation, limit: str | None, mode: str = "block", owed: str = "0") -> Contact:
    item = contact(
        org,
        "Maple Leaf Supplies",
        credit_limit=None if limit is None else Decimal(limit),
        credit_mode=mode,
    )
    OWED[item.pk] = Decimal(owed)
    return item


def test_no_limit_lets_everything_through(org: Organisation) -> None:
    item = customer(org, None, owed="1000000")
    check = check_credit(item, Decimal("999999.99"))
    assert check.outcome == "no_limit" and check.allowed and check.message == ""


def test_within_and_exactly_at_the_limit(org: Organisation) -> None:
    item = customer(org, "5000.00", owed="4000.00")
    assert check_credit(item, Decimal("999.99")).outcome == "within"
    at_limit = check_credit(item, Decimal("1000.00"))
    assert at_limit.outcome == "within" and at_limit.over_by == 0


def test_warn_mode_allows_with_a_message(org: Organisation) -> None:
    item = customer(org, "5000.00", mode="warn", owed="4500.00")
    check = assert_credit(item, Decimal("700.00"), document_type=INVOICE)
    assert check.outcome == "warn" and check.allowed
    assert check.projected == Decimal("5200.00") and check.over_by == Decimal("200.00")
    assert check.message == (
        "This takes Maple Leaf Supplies to $5,200.00, $200.00 over its credit limit of $5,000.00."
    )


@pytest.mark.gap("gap-20")
def test_block_mode_requires_an_approver(org: Organisation, owner: User, clerk: User) -> None:
    item = customer(org, "5000.00", owed="4500.00")
    with pytest.raises(CreditLimitBlocked) as refused:
        assert_credit(item, Decimal("700.00"), user=clerk, document_type=INVOICE)
    error = refused.value
    assert error.extra is not None
    assert error.status_code == 409 and error.get_codes() == "contact.credit_limit_blocked"
    assert error.extra["over_by"] == "200.00" and error.extra["limit"] == "5000.00"
    assert [a["name"] for a in error.extra["approvers"]] == ["Olivia Tremblay"]

    request = request_override(
        item,
        Decimal("700.00"),
        user=clerk,
        reason="Paid by cheque, clearing Friday",
        document_type=INVOICE,
        document_ref="INV-1",
    )
    with pytest.raises(CreditLimitBlocked):  # still waiting
        assert_credit(
            item, Decimal("700.00"), user=clerk, document_type=INVOICE, document_ref="INV-1"
        )

    approve_override(request, owner, "OK this once")
    check = assert_credit(
        item, Decimal("700.00"), user=clerk, document_type=INVOICE, document_ref="INV-1"
    )
    assert check.outcome == "override" and check.allowed
    request.refresh_from_db()
    assert request.status == CreditOverrideStatus.USED and request.used_at is not None
    assert request.decided_by == owner
    with pytest.raises(CreditLimitBlocked):  # used once
        assert_credit(
            item, Decimal("700.00"), user=clerk, document_type=INVOICE, document_ref="INV-1"
        )


def test_approval_covers_its_document_and_amount_only(
    org: Organisation, owner: User, clerk: User
) -> None:
    item = customer(org, "5000.00", owed="4500.00")
    request = request_override(
        item,
        Decimal("700.00"),
        user=clerk,
        reason="Big order",
        document_type=INVOICE,
        document_ref="INV-1",
    )
    approve_override(request, owner)
    for amount, ref in ((Decimal("800.00"), "INV-1"), (Decimal("700.00"), "INV-2")):
        with pytest.raises(CreditLimitBlocked):
            assert_credit(item, amount, user=clerk, document_type=INVOICE, document_ref=ref)
    with pytest.raises(CreditLimitBlocked):
        assert_credit(item, Decimal("700.00"), user=clerk, document_type="sales_order")
    assert (
        assert_credit(
            item, Decimal("650.00"), user=clerk, document_type=INVOICE, document_ref="INV-1"
        ).outcome
        == "override"
    )


def test_revised_document_is_not_counted_twice(org: Organisation) -> None:
    item = customer(org, "5000.00", owed="5000.00")  # includes INV-9 for $100
    assert check_credit(item, Decimal("100.00"), document_ref="INV-9").outcome == "within"
    assert check_credit(item, Decimal("100.00")).outcome == "block"


def test_requester_cannot_approve_their_own_request(org: Organisation, owner: User) -> None:
    other = member(org, "admin", "alex@refined.ca", "Alex Roy")
    item = customer(org, "100.00")
    request = request_override(
        item, Decimal("500.00"), user=owner, reason="Trusted client", document_type=INVOICE
    )
    with pytest.raises(SelfApprovalRefused):
        approve_override(request, owner)
    approve_override(request, other)


def test_approver_needs_the_permission(org: Organisation, owner: User) -> None:
    viewer = member(org, "sales", "rita@refined.ca", "Rita Read")
    item = customer(org, "100.00")
    request = request_override(
        item, Decimal("500.00"), user=viewer, reason="Trusted client", document_type=INVOICE
    )
    with pytest.raises(CatalogueError) as denied:
        approve_override(request, viewer)
    assert denied.value.get_codes() == "permission.denied"
    other_viewer = member(org, "sales", "ray@refined.ca", "Ray Read")
    with pytest.raises(CatalogueError):
        approve_override(request, other_viewer)
    approve_override(request, owner)


def test_nobody_to_approve(org: Organisation) -> None:
    lone = member(org, "owner", "solo@refined.ca", "Solo Owner")
    item = customer(org, "100.00")
    with pytest.raises(CatalogueError) as refused:
        request_override(
            item, Decimal("500.00"), user=lone, reason="Trusted client", document_type=INVOICE
        )
    assert refused.value.get_codes() == "contact.credit_override_no_approver"
    with org_context(org):
        assert not CreditOverride.objects.exists()


def test_reason_is_required(org: Organisation, owner: User, clerk: User) -> None:
    item = customer(org, "100.00")
    with pytest.raises(CatalogueError) as refused:
        request_override(item, Decimal("500.00"), user=clerk, reason="  ", document_type=INVOICE)
    assert refused.value.get_codes() == "contact.credit_override_reason"


def test_approvers_are_notified_and_requester_hears_back(
    org: Organisation, owner: User, clerk: User
) -> None:
    item = customer(org, "5000.00", owed="4500.00")
    request = request_override(
        item, Decimal("700.00"), user=clerk, reason="Big order", document_type=INVOICE
    )
    with org_context(org):
        asked = Notification.objects.get(recipient=owner)
        assert asked.title_key == "notifications.contacts.credit_override_requested"
        assert asked.body_params["over"] == "$200.00"
        assert not Notification.objects.filter(recipient=clerk).exists()
    reject_override(request, owner, "Overdue since June")
    with org_context(org):
        told = Notification.objects.get(recipient=clerk)
    assert told.title_key == "notifications.contacts.credit_override_rejected"
    request.refresh_from_db()
    assert request.status == CreditOverrideStatus.REJECTED
    with pytest.raises(CatalogueError) as again:
        approve_override(request, owner)
    assert again.value.get_codes() == "contact.credit_override_decided"
    with pytest.raises(CreditLimitBlocked):
        assert_credit(item, Decimal("700.00"), user=clerk, document_type=INVOICE)


def test_requests_and_approvals_expire(org: Organisation, owner: User, clerk: User) -> None:
    item = customer(org, "100.00")
    request = request_override(
        item, Decimal("500.00"), user=clerk, reason="Trusted client", document_type=INVOICE
    )
    with org_context(org):
        CreditOverride.objects.filter(pk=request.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
    with pytest.raises(CatalogueError) as late:
        approve_override(request, owner)
    assert late.value.get_codes() == "contact.credit_override_expired"

    fresh = request_override(
        item, Decimal("500.00"), user=clerk, reason="Trusted client", document_type=INVOICE
    )
    approve_override(fresh, owner)
    with org_context(org):
        CreditOverride.objects.filter(pk=fresh.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
    with pytest.raises(CreditLimitBlocked):
        assert_credit(item, Decimal("500.00"), user=clerk, document_type=INVOICE)


def test_french_message(org: Organisation, owner: User) -> None:
    item = customer(org, "5000.00", owed="4500.00")
    with translation.override("fr-ca"), pytest.raises(CreditLimitBlocked) as refused:
        assert_credit(item, Decimal("700.00"), document_type=INVOICE)
    assert "limite de crédit" in str(refused.value.detail)


@pytest.mark.parametrize("bad", [1.5, Decimal("-1"), Decimal("NaN"), True])
def test_amounts_are_decimal_and_not_negative(org: Organisation, bad: Any) -> None:
    item = customer(org, "100.00")
    with pytest.raises((TypeError, ValueError)):
        check_credit(item, bad)
