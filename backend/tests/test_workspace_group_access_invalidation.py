"""V-02-T06 — Cache invalidation on any membership/assignment change.

Acceptance: a revocation is effective on the next request. A staff member who reaches a client
only through a practice group opens the client's settings (``/api/v1/o/<org>/settings``: an
organisation-scoped endpoint); the cache is warm; then one change takes the access away and the
very next request answers 404. Every way the rows change is covered: service calls, deletes
(cascading from a deleted group), group moves (raw SQL paths), bulk ``update()`` /
``bulk_create()`` on workspace and tenancy rows. Access through a second group or a direct
assignment survives removal from one group; grants are effective on the next request too.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from django.test import Client

from numo9.tenancy.models import Organisation, PracticeAssignment, PracticeMember
from numo9.workspace.access import group_organisation_ids
from numo9.workspace.groups import (
    add_organisation,
    assign_staff,
    create_group,
    move_group,
    remove_organisation,
    unassign_staff,
)
from numo9.workspace.models import GroupStaffAssignment, OrgGroup, OrgGroupMembership
from tests.workspace_helpers import client_org, member, practice, user

pytestmark = pytest.mark.django_db


class World:
    def __init__(self) -> None:
        self.admin = user("admin@cpa.ca")
        self.firm = practice("Abuodeh CPA", self.admin)
        self.person = user("sam@cpa.ca", "Sam Patel")
        self.staff = member(self.firm, self.person)
        self.org = client_org(self.firm, "Maple Leaf Supply Ltd.")
        self.toronto = create_group(self.firm, "Toronto office")
        self.retail = create_group(self.firm, "Retail clients", self.toronto)
        add_organisation(self.retail, self.org)
        assign_staff(self.toronto, self.staff)
        self.browser = Client()
        self.browser.force_login(self.person)

    def status(self, organisation: Organisation | None = None) -> int:
        target = organisation or self.org
        return int(self.browser.get(f"/api/v1/o/{target.public_id}/settings").status_code)


@pytest.fixture
def world() -> World:
    return World()


def _warm(world: World) -> None:
    assert world.status() == 200
    assert world.status() == 200  # second request answered from the cache
    assert world.org.pk in group_organisation_ids(world.person)


def _switch_off(world: World) -> None:
    assignment = PracticeAssignment.objects.get(practice=world.firm, organisation=world.org)
    assignment.active = False
    assignment.save()


REVOCATIONS: dict[str, Callable[[World], Any]] = {
    "staff unassigned (service)": lambda w: unassign_staff(w.toronto, w.staff),
    "organisation removed from group": lambda w: remove_organisation(w.retail, w.org),
    "membership deleted": lambda w: OrgGroupMembership.objects.filter(group=w.retail).delete(),
    "group deleted (cascade)": lambda w: OrgGroup.objects.get(pk=w.toronto.pk).delete(),
    "sub-group moved out": lambda w: move_group(w.retail, None),
    "practice stops serving": lambda w: _switch_off(w),
    "bulk update of the assignment": lambda w: PracticeAssignment.objects.filter(
        practice=w.firm, organisation=w.org
    ).update(active=False),
    "bulk update moves staff row to another group": lambda w: GroupStaffAssignment.objects.filter(
        practice_member=w.staff
    ).update(group=create_group(w.firm, "Ottawa office")),
    "bulk update moves membership to another group": lambda w: OrgGroupMembership.objects.filter(
        organisation=w.org
    ).update(group=create_group(w.firm, "Archive")),
}


@pytest.mark.parametrize("change", list(REVOCATIONS), ids=list(REVOCATIONS))
def test_revocation_is_effective_on_the_next_request(world: World, change: str) -> None:
    _warm(world)
    REVOCATIONS[change](world)
    assert world.status() == 404
    assert world.org.pk not in group_organisation_ids(world.person)


def test_grant_is_effective_on_the_next_request(world: World) -> None:
    other = client_org(world.firm, "Érable Bakery Inc.")
    assert world.status(other) == 404  # cache warm, without the new client
    add_organisation(world.retail, other)  # filed later: reachable at once
    assert world.status(other) == 200


def test_bulk_create_grants_on_the_next_request(world: World) -> None:
    other = client_org(world.firm, "Érable Bakery Inc.")
    assert world.status(other) == 404
    OrgGroupMembership.objects.bulk_create(
        [OrgGroupMembership(group=world.toronto, organisation=other)]
    )
    assert world.status(other) == 200


def test_bulk_create_of_practice_member_rows_invalidates(world: World) -> None:
    _warm(world)
    generation_before = group_organisation_ids.__globals__["_generation"]()
    PracticeMember.objects.bulk_create(
        [PracticeMember(practice=world.firm, user=user("new@cpa.ca"), role="accountant")]
    )
    assert group_organisation_ids.__globals__["_generation"]() > generation_before


def test_removal_from_one_group_keeps_access_through_another(world: World) -> None:
    ottawa = create_group(world.firm, "Ottawa office")
    add_organisation(ottawa, world.org)
    assign_staff(ottawa, world.staff)
    _warm(world)
    unassign_staff(world.toronto, world.staff)
    assert world.status() == 200  # still reached through Ottawa office


def test_removal_from_group_keeps_direct_assignment(world: World) -> None:
    PracticeAssignment.objects.get(practice=world.firm, organisation=world.org).assigned_staff.add(
        world.staff
    )
    _warm(world)
    unassign_staff(world.toronto, world.staff)
    assert world.status() == 200  # still assigned directly


def test_other_users_cache_is_refreshed_too(world: World) -> None:
    second = user("lee@cpa.ca", "Lee Wong")
    assign_staff(world.toronto, member(world.firm, second))
    other_browser = Client()
    other_browser.force_login(second)
    url = f"/api/v1/o/{world.org.public_id}/settings"
    assert other_browser.get(url).status_code == 200
    _warm(world)
    remove_organisation(world.retail, world.org)  # one change, both users lose access
    assert other_browser.get(url).status_code == 404
    assert world.status() == 404


def test_group_role_decides_permissions(world: World) -> None:
    """The group assignment's role is the role in the reached clients: read-only staff read the
    settings but can't change them; a role change applies on the next request."""
    assign_staff(world.toronto, world.staff, "read_only")
    url = f"/api/v1/o/{world.org.public_id}/settings"
    assert world.browser.get(url).status_code == 200
    body = {"display_name": "Maple Leaf"}
    assert world.browser.patch(url, body, content_type="application/json").status_code == 403
    assign_staff(world.toronto, world.staff, "accountant")
    assert world.browser.patch(url, body, content_type="application/json").status_code != 403
