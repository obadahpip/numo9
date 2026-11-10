"""Template filters for printed documents: ``{{ amount|money:document_locale }}``."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from numo9.documents.formatting import format_date, format_money

register = template.Library()


@register.filter
def money(amount: Decimal | int | str, locale: str | None = None) -> str:
    return format_money(amount, locale)


@register.filter
def docdate(value: dt.date, locale: str | None = None) -> str:
    return format_date(value, locale)


def _css_string(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


@register.simple_tag
def page_counter_css() -> str:
    """CSS ``content`` value for the footer, e.g. ``"Page " counter(page) " of " counter(pages)``.

    The sentence stays one translatable message (no concatenated strings); the counters are
    spliced in where the translation puts ``%(page)s`` and ``%(pages)s``.
    """
    sentinel_page, sentinel_pages = "\x00PAGE\x00", "\x00PAGES\x00"
    sentence = _("Page %(page)s of %(pages)s") % {"page": sentinel_page, "pages": sentinel_pages}
    quoted = _css_string(sentence)
    value = '"' + quoted + '"'
    value = value.replace(sentinel_page, '" counter(page) "')
    value = value.replace(sentinel_pages, '" counter(pages) "')
    return mark_safe(value)  # noqa: S308 — built from an escaped translation and fixed tokens
