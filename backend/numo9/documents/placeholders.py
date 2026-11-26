"""Placeholders in recurring documents (D-04-T03; shared with recurring bills, E-03-T02).

``render(text, period_start, period_end, locale)`` resolves, in one pass:

| Placeholder | en-CA | fr-CA |
|---|---|---|
| ``{{month}}`` | ``October`` | ``octobre`` |
| ``{{year}}`` | ``2026`` | ``2026`` |
| ``{{period_start}}`` / ``{{period_end}}`` | ``1 Oct 2026`` | ``1 oct. 2026`` |

The month and year are those of the period's start. "ICU-safe": the text is the customer's own
words, never parsed as an ICU message — braces, ``#`` and apostrophes stay as typed; a value is
inserted once and never expanded again; an unknown ``{{name}}`` is left as is (``unknown()``
lists them so the editor can flag a typo). Spaces inside the braces are allowed
(``{{ month }}``); names are case-insensitive.
"""

from __future__ import annotations

import datetime as dt
import re

from django.utils import translation
from django.utils.dates import MONTHS

from numo9.documents.formatting import format_date
from numo9.i18n.locale import DEFAULT, normalise_locale

NAMES = ("period_start", "period_end", "month", "year")
PATTERN = re.compile(r"\{\{\s*([A-Za-z_]+)\s*\}\}")


def month_name(month: int, locale: str | None = None) -> str:
    """The month's full name in ``locale`` (Django's own catalogues: ``octobre``)."""
    with translation.override(normalise_locale(locale) or DEFAULT):
        return str(MONTHS[month])


def values(period_start: dt.date, period_end: dt.date, locale: str | None = None) -> dict[str, str]:
    return {
        "period_start": format_date(period_start, locale),
        "period_end": format_date(period_end, locale),
        "month": month_name(period_start.month, locale),
        "year": str(period_start.year),
    }


def render(text: str, period_start: dt.date, period_end: dt.date, locale: str | None = None) -> str:
    if not text or "{{" not in text:
        return text
    found = values(period_start, period_end, locale)
    return PATTERN.sub(lambda m: found.get(m.group(1).lower(), m.group(0)), text)


def unknown(text: str) -> list[str]:
    """Placeholders in ``text`` that aren't one of ``NAMES``."""
    return [m.group(1) for m in PATTERN.finditer(text or "") if m.group(1).lower() not in NAMES]
