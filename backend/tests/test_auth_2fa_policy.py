"""A-02-T06 — 2FA enforcement policy flags (platform owner always; practice admin when the
practice enables it).

Acceptance: an enforced role cannot skip enrolment — a platform owner without two-factor
authentication, and a practice admin of a practice requiring it, get ``403
auth.two_factor_required`` on every API call except what enrolling needs (session, password
confirmation, authenticators, CSRF, their own profile); once a TOTP authenticator exists they
pass. Not enforced: a practice admin while the practice doesn't require it, other practice
roles, organisation users. The practice flag: GET for members, PATCH only with
``practice.settings.manage``, audited.
"""

from __future__ import annotations

from typing import Any

import pytest
from allauth.mfa.models import Authenticator
from django.test import Client

from numo9.accounts.models import User
from numo9.accounts.twofactor_policy import two_factor_required
from numo9.audit.models import AuditEvent
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.models import Organisation, OrganisationMember, Practice, PracticeMember
from tests.auth_helpers import API, login, make_user

pytestmark = pytest.mark.django_db

BLOCKED = "/api/v1/practices"  # any business API


def _client(user: User) -> Client:
    browser = Client()
    browser.force_login(user)
    return browser


def _enrol(user: User) -> None:
    Authenticator.objects.create(user=user, type=Authenticator.Type.TOTP, data={"secret": "x"})


@pytest.fixture
def practice() -> Practice:
    return Practice.objects.create(name="North Star CPA")


def _practice_member(practice: Practice, role: str, email: str) -> User:
    user = make_user(email)
    PracticeMember.objects.create(practice=practice, user=user, role=role)
    return user


def test_platform_owner_always(practice: Practice) -> None:
    owner = make_user("owner@numo9.ca")
    role = Role.objects.get(scope=RoleScope.PLATFORM, is_system=True, key="platform_owner")
    RoleAssignment.objects.create(role=role, user=owner)
    assert two_factor_required(owner) == "platform_owner"
    browser = _client(owner)
    refused = browser.get("/api/v1/platform/jobs")
    assert refused.status_code == 403
    assert refused.json()["code"] == "auth.two_factor_required"
    assert refused.json()["reason"] == "platform_owner"
    # What enrolling needs stays reachable.
    assert browser.get(f"{API}/auth/session").status_code == 200
    assert browser.get(f"{API}/account/authenticators").status_code == 200
    assert browser.get("/api/v1/auth/csrf").status_code == 200
    assert browser.get("/api/v1/me/organisations").status_code == 200
    _enrol(owner)
    assert browser.get("/api/v1/platform/jobs").status_code == 200


def test_practice_admin_when_the_practice_requires_it(practice: Practice) -> None:
    admin = _practice_member(practice, "practice_admin", "admin@northstar.ca")
    accountant = _practice_member(practice, "accountant", "acc@northstar.ca")
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    owner = make_user("dana@refined.ca")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    url = f"/api/v1/practice/orgs?practice={practice.public_id}"

    assert two_factor_required(admin) is None
    assert _client(admin).get(url).status_code == 200

    practice.require_2fa_for_admins = True
    practice.save()
    assert two_factor_required(admin) == "practice_admin"
    refused = _client(admin).get(url)
    assert refused.status_code == 403 and refused.json()["reason"] == "practice_admin"
    # Other practice roles and organisation users are not affected.
    assert two_factor_required(accountant) is None
    assert two_factor_required(owner) is None
    assert _client(accountant).get(url).status_code == 200
    _enrol(admin)
    assert _client(admin).get(url).status_code == 200


def test_login_then_blocked_until_enrolled(practice: Practice) -> None:
    practice.require_2fa_for_admins = True
    practice.save()
    _practice_member(practice, "practice_admin", "admin@northstar.ca")
    browser = Client()
    assert login(browser, "admin@northstar.ca").status_code == 200
    assert browser.get(BLOCKED).status_code in (403, 405)
    answer = browser.get(f"/api/v1/practice/orgs?practice={practice.public_id}")
    assert answer.json()["code"] == "auth.two_factor_required"
    setup = browser.get(f"{API}/account/authenticators/totp")
    assert setup.status_code in (401, 404)  # 404 = set-up data; 401 = confirm password first


def test_practice_flag_api(practice: Practice) -> None:
    admin = _practice_member(practice, "practice_admin", "admin@northstar.ca")
    _enrol(admin)  # once the flag is on, the admin must have 2FA to keep using the API
    accountant = _practice_member(practice, "accountant", "acc@northstar.ca")
    url = f"/api/v1/practice/security?practice={practice.public_id}"
    body: dict[str, Any] = {"require_2fa_for_admins": True}

    assert _client(accountant).get(url).json() == {"require_2fa_for_admins": False}
    refused = _client(accountant).patch(url, body, content_type="application/json")
    assert refused.status_code == 403 and refused.json()["code"] == "practice.permission_denied"
    changed = _client(admin).patch(url, body, content_type="application/json")
    assert changed.status_code == 200 and changed.json() == body
    practice.refresh_from_db()
    assert practice.require_2fa_for_admins is True
    event = AuditEvent.objects.unscoped(reason="test").get(
        action="tenancy.practice.security_changed"
    )
    assert event.changes == {"require_2fa_for_admins": [False, True]}
    stranger = make_user("x@elsewhere.ca")
    assert _client(stranger).get(url).status_code == 404
