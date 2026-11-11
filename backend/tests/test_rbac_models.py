"""Role, RolePermission, RoleAssignment, ApprovalLimit (A-03-T02)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from numo9.accounts.models import User
from numo9.rbac.models import (
    ApprovalDocumentType,
    ApprovalLimit,
    Role,
    RoleAssignment,
    RolePermission,
    RoleScope,
)
from numo9.tenancy.checks import models_violating_org_ownership
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrgOwnedModel, Practice

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def other_org() -> Organisation:
    return Organisation.objects.create(name="Northern Lights Bakery Inc.")


@pytest.fixture
def practice() -> Practice:
    return Practice.objects.create(name="Profitex")


@pytest.fixture
def user() -> User:
    return User.objects.create_user(email="dana@maple.ca", password="x" * 12, name="Dana Lee")


def custom(org: Organisation, name: str = "Bills up to $5,000") -> Role:
    return Role.objects.create(scope=RoleScope.ORGANISATION, name=name, organisation=org)


def system(scope: str = RoleScope.ORGANISATION, key: str = "test_role") -> Role:
    return Role.objects.create(scope=scope, key=key, name="Test role", is_system=True)


def integrity(make: object) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make()  # type: ignore[operator]


# ---- Role -------------------------------------------------------------------------------------


def test_custom_and_system_roles(org: Organisation, practice: Practice) -> None:
    role = custom(org)
    assert role.editable and not role.is_system and role.public_id
    practice_role = Role.objects.create(scope=RoleScope.PRACTICE, name="Senior", practice=practice)
    assert practice_role.practice == practice
    assert not system().editable


def test_system_roles_belong_to_no_tenant_and_have_a_key(org: Organisation) -> None:
    integrity(
        lambda: Role.objects.create(
            scope="organisation", key="x", name="X", is_system=True, organisation=org
        )
    )
    integrity(lambda: Role.objects.create(scope="organisation", name="X", is_system=True))


def test_custom_roles_have_no_key_and_belong_to_their_scope(
    org: Organisation, practice: Practice
) -> None:
    integrity(
        lambda: Role.objects.create(scope="organisation", key="x", name="X", organisation=org)
    )
    integrity(lambda: Role.objects.create(scope="organisation", name="X"))  # no organisation
    integrity(lambda: Role.objects.create(scope="organisation", name="X", practice=practice))
    integrity(lambda: Role.objects.create(scope="practice", name="X", organisation=org))
    integrity(lambda: Role.objects.create(scope="platform", name="X"))  # no custom platform roles


def test_system_keys_unique_per_scope() -> None:
    system(RoleScope.ORGANISATION, "auditor_x")
    system(RoleScope.PRACTICE, "auditor_x")  # same key, other scope: allowed
    integrity(lambda: system(RoleScope.ORGANISATION, "auditor_x"))


def test_custom_names_unique_per_tenant_ignoring_case(
    org: Organisation, other_org: Organisation
) -> None:
    custom(org, "Bookkeeper")
    custom(other_org, "Bookkeeper")
    integrity(lambda: custom(org, "BOOKKEEPER"))


# ---- RolePermission ---------------------------------------------------------------------------


def test_grants_catalogue_permissions(org: Organisation) -> None:
    role = custom(org)
    RolePermission.objects.create(role=role, permission="organisation.members.view")
    RolePermission.objects.create(role=role, permission="roles.limit.view")
    assert role.permission_keys() == {"organisation.members.view", "roles.limit.view"}
    integrity(lambda: RolePermission.objects.create(role=role, permission="roles.limit.view"))


def test_unknown_permission_is_refused(org: Organisation) -> None:
    with pytest.raises(ValidationError, match="There is no permission 'roles.limits.view'"):
        RolePermission.objects.create(role=custom(org), permission="roles.limits.view")


@pytest.mark.parametrize(
    "scope, permission, allowed",
    [
        ("organisation", "organisation.members.view", True),
        ("organisation", "practice.staff.view", False),
        ("organisation", "platform.console.view", False),
        ("practice", "practice.staff.view", True),
        ("practice", "organisation.members.view", True),  # in the organisations it serves
        ("practice", "platform.console.view", False),
        ("platform", "platform.console.view", True),
        ("platform", "organisation.members.view", False),
    ],
)
def test_permission_scope_must_fit_the_role(scope: str, permission: str, allowed: bool) -> None:
    role = system(scope, f"r_{scope}")
    if allowed:
        RolePermission.objects.create(role=role, permission=permission)
    else:
        with pytest.raises(ValidationError, match="can't grant it"):
            RolePermission.objects.create(role=role, permission=permission)


# ---- RoleAssignment ---------------------------------------------------------------------------


def test_assignment_at_the_role_scope(user: User, org: Organisation, practice: Practice) -> None:
    RoleAssignment.objects.create(role=custom(org), user=user, organisation=org)
    RoleAssignment.objects.create(role=system("practice", "p"), user=user, practice=practice)
    RoleAssignment.objects.create(role=system("platform", "support"), user=user)
    assert RoleAssignment.objects.filter(user=user).count() == 3


@pytest.mark.parametrize(
    "scope, where",
    [
        ("organisation", "practice"),
        ("organisation", "none"),
        ("practice", "organisation"),
        ("platform", "organisation"),
    ],
)
def test_assignment_tenant_must_match_scope(
    user: User, org: Organisation, practice: Practice, scope: str, where: str
) -> None:
    tenants: dict[str, dict[str, object]] = {
        "organisation": {"organisation": org},
        "practice": {"practice": practice},
    }
    tenant = tenants.get(where, {})
    with pytest.raises(ValidationError):
        RoleAssignment.objects.create(role=system(scope, "k"), user=user, **tenant)


def test_custom_role_only_in_its_own_organisation(
    user: User, org: Organisation, other_org: Organisation
) -> None:
    with pytest.raises(ValidationError, match="belongs to another organisation"):
        RoleAssignment.objects.create(role=custom(org), user=user, organisation=other_org)


def test_assignment_is_unique(user: User, org: Organisation) -> None:
    role = custom(org)
    RoleAssignment.objects.create(role=role, user=user, organisation=org)
    integrity(lambda: RoleAssignment.objects.create(role=role, user=user, organisation=org))
    platform = system("platform", "owner_p")
    RoleAssignment.objects.create(role=platform, user=user)
    integrity(lambda: RoleAssignment.objects.create(role=platform, user=user))


def test_assignment_never_names_two_tenants(
    user: User, org: Organisation, practice: Practice
) -> None:
    role = system("practice", "both")
    integrity(
        lambda: RoleAssignment.objects.bulk_create(  # bulk_create skips clean(): the DB refuses
            [RoleAssignment(role=role, user=user, organisation=org, practice=practice)]
        )
    )


# ---- ApprovalLimit ----------------------------------------------------------------------------


def test_approval_limit_is_an_organisation_record() -> None:
    assert issubclass(ApprovalLimit, OrgOwnedModel)
    from django.apps import apps

    assert models_violating_org_ownership(apps.get_app_configs(), ("numo9.",)) == []


def test_limit_for_a_user_or_a_role(user: User, org: Organisation) -> None:
    role = custom(org)
    with org_context(org):
        mine = ApprovalLimit.objects.create(
            user=user, doc_type=ApprovalDocumentType.BILL, max_amount=Decimal("5000.00")
        )
        ApprovalLimit.objects.create(role=role, doc_type="bill", max_amount=Decimal("25000"))
        mine.refresh_from_db()
        assert mine.max_amount == Decimal("5000.00")
        assert mine.organisation == org
        integrity(
            lambda: ApprovalLimit.objects.create(doc_type="bill", max_amount=Decimal("1"))
        )  # neither
        integrity(
            lambda: ApprovalLimit.objects.create(
                user=user, role=role, doc_type="journal", max_amount=Decimal("1")
            )
        )  # both


def test_one_limit_per_user_and_document_type_until_deleted(user: User, org: Organisation) -> None:
    with org_context(org):
        first = ApprovalLimit.objects.create(user=user, doc_type="bill", max_amount=Decimal("5000"))
        integrity(
            lambda: ApprovalLimit.objects.create(
                user=user, doc_type="bill", max_amount=Decimal("6000")
            )
        )
        ApprovalLimit.objects.create(user=user, doc_type="purchase_order", max_amount=Decimal("1"))
        first.soft_delete()
        ApprovalLimit.objects.create(user=user, doc_type="bill", max_amount=Decimal("6000"))


def test_limit_amount_is_money_and_not_negative(user: User, org: Organisation) -> None:
    with org_context(org):
        limit = ApprovalLimit(user=user, doc_type="bill", max_amount=Decimal("-0.01"))
        limit.organisation = org
        with pytest.raises(ValidationError):
            limit.full_clean()
        integrity(lambda: ApprovalLimit.objects.create(user=user, doc_type="bill", max_amount=-1))
        field = ApprovalLimit._meta.get_field("max_amount")
        assert (field.max_digits, field.decimal_places) == (18, 2)


def test_limit_role_must_be_usable_in_the_organisation(
    org: Organisation, other_org: Organisation
) -> None:
    with org_context(org):
        for role in (custom(other_org), system("platform", "plat")):
            limit = ApprovalLimit(role=role, doc_type="bill", max_amount=Decimal("1"))
            limit.organisation = org
            with pytest.raises(ValidationError, match="Choose a role used in this organisation"):
                limit.full_clean()
        ok = ApprovalLimit(role=system("practice", "acct"), doc_type="bill", max_amount=Decimal(1))
        ok.organisation = org
        ok.full_clean()


def test_document_types() -> None:
    assert set(ApprovalDocumentType.values) == {"journal", "bill", "purchase_order", "pay_run"}
