"""B-03-T11 — imports API: upload, map, dry-run, apply, status, errors CSV (+ template, export).

Contract: upload returns headers, samples, the suggested mapping (French headers too) and the
fields; a dry run stores and returns the rows and writes nothing; apply needs a dry run and
starts a background job; status and rows by action; the errors CSV lists row, column and reason;
template and export downloads; 25 MB limit; permissions (403), another organisation (404),
documented.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from numo9.accounts.models import User
from numo9.contacts.models import Contact
from numo9.imports.models import ImportRun
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = pytest.mark.django_db

CSV = (
    "Identifiant externe,Nom,Courriel,Province\n"
    "X-1,Maple Leaf Supply Ltd.,dana@m.ca,ON\n"
    "X-2,Birch,,Ontar\n"
)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


def _client(org: Organisation, role: str = "owner") -> Client:
    user = User.objects.create_user(
        f"{role}-{org.public_id.hex[:6]}@m.ca", password="x" * 12, name=role
    )
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


def url(org: Organisation, suffix: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/imports{suffix}"


def _upload(browser: Client, org: Organisation, text: str = CSV) -> Any:
    return browser.post(
        url(org),
        {"entity": "contacts.contact", "file": SimpleUploadedFile("contacts.csv", text.encode())},
    )


def test_wizard_steps(org: Organisation) -> None:
    browser = _client(org)
    uploaded = _upload(browser, org)
    assert uploaded.status_code == 201, uploaded.json()
    body = uploaded.json()
    assert body["columns"] == {
        "Identifiant externe": "external_id",
        "Nom": "display_name",
        "Courriel": "email",
        "Province": "billing_province",
    }
    assert body["samples"]["Nom"][0] == "Maple Leaf Supply Ltd."
    assert any(f["key"] == "display_name" and f["required"] for f in body["fields"])

    run = body["id"]
    assert browser.post(url(org, f"/{run}/apply")).status_code == 400  # dry run first
    checked = browser.post(
        url(org, f"/{run}/dry-run"),
        {
            "columns": body["columns"],
            "options": {"match_bn": False},
            "save_mapping_as": "Xero export",
        },
        content_type="application/json",
    )
    assert checked.status_code == 200, checked.json()
    assert checked.json()["counts"] == {"create": 1, "update": 0, "unchanged": 0, "error": 1}
    assert Contact.objects.unscoped(reason="test").filter(organisation=org).count() == 0
    errors = browser.get(url(org, f"/{run}/rows"), {"action": "error"}).json()
    assert errors["count"] == 1 and errors["results"][0]["row"] == 3

    csv = browser.get(url(org, f"/{run}/errors.csv"))
    assert csv.status_code == 200
    text = csv.content.decode("utf-8-sig")
    assert "3,Billing province" in text and "Ontar" in text

    started = browser.post(url(org, f"/{run}/apply"))
    assert started.status_code == 202, started.json()
    assert started.json()["job"]
    assert ImportRun.objects.unscoped(reason="test").get(public_id=run).status in (
        "applying",
        "applied",
    )
    assert browser.get(url(org, f"/{run}")).json()["entity"] == "contacts.contact"


def test_template_and_export(org: Organisation) -> None:
    browser = _client(org)
    template = browser.get(url(org, "/template"), {"entity": "contacts.person"})
    assert template.status_code == 200
    assert template.content.decode("utf-8-sig").startswith("Contact (External ID or number)")
    export = browser.get(f"/api/v1/o/{org.public_id}/contacts/export", {"file_type": "xlsx"})
    assert export.status_code == 200 and export.content[:2] == b"PK"


def test_bad_file_permissions_and_isolation(org: Organisation) -> None:
    browser = _client(org)
    bad = browser.post(
        url(org), {"entity": "contacts.contact", "file": SimpleUploadedFile("x.pdf", b"%PDF-1.4")}
    )
    assert bad.status_code == 400 and "file" in bad.json()
    assert _upload(_client(org, "employee"), org).status_code == 403
    run = _upload(browser, org).json()["id"]
    other = Organisation.objects.create(name="Other Inc.")
    assert _client(other).get(url(other, f"/{run}")).status_code == 404


def test_documented(org: Organisation) -> None:
    schema = yaml.safe_load(_client(org).get("/api/schema/").content)
    assert "post" in schema["paths"]["/api/v1/o/{org}/imports"]
    assert "post" in schema["paths"]["/api/v1/o/{org}/imports/{public_id}/dry-run"]
