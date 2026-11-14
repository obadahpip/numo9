"""Roles, assignments, approval limits and catalogue API (A-03-T09). Acceptance: OpenAPI documented.

Covers each endpoint's happy path and its rules: system roles read-only, custom roles only in
their organisation, copy from role, no escalation (only permissions you hold), names unique,
role in use can't be deleted, main role replaced (last owner kept), custom roles added/removed,
practice staff, approval limits CRUD + enforcement through assert_can_approve, permission and
isolation answers (403 / 404), French labels, OpenAPI.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from django.core.management import call_command
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.rbac.approvals import ApprovalLimitExceeded, assert_can_approve
from numo9.rbac.catalogue import MODULE_LABELS, MODULES, catalogue
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

CATALOGUE = "/api/v1/permissions/catalogue"


def make_user(email: str, name: str) -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=name)


def member(org: Organisation, role: str, email: str, name: str) -> User:
    user = make_user(email, name)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def system(key: str, scope: str = RoleScope.ORGANISATION) -> Role:
    return Role.objects.get(is_system=True, scope=scope, key=key)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def owner(org: Organisation) -> User:
    return member(org, "owner", "avery@refined.ca", "Avery Owner")


def url(org: Organisation, path: str) -> str:
    return f"/api/v1/o/{org.public_id}/{path}"


# ---- catalogue -----------------------------------------------------------------------------


def test_catalogue_lists_every_permission_grouped_by_module(owner: User) -> None:
    body = client_for(owner).get(CATALOGUE).json()
    keys = [p["key"] for p in body["permissions"]]
    assert keys == [p.key for p in catalogue]  # every permission, module order
    close = next(p for p in body["permissions"] if p["key"] == "organisation.close")
    assert close == {
        "key": "organisation.close",
        "label": "Close the organisation",
        "module": "settings",
        "risk": "critical",
        "risk_label": "Critical",
        "scope": "organisation",
        "owner_only": True,
        "read_only": False,
    }
    modules = [m["key"] for m in body["modules"]]
    assert modules == [m for m in MODULES if m in {p.module for p in catalogue}]
    assert {"key": "users", "label": "Users and roles"} in body["modules"]


def test_catalogue_in_french_and_for_signed_in_users_only(owner: User) -> None:
    assert APIClient().get(CATALOGUE).status_code in {401, 403}
    body = client_for(owner).get(CATALOGUE, HTTP_ACCEPT_LANGUAGE="fr-ca").json()
    close = next(p for p in body["permissions"] if p["key"] == "organisation.close")
    assert close["label"] == "Fermer l’organisation"
    assert close["risk_label"] == "Critique"


def test_every_module_has_a_label() -> None:
    assert set(MODULE_LABELS) == set(MODULES)


# ---- roles ---------------------------------------------------------------------------------


def test_list_roles_system_then_custom(org: Organisation, owner: User) -> None:
    Role.objects.create(scope=RoleScope.ORGANISATION, name="Site buyer", organisation=org)
    other = Organisation.objects.create(name="Elsewhere Ltd.")
    Role.objects.create(scope=RoleScope.ORGANISATION, name="Not here", organisation=other)
    roles = client_for(owner).get(url(org, "roles")).json()
    names = [r["name"] for r in roles]
    assert names[:8] == [
        "Owner",
        "Admin",
        "Accountant delegate",
        "Sales",
        "Purchasing",
        "Payroll",
        "HR",
        "Employee",
    ]
    assert "Site buyer" in names and "Not here" not in names
    owner_row = roles[0]
    assert owner_row["is_system"] and not owner_row["editable"] and owner_row["assignable"]
    assert owner_row["holders"] == 1
    assert "organisation.close" in owner_row["permissions"]
    practice = [r for r in roles if r["scope"] == "practice"]
    assert {r["key"] for r in practice} == {
        "practice_admin",
        "accountant",
        "reviewer",
        "payroll_specialist",
        "read_only",
    }
    assert not any(r["assignable"] for r in practice)


def test_create_custom_role_copied_from_a_system_role(org: Organisation, owner: User) -> None:
    sales = system("sales")
    response = client_for(owner).post(
        url(org, "roles"),
        {
            "name": " Showroom ",
            "copy_from": str(sales.public_id),
            "permissions": ["organisation.members.view"],
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["name"] == "Showroom" and body["editable"] and not body["is_system"]
    assert set(body["permissions"]) == sales.permission_keys() | {"organisation.members.view"}
    role = Role.objects.get(public_id=body["id"])
    assert role.organisation == org and role.scope == RoleScope.ORGANISATION


def test_create_role_validation(org: Organisation, owner: User) -> None:
    client = client_for(owner)
    bad = client.post(
        url(org, "roles"),
        {"name": "X", "permissions": ["organisation.nope", "practice.staff.view"]},
        format="json",
    ).json()
    assert bad["permissions"] == [
        "There's no permission called organisation.nope. Verify the key.",
        "practice.staff.view is a practice permission, so an organisation role can't give it.",
    ]
    assert client.post(url(org, "roles"), {"name": "Buyer"}, format="json").status_code == 201
    taken = client.post(url(org, "roles"), {"name": "BUYER"}, format="json")
    assert taken.status_code == 409 and taken.json()["code"] == "roles.name_taken"
    unknown = client.post(
        url(org, "roles"), {"name": "Y", "copy_from": str(org.public_id)}, format="json"
    )
    assert unknown.status_code == 400 and "copy_from" in unknown.json()


def test_no_escalation_only_permissions_you_hold(org: Organisation) -> None:
    admin = member(org, "admin", "dana@refined.ca", "Dana Admin")
    client = client_for(admin)
    refused = client.post(
        url(org, "roles"),
        {"name": "Closer", "permissions": ["organisation.close"]},
        format="json",
    )
    assert refused.status_code == 403
    assert refused.json()["code"] == "roles.grant_exceeds_own"
    assert refused.json()["permissions"] == ["organisation.close"]
    assert "Close the organisation" in refused.json()["detail"]
    # Copying the owner role would include it too.
    copy = client.post(
        url(org, "roles"),
        {"name": "Owner 2", "copy_from": str(system("owner").public_id)},
        format="json",
    )
    assert copy.status_code == 403
    assert not Role.objects.filter(organisation=org).exists()


def test_update_custom_role_and_system_roles_are_read_only(org: Organisation, owner: User) -> None:
    client = client_for(owner)
    role = client.post(
        url(org, "roles"),
        {"name": "Buyer", "permissions": ["organisation.profile.view"]},
        format="json",
    ).json()
    changed = client.patch(
        url(org, f"roles/{role['id']}"),
        {"name": "Senior buyer", "permissions": ["organisation.members.view"]},
        format="json",
    )
    assert changed.status_code == 200
    assert changed.json()["name"] == "Senior buyer"
    assert changed.json()["permissions"] == ["organisation.members.view"]
    owner_role = system("owner")
    for verb in ("patch", "delete"):
        answer = getattr(client, verb)(
            url(org, f"roles/{owner_role.public_id}"), {"name": "Boss"}, format="json"
        )
        assert answer.status_code == 409 and answer.json()["code"] == "roles.system_role"
    assert client.get(url(org, f"roles/{owner_role.public_id}")).status_code == 200


def test_editing_keeps_permissions_you_lack_but_cannot_add_them(org: Organisation) -> None:
    role = Role.objects.create(scope=RoleScope.ORGANISATION, name="Closer", organisation=org)
    role.grants.create(permission="organisation.close")
    admin = member(org, "admin", "dana@refined.ca", "Dana Admin")
    client = client_for(admin)
    keep = client.patch(
        url(org, f"roles/{role.public_id}"),
        {"permissions": ["organisation.close", "organisation.members.view"]},
        format="json",
    )
    assert keep.status_code == 200  # organisation.close was already there
    role.grants.filter(permission="organisation.close").delete()
    add = client.patch(
        url(org, f"roles/{role.public_id}"),
        {"permissions": ["organisation.close"]},
        format="json",
    )
    assert add.status_code == 403


def test_delete_role_in_use_refused_then_allowed(org: Organisation, owner: User) -> None:
    role = Role.objects.create(scope=RoleScope.ORGANISATION, name="Buyer", organisation=org)
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    RoleAssignment.objects.create(role=role, user=sam, organisation=org)
    with org_context(org):
        ApprovalLimit.objects.create(role=role, doc_type="bill", max_amount=Decimal(10))
    client = client_for(owner)
    in_use = client.delete(url(org, f"roles/{role.public_id}"))
    assert in_use.status_code == 409 and in_use.json()["code"] == "roles.in_use"
    RoleAssignment.objects.all().delete()
    assert client.delete(url(org, f"roles/{role.public_id}")).status_code == 204
    assert not Role.objects.filter(pk=role.pk).exists()
    assert not ApprovalLimit._base_manager.filter(role_id=role.pk).exists()


@pytest.mark.tenant_isolation
def test_another_organisations_role_is_unknown(org: Organisation, owner: User) -> None:
    other = Organisation.objects.create(name="Elsewhere Ltd.")
    foreign = Role.objects.create(scope=RoleScope.ORGANISATION, name="Theirs", organisation=other)
    client = client_for(owner)
    for verb in ("get", "patch", "delete"):
        answer = getattr(client, verb)(url(org, f"roles/{foreign.public_id}"))
        assert answer.status_code == 404
    sam = member(org, "sales", "sam@refined.ca", "Sam Patel")
    assign = client.post(
        url(org, f"members/{sam.public_id}/roles"),
        {"role": str(foreign.public_id)},
        format="json",
    )
    assert assign.status_code == 400
    assert not RoleAssignment.objects.exists()


# ---- members and assignments ---------------------------------------------------------------


@pytest.fixture
def practice(org: Organisation) -> dict[str, Any]:
    firm = Practice.objects.create(name="Profitex")
    assignment = PracticeAssignment.objects.create(
        practice=firm, organisation=org, role=AssignmentRole.FULL_SERVICE
    )
    ali = make_user("ali@profitex.ca", "Ali Accountant")
    pm = PracticeMember.objects.create(practice=firm, user=ali, role="accountant")
    assignment.assigned_staff.add(pm)
    PracticeMember.objects.create(
        practice=firm, user=make_user("nope@profitex.ca", "Not Assigned"), role="accountant"
    )
    return {"practice": firm, "ali": ali}


def test_members_list(org: Organisation, owner: User, practice: dict[str, Any]) -> None:
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    buyer = Role.objects.create(scope=RoleScope.ORGANISATION, name="Buyer", organisation=org)
    RoleAssignment.objects.create(role=buyer, user=sam, organisation=org)
    rows = client_for(owner).get(url(org, "members")).json()
    assert [r["name"] for r in rows] == ["Avery Owner", "Sam Patel", "Ali Accountant"]
    sam_row = rows[1]
    assert sam_row["id"] == str(sam.public_id) and sam_row["kind"] == "member"
    assert sam_row["main_role"]["key"] == "purchasing"
    assert sam_row["main_role"]["name"] == "Purchasing"
    assert [r["name"] for r in sam_row["roles"]] == ["Buyer"]
    ali = rows[2]
    assert ali["kind"] == "practice" and ali["main_role"] is None
    assert ali["practices"] == [
        {
            "id": str(practice["practice"].public_id),
            "name": "Profitex",
            "role": "accountant",
            "role_name": "Accountant",
        }
    ]


def test_give_and_take_a_custom_role(org: Organisation, owner: User) -> None:
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    buyer = Role.objects.create(scope=RoleScope.ORGANISATION, name="Buyer", organisation=org)
    client = client_for(owner)
    given = client.post(
        url(org, f"members/{sam.public_id}/roles"), {"role": str(buyer.public_id)}, format="json"
    )
    assert given.status_code == 201
    assert [r["name"] for r in given.json()["roles"]] == ["Buyer"]
    again = client.post(
        url(org, f"members/{sam.public_id}/roles"), {"role": str(buyer.public_id)}, format="json"
    )
    assert again.status_code == 200  # already held: nothing changes
    assert RoleAssignment.objects.get().assigned_by == owner
    taken = client.delete(url(org, f"members/{sam.public_id}/roles/{buyer.public_id}"))
    assert taken.status_code == 204 and not RoleAssignment.objects.exists()
    assert (
        client.delete(url(org, f"members/{sam.public_id}/roles/{buyer.public_id}")).status_code
        == 404
    )


def test_system_role_replaces_the_main_role(org: Organisation, owner: User) -> None:
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    client = client_for(owner)
    answer = client.post(
        url(org, f"members/{sam.public_id}/roles"),
        {"role": str(system("admin").public_id)},
        format="json",
    )
    assert answer.status_code == 200
    assert answer.json()["main_role"]["key"] == "admin"
    assert OrganisationMember.objects.get(user=sam).role == "admin"
    main = client.delete(url(org, f"members/{sam.public_id}/roles/{system('admin').public_id}"))
    assert main.status_code == 409 and main.json()["code"] == "roles.main_role"


def test_last_owner_keeps_the_owner_role(org: Organisation, owner: User) -> None:
    client = client_for(owner)
    demote = client.post(
        url(org, f"members/{owner.public_id}/roles"),
        {"role": str(system("admin").public_id)},
        format="json",
    )
    assert demote.status_code == 409 and demote.json()["code"] == "roles.last_owner"
    second = member(org, "admin", "lee@refined.ca", "Lee Second")
    promote = client.post(
        url(org, f"members/{second.public_id}/roles"),
        {"role": str(system("owner").public_id)},
        format="json",
    )
    assert promote.status_code == 200
    assert (
        client.post(
            url(org, f"members/{owner.public_id}/roles"),
            {"role": str(system("admin").public_id)},
            format="json",
        ).status_code
        == 200
    )


def test_admin_cannot_make_an_owner(org: Organisation, owner: User) -> None:
    admin = member(org, "admin", "dana@refined.ca", "Dana Admin")
    sam = member(org, "sales", "sam@refined.ca", "Sam Patel")
    answer = client_for(admin).post(
        url(org, f"members/{sam.public_id}/roles"),
        {"role": str(system("owner").public_id)},
        format="json",
    )
    assert answer.status_code == 403 and answer.json()["code"] == "roles.grant_exceeds_own"


def test_practice_staff_get_custom_roles_not_main_roles(
    org: Organisation, owner: User, practice: dict[str, Any]
) -> None:
    ali = practice["ali"]
    buyer = Role.objects.create(scope=RoleScope.ORGANISATION, name="Buyer", organisation=org)
    client = client_for(owner)
    main = client.post(
        url(org, f"members/{ali.public_id}/roles"),
        {"role": str(system("sales").public_id)},
        format="json",
    )
    assert main.status_code == 400 and "works here through their practice" in main.json()["role"][0]
    practice_role = client.post(
        url(org, f"members/{ali.public_id}/roles"),
        {"role": str(system("reviewer", RoleScope.PRACTICE).public_id)},
        format="json",
    )
    assert practice_role.status_code == 400
    custom = client.post(
        url(org, f"members/{ali.public_id}/roles"), {"role": str(buyer.public_id)}, format="json"
    )
    assert custom.status_code == 201
    not_here = make_user("nope2@profitex.ca", "Nobody")
    assert (
        client.post(
            url(org, f"members/{not_here.public_id}/roles"),
            {"role": str(buyer.public_id)},
            format="json",
        ).status_code
        == 404
    )


def test_pending_invitations(org: Organisation, owner: User) -> None:
    from numo9.tenancy import invitations

    invitations.create(
        inviter=owner, kind="organisation_user", email="new@refined.ca", role="sales", target=org
    )
    rows = client_for(owner).get(url(org, "invitations")).json()
    assert [(r["email"], r["role"], r["inviter_name"]) for r in rows] == [
        ("new@refined.ca", "sales", "Avery Owner")
    ]


# ---- permission and isolation answers ------------------------------------------------------


def test_permissions_per_method(org: Organisation, owner: User) -> None:
    sales = client_for(member(org, "sales", "sam@refined.ca", "Sam Patel"))
    assert sales.get(url(org, "roles")).status_code == 403  # roles.role.view: not for Sales
    assert sales.get(url(org, "members")).status_code == 403
    delegate = client_for(member(org, "accountant_delegate", "bo@refined.ca", "Bo Books"))
    assert delegate.get(url(org, "roles")).status_code == 200
    assert delegate.get(url(org, "approval-limits")).status_code == 200
    refused = delegate.post(url(org, "roles"), {"name": "Mine"}, format="json")
    assert refused.status_code == 403 and refused.json()["code"] == "permission.denied"
    assert (
        delegate.post(
            url(org, "approval-limits"),
            {"doc_type": "bill", "max_amount": "1", "role": str(system("sales").public_id)},
            format="json",
        ).status_code
        == 403
    )


@pytest.mark.tenant_isolation
def test_outsiders_get_404(org: Organisation, owner: User) -> None:
    other = Organisation.objects.create(name="Elsewhere Ltd.")
    outsider = client_for(member(other, "owner", "x@elsewhere.ca", "Out Sider"))
    for path in ("roles", "members", "invitations", "approval-limits"):
        assert outsider.get(url(org, path)).status_code == 404
    assert APIClient().get(url(org, "roles")).status_code in {401, 403}


# ---- approval limits -----------------------------------------------------------------------


def test_limits_crud_and_enforced(org: Organisation, owner: User) -> None:
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    client = client_for(owner)
    created = client.post(
        url(org, "approval-limits"),
        {"doc_type": "bill", "max_amount": "5000.00", "user": str(sam.public_id)},
        format="json",
    )
    assert created.status_code == 201, created.json()
    row = created.json()
    assert row["user"] == {"id": str(sam.public_id), "name": "Sam Patel"}
    assert row["role"] is None and row["max_amount"] == "5000.00"
    with org_context(org), pytest.raises(ApprovalLimitExceeded):
        assert_can_approve(sam, "bill", Decimal("5001"))
    duplicate = client.post(
        url(org, "approval-limits"),
        {"doc_type": "bill", "max_amount": "1", "user": str(sam.public_id)},
        format="json",
    )
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "limits.duplicate"
    changed = client.patch(
        url(org, f"approval-limits/{row['id']}"), {"max_amount": "7500"}, format="json"
    )
    assert changed.status_code == 200 and changed.json()["max_amount"] == "7500.00"
    with org_context(org):
        assert assert_can_approve(sam, "bill", Decimal("5001")) == Decimal("7500.00")
    listed = client.get(url(org, "approval-limits")).json()
    assert [r["id"] for r in listed] == [row["id"]]
    assert client.get(url(org, f"approval-limits/{row['id']}")).status_code == 200
    assert client.delete(url(org, f"approval-limits/{row['id']}")).status_code == 204
    assert client.get(url(org, "approval-limits")).json() == []
    assert ApprovalLimit._base_manager.get(public_id=row["id"]).deleted_at is not None  # kept
    assert client.get(url(org, f"approval-limits/{row['id']}")).status_code == 404


def test_limit_for_a_role_and_validation(org: Organisation, owner: User) -> None:
    client = client_for(owner)
    role_limit = client.post(
        url(org, "approval-limits"),
        {
            "doc_type": "purchase_order",
            "max_amount": "2500",
            "role": str(system("accountant", RoleScope.PRACTICE).public_id),
        },
        format="json",
    )
    assert role_limit.status_code == 201
    assert role_limit.json()["role"]["name"] == "Accountant"
    both = client.post(
        url(org, "approval-limits"),
        {
            "doc_type": "bill",
            "max_amount": "1",
            "role": str(system("sales").public_id),
            "user": str(owner.public_id),
        },
        format="json",
    )
    assert both.status_code == 400
    neither = client.post(
        url(org, "approval-limits"), {"doc_type": "bill", "max_amount": "1"}, format="json"
    )
    assert neither.status_code == 400
    negative = client.post(
        url(org, "approval-limits"),
        {"doc_type": "bill", "max_amount": "-1", "user": str(owner.public_id)},
        format="json",
    )
    assert negative.status_code == 400 and "max_amount" in negative.json()
    stranger = make_user("x@elsewhere.ca", "Stranger")
    assert (
        client.post(
            url(org, "approval-limits"),
            {"doc_type": "bill", "max_amount": "1", "user": str(stranger.public_id)},
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.post(
            url(org, "approval-limits"),
            {"doc_type": "invoice", "max_amount": "1", "user": str(owner.public_id)},
            format="json",
        ).status_code
        == 400
    )


@pytest.mark.tenant_isolation
def test_another_organisations_limit_is_unknown(org: Organisation, owner: User) -> None:
    other = Organisation.objects.create(name="Elsewhere Ltd.")
    with org_context(other):
        foreign = ApprovalLimit.objects.create(
            role=system("owner"), doc_type="bill", max_amount=Decimal(1)
        )
    client = client_for(owner)
    for verb in ("get", "patch", "delete"):
        answer = getattr(client, verb)(
            url(org, f"approval-limits/{foreign.public_id}"), {"max_amount": "9"}, format="json"
        )
        assert answer.status_code == 404
    foreign.refresh_from_db()
    assert foreign.max_amount == Decimal("1.00") and foreign.deleted_at is None


# ---- OpenAPI -------------------------------------------------------------------------------


def test_openapi_documents_every_route(tmp_path: Path) -> None:
    out = tmp_path / "schema.yaml"
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(out))
    paths = yaml.safe_load(out.read_text(encoding="utf-8"))["paths"]
    org = "/api/v1/o/{org}/"
    assert set(paths["/api/v1/permissions/catalogue"]) == {"get"}
    assert set(paths[f"{org}roles"]) == {"get", "post"}
    assert set(paths[f"{org}roles/{{role_id}}"]) == {"get", "patch", "delete"}
    assert set(paths[f"{org}members"]) == {"get"}
    assert set(paths[f"{org}members/{{user_id}}/roles"]) == {"post"}
    assert set(paths[f"{org}members/{{user_id}}/roles/{{role_id}}"]) == {"delete"}
    assert set(paths[f"{org}invitations"]) == {"get"}
    assert set(paths[f"{org}approval-limits"]) == {"get", "post"}
    assert set(paths[f"{org}approval-limits/{{public_id}}"]) == {"get", "patch", "delete"}
    assert "201" in paths[f"{org}roles"]["post"]["responses"]


def test_my_permissions(org: Organisation, owner: User) -> None:
    mine = client_for(owner).get(url(org, "my-permissions")).json()["permissions"]
    assert "organisation.close" in mine and mine == sorted(mine)
    sales = client_for(member(org, "sales", "sam@refined.ca", "Sam Patel"))
    assert sales.get(url(org, "my-permissions")).json() == {
        "permissions": ["documents.file.view", "organisation.profile.view"]
    }
    other = Organisation.objects.create(name="Elsewhere Ltd.")
    outsider = client_for(member(other, "owner", "x@elsewhere.ca", "Out Sider"))
    assert outsider.get(url(org, "my-permissions")).status_code == 404


def test_limit_saved_through_the_api_is_enforced_by_the_check(
    org: Organisation, owner: User
) -> None:
    """A-03-T13 acceptance (backend half): a limit saved in the editor is the one enforced."""
    sam = member(org, "purchasing", "sam@refined.ca", "Sam Patel")
    client = client_for(owner)
    client.post(
        url(org, "approval-limits"),
        {"doc_type": "bill", "max_amount": "5000", "user": str(sam.public_id)},
        format="json",
    )
    client.post(
        url(org, "approval-limits"),
        {"doc_type": "bill", "max_amount": "50000", "user": str(owner.public_id)},
        format="json",
    )
    check = url(org, "approval-limits/check")
    ok = client.get(check, {"doc_type": "bill", "amount": "5000", "user": str(sam.public_id)})
    assert ok.json() == {
        "allowed": True,
        "limit": "5000.00",
        "code": None,
        "detail": None,
        "approvers": [],
    }
    over = client.get(
        check, {"doc_type": "bill", "amount": "5001", "user": str(sam.public_id)}
    ).json()
    assert over["allowed"] is False and over["code"] == "approval.limit_exceeded"
    assert over["detail"].startswith("This bill is for $5,001.00, above your approval limit")
    assert [a["name"] for a in over["approvers"]] == ["Avery Owner"]
    none = client.get(
        check, {"doc_type": "pay_run", "amount": "1", "user": str(sam.public_id)}
    ).json()
    assert none["allowed"] is False and none["code"] == "approval.no_limit"
    stranger = make_user("x@elsewhere.ca", "Stranger")
    assert (
        client.get(
            check, {"doc_type": "bill", "amount": "1", "user": str(stranger.public_id)}
        ).status_code
        == 400
    )
    assert client.get(check, {"doc_type": "bill"}).status_code == 400
