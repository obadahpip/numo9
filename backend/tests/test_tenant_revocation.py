"""A-01-T10 — revocation: access removed in the middle of a signed-in session takes effect on the
very next request (404), because nothing about access is cached in the session or the process.

Each scenario signs in through the real session login, proves access (200 on list and detail),
revokes it in one specific way, and expects 404 on the next requests with the same session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)
from tests.testapp.models import Widget

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.tenant_isolation,
    pytest.mark.urls("tests.testapp.sweep_urls"),
]

PASSWORD = "correct-horse-battery-staple"  # noqa: S105 (test fixture)


@dataclass
class World:
    user: User
    org: Organisation
    widget: Widget
    practice: Practice
    member: PracticeMember | None
    assignment: PracticeAssignment | None
    org_member: OrganisationMember | None


def world(*, via: str) -> World:
    """A signed-in user with access to ``org`` through one path: org member, staff or admin."""
    user = User.objects.create_user("acc@example.com", PASSWORD, name="Acc")
    org = Organisation.objects.create(name="Maple Bakery")
    practice = Practice.objects.create(name="Profitex")
    with org_context(org):
        widget = Widget.objects.create(label="w1")
    member = assignment = org_member = None
    if via == "org_member":
        org_member = OrganisationMember.objects.create(
            organisation=org, user=user, role=OrganisationRole.SALES
        )
    else:
        role = PracticeRole.PRACTICE_ADMIN if via == "practice_admin" else PracticeRole.ACCOUNTANT
        member = PracticeMember.objects.create(practice=practice, user=user, role=role)
        assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
        if via == "staff":
            assignment.assigned_staff.add(member)
    return World(user, org, widget, practice, member, assignment, org_member)


def signed_in(w: World) -> Client:
    client = Client()
    assert client.login(username=w.user.email, password=PASSWORD)
    return client


def urls(w: World) -> list[str]:
    base = f"/api/v1/o/{w.org.public_id}/widgets/"
    return [base, f"{base}{w.widget.public_id}/"]


def statuses(client: Client, w: World) -> list[int]:
    return [client.get(url).status_code for url in urls(w)]


def _remove_staff(w: World) -> None:
    assert w.assignment is not None and w.member is not None
    w.assignment.assigned_staff.remove(w.member)


def _deactivate_assignment(w: World) -> None:
    assert w.assignment is not None
    w.assignment.active = False
    w.assignment.save()


def _delete_assignment(w: World) -> None:
    assert w.assignment is not None
    w.assignment.delete()


def _remove_practice_member(w: World) -> None:
    assert w.member is not None
    w.member.delete()


def _downgrade_practice_admin(w: World) -> None:
    assert w.member is not None
    w.member.role = PracticeRole.ACCOUNTANT
    w.member.save()


def _remove_org_member(w: World) -> None:
    assert w.org_member is not None
    w.org_member.delete()


SCENARIOS: list[tuple[str, str, Callable[[World], None]]] = [
    ("staff", "staff removed from the assignment", _remove_staff),
    ("staff", "assignment deactivated", _deactivate_assignment),
    ("staff", "assignment deleted", _delete_assignment),
    ("staff", "practice membership removed", _remove_practice_member),
    ("practice_admin", "assignment deactivated", _deactivate_assignment),
    ("practice_admin", "practice membership removed", _remove_practice_member),
    ("practice_admin", "practice admin downgraded to accountant", _downgrade_practice_admin),
    ("org_member", "organisation membership removed", _remove_org_member),
]


@pytest.mark.parametrize(
    ("via", "revoke"),
    [(via, fn) for via, _, fn in SCENARIOS],
    ids=[f"{via}: {label}" for via, label, _ in SCENARIOS],
)
def test_revoked_access_is_404_on_the_next_request(
    via: str, revoke: Callable[[World], None]
) -> None:
    w = world(via=via)
    client = signed_in(w)
    assert statuses(client, w) == [200, 200]
    revoke(w)
    assert statuses(client, w) == [404, 404]
    assert statuses(client, w) == [404, 404]  # and stays revoked


def test_restored_access_works_again_without_new_login() -> None:
    w = world(via="staff")
    client = signed_in(w)
    _remove_staff(w)
    assert statuses(client, w) == [404, 404]
    assert w.assignment is not None and w.member is not None
    w.assignment.assigned_staff.add(w.member)  # no negative caching either
    assert statuses(client, w) == [200, 200]


def test_revoking_one_path_keeps_access_through_another() -> None:
    w = world(via="staff")
    OrganisationMember.objects.create(organisation=w.org, user=w.user, role=OrganisationRole.HR)
    client = signed_in(w)
    _deactivate_assignment(w)
    assert statuses(client, w) == [200, 200]


def test_deactivated_user_loses_the_session() -> None:
    w = world(via="org_member")
    client = signed_in(w)
    assert statuses(client, w) == [200, 200]
    w.user.is_active = False
    w.user.save()
    assert all(status in (401, 403) for status in statuses(client, w))
