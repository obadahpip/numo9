"""U-06-T14 — security tests: RBAC on every ``/api/v1/platform/`` endpoint and the impersonation
limits.

RBAC (every method of every platform route, found from the URLconf — nothing is listed by hand):

- each declares a **platform** permission, except the browser's own impersonation
  ``current``/``end`` (signed in; they only ever show or end that browser's session);
- anonymous callers never get through (401/403); organisation and practice users never get through
  (403/404); platform staff without two-factor authentication never get through;
- a platform role gets through exactly the methods whose permission it holds.

Impersonation limits:

- at most 2 hours (API and database), a reason, one open session per staff member, only members of
  the organisation, never oneself or other platform staff;
- while impersonating, every platform endpoint but ``current``/``end`` is refused with
  ``impersonation.blocked`` — a session can't start another or reach the console;
- the session is scoped to its organisation (another one is 404), and expires on time;
- a session id copied into another staff member's browser does nothing.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from numo9.platform.middleware import SESSION_KEY
from numo9.platform.models import ImpersonationSession
from numo9.rbac.catalogue import Scope, catalogue
from numo9.rbac.checks import Declaration, declarations
from numo9.rbac.drf import AUTHENTICATED
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.rbac.system_roles import SYSTEM_ROLES
from numo9.tenancy.models import Organisation, OrganisationMember
from numo9.tenancy.sweep import build_path, iter_endpoints
from tests.auth_helpers import enrol_two_factor
from tests.workspace_helpers import member, practice, user

pytestmark = pytest.mark.django_db

PLATFORM = [d for d in declarations() if d.route.startswith("api/v1/platform/")]
OWN_SESSION = {"api/v1/platform/impersonation/current", "api/v1/platform/impersonation/end"}
_ENDPOINTS = {e.display or e.route: e for e in iter_endpoints()}
PLATFORM_ROLES = [role for role in SYSTEM_ROLES if role.scope == Scope.PLATFORM]
UNKNOWN = "00000000-0000-4000-8000-000000000000"


def _path(declaration: Declaration) -> str:
    endpoint = _ENDPOINTS[declaration.route]
    values = {
        "org_id": UNKNOWN,
        "public_id": UNKNOWN,
        "price_id": UNKNOWN,
        "code": "matrix",
        "metric": "active",
        "name": "matrix.flag",
        "kind": "csv",
    }
    path = build_path(endpoint, values)
    assert path is not None, f"fill the parameters of {declaration.route}"
    return path


def _call(browser: Client, declaration: Declaration) -> Any:
    method = declaration.method.lower()
    return getattr(browser, method)(_path(declaration), {}, content_type="application/json")


def _staff(key: str | None, two_factor: bool = True, email: str = "") -> tuple[Any, Client]:
    person = user(email or f"{key or 'nobody'}@numo9.ca", name="Sam Support")
    if key:
        RoleAssignment.objects.create(
            user=person, role=Role.objects.get(scope=RoleScope.PLATFORM, key=key)
        )
    if two_factor:
        enrol_two_factor(person)
    browser = Client()
    browser.force_login(person)
    return person, browser


def test_platform_routes_are_found() -> None:
    routes = {d.route for d in PLATFORM}
    assert {
        "api/v1/platform/me",
        "api/v1/platform/organisations",
        "api/v1/platform/metrics",
        "api/v1/platform/impersonation",
        "api/v1/platform/flags",
    } <= routes
    assert len(PLATFORM) >= 20


@pytest.mark.parametrize("declaration", PLATFORM, ids=lambda d: f"{d.method} {d.route}")
def test_every_platform_method_declares_a_platform_permission(declaration: Declaration) -> None:
    if declaration.route in OWN_SESSION:
        assert declaration.permission == AUTHENTICATED
    elif declaration.route == "api/v1/platform/me":
        assert declaration.permission == AUTHENTICATED  # answers 404 to anyone without a role
    else:
        assert declaration.permission is not None
        assert catalogue.get(declaration.permission).scope == Scope.PLATFORM


@pytest.mark.parametrize("declaration", PLATFORM, ids=lambda d: f"{d.method} {d.route}")
def test_outsiders_never_get_through(declaration: Declaration) -> None:
    anonymous = Client()
    assert _call(anonymous, declaration).status_code in (401, 403)
    org = Organisation.objects.create(name="Maple")
    owner = user("owner@maple.ca")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    enrol_two_factor(owner)
    accountant = user("cpa@firm.ca")
    member(practice("Firm"), accountant, role="practice_admin")
    enrol_two_factor(accountant)
    for person in (owner, accountant):
        browser = Client()
        browser.force_login(person)
        response = _call(browser, declaration)
        if declaration.route in OWN_SESSION:
            # their own (absent) session: nothing to show, nothing ended, nothing leaked
            assert response.status_code == 200
            assert response.json()["session"] is None
        else:
            assert response.status_code in (403, 404), (person, response.status_code)


@pytest.mark.parametrize("declaration", PLATFORM, ids=lambda d: f"{d.method} {d.route}")
def test_platform_staff_need_two_factor(declaration: Declaration) -> None:
    if declaration.route in OWN_SESSION:
        pytest.skip("the browser's own session")
    _person, browser = _staff("platform_owner", two_factor=False)
    response = _call(browser, declaration)
    assert response.status_code == 403
    assert response.json()["code"] == "auth.two_factor_required"


@pytest.mark.parametrize("role", PLATFORM_ROLES, ids=lambda r: r.key)
def test_each_platform_role_gets_exactly_its_permissions(role: Any) -> None:
    _person, browser = _staff(role.key)
    for declaration in PLATFORM:
        if declaration.permission in (AUTHENTICATED, None):
            continue
        response = _call(browser, declaration)
        allowed = declaration.permission in role.permission_keys()
        if allowed:
            assert response.status_code not in (401, 403), (declaration, response.content)
        else:
            assert response.status_code == 403, (declaration, response.status_code)
            assert response.json()["code"] == "permission.denied"


# ---- impersonation limits ----------------------------------------------------------------------


@pytest.fixture
def world() -> dict[str, Any]:
    org = Organisation.objects.create(name="Maple Leaf Supply")
    other = Organisation.objects.create(name="Birch Holdings")
    owner = user("dana@maple.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    OrganisationMember.objects.create(organisation=other, user=owner, role="owner")
    actor, browser = _staff("platform_support")
    return {"org": org, "other": other, "owner": owner, "actor": actor, "browser": browser}


def _start(browser: Client, world: dict[str, Any], **body: Any) -> Any:
    payload = {
        "organisation": str(world["org"].public_id),
        "user": str(world["owner"].public_id),
        "reason": "Ticket #42",
        **body,
    }
    return browser.post("/api/v1/platform/impersonation", payload, content_type="application/json")


@pytest.mark.parametrize("minutes", [0, -1, 121, 600])
def test_time_box_is_enforced(world: dict[str, Any], minutes: int) -> None:
    response = _start(world["browser"], world, minutes=minutes)
    assert response.status_code == 400 and response.json()["code"] == "impersonation.bad_duration"
    assert _start(world["browser"], world, minutes=120).status_code == 201
    session = ImpersonationSession.objects.get()
    assert session.expires_at - session.started_at == dt.timedelta(hours=2)


@pytest.mark.parametrize("declaration", PLATFORM, ids=lambda d: f"{d.method} {d.route}")
def test_impersonating_blocks_every_platform_endpoint(
    world: dict[str, Any], declaration: Declaration
) -> None:
    assert _start(world["browser"], world).status_code == 201
    response = _call(world["browser"], declaration)
    if declaration.route in OWN_SESSION:
        assert response.status_code == 200
    else:
        assert response.status_code == 403
        assert response.json()["code"] == "impersonation.blocked"
    assert ImpersonationSession.objects.count() == 1  # never a second session


def test_scoped_to_one_organisation(world: dict[str, Any]) -> None:
    assert _start(world["browser"], world).status_code == 201
    browser = world["browser"]
    assert browser.get(f"/api/v1/o/{world['org'].public_id}/settings").status_code == 200
    assert browser.get(f"/api/v1/o/{world['other'].public_id}/settings").status_code == 404
    header = browser.get("/api/v1/me/flags", HTTP_X_NUMO9_ORG=str(world["other"].public_id))
    assert header.status_code == 404


def test_expires_on_time(world: dict[str, Any]) -> None:
    assert _start(world["browser"], world, minutes=1).status_code == 201
    ImpersonationSession.objects.update(
        started_at=timezone.now() - dt.timedelta(minutes=1, seconds=1),
        expires_at=timezone.now() - dt.timedelta(seconds=1),
    )
    response = world["browser"].get(f"/api/v1/o/{world['org'].public_id}/settings")
    assert response.json()["code"] == "impersonation.expired"
    assert ImpersonationSession.objects.get().end_reason == "expired"


def test_cannot_impersonate_staff_or_self(world: dict[str, Any]) -> None:
    colleague, _ = _staff("platform_owner", email="colleague@numo9.ca")
    OrganisationMember.objects.create(organisation=world["org"], user=colleague, role="admin")
    refused = _start(world["browser"], world, user=str(colleague.public_id))
    assert refused.json()["code"] == "impersonation.platform_user"
    OrganisationMember.objects.create(organisation=world["org"], user=world["actor"], role="admin")
    self_ = _start(world["browser"], world, user=str(world["actor"].public_id))
    assert self_.json()["code"] == "impersonation.not_self"
    stranger = user("x@else.ca")
    assert _start(world["browser"], world, user=str(stranger.public_id)).json()["code"] == (
        "impersonation.not_a_member"
    )


def test_a_copied_session_id_does_nothing_for_another_staff_member(world: dict[str, Any]) -> None:
    assert _start(world["browser"], world).status_code == 201
    session = ImpersonationSession.objects.get()
    _other, thief = _staff("platform_owner", email="other@numo9.ca")
    store = thief.session
    store[SESSION_KEY] = str(session.public_id)
    store.save()
    assert thief.get("/api/v1/platform/impersonation/current").json()["session"] is None
    assert thief.get(f"/api/v1/o/{world['org'].public_id}/settings").status_code in (403, 404)
    assert thief.get("/api/v1/platform/me").status_code == 200  # still themselves
    session.refresh_from_db()
    assert session.ended_at is None  # the real session is untouched


def test_reason_is_required(world: dict[str, Any]) -> None:
    for reason in ("", "   "):
        response = _start(world["browser"], world, reason=reason)
        assert response.json()["code"] == "impersonation.reason_required"
