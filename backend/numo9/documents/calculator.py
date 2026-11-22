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

Inclusive mode (D-01-T04): the unit prices include tax. The line amount and line discount are
worked out the same way on the tax-inclusive amount; each line's tax is backed out of it with the
G-01-T06 rule — the exclusive amount is the one whose exclusive tax gives back exactly the
inclusive amount (round(amount ÷ (1 + Σ rates)) or a cent either side); when none does, the
residual cent goes to the largest component, so exclusive + tax = inclusive always.
``total`` = subtotal (the tax is included in it); ``tax_total`` is the tax it includes.

Document discount (D-01-T05): an amount (at most the lines' total) or a percent of the lines'
total, round(Σ net × % ÷ 100). It is allocated to the lines pro-rata to their net —
round(discount × net ÷ Σ net) each — and the cents left over by rounding go one by one to the
largest lines (the first of equal ones), so Σ shares = the discount exactly and no line's share
is more than its net (a line never goes negative; lines with a net of zero or less take no
share). Tax is calculated on each line's net less its share (``taxable``). ``discount_total`` is
the discount; exclusive ``total`` = subtotal − discount + tax, inclusive ``total`` = subtotal −
discount.

No-tax mode: components are ignored, there is no tax, ``total`` = subtotal.

Every line also carries ``exclusive`` (its taxable amount before tax) and the document
``net_total`` (total − tax): what posts to the revenue or expense accounts.

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
    discount_type: str = NONE
    discount_value: Decimal = ZERO


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
    #: Tax is calculated on this (net less the line's share of the document discount); in
    #: inclusive mode it includes the tax.
    taxable: Decimal
    taxes: tuple[ComponentResult, ...]
    #: The taxable amount before tax (= taxable, except in inclusive mode).
    exclusive: Decimal = ZERO
    #: The line's share of the document discount.
    discount_share: Decimal = ZERO

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
    discount_total: Decimal = ZERO

    @property
    def tax_included(self) -> bool:
        return self.tax_mode == INCLUSIVE

    @property
    def net_total(self) -> Decimal:
        """The total before tax."""
        return self.total - self.tax_total


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


def _inclusive_taxes(
    gross: Decimal, components: Sequence[Component], side: str
) -> tuple[Decimal, tuple[ComponentResult, ...]]:
    """(exclusive amount, taxes) backed out of the tax-inclusive ``gross`` (module docstring)."""
    if not components:
        return gross, ()
    rates = [dec(c.rate) for c in components]
    first = cents(gross / (1 + sum(rates, Decimal("0")) / HUNDRED))
    step = CENT if gross >= 0 else -CENT
    for net in (first, first - step, first + step):
        amounts = [cents(net * rate / HUNDRED) for rate in rates]
        if net + sum(amounts, ZERO) == gross:
            return net, tuple(_split(c, a, side) for c, a in zip(components, amounts, strict=True))
    amounts = [cents(first * rate / HUNDRED) for rate in rates]
    largest = max(range(len(rates)), key=lambda i: (rates[i], -i))
    amounts[largest] += gross - first - sum(amounts, ZERO)
    return first, tuple(_split(c, a, side) for c, a in zip(components, amounts, strict=True))


def _split(component: Component, amount: Decimal, side: str) -> ComponentResult:
    claimable = cost = ZERO
    if side == "purchase":
        claimable = cents(amount * dec(component.claimable_pct) / HUNDRED)
        cost = amount - claimable
    return ComponentResult(component.key, dec(component.rate), amount, claimable, cost)


def document_discount(nets: Sequence[Decimal], kind: str, value: Decimal) -> Decimal:
    """The document discount on lines whose nets are ``nets`` (module docstring)."""
    value = dec(value)
    if kind == NONE or not value:
        return ZERO
    if value < 0:
        raise CalculationError("A discount can't be negative.")
    base = sum((n for n in nets if n > 0), ZERO)
    if kind == AMOUNT:
        return min(cents(value), base)
    if kind == PERCENT:
        if value > HUNDRED:
            raise CalculationError("A percent discount is at most 100 %.")
        return cents(base * value / HUNDRED)
    raise CalculationError(f"Unknown discount type {kind!r}.")


def allocate(discount: Decimal, nets: Sequence[Decimal]) -> list[Decimal]:
    """Pro-rata shares of ``discount`` (module docstring): Σ shares = discount exactly."""
    shares = [ZERO] * len(nets)
    base = sum((n for n in nets if n > 0), ZERO)
    if not discount or not base:
        return shares
    if discount > base:
        raise CalculationError("The discount is more than the lines' total.")
    for i, net in enumerate(nets):
        if net > 0:
            shares[i] = min(cents(discount * net / base), net)
    remainder = discount - sum(shares, ZERO)
    order = sorted((i for i, n in enumerate(nets) if n > 0), key=lambda i: (-nets[i], i))
    step = CENT if remainder > 0 else -CENT
    while remainder:
        moved = False
        for i in order:
            if not remainder:
                break
            proposed = shares[i] + step
            if ZERO <= proposed <= nets[i]:
                shares[i] = proposed
                remainder -= step
                moved = True
        if not moved:  # pragma: no cover — impossible while discount ≤ base
            raise CalculationError("The discount can't be allocated.")
    return shares


def calculate(document: DocumentInput) -> DocumentResult:
    """The document's amounts (module docstring)."""
    if document.tax_mode not in TAX_MODES:
        raise CalculationError(f"Unknown tax mode {document.tax_mode!r}.")
    figures = []
    for line in document.lines:
        gross = cents(dec(line.quantity) * dec(line.unit_price))
        discount = _line_discount(gross, line)
        figures.append((line, gross, discount, gross - discount))
    nets = [net for *_, net in figures]
    discount_total = document_discount(nets, document.discount_type, document.discount_value)
    shares = allocate(discount_total, nets)
    lines: list[LineResult] = [
        _line(document, line, gross, discount, net, share)
        for (line, gross, discount, net), share in zip(figures, shares, strict=True)
    ]
    by_component: dict[str, Decimal] = {}
    for result in lines:
        for tax in result.taxes:
            by_component[tax.key] = by_component.get(tax.key, ZERO) + tax.amount
    subtotal = sum((r.net for r in lines), ZERO)
    tax_total = sum(by_component.values(), ZERO)
    after_discount = subtotal - discount_total
    total = after_discount if document.tax_mode == INCLUSIVE else after_discount + tax_total
    return DocumentResult(
        document.tax_mode, tuple(lines), subtotal, tax_total, total, by_component, discount_total
    )


def _line(
    document: DocumentInput,
    line: LineInput,
    gross: Decimal,
    discount: Decimal,
    net: Decimal,
    share: Decimal,
) -> LineResult:
    taxable = net - share
    if document.tax_mode == NO_TAX:
        return LineResult(gross, discount, net, taxable, (), taxable, share)
    if document.tax_mode == INCLUSIVE:
        exclusive, taxes = _inclusive_taxes(taxable, line.components, document.side)
        return LineResult(gross, discount, net, taxable, taxes, exclusive, share)
    taxes = _taxes(taxable, line.components, document.side)
    return LineResult(gross, discount, net, taxable, taxes, taxable, share)


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
        discount_type=data.get("discount_type", NONE),
        discount_value=dec(data.get("discount_value", "0")),
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
                "discount_share": money(line.discount_share),
                "taxable": money(line.taxable),
                "exclusive": money(line.exclusive),
                "taxes": {t.key: money(t.amount) for t in line.taxes},
            }
            for line in result.lines
        ],
        "subtotal": money(result.subtotal),
        "discount_total": money(result.discount_total),
        "tax_total": money(result.tax_total),
        "total": money(result.total),
        "net_total": money(result.net_total),
        "tax_by_component": {k: money(v) for k, v in sorted(result.tax_by_component.items())},
    }
