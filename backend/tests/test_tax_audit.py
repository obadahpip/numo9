"""G-01-T16 — audit of tax-table changes and en / fr names.

Acceptance: correcting a component's rate through the API is audited with the person and the old
and new rate; a rate used by posted lines can't be changed (409); renaming a code is audited;
installing the table with a chart loaded by a person is attributed to that person (never an
anonymous "System" without a job); names come in English and French.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client
from django.utils import translation

from numo9.audit.models import AuditEvent
from numo9.ledger.models import Account
from numo9.ledger.services import post_journal
from numo9.ledger.template import load_template
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tax.models import TaxCode, TaxComponent
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    found = people(org)
    load_template(org, "ON", actor=found["owner"])
    client = Client()
    client.force_login(found["owner"])
    return {"org": org, "owner": found["owner"], "client": client}


def _url(org: Organisation, suffix: str) -> str:
    return f"/api/v1/o/{org.public_id}/tax/{suffix}"


def test_rate_correction_shows_user_and_old_new_rate(books: dict[str, Any]) -> None:
    org, client = books["org"], books["client"]
    with org_context(org):
        sk = TaxComponent.objects.get(key="pst_sk")
    changed = client.patch(
        _url(org, f"components/{sk.public_id}"), {"rate": "6.5"}, content_type="application/json"
    )
    assert changed.status_code == 200 and changed.json()["rate"] == "6.5"
    with org_context(org):
        event = AuditEvent.objects.filter(
            object_type="tax.TaxComponent", object_id=str(sk.public_id)
        ).latest("pk")
    assert event.actor_user_id == books["owner"].pk and event.actor_kind == "user"
    assert event.changes["rate"] == ["6.0000", "6.5000"]


def test_used_rate_is_refused(books: dict[str, Any]) -> None:
    org, client = books["org"], books["client"]
    with org_context(org):
        hst = TaxComponent.objects.get(key="hst_on")
        office, bank = Account.objects.get(code="6080"), Account.objects.get(code="1010")
        post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 15),
                lines=[
                    LineSpec(office, debit="10.00", tax_code="purchase.ON.standard"),
                    LineSpec(bank, credit="10.00"),
                ],
            ),
            user=None,
        )
    refused = client.patch(
        _url(org, f"components/{hst.public_id}"), {"rate": "14"}, content_type="application/json"
    )
    assert (refused.status_code, refused.json()["code"]) == (409, "tax.component.in_use")
    renamed = client.patch(
        _url(org, f"components/{hst.public_id}"),
        {"name": "HST Ontario", "name_fr": "TVH Ontario"},
        content_type="application/json",
    )
    assert renamed.status_code == 200


def test_code_rename_is_audited_and_names_are_bilingual(books: dict[str, Any]) -> None:
    org, client = books["org"], books["client"]
    with org_context(org):
        code = TaxCode.objects.get(code="sales.ON.standard")
        with translation.override("fr-ca"):
            assert code.name == "TVH 13 % (Ontario) sur les ventes"
        assert code.name == "HST 13 % (Ontario) on sales"
    done = client.patch(
        _url(org, f"codes/{code.public_id}"),
        {"name_fr": "TVH 13 % (Ont.) sur les ventes"},
        content_type="application/json",
    )
    assert done.status_code == 200
    with org_context(org):
        event = AuditEvent.objects.filter(
            object_type="tax.TaxCode", object_id=str(code.public_id)
        ).latest("pk")
    assert event.actor_user_id == books["owner"].pk
    assert "name_i18n" in event.changes


def test_installation_attributed_to_the_person_loading_the_chart(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        events = AuditEvent.objects.filter(object_type__startswith="tax.")
        assert events.exists()
        assert set(events.values_list("actor_user", flat=True)) == {books["owner"].pk}
        assert not events.filter(actor_kind="system").exists()
