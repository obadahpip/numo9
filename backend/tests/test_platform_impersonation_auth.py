"""U-06-T09 — impersonation auth backend: time-box and blocked endpoints.

Acceptance: an expired session auto-ends (the next request is refused with
``impersonation.expired`` and the row is closed); blocked endpoints answer 403 while impersonating
(billing portal/checkout/change/cancel, password, 2FA, email, the console); requests are scoped to
the session's organisation; only ``platform.impersonate`` may start one.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from numo9.platform.models import ImpersonationSession
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.auth_helpers import enrol_two_factor
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db
START = "/api/v1/platform/impersonation"


def staff(role: str = "platform_support") -> tuple[Any, Client]:
    person = user(f"{role}@numo9.ca", name="Sam Support")
    RoleAssignment.objects.create(
        user=person, role=Role.objects.get(scope=RoleScope.PLATFORM, key=role)
    )
    enrol_two_factor(person)
    browser = Client()
    browser.force_login(person)
    return person, browser


@pytest.fixture
def world() -> dict[str, Any]:
    org = Organisation.objects.create(name="Maple Leaf Supply")
    other = Organisation.objects.create(name="Birch Holdings")
    owner = user("dana@maple.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    OrganisationMember.objects.create(organisation=other, user=owner, role="owner")
    actor, browser = staff()
    return {"org": org, "other": other, "owner": owner, "actor": actor, "browser": browser}


def start(world: dict[str, Any], **body: Any) -> Any:
    payload = {
        "organisation": str(world["org"].public_id),
        "user": str(world["owner"].public_id),
        "reason": "Ticket #42",
        **body,
    }
    return world["browser"].post(START, payload, content_type="application/json")


def me_orgs(browser: Client) -> list[str]:
    return [row["name"] for row in browser.get("/api/v1/me/organisations").json()]


def test_start_acts_as_the_user_in_that_organisation(world: dict[str, Any]) -> None:
    response = start(world)
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["user"]["email"] == "dana@maple.ca" and body["organisation"]["name"] == (
        "Maple Leaf Supply"
    )
    browser = world["browser"]
    assert "Maple Leaf Supply" in me_orgs(browser)  # Dana's organisations: acting as Dana
    assert browser.get(f"/api/v1/o/{world['org'].public_id}/settings").status_code == 200
    # scoped to one organisation: Dana's other organisation is unknown here
    assert browser.get(f"/api/v1/o/{world['other'].public_id}/settings").status_code == 404
    current = browser.get(f"{START}/current").json()
    assert current["session"]["id"] == body["id"] and current["ended"] is None
    ended = browser.post(f"{START}/end").json()
    assert ended["session"] is None and ended["ended"]["end_reason"] == "ended"
    assert me_orgs(browser) == []  # the staff member again
    assert ImpersonationSession.objects.get().end_reason == "ended"


def test_expired_session_auto_ends(world: dict[str, Any]) -> None:
    assert start(world, minutes=10).status_code == 201
    ImpersonationSession.objects.update(
        started_at=timezone.now() - dt.timedelta(minutes=11),
        expires_at=timezone.now() - dt.timedelta(minutes=1),
    )
    browser = world["browser"]
    response = browser.get(f"/api/v1/o/{world['org'].public_id}/settings")
    assert response.status_code == 403
    assert response.json()["code"] == "impersonation.expired"
    row = ImpersonationSession.objects.get()
    assert row.end_reason == "expired" and row.ended_at == row.expires_at
    assert browser.get(f"{START}/current").json()["session"] is None
    assert me_orgs(browser) == []  # back to the staff member


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/o/{org}/billing/portal"),
        ("post", "/api/v1/o/{org}/billing/checkout"),
        ("post", "/api/v1/o/{org}/billing/change"),
        ("post", "/api/v1/o/{org}/billing/change/preview"),
        ("post", "/api/v1/o/{org}/billing/cancel"),
        ("post", "/api/v1/o/{org}/reveal"),
        ("post", "/_allauth/browser/v1/account/password/change"),
        ("get", "/_allauth/browser/v1/account/authenticators"),
        ("post", "/_allauth/browser/v1/account/authenticators/totp"),
        ("get", "/_allauth/browser/v1/account/email"),
        ("post", "/_allauth/browser/v1/auth/password/request"),
        ("get", "/_allauth/browser/v1/auth/sessions"),
        ("get", "/api/v1/platform/me"),
        ("get", "/api/v1/platform/organisations"),
        ("post", "/api/v1/platform/impersonation"),
        ("get", "/api/v1/practice/orgs"),
        ("post", "/api/v1/organisations"),
        ("get", "/admin/"),
    ],
)
def test_blocked_endpoints_answer_403(world: dict[str, Any], method: str, path: str) -> None:
    assert start(world).status_code == 201
    url = path.format(org=world["org"].public_id)
    response = getattr(world["browser"], method)(url, {}, content_type="application/json")
    assert response.status_code == 403, (url, response.status_code)
    assert response.json()["code"] == "impersonation.blocked"


def test_the_same_endpoints_work_without_impersonation(world: dict[str, Any]) -> None:
    assert world["browser"].get("/api/v1/platform/me").status_code == 200


def test_only_platform_impersonate_may_start(world: dict[str, Any]) -> None:
    _person, viewer = staff("platform_owner")
    owner_ok = viewer.post(
        START,
        {
            "organisation": str(world["org"].public_id),
            "user": str(world["owner"].public_id),
            "reason": "why",
        },
        content_type="application/json",
    )
    assert owner_ok.status_code == 201
    stranger = Client()
    stranger.force_login(world["owner"])
    refused = stranger.post(
        START,
        {
            "organisation": str(world["org"].public_id),
            "user": str(world["owner"].public_id),
            "reason": "why",
        },
        content_type="application/json",
    )
    assert refused.status_code in (403, 404)


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"reason": " "}, 400, "impersonation.reason_required"),
        ({"minutes": 121}, 400, "impersonation.bad_duration"),
        ({"organisation": "00000000-0000-4000-8000-000000000000"}, 404, "not_found"),
    ],
)
def test_refusals(world: dict[str, Any], body: dict[str, Any], status: int, code: str) -> None:
    response = start(world, **body)
    assert response.status_code == status
    assert response.json()["code"] == code


def test_signing_out_ends_the_session(world: dict[str, Any]) -> None:
    assert start(world).status_code == 201
    world["browser"].logout()
    assert ImpersonationSession.objects.get().end_reason == "ended"


def test_losing_the_permission_revokes(world: dict[str, Any]) -> None:
    assert start(world).status_code == 201
    RoleAssignment.objects.filter(user=world["actor"]).delete()
    world["browser"].get("/api/v1/me/organisations")
    assert ImpersonationSession.objects.get().end_reason == "revoked"
