"""D-05-T06 — refund a customer credit to the bank: posts Dr accounts receivable (the customer's
credit) / Cr the bank account, lowers what the credit has left, and can't refund more than that;
a locked date is refused by the posting engine and changes nothing."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.banking.services import create_bank_account
from numo9.orgsettings.models import LockDate
from numo9.sales.models import CustomerCredit
from numo9.sales.receipts import ReceiptRefused, receive_payment, refund_credit
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, sales_books

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    books["bank"] = create_bank_account(books["org"], type="chequing", display_name="TD Chequing")
    receive_payment(books["customers"]["ON"], books["bank"], DAY, D("113.00"), books["owner"])
    with org_context(books["org"]):
        books["credit"] = CustomerCredit.objects.get()
    return books


def test_refund_posts_dr_ar_cr_bank(books: dict[str, Any]) -> None:
    refund = refund_credit(
        books["credit"], books["bank"], dt.date(2026, 6, 20), D("40.00"), books["owner"]
    )
    with org_context(books["org"]):
        lines = [
            (line.account.system_role or line.account.code, line.debit, line.credit, line.contact)
            for line in refund.journal_entry.lines.select_related("account", "contact")
        ]
        books["credit"].refresh_from_db()
    gl = books["bank"].gl_account.code
    customer = books["customers"]["ON"]
    assert sorted(lines, key=lambda r: r[1], reverse=True) == [
        ("ar", D("40.00"), D("0.00"), customer),
        (gl, D("0.00"), D("40.00"), None),
    ]
    assert refund.journal_entry.date == dt.date(2026, 6, 20)
    with org_context(books["org"]):
        left = books["credit"].remaining
    assert (books["credit"].amount_refunded, left) == (D("40.00"), D("73.00"))


def test_no_more_than_the_credit_has_left(books: dict[str, Any]) -> None:
    with pytest.raises(ReceiptRefused) as over:
        refund_credit(books["credit"], books["bank"], DAY, D("113.01"), books["owner"])
    assert over.value.code == "sales.credit.over_refund"
    refund_credit(books["credit"], books["bank"], DAY, D("113.00"), books["owner"])
    with pytest.raises(ReceiptRefused):
        refund_credit(books["credit"], books["bank"], DAY, D("0.01"), books["owner"])


def test_a_locked_date_changes_nothing(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        LockDate(organisation=books["org"], module="ar", level="everyone", date=DAY).save()
    with pytest.raises(Exception):  # noqa: B017 — the lock refusal (409)
        refund_credit(books["credit"], books["bank"], DAY, D("10.00"), books["owner"])
    with org_context(books["org"]):
        books["credit"].refresh_from_db()
        assert books["credit"].remaining == D("113.00") and not books["credit"].refunds.exists()
