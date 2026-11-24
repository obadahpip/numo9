"""D-06-T03 — approving a credit note posts the invoice's lines on the other side: Dr revenue,
Dr each tax control account, Cr AR — so the customer's balance goes down and the revenue and tax
reverse, in the period of the credit note's date; numbered CN-0001; refusals."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum

from numo9.ledger.models import JournalLine
from numo9.sales.credit_notes import CreditNoteRefused, approve, recalculate
from numo9.sales.models import CreditNote, CreditNoteLine
from numo9.sales.posting import approve as approve_invoice
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books["owner"] = people(books["org"])["owner"]
    return books


def credit(
    books: dict[str, Any],
    lines: list[tuple[str, str, str]],
    *,
    province: str = "ON",
    date: dt.date = DAY,
    **fields: Any,
) -> CreditNote:
    org = books["org"]
    with org_context(org):
        note = CreditNote(
            organisation=org, contact=books["customers"][province], date=date, **fields
        )
        note.save()
        for position, (quantity, price, key) in enumerate(lines):
            CreditNoteLine(
                organisation=org,
                document=note,
                position=position,
                description=f"Line {position + 1}",
                quantity=D(quantity),
                unit_price=D(price),
                account=books["revenue"],
                tax_code=code_for(key, "sales", date, org) if key else None,
            ).save()
        return recalculate(note)


def posted(books: dict[str, Any], entry: Any) -> dict[str, tuple[Decimal, Decimal]]:
    with org_context(books["org"]):
        rows = JournalLine.objects.filter(entry=entry).select_related("account")
        return {r.account.system_role or "revenue": (r.debit, r.credit) for r in rows}


def balance(books: dict[str, Any], role: str) -> Decimal:
    with org_context(books["org"]):
        lines = JournalLine.objects.filter(account__system_role=role)
        sums = lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        return (sums["d"] or D(0)) - (sums["c"] or D(0))


def test_reverses_revenue_and_tax_and_reduces_ar(books: dict[str, Any]) -> None:
    invoice = approve_invoice(draft(books, [("2", "150.00", "sales.ON.standard")]), books["owner"])
    assert balance(books, "ar") == D("339.00")
    note = credit(books, [("1", "150.00", "sales.ON.standard")], invoice=invoice)
    approved = approve(note, books["owner"])
    assert (approved.status, approved.number, approved.total) == (
        "approved",
        "CN-0001",
        D("169.50"),
    )
    lines = posted(books, approved.journal_entry)
    assert lines == {
        "ar": (D("0.00"), D("169.50")),
        "gst_hst_payable": (D("19.50"), D("0.00")),
        "revenue": (D("150.00"), D("0.00")),
    }
    assert balance(books, "ar") == D("169.50")
    assert balance(books, "gst_hst_payable") == D("-19.50")
    with org_context(books["org"]):
        entry = approved.journal_entry
        assert entry is not None and entry.date == DAY
        assert entry.source_type == "sales.credit_note"
        assert {line.contact_id for line in entry.lines.filter(account__system_role="ar")} == {
            books["customers"]["ON"].pk
        }


def test_bc_pst_reverses_to_its_own_account(books: dict[str, Any]) -> None:
    note = credit(books, [("1", "1000.00", "sales.BC.standard")], province="BC")
    lines = posted(books, approve(note, books["owner"]).journal_entry)
    assert lines["pst_payable"] == (D("70.00"), D("0.00"))
    assert lines["gst_hst_payable"] == (D("50.00"), D("0.00"))
    assert lines["ar"] == (D("0.00"), D("1120.00"))


def test_refusals(books: dict[str, Any]) -> None:
    zero = credit(books, [("1", "0.00", "")])
    with pytest.raises(CreditNoteRefused) as error:
        approve(zero, books["owner"])
    assert error.value.code == "sales.credit_note.total_not_positive"
    with org_context(books["org"]):
        assert CreditNote.objects.get(pk=zero.pk).number == ""
    other = draft(books, [("1", "100.00", "")], province="BC")
    mismatch = credit(books, [("1", "10.00", "")], invoice=other)
    with pytest.raises(CreditNoteRefused) as error:
        approve(mismatch, books["owner"])
    assert error.value.code == "sales.credit_note.invoice_mismatch"
    done = approve(credit(books, [("1", "10.00", "")]), books["owner"])
    with pytest.raises(CreditNoteRefused):
        approve(done, books["owner"])
