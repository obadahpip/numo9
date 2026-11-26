"""D-07-T06 — late-fee / interest lines: invoice INV at 1,130.00 due 15 Jul 2026, policy 24 % a
year, 10 days' grace, 5.00 minimum. Within the grace period nothing; on 15 Aug: 31 days →
1,130.00 × 24 % × 31 / 365 = 23.03, appended to the statement; the next charge starts where it
ended (30 more days → 22.29); the payment term's rate wins over the policy's; small fees are
raised to the minimum; a fee invoice is a draft with one line per fee."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.contacts.models import PaymentTerm
from numo9.contacts.statement_engine import build_statement
from numo9.sales.late_fees import (
    LateFeeRefused,
    charge_fee_invoice,
    charge_statement,
    fee_for,
    late_fees,
)
from numo9.sales.models import Invoice, LateFeeCharge, LateFeePolicy
from numo9.sales.posting import approve
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db
D = Decimal
DUE = dt.date(2026, 7, 15)


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    made = draft(books, [("10", "100.00", "sales.ON.standard")])  # 1,130.00
    with org_context(books["org"]):
        made.due_date = DUE
        made.terms = None
        made.save(update_fields=["due_date", "terms"])
        books["policy"] = LateFeePolicy.objects.create(
            organisation=books["org"],
            is_active=True,
            rate_pct=D("24"),
            grace_days=10,
            min_fee=D("5.00"),
            fee_account=books["revenue"],
        )
    books["invoice"] = approve(made, books["owner"])
    books["contact"] = books["invoice"].contact
    return books


@pytest.mark.parametrize(
    ("balance", "rate", "days", "minimum", "fee"),
    [
        ("1130.00", "24", 31, "5.00", "23.03"),
        ("1130.00", "24", 30, "5.00", "22.29"),
        ("1130.00", "12", 31, "0.00", "11.52"),
        ("40.00", "24", 31, "5.00", "5.00"),  # 0.82 raised to the minimum
        ("1130.00", "0", 31, "5.00", "0.00"),  # no rate, no fee
        ("0.00", "24", 31, "5.00", "0.00"),
    ],
)
def test_fee_per_fixture(balance: str, rate: str, days: int, minimum: str, fee: str) -> None:
    assert fee_for(D(balance), D(rate), days, D(minimum)) == D(fee)


def test_nothing_within_the_grace_period(books: dict[str, Any]) -> None:
    assert late_fees(books["org"], DUE + dt.timedelta(days=10)) == []
    (line,) = late_fees(books["org"], DUE + dt.timedelta(days=11))
    assert (line.days, line.amount) == (11, D("8.17"))  # 1,130 × 24 % × 11 / 365


def test_statement_line_then_the_next_charge_starts_where_it_ended(
    books: dict[str, Any],
) -> None:
    contact, august = books["contact"], dt.date(2026, 8, 15)
    with org_context(books["org"]):
        statement = build_statement(contact, "outstanding", august, side="receivables")
        charged = charge_statement(statement, contact, books["owner"])
    fee = charged.lines[-1]
    assert (fee.amount, fee.balance) == (D("23.03"), D("1153.03"))
    assert "31 days at 24 % a year on 1130.00" in fee.description
    assert charged.amount_due == D("1153.03") and charged.aging["current"] == D("23.03")
    with org_context(books["org"]):
        (row,) = LateFeeCharge.objects.all()
    assert (row.start, row.end, row.days, row.target) == (DUE, august, 31, "statement")

    (later,) = late_fees(books["org"], dt.date(2026, 9, 14))
    assert (later.start, later.days, later.amount) == (august, 30, D("22.29"))
    assert late_fees(books["org"], august) == []  # the same days are never charged twice


def test_the_payment_term_rate_wins(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        term = PaymentTerm.objects.filter(organisation=books["org"]).first()
        assert term is not None
        term.late_interest_pct = D("12")
        term.save()
        Invoice.objects.filter(pk=books["invoice"].pk).update(terms=term)
    (line,) = late_fees(books["org"], dt.date(2026, 8, 15))
    assert (line.rate_pct, line.amount) == (D("12"), D("11.52"))


def test_fee_invoice_is_a_draft_with_a_line_per_fee(books: dict[str, Any]) -> None:
    invoice = charge_fee_invoice(books["contact"], dt.date(2026, 8, 15), books["owner"])
    assert invoice is not None and invoice.status == "draft"
    with org_context(books["org"]):
        (line,) = invoice.lines.all()
        assert (line.unit_price, line.account_id, line.tax_code_id) == (
            D("23.03"),
            books["revenue"].pk,
            None,
        )
        assert invoice.total == D("23.03")
        (row,) = LateFeeCharge.objects.all()
        assert (row.target, row.fee_invoice_id) == ("fee_invoice", invoice.pk)
    assert charge_fee_invoice(books["contact"], dt.date(2026, 8, 15)) is None  # charged already


def test_off_policy_and_missing_account(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        LateFeePolicy.objects.filter(pk=books["policy"].pk).update(fee_account=None)
    with pytest.raises(LateFeeRefused):
        charge_fee_invoice(books["contact"], dt.date(2026, 8, 15))
    with org_context(books["org"]):
        LateFeePolicy.objects.filter(pk=books["policy"].pk).update(is_active=False)
    assert late_fees(books["org"], dt.date(2026, 8, 15)) == []
    assert DAY < DUE
