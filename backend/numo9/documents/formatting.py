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


def format_time(value: dt.datetime, locale: str | None = None, time_format: str = "") -> str:
    """``4:33 p.m.`` / ``16:33`` (en-CA), ``4 h 33 p.m.`` / ``16 h 33`` (fr-CA) — the person's
    12/24-hour preference (A-02-T01), as ``formatTime`` in ``@numo9/ui``. Never "16:33PM"
    (gap-44). ``value`` is shown in its own time zone; ``time_format`` defaults per locale (12 h
    in English, 24 h in French). Plain spaces, as ``Intl.DateTimeFormat`` writes them."""
    language = _locale(locale)
    hour24 = (time_format or ("24h" if language == "fr-ca" else "12h")) == "24h"
    minutes = f"{value.minute:02d}"
    if hour24:
        return (
            f"{value.hour} h {minutes}" if language == "fr-ca" else (f"{value.hour:02d}:{minutes}")
        )
    hour = value.hour % 12 or 12
    suffix = "a.m." if value.hour < 12 else "p.m."
    if language == "fr-ca":
        return f"{hour} h {minutes} {suffix}"
    return f"{hour}:{minutes} {suffix}"


def format_datetime(value: dt.datetime, locale: str | None = None, time_format: str = "") -> str:
    """``26 Oct 2026, 4:33 p.m.`` / ``26 oct. 2026, 16 h 33`` (audit log exports)."""
    return f"{format_date(value.date(), locale)}, {format_time(value, locale, time_format)}"
