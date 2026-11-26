"""D-05-T02 — allocation: auto-allocate pays the oldest due first; manual allocations; an
allocation above an invoice's open balance, above what the payment has left, to another
customer's invoice or to a draft is refused and changes nothing; unallocating gives the amount
back. Property (Hypothesis): whatever the plan, no invoice is ever paid more than its total and
no payment allocates more than its amount."""

from __future__ import annotations

import contextlib
import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.banking.services import create_bank_account
from numo9.sales.allocations import (
    AllocationRefused,
    allocate,
    auto_allocate,
    open_balance,
    unallocate,
)
from numo9.sales.models import CustomerPayment, Invoice
from numo9.sales.posting import approve
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db
D = Decimal


def _books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    books["bank"] = create_bank_account(books["org"], type="chequing", display_name="TD Chequing")
    return books


@pytest.fixture
def books() -> dict[str, Any]:
    return _books()


def invoice(books: dict[str, Any], price: str, due: dt.date, **fields: Any) -> Invoice:
    made = draft(books, [("1", price, "sales.ON.standard")], **fields)
    with org_context(books["org"]):
        made.due_date = due
        made.save(update_fields=["due_date"])
    return approve(made, books["owner"])


def payment(books: dict[str, Any], amount: str, province: str = "ON") -> CustomerPayment:
    with org_context(books["org"]):
        row = CustomerPayment(
            organisation=books["org"],
            contact=books["customers"][province],
            bank_account=books["bank"],
            date=DAY,
            amount=D(amount),
        )
        row.save()
    return row


def test_auto_allocate_pays_the_oldest_due_first(books: dict[str, Any]) -> None:
    late = invoice(books, "100.00", dt.date(2026, 7, 30))  # 113.00
    early = invoice(books, "200.00", dt.date(2026, 7, 1))  # 226.00
    with org_context(books["org"]):
        plan = auto_allocate(books["customers"]["ON"], D("300.00"))
    assert [(i.pk, a) for i, a in plan] == [(early.pk, D("226.00")), (late.pk, D("74.00"))]
    paid = payment(books, "300.00")
    allocate(paid, plan, books["owner"])
    with org_context(books["org"]):
        early.refresh_from_db()
        late.refresh_from_db()
        assert (open_balance(early), open_balance(late)) == (D("0.00"), D("39.00"))
        assert paid.unallocated == D("0.00")
        assert auto_allocate(books["customers"]["ON"], D("1000.00")) == [(late, D("39.00"))]


def test_refusals_change_nothing(books: dict[str, Any]) -> None:
    owed = invoice(books, "100.00", dt.date(2026, 7, 1))  # 113.00
    paid = payment(books, "150.00")
    with pytest.raises(AllocationRefused) as over:
        allocate(paid, [(owed, D("113.01"))], books["owner"])
    assert over.value.code == "sales.allocation.over_invoice"
    assert "has 113.00 open: 113.01 is more than it is owed" in str(over.value.messages[0])
    with pytest.raises(AllocationRefused) as source:
        allocate(payment(books, "50.00"), [(owed, D("60.00"))], books["owner"])
    assert source.value.code == "sales.allocation.over_source"
    other = invoice(books, "100.00", dt.date(2026, 7, 1), province="BC")
    with pytest.raises(AllocationRefused) as wrong:
        allocate(paid, [(other, D("10.00"))], books["owner"])
    assert wrong.value.code == "sales.allocation.wrong_customer"
    drafted = draft(books, [("1", "100.00", "sales.ON.standard")])
    with pytest.raises(AllocationRefused) as closed:
        allocate(paid, [(drafted, D("10.00"))], books["owner"])
    assert closed.value.code == "sales.allocation.over_invoice"  # a draft owes nothing yet
    with org_context(books["org"]):
        owed.refresh_from_db()
        assert owed.amount_paid == D("0.00") and paid.allocations.count() == 0


def test_manual_allocation_and_unallocate(books: dict[str, Any]) -> None:
    owed = invoice(books, "100.00", dt.date(2026, 7, 1))
    paid = payment(books, "100.00")
    (row,) = allocate(paid, [(owed, D("40.00"))], books["owner"], date=dt.date(2026, 6, 20))
    assert row.date == dt.date(2026, 6, 20)
    with org_context(books["org"]):
        owed.refresh_from_db()
        assert (owed.amount_paid, open_balance(owed)) == (D("40.00"), D("73.00"))
    unallocate(row, books["owner"])
    with org_context(books["org"]):
        owed.refresh_from_db()
        assert open_balance(owed) == D("113.00") and paid.unallocated == D("100.00")
        row.refresh_from_db()
        assert row.reversed_at is not None


AMOUNTS = st.lists(
    st.decimals(min_value=D("0.01"), max_value=D("300.00"), places=2), min_size=1, max_size=4
)


@settings(
    max_examples=15, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(paid=st.decimals(min_value=D("0.01"), max_value=D("500.00"), places=2), parts=AMOUNTS)
def test_never_over_allocated(paid: Decimal, parts: list[Decimal]) -> None:
    from django.db import transaction

    with transaction.atomic():  # each example in its own savepoint, rolled back
        books = _books()
        owed = [invoice(books, "100.00", dt.date(2026, 7, n + 1)) for n in range(2)]  # 113.00
        source = payment(books, str(paid))
        for n, amount in enumerate(parts):
            with contextlib.suppress(AllocationRefused):
                allocate(source, [(owed[n % 2], amount)], books["owner"])
        with org_context(books["org"]):
            for row in owed:
                row.refresh_from_db()
                assert D("0.00") <= row.amount_paid <= row.total
            assert source.allocated <= source.amount
        transaction.set_rollback(True)
