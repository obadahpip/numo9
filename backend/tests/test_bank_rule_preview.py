"""F-04-T08 — history preview: runs a rule against the last N days (default 90) of statement
lines without writing; returns the matches and the conflicts.

Acceptance (integration): the preview count equals the actual apply count on the same data;
nothing is written by the preview; a line won by a higher-priority rule is reported shadowed with
that rule; lines the winner shadows are listed as conflicts; lines older than the window, coded,
matched or locked are left out; an unsaved rule can be previewed.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.banking.models import BankRuleAllocation, BankRuleApplication, StatementLineStatus
from numo9.banking.rules.apply import apply_rules, uncoded_lines
from numo9.banking.rules.conditions import Condition
from numo9.banking.rules.engine import RuleSpec, rule_spec, rules_queryset
from numo9.banking.rules.preview import preview_rule
from numo9.banking.services import create_bank_account
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.bank_rule_helpers import rule, statement_line
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
D = Decimal
TODAY = dt.date(2026, 6, 30)


@pytest.fixture
def setup() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    with org_context(org):
        fuel = account(org, "5901", "Fuel")
        big = rule(
            org,
            "Big fuel",
            conditions=[("description", "contains", "petro"), ("amount", "gt", "100")],
        )
        any_fuel = rule(org, "Any fuel", conditions=[("description", "regex", r"petro|shell")])
        later = rule(org, "Fuel not Shell", conditions=[("description", "not_contains", "shell")])
        for item in (big, any_fuel, later):
            BankRuleAllocation.objects.create(
                organisation=org, rule=item, account=fuel, percent=D("100")
            )
        day = dt.date(2026, 6, 10)
        statement_line(org, bank, "-150.00", "PETRO-CANADA", date=day)  # big wins
        statement_line(org, bank, "-40.00", "Petro-Canada", date=day)  # any_fuel wins over later
        statement_line(org, bank, "-35.00", "SHELL 22", date=day)  # any_fuel
        statement_line(org, bank, "-20.00", "PETRO old", date=dt.date(2026, 3, 1))  # too old
        statement_line(org, bank, "-20.00", "PETRO", date=day, status=StatementLineStatus.MATCHED)
    return {"org": org, "bank": bank, "big": big, "any": any_fuel, "later": later}


def spec_of(item: Any) -> RuleSpec:
    return rule_spec(rules_queryset().get(pk=item.pk))


def test_preview_count_equals_apply_count(setup: dict[str, Any]) -> None:
    org = setup["org"]
    with org_context(org):
        preview = preview_rule(spec_of(setup["any"]), today=TODAY)
        assert (preview.applies, preview.shadowed, preview.days) == (2, 1, 90)
        shadowed = next(row for row in preview.rows if row.outcome == "shadowed")
        assert shadowed.shadowed_by is not None and shadowed.shadowed_by.name == "Big fuel"
        conflicts = {
            row.line.description: [r.name for r in row.also_matches]
            for row in preview.rows
            if row.outcome == "applies"
        }
        assert conflicts == {"Petro-Canada": ["Fuel not Shell"], "SHELL 22": []}
        # Nothing written.
        assert not BankRuleApplication.objects.exists()
        assert all(line.bank_transaction_id is None for line in uncoded_lines())

        result = apply_rules(uncoded_lines().filter(date__gte=preview.since))
        applied_by_rule = [r.pk for _l, r, _t in result.applied]
        assert applied_by_rule.count(setup["any"].pk) == preview.applies
        assert applied_by_rule.count(setup["big"].pk) == 1


def test_window_and_unsaved_rule(setup: dict[str, Any]) -> None:
    org = setup["org"]
    with org_context(org):
        draft = RuleSpec(
            name="New",
            type="spend",
            priority=1,
            conditions=(Condition("description", "contains", "petro"),),
        )
        short = preview_rule(draft, today=TODAY, days=10)
        assert [row.line.description for row in short.rows] == []
        wide = preview_rule(draft, today=TODAY, days=365)
        # The unsaved rule shares priority 1 with "Big fuel": the saved one is evaluated first.
        assert sorted((row.line.description, row.outcome) for row in wide.rows) == [
            ("PETRO old", "applies"),
            ("PETRO-CANADA", "shadowed"),
            ("Petro-Canada", "applies"),
        ]
