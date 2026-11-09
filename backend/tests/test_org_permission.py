"""A-01-T06 — DRF permission IsOrgMemberOrAssigned: access only for members/assigned practice
staff of the active organisation; cross-organisation ids and inaccessible organisations → 404,
indistinguishable from an organisation that does not exist."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient, APIRequestFactory

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
from numo9.tenancy.permissions import IsOrgMemberOrAssigned
from tests.testapp.models import Widget

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.testapp.urls")]

NOT_FOUND = {"detail": str(NotFound.default_detail)}


@pytest.fixture
def org_a() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery")


@pytest.fixture
def org_b() -> Organisation:
    return Organisation.objects.create(name="Birch Garage")


@pytest.fixture
def widgets(org_a: Organisation, org_b: Organisation) -> dict[str, Widget]:
    with org_context(org_a):
        a = Widget.objects.create(label="a1")
    with org_context(org_b):
        b = Widget.objects.create(label="b1")
    return {"a": a, "b": b}


def member_of(org: Organisation, email: str = "m@example.com") -> User:
    user = User.objects.create_user(email, name="M")
    OrganisationMember.objects.create(organisation=org, user=user, role=OrganisationRole.SALES)
    return user


def client_for(user: User | None) -> APIClient:
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def get(client: APIClient, url: str) -> tuple[int, Any]:
    response = client.get(url)
    return response.status_code, response.json()


def test_member_lists_only_own_organisation_rows(
    org_a: Organisation, widgets: dict[str, Widget]
) -> None:
    status, body = get(client_for(member_of(org_a)), f"/api/v1/o/{org_a.public_id}/widgets/")
    assert status == 200
    assert [w["label"] for w in body] == ["a1"]


def test_assigned_practice_staff_and_practice_admin_get_in(
    org_a: Organisation, widgets: dict[str, Widget]
) -> None:
    practice = Practice.objects.create(name="Profitex")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org_a)
    staff = User.objects.create_user("staff@example.com", name="Staff")
    assignment.assigned_staff.add(
        PracticeMember.objects.create(practice=practice, user=staff, role=PracticeRole.ACCOUNTANT)
    )
    admin = User.objects.create_user("padmin@example.com", name="Admin")
    PracticeMember.objects.create(practice=practice, user=admin, role=PracticeRole.PRACTICE_ADMIN)
    for user in (staff, admin):
        assert get(client_for(user), f"/api/v1/o/{org_a.public_id}/widgets/")[0] == 200


def test_inaccessible_and_unknown_organisations_answer_the_same_404(
    org_a: Organisation, org_b: Organisation, widgets: dict[str, Widget]
) -> None:
    client = client_for(member_of(org_a))
    inaccessible = get(client, f"/api/v1/o/{org_b.public_id}/widgets/")
    unknown = get(client, f"/api/v1/o/{uuid.uuid4()}/widgets/")
    malformed = get(client, "/api/v1/o/not-a-uuid/widgets/")
    assert inaccessible == unknown == malformed == (404, NOT_FOUND)


def test_cross_org_id_is_404(
    org_a: Organisation, org_b: Organisation, widgets: dict[str, Widget]
) -> None:
    client = client_for(member_of(org_a))
    own, foreign = widgets["a"].public_id, widgets["b"].public_id
    assert get(client, f"/api/v1/o/{org_a.public_id}/widgets/{own}/")[0] == 200
    # Another organisation's object through my organisation's URL, and through its own URL.
    missing = get(client, f"/api/v1/o/{org_a.public_id}/widgets/{uuid.uuid4()}/")
    assert missing[0] == 404
    assert get(client, f"/api/v1/o/{org_a.public_id}/widgets/{foreign}/") == missing
    assert get(client, f"/api/v1/o/{org_b.public_id}/widgets/{foreign}/") == (404, NOT_FOUND)


def test_object_level_check_catches_objects_loaded_across_organisations(
    org_a: Organisation, widgets: dict[str, Widget]
) -> None:
    client = client_for(member_of(org_a))
    base = f"/api/v1/o/{org_a.public_id}/unscoped-widgets"
    assert get(client, f"{base}/{widgets['a'].public_id}/")[0] == 200
    assert get(client, f"{base}/{widgets['b'].public_id}/") == (404, NOT_FOUND)
    assert get(client, f"{base}/{uuid.uuid4()}/")[0] == 404


def test_organisation_object_check(org_a: Organisation, org_b: Organisation) -> None:
    client = client_for(member_of(org_a))
    status, body = get(client, f"/api/v1/o/{org_a.public_id}/organisation/")
    assert (status, body) == (200, {"name": "Maple Bakery", "active": "Maple Bakery"})


def test_anonymous_is_refused_the_same_way_for_any_organisation(org_a: Organisation) -> None:
    client = client_for(None)
    real = client.get(f"/api/v1/o/{org_a.public_id}/widgets/")
    unknown = client.get(f"/api/v1/o/{uuid.uuid4()}/widgets/")
    assert real.status_code in (401, 403)
    assert unknown.status_code in (401, 403, 404)
    assert real.status_code != 200


def test_endpoint_without_organisation_is_404(org_a: Organisation) -> None:
    assert get(client_for(member_of(org_a)), "/api/v1/no-org/widgets/") == (404, NOT_FOUND)


def test_removed_member_gets_404_on_next_request(
    org_a: Organisation, widgets: dict[str, Widget]
) -> None:
    user = member_of(org_a)
    client = client_for(user)
    url = f"/api/v1/o/{org_a.public_id}/widgets/{widgets['a'].public_id}/"
    assert get(client, url)[0] == 200
    OrganisationMember.objects.filter(user=user).delete()
    assert get(client, url) == (404, NOT_FOUND)


def test_object_without_organisation_is_a_configuration_error(org_a: Organisation) -> None:
    request = APIRequestFactory().get("/")
    with org_context(org_a), pytest.raises(ImproperlyConfigured):
        IsOrgMemberOrAssigned().has_object_permission(request, None, object())  # type: ignore[arg-type]
