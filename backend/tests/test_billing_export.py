"""U-04-T11 — Cancellation and the data export job. Acceptance: the ZIP holds every dataset.

Covers: cancelling sets the Stripe subscription to cancel at the period end (access continues),
marks it locally and starts the export; resuming undoes it; the export job writes one ZIP to the
organisation's prefix: README, one CSV per registered dataset (every one — settings,
registrations, lock dates, contacts, chart of accounts, journal lines, documents, Numo9 invoices),
the XLSX workbook (one sheet each), the JSON ledger with every posted journal and its lines, and
the clean documents' files (an infected one is listed, not included); the billing page gets a
fresh signed link; owner only; not paying → 409.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import zipfile
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
import requests
from django.test import Client, override_settings
from openpyxl import load_workbook

from numo9.billing.export import (
    build_zip,
    cancel,
    datasets,
    export_link,
    export_organisation,
    latest_export,
    resume,
)
from numo9.billing.models import PlatformInvoice
from numo9.entitlements.models import Subscription
from numo9.files.models import Document
from numo9.files.storage import new_key, org_prefix, put_bytes
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import LockDate, TaxRegistration
from numo9.packages.models import Package
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.billing_helpers import FakeGateway, owned_org, sold_package
from tests.contact_helpers import contact
from tests.files_helpers import PDF
from tests.job_helpers import deliver
from tests.ledger_helpers import account

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("s3")]

EVERY = {
    "organisation_settings",
    "tax_registrations",
    "lock_dates",
    "contacts",
    "chart_of_accounts",
    "journal_lines",
    "documents",
    "numo9_invoices",
}


@pytest.fixture(autouse=True)
def fake() -> Iterator[None]:
    FakeGateway.reset()
    FakeGateway.subscriptions = {"sub_1": {"id": "sub_1"}}
    sold_package("growth")
    with override_settings(NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway"):
        yield


@pytest.fixture
def paying() -> tuple[Organisation, Any]:
    org, owner = owned_org()
    Subscription._base_manager.filter(organisation=org).update(
        stripe_customer_id="cus_test_0001",
        stripe_subscription_id="sub_1",
        status="active",
        package=Package.objects.get(code="growth"),
        current_period_end=dt.datetime(2026, 12, 31, tzinfo=dt.UTC),
    )
    with org_context(org):
        TaxRegistration(organisation=org, type="bn", number="123456782").save()
        LockDate(organisation=org, module="gl", level="everyone", date=dt.date(2025, 12, 31)).save()
        contact(org, "Érable Distribution inc.")
        bank = account(org, "1000", "Chequing", subtype="bank")
        sales = account(org, "4000", "Sales", subtype="revenue")
        post_journal(
            JournalSpec(
                date=dt.date(2026, 3, 1),
                narration="Opening sale",
                lines=(
                    LineSpec(bank, debit=Decimal("100.00")),
                    LineSpec(sales, credit=Decimal("100.00")),
                ),
            ),
            user=None,
        )
        for name, status in (("receipt.pdf", "clean"), ("virus.pdf", "infected")):
            key = new_key(org, name)
            put_bytes(key, PDF, "application/pdf")
            Document.objects.create(
                organisation=org,
                file_key=key,
                name=name,
                mime="application/pdf",
                size=len(PDF),
                status=status,
            )
        PlatformInvoice.objects.create(
            organisation=org,
            stripe_invoice_id="in_1",
            number="NUMO9-0001",
            status="paid",
            total_cents=5537,
            amount_paid_cents=5537,
        )
    return org, owner


def test_registered_datasets_are_every_module() -> None:
    assert {d.name for d in datasets()} == EVERY


def test_zip_contains_every_dataset(paying: tuple[Organisation, Any]) -> None:
    org, _ = paying
    with org_context(org):
        archive = zipfile.ZipFile(io.BytesIO(build_zip(org)))
    names = set(archive.namelist())
    assert {f"csv/{name}.csv" for name in EVERY} <= names
    assert {"README.txt", "numo9-export.xlsx", "json/ledger.json", "documents/receipt.pdf"} <= names
    assert "documents/virus.pdf" not in names
    assert archive.read("documents/receipt.pdf") == PDF
    contacts = list(csv.reader(io.StringIO(archive.read("csv/contacts.csv").decode("utf-8-sig"))))
    assert (
        contacts[0][:2] == ["number", "display_name"]
        and contacts[1][1] == "Érable Distribution inc."
    )
    lines = list(csv.reader(io.StringIO(archive.read("csv/journal_lines.csv").decode("utf-8-sig"))))
    assert [row[4:7] for row in lines[1:]] == [
        ["1000", "100.00", "0.00"],
        ["4000", "0.00", "100.00"],
    ]
    docs = archive.read("csv/documents.csv").decode("utf-8-sig")
    assert "virus.pdf" in docs and "infected" in docs
    workbook = load_workbook(io.BytesIO(archive.read("numo9-export.xlsx")))
    assert set(workbook.sheetnames) == EVERY
    ledger = json.loads(archive.read("json/ledger.json"))
    assert ledger["journals"][0]["number"] == "JE-000001"
    assert [line["account"] for line in ledger["journals"][0]["lines"]] == ["1000", "4000"]


def test_cancel_resume_and_the_export_link(
    paying: tuple[Organisation, Any], sent: list[dict[str, Any]]
) -> None:
    org, owner = paying
    subscription, run = cancel(org, owner)
    assert subscription.cancel_at_period_end and subscription.status == "active"
    assert FakeGateway.calls[-1][1]["cancel"] is True
    assert export_link(run) is None  # not run yet
    deliver(export_organisation, sent[-1])
    latest = latest_export(org)
    assert latest is not None and latest.status == "succeeded"
    link = export_link(latest)
    assert link is not None
    download = requests.get(link.url, timeout=10)
    assert download.status_code == 200
    assert "csv/contacts.csv" in zipfile.ZipFile(io.BytesIO(download.content)).namelist()
    result: Any = latest.result
    assert result["key"].startswith(org_prefix(org))
    resumed = resume(org, owner)
    assert not resumed.cancel_at_period_end and FakeGateway.calls[-1][1]["cancel"] is False


def test_api_owner_only(paying: tuple[Organisation, Any], sent: list[dict[str, Any]]) -> None:
    org, owner = paying
    client = Client()
    client.force_login(owner)
    base = f"/api/v1/o/{org.public_id}/billing"
    assert client.get(f"{base}/export").json()["job"] is None
    cancelled = client.post(f"{base}/cancel", {}, content_type="application/json")
    assert cancelled.status_code == 200 and cancelled.json()["cancel_at_period_end"] is True
    assert cancelled.json()["export"]["status"] == "queued"
    started = client.post(f"{base}/export")
    assert started.status_code == 202
    resumed = client.post(f"{base}/cancel", {"resume": True}, content_type="application/json")
    assert resumed.json()["cancel_at_period_end"] is False
    from numo9.accounts.models import User
    from numo9.tenancy.models import OrganisationMember

    admin = User.objects.create_user("admin@maple.ca", password="x" * 12)
    OrganisationMember.objects.create(organisation=org, user=admin, role="admin")
    other = Client()
    other.force_login(admin)
    assert other.post(f"{base}/cancel", {}, content_type="application/json").status_code == 403
    assert other.get(f"{base}/export").status_code == 403


def test_not_paying_is_refused(paying: tuple[Organisation, Any]) -> None:
    org, owner = paying
    Subscription._base_manager.filter(organisation=org).update(stripe_subscription_id="")
    client = Client()
    client.force_login(owner)
    refused = client.post(
        f"/api/v1/o/{org.public_id}/billing/cancel", {}, content_type="application/json"
    )
    assert (refused.status_code, refused.json()["code"]) == (409, "billing.not_paying")
