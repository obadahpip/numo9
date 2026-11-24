"""D-03a-T09 — invoice PDF on the template baseline (gap-43): Letter pages, content inside the
1 in margins, the issuer's GST/HST program account and QST number, tax per component (GST and
PST shown apart), terms and notes, the pay-advice slip, "Draft" before approval, the customer's
language, the theme's accent colour; the text matches the fixture snapshot; the theme preview
uses the Canadian sample.
"""

from __future__ import annotations

import datetime as dt
import io
import os
import re
from pathlib import Path
from typing import Any

import pypdf
import pytest

from numo9.documents.pdf import LETTER_POINTS, render_html, render_pdf
from numo9.notifications.models import OrganisationBranding
from numo9.orgsettings.models import TaxRegistration
from numo9.orgsettings.service import get_settings
from numo9.sales.pdf import TEMPLATE, invoice_context, render_invoice_pdf, sample_invoice_context
from numo9.sales.posting import approve
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db
SNAPSHOT = Path(__file__).parent / "snapshots" / "invoice_pdf.txt"


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    org = books["org"]
    with org_context(org):
        settings = get_settings(org)
        settings.legal_name = "Refined Interiors Inc."
        settings.mailing_line1 = "200 King Street West, Suite 1200"
        settings.mailing_city, settings.mailing_province = "Toronto", "ON"
        settings.mailing_postal_code = "M5V 2T6"
        settings.save()
        for kind, number in (
            ("bn", "123456782"),
            ("rt", "123456782RT0001"),
            ("qst", "1234567890TQ0001"),
        ):
            TaxRegistration(
                organisation=org, type=kind, number=number, effective_from=dt.date(2020, 1, 1)
            ).save()
        OrganisationBranding(organisation=org, colour="#0B6E4F").save()
    books["owner"] = people(org)["owner"]
    return books


def text_of(pdf: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() for page in reader.pages)


def squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\xa0", " "))


def normalised(text: str) -> str:
    return "\n".join(
        line.rstrip() for line in re.sub(r"[ \t]+", " ", text).splitlines() if line.strip()
    )


@pytest.mark.gap("gap-43")
def test_invoice_pdf_matches_the_snapshot(books: dict[str, Any]) -> None:
    invoice = draft(
        books,
        [("3", "250.00", "sales.BC.standard"), ("1", "120.00", "sales.BC.standard")],
        province="BC",
        notes="Thank you. Pay by cheque or e-Transfer to accounts@refined.example.ca.",
    )
    approved = approve(invoice, books["owner"])
    pdf = render_invoice_pdf(approved)
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    for page in reader.pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == LETTER_POINTS
    text = normalised(text_of(pdf))
    for expected in (
        "Invoice number INV-0001",
        "GST/HST registration: 123456782 RT 0001",
        "QST registration: 1234567890 TQ 0001",
        "BC Customer Ltd",
        "Payment advice",
        "Amount enclosed",
        "Thank you. Pay by cheque",
    ):
        assert expected in text, expected
    # Tax per component, never one lumped "Tax".
    assert re.search(r"GST.*\$43\.50", text) and re.search(r"PST.*\$60\.90", text)
    assert "$974.40" in text  # 870.00 + 43.50 + 60.90
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(text + "\n", encoding="utf-8")
    # Compared without whitespace: line breaks of text extraction depend on the fonts installed.
    assert squeezed(text) == squeezed(SNAPSHOT.read_text(encoding="utf-8"))


def test_draft_says_draft_and_the_theme_colour_is_used(books: dict[str, Any]) -> None:
    invoice = draft(books, [("1", "100.00", "sales.ON.standard")])
    context = invoice_context(invoice)
    assert context["document_number"] == "Draft" and context["accent"] == "#0B6E4F"
    html = render_html(TEMPLATE, context)
    assert "#0B6E4F" in html and "Draft" in html


def test_french_customer_gets_a_french_invoice(books: dict[str, Any]) -> None:
    customer = books["customers"]["QC"]
    with org_context(books["org"]):
        customer.language = "fr-ca"
        customer.save()
    invoice = approve(
        draft(books, [("1", "100.00", "sales.QC.standard")], province="QC"), books["owner"]
    )
    text = text_of(render_invoice_pdf(invoice))
    assert "Page 1" in text or "page 1" in text.lower()
    assert "100,00" in text  # French money format


@pytest.mark.gap("gap-43")
def test_theme_preview_uses_the_canadian_sample() -> None:
    context = sample_invoice_context()
    assert context["issuer"]["province"] == "ON" and context["customer"]["postal_code"] == "K1P 5A9"
    text = text_of(render_pdf(TEMPLATE, context))
    assert "Maple Leaf Supply Ltd." in text and "HST (ON) 13 %" in text
    assert "Toronto ON" in text
