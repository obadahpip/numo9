"""A-01-T13 — GET /api/v1/me/organisations, POST /api/v1/practices, POST /api/v1/organisations,
and their OpenAPI documentation."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml
from django.core.management import call_command
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.tenancy.access import can_access
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)

pytestmark = pytest.mark.django_db

ME = "/api/v1/me/organisations"
PRACTICES = "/api/v1/practices"
ORGANISATIONS = "/api/v1/organisations"


@pytest.fixture
def user() -> User:
    return User.objects.create_user("acc@example.com", name="Acc")


@pytest.fixture
def client(user: User) -> APIClient:
    api = APIClient()
    api.force_authenticate(user)
    return api


# ---- GET /api/v1/me/organisations ------------------------------------------------------------


def test_me_organisations_requires_authentication() -> None:
    assert APIClient().get(ME).status_code in (401, 403)


def test_me_organisations_empty(client: APIClient) -> None:
    response = client.get(ME)
    assert response.status_code == 200
    assert response.json() == []


def test_me_organisations_lists_memberships_and_assignments(user: User, client: APIClient) -> None:
    own = Organisation.objects.create(name="Birch Garage")
    OrganisationMember.objects.create(organisation=own, user=user, role=OrganisationRole.OWNER)
    practice = Practice.objects.create(name="Profitex")
    member = PracticeMember.objects.create(
        practice=practice, user=user, role=PracticeRole.ACCOUNTANT
    )
    client_org = Organisation.objects.create(name="Alder Bakery")
    PracticeAssignment.objects.create(
        practice=practice, organisation=client_org
    ).assigned_staff.add(member)
    not_staff = Organisation.objects.create(name="Cedar Café")  # assigned, but user not staff
    PracticeAssignment.objects.create(practice=practice, organisation=not_staff)
    inactive = Organisation.objects.create(name="Dogwood Inc.")
    PracticeAssignment.objects.create(
        practice=practice, organisation=inactive, active=False
    ).assigned_staff.add(member)
    Organisation.objects.create(name="Elm Unrelated")

    body: list[dict[str, Any]] = client.get(ME).json()
    assert [o["name"] for o in body] == ["Alder Bakery", "Birch Garage"]
    alder, birch = body
    assert alder == {
        "id": str(client_org.public_id),
        "name": "Alder Bakery",
        "status": "trial",
        "time_zone": "America/Toronto",
        "locale": "en-ca",
        "membership": None,
        "via_practices": [
            {
                "practice_id": str(practice.public_id),
                "practice_name": "Profitex",
                "practice_role": "accountant",
                "assignment_role": "full_service",
                "assigned_staff": True,
            }
        ],
    }
    assert birch["membership"] == {"role": "owner"} and birch["via_practices"] == []


def test_me_organisations_practice_admin_sees_all_assigned(user: User, client: APIClient) -> None:
    practice = Practice.objects.create(name="Profitex")
    PracticeMember.objects.create(practice=practice, user=user, role=PracticeRole.PRACTICE_ADMIN)
    org = Organisation.objects.create(name="Client")
    PracticeAssignment.objects.create(practice=practice, organisation=org)
    [entry] = client.get(ME).json()
    assert entry["via_practices"][0]["practice_role"] == "practice_admin"
    assert entry["via_practices"][0]["assigned_staff"] is False


# ---- POST /api/v1/practices ------------------------------------------------------------------


def test_create_practice_makes_the_creator_practice_admin(user: User, client: APIClient) -> None:
    response = client.post(PRACTICES, {"name": "  Profitex Accounting  "}, format="json")
    assert response.status_code == 201
    body = response.json()
    practice = Practice.objects.get(public_id=body["id"])
    assert body == {
        "id": str(practice.public_id),
        "name": "Profitex Accounting",
        "role": "practice_admin",
    }
    assert PracticeMember.objects.get(practice=practice, user=user).role == "practice_admin"


@pytest.mark.parametrize("payload", [{}, {"name": ""}, {"name": "   "}, {"name": "x" * 201}])
def test_create_practice_validates_name(client: APIClient, payload: dict[str, str]) -> None:
    response = client.post(PRACTICES, payload, format="json")
    assert response.status_code == 400
    assert "name" in response.json()
    assert Practice.objects.count() == 0


def test_create_practice_requires_authentication() -> None:
    assert APIClient().post(PRACTICES, {"name": "X"}, format="json").status_code in (401, 403)
    assert Practice.objects.count() == 0


# ---- POST /api/v1/organisations --------------------------------------------------------------


def test_create_organisation_without_practice_makes_the_creator_owner(
    user: User, client: APIClient
) -> None:
    response = client.post(ORGANISATIONS, {"name": "Maple Bakery"}, format="json")
    assert response.status_code == 201
    body = response.json()
    org = Organisation.objects.get(public_id=body["id"])
    assert (org.status, org.time_zone) == ("trial", "America/Toronto")
    assert OrganisationMember.objects.get(organisation=org, user=user).role == "owner"
    assert body["membership"] == {"role": "owner"}
    assert can_access(user, org)


def test_create_organisation_with_time_zone(client: APIClient) -> None:
    response = client.post(
        ORGANISATIONS, {"name": "Pacific Co", "time_zone": "America/Vancouver"}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["time_zone"] == "America/Vancouver"


def test_create_organisation_rejects_invalid_time_zone(client: APIClient) -> None:
    response = client.post(ORGANISATIONS, {"name": "X", "time_zone": "Mars/Base"}, format="json")
    assert response.status_code == 400
    assert "time_zone" in response.json()
    assert Organisation.objects.count() == 0


def test_create_organisation_for_a_practice_client(user: User, client: APIClient) -> None:
    practice = Practice.objects.create(name="Profitex")
    member = PracticeMember.objects.create(
        practice=practice, user=user, role=PracticeRole.ACCOUNTANT
    )
    response = client.post(
        ORGANISATIONS, {"name": "Client Co", "practice": str(practice.public_id)}, format="json"
    )
    assert response.status_code == 201
    org = Organisation.objects.get(public_id=response.json()["id"])
    assignment = PracticeAssignment.objects.get(practice=practice, organisation=org)
    assert assignment.active and list(assignment.assigned_staff.all()) == [member]
    assert not OrganisationMember.objects.filter(organisation=org).exists()  # owner invited later
    assert response.json()["via_practices"][0]["assigned_staff"] is True
    assert can_access(user, org)


@pytest.mark.parametrize("known", [True, False])
def test_create_organisation_for_a_practice_the_user_does_not_belong_to(
    client: APIClient, known: bool
) -> None:
    practice_id = Practice.objects.create(name="Other firm").public_id if known else uuid.uuid4()
    response = client.post(
        ORGANISATIONS, {"name": "X", "practice": str(practice_id)}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {
        "practice": [
            "This practice doesn't exist or you're not a member. Choose one of your practices."
        ]
    }  # same for both cases
    assert Organisation.objects.count() == 0


def test_create_organisation_requires_a_name(client: APIClient) -> None:
    assert client.post(ORGANISATIONS, {"name": " "}, format="json").status_code == 400


# ---- OpenAPI ---------------------------------------------------------------------------------


def test_endpoints_are_documented_in_openapi(tmp_path: Path) -> None:
    out = tmp_path / "schema.yaml"
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(out))
    schema = yaml.safe_load(out.read_text(encoding="utf-8"))
    paths = schema["paths"]
    assert set(paths["/api/v1/me/organisations"]) == {"get"}
    assert set(paths["/api/v1/practices"]) == {"post"}
    assert set(paths["/api/v1/organisations"]) == {"post"}
    assert "201" in paths["/api/v1/organisations"]["post"]["responses"]
    components = schema["components"]["schemas"]
    assert {"MyOrganisation", "PracticeCreateRequest", "OrganisationCreateRequest"} <= set(
        components
    )
    assert components["OrganisationStatusEnum"]["enum"] == [
        "demo",
        "trial",
        "active",
        "grace",
        "read_only",
        "cancelled",
    ]


def test_schema_served_to_signed_in_users_only(client: APIClient) -> None:
    assert APIClient().get("/api/schema/").status_code in (401, 403)
    response = client.get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert response.status_code == 200
    assert "/api/v1/me/organisations" in response.json()["paths"]
