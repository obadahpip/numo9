"""S-03-T05 — MaskedValue serializer + "reveal" endpoint with permission, re-authentication and
an audit hook.

Acceptance: reveal without the permission → 403; a reveal is audited (event
``security.value.revealed`` names the record and the field, never the value). Also: the masked
form (``•••• 6286``, short values fully hidden, empty values), the reveal reference only for
registered fields with a value; without a fresh password confirmation → 401
``security.reauthentication_required``; after ``auth/reauthenticate`` → the value; unregistered
field or another organisation's record → 404; the value never appears in the audit log.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from rest_framework import serializers

from numo9.audit.models import AuditEvent
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.security.masking import MaskedValueField, mask, register_revealable
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.auth_helpers import API, PASSWORD, login, make_user
from tests.testapp.models import Payee

pytestmark = pytest.mark.django_db

register_revealable("testapp.Payee", "sin")


class PayeeSerializer(serializers.ModelSerializer[Payee]):
    sin = MaskedValueField()
    bank_account = MaskedValueField()

    class Meta:
        model = Payee
        fields = ("name", "sin", "bank_account")


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def payee(org: Organisation) -> Payee:
    with org_context(org):
        row: Payee = Payee.objects.create(
            organisation=org, name="Sam", sin="046454286", bank_account=""
        )
        return row


def _member(org: Organisation, role: str, email: str) -> Client:
    user = make_user(email)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    assert login(browser, email).status_code == 200
    return browser


def _reveal(browser: Client, org: Organisation, payee: Payee, field: str = "sin") -> Any:
    return browser.post(
        f"/api/v1/o/{org.public_id}/reveal",
        {"record_type": "testapp.Payee", "record_id": str(payee.public_id), "field": field},
        content_type="application/json",
    )


def _reauthenticate(browser: Client) -> None:
    answer = browser.post(
        f"{API}/auth/reauthenticate",
        json.dumps({"password": PASSWORD}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content


def test_masked_representation(payee: Payee) -> None:
    assert mask("046454286") == "•••• 4286"
    assert mask("12 3456 7890") == "•••• 7890"
    assert mask("1234") == "••••" and mask("") == "" and mask(None) == ""
    data = PayeeSerializer(payee).data
    assert data["sin"] == {
        "masked": "•••• 4286",
        "has_value": True,
        "reveal": {
            "record_type": "testapp.Payee",
            "record_id": str(payee.public_id),
            "field": "sin",
        },
    }
    assert data["bank_account"] == {"masked": "", "has_value": False, "reveal": None}
    assert "046454286" not in json.dumps(data)


def test_without_permission_403(org: Organisation, payee: Payee) -> None:
    employee = _member(org, "employee", "emp@refined.ca")
    _reauthenticate(employee)
    answer = _reveal(employee, org, payee)
    assert answer.status_code == 403
    with org_context(org):
        assert not AuditEvent.objects.filter(action="security.value.revealed").exists()


def test_reveal_needs_a_fresh_password_and_is_audited(org: Organisation, payee: Payee) -> None:
    owner = _member(org, "owner", "dana@refined.ca")
    first = _reveal(owner, org, payee)
    assert first.status_code == 401
    assert first.json()["code"] == "security.reauthentication_required"

    _reauthenticate(owner)
    answer = _reveal(owner, org, payee)
    assert answer.status_code == 200 and answer.json() == {"value": "046454286"}

    with org_context(org):
        [event] = AuditEvent.objects.filter(action="security.value.revealed")
    assert event.object_type == "testapp.Payee" and event.object_id == str(payee.public_id)
    assert event.meta == {"field": "sin"} and event.actor_user.email == "dana@refined.ca"
    assert "046454286" not in json.dumps(
        {"changes": event.changes, "meta": event.meta, "label": event.object_label}
    )


def test_unregistered_field_and_other_organisation_404(org: Organisation, payee: Payee) -> None:
    owner = _member(org, "owner", "dana@refined.ca")
    _reauthenticate(owner)
    assert _reveal(owner, org, payee, field="bank_account").status_code == 404
    other = Organisation.objects.create(name="Maple Leaf Bakery")
    OrganisationMember.objects.create(
        organisation=other, user=OrganisationMember.objects.get(organisation=org).user, role="owner"
    )
    assert _reveal(owner, other, payee).status_code == 404


def test_custom_role_with_the_permission(org: Organisation, payee: Payee) -> None:
    browser = _member(org, "employee", "pay@refined.ca")
    role = Role.objects.create(
        scope=RoleScope.ORGANISATION, name="Payroll reveal", organisation=org
    )
    role.grants.create(permission="security.sensitive.reveal")
    RoleAssignment.objects.create(
        role=role,
        user=OrganisationMember.objects.get(user__email="pay@refined.ca").user,
        organisation=org,
    )
    _reauthenticate(browser)
    assert _reveal(browser, org, payee).status_code == 200
