"""F-04-T02 — ``BankRule`` (type, name, match mode, priority, scope accounts, contact strategy,
contact, reference template, auto-apply off by default, active) and ``BankRuleCondition`` (field,
operator, value, value_to); statement lines carry the rule fields (bank transaction, applied rule,
auto-coded).

Acceptance: the migration applies with row-level security; the priority is unique per
organisation and type — **deferred**, so two rules can swap numbers inside one transaction while a
clash left at commit is refused; the same number is fine for another type or organisation; unknown
values and a "set this contact" rule without a contact are refused.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from numo9.banking.models import (
    BankRule,
    BankRuleCondition,
    BankRuleType,
    ContactStrategy,
    MatchMode,
    StatementLineStatus,
)
from numo9.banking.services import create_bank_account
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.bank_rule_helpers import rule, statement_line

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.mark.parametrize("table", ["banking_bankrule", "banking_bankrulecondition"])
def test_tables_have_row_level_security(table: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s", [table]
        )
        assert cursor.fetchone() == (True, True)


def test_defaults_conditions_and_scope(org: Organisation) -> None:
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    with org_context(org):
        item = rule(
            org,
            "Petro-Canada fuel",
            conditions=[("description", "contains", "PETRO"), ("amount", "between", "20", "200")],
        )
        item.scope_accounts.add(bank)
        assert (item.match_mode, item.contact_strategy) == (MatchMode.ALL, ContactStrategy.NONE)
        assert (item.auto_apply, item.active, item.priority) == (False, True, 1)
        assert [c.operator for c in item.conditions.all()] == ["contains", "between"]
        assert list(item.scope_accounts.all()) == [bank]
        line = statement_line(org, bank, "-45.00", "PETRO-CANADA 1234")
        assert (line.status, line.applied_rule, line.auto_coded) == (
            StatementLineStatus.UNCODED,
            None,
            False,
        )
        line.applied_rule = item
        line.save()
        assert list(item.coded_lines.all()) == [line]


def test_priority_unique_per_org_and_type_deferred(org: Organisation) -> None:
    with org_context(org):
        first = rule(org, "Fuel")
        second = rule(org, "Coffee")
        assert (first.priority, second.priority) == (1, 2)
        # Same number for another type is fine.
        assert rule(org, "Interest", type=BankRuleType.RECEIVE, priority=1).pk
        # Swapping inside one transaction: the check runs at commit (deferred).
        with transaction.atomic():
            BankRule.objects.filter(pk=first.pk).update(priority=2)
            BankRule.objects.filter(pk=second.pk).update(priority=1)
        first.refresh_from_db()
        assert first.priority == 2
        # A clash still there at commit is refused.
        with pytest.raises(IntegrityError), transaction.atomic():
            BankRule.objects.filter(pk=first.pk).update(priority=1)
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        # A deleted rule gives its number up (null priorities never clash).
        BankRule.objects.filter(pk=first.pk).update(priority=None)
        assert rule(org, "Again", priority=2).pk
    other = Organisation.objects.create(name="Other Ltd.")
    with org_context(other):
        assert rule(other, "Fuel", priority=1).pk


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        ("rule", "type", "refund"),
        ("rule", "match_mode", "one"),
        ("rule", "contact_strategy", "fixed"),  # "set this contact" needs a contact
        ("rule", "name", ""),
        ("condition", "field", "memo"),
        ("condition", "operator", "sounds_like"),
    ],
)
def test_invalid_values_refused(org: Organisation, model: str, field: str, value: str) -> None:
    with org_context(org):
        item = rule(org, "Fuel", conditions=[("payee", "equals", "Shell")])
        with pytest.raises(IntegrityError), transaction.atomic():
            if model == "rule":
                BankRule.objects.filter(pk=item.pk).update(**{field: value})
            else:
                BankRuleCondition.objects.filter(rule=item).update(**{field: value})


def test_amount_condition_keeps_its_bounds(org: Organisation) -> None:
    with org_context(org):
        item = rule(org, "Range", conditions=[("amount", "between", "20", "200")])
        condition = item.conditions.get()
        assert (Decimal(condition.value), Decimal(condition.value_to)) == (
            Decimal("20"),
            Decimal("200"),
        )
