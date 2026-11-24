"""F-01-T14 — banking audit hooks: creating, renaming, editing the statement balance, archiving
and restoring a bank account through the API each leave an audit event attributed to the person
(never "System Generated"), with old and new values; the rename shows on the linked ledger
account too; the masked number never appears.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.audit.models import AuditEvent
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


def events(org: Organisation, object_type: str, object_id: str) -> list[AuditEvent]:
    with org_context(org):
        return list(
            AuditEvent.objects.filter(object_type=object_type, object_id=object_id).order_by("pk")
        )


def test_bank_account_lifecycle_is_audited_with_the_person(org: Organisation) -> None:
    owner = people(org)["owner"]
    client = Client()
    client.force_login(owner)
    base = f"/api/v1/o/{org.public_id}/bank-accounts"

    made = client.post(
        base,
        {
            "type": "chequing",
            "display_name": "TD Chequing",
            "institution": "TD",
            "account_last4": "4821",
        },
        content_type="application/json",
    )
    assert made.status_code == 201, made.json()
    bank: dict[str, Any] = made.json()

    def patch(body: dict[str, str]) -> Any:
        return client.patch(f"{base}/{bank['id']}", body, content_type="application/json")

    assert patch({"display_name": "TD Business Chequing"}).status_code == 200
    assert (
        patch({"statement_balance": "1250.00", "statement_balance_date": "2026-06-30"}).status_code
        == 200
    )
    assert client.post(f"{base}/{bank['id']}/archive").status_code == 200
    assert client.post(f"{base}/{bank['id']}/restore").status_code == 200

    trail = events(org, "banking.BankAccount", bank["id"])
    assert len(trail) >= 5
    # Every change is the owner's — no "System Generated" entry without a job id.
    assert {e.actor_user_id for e in trail} == {owner.pk}
    assert all(e.actor_kind != "system" for e in trail)

    created, *changes = trail
    assert created.changes["display_name"] == [None, "TD Chequing"]
    renamed = next(e for e in changes if "display_name" in (e.changes or {}))
    assert renamed.changes["display_name"] == ["TD Chequing", "TD Business Chequing"]
    statement = next(e for e in changes if "statement_balance" in (e.changes or {}))
    assert statement.changes["statement_balance"][1] == "1250.00"
    assert statement.changes["statement_balance_date"] == [None, "2026-06-30"]
    archived = [e for e in changes if "archived_at" in (e.changes or {})]
    assert len(archived) == 2 and archived[0].changes["archived_at"][0] is None
    assert archived[1].changes["archived_at"][1] is None
    # The last 4 digits are masked in the log, never the value.
    assert "4821" not in str([e.changes for e in trail])

    # The linked ledger account is renamed with it, attributed to the same person.
    gl = bank["ledger_account"]["id"]
    ledger = [e for e in events(org, "ledger.Account", gl) if "name_i18n" in (e.changes or {})]
    assert ledger and ledger[-1].actor_user_id == owner.pk
    assert "TD Business Chequing" in str(ledger[-1].changes["name_i18n"][1])


def test_record_history_of_the_account(org: Organisation) -> None:
    owner = people(org)["owner"]
    client = Client()
    client.force_login(owner)
    made = client.post(
        f"/api/v1/o/{org.public_id}/bank-accounts",
        {"type": "cash", "display_name": "Petty Cash"},
        content_type="application/json",
    ).json()
    client.patch(
        f"/api/v1/o/{org.public_id}/bank-accounts/{made['id']}",
        {"display_name": "Office float"},
        content_type="application/json",
    )
    history = client.get(
        f"/api/v1/o/{org.public_id}/audit/records/banking.BankAccount/{made['id']}"
    )
    assert history.status_code == 200, history.json()
    body = history.json()
    rows = body["results"]
    assert len(rows) >= 2
    assert {row["record"]["id"] for row in rows} == {made["id"]}
    renames = [
        change
        for row in rows
        for change in row["changes"]
        if change["field"] == "display_name" and change["old"] is not None
    ]
    assert [(c["label"], c["old"], c["new"]) for c in renames] == [
        ("Name", "Petty Cash", "Office float")
    ]
    assert rows[0]["record"]["type_label"] == "Bank account"
