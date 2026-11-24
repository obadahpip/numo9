"""D-03a-T03 — approving an invoice posts a balanced journal equal to the posting preview: Dr
AR, Cr revenue, Cr each tax control account separately (GST/HST payable, PST payable, QST
payable); number taken in the same transaction; all or nothing; drafts with missing accounts,
zero or negative totals and invoices already approved are refused.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.models import JournalLine
from numo9.orgsettings.models import LockDate
from numo9.sales.models import Invoice, InvoiceLine
from numo9.sales.posting import InvoiceRefused, approve, invoice_preview
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books["owner"] = people(books["org"])["owner"]
    return books


def posted(books: dict[str, Any], invoice: Invoice) -> list[tuple[str, str, Decimal, Decimal]]:
    with org_context(books["org"]):
        rows = JournalLine.objects.filter(entry=invoice.journal_entry).select_related("account")
        return sorted(
            (r.account.system_role or "revenue", r.account.code, r.debit, r.credit) for r in rows
        )


def test_ontario_hst_posts_ar_revenue_and_hst(books: dict[str, Any]) -> None:
    invoice = draft(books, [("2", "150.00", "sales.ON.standard")])
    shown = invoice_preview(invoice)
    approved = approve(invoice, books["owner"])
    assert (approved.status, approved.number) == ("approved", "INV-0001")
    assert (approved.subtotal, approved.tax_total, approved.total) == (
        Decimal("300.00"),
        Decimal("39.00"),
        Decimal("339.00"),
    )
    lines = posted(books, approved)
    assert [(role, d, c) for role, _code, d, c in lines] == [
        ("ar", Decimal("339.00"), Decimal("0.00")),
        ("gst_hst_payable", Decimal("0.00"), Decimal("39.00")),
        ("revenue", Decimal("0.00"), Decimal("300.00")),
    ]
    # The posted journal is the preview's lines.
    with org_context(books["org"]):
        entry = approved.journal_entry
        assert entry is not None
        assert entry.source_type == "sales.invoice" and entry.source_id == str(approved.public_id)
        assert entry.created_by == books["owner"] or entry.posted_by == books["owner"]
    expected = sorted((Decimal(x.debit), Decimal(x.credit)) for x in shown.lines)
    assert sorted((d, c) for _r, _c, d, c in lines) == expected
    with org_context(books["org"]):
        line = InvoiceLine.objects.get(document=approved)
        assert (line.net, line.tax_amount, line.amount) == (
            Decimal("300.00"),
            Decimal("39.00"),
            Decimal("300.00"),
        )


def test_bc_gst_and_pst_go_to_separate_control_accounts(books: dict[str, Any]) -> None:
    invoice = draft(books, [("1", "1000.00", "sales.BC.standard")], province="BC")
    lines = posted(books, approve(invoice, books["owner"]))
    roles = {role: (d, c) for role, _code, d, c in lines}
    assert roles["gst_hst_payable"] == (Decimal("0.00"), Decimal("50.00"))
    assert roles["pst_payable"] == (Decimal("0.00"), Decimal("70.00"))
    assert roles["ar"] == (Decimal("1120.00"), Decimal("0.00"))


def test_quebec_qst_separate(books: dict[str, Any]) -> None:
    invoice = draft(books, [("1", "100.00", "sales.QC.standard")], province="QC")
    roles = {role: (d, c) for role, _code, d, c in posted(books, approve(invoice, books["owner"]))}
    assert roles["qst_payable"] == (Decimal("0.00"), Decimal("9.98"))
    assert roles["gst_hst_payable"] == (Decimal("0.00"), Decimal("5.00"))


def test_refusals(books: dict[str, Any]) -> None:
    owner = books["owner"]
    zero = draft(books, [("1", "0.00", "sales.ON.standard")])
    with pytest.raises(InvoiceRefused) as caught:
        approve(zero, owner)
    assert caught.value.code == "sales.invoice.total_not_positive"
    negative = draft(books, [("-1", "50.00", "sales.ON.standard")])
    with pytest.raises(InvoiceRefused):
        approve(negative, owner)
    incomplete = draft(books, [("1", "50.00", "sales.ON.standard")])
    with org_context(books["org"]):
        InvoiceLine.objects.filter(document=incomplete).update(account=None)
    with pytest.raises(InvoiceRefused) as caught:
        approve(incomplete, owner)
    assert caught.value.code == "sales.invoice.incomplete"
    good = draft(books, [("1", "50.00", "sales.ON.standard")])
    approve(good, owner)
    with pytest.raises(InvoiceRefused) as caught:
        approve(good, owner)
    assert caught.value.code == "sales.invoice.not_draft"


def test_all_or_nothing_when_the_period_is_locked(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        LockDate(organisation=books["org"], module="ar", level="everyone", date=DAY).save()
    invoice = draft(books, [("1", "50.00", "sales.ON.standard")])
    with pytest.raises(Exception):  # noqa: B017 — the lock refusal (409)
        approve(invoice, books["owner"])
    with org_context(books["org"]):
        invoice.refresh_from_db()
    assert (invoice.status, invoice.number, invoice.journal_entry_id) == ("draft", "", None)
    later = draft(books, [("1", "50.00", "sales.ON.standard")], date=DAY.replace(day=16))
    assert approve(later, books["owner"]).number == "INV-0001"  # no gap from the refused one
