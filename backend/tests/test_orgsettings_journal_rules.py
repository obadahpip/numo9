"""C-03-T05 — organisation settings toggles for expense journals:
``journal_expense_requires_attachment`` and ``journal_expense_requires_contact``.

Acceptance: both off by default; changed through the settings API (organisation.settings.manage
only), they persist and every change is audited with its before and after.
"""

from __future__ import annotations

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.orgsettings.models import OrganisationSettings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = pytest.mark.django_db
FIELDS = ("journal_expense_requires_attachment", "journal_expense_requires_contact")


def client(org: Organisation, role: str) -> Client:
    user = User.objects.create_user(f"{role}@refined.ca", password="x" * 12, name=role)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


def test_toggles_default_off_persist_and_are_audited() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    owner = client(org, "owner")
    url = f"/api/v1/o/{org.public_id}/settings"
    body = owner.get(url).json()
    assert [body[name] for name in FIELDS] == [False, False]
    changed = owner.patch(url, dict.fromkeys(FIELDS, True), content_type="application/json")
    assert changed.status_code == 200
    assert [changed.json()[name] for name in FIELDS] == [True, True]
    with org_context(org):
        row = OrganisationSettings.objects.get()
        assert (row.journal_expense_requires_attachment, row.journal_expense_requires_contact) == (
            True,
            True,
        )
        event = AuditEvent.objects.filter(object_type="orgsettings.OrganisationSettings").latest(
            "pk"
        )
    assert event.changes["journal_expense_requires_attachment"] == [False, True]
    assert event.changes["journal_expense_requires_contact"] == [False, True]


def test_only_settings_managers_change_them() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    employee = client(org, "employee")
    response = employee.patch(
        f"/api/v1/o/{org.public_id}/settings",
        {"journal_expense_requires_contact": True},
        content_type="application/json",
    )
    assert response.status_code == 403


def test_journal_approval_threshold_persisted_and_audited() -> None:
    """C-04-T01 — journal_approval_threshold: empty by default (never), set and cleared through
    the settings API, every change audited; negative amounts refused."""
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    owner = client(org, "owner")
    url = f"/api/v1/o/{org.public_id}/settings"
    assert owner.get(url).json()["journal_approval_threshold"] is None
    changed = owner.patch(
        url, {"journal_approval_threshold": "5000.00"}, content_type="application/json"
    )
    assert changed.status_code == 200 and changed.json()["journal_approval_threshold"] == "5000.00"
    with org_context(org):
        event = AuditEvent.objects.filter(object_type="orgsettings.OrganisationSettings").latest(
            "pk"
        )
        assert event.changes["journal_approval_threshold"] == [None, "5000.00"]
    refused = owner.patch(
        url, {"journal_approval_threshold": "-1"}, content_type="application/json"
    )
    assert refused.status_code == 400
    cleared = owner.patch(
        url, {"journal_approval_threshold": None}, content_type="application/json"
    )
    assert cleared.json()["journal_approval_threshold"] is None
