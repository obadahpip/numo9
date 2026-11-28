"""F-04-T03 — ``BankRuleAllocation`` (account, tax code, description, fixed amount **or**
percentage, order) and the validator.

Acceptance: percentages total 100 % when present — 60 % + 30 % is refused, fixed 10.00 + 100 %
is accepted; a line with both or neither of amount and percentage, or with a non-positive value,
is refused (validator and database check); the table has row-level security.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from numo9.banking.models import BankRuleAllocation
from numo9.banking.rules.allocation import Share, validate_allocations
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.bank_rule_helpers import rule
from tests.ledger_helpers import account

D = Decimal


def test_60_plus_30_percent_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        validate_allocations([Share(percent=D("60")), Share(percent=D("30"))])
    assert caught.value.code == "banking.rule.percent_total"
    assert "90 %" in caught.value.messages[0]


@pytest.mark.parametrize(
    "shares",
    [
        [Share(fixed_amount=D("10.00")), Share(percent=D("100"))],
        [Share(percent=D("33.3333")), Share(percent=D("33.3333")), Share(percent=D("33.3334"))],
        [Share(fixed_amount=D("25.00"))],
        [Share(percent=D("100"))],
    ],
)
def test_accepted(shares: list[Share]) -> None:
    validate_allocations(shares)


@pytest.mark.parametrize(
    ("shares", "code"),
    [
        ([], "banking.rule.allocations_required"),
        ([Share(fixed_amount=D("10"), percent=D("100"))], "banking.rule.allocation_kind"),
        ([Share()], "banking.rule.allocation_kind"),
        ([Share(fixed_amount=D("0"))], "banking.rule.allocation_amount"),
        ([Share(percent=D("0")), Share(percent=D("100"))], "banking.rule.allocation_percent"),
        ([Share(percent=D("101"))], "banking.rule.allocation_percent"),
        ([Share(fixed_amount=D("5")), Share(percent=D("50"))], "banking.rule.percent_total"),
    ],
)
def test_refused(shares: list[Share], code: str) -> None:
    with pytest.raises(ValidationError) as caught:
        validate_allocations(shares)
    assert caught.value.code == code


@pytest.mark.django_db
def test_table_has_row_level_security() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            ["banking_bankruleallocation"],
        )
        assert cursor.fetchone() == (True, True)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fixed", "percent"),
    [(D("10.00"), D("50")), (None, None), (D("-1.00"), None), (None, D("120"))],
)
def test_database_check(fixed: Decimal | None, percent: Decimal | None) -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        item = rule(org, "Fuel", conditions=[("payee", "equals", "Shell")])
        fuel = account(org, "5100", "Fuel")
        made = BankRuleAllocation.objects.create(
            organisation=org,
            rule=item,
            account=fuel,
            percent=D("100"),
            tax_code="purchase.ON.standard",
        )
        assert [Share.of(a).percent for a in item.allocations.all()] == [D("100")]
        with pytest.raises(IntegrityError), transaction.atomic():
            BankRuleAllocation.objects.filter(pk=made.pk).update(
                fixed_amount=fixed, percent=percent
            )
