"""A-01-T03 — tenant request context: active organisation from /o/:org or X-Numo9-Org, acting
practice, held in contextvars and cleared after every request."""

from __future__ import annotations

import threading
import uuid
from typing import Any

import pytest
from django.test import Client, override_settings

from numo9.accounts.models import User
from numo9.tenancy.context import acting_practice, current_org, org_context
from numo9.tenancy.models import (
    Organisation,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("tests.testapp.urls"),
]


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery")


@pytest.fixture
def other_org() -> Organisation:
    return Organisation.objects.create(name="Birch Garage")


def ctx(client: Client, url: str, **headers: str) -> dict[str, Any]:
    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.content
    data: dict[str, Any] = response.json()
    return data


def assign(practice: Practice, org: Organisation, *, active: bool = True) -> PracticeAssignment:
    return PracticeAssignment.objects.create(practice=practice, organisation=org, active=active)


def member(practice: Practice, user: User) -> PracticeMember:
    return PracticeMember.objects.create(practice=practice, user=user, role=PracticeRole.ACCOUNTANT)


# ---- organisation ----------------------------------------------------------------------------


def test_no_organisation_outside_org_urls(client: Client) -> None:
    assert ctx(client, "/ctx/") == {"org": None, "practice": None, "request_org": None}


def test_organisation_from_url(client: Client, org: Organisation) -> None:
    data = ctx(client, f"/o/{org.public_id}/ctx/")
    assert data["org"] == data["request_org"] == str(org.public_id)


def test_organisation_from_api_url(client: Client, org: Organisation) -> None:
    assert ctx(client, f"/api/v1/o/{org.public_id}/ctx/")["org"] == str(org.public_id)


def test_organisation_id_is_case_insensitive(client: Client, org: Organisation) -> None:
    assert ctx(client, f"/o/{str(org.public_id).upper()}/ctx/")["org"] == str(org.public_id)


def test_organisation_from_header(client: Client, org: Organisation) -> None:
    assert ctx(client, "/ctx/", X_Numo9_Org=str(org.public_id))["org"] == str(org.public_id)


def test_url_and_matching_header(client: Client, org: Organisation) -> None:
    data = ctx(client, f"/o/{org.public_id}/ctx/", X_Numo9_Org=str(org.public_id))
    assert data["org"] == str(org.public_id)


def test_url_and_header_disagree_is_rejected(
    client: Client, org: Organisation, other_org: Organisation
) -> None:
    response = client.get(
        f"/o/{org.public_id}/ctx/", headers={"X-Numo9-Org": str(other_org.public_id)}
    )
    assert response.status_code == 400


@pytest.mark.parametrize("bad", ["not-a-uuid", "12345", str(uuid.uuid4())])
def test_malformed_or_unknown_organisation_is_404(client: Client, bad: str) -> None:
    assert client.get(f"/o/{bad}/ctx/").status_code == 404
    assert client.get("/ctx/", headers={"X-Numo9-Org": bad}).status_code == 404


def test_each_request_gets_its_own_organisation(
    client: Client, org: Organisation, other_org: Organisation
) -> None:
    assert ctx(client, f"/o/{org.public_id}/ctx/")["org"] == str(org.public_id)
    assert ctx(client, f"/o/{other_org.public_id}/ctx/")["org"] == str(other_org.public_id)
    assert ctx(client, "/ctx/")["org"] is None


def test_context_cleared_after_request(client: Client, org: Organisation) -> None:
    ctx(client, f"/o/{org.public_id}/ctx/")
    assert current_org() is None and acting_practice() is None


@override_settings(DEBUG_PROPAGATE_EXCEPTIONS=False)
def test_context_cleared_when_view_raises(org: Organisation) -> None:
    client = Client(raise_request_exception=False)
    response = client.get("/boom/", headers={"X-Numo9-Org": str(org.public_id)})
    assert response.status_code == 500
    assert current_org() is None


# ---- acting practice -------------------------------------------------------------------------


def test_practice_derived_from_single_active_assignment(client: Client, org: Organisation) -> None:
    user = User.objects.create_user("acc@example.com", name="Acc")
    practice = Practice.objects.create(name="Profitex")
    member(practice, user)
    assign(practice, org)
    client.force_login(user)
    assert ctx(client, f"/o/{org.public_id}/ctx/")["practice"] == str(practice.public_id)


def test_no_practice_for_inactive_assignment(client: Client, org: Organisation) -> None:
    user = User.objects.create_user("acc@example.com", name="Acc")
    practice = Practice.objects.create(name="Profitex")
    member(practice, user)
    assign(practice, org, active=False)
    client.force_login(user)
    assert ctx(client, f"/o/{org.public_id}/ctx/")["practice"] is None


def test_no_practice_for_anonymous_or_non_member(client: Client, org: Organisation) -> None:
    assign(Practice.objects.create(name="Profitex"), org)
    assert ctx(client, f"/o/{org.public_id}/ctx/")["practice"] is None
    client.force_login(User.objects.create_user("owner@example.com", name="Owner"))
    assert ctx(client, f"/o/{org.public_id}/ctx/")["practice"] is None


def test_two_candidate_practices_need_the_header(client: Client, org: Organisation) -> None:
    user = User.objects.create_user("both@example.com", name="Both")
    bookkeeper = Practice.objects.create(name="Bookkeeper Co")
    tax = Practice.objects.create(name="Tax Co")
    for practice in (bookkeeper, tax):
        member(practice, user)
        assign(practice, org)
    client.force_login(user)
    url = f"/o/{org.public_id}/ctx/"
    assert ctx(client, url)["practice"] is None
    assert ctx(client, url, X_Numo9_Practice=str(tax.public_id))["practice"] == str(tax.public_id)


def test_practice_header_must_be_actively_assigned(client: Client, org: Organisation) -> None:
    unassigned = Practice.objects.create(name="Elsewhere")
    inactive = Practice.objects.create(name="Former")
    assign(inactive, org, active=False)
    url = f"/o/{org.public_id}/ctx/"
    for practice_id in (str(unassigned.public_id), str(inactive.public_id), "junk"):
        assert client.get(url, headers={"X-Numo9-Practice": practice_id}).status_code == 404


def test_practice_header_ignored_without_organisation(client: Client) -> None:
    practice = Practice.objects.create(name="Profitex")
    assert ctx(client, "/ctx/", X_Numo9_Practice=str(practice.public_id))["practice"] is None


# ---- org_context -----------------------------------------------------------------------------


def test_org_context_sets_and_restores_nested(org: Organisation, other_org: Organisation) -> None:
    practice = Practice.objects.create(name="Profitex")
    assert current_org() is None
    with org_context(org, practice):
        assert current_org() == org and acting_practice() == practice
        with org_context(other_org):
            assert current_org() == other_org and acting_practice() is None
        assert current_org() == org and acting_practice() == practice
    assert current_org() is None and acting_practice() is None


def test_org_context_restored_on_exception(org: Organisation) -> None:
    with pytest.raises(RuntimeError), org_context(org):
        raise RuntimeError
    assert current_org() is None


def test_context_is_not_shared_between_threads(org: Organisation) -> None:
    seen: list[Organisation | None] = []
    with org_context(org):
        thread = threading.Thread(target=lambda: seen.append(current_org()))
        thread.start()
        thread.join()
    assert seen == [None]
