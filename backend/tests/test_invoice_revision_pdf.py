"""D-03b-T14 — PDF stamp: revision n says "Revision n of invoice 101 — supersedes the version
issued on …" and carries the number 101-n; the PDF of a superseded revision is watermarked
"Superseded" and prints what was issued. Acceptance: snapshot PDFs for 101 and 101-1."""

from __future__ import annotations

import datetime as dt
import io
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pypdf
import pytest

from numo9.sales.models import Invoice, InvoiceLine, InvoiceRevision
from numo9.sales.pdf import render_invoice_pdf, render_revision_pdf, revision_context
from numo9.sales.posting import approve
from numo9.sales.revisions import display_number, issued_on, pdf_snapshot, restore
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db
SNAPSHOTS = Path(__file__).parent / "snapshots"


def text_of(pdf: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    text = "\n".join(page.extract_text() for page in reader.pages)
    return "\n".join(
        line.rstrip() for line in re.sub(r"[ \t]+", " ", text).splitlines() if line.strip()
    )


def squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\xa0", " "))


def matches(name: str, text: str) -> None:
    path = SNAPSHOTS / name
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not path.exists():
        path.write_text(text + "\n", encoding="utf-8")
    assert squeezed(text) == squeezed(path.read_text(encoding="utf-8"))


@pytest.fixture
def revised() -> dict[str, Any]:
    """Invoice INV-0001 at 1,130.00 (revision 0, issued 26 Oct 2026) revised to 1,017.00."""
    books = sales_books()
    org = books["org"]
    owner = people(org)["owner"]
    invoice = approve(draft(books, [("1", "1000.00", "sales.ON.standard")]), owner)
    with org_context(org):
        first = invoice.current_revision  # revision 0, made at approval (D-03b-T03)
        first.snapshot = pdf_snapshot(invoice, dt.date(2026, 10, 26))
        first.save()
        # The revised invoice: the rows hold the current revision (ADR-0006).
        InvoiceLine._base_manager.filter(document=invoice).update(unit_price=Decimal("900.00"))
        invoice = Invoice.objects.get(pk=invoice.pk)
        second = InvoiceRevision(
            organisation=org,
            invoice=invoice,
            revision=1,
            snapshot=pdf_snapshot(invoice, dt.date(2026, 11, 3)),
            reason="Unit price corrected",
        )
        second.save()
        Invoice._base_manager.filter(pk=invoice.pk).update(current_revision=second)
        invoice = Invoice.objects.get(pk=invoice.pk)
    return {"org": org, "invoice": invoice, "first": first, "second": second}


def test_revision_one_is_stamped_and_numbered(revised: dict[str, Any]) -> None:
    text = text_of(render_invoice_pdf(revised["invoice"]))
    assert "Invoice number INV-0001-1" in text
    assert "Revision 1 of invoice INV-0001 — supersedes the version issued on 26 Oct 2026" in text
    assert "$1,017.00" in text and "$1,130.00" not in text
    assert "Superseded" not in text
    assert text == text_of(render_revision_pdf(revised["second"]))  # the same document
    matches("invoice_revision_1_pdf.txt", text)


def test_the_superseded_version_is_watermarked_and_unchanged(revised: dict[str, Any]) -> None:
    text = text_of(render_revision_pdf(revised["first"]))
    assert "Superseded" in text
    assert "Invoice number INV-0001" in text and "INV-0001-1" not in text
    assert "$1,130.00" in text and "$1,017.00" not in text  # as issued, not as it is now
    assert "Revision" not in text  # revision 0 is the original: no stamp
    matches("invoice_revision_0_superseded_pdf.txt", text)


def test_an_unrevised_invoice_has_no_stamp_and_helpers() -> None:
    books = sales_books("Plain Ltd.")
    owner = people(books["org"])["owner"]
    invoice = approve(draft(books, [("1", "100.00", "sales.ON.standard")]), owner)
    text = text_of(render_invoice_pdf(invoice))
    assert "Revision" not in text and "Superseded" not in text
    assert (display_number("101", 0), display_number("101", 2)) == ("101", "101-2")
    kept = pdf_snapshot(invoice, dt.date(2026, 10, 26))
    back = restore(kept["pdf"])
    assert back["total"] == Decimal("113.00") and isinstance(back["issue_date"], dt.date)
    with org_context(books["org"]):
        row = InvoiceRevision.objects.get(invoice=invoice, revision=0)
        row.snapshot = {}
        row.save()
        assert isinstance(issued_on(row), dt.date)  # no snapshot: the day the row was created
        assert revision_context(row)["total"] == Decimal("113.00")  # no snapshot: the invoice
