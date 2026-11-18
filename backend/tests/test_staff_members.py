"""V-05-T05 — suspend / remove member service (last-admin guard).

Acceptance: removing (or suspending) the last active practice admin is refused; a suspended
member keeps their history but reaches nothing (organisations, directory, practice API) until
reinstated; a removed member loses every organisation at once; each change audited.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client
from rest_framework.exceptions import APIException

from numo9.audit.models import AuditEvent
from numo9.staff import members
from numo9.tenancy.models import PracticeMember, PracticeRole
from numo9.workspace.groups import add_organisation, assign_staff, create_group
from numo9.workspace.models import GroupStaffAssignment
from numo9.workspace.summary import rebuild_all
from tests.workspace_helpers import client_org, member, practice, user

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def world() -> dict[str, Any]:
    firm = practice("Abuodeh CPA")
    ada = user("ada@cpa.ca", name="Ada Admin")
    admin = member(firm, ada, role=PracticeRole.PRACTICE_ADMIN)
    sam_user = user("sam@cpa.ca", name="Sam Patel")
    sam = member(firm, sam_user)
    org = client_org(firm, "Maple Leaf Supply", settings={}, staff=[sam])
    grouped = client_org(firm, "Birch Holdings", settings={})
    group = create_group(firm, "Toronto office")
    add_organisation(group, grouped)
    assign_staff(group, sam)
    rebuild_all()
    browser = Client()
    browser.force_login(sam_user)
    return {
        "firm": firm,
        "admin": admin,
        "sam": sam,
        "org": org,
        "grouped": grouped,
        "sam_browser": browser,
        "ada": ada,
    }


def reaches(world: dict[str, Any], org: Any) -> int:
    return world["sam_browser"].get(f"/api/v1/o/{org.public_id}/settings").status_code


def directory(world: dict[str, Any]) -> int:
    return (
        world["sam_browser"]
        .get(f"/api/v1/practice/orgs?practice={world['firm'].public_id}")
        .status_code
    )


def test_last_admin_cannot_be_removed_or_suspended(world: dict[str, Any]) -> None:
    for action in (members.remove, members.suspend):
        with pytest.raises(APIException) as refused:
            action(world["admin"])
        assert "staff.last_admin" in str(refused.value.get_codes())
    assert PracticeMember.objects.filter(pk=world["admin"].pk, suspended_at__isnull=True).exists()
    second = member(world["firm"], user("bo@cpa.ca"), role=PracticeRole.PRACTICE_ADMIN)
    members.suspend(world["admin"])  # another active admin exists now
    with pytest.raises(APIException):
        members.remove(second)  # …and is now the last active one


def test_suspended_member_reaches_nothing_until_reinstated(world: dict[str, Any]) -> None:
    assert (reaches(world, world["org"]), reaches(world, world["grouped"]), directory(world)) == (
        200,
        200,
        200,
    )
    members.suspend(world["sam"], by=world["ada"])
    assert (reaches(world, world["org"]), reaches(world, world["grouped"]), directory(world)) == (
        404,
        404,
        404,
    )
    assert GroupStaffAssignment.objects.filter(practice_member=world["sam"]).exists()  # kept
    members.reinstate(world["sam"], by=world["ada"])
    assert reaches(world, world["org"]) == 200 and reaches(world, world["grouped"]) == 200
    actions = list(
        AuditEvent.platform_events.filter(object_id=str(world["sam"].user.public_id))
        .order_by("created_at")
        .values_list("action", flat=True)
    )
    assert actions[-2:] == ["staff.member_suspended", "staff.member_reinstated"]


def test_removed_member_loses_everything_at_once(world: dict[str, Any]) -> None:
    members.remove(world["sam"], by=world["ada"])
    assert not PracticeMember.objects.filter(pk=world["sam"].pk).exists()
    assert (reaches(world, world["org"]), reaches(world, world["grouped"]), directory(world)) == (
        404,
        404,
        404,
    )
    event = AuditEvent.platform_events.get(action="staff.member_removed")
    assert event.meta["organisations"] == [str(world["org"].public_id)]


def test_api_suspend_reinstate_remove(world: dict[str, Any]) -> None:
    admin = Client()
    admin.force_login(world["ada"])
    base = f"/api/v1/practice/staff/{world['sam'].user.public_id}"
    q = f"?practice={world['firm'].public_id}"
    suspended = admin.post(f"{base}/suspend{q}")
    assert suspended.status_code == 200 and suspended.json()["status"] == "suspended"
    assert admin.post(f"{base}/reinstate{q}").json()["status"] == "active"
    assert admin.post(f"{base}/reinstate{q}").status_code == 409
    last = admin.delete(f"/api/v1/practice/staff/{world['ada'].public_id}{q}")
    assert last.status_code == 409 and last.json()["code"] == "staff.last_admin"
    assert admin.delete(f"{base}{q}").status_code == 204
    assert world["sam_browser"].post(f"{base}/suspend{q}").status_code in (403, 404)
