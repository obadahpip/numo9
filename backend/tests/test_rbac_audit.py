"""Audit hooks for role / limit changes (A-03-T15): every change emits one event with its diff.

Acceptance "diff visible" needs the audit log (A-04); these tests prove each change through the
API emits the right event — actor, organisation, object, ``{field: [before, after]}`` — on the
``rbac_changed`` signal and the ``numo9.audit`` log, ready for A-04-T03 to store.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.rbac.audit import RbacChange, diff, rbac_changed, record
from numo9.rbac.models import Role, RoleScope
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = pytest.mark.django_db


@pytest.fixture
def events() -> Iterator[list[RbacChange]]:
    seen: list[RbacChange] = []

    def receiver(sender: Any, change: RbacChange, **kwargs: Any) -> None:
        seen.append(change)

    rbac_changed.connect(receiver, weak=False)
    try:
        yield seen
    finally:
        rbac_changed.disconnect(receiver)


def make_user(email: str, name: str) -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=name)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def owner(org: Organisation) -> User:
    user = make_user("avery@refined.ca", "Avery Owner")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    return user


@pytest.fixture
def sam(org: Organisation) -> User:
    user = make_user("sam@refined.ca", "Sam Patel")
    OrganisationMember.objects.create(organisation=org, user=user, role="purchasing")
    return user


def api(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def url(org: Organisation, path: str) -> str:
    return f"/api/v1/o/{org.public_id}/{path}"


def test_diff_lists_only_changed_fields() -> None:
    assert diff({"a": 1, "b": ["x"], "c": None}, {"a": 1, "b": ["x", "y"], "d": "new"}) == {
        "b": [["x"], ["x", "y"]],
        "d": [None, "new"],
    }
    with pytest.raises(ValueError, match="Unknown audit action"):
        record("role.renamed", actor=None, organisation=None, obj=None, label="")


def test_role_lifecycle_is_audited_with_diffs(
    org: Organisation, owner: User, events: list[RbacChange]
) -> None:
    client = api(owner)
    role = client.post(
        url(org, "roles"),
        {"name": "Buyer", "permissions": ["organisation.profile.view"]},
        format="json",
    ).json()
    client.patch(
        url(org, f"roles/{role['id']}"),
        {"name": "Senior buyer", "permissions": ["organisation.members.view"]},
        format="json",
    )
    client.patch(url(org, f"roles/{role['id']}"), {"name": "Senior buyer"}, format="json")
    client.delete(url(org, f"roles/{role['id']}"))
    assert [e.action for e in events] == ["role.created", "role.updated", "role.deleted"]
    created, updated, deleted = events
    assert created.actor_id == str(owner.public_id)
    assert created.organisation_id == str(org.public_id)
    assert created.object_type == "rbac.Role" and created.object_id == role["id"]
    assert created.changes == {
        "description": [None, ""],
        "name": [None, "Buyer"],
        "permissions": [None, ["organisation.profile.view"]],
    }
    assert updated.changes == {
        "name": ["Buyer", "Senior buyer"],
        "permissions": [["organisation.profile.view"], ["organisation.members.view"]],
    }  # the no-op PATCH emitted nothing
    assert deleted.changes["name"] == ["Senior buyer", None]


def test_assignments_and_main_role_are_audited(
    org: Organisation, owner: User, sam: User, events: list[RbacChange]
) -> None:
    client = api(owner)
    buyer = Role.objects.create(scope=RoleScope.ORGANISATION, name="Buyer", organisation=org)
    admin = Role.objects.get(is_system=True, scope=RoleScope.ORGANISATION, key="admin")
    client.post(url(org, f"members/{sam.public_id}/roles"), {"role": str(buyer.public_id)})
    client.post(url(org, f"members/{sam.public_id}/roles"), {"role": str(buyer.public_id)})
    client.post(url(org, f"members/{sam.public_id}/roles"), {"role": str(admin.public_id)})
    client.delete(url(org, f"members/{sam.public_id}/roles/{buyer.public_id}"))
    assert [e.action for e in events] == [
        "role.assigned",
        "member.main_role_changed",
        "role.unassigned",
    ]  # giving a role already held emits nothing
    assigned, main, unassigned = events
    assert assigned.object_type == "rbac.RoleAssignment"
    assert assigned.object_label == "Buyer → Sam Patel"
    assert assigned.changes == {
        "role": [None, str(buyer.public_id)],
        "user": [None, str(sam.public_id)],
    }
    assert main.object_type == "accounts.User" and main.object_id == str(sam.public_id)
    assert main.changes == {"main_role": ["purchasing", "admin"]}
    assert unassigned.changes["role"] == [str(buyer.public_id), None]


def test_limits_are_audited_with_amount_diffs(
    org: Organisation, owner: User, sam: User, events: list[RbacChange]
) -> None:
    client = api(owner)
    row = client.post(
        url(org, "approval-limits"),
        {"doc_type": "bill", "max_amount": "5000", "user": str(sam.public_id)},
        format="json",
    ).json()
    client.patch(url(org, f"approval-limits/{row['id']}"), {"max_amount": "7500"}, format="json")
    client.patch(url(org, f"approval-limits/{row['id']}"), {"max_amount": "7500"}, format="json")
    client.delete(url(org, f"approval-limits/{row['id']}"))
    assert [e.action for e in events] == ["limit.created", "limit.updated", "limit.deleted"]
    created, updated, deleted = events
    assert created.object_label == "Sam Patel"
    assert created.changes["max_amount"] == [None, "5000.00"]
    assert created.changes["user"] == [None, str(sam.public_id)]
    assert updated.changes == {"max_amount": ["5000.00", "7500.00"]}
    assert deleted.changes["max_amount"] == ["7500.00", None]


def test_access_requests_are_audited(
    org: Organisation, owner: User, events: list[RbacChange]
) -> None:
    sales = make_user("lee@refined.ca", "Lee Sales")
    OrganisationMember.objects.create(organisation=org, user=sales, role="sales")
    request = (
        api(sales)
        .post(url(org, "access-requests"), {"permission": "roles.role.view"}, format="json")
        .json()
    )
    api(owner).delete(url(org, f"access-requests/{request['id']}"))
    assert [e.action for e in events] == ["access_request.created", "access_request.closed"]
    assert events[0].actor_id == str(sales.public_id)
    assert events[0].changes["permission"] == [None, "roles.role.view"]
    assert events[1].actor_id == str(owner.public_id)


def test_refused_changes_emit_nothing(
    org: Organisation, owner: User, sam: User, events: list[RbacChange]
) -> None:
    api(sam).post(url(org, "roles"), {"name": "Mine"}, format="json")  # 403
    api(owner).post(url(org, "roles"), {"name": "X", "permissions": ["nope.x"]}, format="json")
    owner_role = Role.objects.get(is_system=True, scope=RoleScope.ORGANISATION, key="owner")
    api(owner).patch(url(org, f"roles/{owner_role.public_id}"), {"name": "Boss"}, format="json")
    assert events == []


def test_events_reach_the_audit_log(
    org: Organisation, owner: User, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="numo9.audit"):
        api(owner).post(url(org, "roles"), {"name": "Buyer"}, format="json")
    entries = [r for r in caplog.records if r.name == "numo9.audit"]
    assert len(entries) == 1
    payload = entries[0].audit  # type: ignore[attr-defined]
    assert payload["action"] == "role.created"
    assert payload["changes"]["name"] == [None, "Buyer"]
