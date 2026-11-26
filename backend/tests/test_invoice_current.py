"""D-03b-T12 — reports read the current revision through one query layer (``sales.current``):
invoice 101 at 1,130.00 revised to 1,017.00 in the same period — the tax report for the period
shows the invoice once, at 1,017.00 (900.00 + HST 117.00) labelled "101-1", never 1,130.00; AR
aging, the outstanding and activity statements and the reminder all show 101-1 and the current
revision's balance after a partial payment; an as-at date before the payment shows it unpaid."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.banking.services import create_bank_account
from numo9.contacts.statement_engine import build_statement
from numo9.reports.engine import registry
from numo9.sales.current import (
    ar_aging,
    current_invoices,
    current_of,
    current_tax_lines,
    open_balance,
)
from numo9.sales.posting import approve
from numo9.sales.receipts import receive_payment
from numo9.sales.reminder_templates import reminder_context
from numo9.sales.revise import revise
from numo9.sales.revisions import build_revision
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db
D = Decimal
JUNE = {"date_from": "2026-06-01", "date_to": "2026-06-30"}


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    invoice = draft(books, [("10", "100.00", "sales.ON.standard")])  # 1,130.00
    with org_context(books["org"]):
        invoice.due_date = DAY + dt.timedelta(days=30)
        invoice.save(update_fields=["due_date"])
    books["invoice"] = approve(invoice, books["owner"])
    return books


def revise_to_1017(books: dict[str, Any]) -> Any:
    with org_context(books["org"]):
        books["invoice"].refresh_from_db()
        opened = build_revision(books["invoice"])
    opened.lines[0]["quantity"] = D("9")
    opened.reason = "Nine hours, not ten"
    revision = revise(books["invoice"], opened, books["owner"])
    with org_context(books["org"]):
        books["invoice"].refresh_from_db()
    return revision


def sales_rows(result: Any) -> list[Any]:
    return [r for r in result.rows if r.kind == "row"]


def test_tax_report_for_the_period_shows_the_current_revision_only(books: dict[str, Any]) -> None:
    before = sales_rows(registry.get("tax_detail").run(books["org"], JUNE))
    assert [r.values[:2] for r in before] == [[D("1000.00"), D("130.00")]]

    revision = revise_to_1017(books)
    result = registry.get("tax_detail").run(books["org"], JUNE)
    (row,) = sales_rows(result)  # one row: no 1,130.00 / −1,130.00 pair beside it
    assert row.values[:2] == [D("900.00"), D("117.00")]
    assert row.values[0] + row.values[1] == D("1017.00")
    assert revision.number_display in row.label  # "INV-0001-1"
    assert result.totals[0].values[:2] == [D("900.00"), D("117.00")]
    summary = registry.get("tax_summary").run(books["org"], JUNE)
    assert summary.totals[0].values[:2] == [D("900.00"), D("117.00")]
    with org_context(books["org"]):
        lines = list(current_tax_lines(books["org"], dt.date(2026, 6, 1), dt.date(2026, 6, 30)))
    assert {line.entry_id for line in lines} == {revision.journal_post_id}
    assert sum((line.basis + line.tax for line in lines), D("0")) == D("1017.00")


def test_aging_statements_and_reminders_follow_the_current_revision(
    books: dict[str, Any],
) -> None:
    org, invoice = books["org"], books["invoice"]
    revision = revise_to_1017(books)
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    paid_on = DAY + dt.timedelta(days=5)
    receive_payment(invoice.contact, bank, paid_on, D("500.00"), books["owner"])

    with org_context(org):
        (current,) = current_invoices(org)
        assert (current.number, current.revision) == (revision.number_display, 1)
        assert (current.total, current.paid, current.balance) == (
            D("1017.00"),
            D("500.00"),
            D("517.00"),
        )
        assert open_balance(invoice) == D("517.00")
        assert open_balance(invoice, DAY) == D("1017.00")  # as at before the payment
        assert current_of(invoice, DAY - dt.timedelta(days=1)) is None  # not issued yet

        as_at = invoice.due_date + dt.timedelta(days=10)
        aging = ar_aging(org, as_at)
        assert aging[invoice.contact_id]["days_1_30"] == D("517.00")
        assert sum(aging[invoice.contact_id].values(), D("0")) == D("517.00")

        outstanding = build_statement(invoice.contact, "outstanding", as_at, side="receivables")
        assert [(line.document, line.amount) for line in outstanding.lines] == [
            (revision.number_display, D("517.00"))
        ]
        activity = build_statement(
            invoice.contact, "activity", as_at, start=dt.date(2026, 6, 1), side="receivables"
        )
        assert [line.amount for line in activity.lines] == [D("1017.00"), D("-500.00")]
        assert activity.amount_due == outstanding.amount_due == D("517.00")

        context = reminder_context(
            invoice, 10, amount_due=open_balance(invoice), link="https://x.test", language="en-ca"
        )
    assert context["number"] == revision.number_display
    assert context["amount_due"].startswith("$517.00")


def test_a_void_invoice_leaves_every_report(books: dict[str, Any]) -> None:
    from numo9.sales.posting import void

    void(books["invoice"], books["owner"], reason="Twice")
    with org_context(books["org"]):
        assert current_invoices(books["org"]) == []
        assert ar_aging(books["org"], DAY) == {}
