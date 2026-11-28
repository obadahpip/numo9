"""gap-28 (F-04-T16) — bank rules better than Xero, end to end on the API: regex,
does-not-contain and amount-range conditions; explicit priority (first match wins, reorder
changes the winner); the history preview shows the affected lines and the shadowing rule, and
counts what apply then codes. Audit hooks: rule create / conditions change / reorder / delete /
apply each leave an audit event.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.banking.models import StatementLine
from numo9.banking.services import create_bank_account
from numo9.banking.transactions import MoneyLine, MoneySpec, record_bank_transaction
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.bank_rule_helpers import statement_line
from tests.journal_helpers import people
from tests.ledger_helpers import account

pytestmark = [pytest.mark.django_db, pytest.mark.gap("gap-28")]


def send(client: Client, path: str, body: Any) -> Any:
    return client.post(path, body, content_type="application/json")


def test_gap_28_regex_not_contains_range_priority_preview() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    today = timezone.localdate()
    with org_context(org):
        fuel = account(org, "5901", "Fuel")
        fleet = account(org, "5902", "Fleet")
        sales = account(org, "4901", "Sales", subtype="revenue")
        record_bank_transaction(
            MoneySpec(
                "receive", bank, today - dt.timedelta(days=200), [MoneyLine(sales, Decimal("5000"))]
            )
        )
        lines = {
            "fuel": statement_line(org, bank, "-45.00", "POS PETRO-CANADA 12", date=today),
            "wash": statement_line(org, bank, "-25.00", "PETRO-CANADA 12 CAR WASH", date=today),
            "big": statement_line(org, bank, "-450.00", "PETRO-CANADA 77", date=today),
            "fleet": statement_line(org, bank, "-60.00", "PETRO-CANADA 31 FLEET", date=today),
        }
    client = Client()
    client.force_login(people(org)["owner"])
    base = f"/api/v1/o/{org.public_id}/bank-rules"

    def rule_body(name: str, conditions: list[dict[str, str]], target: Any) -> dict[str, Any]:
        return {
            "type": "spend",
            "name": name,
            "conditions": conditions,
            "allocations": [{"account": str(target.public_id), "percent": "100"}],
            "auto_apply": True,
        }

    fuel_rule = rule_body(
        "Fuel — not car wash",
        [
            {"field": "description", "operator": "regex", "value": r"petro.?canada\s+\d+"},
            {"field": "description", "operator": "not_contains", "value": "car wash"},
            {"field": "amount", "operator": "between", "value": "20", "value_to": "200"},
        ],
        fuel,
    )
    made_fuel = send(client, base, fuel_rule)
    assert made_fuel.status_code == 201, made_fuel.json()
    made_fleet = send(
        client,
        base,
        rule_body(
            "Fleet cards", [{"field": "any_text", "operator": "contains", "value": "fleet"}], fleet
        ),
    )
    assert made_fleet.status_code == 201, made_fleet.json()
    fuel_id, fleet_id = made_fuel.json()["id"], made_fleet.json()["id"]

    # Fleet cards is priority 2: on the fleet line, fuel wins and shadows it.
    preview = send(
        client,
        f"{base}/preview",
        {
            "rule": rule_body(
                "Fleet cards",
                [{"field": "any_text", "operator": "contains", "value": "fleet"}],
                fleet,
            ),
            "id": fleet_id,
        },
    ).json()
    assert [
        (r["line"]["description"], r["outcome"], r["shadowed_by"]["name"]) for r in preview["rows"]
    ] == [("PETRO-CANADA 31 FLEET", "shadowed", "Fuel — not car wash")]
    # Explicit priority: move Fleet cards first — now it wins that line.
    reordered = send(client, f"{base}/reorder", {"type": "spend", "order": [fleet_id, fuel_id]})
    assert [r["name"] for r in reordered.json()["results"]] == [
        "Fleet cards",
        "Fuel — not car wash",
    ]
    preview = send(client, f"{base}/preview", {"rule": fuel_rule, "id": fuel_id}).json()
    by_line = {r["line"]["description"]: r for r in preview["rows"]}
    # Regex + not-contains + range: the car wash (not-contains) and the 450.00 (range) are out.
    assert set(by_line) == {"POS PETRO-CANADA 12", "PETRO-CANADA 31 FLEET"}
    assert by_line["POS PETRO-CANADA 12"]["outcome"] == "applies"
    assert by_line["PETRO-CANADA 31 FLEET"]["shadowed_by"]["name"] == "Fleet cards"

    applied = send(client, f"{base}/apply", {}).json()["applied"]
    by_rule: dict[str, list[str]] = {}
    for item in applied:
        by_rule.setdefault(item["rule"]["name"], []).append(item["line"])
    assert len(by_rule["Fuel — not car wash"]) == preview["applies"] == 1
    assert by_rule["Fleet cards"] == [str(lines["fleet"].public_id)]
    with org_context(org):
        assert StatementLine.objects.get(pk=lines["wash"].pk).applied_rule is None
        assert StatementLine.objects.get(pk=lines["big"].pk).applied_rule is None

    # Audit hooks.
    changed = dict(fuel_rule, conditions=fuel_rule["conditions"][:1])
    assert (
        client.patch(f"{base}/{fuel_id}", changed, content_type="application/json").status_code
        == 200
    )
    assert client.delete(f"{base}/{fleet_id}").status_code == 204
    with org_context(org):
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        conditions = AuditEvent.objects.get(action="banking.bankrule.conditions_changed")
    assert {
        "banking.bankrule.created",
        "banking.bankrule.conditions_changed",
        "banking.bankrule.deleted",
        "banking.rule.reordered",
        "banking.rule.applied",
    } <= actions
    assert conditions.changes["conditions"][1] == [r"description regex petro.?canada\s+\d+"]
