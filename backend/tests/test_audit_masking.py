"""Masking end to end (A-04-T13): SIN and bank details never leave the record through the log.

A record with a SIN (encrypted field), a bank account (masked by name) and an internal code
(masked by the model's list) is created, changed and deleted; then every way out of the audit log
is searched for the values — the table itself (as PostgreSQL stores it), the list, the event
detail, the record history, "view as of", the CSV, XLSX and PDF exports and the platform log.
None may contain them; each says the field changed and that its value is hidden.
"""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from openpyxl import load_workbook
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.audit.service import MASKED
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.testapp.models import AuditedInvoice

pytestmark = pytest.mark.django_db

SECRETS = ("046454286", "130692544", "00123-004-1234567", "99999-001-7654321", "INT-SECRET-1")


@pytest.fixture
def setup() -> tuple[Organisation, AuditedInvoice, APIClient]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    owner = User.objects.create_user("avery@refined.ca", password="x" * 12, name="Avery Owner")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    with org_context(org):
        invoice = AuditedInvoice.objects.create(
            number="INV-1",
            amount=Decimal("10.00"),
            payee_sin="046454286",
            bank_account="00123-004-1234567",
            internal_code="INT-SECRET-1",
        )
        invoice.payee_sin = "130692544"
        invoice.bank_account = "99999-001-7654321"
        invoice.amount = Decimal("11.00")
        invoice.save()
        invoice.delete()
    client = APIClient()
    client.force_authenticate(owner)
    return org, invoice, client


def assert_clean(text: str, where: str) -> None:
    for secret in SECRETS:
        assert secret not in text, f"{secret} found in {where}"


def test_no_way_out_of_the_log_shows_a_masked_value(
    setup: tuple[Organisation, AuditedInvoice, APIClient],
) -> None:
    org, invoice, client = setup
    base = f"/api/v1/o/{org.public_id}/audit/"
    record = f"records/testapp.AuditedInvoice/{invoice.public_id}"

    with connection.cursor() as cursor:
        cursor.execute("SELECT changes::text, meta::text, hash FROM audit_event")
        assert_clean(" ".join(" ".join(row) for row in cursor.fetchall()), "the table")

    listed = client.get(base + "events").json()
    assert_clean(str(listed), "the list")
    updated = next(r for r in listed["results"] if r["verb"] == "updated")
    sin = next(c for c in updated["changes"] if c["field"] == "payee_sin")
    assert sin["masked"] is True and sin["old"] == MASKED and sin["new"] == MASKED

    assert_clean(str(client.get(base + f"events/{updated['id']}").json()), "the event detail")
    assert_clean(str(client.get(base + record).json()), "the record history")
    as_of = client.get(base + record + "/as-of", {"at": "2100-01-01"}).json()
    assert_clean(str(as_of), "view as of")
    assert next(f for f in as_of["state"] if f["field"] == "payee_sin")["masked"] is True

    csv_response: Any = client.get(base + "export/csv")
    csv_text = b"".join(csv_response.streaming_content).decode()
    assert_clean(csv_text, "the CSV export")
    assert "Payee sin: Hidden" in csv_text
    sheet = load_workbook(io.BytesIO(client.get(base + "export/xlsx").content)).worksheets[0]
    cells = " ".join(str(c) for row in sheet.iter_rows(values_only=True) for c in row)
    assert_clean(cells, "the XLSX export")
    from pypdf import PdfReader

    pdf = PdfReader(io.BytesIO(client.get(base + "export/pdf").content))
    assert_clean(" ".join(p.extract_text() for p in pdf.pages), "the PDF export")

    staff = User.objects.create_user("support@numo9.ca", password="x" * 12, name="Support")
    RoleAssignment.objects.create(
        role=Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key="platform_owner"),
        user=staff,
    )
    browser = Client()
    browser.force_login(staff)
    platform = browser.get("/api/v1/platform/audit/events").json()
    assert_clean(str(platform), "the platform log")
