"""F-04-T05 — priority engine: ordered evaluation, first match wins; the winner plus the shadowed
matches.

Acceptance: two matching rules → priority 1 applied, rule 2 reported shadowed; types follow the
sign of the line (spend = money out, receive = money in, transfer either); scope limits a rule to
its bank accounts; inactive, deleted and disabled rules (archived account) are not evaluated.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.banking.models import BankRuleAllocation
from numo9.banking.rules.conditions import Condition, LineFacts
from numo9.banking.rules.engine import RuleSpec, choose, load_rules, rule_warnings
from numo9.banking.services import create_bank_account
from numo9.ledger.models import AccountStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.bank_rule_helpers import rule
from tests.ledger_helpers import account

PETRO = (Condition("description", "contains", "petro"),)
FUEL_LINE = LineFacts(amount=Decimal("-45.00"), description="PETRO-CANADA 1234", bank_account_id=1)


def spec(name: str, priority: int, type: str = "spend", **fields: object) -> RuleSpec:
    return RuleSpec(name=name, type=type, priority=priority, conditions=PETRO, **fields)  # type: ignore[arg-type]


def test_two_matching_rules_priority_one_wins_two_shadowed() -> None:
    outcome = choose([spec("Second", 2), spec("First", 1)], FUEL_LINE)
    assert outcome.winner is not None and outcome.winner.name == "First"
    assert [r.name for r in outcome.shadowed] == ["Second"]


def test_no_match() -> None:
    assert (
        choose([spec("Fuel", 1)], LineFacts(amount=Decimal("-5"), description="Coffee")).winner
        is None
    )


@pytest.mark.parametrize(
    ("type", "amount", "codes"),
    [
        ("spend", "-45.00", True),
        ("spend", "45.00", False),
        ("receive", "45.00", True),
        ("receive", "-45.00", False),
        ("transfer", "-45.00", True),
        ("transfer", "45.00", True),
        ("spend", "0.00", False),
    ],
)
def test_type_follows_sign(type: str, amount: str, codes: bool) -> None:
    line = LineFacts(amount=Decimal(amount), description="PETRO", bank_account_id=1)
    assert (choose([spec("R", 1, type)], line).winner is not None) is codes


def test_scope_and_type_order() -> None:
    scoped = spec("Savings only", 1, scope=frozenset({2}))
    transfer = spec("Transfer", 1, "transfer")
    spend = spec("Spend", 1)
    outcome = choose([scoped, transfer, spend], FUEL_LINE)
    assert outcome.winner == spend
    assert outcome.shadowed == (transfer,)


@pytest.mark.django_db
def test_load_rules_skips_inactive_deleted_and_disabled() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    with org_context(org):
        fuel = account(org, "5100", "Fuel")
        old = account(org, "5200", "Old fuel")
        first = rule(org, "First", conditions=[("description", "contains", "petro")])
        rule(org, "Off", conditions=[("description", "contains", "petro")], active=False)
        gone = rule(org, "Gone", conditions=[("description", "contains", "petro")])
        gone.priority = None
        gone.soft_delete()
        disabled = rule(org, "Disabled", conditions=[("description", "contains", "petro")])
        for item, target in ((first, fuel), (disabled, old)):
            BankRuleAllocation.objects.create(
                organisation=org, rule=item, account=target, percent=Decimal("100")
            )
        old.status = AccountStatus.ARCHIVED
        old.save()
        disabled.refresh_from_db()
        assert rule_warnings(disabled) == ["archived_account"]
        rules = load_rules()
        assert [r.name for r in rules] == ["First"]
        line = LineFacts(amount=Decimal("-45"), description="Petro", bank_account_id=bank.pk)
        assert choose(rules, line).winner == rules[0]
        assert rules[0].model == first
