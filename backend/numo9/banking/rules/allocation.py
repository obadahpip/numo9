"""Allocation lines of a bank rule: the validator (F-04-T03) and the calculator (F-04-T06).

A rule's allocation lines say where the money goes: each line has **either** a fixed amount
**or** a percentage. Fixed lines are taken first; the percentages share what remains and must
total exactly **100 %** whenever the rule has any percentage line — 60 % + 30 % is refused, fixed
10.00 + 100 % is accepted. A rule with fixed lines only codes a line whose amount equals their sum
(checked when applied, F-04-T06).

**Calculator** (``allocate(amount, shares)``, F-04-T06): the fixed lines are taken first; what
remains is shared by percentage, each line rounded half-up to the cent, and the **rounding
remainder goes to the last percentage line** — 100.00 split 33.33 % × 3 → 33.33 / 33.33 / 33.34.
The amounts always add up to the line's amount (property-tested). Should half-up rounding of the
earlier lines leave the last one below zero (tiny amounts over many lines), the earlier lines are
rounded down instead. Lines that come to 0.00 are dropped. Refused: fixed lines over the amount
(``banking.rule.fixed_exceeds``) and fixed lines only that don't equal it
(``banking.rule.allocation_mismatch``).

**Tax split per line** (``money_spec``): every allocated line keeps its own tax code and the
bank amount **includes** the tax, so each line's tax is computed on its own amount (G-01
calculator through ``tax_defaults.apply_auto``, tax inclusive) — 113.00 HST split 50/50 → two
lines of 50.00 + 6.50 HST.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

HUNDRED = Decimal("100")
ZERO = Decimal("0")
CENT = Decimal("0.01")


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


@dataclass(frozen=True)
class Allocated:
    share: Share
    amount: Decimal


def allocate(amount: Decimal, shares: Iterable[Share]) -> list[Allocated]:
    """Split ``amount`` (positive: the line's amount without its sign) over the shares."""
    total = Decimal(amount).copy_abs().quantize(CENT)
    items = list(shares)
    fixed = [(i, s) for i, s in enumerate(items) if s.fixed_amount is not None]
    percent = [(i, s) for i, s in enumerate(items) if s.percent is not None]
    out: dict[int, Decimal] = {i: Decimal(str(s.fixed_amount)).quantize(CENT) for i, s in fixed}
    remainder = total - sum(out.values(), ZERO)
    if remainder < ZERO:
        raise ValidationError(
            _("The fixed amounts (%(fixed)s) are more than the line's amount (%(amount)s)."),
            code="banking.rule.fixed_exceeds",
            params={"fixed": f"{total - remainder:.2f}", "amount": f"{total:.2f}"},
        )
    if not percent:
        if remainder != ZERO:
            raise ValidationError(
                _("The fixed amounts (%(fixed)s) don't equal the line's amount (%(amount)s)."),
                code="banking.rule.allocation_mismatch",
                params={"fixed": f"{total - remainder:.2f}", "amount": f"{total:.2f}"},
            )
    else:
        *head, (last, _share) = percent

        def shares_of(rounding: str) -> list[Decimal]:
            return [
                (remainder * Decimal(str(s.percent)) / HUNDRED).quantize(CENT, rounding=rounding)
                for _i, s in head
            ]

        parts = shares_of(ROUND_HALF_UP)
        if sum(parts, ZERO) > remainder:
            parts = shares_of(ROUND_DOWN)
        for (i, _s), part in zip(head, parts, strict=True):
            out[i] = part
        out[last] = remainder - sum(parts, ZERO)
    return [Allocated(items[i], out[i]) for i in sorted(out) if out[i] > ZERO]


def money_spec(
    kind: str,
    bank_account: Any,
    date: Any,
    allocated: Iterable[Allocated],
    *,
    contact: Any = None,
    reference: str = "",
) -> Any:
    """The spend / receive (F-01 ``MoneySpec``) of allocated lines, each line taxed on its own
    amount with its own code (tax inclusive; no code = no tax on that line)."""
    from ..models import TaxMode
    from ..tax_defaults import apply_auto
    from ..transactions import MoneyLine, MoneySpec

    lines = [
        MoneyLine(
            a.share.account,
            a.amount,
            description=a.share.description,
            tax_code=a.share.tax_code,
        )
        for a in allocated
    ]
    spec = MoneySpec(
        kind=kind,
        bank_account=bank_account,
        date=date,
        lines=lines,
        contact=contact,
        reference=reference,
        tax_mode=TaxMode.INCLUSIVE,
    )
    return apply_auto(spec)
