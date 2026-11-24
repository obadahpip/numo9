"""System roles seeded with default permission sets (A-03-T03). Acceptance: 15 system roles."""

from __future__ import annotations

from collections.abc import Iterator
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import translation

from numo9.rbac.catalogue import Permission, Risk, Scope, catalogue
from numo9.rbac.models import Role, RolePermission
from numo9.rbac.system_roles import SYSTEM_ROLES, sync_system_roles, system_role
from numo9.tenancy.models import OrganisationRole, PracticeRole

pytestmark = pytest.mark.django_db


def grants(scope: str, key: str) -> set[str]:
    role = Role.objects.get(is_system=True, scope=scope, key=key)
    return set(role.grants.values_list("permission", flat=True))


ORG_PERMS = {p.key for p in catalogue if p.scope == Scope.ORGANISATION}
PRACTICE_PERMS = {p.key for p in catalogue if p.scope == Scope.PRACTICE}
PLATFORM_PERMS = {p.key for p in catalogue if p.scope == Scope.PLATFORM}


def test_fifteen_system_roles_are_seeded() -> None:
    system = Role.objects.filter(is_system=True)
    assert system.count() == 15
    by_scope = {s: set(system.filter(scope=s).values_list("key", flat=True)) for s in Scope}
    assert by_scope[Scope.PLATFORM] == {"platform_owner", "platform_support"}
    # The membership roles of A-01 are exactly the practice and organisation system roles.
    assert by_scope[Scope.PRACTICE] == set(PracticeRole.values)
    assert by_scope[Scope.ORGANISATION] == set(OrganisationRole.values)
    assert not system.filter(organisation__isnull=False).exists()
    assert not system.filter(practice__isnull=False).exists()


def test_names_are_stored_in_english_and_translated_by_key() -> None:
    assert Role.objects.get(is_system=True, key="accountant_delegate").name == "Accountant delegate"
    with translation.override("fr-ca"):
        assert str(system_role("organisation", "owner").name) == "Propriétaire"


#: Owner-only permissions: closing the organisation (A-03) and billing (U-04-T05).
OWNER_ONLY = {"organisation.close", "organisation.billing.view", "organisation.billing.manage"}


def test_owner_only_permissions_go_to_the_owner_role_only() -> None:
    """U-04-T16: billing (and closing) never reach practice staff or broad organisation roles."""
    owner_only = {p.key for p in catalogue if p.owner_only}
    assert owner_only >= OWNER_ONLY
    for role in SYSTEM_ROLES:
        granted = role.permission_keys()
        if role.key == "owner":
            assert owner_only <= granted
        else:
            assert not granted & owner_only, role.key


def test_owner_and_admin() -> None:
    assert grants("organisation", "owner") == ORG_PERMS
    assert grants("organisation", "admin") == ORG_PERMS - OWNER_ONLY


def test_practice_admin_runs_the_practice_and_its_clients() -> None:
    assert grants("practice", "practice_admin") == PRACTICE_PERMS | (ORG_PERMS - OWNER_ONLY)


def test_accountants_keep_books_but_do_not_manage_users() -> None:
    for scope, key in [("practice", "accountant"), ("organisation", "accountant_delegate")]:
        got = grants(scope, key)
        assert "organisation.settings.manage" in got
        assert "organisation.members.view" in got
        assert not got & {
            "organisation.members.invite",
            "organisation.members.manage",
            "roles.role.manage",
            "roles.assignment.manage",
            "roles.limit.manage",
            "organisation.close",
        }
    assert grants("practice", "accountant") & PRACTICE_PERMS == {
        "practice.profile.view",
        "practice.staff.view",
        "practice.clients.create",
        "practice.directory.view",  # the organisation directory (V-01)
    }


def test_read_only_and_reviewer_change_nothing() -> None:
    read_only = {
        p.key for p in catalogue if p.read_only and p.scope != Scope.PLATFORM and not p.owner_only
    }
    assert grants("practice", "read_only") == read_only
    reviewer = grants("practice", "reviewer")
    # The reviewer reads and approves (journals, C-04-T07) — and changes nothing else.
    assert all(
        catalogue.get(k).read_only or catalogue.get(k).action in {"approve", "review"}
        for k in reviewer
    )
    assert "accounting.journals.approve" in reviewer
    assert "practice.staff.view" in reviewer


