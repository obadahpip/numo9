""" "Why can't I?" payload and request access (A-03-T14). Acceptance: the refusal shows names.

Covers: the explain payload of every 403 permission.denied (permission, holders with the roles
that give it, managers = can give roles and hold it, can_request, caps, the refused user left
out, no emails), request access (emails the managers in their language, one open request,
nobody to ask, already have it, unknown/non-organisation keys), listing and closing requests.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core import mail
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.rbac.explain import MAX_PEOPLE
from numo9.rbac.models import AccessRequest, Role, RoleAssignment, RoleScope
from numo9.tenancy.models import (
    AssignmentRole,
    Organisation,
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)

pytestmark = pytest.mark.django_db


def make_user(email: str, name: str, locale: str = "en-ca") -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=name, locale=locale)


def member(org: Organisation, role: str, email: str, name: str, **kw: Any) -> User:
    user = make_user(email, name, **kw)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def team(org: Organisation) -> dict[str, User]:
    return {
        "owner": member(org, "owner", "avery@refined.ca", "Avery Owner"),
        "admin": member(org, "admin", "dana@refined.ca", "Dana Admin", locale="fr-ca"),
        "delegate": member(org, "accountant_delegate", "bo@refined.ca", "Bo Books"),
        "sales": member(org, "sales", "sam@refined.ca", "Sam Patel"),
    }


def url(org: Organisation, path: str) -> str:
    return f"/api/v1/o/{org.public_id}/{path}"


def test_refusal_names_who_has_it_and_who_can_give_it(
    org: Organisation, team: dict[str, User]
) -> None:
    refused = client_for(team["sales"]).get(url(org, "roles"))
    assert refused.status_code == 403
    body = refused.json()
    assert body["code"] == "permission.denied"
    explain = body["explain"]
    assert explain["rule"] == "permission"
    assert explain["permission"] == {
        "key": "roles.role.view",
        "label": "View roles and what they allow",
        "module": "users",
        "module_label": "Users and roles",
        "risk": "low",
        "risk_label": "Low risk",
    }
    assert [h["name"] for h in explain["holders"]] == ["Avery Owner", "Bo Books", "Dana Admin"]
    assert explain["holders"][0]["roles"] == ["Owner"]
    assert explain["holders_total"] == 3
    # Managers: may give roles and hold the permission (the accountant delegate can't give roles).
    assert [m["name"] for m in explain["managers"]] == ["Avery Owner", "Dana Admin"]
    assert explain["can_request"] is True
    assert "email" not in str(explain) and "@" not in str(explain)


def test_custom_role_and_practice_staff_appear_as_holders(
    org: Organisation, team: dict[str, User]
) -> None:
    lee = member(org, "employee", "lee@refined.ca", "Lee Buyer")
    buyer = Role.objects.create(scope=RoleScope.ORGANISATION, name="Buyer", organisation=org)
    buyer.grants.create(permission="organisation.settings.manage")
    RoleAssignment.objects.create(role=buyer, user=lee, organisation=org)
    firm = Practice.objects.create(name="Profitex")
    assignment = PracticeAssignment.objects.create(
        practice=firm, organisation=org, role=AssignmentRole.FULL_SERVICE
    )
    ali = make_user("ali@profitex.ca", "Ali Accountant")
    assignment.assigned_staff.add(
        PracticeMember.objects.create(practice=firm, user=ali, role="accountant")
    )
    explain = client_for(team["sales"]).post(url(org, "roles"), {"name": "x"}).json()["explain"]
    assert explain["permission"]["key"] == "roles.role.manage"
    settings_refusal = (
        client_for(team["sales"])
        .post(f"/api/v1/o/{org.public_id}/roles", {"name": "y"}, format="json")
        .json()
    )
    assert settings_refusal["code"] == "permission.denied"
    # organisation.settings.manage: owner, admin, delegate, the Buyer and the practice accountant.
    from numo9.rbac.explain import explain as build

    payload = build(team["sales"], "organisation.settings.manage", org)
    by_name = {h["name"]: h["roles"] for h in payload["holders"]}
    assert by_name["Lee Buyer"] == ["Buyer"]
    assert by_name["Ali Accountant"] == ["Accountant"]
    assert payload["holders_total"] == 5


def test_lists_are_capped_and_the_refused_user_is_left_out(org: Organisation) -> None:
    for n in range(MAX_PEOPLE + 2):
        member(org, "owner", f"o{n}@refined.ca", f"Owner {n}")
    sales = member(org, "sales", "sam@refined.ca", "Sam Patel")
    explain = client_for(sales).get(url(org, "roles")).json()["explain"]
    assert len(explain["holders"]) == MAX_PEOPLE
    assert explain["holders_total"] == MAX_PEOPLE + 2
    assert "Sam Patel" not in [h["name"] for h in explain["holders"]]


def test_nobody_to_ask(org: Organisation) -> None:
    sales = member(org, "sales", "sam@refined.ca", "Sam Patel")
    explain = client_for(sales).get(url(org, "roles")).json()["explain"]
    assert explain["holders"] == [] and explain["managers"] == []
    assert explain["can_request"] is False
    answer = client_for(sales).post(
        url(org, "access-requests"), {"permission": "roles.role.view"}, format="json"
    )
    assert answer.status_code == 409 and answer.json()["code"] == "access.nobody"
    assert not AccessRequest._base_manager.exists()


def test_request_access_emails_the_managers_in_their_language(
    org: Organisation, team: dict[str, User]
) -> None:
    sam = client_for(team["sales"])
    answer = sam.post(
        url(org, "access-requests"),
        {"permission": "roles.role.view", "note": "To check the Sales role"},
        format="json",
    )
    assert answer.status_code == 201, answer.json()
    body = answer.json()
    assert body["requester"]["name"] == "Sam Patel"
    assert body["permission"]["label"] == "View roles and what they allow"
    assert body["notified"] == 2 and body["already_open"] is False
    sent = {m.to[0]: m for m in mail.outbox}
    assert set(sent) == {"avery@refined.ca", "dana@refined.ca"}
    english = sent["avery@refined.ca"]
    assert english.subject == "Sam Patel asks for access in Refined Interiors Inc."
    assert "View roles and what they allow" in english.body
    assert "Their note: To check the Sales role" in english.body
    assert f"/o/{org.public_id}/settings/users-roles" in english.body
    french = sent["dana@refined.ca"]
    assert french.subject == "Sam Patel demande un accès dans Refined Interiors Inc."
    # Asking again: the open request, nobody emailed again.
    again = sam.post(url(org, "access-requests"), {"permission": "roles.role.view"}, format="json")
    assert again.status_code == 200 and again.json()["already_open"] is True
    assert len(mail.outbox) == 2
    assert AccessRequest._base_manager.count() == 1


def test_request_access_refusals(org: Organisation, team: dict[str, User]) -> None:
    sam = client_for(team["sales"])
    have = sam.post(
        url(org, "access-requests"), {"permission": "organisation.profile.view"}, format="json"
    )
    assert have.status_code == 409 and have.json()["code"] == "access.already_have"
    for key in ("organisation.nope", "practice.staff.view", "platform.console.view"):
        bad = sam.post(url(org, "access-requests"), {"permission": key}, format="json")
        assert bad.status_code == 400 and "permission" in bad.json()
    outsider = member(Organisation.objects.create(name="Elsewhere"), "owner", "x@e.ca", "X")
    assert (
        client_for(outsider)
        .post(url(org, "access-requests"), {"permission": "roles.role.view"}, format="json")
        .status_code
        == 404
    )


def test_managers_list_and_close_requests(org: Organisation, team: dict[str, User]) -> None:
    client_for(team["sales"]).post(
        url(org, "access-requests"), {"permission": "roles.role.view"}, format="json"
    )
    owner = client_for(team["owner"])
    rows = owner.get(url(org, "access-requests")).json()
    assert [(r["requester"]["name"], r["permission"]["key"]) for r in rows] == [
        ("Sam Patel", "roles.role.view")
    ]
    assert client_for(team["sales"]).get(url(org, "access-requests")).status_code == 403
    assert owner.delete(url(org, f"access-requests/{rows[0]['id']}")).status_code == 204
    assert owner.get(url(org, "access-requests")).json() == []
    assert owner.delete(url(org, f"access-requests/{rows[0]['id']}")).status_code == 404
    # Closed: asking again opens a new request.
    again = client_for(team["sales"]).post(
        url(org, "access-requests"), {"permission": "roles.role.view"}, format="json"
    )
    assert again.status_code == 201


def test_french_refusal(org: Organisation, team: dict[str, User]) -> None:
    body = client_for(team["sales"]).get(url(org, "roles"), HTTP_ACCEPT_LANGUAGE="fr-ca").json()
    assert body["explain"]["permission"]["module_label"] == "Utilisateurs et rôles"
    assert body["explain"]["permission"]["risk_label"] == "Risque faible"


@pytest.mark.tenant_isolation
def test_requests_of_another_organisation_are_invisible(
    org: Organisation, team: dict[str, User]
) -> None:
    other = Organisation.objects.create(name="Elsewhere Ltd.")
    them = member(other, "owner", "x@elsewhere.ca", "Them")
    member(other, "sales", "y@elsewhere.ca", "Y")
    foreign = AccessRequest._base_manager.create(
        organisation=other, requester=them, permission="roles.role.view"
    )
    owner = client_for(team["owner"])
    assert owner.get(url(org, "access-requests")).json() == []
    assert owner.delete(url(org, f"access-requests/{foreign.public_id}")).status_code == 404
    foreign.refresh_from_db()
    assert foreign.deleted_at is None
