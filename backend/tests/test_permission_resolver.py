"""Permission resolver has_perm (A-03-T04). Acceptance: the truth table passes.

Cases: organisation member roles; practice access (practice-wide role, assigned staff, not
assigned, inactive assignment); custom organisation and practice roles; a user with both a
practice role and an organisation role in the same organisation (union); no access → nothing;
request-level cache and revocation on the next request.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from numo9.accounts.models import User
from numo9.rbac.catalogue import UnknownPermission
from numo9.rbac.models import Role, RoleAssignment, RolePermission, RoleScope
from numo9.rbac.resolver import (
    has_perm,
    has_platform_perm,
    has_practice_perm,
    organisation_permissions,
    permission_cache,
)
from numo9.tenancy.models import (
    AssignmentRole,
    Organisation,
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)

pytestmark = pytest.mark.django_db

VIEW = "organisation.profile.view"
SETTINGS = "organisation.settings.manage"
CLOSE = "organisation.close"
INVITE = "organisation.members.invite"
LIMITS = "roles.limit.manage"


def make_user(email: str) -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=email.split("@")[0])


@pytest.fixture
def world() -> dict[str, Any]:
    org = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    other = Organisation.objects.create(name="Northern Lights Bakery Inc.")
    practice = Practice.objects.create(name="Profitex")
    assignment = PracticeAssignment.objects.create(
        practice=practice, organisation=org, role=AssignmentRole.FULL_SERVICE
    )
    return {"org": org, "other": other, "practice": practice, "assignment": assignment}


def member(org: Organisation, role: str, email: str) -> User:
    user = make_user(email)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


def staff(world: dict[str, Any], role: str, email: str, assigned: bool) -> User:
    user = make_user(email)
    pm = PracticeMember.objects.create(practice=world["practice"], user=user, role=role)
    if assigned:
        world["assignment"].assigned_staff.add(pm)
    return user


# ---- the truth table ---------------------------------------------------------------------------

TABLE = [
    # (how the user relates to the organisation, VIEW, SETTINGS, INVITE, CLOSE, LIMITS)
    ("owner", True, True, True, True, True),
    ("admin", True, True, True, False, True),
    ("accountant_delegate", True, True, False, False, False),
    ("sales", True, False, False, False, False),
    ("employee", True, False, False, False, False),
    ("practice_admin (not assigned)", True, True, True, False, True),
    ("accountant assigned", True, True, False, False, False),
    ("accountant not assigned", False, False, False, False, False),
    ("reviewer assigned", True, False, False, False, False),
    ("read_only assigned", True, False, False, False, False),
    ("accountant assigned, assignment inactive", False, False, False, False, False),
    ("member of another organisation only", False, False, False, False, False),
    ("nobody", False, False, False, False, False),
]


def build(world: dict[str, Any], case: str) -> User:
    org = world["org"]
    if case in {"owner", "admin", "accountant_delegate", "sales", "employee"}:
        return member(org, case, f"{case}@maple.ca")
    if case == "practice_admin (not assigned)":
        return staff(world, "practice_admin", "pa@profitex.ca", assigned=False)
    if case.endswith(" assigned") and " not " not in case:
        return staff(world, case.split()[0], f"{case.split()[0]}@profitex.ca", assigned=True)
    if case == "accountant not assigned":
        return staff(world, "accountant", "lonely@profitex.ca", assigned=False)
    if case == "accountant assigned, assignment inactive":
        user = staff(world, "accountant", "inactive@profitex.ca", assigned=True)
        world["assignment"].active = False
        world["assignment"].save()
        return user
    if case == "member of another organisation only":
        return member(world["other"], "owner", "other@bakery.ca")
    return make_user("nobody@example.ca")


@pytest.mark.parametrize("case, view, settings, invite, close, limits", TABLE)
def test_truth_table(
    world: dict[str, Any],
    case: str,
    view: bool,
    settings: bool,
    invite: bool,
    close: bool,
    limits: bool,
) -> None:
    user = build(world, case)
    org = world["org"]
    got = tuple(has_perm(user, org, key) for key in (VIEW, SETTINGS, INVITE, CLOSE, LIMITS))
    assert got == (view, settings, invite, close, limits)


def test_union_of_practice_and_organisation_roles(world: dict[str, Any]) -> None:
    """A Sales member who is also assigned through the practice as accountant gets both sets."""
    org = world["org"]
    user = staff(world, "accountant", "both@profitex.ca", assigned=True)
    OrganisationMember.objects.create(organisation=org, user=user, role="sales")
    assert has_perm(user, org, SETTINGS)  # from the practice accountant role
    assert not has_perm(user, org, INVITE)  # neither role allows it
    OrganisationMember.objects.filter(user=user).update(role="admin")
    assert has_perm(user, org, INVITE)  # now from the organisation admin role


def test_custom_organisation_role_adds_permissions(world: dict[str, Any]) -> None:
    org = world["org"]
    user = member(org, "sales", "sam@maple.ca")
    assert not has_perm(user, org, LIMITS)
    role = Role.objects.create(scope=RoleScope.ORGANISATION, name="Controller", organisation=org)
    RolePermission.objects.create(role=role, permission=LIMITS)
    RoleAssignment.objects.create(role=role, user=user, organisation=org)
    assert has_perm(user, org, LIMITS)
    # Only where it is assigned: the same user in another organisation gets nothing from it.
    OrganisationMember.objects.create(organisation=world["other"], user=user, role="employee")
    assert not has_perm(user, world["other"], LIMITS)


def test_custom_practice_role_applies_in_served_organisations(world: dict[str, Any]) -> None:
    org, practice = world["org"], world["practice"]
    user = staff(world, "read_only", "ro@profitex.ca", assigned=True)
    assert not has_perm(user, org, SETTINGS)
    role = Role.objects.create(scope=RoleScope.PRACTICE, name="Settings helper", practice=practice)
    RolePermission.objects.create(role=role, permission=SETTINGS)
    RolePermission.objects.create(role=role, permission="practice.clients.create")
    RoleAssignment.objects.create(role=role, user=user, practice=practice)
    assert has_perm(user, org, SETTINGS)
    assert has_practice_perm(user, practice, "practice.clients.create")
    assert not has_perm(user, world["other"], SETTINGS)  # not served by the practice


def test_no_access_means_no_permissions_whatever_the_roles(world: dict[str, Any]) -> None:
    org = world["org"]
    user = member(org, "owner", "gone@maple.ca")
    assert has_perm(user, org, CLOSE)
    user.is_active = False
    user.save()
    assert organisation_permissions(user, org) == frozenset()
    from django.contrib.auth.models import AnonymousUser

    assert not has_perm(AnonymousUser(), org, VIEW)


def test_practice_permissions(world: dict[str, Any]) -> None:
    practice = world["practice"]
    admin = staff(world, "practice_admin", "pa@profitex.ca", assigned=False)
    accountant = staff(world, "accountant", "acc@profitex.ca", assigned=True)
    assert has_practice_perm(admin, practice, "practice.staff.manage")
    assert has_practice_perm(accountant, practice, "practice.clients.create")
    assert not has_practice_perm(accountant, practice, "practice.staff.manage")
    outsider = make_user("out@example.ca")
    assert not has_practice_perm(outsider, practice, "practice.profile.view")


def test_platform_permissions_only_from_platform_roles(world: dict[str, Any]) -> None:
    user = member(world["org"], "owner", "owner@maple.ca")
    user.is_superuser = user.is_staff = True  # no bypass for Django flags
    user.save()
    assert not has_platform_perm(user, "platform.console.view")
    support = Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key="platform_support")
    RoleAssignment.objects.create(role=support, user=user)
    assert has_platform_perm(user, "platform.console.view")
    assert not has_platform_perm(user, "platform.catalogue.manage")


def test_wrong_scope_or_unknown_key_is_a_programming_error(world: dict[str, Any]) -> None:
    user = make_user("dev@example.ca")
    with pytest.raises(UnknownPermission):
        has_perm(user, world["org"], "organisation.profile.veiw")
    with pytest.raises(ValueError, match="practice permission"):
        has_perm(user, world["org"], "practice.staff.view")


# ---- caching ---------------------------------------------------------------------------------


def test_cached_within_a_request_only(world: dict[str, Any]) -> None:
    org = world["org"]
    user = member(org, "admin", "admin@maple.ca")
    with permission_cache():
        assert has_perm(user, org, INVITE)
        with CaptureQueriesContext(connection) as queries:
            assert has_perm(user, org, SETTINGS)
            assert not has_perm(user, org, CLOSE)
        assert len(queries) == 0
    # A new request sees the change at once (no cache across requests).
    OrganisationMember.objects.filter(user=user).update(role="employee")
    with permission_cache():
        assert not has_perm(user, org, INVITE)


def test_without_a_cache_every_check_reads_the_database(world: dict[str, Any]) -> None:
    org = world["org"]
    user = member(org, "admin", "admin2@maple.ca")
    with CaptureQueriesContext(connection) as queries:
        has_perm(user, org, VIEW)
    first = len(queries)
    with CaptureQueriesContext(connection) as queries:
        has_perm(user, org, VIEW)
    assert len(queries) == first > 0


def test_middleware_opens_one_cache_per_request() -> None:
    from django.conf import settings
    from django.http import HttpResponse
    from django.test import RequestFactory

    from numo9.rbac.resolver import PermissionCacheMiddleware, _cache

    assert "numo9.rbac.resolver.PermissionCacheMiddleware" in settings.MIDDLEWARE
    seen: list[object] = []

    def view(request: object) -> HttpResponse:
        seen.append(_cache.get())
        return HttpResponse()

    middleware = PermissionCacheMiddleware(view)
    middleware(RequestFactory().get("/"))
    middleware(RequestFactory().get("/"))
    assert seen[0] == {} and seen[1] == {} and seen[0] is not seen[1]
    assert _cache.get() is None  # nothing leaks out of a request
