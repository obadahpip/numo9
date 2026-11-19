"""B-02-T09 — APIs: timeline, statements (preview, PDF, send, history), supplier reconciliation.

Contract: the timeline with type filter and notes; the statement preview equals the engine and the
PDF is a PDF; sending stores the history and the timeline event; a supplier statement uploaded from
a CSV reconciles (pairs, unmatched, totals) and a line can be matched by hand; permissions (403),
another organisation's contact (404), documented, swept.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest
import yaml
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from numo9.accounts.models import User
from numo9.contacts import subledger
from numo9.contacts.models import ContactPerson
from numo9.contacts.subledger import FixtureDocument, FixtureSource
from numo9.notifications import mail as outgoing
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db
D, day = Decimal, dt.date


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture
def sources() -> Iterator[dict[str, FixtureSource]]:
    made = {"receivables": FixtureSource("receivables"), "payables": FixtureSource("payables")}
    for source in made.values():
        subledger.register_source(source)
    yield made
    for source in made.values():
        subledger.unregister_source(source)


def _client(org: Organisation, role: str = "owner") -> Client:
    user = User.objects.create_user(
        f"{role}-{org.public_id.hex[:6]}@m.ca", password="x" * 12, name=role
    )
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


def _maple(org: Organisation, roles: list[str]) -> Any:
    with org_context(org):
        maple = contact(org, "Maple Leaf Supply Ltd.", roles=roles)
        ContactPerson(organisation=org, contact=maple, first_name="Dana", email="dana@m.ca").save()
        return maple


def base(org: Organisation, maple: Any) -> str:
    return f"/api/v1/o/{org.public_id}/contacts/{maple.public_id}"


def test_statement_preview_pdf_send_and_timeline(
    org: Organisation, sources: dict[str, FixtureSource], s3: str
) -> None:
    maple = _maple(org, ["customer"])
    sources["receivables"].add(
        FixtureDocument(maple.pk, "INV-1", day(2026, 3, 1), D("300.00"), day(2026, 3, 31))
    )
    browser = _client(org)
    preview = browser.get(f"{base(org, maple)}/statement", {"as_at": "2026-03-31"}).json()
    assert preview["amount_due"] == "300.00" and preview["lines"][0]["document"] == "INV-1"
    pdf = browser.get(f"{base(org, maple)}/statement.pdf", {"as_at": "2026-03-31"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    with mock.patch.object(outgoing.send_email, "apply_async", lambda args=None, **kw: None):
        sent = browser.post(
            f"{base(org, maple)}/statement/send",
            {"kind": "outstanding", "as_at": "2026-03-31"},
            content_type="application/json",
        )
    assert sent.status_code == 201, sent.json()
    assert sent.json()["recipients"] == ["dana@m.ca"]
    history = browser.get(f"{base(org, maple)}/statements").json()["results"]
    assert history[0]["amount_due"] == "300.00"
    browser.post(
        f"{base(org, maple)}/activity", {"title": "Called Dana"}, content_type="application/json"
    )
    events = browser.get(f"{base(org, maple)}/activity").json()["results"]
    assert [e["type"] for e in events] == ["note", "statement"]
    only = browser.get(f"{base(org, maple)}/activity", {"type": "statement"}).json()["results"]
    assert [e["type"] for e in only] == ["statement"]
    bad = browser.get(f"{base(org, maple)}/statement", {"kind": "activity", "as_at": "2026-03-31"})
    assert bad.status_code == 400


def test_supplier_reconciliation(org: Organisation, sources: dict[str, FixtureSource]) -> None:
    maple = _maple(org, ["supplier"])
    sources["payables"].add(FixtureDocument(maple.pk, "B-1", day(2026, 3, 2), D("100.00")))
    sources["payables"].add(FixtureDocument(maple.pk, "B-2", day(2026, 3, 9), D("40.00")))
    browser = _client(org)
    csv = b"Date,Invoice,Amount\n2026-03-02,b-1,100.00\n2026-03-20,X-9,55.00\n"
    made = browser.post(
        f"{base(org, maple)}/supplier-statements",
        {"file": SimpleUploadedFile("their.csv", csv), "statement_date": "2026-03-31"},
    )
    assert made.status_code == 201, made.json()
    url = f"{base(org, maple)}/supplier-statements/{made.json()['id']}"
    report = browser.get(f"{url}/reconciliation").json()
    assert [p["how"] for p in report["pairs"]] == ["number"]
    assert [line["amount"] for line in report["unmatched_theirs"]] == ["55.00"]
    assert [item["document"] for item in report["unmatched_ours"]] == ["B-2"]
    assert (report["their_total"], report["our_total"], report["difference"]) == (
        "155.00",
        "140.00",
        "15.00",
    )
    line = report["unmatched_theirs"][0]["id"]
    patched = browser.patch(
        f"{url}/lines/{line}",
        {"manual_ref": "B-2", "note": "They billed 55, we 40"},
        content_type="application/json",
    )
    assert patched.status_code == 200
    again = browser.get(f"{url}/reconciliation").json()
    assert sorted(p["how"] for p in again["pairs"]) == ["manual", "number"]
    assert (
        browser.get(f"{base(org, maple)}/supplier-statements").json()["results"][0][
            "statement_date"
        ]
        == "2026-03-31"
    )


def test_permissions_isolation_documented(org: Organisation) -> None:
    maple = _maple(org, ["customer"])
    assert _client(org, "employee").get(f"{base(org, maple)}/activity").status_code == 403
    other = Organisation.objects.create(name="Other Inc.")
    assert (
        _client(other)
        .get(f"/api/v1/o/{other.public_id}/contacts/{maple.public_id}/activity")
        .status_code
        == 404
    )
    schema = yaml.safe_load(_client(org).get("/api/schema/").content)
    assert "get" in schema["paths"]["/api/v1/o/{org}/contacts/{public_id}/statement"]
