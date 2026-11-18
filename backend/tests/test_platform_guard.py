"""U-06-T02 (API side) — the console's route guard ``GET /api/v1/platform/me``.

Acceptance: a non-platform user gets 404 (no leak) — an organisation owner, a practice admin, a
signed-out visitor (401/403); a platform user without two-factor authentication gets
``403 auth.two_factor_required``; with 2FA the platform permissions come back.
"""

from __future__ import annotations

import pytest
from django.test import Client

from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.auth_helpers import enrol_two_factor
from tests.workspace_helpers import practice, user

pytestmark = pytest.mark.django_db
URL = "/api/v1/platform/me"


def platform_user(email: str, role: str = "platform_owner", two_factor: bool = True) -> Client:
    person = user(email, "Staff")
    RoleAssignment.objects.create(
        user=person, role=Role.objects.get(scope=RoleScope.PLATFORM, key=role)
    )
    if two_factor:
        enrol_two_factor(person)
    browser = Client()
    browser.force_login(person)
    return browser


def test_non_platform_users_get_404() -> None:
    owner = user("owner@refined.ca")
    OrganisationMember.objects.create(
        organisation=Organisation.objects.create(name="Refined"), user=owner, role="owner"
    )
    admin = user("admin@cpa.ca")
    practice("Abuodeh CPA", admin)
    for person in (owner, admin):
        browser = Client()
        browser.force_login(person)
        assert browser.get(URL).status_code == 404
    assert Client().get(URL).status_code in (401, 403)


def test_platform_user_needs_two_factor() -> None:
    response = platform_user("support@numo9.ca", "platform_support", two_factor=False).get(URL)
    assert response.status_code == 403
    assert response.json()["code"] == "auth.two_factor_required"


def test_platform_permissions_come_back() -> None:
    body = platform_user("support@numo9.ca", "platform_support").get(URL).json()
    assert "platform.console.view" in body["permissions"]
    assert "platform.flags.manage" not in body["permissions"]
    owner = platform_user("owner@numo9.ca").get(URL).json()
    assert "platform.flags.manage" in owner["permissions"]
