"""F-07-T08 — Banking settings: the negative-balance policy per account type, with an explanation.

Acceptance: changing Chequing to BLOCK takes effect on the next post — an owner's overdrawing
spend is a warning (422, reason asked) before and a block (409) right after the change. Also:
GET lists the four controlled types (no liabilities) with defaults, choices and explanations;
the change is audited; an unchanged row writes nothing; a type twice or a liability → 400; an
employee can't change it (403); the router sweep passes.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    owner = Client()
    owner.force_login(people(org)["owner"])
    base = f"/api/v1/o/{org.public_id}/"
    chequing = owner.post(
        base + "bank-accounts",
        {"type": "chequing", "display_name": "TD Chequing"},
        content_type="application/json",
    ).json()["id"]
    with org_context(org):
        office = Account.objects.filter(subtype="operating_expense").order_by("code").first()
    assert office is not None
    return {"org": org, "owner": owner, "base": base, "chequing": chequing, "office": office}


def _policies(client: Client, books: dict[str, Any]) -> Any:
    return client.get(books["base"] + "bank-settings/cash-policies")


def _put(client: Client, books: dict[str, Any], rows: list[dict[str, str]]) -> Any:
    return client.put(
        books["base"] + "bank-settings/cash-policies",
        {"policies": rows},
        content_type="application/json",
    )


def _spend(books: dict[str, Any]) -> Any:
    return books["owner"].post(
        books["base"] + "bank-transactions",
        {
            "kind": "spend",
            "bank_account": books["chequing"],
            "date": "2026-06-15",
            "tax_mode": "no_tax",
            "lines": [{"account": str(books["office"].public_id), "amount": "75.00"}],
        },
        content_type="application/json",
    )


def test_lists_the_controlled_types_with_defaults_and_explanations(books: dict[str, Any]) -> None:
    body = _policies(books["owner"], books).json()
    rows = {row["account_type"]: row for row in body["policies"]}
    assert list(rows) == ["chequing", "savings", "cash", "clearing"]
    assert (rows["cash"]["standard"], rows["cash"]["adviser"]) == ("block", "warn")
    assert rows["chequing"]["default"] == {"standard": "warn", "adviser": "warn"}
    assert "overdraft" in rows["chequing"]["explanation"]
    assert [a["value"] for a in body["actions"]] == ["allow", "warn", "block"]


def test_changing_to_block_takes_effect_on_the_next_post(books: dict[str, Any]) -> None:
    before = _spend(books)
    assert (before.status_code, before.json()["code"]) == (
        422,
        "ledger.journal.override_reason_required",
    )
    changed = _put(
        books["owner"],
        books,
        [{"account_type": "chequing", "standard": "block", "adviser": "warn"}],
    )
    assert changed.status_code == 200
    assert changed.json()["policies"][0]["standard"] == "block"
    after = _spend(books)
    assert (after.status_code, after.json()["code"]) == (409, "ledger.journal.negative_cash")
    with org_context(books["org"]):
        events = AuditEvent.objects.filter(action__startswith="banking.cashcontrolpolicy")
        assert events.count() == 1
    # the same values again write nothing
    _put(
        books["owner"],
        books,
        [{"account_type": "chequing", "standard": "block", "adviser": "warn"}],
    )
    with org_context(books["org"]):
        assert (
            AuditEvent.objects.filter(action__startswith="banking.cashcontrolpolicy").count() == 1
        )


def test_validation_permission_and_sweep(books: dict[str, Any]) -> None:
    twice = _put(
        books["owner"],
        books,
        [
            {"account_type": "cash", "standard": "warn", "adviser": "warn"},
            {"account_type": "cash", "standard": "block", "adviser": "warn"},
        ],
    )
    assert twice.status_code == 400
    card = _put(
        books["owner"],
        books,
        [{"account_type": "credit_card", "standard": "block", "adviser": "warn"}],
    )
    assert card.status_code == 400
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=books["org"], user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    refused = _put(
        client, books, [{"account_type": "cash", "standard": "allow", "adviser": "allow"}]
    )
    assert refused.status_code == 403
    call_command("tenant_sweep", stdout=StringIO())
