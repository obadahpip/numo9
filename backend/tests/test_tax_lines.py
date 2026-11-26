"""G-05-T02 — the posted tax lines: one per line and component, written when a document posts;
a reversal copies them negated; a recode re-post copies them; a manual journal's tax-coded line
is a journal-source line; the query layer filters by range, tax and side, current revision
only."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tax.models import TaxLine
from numo9.tax.tax_lines import posted_tax_lines
from numo9.tenancy.context import org_context
from tests.tax_report_helpers import Q2, tax_books

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    return tax_books()


def sums(rows: Any) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    rows = list(rows)
    return (
        sum((r.basis for r in rows), D("0")),
        sum((r.tax for r in rows), D("0")),
        sum((r.recoverable for r in rows), D("0")),
        sum((r.non_recoverable for r in rows), D("0")),
    )


def test_documents_write_their_tax_lines(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        sales = posted_tax_lines(org, *Q2, side="sales")
        purchases = posted_tax_lines(org, *Q2, side="purchase")
        assert sums(sales) == (D("1500.00"), D("195.00"), D("0"), D("0"))
        assert sums(purchases) == (D("1200.00"), D("156.00"), D("143.00"), D("13.00"))
        first = sales.first()
        assert first is not None
        assert (first.code, first.kind, first.rate) == ("sales.ON.standard", "hst", D("13.0000"))
        assert first.entry_id == books["invoices"][0].journal_entry_id and first.line_no == 1
        meals = purchases.get(restricted=True)
        assert (meals.tax, meals.recoverable, meals.non_recoverable) == (
            D("26.00"),
            D("13.00"),
            D("13.00"),
        )
        # the journal posted straight to GST/HST payable has no tax line
        assert not TaxLine.objects.filter(entry=books["direct"]).exists()
        assert posted_tax_lines(org, *Q2, kind="qst").count() == 0
        assert posted_tax_lines(org, *Q2, kind="gst_hst").count() == 4
        assert posted_tax_lines(org, dt.date(2026, 5, 1), dt.date(2026, 5, 31)).count() == 2


def test_a_reversal_copies_negated_and_current_only_hides_the_pair(books: dict[str, Any]) -> None:
    from numo9.sales.posting import void

    org = books["org"]
    void(books["invoices"][1], books["owner"], reason="Entered twice")
    with org_context(org):
        everything = posted_tax_lines(org, *Q2, side="sales")
        assert everything.count() == 3
        assert sums(everything)[1] == D("130.00")
        reversal = everything.get(reverses__isnull=False)
        assert (reversal.tax, reversal.basis) == (D("-65.00"), D("-500.00"))
        current = posted_tax_lines(org, *Q2, side="sales", current_only=True)
        assert [r.tax for r in current] == [D("130.00")]
        assert reversal.date == books["invoices"][1].date  # the void is dated the invoice's date
        may = posted_tax_lines(org, dt.date(2026, 5, 1), dt.date(2026, 5, 20), current_only=True)
        assert [r.side for r in may] == ["purchase"]  # the voided sale and its reversal: hidden


def test_manual_journal_with_a_tax_code_is_journal_source(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        entry = post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 10),
                lines=[
                    LineSpec(
                        books["bank_like"] if "bank_like" in books else books["expense"],
                        debit=D("50.00"),
                        tax_code="purchase.ON.standard",
                    ),
                    LineSpec(books["revenue"], credit=D("50.00")),
                ],
            ),
            user=books["owner"],
        )
        (row,) = TaxLine.objects.filter(entry=entry)
    assert (row.source, row.side, row.basis, row.tax) == ("journal", "purchase", D("50.00"), D("0"))


def test_recode_repost_carries_the_tax_lines(books: dict[str, Any]) -> None:
    from numo9.ledger.models import Account
    from numo9.ledger.recode_execute import create_batch, execute

    org = books["org"]
    with org_context(org):
        other = Account.objects.filter(subtype="revenue").exclude(pk=books["revenue"].pk).first()
        assert other is not None
        criteria = {
            "conditions": [
                {"field": "account", "op": "is", "value": str(books["revenue"].public_id)}
            ]
        }
        done = execute(
            create_batch(org, criteria, {"account": str(other.public_id)}, books["owner"]),
            books["owner"],
        )
        assert done.line_count == 2
        rows = posted_tax_lines(org, *Q2, side="sales")
        assert sums(rows)[1] == D("195.00")  # original + reversal + re-post
        assert sums(posted_tax_lines(org, *Q2, side="sales", current_only=True))[1] == D("195.00")
        change = done.lines.first()
        assert change is not None
        repost = change.repost_entry
        assert TaxLine.objects.filter(entry=repost).count() == 1
