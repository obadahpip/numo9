"""D-06-T07 — credit note PDF on the template baseline (gap-43): Letter pages, the red "Credit
note" title, number and date, the invoice it credits, tax per component, the total credit and
the credit remaining, no pay-advice slip; "Draft" before approval; the customer's language; the
text matches the fixture snapshot."""

from __future__ import annotations

import io
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pypdf
import pytest

from numo9.documents.pdf import LETTER_POINTS, render_html
from numo9.sales.credit_notes import approve
from numo9.sales.pdf import CREDIT_NOTE_TEMPLATE, credit_note_context, render_credit_note_pdf
from numo9.sales.posting import approve as approve_invoice
from numo9.tenancy.context import org_context
from tests.sales_helpers import draft
from tests.test_credit_note_posting import credit
from tests.test_invoice_pdf import books, normalised, squeezed, text_of  # noqa: F401 — fixture

pytestmark = pytest.mark.django_db
SNAPSHOT = Path(__file__).parent / "snapshots" / "credit_note_pdf.txt"


@pytest.mark.gap("gap-43")
def test_credit_note_pdf_matches_the_snapshot(books: dict[str, Any]) -> None:  # noqa: F811
    invoice = approve_invoice(
        draft(books, [("3", "250.00", "sales.BC.standard")], province="BC"), books["owner"]
    )
    note = credit(
        books,
        [("1", "250.00", "sales.BC.standard")],
        province="BC",
        invoice=invoice,
        notes="One chair returned damaged.",
    )
    approved = approve(note, books["owner"])
    pdf = render_credit_note_pdf(approved)
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    for page in reader.pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == LETTER_POINTS
    text = normalised(text_of(pdf))
    for expected in (
        "Credit note number CN-0001",
        "Credits invoice INV-0001",
        "GST/HST registration: 123456782 RT 0001",
        "BC Customer Ltd",
        "Credit remaining",
        "One chair returned damaged.",
    ):
        assert expected in text, expected
    assert "Payment advice" not in text
    assert re.search(r"GST.*\$12\.50", text) and re.search(r"PST.*\$17\.50", text)
    assert "$280.00" in text
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(text + "\n", encoding="utf-8")
    assert squeezed(text) == squeezed(SNAPSHOT.read_text(encoding="utf-8"))


def test_draft_and_remaining_credit(books: dict[str, Any]) -> None:  # noqa: F811
    note = credit(books, [("1", "100.00", "sales.ON.standard")])
    with org_context(books["org"]):
        note.amount_applied = Decimal("50.00")
    context = credit_note_context(note)
    assert context["document_number"] == "Draft" and context["accent"] == "#B42318"
    assert context["credit_remaining"] == Decimal("63.00")
    html = render_html(CREDIT_NOTE_TEMPLATE, context)
    assert "Draft" in html and "Applied to invoices" in html


def test_french_customer_gets_a_french_credit_note(books: dict[str, Any]) -> None:  # noqa: F811
    customer = books["customers"]["QC"]
    with org_context(books["org"]):
        customer.language = "fr-ca"
        customer.save()
    note = approve(
        credit(books, [("1", "100.00", "sales.QC.standard")], province="QC"), books["owner"]
    )
    text = text_of(render_credit_note_pdf(note))
    assert "100,00" in text
