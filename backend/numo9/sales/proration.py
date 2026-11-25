"""Proration of a first or last partial period (D-04-T04).

A recurring invoice bills a period (``recurring_invoices.period_of``); when the template's
``prorate`` is on and the service starts after the period starts or ends before it ends
(``service_start`` / ``service_end``), each line is charged for the days covered:

    line net = quantity × unit price × days covered / days in the period, rounded to the cent
    (half up) per line.

``proration(period_start, period_end, service_start, service_end)`` → ``Proration`` (days
covered, days in the period; ``full`` when every day is covered, ``0`` days when none).
``Proration.amount(quantity, price)`` is the line's prorated net; ``Proration.line(quantity,
price)`` the quantity and unit price to put on the invoice line so that the line calculates to
exactly that net: the quantity kept, the price scaled (four decimals) — or, when no four-decimal
price gets there for that quantity, one unit at the prorated net.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from numo9.documents.calculator import cents

PRICE = Decimal("0.0001")


@dataclass(frozen=True)
class Proration:
    covered: int
    days: int

    @property
    def full(self) -> bool:
        return self.covered == self.days

    @property
    def fraction(self) -> Decimal:
        return Decimal(self.covered) / Decimal(self.days)

    def amount(self, quantity: Decimal, price: Decimal) -> Decimal:
        if self.full:
            return cents(quantity * price)
        return cents(quantity * price * self.covered / self.days)

    def line(self, quantity: Decimal, price: Decimal) -> tuple[Decimal, Decimal]:
        if self.full:
            return quantity, price
        net = self.amount(quantity, price)
        if quantity == 0:
            return quantity, price
        scaled = (net / quantity).quantize(PRICE, rounding=ROUND_HALF_UP)
        if cents(quantity * scaled) == net:
            return quantity, scaled
        return Decimal("1"), net


def proration(
    period_start: dt.date,
    period_end: dt.date,
    service_start: dt.date | None = None,
    service_end: dt.date | None = None,
) -> Proration:
    if period_end < period_start:
        raise ValueError("A period ends on or after its start.")
    days = (period_end - period_start).days + 1
    first = max(period_start, service_start) if service_start else period_start
    last = min(period_end, service_end) if service_end else period_end
    covered = max((last - first).days + 1, 0)
    return Proration(covered, days)


def for_template(template: object, period_start: dt.date, period_end: dt.date) -> Proration:
    """The template's proration of that period — full unless ``prorate`` is on."""
    days = (period_end - period_start).days + 1
    if not getattr(template, "prorate", False):
        return Proration(days, days)
    return proration(
        period_start,
        period_end,
        getattr(template, "service_start", None),
        getattr(template, "service_end", None),
    )
