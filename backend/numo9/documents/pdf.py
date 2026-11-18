"""Render a Django template to PDF with WeasyPrint (A-10-T16).

    pdf = render_pdf("documents/sample.html", sample_context(), locale="fr-ca")

The page geometry lives in ``documents/base.html`` (``@page { size: letter; margin: 1in }``) so
every document shares it; nothing here may override it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.template.loader import render_to_string
from django.utils import translation

from numo9.i18n.locale import DEFAULT, normalise_locale

# Letter, in PDF points (1 in = 72 pt) and inches — what a rendered page must measure.
LETTER_POINTS = (612.0, 792.0)
LETTER_INCHES = (8.5, 11.0)
MARGIN_INCHES = 1.0


#: Watermark hooks (U-07-T08): each returns the text to print across every page, or "" — the
#: first non-empty one wins. ``numo9.demo`` registers the demo watermark.
WatermarkHook = Callable[[dict[str, Any]], str]
_watermark_hooks: list[WatermarkHook] = []


def register_watermark(hook: WatermarkHook) -> WatermarkHook:
    if hook not in _watermark_hooks:
        _watermark_hooks.append(hook)
    return hook


def watermark_for(context: dict[str, Any]) -> str:
    for hook in _watermark_hooks:
        text = hook(context)
        if text:
            return str(text)
    return ""


def render_html(template_name: str, context: dict[str, Any], *, locale: str | None = None) -> str:
    """The document's HTML in ``locale`` (en-CA when not given), watermarked when a hook says
    so (in the document's language)."""
    language = normalise_locale(locale) or DEFAULT
    with translation.override(language):
        return render_to_string(
            template_name,
            {**context, "document_locale": language, "document_watermark": watermark_for(context)},
        )


def render_pdf(template_name: str, context: dict[str, Any], *, locale: str | None = None) -> bytes:
    """The document as PDF bytes. Templates must be self-contained (inline CSS, no network)."""
    # Imported lazily: WeasyPrint loads Pango at import time, which only document code needs.
    from weasyprint import HTML

    html = render_html(template_name, context, locale=locale)
    pdf: bytes = HTML(string=html, url_fetcher=inline_only_fetcher()).write_pdf()
    return pdf


def inline_only_fetcher() -> Any:
    """A URL fetcher that loads ``data:`` URIs only: a document never reaches the network or the
    file system (no SSRF or local-file disclosure through an image or stylesheet URL that ends
    up in user content). Other URLs are skipped with a warning; the document still renders."""
    from weasyprint.urls import URLFetcher

    return URLFetcher(allowed_protocols={"data"}, allow_redirects=False)
