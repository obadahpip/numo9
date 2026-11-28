"""Shared helpers for the bank-rule tests (F-04): statement lines are created directly (the F-02
import is built on another branch), rules through the model."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from numo9.banking.models import (
    BankAccount,
    BankRule,
    BankRuleCondition,
    StatementLine,
)
from numo9.tenancy.models import Organisation


def statement_line(
    organisation: Organisation,
    bank: BankAccount,
    amount: str | Decimal,
    description: str = "",
    *,
    payee: str = "",
    reference: str = "",
    date: dt.date = dt.date(2026, 6, 15),
    **fields: Any,
) -> StatementLine:
    line: StatementLine = StatementLine.objects.create(
        organisation=organisation,
        bank_account=bank,
        date=date,
        amount=Decimal(str(amount)),
        description=description,
        payee=payee,
        reference=reference,
        fingerprint=uuid.uuid4().hex,
        **fields,
    )
    return line


def rule(
    organisation: Organisation,
    name: str,
    *,
    type: str = "spend",
    priority: int | None = None,
    conditions: Sequence[tuple[str, ...]] = (),
    **fields: Any,
) -> BankRule:
    """A rule with its conditions (``(field, operator, value[, value_to])``); the priority is the
    next free one of its type unless given."""
    if priority is None:
        last = (
            BankRule.objects.filter(type=type, priority__isnull=False)
            .order_by("-priority")
            .values_list("priority", flat=True)
            .first()
        )
        priority = (last or 0) + 1
    item = BankRule(organisation=organisation, name=name, type=type, priority=priority, **fields)
    item.save()
    for order, condition in enumerate(conditions):
        field, operator, value, *rest = condition
        BankRuleCondition.objects.create(
            organisation=organisation,
            rule=item,
            order=order,
            field=field,
            operator=operator,
            value=value,
            value_to=rest[0] if rest else "",
        )
    return item
