"""Due-date resolver (D-01-T07): a document's due date from its payment terms (B-01-T05).

``due_date(date, terms_type, days)`` — the four term types of the master list and the
organisation's defaults (A-05):

- ``days_after_document`` *n* — the document date + *n* days (Net 30; Due on receipt is 0);
- ``days_after_month_end`` *n* — the last day of the document's month + *n* days (EOM is 0);
- ``day_of_following_month`` *n* — the *n*th of the next month, the month's last day when it is
  shorter (31 → 28 or 29 February);
- ``day_of_current_month`` *n* — the *n*th of the document's month (last day when shorter); when
  that day is before the document date, the *n*th of the next month (a due date is never before
  the document date).

``resolve(date, term)`` — a ``PaymentTerm`` (or anything with ``terms_type``, ``days``,
``discount_pct``, ``discount_days``) → ``DueDates``: the due date and, for an early-payment
discount (2/10 net 30), the last day it applies (date + discount days) and its percent.

``document_terms(side, contact, organisation)`` — the terms a new document starts with: the
contact's default invoice / bill terms (an archived term is skipped), else the organisation's
default for the side.
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from numo9.orgsettings.models import TermsType

SALES = "sales"
PURCHASE = "purchase"


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _next_month(day: dt.date) -> tuple[int, int]:
    return (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)


def _day_of(year: int, month: int, n: int) -> dt.date:
    return dt.date(year, month, min(max(n, 1), _last_day(year, month)))


def due_date(date: dt.date, terms_type: str, days: int) -> dt.date:
    """The due date (module docstring)."""
    if days < 0:
        raise ValueError("Terms days can't be negative.")
    if terms_type == TermsType.DAYS_AFTER_DOCUMENT:
        return date + dt.timedelta(days=days)
    if terms_type == TermsType.DAYS_AFTER_MONTH_END:
        return dt.date(date.year, date.month, _last_day(date.year, date.month)) + dt.timedelta(
            days=days
        )
    if terms_type == TermsType.DAY_OF_FOLLOWING_MONTH:
        return _day_of(*_next_month(date), days)
    if terms_type == TermsType.DAY_OF_CURRENT_MONTH:
        this_month = _day_of(date.year, date.month, days)
        return this_month if this_month >= date else _day_of(*_next_month(date), days)
    raise ValueError(f"Unknown terms type {terms_type!r}.")


@dataclass(frozen=True)
class DueDates:
    due: dt.date
    #: Last day the early-payment discount applies (None without a discount).
    discount_until: dt.date | None = None
    discount_pct: Decimal = Decimal("0")


def due_in(date: dt.date, due: dt.date) -> int:
    """Days from ``date`` to ``due`` ("due in N days" — D-01-T17's helper)."""
    return (due - date).days


def resolve(date: dt.date, term: Any) -> DueDates:
    due = due_date(date, term.terms_type, term.days)
    pct = Decimal(str(getattr(term, "discount_pct", 0) or 0))
    discount_days = int(getattr(term, "discount_days", 0) or 0)
    if pct and discount_days:
        return DueDates(due, min(date + dt.timedelta(days=discount_days), due), pct)
    return DueDates(due)


@dataclass(frozen=True)
class Terms:
    """The terms a document uses: a master-list term, or the organisation's default."""

    terms_type: str
    days: int
    term: Any = None
    discount_pct: Decimal = Decimal("0")
    discount_days: int = 0


def document_terms(side: str, contact: Any, organisation: Any) -> Terms:
    term = None
    if contact is not None:
        term = contact.sales_payment_term if side == SALES else contact.purchase_payment_term
    if term is not None and getattr(term, "status", "active") == "active":
        return Terms(term.terms_type, term.days, term, term.discount_pct, term.discount_days)
    from numo9.orgsettings.service import get_settings

    settings = get_settings(organisation)
    if side == SALES:
        return Terms(settings.sales_terms_type, settings.sales_terms_days)
    return Terms(settings.purchase_terms_type, settings.purchase_terms_days)
