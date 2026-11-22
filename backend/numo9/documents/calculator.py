"""DocumentCalculator (D-01-T03): the amounts of a sales or purchase document, to the cent.

Server-authoritative: the editors show the client mirror's result (D-01-T10) instantly and the
server's result replaces it. Both run the same fixtures (``tests/fixtures/documents``).

Input — a ``DocumentInput``: the tax mode and a list of ``LineInput`` (quantity, unit price, line
discount as an amount or a percent, and the line's tax components: key, kind, rate in %, the
claimable % on purchases). Output — a ``DocumentResult`` with every line's figures and the
totals.

Rules (exclusive mode):

- **Line amount** = round(quantity × unit price) — rounded per line to 2 decimals (half up);
- **Line discount**: an amount (at most the line amount) or a percent, round(amount × % ÷ 100);
  ``net`` = line amount − line discount, never negative;
- **Tax** per component per line = round(net × rate ÷ 100), half up (the per-line rule of
  G-01-T06; QST on the net, never compounded); the document's tax per component is the sum of
  its lines' (``tax_by_component``);
- **Totals**: ``subtotal`` = Σ net; ``tax_total`` = Σ tax; ``total`` = subtotal + tax.

Money is ``Decimal`` throughout; nothing goes through floats.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")

EXCLUSIVE = "exclusive"
INCLUSIVE = "inclusive"
NO_TAX = "no_tax"
TAX_MODES = (EXCLUSIVE, INCLUSIVE, NO_TAX)

NONE = "none"
AMOUNT = "amount"
PERCENT = "percent"


def cents(value: Decimal) -> Decimal:
    """Round half up (away from zero) to the cent."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def dec(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class CalculationError(ValueError):
    """Input the calculator can't use (an unknown mode, a negative discount…)."""


@dataclass(frozen=True)
class Component:
    key: str
    rate: Decimal
    kind: str = ""
    #: Purchases: the claimable share in % (ITC / ITR). Sales: ignored.
    claimable_pct: Decimal = HUNDRED


@dataclass(frozen=True)
class LineInput:
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = ZERO
    discount_type: str = NONE
    discount_value: Decimal = ZERO
    components: tuple[Component, ...] = ()


@dataclass(frozen=True)
class DocumentInput:
    lines: Sequence[LineInput]
    tax_mode: str = EXCLUSIVE
    side: str = "sales"


@dataclass(frozen=True)
class ComponentResult:
    key: str
    rate: Decimal
    amount: Decimal
    claimable: Decimal = ZERO
    cost: Decimal = ZERO


@dataclass(frozen=True)
class LineResult:
    #: round(quantity × unit price).
    gross: Decimal
    line_discount: Decimal
    #: gross − line discount: the line's Amount column.
    net: Decimal
    #: Tax is calculated on this (net less the line's share of the document discount).
    taxable: Decimal
    taxes: tuple[ComponentResult, ...]

    @property
    def tax(self) -> Decimal:
        return sum((t.amount for t in self.taxes), ZERO)


@dataclass(frozen=True)
class DocumentResult:
    tax_mode: str
    lines: tuple[LineResult, ...]
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    tax_by_component: dict[str, Decimal] = field(default_factory=dict)


def _line_discount(gross: Decimal, line: LineInput) -> Decimal:
    value = dec(line.discount_value)
    if line.discount_type == NONE or not value:
        return ZERO
    if value < 0:
        raise CalculationError("A discount can't be negative.")
    if line.discount_type == AMOUNT:
        return min(cents(value), gross) if gross >= 0 else ZERO
    if line.discount_type == PERCENT:
        if value > HUNDRED:
            raise CalculationError("A percent discount is at most 100 %.")
        return cents(gross * value / HUNDRED)
    raise CalculationError(f"Unknown discount type {line.discount_type!r}.")


def _taxes(
    base: Decimal, components: Sequence[Component], side: str
) -> tuple[ComponentResult, ...]:
    out = []
    for component in components:
        amount = cents(base * dec(component.rate) / HUNDRED)
        out.append(_split(component, amount, side))
    return tuple(out)


def _split(component: Component, amount: Decimal, side: str) -> ComponentResult:
    claimable = cost = ZERO
    if side == "purchase":
        claimable = cents(amount * dec(component.claimable_pct) / HUNDRED)
        cost = amount - claimable
    return ComponentResult(component.key, dec(component.rate), amount, claimable, cost)


def calculate(document: DocumentInput) -> DocumentResult:
    """The document's amounts (module docstring)."""
    if document.tax_mode not in TAX_MODES:
        raise CalculationError(f"Unknown tax mode {document.tax_mode!r}.")
    if document.tax_mode != EXCLUSIVE:
        raise CalculationError(f"Tax mode {document.tax_mode!r} isn't supported yet.")
    lines: list[LineResult] = []
    for line in document.lines:
        gross = cents(dec(line.quantity) * dec(line.unit_price))
        discount = _line_discount(gross, line)
        net = gross - discount
        lines.append(
            LineResult(gross, discount, net, net, _taxes(net, line.components, document.side))
        )
    by_component: dict[str, Decimal] = {}
    for result in lines:
        for tax in result.taxes:
            by_component[tax.key] = by_component.get(tax.key, ZERO) + tax.amount
    subtotal = sum((r.net for r in lines), ZERO)
    tax_total = sum(by_component.values(), ZERO)
    return DocumentResult(
        document.tax_mode,
        tuple(lines),
        subtotal,
        tax_total,
        subtotal + tax_total,
        by_component,
    )


# ---- fixtures (shared with the client mirror) ----------------------------------------------------


def from_fixture(data: dict[str, Any]) -> DocumentInput:
    """A ``DocumentInput`` from the shared fixture format (``tests/fixtures/documents``)."""
    return DocumentInput(
        lines=[
            LineInput(
                quantity=dec(line.get("quantity", "1")),
                unit_price=dec(line.get("unit_price", "0")),
                discount_type=line.get("discount_type", NONE),
                discount_value=dec(line.get("discount_value", "0")),
                components=tuple(
                    Component(
                        c["key"],
                        dec(c["rate"]),
                        c.get("kind", ""),
                        dec(c.get("claimable_pct", "100")),
                    )
                    for c in line.get("components", [])
                ),
            )
            for line in data["lines"]
        ],
        tax_mode=data.get("tax_mode", EXCLUSIVE),
        side=data.get("side", "sales"),
    )


def to_fixture(result: DocumentResult) -> dict[str, Any]:
    """The result in the fixture format (strings with 2 decimals)."""

    def money(value: Decimal) -> str:
        return f"{value:.2f}"

    return {
        "lines": [
            {
                "gross": money(line.gross),
                "line_discount": money(line.line_discount),
                "net": money(line.net),
                "taxable": money(line.taxable),
                "taxes": {t.key: money(t.amount) for t in line.taxes},
            }
            for line in result.lines
        ],
        "subtotal": money(result.subtotal),
        "tax_total": money(result.tax_total),
        "total": money(result.total),
        "tax_by_component": {k: money(v) for k, v in sorted(result.tax_by_component.items())},
    }