def test_functional_roles_start_small() -> None:
    # Documents are read-only for the functional roles (A-06); their own modules arrive later.
    # Sales and purchasing keep contacts (B-01-T11): customers and suppliers are their work; each
    # sees its own side's documents (D-01-T09); sales sees, writes and emails invoices (D-03a);
    # purchasing writes, approves (within a limit) and receives purchase orders (E-01). Every
    # functional role that reads reports runs them (K-01).
    for key, own in (
        (
            "sales",
            {
                "sales.document.view",
                "sales.invoices.view",
                "sales.invoices.write",
                "sales.invoices.send",
                "reports.reports.view",
            },
        ),
        (
            "purchasing",
            {
                "purchases.document.view",
                "purchases.orders.view",
                "purchases.orders.write",
                "purchases.orders.approve",
                "purchases.orders.receive",
                "reports.reports.view",
            },
        ),
    ):
        assert grants("organisation", key) == {
            "organisation.profile.view",
            "documents.file.view",
            "contacts.contacts.view",
            "contacts.contacts.manage",
            *own,
        }, key
    assert grants("organisation", "payroll") == {
        "organisation.profile.view",
        "documents.file.view",
        "reports.reports.view",
    }
    assert grants("organisation", "hr") == {"organisation.profile.view", "documents.file.view"}
    assert grants("organisation", "employee") == {"organisation.profile.view"}


def test_platform_roles() -> None:
    assert grants("platform", "platform_owner") == PLATFORM_PERMS
    assert grants("platform", "platform_support") == {
        "platform.console.view",
        "platform.jobs.view",
        "platform.impersonate",
        "platform.audit.view",  # A-04-T07
    }


def test_every_tenant_role_can_see_the_organisation_details() -> None:
    for definition in SYSTEM_ROLES:
        if definition.scope != Scope.PLATFORM:
            assert "organisation.profile.view" in grants(definition.scope, definition.key)


def test_every_grant_is_valid_for_its_role() -> None:
    for grant in RolePermission.objects.select_related("role"):
        grant.clean()  # in the catalogue and grantable at the role's scope


# ---- the sync keeps roles in step with the catalogue -------------------------------------------


@pytest.fixture
def new_permissions() -> Iterator[None]:
    added = [
        Permission("sales.invoice.view", "View invoices", "sales", Risk.LOW),
        Permission("sales.invoice.approve", "Approve invoices", "sales", Risk.HIGH),
        Permission("sales.invoice.void", "Void invoices", "sales", Risk.CRITICAL),
        Permission("payroll.payrun.post", "Post pay runs", "payroll", Risk.HIGH),
    ]
    for permission in added:
        catalogue.register(permission)
    yield
    for permission in added:
        catalogue.unregister(permission.key)


def test_sync_grants_permissions_declared_later_and_removes_dropped_ones(
    new_permissions: None,
) -> None:
    counts = sync_system_roles(Role, RolePermission)
    assert counts["roles_created"] == 0
    assert {"sales.invoice.view", "sales.invoice.approve"} <= grants("organisation", "sales")
    assert "sales.invoice.void" not in grants("organisation", "sales")  # critical
    assert "sales.invoice.void" in grants("organisation", "owner")
    assert grants("practice", "reviewer") >= {"sales.invoice.view", "sales.invoice.approve"}
    assert "payroll.payrun.post" in grants("organisation", "payroll")
    assert "payroll.payrun.post" in grants("practice", "payroll_specialist")
    assert "payroll.payrun.post" not in grants("organisation", "sales")
    assert grants("organisation", "employee") == {"organisation.profile.view"}

    for key in ("sales.invoice.view", "sales.invoice.approve", "sales.invoice.void"):
        catalogue.unregister(key)
    counts = sync_system_roles(Role, RolePermission)
    assert counts["permissions_removed"] > 0
    assert not any(k.startswith("sales.invoice.") for k in grants("organisation", "owner"))


def test_sync_is_idempotent_and_restores_a_deleted_role() -> None:
    assert sync_system_roles(Role, RolePermission) == {
        "roles_created": 0,
        "permissions_added": 0,
        "permissions_removed": 0,
    }
    Role.objects.get(is_system=True, key="hr").delete()
    out = StringIO()
    call_command("sync_system_roles", stdout=out)
    assert "1 created" in out.getvalue()
    assert grants("organisation", "hr") == {"organisation.profile.view", "documents.file.view"}
