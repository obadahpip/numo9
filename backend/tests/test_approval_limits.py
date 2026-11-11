"""Approval limit service (A-03-T07). Acceptance: a $5,000 limit blocks a $5,001 bill (gap-25).

Covers: user limit, role limit, the lower of the two applies, several roles (lowest), no limit
→ refused, practice staff through a serving practice, no access → no limit, soft-deleted
limits ignored, next eligible approvers (by name, refused user and ``exclude`` left out, none
left), limits changed mid-action apply at commit (no caching), input validation, the API error
body, French message, organisation context rules.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.utils import translation
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.i18n.exceptions import exception_handler
from numo9.rbac.approvals import (
    ApprovalLimitExceeded,
    assert_can_approve,
    can_approve,
    effective_limit,
    eligible_approvers,
)
from numo9.rbac.models import ApprovalLimit, Role, RoleAssignment, RoleScope
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    AssignmentRole,
    Organisation,
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)

pytestmark = pytest.mark.django_db

BILL = "bill"


def make_user(email: str, name: str | None = None) -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=name or email)


def member(org: Organisation, role: str, email: str, name: str | None = None) -> User:
    user = make_user(email, name)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


def system_role(scope: str, key: str) -> Role:
    return Role.objects.get(is_system=True, scope=scope, key=key)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def limit(org: Organisation, amount: str, doc_type: str = BILL, **who: Any) -> ApprovalLimit:
    with org_context(org):
        row: ApprovalLimit = ApprovalLimit.objects.create(
            doc_type=doc_type, max_amount=Decimal(amount), **who
        )
    return row


@pytest.mark.gap("gap-25")
def test_5000_limit_blocks_5001_bill(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    limit(org, "5000.00", user=sam)
    with org_context(org):
        assert assert_can_approve(sam, BILL, Decimal("5000.00")) == Decimal("5000.00")
        with pytest.raises(ApprovalLimitExceeded) as refused:
            assert_can_approve(sam, BILL, Decimal("5001.00"))
    assert refused.value.limit == Decimal("5000.00")
    assert refused.value.status_code == 403
    assert refused.value.get_codes() == "approval.limit_exceeded"
    assert "This bill is for $5,001.00, above your approval limit of $5,000.00." in str(
        refused.value.detail
    )


def test_role_limit_and_the_lower_one_wins(org: Organisation) -> None:
    dana = member(org, "admin", "dana@refined.ca")
    limit(org, "10000", role=system_role(RoleScope.ORGANISATION, "admin"))
    with org_context(org):
        assert effective_limit(dana, BILL) == Decimal("10000.00")
    limit(org, "2500", user=dana)  # own limit lower than the role's
    with org_context(org):
        assert effective_limit(dana, BILL) == Decimal("2500.00")
        assert not can_approve(dana, BILL, Decimal("2500.01"))
    other = member(org, "admin", "lee@refined.ca")
    limit(org, "50000", user=other)  # own limit higher: the role's still caps it
    with org_context(org):
        assert effective_limit(other, BILL) == Decimal("10000.00")


def test_custom_role_limits_lowest_of_all_roles(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca")
    custom = Role.objects.create(scope=RoleScope.ORGANISATION, name="Site buyer", organisation=org)
    RoleAssignment.objects.create(role=custom, user=sam, organisation=org)
    limit(org, "800", role=custom)
    limit(org, "3000", role=system_role(RoleScope.ORGANISATION, "purchasing"))
    with org_context(org):
        assert effective_limit(sam, BILL) == Decimal("800.00")


def test_no_limit_means_no_approval(org: Organisation) -> None:
    owner = member(org, "owner", "owner@refined.ca", "Avery Owner")
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    limit(org, "100", user=sam, doc_type="purchase_order")  # other document type
    with org_context(org):
        assert effective_limit(sam, BILL) is None
        assert effective_limit(owner, BILL) is None  # owners too: limits are explicit
        with pytest.raises(ApprovalLimitExceeded) as refused:
            assert_can_approve(sam, BILL, Decimal("1"))
    assert refused.value.limit is None
    assert refused.value.get_codes() == "approval.no_limit"
    detail = str(refused.value.detail)
    assert "You don't have an approval limit for bills in this organisation" in detail
    assert "Nobody here can approve that amount yet" in detail


def test_zero_limit_allows_only_zero(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca")
    limit(org, "0", user=sam)
    with org_context(org):
        assert can_approve(sam, BILL, Decimal("0"))
        assert not can_approve(sam, BILL, Decimal("0.01"))


def test_practice_staff_limits_through_the_serving_practice(org: Organisation) -> None:
    practice = Practice.objects.create(name="Profitex")
    assignment = PracticeAssignment.objects.create(
        practice=practice, organisation=org, role=AssignmentRole.FULL_SERVICE
    )
    accountant = make_user("ali@profitex.ca")
    pm = PracticeMember.objects.create(practice=practice, user=accountant, role="accountant")
    limit(org, "20000", role=system_role(RoleScope.PRACTICE, "accountant"))
    with org_context(org):
        assert effective_limit(accountant, BILL) is None  # not assigned: no access
    assignment.assigned_staff.add(pm)
    with org_context(org):
        assert effective_limit(accountant, BILL) == Decimal("20000.00")
    assignment.active = False
    assignment.save()
    with org_context(org):
        assert effective_limit(accountant, BILL) is None


def test_no_access_means_no_limit_even_with_a_user_limit(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca")
    limit(org, "5000", user=sam)
    OrganisationMember.objects.filter(user=sam).delete()
    with org_context(org):
        assert effective_limit(sam, BILL) is None
    inactive = member(org, "admin", "gone@refined.ca")
    limit(org, "5000", user=inactive)
    inactive.is_active = False
    inactive.save()
    with org_context(org):
        assert effective_limit(inactive, BILL) is None


def test_deleted_limit_is_ignored_and_changes_apply_at_commit(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca")
    row = limit(org, "5000", user=sam)
    with org_context(org):
        assert can_approve(sam, BILL, Decimal("4000"))
        row.max_amount = Decimal("1000")  # lowered while Sam is reviewing the bill
        row.save()
        assert not can_approve(sam, BILL, Decimal("4000"))
        row.soft_delete()
        assert effective_limit(sam, BILL) is None


def test_limits_of_another_organisation_do_not_count(org: Organisation) -> None:
    other = Organisation.objects.create(name="Northern Lights Bakery Inc.")
    sam = member(org, "purchasing", "sam@refined.ca")
    OrganisationMember.objects.create(organisation=other, user=sam, role="purchasing")
    limit(other, "9999", user=sam)
    with org_context(org):
        assert effective_limit(sam, BILL) is None
    with org_context(other):
        assert effective_limit(sam, BILL) == Decimal("9999.00")


def test_next_eligible_approvers(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    creator = member(org, "admin", "casey@refined.ca", "Casey Creator")
    member(org, "admin", "zoe@refined.ca", "Zoe Admin")
    member(org, "owner", "avery@refined.ca", "Avery Owner")
    member(org, "sales", "small@refined.ca", "Bo Small")
    limit(org, "5000", user=sam)
    limit(org, "25000", role=system_role(RoleScope.ORGANISATION, "admin"))
    limit(org, "100000", user=User.objects.get(email="avery@refined.ca"))
    limit(org, "6000", user=User.objects.get(email="small@refined.ca"))
    with org_context(org):
        names = [a.name for a in eligible_approvers(BILL, Decimal("7500"))]
        assert names == ["Avery Owner", "Casey Creator", "Zoe Admin"]
        with pytest.raises(ApprovalLimitExceeded) as refused:
            assert_can_approve(sam, BILL, Decimal("7500"), exclude=[creator])
    approvers = refused.value.next_approvers
    assert [a.name for a in approvers] == ["Avery Owner", "Zoe Admin"]  # creator left out
    assert "Ask Avery Owner, Zoe Admin to approve it." in str(refused.value.detail)
    assert refused.value.extra is not None
    assert refused.value.extra["approvers"] == [
        {"id": str(approvers[0].public_id), "name": "Avery Owner", "limit": "100000.00"},
        {"id": str(approvers[1].public_id), "name": "Zoe Admin", "limit": "25000.00"},
    ]
    with org_context(org), pytest.raises(ApprovalLimitExceeded) as nobody:
        assert_can_approve(sam, BILL, Decimal("1000000"))
    assert nobody.value.next_approvers == []
    assert "Nobody here can approve that amount yet" in str(nobody.value.detail)


def test_api_error_body_lists_the_approvers(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    member(org, "owner", "avery@refined.ca", "Avery Owner")
    limit(org, "5000", user=sam)
    limit(org, "50000", role=system_role(RoleScope.ORGANISATION, "owner"))
    with org_context(org), pytest.raises(ApprovalLimitExceeded) as refused:
        assert_can_approve(sam, BILL, Decimal("5001"))
    response = exception_handler(refused.value, {"view": APIView()})
    assert isinstance(response, Response)
    assert response.status_code == 403
    assert response.data["code"] == "approval.limit_exceeded"
    assert response.data["limit"] == "5000.00" and response.data["amount"] == "5001.00"
    assert [a["name"] for a in response.data["approvers"]] == ["Avery Owner"]


def test_french_message(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    limit(org, "5000", user=sam)
    with (
        translation.override("fr-ca"),
        org_context(org),
        pytest.raises(ApprovalLimitExceeded) as refused,
    ):
        assert_can_approve(sam, BILL, Decimal("5001"))
    detail = str(refused.value.detail)
    assert "5\u00a0001,00\u00a0$" in detail and "5\u00a0000,00\u00a0$" in detail
    assert detail.startswith("Ce document (facture fournisseur) s’élève à")
    assert "limite d’approbation" in detail


@pytest.mark.parametrize("bad", [5001.0, "5001", True, None])
def test_amount_must_be_decimal(org: Organisation, bad: Any) -> None:
    sam = member(org, "purchasing", "sam@refined.ca")
    with org_context(org), pytest.raises(TypeError):
        assert_can_approve(sam, BILL, bad)


@pytest.mark.parametrize("bad", [Decimal("-1"), Decimal("NaN"), Decimal("Infinity")])
def test_amount_must_be_finite_and_not_negative(org: Organisation, bad: Decimal) -> None:
    sam = member(org, "purchasing", "sam@refined.ca")
    with org_context(org), pytest.raises(ValueError):
        assert_can_approve(sam, BILL, bad)


def test_unknown_document_type(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca")
    with org_context(org), pytest.raises(ValueError, match="document type"):
        assert_can_approve(sam, "invoice", Decimal("1"))


def test_organisation_argument_and_context(org: Organisation) -> None:
    sam = member(org, "purchasing", "sam@refined.ca")
    limit(org, "5000", user=sam)
    # Outside a request (a job): pass the organisation; the context is opened for the check.
    assert effective_limit(sam, BILL, organisation=org) == Decimal("5000.00")
    with pytest.raises(ValueError, match="No organisation"):
        effective_limit(sam, BILL)
    other = Organisation.objects.create(name="Elsewhere Ltd.")
    with org_context(other), pytest.raises(ValueError, match="active organisation only"):
        effective_limit(sam, BILL, organisation=org)
