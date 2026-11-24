"""G-06-T06 — unified tax settings history: one audit-log filter over every tax object
(``?scope=tax``), and attribution enforced — every row names a person or a job id (seeds and
commands get their run's id; background jobs keep theirs); never "System" alone.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client

from numo9.audit.models import AuditEvent
from numo9.audit.service import record
from numo9.orgsettings.models import TaxRegistration
from numo9.tax.history import PROCESS_RUN, TAX_OBJECT_TYPES, tax_history
from numo9.tax.seed import ensure_tax_table
from numo9.tax.settings import change_basis, tax_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    owner = people(org)["owner"]
    with org_context(org):
        ensure_tax_table(org)  # a system seed: no person
        change_basis(
            org, "cash", "Cash basis for a small business", user=owner, today=dt.date(2026, 1, 1)
        )
    return {"org": org, "owner": owner}


def test_no_tax_history_row_without_a_person_or_job_id(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        events = AuditEvent.objects.filter(object_type__in=TAX_OBJECT_TYPES)
        assert events.exists()
        for event in events:
            job = (event.meta or {}).get("job") or {}
            assert event.actor_user_id is not None or job.get("id"), (event.action, event.meta)
        seeded = events.filter(actor_user__isnull=True).first()
        assert seeded is not None and seeded.meta["job"]["id"] == PROCESS_RUN


def test_a_background_job_keeps_its_own_id(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        row = tax_settings(org)
        event = record(
            "tax.taxsettings.updated",
            obj=row,
            changes={"rounding_mode": ["line", "document"]},
            meta={"job": {"id": "8421", "task": "numo9.tax.nightly"}},
        )
    assert event.meta["job"] == {"id": "8421", "task": "numo9.tax.nightly"}


def test_other_records_are_left_alone(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        event = record("contacts.contact.updated", object_type="contacts.Contact", object_id="x")
    assert "job" not in (event.meta or {})


def test_history_rows_and_the_audit_scope(books: dict[str, Any]) -> None:
    org, owner = books["org"], books["owner"]
    with org_context(org):
        TaxRegistration(organisation=org, type="bn", number="123456782").save()
    rows = tax_history(org)
    basis = next(r for r in rows if r["action"] == "tax.taxsettings.basis_changed")
    assert basis["by"]["kind"] == "user" and basis["by"]["name"]
    assert basis["changes"] == {"basis": ["accrual", "cash"]}
    assert basis["reason"] == "Cash basis for a small business"
    assert all(r["by"]["kind"] == "user" or r["by"]["id"] for r in rows)
    assert any(r["record"]["type"] == "orgsettings.TaxRegistration" for r in rows)

    client = Client()
    client.force_login(owner)
    body = client.get(f"/api/v1/o/{org.public_id}/audit/events", {"scope": "tax"}).json()
    types = {r["record"]["type"] for r in body["results"]}
    assert types and types <= set(TAX_OBJECT_TYPES)
    none = client.get(f"/api/v1/o/{org.public_id}/audit/events", {"scope": "nope"}).json()
    assert none["results"] == []
