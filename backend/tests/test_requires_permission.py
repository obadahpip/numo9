"""RequiresPermission and the declaration system check (A-03-T05).

Acceptance: an endpoint without a declaration fails the system check.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client, override_settings

from numo9.accounts.models import User
from numo9.rbac.checks import check_permission_declarations
from numo9.rbac.drf import AUTHENTICATED, PUBLIC, declared_permission
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.testapp import rbac_api

URLS = "tests.testapp.rbac_urls"


# ---- system check -----------------------------------------------------------------------------


def test_project_endpoints_all_declare_a_permission() -> None:
    assert check_permission_declarations() == []
    call_command("check")  # raises SystemCheckError on any error


def test_check_reports_every_kind_of_mistake() -> None:
    messages = check_permission_declarations(urlconf="tests.testapp.rbac_urls_bad")
    found = {(m.id, m.obj) for m in messages}
    assert ("rbac.E001", rbac_api.Undeclared) in found
    assert ("rbac.E002", rbac_api.UnknownKey) in found
    assert ("rbac.E003", rbac_api.NotEnforced) in found
    assert any(m.id == "rbac.E004" and "SpectacularJSONAPIView" in m.msg for m in messages)
    e001 = next(m for m in messages if m.id == "rbac.E001")
    assert "DELETE on tests.testapp.rbac_api.Undeclared" in e001.msg
    # The declared methods of the same view are fine; nothing else is reported.
    assert len(messages) == 4, [m.msg for m in messages]


def test_exempt_third_party_views_need_a_reason(settings: Any) -> None:
    settings.RBAC_EXEMPT_VIEWS = {
        **settings.RBAC_EXEMPT_VIEWS,
        "drf_spectacular.views.SpectacularJSONAPIView": "test: schema",
    }
    ids = {m.id for m in check_permission_declarations(urlconf="tests.testapp.rbac_urls_bad")}
    assert "rbac.E004" not in ids


def test_declaration_lookup() -> None:
    assert declared_permission(rbac_api.OrgSettings, "get") == "organisation.profile.view"
    assert declared_permission(rbac_api.OrgSettings, "HEAD") == "organisation.profile.view"
    assert declared_permission(rbac_api.OrgSettings, "POST") == "organisation.settings.manage"
    assert declared_permission(rbac_api.OrgSettings, "DELETE") is None
    assert declared_permission(rbac_api.ByClass, "GET") == PUBLIC
    assert declared_permission(rbac_api.ByClass, "POST") == AUTHENTICATED
    assert declared_permission(rbac_api.ByClass, "PUT") is None


# ---- enforcement ------------------------------------------------------------------------------


def user(email: str) -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=email.split("@")[0])


def signed_in(account: User) -> Client:
    client = Client()
    client.force_login(account)
    return client


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


def member(org: Organisation, role: str) -> User:
    account = user(f"{role}@maple.ca")
    OrganisationMember.objects.create(organisation=org, user=account, role=role)
    return account


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=URLS)
def test_organisation_permission_per_method(org: Organisation) -> None:
    url = f"/api/v1/o/{org.public_id}/settings/"
    owner = signed_in(member(org, "owner"))
    assert owner.get(url).status_code == 200
    assert owner.head(url).status_code == 200
    assert owner.post(url).json() == {"ok": "changed"}

    sales = signed_in(member(org, "sales"))
    assert sales.get(url).status_code == 200
    refused = sales.post(url)
    assert refused.status_code == 403
    assert refused.json()["code"] == "permission.denied"
    assert "change organisation settings" in refused.json()["detail"]


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=URLS)
def test_outsiders_get_404_and_anonymous_401_or_403(org: Organisation) -> None:
    url = f"/api/v1/o/{org.public_id}/settings/"
    other = Organisation.objects.create(name="Northern Lights Bakery Inc.")
    outsider = user("owner@bakery.ca")
    OrganisationMember.objects.create(organisation=other, user=outsider, role="owner")
    assert signed_in(outsider).get(url).status_code == 404
    assert signed_in(outsider).post(url).status_code == 404
    assert Client().get(url).status_code in {401, 403}


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=URLS)
def test_custom_role_grants_the_permission(org: Organisation) -> None:
    url = f"/api/v1/o/{org.public_id}/settings/"
    account = member(org, "employee")
    client = signed_in(account)
    assert client.post(url).status_code == 403
    role = Role.objects.create(scope=RoleScope.ORGANISATION, name="Settings", organisation=org)
    role.grants.create(permission="organisation.settings.manage")
    RoleAssignment.objects.create(role=role, user=account, organisation=org)
    assert client.post(url).status_code == 200  # next request: no stale cache


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=URLS)
def test_public_and_authenticated_sentinels() -> None:
    assert Client().get("/api/v1/by-class/").json() == {"ok": "public"}
    assert Client().post("/api/v1/by-class/").status_code in {401, 403}
    assert signed_in(user("dana@maple.ca")).post("/api/v1/by-class/").status_code == 200
    # A method without a declaration is refused even for signed-in users.
    assert signed_in(user("sam@maple.ca")).put("/api/v1/by-class/").status_code in {403, 405}


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=URLS)
def test_undeclared_method_is_refused_at_runtime(org: Organisation) -> None:
    owner = signed_in(member(org, "owner"))
    response = owner.delete("/api/v1/undeclared/", HTTP_X_NUMO9_ORG=str(org.public_id))
    assert response.status_code == 403
    assert "deleted" not in response.json()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=URLS)
def test_platform_permission() -> None:
    account = user("support@numo9.ca")
    client = signed_in(account)
    assert client.get("/api/v1/console/").status_code == 403
    support = Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key="platform_support")
    RoleAssignment.objects.create(role=support, user=account)
    assert client.get("/api/v1/console/").status_code == 200


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=URLS)
def test_practice_permission_without_a_practice_is_404() -> None:
    assert signed_in(user("pa@profitex.ca")).get("/api/v1/practice-staff/").status_code == 404


@pytest.mark.django_db
def test_existing_endpoints_keep_their_access_rules() -> None:
    assert Client().get("/api/v1/auth/csrf").status_code == 200  # PUBLIC
    assert Client().get("/api/v1/me/organisations").status_code in {401, 403}  # AUTHENTICATED
    account = user("dana@maple.ca")
    assert signed_in(account).get("/api/v1/me/organisations").status_code == 200
    preview = Client().post(
        "/api/v1/invitations/preview", {"token": "x" * 43}, content_type="application/json"
    )
    assert preview.status_code == 404  # PUBLIC: reaches the service, which says "invalid"
