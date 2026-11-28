"""F-06-T06 — transfers API ``/api/v1/o/<org>/bank-transfers``: create, list (either side), read,
presets, void; permission ``accounting.banking.transfer``; feature ``accounting.banking.write``.

Acceptance: the router/tenant sweep passes with the new endpoints. Also: an owner funds petty
cash from chequing (201, both balances move, one journal); a transfer that would take the
from-account below zero meets the cash guard (409); same account → 400
``banking.transfer.same_account``; voiding twice → 409; an employee gets 403; without the
package feature 402; another organisation's transfer is 404; presets pre-fill by type.
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


def send(client: Client, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, payload, content_type="application/json")


def _accounts(org: Organisation, owner: Client) -> dict[str, str]:
    made = {
        name: send(owner, url(org, "bank-accounts"), {"type": kind, "display_name": label}).json()[
            "id"
        ]
        for name, kind, label in [
            ("chequing", "chequing", "TD Chequing"),
            ("petty", "cash", "Petty Cash Float"),
            ("visa", "credit_card", "TD Visa"),
        ]
    }
    with org_context(org):
        sales = Account.objects.filter(subtype="revenue").order_by("code").first()
    assert sales is not None
    funded = send(
        owner,
        url(org, "bank-transactions"),
        {
            "kind": "receive",
            "bank_account": made["chequing"],
            "date": "2026-06-01",
            "tax_mode": "no_tax",
            "lines": [{"account": str(sales.public_id), "amount": "5000.00"}],
        },
    )
    assert funded.status_code == 201, funded.json()
    return made


def _balance(owner: Client, org: Organisation, bank: str) -> str:
    return str(owner.get(url(org, f"bank-accounts/{bank}")).json()["ledger_balance"])


def _transfer(owner: Client, org: Organisation, source: str, target: str, amount: str) -> Any:
    return send(
        owner,
        url(org, "bank-transfers"),
        {
            "from_account": source,
            "to_account": target,
            "date": "2026-06-03",
            "amount": amount,
            "reference": "Float",
        },
    )


def test_fund_petty_cash_list_read_void(org: Organisation, owner: Client) -> None:
    banks = _accounts(org, owner)
    created = _transfer(owner, org, banks["chequing"], banks["petty"], "1000.00")
    assert created.status_code == 201, created.json()
    body = created.json()
    assert (body["amount"], body["status"], body["from_account"]["name"]) == (
        "1000.00",
        "posted",
        "TD Chequing",
    )
    assert body["journal"]["number"]
    assert _balance(owner, org, banks["chequing"]) == "4000.00"
    assert _balance(owner, org, banks["petty"]) == "1000.00"
    for side in ("chequing", "petty"):
        listed = owner.get(url(org, f"bank-transfers?bank_account={banks[side]}")).json()
        assert [t["id"] for t in listed["results"]] == [body["id"]]
    assert owner.get(url(org, f"bank-transfers?bank_account={banks['visa']}")).json() == {
        "results": []
    }
    assert owner.get(url(org, f"bank-transfers/{body['id']}")).json()["id"] == body["id"]
    voided = send(owner, url(org, f"bank-transfers/{body['id']}/void"), {})
    assert (voided.status_code, voided.json()["status"]) == (200, "voided")
    assert _balance(owner, org, banks["petty"]) == "0.00"
    again = send(owner, url(org, f"bank-transfers/{body['id']}/void"), {})
    assert (again.status_code, again.json()["code"]) == (409, "banking.transfer.voided")


def test_refusals(org: Organisation, owner: Client) -> None:
    banks = _accounts(org, owner)
    same = _transfer(owner, org, banks["chequing"], banks["chequing"], "10.00")
    assert (same.status_code, same.json()["code"]) == (400, "banking.transfer.same_account")
    negative = _transfer(owner, org, banks["petty"], banks["chequing"], "10.00")
    assert negative.status_code == 409
    assert "Petty Cash Float would be −10.00" in negative.json()["detail"]
    unknown = _transfer(owner, org, banks["chequing"], "6ca1b880-64f7-4053-80e3-0c3618895553", "1")
    assert unknown.status_code == 400 and "to_account" in unknown.json()
    with org_context(org):
        assert JournalEntry.objects.filter(type="transfer").count() == 0


def test_presets(org: Organisation, owner: Client) -> None:
    _accounts(org, owner)
    presets = owner.get(url(org, "bank-transfers/presets")).json()["results"]
    shown = {p["key"]: (p["from_account"]["name"], p["to_account"]["name"]) for p in presets}
    assert shown == {
        "fund_petty_cash": ("TD Chequing", "Petty Cash Float"),
        "pay_credit_card": ("TD Chequing", "TD Visa"),
    }


def test_permissions_feature_tenancy_and_sweep(
    org: Organisation, owner: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    banks = _accounts(org, owner)
    made = _transfer(owner, org, banks["chequing"], banks["petty"], "50.00").json()
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=org, user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    assert _transfer(client, org, banks["chequing"], banks["petty"], "5.00").status_code == 403

    other = Organisation.objects.create(name="Other Ltd.")
    stranger = User.objects.create_user("owner@other.ca", name="Other owner")
    OrganisationMember.objects.create(organisation=other, user=stranger, role="owner")
    foreign = Client()
    foreign.force_login(stranger)
    assert foreign.get(url(other, f"bank-transfers/{made['id']}")).status_code == 404

    call_command("tenant_sweep", stdout=StringIO())
    assert "accounting.banking.transfer" in {p.key for p in catalogue}

    class NoPackage:
        def allows(self, organisation: Organisation | None, key: str) -> bool:
            return key != "accounting.banking.write"

    monkeypatch.setattr(catalogue_drf, "get_resolver", lambda: NoPackage())
    refused = _transfer(owner, org, banks["chequing"], banks["petty"], "5.00")
    assert (refused.status_code, refused.json()["feature"]) == (402, "accounting.banking.write")
