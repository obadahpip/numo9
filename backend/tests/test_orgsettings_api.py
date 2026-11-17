"""A-05-T09 — API endpoints for settings, registrations, locks and numbering.

Acceptance: OpenAPI documented — every endpoint and method is in the schema with its request and
response. Also, per endpoint: read for every member, change only with
``organisation.settings.manage``; model rules come back as 400 with field and code (numeric-only
legal name, invalid BN, lock moved back without a reason, levels out of order, numbering below
the last number); changes are saved and audited; another organisation's registration is a 404;
base currency read-only.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from django.test import Client

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def _client(org: Organisation, role: str) -> Client:
    email = f"{role}-{org.public_id.hex[:6]}@refined.ca"
    user = User.objects.create_user(email, password="x" * 12, name=role)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


def url(org: Organisation, suffix: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/settings{suffix}"


def patch(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.patch(path, body, content_type="application/json")


def test_openapi_documents_every_settings_endpoint(org: Organisation) -> None:
    schema = yaml.safe_load(_client(org, "owner").get("/api/schema/").content)
    paths = schema["paths"]
    expected = {
        "/api/v1/o/{org}/settings": {"get", "patch"},
        "/api/v1/o/{org}/settings/registrations": {"get", "post"},
        "/api/v1/o/{org}/settings/registrations/{public_id}": {"get", "patch", "delete"},
        "/api/v1/o/{org}/settings/lock-dates": {"get", "patch"},
        "/api/v1/o/{org}/settings/lock-dates/impact": {"get"},
        "/api/v1/o/{org}/settings/numbering": {"get", "patch"},
    }
    for path, methods in expected.items():
        assert path in paths, path
        assert methods <= set(paths[path]), (path, set(paths[path]))
        for method in methods:
            operation = paths[path][method]
            assert operation["operationId"].startswith("settings_")
            assert operation["responses"]
    assert "requestBody" in paths["/api/v1/o/{org}/settings/lock-dates"]["patch"]


def test_settings_read_and_change(org: Organisation) -> None:
    owner, employee = _client(org, "owner"), _client(org, "employee")
    body = employee.get(url(org)).json()
    assert body["display_name"] == "Refined Interiors Inc." and body["base_currency"] == "CAD"
    assert patch(employee, url(org), {"industry": "Design"}).status_code == 403

    bad = patch(owner, url(org), {"legal_name": "1001633222"})
    assert bad.status_code == 400 and bad.json()["legal_name"][0]
    changed = patch(
        owner, url(org), {"legal_name": "Refined Interiors Inc.", "base_currency": "USD"}
    )
    assert changed.status_code == 200 and changed.json()["base_currency"] == "CAD"
    with org_context(org):
        assert AuditEvent.objects.filter(object_type="orgsettings.OrganisationSettings").exists()


def test_registrations(org: Organisation) -> None:
    owner = _client(org, "owner")
    invalid = owner.post(
        url(org, "/registrations"), {"type": "bn", "number": "123456789"}, "application/json"
    )
    assert invalid.status_code == 400
    created = owner.post(
        url(org, "/registrations"), {"type": "bn", "number": "123456782"}, "application/json"
    )
    assert created.status_code == 201, created.content
    rid = created.json()["id"]
    listed = _client(org, "employee").get(url(org, "/registrations")).json()
    assert [r["id"] for r in listed] == [rid]
    assert patch(owner, url(org, f"/registrations/{rid}"), {"status": "inactive"}).status_code in (
        200,
        400,
    )
    other = Organisation.objects.create(name="Maple Leaf Bakery")
    stranger = _client(other, "owner")
    assert (
        stranger.get(f"/api/v1/o/{other.public_id}/settings/registrations/{rid}").status_code == 404
    )
    assert owner.delete(url(org, f"/registrations/{rid}")).status_code == 204
    assert owner.get(url(org, f"/registrations/{rid}")).status_code == 404


def test_lock_dates(org: Organisation) -> None:
    owner = _client(org, "owner")
    matrix = owner.get(url(org, "/lock-dates")).json()
    assert [row["module"] for row in matrix] == ["gl", "ar", "ap", "bank", "payroll", "tax"]
    assert matrix[0]["everyone"] == {"date": None, "reason": "", "updated_at": None}

    set_ = patch(
        owner,
        url(org, "/lock-dates"),
        {"module": "gl", "level": "advisers_only", "date": "2026-03-31"},
    )
    assert set_.status_code == 200 and set_.json()[0]["advisers_only"]["date"] == "2026-03-31"
    out_of_order = patch(
        owner, url(org, "/lock-dates"), {"module": "gl", "level": "everyone", "date": "2026-04-30"}
    )
    assert out_of_order.status_code == 400
    assert out_of_order.json()["date"][0]
    back = patch(
        owner,
        url(org, "/lock-dates"),
        {"module": "gl", "level": "advisers_only", "date": "2026-02-28"},
    )
    assert back.status_code == 400 and "reason" in back.json()
    ok = patch(
        owner,
        url(org, "/lock-dates"),
        {
            "module": "gl",
            "level": "advisers_only",
            "date": "2026-02-28",
            "reason": "Late bill for March",
        },
    )
    assert (
        ok.status_code == 200 and ok.json()[0]["advisers_only"]["reason"] == "Late bill for March"
    )
    assert (
        patch(
            _client(org, "employee"),
            url(org, "/lock-dates"),
            {"module": "gl", "level": "everyone", "date": None},
        ).status_code
        == 403
    )


def test_numbering(org: Organisation) -> None:
    owner = _client(org, "owner")
    rows = owner.get(url(org, "/numbering")).json()
    by_type = {row["doc_type"]: row for row in rows}
    assert {"invoice", "credit_note", "quote", "purchase_order"} <= set(by_type)
    changed = patch(
        owner, url(org, "/numbering"), {"doc_type": "invoice", "prefix": "RI-", "padding": 5}
    )
    assert changed.status_code == 200
    assert changed.json()["prefix"] == "RI-" and changed.json()["preview"].startswith("RI-")
    bad = patch(owner, url(org, "/numbering"), {"doc_type": "invoice", "next_number": 0})
    assert bad.status_code == 400


def test_lock_change_notifies_the_admins(org: Organisation) -> None:
    """Flow F6: saving a lock date tells the organisation's other owners and admins."""
    from numo9.notifications.models import Notification

    owner = _client(org, "owner")
    admin_user = User.objects.create_user("second-admin@refined.ca", password="x" * 12, name="Ad")
    OrganisationMember.objects.create(organisation=org, user=admin_user, role="admin")
    answer = patch(
        owner,
        url(org, "/lock-dates"),
        {"module": "gl", "level": "advisers_only", "date": "2026-06-30"},
    )
    assert answer.status_code == 200
    with org_context(org):
        [note] = Notification.objects.filter(recipient=admin_user)
    assert note.title_key == "notifications.settings.lock_changed"
    assert note.body_params["date"] == "2026-06-30" and note.link.endswith("/settings/lock-dates")
    with org_context(org):
        assert not Notification.objects.filter(recipient__email__startswith="owner-").exists()


def test_french_reader_gets_french_errors(org: Organisation) -> None:
    """A-05-T15: the model's rules come back in the reader's language (fr-CA)."""
    user = User.objects.create_user(
        "francine@refined.ca", password="x" * 12, name="F", locale="fr-ca"
    )
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    browser = Client()
    browser.force_login(user)
    bad = patch(browser, url(org), {"mailing_province": "ON", "mailing_postal_code": "H2X 1Y4"})
    assert bad.status_code == 400
    message = bad.json()["mailing_postal_code"][0]
    assert "Les codes postaux commençant par H" in message and "vérifiez le code postal" in message
    matrix = browser.get(url(org, "/lock-dates")).json()
    assert matrix[0]["module_label"] == "Grand livre"
