"""V-05-T04 — assignment editor API (organisations / groups).

Acceptance: an assignment grants access immediately — the staff member opens the organisation on
the very next request — and removing it revokes it as fast; group assignments the same; audited;
only ``practice.clients.assign`` / ``practice.groups.manage``.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.audit.models import AuditEvent
from numo9.tenancy.models import PracticeRole
from numo9.workspace.groups import add_organisation, create_group
from numo9.workspace.summary import rebuild_all
from tests.workspace_helpers import client_org, member, practice, user

pytestmark = pytest.mark.django_db(transaction=True)
BASE = "/api/v1/practice/staff"


@pytest.fixture
def world() -> dict[str, Any]:
    firm = practice("Abuodeh CPA")
    admin = user("ada@cpa.ca", name="Ada Admin")
    member(firm, admin, role=PracticeRole.PRACTICE_ADMIN)
    sam_user = user("sam@cpa.ca", name="Sam Patel")
    member(firm, sam_user)
    org = client_org(firm, "Maple Leaf Supply", settings={})
    other = client_org(firm, "Birch Holdings", settings={})
    rebuild_all()
    admin_browser, sam_browser = Client(), Client()
    admin_browser.force_login(admin)
    sam_browser.force_login(sam_user)
    return {
        "firm": firm,
        "org": org,
        "other": other,
        "sam": sam_user,
        "admin": admin_browser,
        "sam_browser": sam_browser,
    }


def url(world: dict[str, Any], tail: str) -> str:
    return f"{BASE}/{world['sam'].public_id}/{tail}?practice={world['firm'].public_id}"


def opens(world: dict[str, Any], org: Any) -> int:
    return world["sam_browser"].get(f"/api/v1/o/{org.public_id}/settings").status_code


def test_direct_assignment_grants_and_revokes_at_once(world: dict[str, Any]) -> None:
    assert opens(world, world["org"]) == 404
    response = world["admin"].put(url(world, f"organisations/{world['org'].public_id}"))
    assert response.status_code == 200, response.content
    assert [o["name"] for o in response.json()["organisations"]] == ["Maple Leaf Supply"]
    assert opens(world, world["org"]) == 200  # the very next request
    assert opens(world, world["other"]) == 404
    assert AuditEvent.platform_events.filter(
        action="staff.organisation_assigned", organisation=world["org"]
    ).exists()
    removed = world["admin"].delete(url(world, f"organisations/{world['org'].public_id}"))
    assert removed.json()["organisations"] == []
    assert opens(world, world["org"]) == 404


def test_group_assignment_grants_and_revokes_at_once(world: dict[str, Any]) -> None:
    group = create_group(world["firm"], "Toronto office")
    add_organisation(group, world["other"])
    response = world["admin"].put(
        url(world, f"groups/{group.public_id}"),
        {"role": "reviewer"},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["groups"] == [
        {"id": str(group.public_id), "name": "Toronto office", "role": "reviewer", "depth": 1}
    ]
    assert opens(world, world["other"]) == 200
    world["admin"].delete(url(world, f"groups/{group.public_id}"))
    assert opens(world, world["other"]) == 404
    listed = world["admin"].get(url(world, "assignments")).json()
    assert listed == {"organisations": [], "groups": []}


def test_only_managers_assign(world: dict[str, Any]) -> None:
    refused = world["sam_browser"].put(url(world, f"organisations/{world['org'].public_id}"))
    assert refused.status_code == 403
    unknown = world["admin"].put(
        f"{BASE}/{world['sam'].public_id}/organisations/00000000-0000-4000-8000-000000000000"
        f"?practice={world['firm'].public_id}"
    )
    assert unknown.status_code == 404
    stranger = client_org(None, "Not served", settings={})
    assert world["admin"].put(url(world, f"organisations/{stranger.public_id}")).status_code == 404
