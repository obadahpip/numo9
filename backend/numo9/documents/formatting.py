"""Date and money formats for printed documents — the same output as ``@numo9/ui`` (A-10-T08).

| | en-CA | fr-CA |
|---|---|---|
| Date | ``26 Oct 2026`` | ``26 oct. 2026`` |
| Money | ``$1,234.56`` | ``1 234,56 $`` |
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from numo9.i18n.locale import DEFAULT, normalise_locale

NBSP = " "

_MONTHS = {
    "en-ca": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "fr-ca": (
        "janv.",
        "févr.",
        "mars",
        "avr.",
        "mai",
        "juin",
        "juill.",
        "août",
        "sept.",
        "oct.",
        "nov.",
        "déc.",
    ),
}


def _locale(locale: str | None) -> str:
    return normalise_locale(locale) or DEFAULT


def format_date(value: dt.date, locale: str | None = None) -> str:
    """``26 Oct 2026`` (en-CA) / ``26 oct. 2026`` (fr-CA)."""
    month = _MONTHS[_locale(locale)][value.month - 1]
    return f"{value.day} {month} {value.year}"


def format_money(amount: Decimal | int | str, locale: str | None = None) -> str:
    """CAD amount: ``$1,234.56`` / ``-$1,234.56`` (en-CA), ``1 234,56 $`` (fr-CA).

    Exact decimal arithmetic, rounded half-up to cents; a negative amount that rounds to zero
    prints as zero.
    """
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value == 0:
        value = Decimal("0.00")
    negative = value < 0
    whole, cents = f"{abs(value):.2f}".split(".")
    groups = f"{int(whole):,}"
    if _locale(locale) == "fr-ca":
        text = f"{groups.replace(',', NBSP)},{cents}{NBSP}$"
        return f"-{text}" if negative else text
    text = f"${groups}.{cents}"
    return f"-{text}" if negative else text
