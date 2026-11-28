"""F-04-T15 — revert an auto-coded line: the journal is reversed, the line is back to Uncoded,
with an audit entry.

Acceptance (integration): after the revert the line is Uncoded (no transaction, no rule, not
auto-coded) and the general ledger nets to 0 on every account the coding touched; the audit
event ``banking.rule.reverted`` is written; the application is marked reverted and the same rule
doesn't code the line again (apply and preview agree); a draft suggestion is discarded; a line not
coded by a rule is refused; the API endpoint works and needs ``accounting.banking.transact``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum
from django.test import Client

from numo9.audit.models import AuditEvent
from numo9.banking.models import (
    BankRuleAllocation,
    BankRuleApplication,
    BankTransactionStatus,
    StatementLineStatus,
)
from numo9.banking.rules.apply import apply_rules, revert_line, uncoded_lines
from numo9.banking.rules.engine import rule_spec, rules_queryset
from numo9.banking.rules.preview import preview_rule
from numo9.banking.services import create_bank_account
from numo9.ledger.models import JournalLine
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.bank_rule_helpers import rule, statement_line
from tests.journal_helpers import people
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def setup() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    with org_context(org):
        fuel = account(org, "5901", "Fuel")
        item = rule(org, "Fuel", conditions=[("description", "contains", "petro")], auto_apply=True)
        BankRuleAllocation.objects.create(
            organisation=org,
            rule=item,
            account=fuel,
            percent=D("100"),
            tax_code="purchase.ON.standard",
        )
    return {"org": org, "bank": bank, "fuel": fuel, "rule": item}


def balances(org: Organisation, accounts: list[Any]) -> dict[str, D]:
    with org_context(org):
        rows = (
            JournalLine.objects.filter(account__in=accounts)
            .values("account__code")
            .annotate(net=Sum("debit") - Sum("credit"))
        )
        return {row["account__code"]: row["net"] for row in rows}


def test_revert_auto_coded_line_gl_nets_to_zero(setup: dict[str, Any]) -> None:
    org, bank = setup["org"], setup["bank"]
    with org_context(org):
        line = statement_line(org, bank, "-113.00", "PETRO-CANADA 12")
        apply_rules(uncoded_lines())
        line.refresh_from_db()
        txn = line.bank_transaction
        assert txn is not None and line.auto_coded and line.status == StatementLineStatus.CODED
        touched = list(
            JournalLine.objects.filter(entry=txn.journal_entry).values_list("account", flat=True)
        )
        assert balances(org, touched)[bank.gl_account.code] == D("-113.00")

        revert_line(line)
        line.refresh_from_db()
        assert (line.status, line.bank_transaction, line.applied_rule, line.auto_coded) == (
            StatementLineStatus.UNCODED,
            None,
            None,
            False,
        )
        txn.refresh_from_db()
        assert txn.status == BankTransactionStatus.VOIDED
        assert set(balances(org, touched).values()) == {D("0.00")}
        event = AuditEvent.objects.filter(action="banking.rule.reverted").get()
        assert event.meta["rule"] == str(setup["rule"].public_id)
        assert event.changes["status"] == ["coded", "uncoded"]
        assert BankRuleApplication.objects.get().reverted_at is not None

        # The reverted rule doesn't code the line again — apply and preview agree.
        assert apply_rules(uncoded_lines()).applied == []
        spec = rule_spec(rules_queryset().get(pk=setup["rule"].pk))
        assert preview_rule(spec, today=line.date).applies == 0


def test_revert_draft_and_refusals(setup: dict[str, Any]) -> None:
    org, bank = setup["org"], setup["bank"]
    with org_context(org):
        item = setup["rule"]
        item.auto_apply = False
        item.save()
        line = statement_line(org, bank, "-20.00", "PETRO")
        apply_rules(uncoded_lines())
        line.refresh_from_db()
        draft = line.bank_transaction
        assert draft is not None and draft.status == BankTransactionStatus.DRAFT
        revert_line(line)
        draft.refresh_from_db()
        assert draft.status == BankTransactionStatus.VOIDED
        other = statement_line(org, bank, "-5.00", "Coffee")
        with pytest.raises(Exception) as caught:
            revert_line(other)
        assert getattr(caught.value, "code", "") == "banking.rule.not_rule_coded"


def test_revert_endpoint(setup: dict[str, Any]) -> None:
    org, bank = setup["org"], setup["bank"]
    with org_context(org):
        line = statement_line(org, bank, "-40.00", "PETRO")
        apply_rules(uncoded_lines())
    client = Client()
    client.force_login(people(org)["owner"])
    url = f"/api/v1/o/{org.public_id}/bank-rules/lines/{line.public_id}/revert"
    done = client.post(url, {}, content_type="application/json")
    assert done.status_code == 200, done.json()
    assert done.json() == {
        "line": str(line.public_id),
        "status": "uncoded",
        "auto_coded": False,
        "applied_rule": None,
    }
    again = client.post(url, {}, content_type="application/json")
    assert (again.status_code, again.json()["code"]) == (400, "banking.rule.not_rule_coded")
