"""A-07-T05 — SendingDomain model + provider API to create the domain and fetch the DKIM records.

Acceptance: records stored (provider mocked) — adding refined.ca creates it at the provider and
stores SPF, DKIM (the provider's key), DMARC and return-path records with their hosts and values.
Also: names normalised and validated (not a domain, public mailbox domains, Numo9's own domain),
one per organisation, provider outage → 503 and nothing stored, refresh after a DKIM rotation
resets that record's check, delete at the provider, the local provider generates a real RSA DKIM
key and keeps the private key encrypted (never in the API), permission and isolation.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from django.db import connection
from django.test import Client

from numo9.accounts.models import User
from numo9.notifications import providers
from numo9.notifications.models import RecordStatus, SendingDomain, SendingDomainRecord
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.notification_helpers import FakeProvider

pytestmark = pytest.mark.django_db


@pytest.fixture
def fake(settings: Any) -> Iterator[FakeProvider]:
    provider = FakeProvider()
    providers.register_provider(provider)
    settings.NUMO9_EMAIL_DOMAIN_PROVIDER = provider.name
    yield provider
    providers._providers.pop(provider.name, None)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def _member(org: Organisation, role: str = "owner", email: str = "dana@refined.ca") -> Client:
    user = User.objects.create_user(email=email, password="x" * 12, name="Dana")
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


def url(org: Organisation, suffix: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/email-domains{suffix}"


def test_records_stored_from_the_provider(org: Organisation, fake: FakeProvider) -> None:
    browser = _member(org)
    response = browser.post(
        url(org), {"domain": " WWW.Refined.CA. ", "from_local_part": "invoices"}, "application/json"
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["domain"] == "refined.ca" and body["status"] == "pending"
    assert body["from_address"] == "invoices@refined.ca" and body["provider"] == "fake-esp"
    assert fake.calls == [("create", "refined.ca")]
    records = {r["kind"]: r for r in body["records"]}
    assert (records["spf"]["record_type"], records["spf"]["host"]) == ("TXT", "refined.ca")
    assert records["spf"]["value"] == "v=spf1 include:spf.numo9.ca ~all"
    assert records["dkim"]["host"] == "pm202611._domainkey.refined.ca"
    assert records["dkim"]["value"] == fake.dkim_value
    assert records["dmarc"]["host"] == "_dmarc.refined.ca"
    assert records["dmarc"]["value"].startswith("v=DMARC1; p=quarantine")
    assert (records["return_path"]["record_type"], records["return_path"]["value"]) == (
        "CNAME",
        "pm.mtasv.net",
    )
    assert all(r["status"] == "unchecked" for r in body["records"])
    assert "dkim_private_key" not in body
    with org_context(org):
        row = SendingDomain.objects.get()
        assert row.provider_domain_id == "esp-refined.ca" and row.dkim_selector == "pm202611"
        assert SendingDomainRecord.objects.filter(sending_domain=row).count() == 4

    listed = browser.get(url(org)).json()["results"]
    assert [d["domain"] for d in listed] == ["refined.ca"]
    again = browser.post(url(org), {"domain": "refined.ca"}, "application/json")
    assert again.status_code == 409 and again.json()["code"] == "email_domain.exists"


@pytest.mark.parametrize(
    ("domain", "code"),
    [
        ("not a domain", "email_domain.invalid"),
        ("refined", "email_domain.invalid"),
        ("gmail.com", "email_domain.not_yours"),
        ("numo9.ca", "email_domain.not_yours"),
        ("mail.numo9.ca", "email_domain.not_yours"),
    ],
)
def test_names_validated(org: Organisation, fake: FakeProvider, domain: str, code: str) -> None:
    response = _member(org).post(url(org), {"domain": domain}, "application/json")
    assert response.status_code == 400 and response.json()["code"] == code
    assert fake.calls == []


def test_provider_outage_stores_nothing(org: Organisation, fake: FakeProvider) -> None:
    fake.fail = True
    response = _member(org).post(url(org), {"domain": "refined.ca"}, "application/json")
    assert response.status_code == 503
    assert response.json()["code"] == "email_domain.provider_unavailable"
    assert SendingDomain.objects.unscoped(reason="test").count() == 0


def test_refresh_after_dkim_rotation_resets_the_check(
    org: Organisation, fake: FakeProvider
) -> None:
    browser = _member(org)
    created = browser.post(url(org), {"domain": "refined.ca"}, "application/json").json()
    with org_context(org):
        SendingDomainRecord.objects.update(status=RecordStatus.OK)
        SendingDomain.objects.update(status="verified")
    unchanged = browser.post(url(org, f"/{created['id']}/refresh")).json()
    assert unchanged["status"] == "verified"
    fake.dkim_value = "v=DKIM1; k=rsa; p=ROTATED"
    rotated = browser.post(url(org, f"/{created['id']}/refresh")).json()
    records = {r["kind"]: r for r in rotated["records"]}
    assert records["dkim"]["value"] == "v=DKIM1; k=rsa; p=ROTATED"
    assert records["dkim"]["status"] == "unchecked" and records["spf"]["status"] == "ok"
    assert rotated["status"] == "partial"


def test_delete_at_the_provider(org: Organisation, fake: FakeProvider) -> None:
    browser = _member(org)
    created = browser.post(url(org), {"domain": "refined.ca"}, "application/json").json()
    assert browser.delete(url(org, f"/{created['id']}")).status_code == 204
    assert ("delete", "esp-refined.ca") in fake.calls
    assert browser.get(url(org, f"/{created['id']}")).status_code == 404
    # The name may be added again.
    assert browser.post(url(org), {"domain": "refined.ca"}, "application/json").status_code == 201


def test_local_provider_generates_a_dkim_key_stored_encrypted(org: Organisation) -> None:
    browser = _member(org)
    body = browser.post(url(org), {"domain": "refined.ca"}, "application/json").json()
    dkim = {r["kind"]: r for r in body["records"]}["dkim"]
    assert dkim["host"].startswith("numo9-") and dkim["host"].endswith("._domainkey.refined.ca")
    public = base64.b64decode(dkim["value"].split("p=", 1)[1])
    key = serialization.load_der_public_key(public)
    assert key.key_size == 2048  # type: ignore[union-attr]
    with org_context(org):
        row = SendingDomain.objects.get()
    assert row.dkim_private_key.startswith("-----BEGIN PRIVATE KEY-----")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT dkim_private_key FROM notifications_sendingdomain WHERE id = %s", [row.pk]
        )
        stored = cursor.fetchone()[0]
    assert "PRIVATE KEY" not in stored  # encrypted at rest


def test_permission_and_isolation(org: Organisation, fake: FakeProvider) -> None:
    owner = _member(org)
    created = owner.post(url(org), {"domain": "refined.ca"}, "application/json").json()
    employee = _member(org, role="employee", email="emp@refined.ca")
    assert employee.get(url(org)).status_code == 403
    other = Organisation.objects.create(name="Maple Leaf Bakery")
    stranger = _member(other, email="sam@mapleleaf.ca")
    assert (
        stranger.get(f"/api/v1/o/{other.public_id}/email-domains/{created['id']}").status_code
        == 404
    )
