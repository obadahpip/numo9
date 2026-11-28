"""Allocation lines of a bank rule (F-04-T03): the validator.

A rule's allocation lines say where the money goes: each line has **either** a fixed amount
**or** a percentage. Fixed lines are taken first; the percentages share what remains and must
total exactly **100 %** whenever the rule has any percentage line — 60 % + 30 % is refused, fixed
10.00 + 100 % is accepted. A rule with fixed lines only codes a line whose amount equals their sum
(checked when applied, F-04-T06).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

HUNDRED = Decimal("100")
ZERO = Decimal("0")


@dataclass(frozen=True)
class Share:
    """One allocation line as the validator and the calculator read it."""

    fixed_amount: Decimal | None = None
    percent: Decimal | None = None
    account: Any = None
    tax_code: str = ""
    description: str = ""

    @classmethod
    def of(cls, row: Any) -> Share:
        return cls(
            fixed_amount=row.fixed_amount,
            percent=row.percent,
            account=row.account,
            tax_code=row.tax_code,
            description=row.description,
        )


def _decimal(value: Any) -> Decimal | None:
    return None if value is None or value == "" else Decimal(str(value))


def validate_allocations(shares: Iterable[Share]) -> None:
    """Refuse an empty allocation, a line with both or neither of fixed amount and percentage,
    non-positive values, and percentages that don't total 100 %."""
    items = list(shares)
    if not items:
        raise ValidationError(
            _("Add at least one allocation line."), code="banking.rule.allocations_required"
        )
    total = ZERO
    has_percent = False
    for number, share in enumerate(items, start=1):
        fixed, percent = _decimal(share.fixed_amount), _decimal(share.percent)
        if (fixed is None) == (percent is None):
            raise ValidationError(
                _("Line %(line)d: give a fixed amount or a percentage, not both."),
                code="banking.rule.allocation_kind",
                params={"line": number},
            )
        if fixed is not None and fixed <= ZERO:
            raise ValidationError(
                _("Line %(line)d: the fixed amount must be more than 0.00."),
                code="banking.rule.allocation_amount",
                params={"line": number},
            )
        if percent is not None:
            if percent <= ZERO or percent > HUNDRED:
                raise ValidationError(
                    _("Line %(line)d: the percentage is more than 0 and at most 100."),
                    code="banking.rule.allocation_percent",
                    params={"line": number},
                )
            has_percent = True
            total += percent
    if has_percent and total != HUNDRED:
        raise ValidationError(
            _("The percentages total %(total)s %%: they must total 100 %%."),
            code="banking.rule.percent_total",
            params={"total": f"{total.normalize():f}"},
        )
