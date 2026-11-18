"""B-01-T11 — contacts API: CRUD, /duplicates, list filters by role, feature key, sweep.

Contract: create with people and addresses in one transaction (a bad address rolls everything
back, the error names the row and field), read every field, edit (people/addresses lists replaced:
ids updated, missing ones removed, new ones added), archive/restore, the list (by name, titled per
role: ``role`` filter and per-role counts, status, ``q`` on name/number/email/BN, paging),
duplicates while typing (trigram name, exact email/BN), permissions (403), feature (402), another
organisation → 404, documented, swept.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from django.test import Client

from numo9.accounts.models import User
from numo9.catalogue import drf as catalogue_drf
from numo9.contacts.models import Contact
from numo9.tenancy.models import Organisation, OrganisationMember
from numo9.tenancy.sweep import SWEEP_FACTORIES

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


def _client(org: Organisation, role: str = "owner") -> Client:
    user = User.objects.create_user(
        f"{role}-{org.public_id.hex[:6]}@maple.ca", password="x" * 12, name=role.title()
    )
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


def url(org: Organisation, suffix: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/contacts{suffix}"


def _create(browser: Client, org: Organisation, **body: Any) -> Any:
    payload = {
        "display_name": "Maple Leaf Supply Ltd.",
        "roles": ["supplier"],
        "people": [{"first_name": "Dana", "last_name": "Lee", "email": "dana@mapleleaf.ca"}],
        "addresses": [
            {
                "kind": "billing",
                "line1": "1 King St W",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "m5v2t6",
            }
        ],
        **body,
    }
    return browser.post(url(org), payload, content_type="application/json")


def test_create_read_edit_archive(org: Organisation) -> None:
    browser = _client(org)
    created = _create(browser, org, bn="123456782")
    assert created.status_code == 201, created.json()
    body = created.json()
    assert body["number"]  # the next number
    assert body["addresses"][0]["postal_code"] == "M5V 2T6"  # normalised by the model
    assert body["people"][0]["is_primary"] is True
    assert (body["email"], body["province"]) == ("dana@mapleleaf.ca", "ON")

    person_id = body["people"][0]["id"]
    edited = browser.patch(
        url(org, f"/{body['id']}"),
        {
            "roles": ["supplier", "customer"],
            "people": [
                {"id": person_id, "phone": "416-555-0100"},
                {"first_name": "Sam", "email": "sam@mapleleaf.ca", "is_primary": True},
            ],
        },
        content_type="application/json",
    )
    assert edited.status_code == 200, edited.json()
    people = {p["first_name"]: p for p in edited.json()["people"]}
    assert people["Dana"]["phone"] and people["Sam"]["is_primary"] is True
    assert people["Dana"]["is_primary"] is False

    dropped = browser.patch(
        url(org, f"/{body['id']}"),
        {"people": [{"id": people["Sam"]["id"]}]},
        content_type="application/json",
    )
    assert [p["first_name"] for p in dropped.json()["people"]] == ["Sam"]

    assert browser.post(url(org, f"/{body['id']}/archive")).json()["status"] == "archived"
    assert browser.get(url(org)).json()["count"] == 0
    assert browser.post(url(org, f"/{body['id']}/restore")).json()["status"] == "active"


def test_invalid_address_rolls_back_the_whole_contact(org: Organisation) -> None:
    browser = _client(org)
    refused = _create(
        browser,
        org,
        addresses=[{"kind": "billing", "province": "ON", "postal_code": "12345", "country": "CA"}],
    )
    assert refused.status_code == 400
    assert any(key.startswith("addresses[0].") for key in refused.json()), refused.json()
    assert not Contact.objects.unscoped(reason="test").filter(organisation=org).exists()

    no_role = _create(browser, org, roles=[])
    assert no_role.status_code == 400 and "roles" in no_role.json()


def test_list_by_role_with_counts_search_and_paging(org: Organisation) -> None:
    browser = _client(org)
    _create(browser, org)
    _create(
        browser, org, display_name="Birch Bakery Co.", roles=["customer"], people=[], addresses=[]
    )
    _create(
        browser, org, display_name="Cedar Foods Inc.", roles=["customer", "supplier"], people=[]
    )
    suppliers = browser.get(url(org), {"role": "supplier"}).json()
    assert [c["display_name"] for c in suppliers["results"]] == [
        "Cedar Foods Inc.",
        "Maple Leaf Supply Ltd.",
    ]
    assert suppliers["role_counts"]["customer"] == 2
    assert suppliers["role_counts"]["supplier"] == 2
    assert browser.get(url(org), {"q": "dana@maple"}).json()["count"] == 1
    page = browser.get(url(org), {"limit": 2}).json()
    assert len(page["results"]) == 2 and page["next_offset"] == 2
    assert browser.get(url(org), {"role": "nope"}).status_code == 400


def test_duplicates_while_typing(org: Organisation) -> None:
    browser = _client(org)
    first = _create(browser, org, bn="123456782").json()
    by_name = browser.get(url(org, "/duplicates"), {"q": "Maple Leaf Suply"}).json()["results"]
    assert by_name and by_name[0]["contact"]["id"] == first["id"]
    assert "name" in by_name[0]["reasons"]
    by_bn = browser.get(url(org, "/duplicates"), {"bn": "123456782"}).json()["results"]
    assert by_bn[0]["exact"] is True
    itself = browser.get(
        url(org, "/duplicates"), {"q": "Maple Leaf Supply Ltd.", "exclude": first["id"]}
    ).json()["results"]
    assert itself == []


def test_permission_feature_and_isolation(
    org: Organisation, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create(_client(org), org).json()
    employee = _client(org, "employee")
    assert employee.get(url(org)).status_code == 403
    other = Organisation.objects.create(name="Other Inc.")
    outsider = _client(other)
    assert outsider.get(url(org)).status_code == 404
    assert outsider.get(url(other, f"/{created['id']}")).status_code == 404

    class NoPackage:
        def allows(self, organisation: Organisation | None, key: str) -> bool:
            return False

    monkeypatch.setattr(catalogue_drf, "get_resolver", lambda: NoPackage())
    refused = _client(org, "admin").get(url(org))
    assert refused.status_code == 402
    assert refused.json()["feature"] == "accounting.contacts.read"


def test_documented_and_swept(org: Organisation) -> None:
    schema = yaml.safe_load(_client(org).get("/api/schema/").content)
    paths = schema["paths"]
    assert set(paths["/api/v1/o/{org}/contacts"]) >= {"get", "post"}
    assert set(paths["/api/v1/o/{org}/contacts/{public_id}"]) >= {"get", "patch"}
    assert "get" in paths["/api/v1/o/{org}/contacts/duplicates"]
    assert "contacts.Contact" in SWEEP_FACTORIES
