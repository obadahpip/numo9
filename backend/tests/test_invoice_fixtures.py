"""D-03a-T18 — fixtures: 50 invoices across every province and territory (HST, GST + PST,
GST + QST, GST alone; zero-rated, exempt and discounted lines; drafts, approved and void), each
posted invoice balanced against its journal; the totals match the snapshot; one PDF per province
with its taxes shown apart.
"""

from __future__ import annotations

import io
import os
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import pypdf
import pytest
from django.core.management import call_command

from numo9.ledger.models import JournalLine
from numo9.sales.fixtures import COUNT, PROVINCES, build_invoice_fixtures, render_pdf_fixtures
from numo9.sales.models import Invoice
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import sales_books

pytestmark = pytest.mark.django_db
SNAPSHOT = Path(__file__).parent / "snapshots" / "invoice_fixtures.txt"


@pytest.fixture
def built() -> dict[str, Any]:
    books = sales_books()
    owner = people(books["org"])["owner"]
    return {"books": books, "owner": owner, "invoices": build_invoice_fixtures(books["org"], owner)}


def province(invoice: Invoice) -> str:
    return str(invoice.contact.addresses.get(kind="billing").province)


def summary(invoices: list[Invoice]) -> str:
    rows = []
    for invoice in invoices:
        rows.append(
            f"{invoice.number or 'draft':9} {province(invoice)} {invoice.status:9} "
            f"{invoice.subtotal:>9} {invoice.tax_total:>8} {invoice.total:>9}"
        )
    return "\n".join(rows) + "\n"


def test_fifty_invoices_across_every_province(built: dict[str, Any]) -> None:
    org, invoices = built["books"]["org"], built["invoices"]
    assert len(invoices) == COUNT
    with org_context(org):
        assert {province(i) for i in invoices} == set(PROVINCES)
        statuses = Counter(i.status for i in invoices)
        assert statuses == {"approved": 39, "draft": 7, "void": 4}
        for invoice in invoices:
            if invoice.status == "draft":
                assert invoice.number == "" and invoice.journal_entry is None
                continue
            lines = JournalLine.objects.filter(entry=invoice.journal_entry)
            debit = sum((line.debit for line in lines), Decimal(0))
            credit = sum((line.credit for line in lines), Decimal(0))
            assert debit == credit == invoice.total
        text = summary(invoices)
    if os.environ.get("UPDATE_SNAPSHOTS"):
        SNAPSHOT.write_text(text)
    assert text == SNAPSHOT.read_text()


def test_pdf_fixtures_one_per_province(built: dict[str, Any], tmp_path: Path) -> None:
    written = render_pdf_fixtures(built["invoices"], tmp_path)
    assert len(written) == len(PROVINCES)
    texts = {
        path.name.split("-")[1]: "\n".join(
            page.extract_text() for page in pypdf.PdfReader(io.BytesIO(path.read_bytes())).pages
        )
        for path in written
    }
    assert "HST" in texts["ON"] and "HST" in texts["NS"]
    assert "PST" in texts["BC"] and "GST" in texts["BC"]
    assert "TVQ" in texts["QC"] or "QST" in texts["QC"]
    assert "GST" in texts["AB"] and "PST" not in texts["AB"]


def test_command_builds_them(tmp_path: Path) -> None:
    books = sales_books("Command Co.")
    owner = people(books["org"])["owner"]
    call_command(
        "seed_invoice_fixtures",
        str(books["org"].public_id),
        "--user",
        owner.email,
        "--pdf-dir",
        str(tmp_path),
    )
    with org_context(books["org"]):
        assert Invoice.objects.count() == COUNT
    assert len(list(tmp_path.glob("*.pdf"))) == len(PROVINCES)
