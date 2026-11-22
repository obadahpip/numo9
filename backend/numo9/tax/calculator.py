"""TaxCalculator (G-01-T06): the tax of one amount under one tax code version, to the cent.

All money is ``Decimal``; every component's tax is rounded **half up to the cent** separately
(the per-line default of the plan; document-level rounding is a later option).

- **Exclusive** (amount before tax): each component's tax = round(net × rate); gross = net +
  Σ tax. QST is on the net, never compounded (since 2013).
- **Inclusive** (amount includes tax): the net is the one amount whose exclusive calculation
  gives back exactly the gross — found from round(gross ÷ (1 + Σ rates)) and its neighbours, so
  inclusive and exclusive always agree (``exclusive(inclusive(g).net).gross == g``). When no net
  gives the gross exactly (rare with two components), the **residual-cent rule** applies: net =
  round(gross ÷ (1 + Σ rates)), each component round(net × rate), and the cent left over goes to
  the largest component — net + Σ tax = gross always.

**Recovery** (purchases): each component's tax splits into the **claimable** part (ITC / QST ITR:
round(tax × claimable %), ``numo9.tax.recovery``) and the **cost** (the rest — added to the expense
line). Sales: everything is tax collected (claimable and cost are 0).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .models import TaxCode, TaxCodeComponent, TaxSide
from .recovery import claimable_pct

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def cents(value: Decimal) -> Decimal:
    """Round half up to the cent."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ComponentTax:
    link: TaxCodeComponent
    rate: Decimal
    amount: Decimal
    #: Purchases: the ITC / ITR part, and the part added to the cost. Sales: 0 and 0.
    claimable: Decimal = ZERO
    cost: Decimal = ZERO

    @property
    def key(self) -> str:
        return self.link.component.key

    @property
    def kind(self) -> str:
        return self.link.component.kind


@dataclass(frozen=True)
class LineTax:
    code: TaxCode | None
    net: Decimal
    components: tuple[ComponentTax, ...]

    @property
    def tax(self) -> Decimal:
        return sum((c.amount for c in self.components), ZERO)

    @property
    def gross(self) -> Decimal:
        return self.net + self.tax

    @property
    def claimable(self) -> Decimal:
        return sum((c.claimable for c in self.components), ZERO)

    @property
    def cost(self) -> Decimal:
        """Tax that isn't claimable on a purchase: it is added to the expense line."""
        return sum((c.cost for c in self.components), ZERO)


def _links(code: TaxCode) -> list[TaxCodeComponent]:
    return list(code.components.select_related("component", "tax_code").order_by("position"))


def _exclusive_amounts(net: Decimal, links: Sequence[TaxCodeComponent]) -> list[Decimal]:
    return [cents(net * Decimal(link.component.rate) / HUNDRED) for link in links]


def _split(
    links: Sequence[TaxCodeComponent],
    amounts: Sequence[Decimal],
    side: str,
    account: Any,
    line_pct: Decimal | None,
) -> tuple[ComponentTax, ...]:
    out = []
    for link, amount in zip(links, amounts, strict=True):
        claimable = cost = ZERO
        if side == TaxSide.PURCHASE:
            claimable = cents(
                amount * claimable_pct(link, line_pct=line_pct, account=account) / HUNDRED
            )
            cost = amount - claimable
        out.append(ComponentTax(link, Decimal(link.component.rate), amount, claimable, cost))
    return tuple(out)


def calculate(
    code: TaxCode | None,
    amount: Decimal,
    *,
    inclusive: bool = False,
    account: Any = None,
    line_pct: Decimal | None = None,
    links: Sequence[TaxCodeComponent] | None = None,
) -> LineTax:
    """The tax of ``amount`` (before tax, or including it when ``inclusive``) under ``code``.

    ``code`` None, or a code without components (exempt, out of scope), gives no tax."""
    amount = cents(Decimal(amount))
    parts = list(links) if links is not None else (_links(code) if code is not None else [])
    side = code.side if code is not None else TaxSide.SALES
    if not parts:
        return LineTax(code, amount, ())
    if not inclusive:
        amounts = _exclusive_amounts(amount, parts)
        return LineTax(code, amount, _split(parts, amounts, side, account, line_pct))
    total_rate = sum((Decimal(p.component.rate) for p in parts), Decimal("0"))
    first = cents(amount / (1 + total_rate / HUNDRED))
    sign = Decimal(1) if amount >= 0 else Decimal(-1)
    for net in (first, first - CENT * sign, first + CENT * sign):
        amounts = _exclusive_amounts(net, parts)
        if net + sum(amounts, ZERO) == amount:
            return LineTax(code, net, _split(parts, amounts, side, account, line_pct))
    amounts = _exclusive_amounts(first, parts)
    residual = amount - first - sum(amounts, ZERO)
    largest = max(range(len(parts)), key=lambda i: (Decimal(parts[i].component.rate), -i))
    amounts[largest] += residual
    return LineTax(code, first, _split(parts, amounts, side, account, line_pct))
