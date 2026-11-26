"""Early-payment discount calculator (E-07-T02): 2/10 net 30 — 2 % off when paid within 10 days.

**Window.** The discount applies on payments dated from the document date to ``until`` =
document date + ``discount_days`` (inclusive), never past the due date. A payment is dated in the
**organisation's time zone** (``payment_day``): one received at 23:59 on the last day is inside;
one at 00:00 the day after is not.

**Base.** ``pct`` of the document total (with tax, ``total``) or of the amount before tax
(``pre_tax``) — the term's ``discount_base`` (E-07-T01). ``full_discount`` is that, rounded half up
to the cent: what a customer saves by paying the whole document in the window, so they pay
``total − full_discount``.

**Partial payments — pro-rata.** A payment of ``P`` inside the window earns the share of the
discount its amount covers of the discounted total: ``discount = full_discount × P / (total −
full_discount)``, rounded to the cent, and the payment settles ``P + discount`` of the document.
Never more than the discount still unclaimed (``already_discounted`` — taken by earlier payments)
nor more than what keeps the settlement within the open balance; the last payment that clears the
discounted balance takes exactly what is left, so the discounts of a document add up to
``full_discount``. A payment outside the window earns nothing.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
HUNDRED = Decimal("100")
TOTAL = "total"
PRE_TAX = "pre_tax"


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def window_until(document_date: dt.date, days: int, due: dt.date | None = None) -> dt.date | None:
    """The last day of the discount window (``None`` without one)."""
    if days <= 0:
        return None
    until = document_date + dt.timedelta(days=days)
    return min(until, due) if due is not None else until


def payment_day(organisation: Any, moment: dt.datetime | dt.date) -> dt.date:
    """The day a payment counts for: its local date in the organisation's time zone."""
    if isinstance(moment, dt.datetime):
        from numo9.orgsettings.locks import local_date

        return local_date(organisation, moment)
    return moment


@dataclass(frozen=True)
class EarlyDiscount:
    """A document's discount terms, resolved."""

    pct: Decimal
    until: dt.date | None
    total: Decimal
    pre_tax: Decimal
    base: str = TOTAL

    @property
    def base_amount(self) -> Decimal:
        return self.pre_tax if self.base == PRE_TAX else self.total

    @property
    def full_discount(self) -> Decimal:
        if self.pct <= 0 or self.until is None:
            return ZERO
        return cents(self.base_amount * self.pct / HUNDRED)

    @property
    def discounted_total(self) -> Decimal:
        """What paying the whole document inside the window costs."""
        return self.total - self.full_discount

    def available_on(self, day: dt.date, document_date: dt.date | None = None) -> bool:
        if self.until is None or self.full_discount <= 0:
            return False
        return day <= self.until and (document_date is None or day >= document_date)

    def days_left(self, today: dt.date) -> int | None:
        """Days left to take the discount (0 on the last day; ``None`` once it has passed)."""
        if self.until is None or today > self.until:
            return None
        return (self.until - today).days


@dataclass(frozen=True)
class PaymentDiscount:
    discount: Decimal
    settles: Decimal  # payment + discount: what the payment clears of the document
    in_window: bool


def for_payment(
    terms: EarlyDiscount,
    amount: Decimal,
    day: dt.date,
    *,
    open_balance: Decimal,
    already_discounted: Decimal = ZERO,
    document_date: dt.date | None = None,
) -> PaymentDiscount:
    """The discount a payment of ``amount`` on ``day`` earns (module docstring)."""
    amount = cents(Decimal(amount))
    if amount <= 0 or not terms.available_on(day, document_date):
        return PaymentDiscount(ZERO, amount, False)
    full = terms.full_discount
    left = max(full - already_discounted, ZERO)
    if left <= 0:
        return PaymentDiscount(ZERO, amount, True)
    if amount >= open_balance - left:  # this payment clears the discounted balance
        discount = min(left, max(open_balance - amount, ZERO))
    else:
        discount = min(cents(full * amount / terms.discounted_total), left)
        discount = min(discount, max(open_balance - amount, ZERO))
    return PaymentDiscount(discount, amount + discount, True)
