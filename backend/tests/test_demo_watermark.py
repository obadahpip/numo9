"""U-07-T08 — PDF/print watermark hook in the document renderer.

Acceptance (snapshot): every page of every PDF a demo organisation renders carries
"DEMO — NOT A REAL DOCUMENT" (French: « DÉMO — DOCUMENT FICTIF »); a real organisation's
documents carry none; the hook registry takes the first non-empty watermark.
"""

from __future__ import annotations

import dataclasses
import io

import pypdf
import pytest

from numo9.contacts.statements import render_statement_html, render_statement_pdf, sample_statement
from numo9.demo.cloning import create_demo
from numo9.documents import pdf
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
WATERMARK = "DEMO — NOT A REAL DOCUMENT"


def _long_statement() -> object:
    document = sample_statement()
    return dataclasses.replace(document, lines=list(document.lines) * 30)


def _pages(data: bytes) -> list[str]:
    """Each page's text without spaces (rotated text extracts with its spaces dropped)."""
    return [
        "".join(page.extract_text().split()) for page in pypdf.PdfReader(io.BytesIO(data)).pages
    ]


def test_every_page_of_a_demo_pdf_is_watermarked() -> None:
    demo = create_demo()
    with org_context(demo):
        pages = _pages(render_statement_pdf(_long_statement()))  # type: ignore[arg-type]
    assert len(pages) >= 2
    for text in pages:
        assert "DEMO—NOTAREALDOCUMENT" in text


def test_html_snapshot_and_french() -> None:
    demo = create_demo()
    with org_context(demo):
        html = render_statement_html(sample_statement())
        french = render_statement_html(sample_statement(), locale="fr-ca")
    assert f'<div class="document-watermark" aria-hidden="true">{WATERMARK}</div>' in html
    assert "DÉMO — DOCUMENT FICTIF" in french


def test_real_documents_carry_no_watermark() -> None:
    real = Organisation.objects.create(name="Real Ltd.")
    with org_context(real):
        html = render_statement_html(sample_statement())
        pages = _pages(render_statement_pdf(sample_statement()))
    assert 'class="document-watermark"' not in html
    assert all("NOTAREALDOCUMENT" not in text for text in pages)
    assert 'class="document-watermark"' not in render_statement_html(sample_statement())


def test_first_non_empty_hook_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "_watermark_hooks", [lambda c: "", lambda c: "DRAFT", lambda c: "X"])
    assert pdf.watermark_for({}) == "DRAFT"
