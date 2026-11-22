"""F-01-T07 — banking API: bank accounts (CRUD, archive, restore) and bank transactions (spend,
receive, list, void → reverse).

Acceptance: an owner creates an account and sees it with its ledger balance; spend money posts and
the balance follows; delete with a transaction → 409 "has 1 transaction — archive it instead"
with the count; archive hides it from the active list; rename renames the ledger account; currency
is fixed once used; void reverses the journal; an employee without the permissions gets 403;
feature ``accounting.banking.write`` 402; another organisation's ids are 404; the router sweep
passes and the permission catalogue lists the new permissions.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.catalogue import drf as catalogue_drf
from numo9.ledger.models import Account, JournalEntry
from numo9.ledger.template import load_template
from numo9.rbac.catalogue import catalogue
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


@pytest.fixture
def owner(org: Organisation) -> Client:
    client = Client()
    client.force_login(people(org)["owner"])
    return client


def url(org: Organisation, suffix: str) -> str:
    return f"/api/v1/o/{org.public_id}/{suffix}"


def send(client: Client, path: str, payload: dict[str, Any], method: str = "post") -> Any:
    return getattr(client, method)(path, payload, content_type="application/json")


def _codes(org: Organisation) -> dict[str, str]:
    with org_context(org):
        office = Account.objects.filter(subtype="operating_expense").order_by("code").first()
        return {"office": str(office.public_id)}  # type: ignore[union-attr]


def _spend(client: Client, org: Organisation, bank: str, amount: str = "113.00") -> Any:
    return send(
        client,
        url(org, "bank-transactions"),
        {
            "kind": "spend",
            "bank_account": bank,
            "date": "2026-06-15",
            "reference": "Staples",
            "tax_mode": "inclusive",
            "lines": [
                {
                    "account": _codes(org)["office"],
                    "amount": amount,
                    "taxes": [{"role": "itc_receivable", "amount": "13.00"}],
                }
            ],
        },
    )


def _fund(client: Client, org: Organisation, bank: str) -> None:
    with org_context(org):
        sales = Account.objects.filter(subtype="revenue").order_by("code").first()
    made = send(
        client,
        url(org, "bank-transactions"),
        {
            "kind": "receive",
            "bank_account": bank,
            "date": "2026-06-01",
            "lines": [{"account": str(sales.public_id), "amount": "1000.00"}],  # type: ignore[union-attr]
        },
    )
    assert made.status_code == 201, made.json()


def test_create_list_spend_and_balance(org: Organisation, owner: Client) -> None:
    made = send(
        owner,
        url(org, "bank-accounts"),
        {
            "type": "chequing",
            "display_name": "TD Chequing",
            "institution": "TD",
            "account_last4": "4821",
        },
    )
    assert made.status_code == 201
    bank = made.json()
    assert (bank["ledger_balance"], bank["masked_number"], bank["is_liability"]) == (
        "0.00",
        "•••• 4821",
        False,
    )
    _fund(owner, org, bank["id"])
    spent = _spend(owner, org, bank["id"])
    assert spent.status_code == 201, spent.json()
    assert (spent.json()["total"], spent.json()["subtotal"]) == ("113.00", "100.00")
    assert spent.json()["journal"]["number"]
    listed = owner.get(url(org, "bank-accounts")).json()["results"]
    assert [(r["display_name"], r["ledger_balance"], r["transaction_count"]) for r in listed] == [
        ("TD Chequing", "887.00", 2)
    ]
    assert listed[0]["last_activity"] == "2026-06-15"
    txns = owner.get(url(org, f"bank-transactions?bank_account={bank['id']}&kind=spend")).json()
    assert [t["total"] for t in txns["results"]] == ["113.00"]


def test_delete_409_archive_restore(org: Organisation, owner: Client) -> None:
    bank = send(
        owner, url(org, "bank-accounts"), {"type": "cash", "display_name": "Petty Cash"}
    ).json()
    _fund(owner, org, bank["id"])
    refused = owner.delete(url(org, f"bank-accounts/{bank['id']}"))
    assert refused.status_code == 409
    assert refused.json() == {
        "code": "banking.account.has_transactions",
        "detail": "Petty Cash has 1 transaction — archive it instead.",
        "count": 1,
    }
    archived = owner.post(url(org, f"bank-accounts/{bank['id']}/archive"))
    assert archived.status_code == 200 and archived.json()["archived_at"]
    assert owner.get(url(org, "bank-accounts")).json()["results"] == []
    assert len(owner.get(url(org, "bank-accounts?status=archived")).json()["results"]) == 1
    assert owner.post(url(org, f"bank-accounts/{bank['id']}/restore")).json()["archived_at"] is None
    empty = send(owner, url(org, "bank-accounts"), {"type": "savings", "display_name": "Spare"})
    assert owner.delete(url(org, f"bank-accounts/{empty.json()['id']}")).status_code == 204


def test_patch_rename_statement_and_currency(org: Organisation, owner: Client) -> None:
    bank = send(
        owner, url(org, "bank-accounts"), {"type": "chequing", "display_name": "Old"}
    ).json()
    renamed = send(
        owner,
        url(org, f"bank-accounts/{bank['id']}"),
        {
            "display_name": "RBC Operating",
            "statement_balance": "1200.50",
            "statement_balance_date": "2026-06-30",
            "currency": "usd",
        },
        method="patch",
    )
    assert renamed.status_code == 200, renamed.json()
    body = renamed.json()
    assert (body["display_name"], body["ledger_account"]["name"], body["statement_balance"]) == (
        "RBC Operating",
        "RBC Operating",
        "1200.50",
    )
    assert body["currency"] == "USD"
    _fund(owner, org, bank["id"])
    fixed = send(
        owner, url(org, f"bank-accounts/{bank['id']}"), {"currency": "CAD"}, method="patch"
    )
    assert (fixed.status_code, fixed.json()["code"]) == (400, "banking.account.currency_fixed")
    send(owner, url(org, "bank-accounts"), {"type": "cash", "display_name": "Taken"})
    clash = send(
        owner, url(org, f"bank-accounts/{bank['id']}"), {"display_name": "taken"}, method="patch"
    )
    assert clash.json()["code"] == "banking.account.name_taken"


def test_void_reverses(org: Organisation, owner: Client) -> None:
    bank = send(owner, url(org, "bank-accounts"), {"type": "chequing", "display_name": "TD"}).json()
    _fund(owner, org, bank["id"])
    txn = _spend(owner, org, bank["id"]).json()
    voided = send(owner, url(org, f"bank-transactions/{txn['id']}/void"), {})
    assert voided.status_code == 200 and voided.json()["status"] == "voided"
    with org_context(org):
        entry = JournalEntry.objects.get(public_id=txn["journal"]["id"])
        assert entry.status == "reversed"
    assert owner.get(url(org, f"bank-accounts/{bank['id']}")).json()["ledger_balance"] == "1000.00"
    again = send(owner, url(org, f"bank-transactions/{txn['id']}/void"), {})
    assert again.status_code == 409


def test_validation_errors(org: Organisation, owner: Client) -> None:
    bank = send(owner, url(org, "bank-accounts"), {"type": "chequing", "display_name": "TD"}).json()
    unknown = send(
        owner,
        url(org, "bank-transactions"),
        {
            "kind": "spend",
            "bank_account": bank["id"],
            "date": "2026-06-15",
            "lines": [{"account": "6ca1b880-64f7-4053-80e3-0c3618895553", "amount": "5.00"}],
        },
    )
    assert unknown.status_code == 400 and "account" in unknown.json()["lines"]["0"]
    zero = send(
        owner,
        url(org, "bank-transactions"),
        {
            "kind": "spend",
            "bank_account": bank["id"],
            "date": "2026-06-15",
            "lines": [{"account": _codes(org)["office"], "amount": "0.00"}],
        },
    )
    assert (zero.status_code, zero.json()["code"]) == (400, "banking.line.amount_positive")


def test_permissions_feature_tenancy_and_sweep(
    org: Organisation, owner: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    bank = send(owner, url(org, "bank-accounts"), {"type": "chequing", "display_name": "TD"}).json()
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=org, user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    assert (
        send(client, url(org, "bank-accounts"), {"type": "cash", "display_name": "X"}).status_code
        == 403
    )
    assert _spend(client, org, bank["id"]).status_code == 403

    other = Organisation.objects.create(name="Other Ltd.")
    stranger = User.objects.create_user("owner@other.ca", name="Other owner")
    OrganisationMember.objects.create(organisation=other, user=stranger, role="owner")
    foreign = Client()
    foreign.force_login(stranger)
    assert foreign.get(url(other, f"bank-accounts/{bank['id']}")).status_code == 404

    call_command("tenant_sweep", stdout=StringIO())
    keys = {p.key for p in catalogue}
    assert {
        "accounting.banking.view",
        "accounting.banking.manage",
        "accounting.banking.transact",
    } <= keys

    class NoPackage:
        def allows(self, organisation: Organisation | None, key: str) -> bool:
            return key != "accounting.banking.write"

    monkeypatch.setattr(catalogue_drf, "get_resolver", lambda: NoPackage())
    refused = send(owner, url(org, "bank-accounts"), {"type": "cash", "display_name": "Y"})
    assert (refused.status_code, refused.json()["feature"]) == (402, "accounting.banking.write")
