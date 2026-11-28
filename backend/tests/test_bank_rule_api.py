"""F-04-T09 — bank rules API: CRUD, atomic reorder, preview, apply and confirm; permissions and
feature key.

Acceptance: a reorder of 50 rules is atomic (all renumbered, or — with a wrong list — none);
the router sweep passes; ``permission_check`` passes and the catalogue lists
``accounting.banking.rules``; an employee gets 403, a package without ``accounting.banking.write``
402, another organisation 404; a malicious regex is refused with 400 ``banking.rule.regex_slow``;
deleting closes the priority gap; the preview counts what apply then codes.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from numo9.accounts.models import User
from numo9.banking.models import BankRule
from numo9.banking.services import create_bank_account
from numo9.banking.transactions import MoneyLine, MoneySpec, record_bank_transaction
from numo9.catalogue import drf as catalogue_drf
from numo9.ledger.template import load_template
from numo9.rbac.catalogue import catalogue
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.bank_rule_helpers import rule, statement_line
from tests.journal_helpers import people
from tests.ledger_helpers import account

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


@pytest.fixture
def fuel(org: Organisation) -> Any:
    with org_context(org):
        return account(org, "5901", "Fuel")


def url(org: Organisation, suffix: str) -> str:
    return f"/api/v1/o/{org.public_id}/{suffix}"


def send(client: Client, path: str, payload: Any, method: str = "post") -> Any:
    return getattr(client, method)(path, payload, content_type="application/json")


def payload(fuel: Any, **changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "spend",
        "name": "Petro-Canada fuel",
        "match_mode": "all",
        "conditions": [
            {"field": "description", "operator": "contains", "value": "PETRO"},
            {"field": "amount", "operator": "between", "value": "20", "value_to": "200"},
        ],
        "allocations": [
            {"account": str(fuel.public_id), "percent": "100", "tax_code": "purchase.ON.standard"}
        ],
        "reference_template": "{payee}",
    }
    body.update(changes)
    return body


def test_crud_toggle_delete(org: Organisation, owner: Client, fuel: Any) -> None:
    made = send(owner, url(org, "bank-rules"), payload(fuel))
    assert made.status_code == 201, made.json()
    body = made.json()
    assert (body["priority"], body["auto_apply"], body["active"]) == (1, False, True)
    assert body["allocations"][0]["percent"] == "100"
    assert body["conditions"][1] == {
        "field": "amount",
        "operator": "between",
        "value": "20",
        "value_to": "200",
    }
    second = send(owner, url(org, "bank-rules"), payload(fuel, name="Shell"))
    assert second.json()["priority"] == 2
    toggled = send(owner, url(org, f"bank-rules/{body['id']}"), {"active": False}, "patch")
    assert toggled.status_code == 200, toggled.json()
    assert (toggled.json()["active"], toggled.json()["name"]) == (False, "Petro-Canada fuel")
    listed = owner.get(url(org, "bank-rules?search=shell")).json()["results"]
    assert [r["name"] for r in listed] == ["Shell"]
    retyped = send(owner, url(org, f"bank-rules/{body['id']}"), {"type": "receive"}, "patch")
    assert retyped.json()["code"] == "banking.rule.type_fixed"
    assert owner.delete(url(org, f"bank-rules/{body['id']}")).status_code == 204
    remaining = owner.get(url(org, "bank-rules")).json()["results"]
    assert [(r["name"], r["priority"]) for r in remaining] == [("Shell", 1)]


@pytest.mark.parametrize(
    ("changes", "code", "field"),
    [
        (
            {"conditions": [{"field": "description", "operator": "regex", "value": "(a|aa)+$"}]},
            "banking.rule.regex_slow",
            "conditions.0",
        ),
        ({"conditions": []}, "banking.rule.conditions_required", "conditions"),
        ({"allocations": []}, "banking.rule.allocations_required", "allocations"),
        ("percent", "banking.rule.percent_total", "allocations"),
        ("sales_code", "banking.rule.tax_code_side", "allocations.0.tax_code"),
        ({"contact_strategy": "fixed"}, "banking.rule.contact_required", "contact"),
        ({"type": "transfer"}, "banking.rule.transfer_account_required", "transfer_account"),
    ],
)
def test_refusals(
    org: Organisation, owner: Client, fuel: Any, changes: Any, code: str, field: str
) -> None:
    if changes == "percent":
        changes = {
            "allocations": [
                {"account": str(fuel.public_id), "percent": "60"},
                {"account": str(fuel.public_id), "percent": "30"},
            ]
        }
    elif changes == "sales_code":
        changes = {
            "allocations": [
                {"account": str(fuel.public_id), "percent": "100", "tax_code": "sales.ON.standard"}
            ]
        }
    refused = send(owner, url(org, "bank-rules"), payload(fuel, **changes))
    assert refused.status_code == 400
    assert (refused.json()["code"], refused.json()["field"]) == (code, field)
    assert not BankRule._base_manager.exists()


def test_reorder_50_rules_atomic(org: Organisation, owner: Client) -> None:
    with org_context(org):
        rules = [
            rule(org, f"Rule {n:02d}", conditions=[("payee", "contains", f"p{n}")])
            for n in range(50)
        ]
        rule(org, "Interest", type="receive", conditions=[("payee", "contains", "bank")])
    ids = [str(r.public_id) for r in reversed(rules)]
    done = send(owner, url(org, "bank-rules/reorder"), {"type": "spend", "order": ids})
    assert done.status_code == 200, done.json()
    assert [r["id"] for r in done.json()["results"]] == ids
    assert [r["priority"] for r in done.json()["results"]] == list(range(1, 51))
    with org_context(org):
        assert BankRule.objects.get(type="receive").priority == 1
    # A wrong list (one missing) changes nothing.
    wrong = send(owner, url(org, "bank-rules/reorder"), {"type": "spend", "order": ids[1:][::-1]})
    assert (wrong.status_code, wrong.json()["code"]) == (400, "banking.rule.reorder_mismatch")
    listed = owner.get(url(org, "bank-rules?type=spend")).json()["results"]
    assert [r["id"] for r in listed] == ids


def test_preview_apply_confirm(org: Organisation, owner: Client, fuel: Any) -> None:
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    today = timezone.localdate()
    with org_context(org):
        sales = account(org, "4901", "Sales", subtype="revenue")
        record_bank_transaction(
            MoneySpec(
                "receive",
                bank,
                today - dt.timedelta(days=200),
                [MoneyLine(sales, Decimal("1000.00"))],
            )
        )
        statement_line(org, bank, "-45.00", "PETRO-CANADA 12", payee="Petro", date=today)
        statement_line(org, bank, "-300.00", "PETRO big", date=today)
        statement_line(org, bank, "-45.00", "PETRO old", date=today - dt.timedelta(days=120))
    unfinished = payload(fuel, name="", allocations=[])
    preview = send(owner, url(org, "bank-rules/preview"), {"rule": unfinished})
    assert preview.status_code == 200, preview.json()
    body = preview.json()
    assert (body["days"], body["applies"], body["shadowed"]) == (90, 1, 0)
    assert body["rows"][0]["line"]["description"] == "PETRO-CANADA 12"
    slow = {"field": "description", "operator": "regex", "value": "(a|aa)+$"}
    refused = send(
        owner, url(org, "bank-rules/preview"), {"rule": payload(fuel, conditions=[slow])}
    )
    assert (refused.status_code, refused.json()["code"]) == (400, "banking.rule.regex_slow")
    made = send(owner, url(org, "bank-rules"), payload(fuel)).json()
    wider = send(
        owner,
        url(org, "bank-rules/preview"),
        {"rule": payload(fuel, name="Second"), "days": 365},
    ).json()
    assert [(r["outcome"], r["shadowed_by"]["name"]) for r in wider["rows"]] == [
        ("shadowed", "Petro-Canada fuel"),
        ("shadowed", "Petro-Canada fuel"),
    ]
    applied = send(owner, url(org, "bank-rules/apply"), {}).json()
    assert [(a["rule"]["id"], a["status"]) for a in applied["applied"]] == [
        (made["id"], "draft"),
        (made["id"], "draft"),
    ]
    line = applied["applied"][-1]["line"]
    confirmed = send(owner, url(org, f"bank-rules/lines/{line}/confirm"), {})
    assert confirmed.status_code == 200, confirmed.json()
    again = send(owner, url(org, f"bank-rules/lines/{line}/confirm"), {})
    assert again.json()["code"] == "banking.rule.no_draft"
    assert owner.get(url(org, f"bank-rules/{made['id']}")).json()["applied_count"] == 2


def test_permissions_feature_isolation_sweep(
    org: Organisation, owner: Client, fuel: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = send(owner, url(org, "bank-rules"), payload(fuel)).json()
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=org, user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    assert send(client, url(org, "bank-rules"), payload(fuel)).status_code == 403
    assert (
        send(client, url(org, "bank-rules/reorder"), {"type": "spend", "order": []}).status_code
        == 403
    )

    other = Organisation.objects.create(name="Other Ltd.")
    stranger = User.objects.create_user("owner@other.ca", name="Other owner")
    OrganisationMember.objects.create(organisation=other, user=stranger, role="owner")
    foreign = Client()
    foreign.force_login(stranger)
    assert foreign.get(url(other, f"bank-rules/{made['id']}")).status_code == 404

    out = StringIO()
    call_command("tenant_sweep", stdout=out)
    assert "bank-rules" in out.getvalue()
    call_command("permission_check", "--quiet", stdout=StringIO())
    assert "accounting.banking.rules" in {p.key for p in catalogue}

    class NoPackage:
        def allows(self, organisation: Organisation | None, key: str) -> bool:
            return key != "accounting.banking.write"

    monkeypatch.setattr(catalogue_drf, "get_resolver", lambda: NoPackage())
    blocked = send(owner, url(org, "bank-rules"), payload(fuel))
    assert (blocked.status_code, blocked.json()["feature"]) == (402, "accounting.banking.write")
    assert owner.get(url(org, "bank-rules")).status_code == 200
