"""E-06-T06 — cheques: numbers unique and sequential **per bank account** (a used number is
skipped, a new cheque book can't start on a used number, the database refuses a duplicate);
issuing links the bill payments (reference = cheque number); register statuses Issued → Printed
→ Cleared, Stale-dated, Void (reason required, audited; refused while its payments are posted)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.audit.models import AuditEvent
from numo9.banking.services import create_bank_account
from numo9.purchases import cheques
from numo9.purchases.models import BillPayment, BillPaymentStatus, Cheque, ChequeStatus
from numo9.tenancy.context import org_context
from tests.payment_helpers import DAY, add_payment, batch, payment_books, posted_bill

pytestmark = pytest.mark.django_db
D = Decimal
S = ChequeStatus


@pytest.fixture
def books() -> dict[str, Any]:
    books = payment_books()
    books["savings"] = create_bank_account(books["org"], type="savings", display_name="Reserve")
    return books


def issue(books: dict[str, Any], amount: str = "100.00", bank: Any = None, **kw: Any) -> Cheque:
    return cheques.issue(
        bank or books["bank"], books["supplier"], D(amount), DAY, user=books["owner"], **kw
    )


def test_numbers_are_sequential_and_unique_per_bank_account(books: dict[str, Any]) -> None:
    assert [issue(books).number for _ in range(3)] == [1, 2, 3]
    assert issue(books, bank=books["savings"]).number == 1  # its own cheque stock
    with org_context(books["org"]):
        assert cheques.next_number(books["bank"]) == 4
        assert str(Cheque.objects.get(bank_account=books["bank"], number=2)) == "000002"
    with pytest.raises(IntegrityError), transaction.atomic(), org_context(books["org"]):
        Cheque(
            organisation=books["org"],
            bank_account=books["bank"],
            number=2,
            payee=books["supplier"],
            payee_name="X",
            date=DAY,
            amount=D("1"),
        ).save()


def test_new_cheque_book_and_used_numbers(books: dict[str, Any]) -> None:
    cheques.set_next_number(books["bank"], 1001, user=books["owner"])
    assert issue(books).number == 1001
    with org_context(books["org"]):  # a cheque written by hand with the next number
        Cheque(
            organisation=books["org"],
            bank_account=books["bank"],
            number=1002,
            payee=books["supplier"],
            payee_name="Cedar Supply Co.",
            date=DAY,
            amount=D("5"),
        ).save()
    assert issue(books).number == 1003  # skipped
    with pytest.raises(cheques.ChequeRefused) as used:
        cheques.set_next_number(books["bank"], 1001)
    assert used.value.code == "purchases.cheque.number_used"
    with pytest.raises(cheques.ChequeRefused):
        cheques.set_next_number(books["bank"], 0)
    with org_context(books["org"]):
        assert AuditEvent.objects.filter(action="purchases.cheque.numbering_changed").count() == 1


def test_issue_links_the_payments(books: dict[str, Any]) -> None:
    made = batch(books)
    one = add_payment(made, posted_bill(books, "300.00", "C-1"), "300.00")
    two = add_payment(made, posted_bill(books, "200.00", "C-2"), "196.00", discount="4.00")
    cheque = issue(books, "496.00", payments=[one, two], batch=made)
    with org_context(books["org"]):
        assert set(cheque.payments.values_list("pk", flat=True)) == {one.pk, two.pk}
        assert BillPayment.objects.get(pk=one.pk).reference == "000001"
        assert cheque.payee_name == "Cedar Supply Co." and cheque.status == S.ISSUED
    other = add_payment(made, posted_bill(books, "10.00", "M-1", supplier="other"), "10.00")
    with pytest.raises(cheques.ChequeRefused) as wrong:
        issue(books, "10.00", payments=[other])
    assert wrong.value.code == "purchases.cheque.payee_mismatch"


def test_register_moves(books: dict[str, Any]) -> None:
    cheque = issue(books)
    cheque = cheques.change_status(cheque, S.PRINTED, books["owner"])
    assert cheque.printed_at is not None
    cleared = cheques.change_status(cheque, S.CLEARED, cleared_on=dt.date(2026, 7, 3))
    assert (cleared.status, cleared.cleared_on) == (S.CLEARED, dt.date(2026, 7, 3))
    with pytest.raises(cheques.ChequeRefused) as final:
        cheques.change_status(cleared, S.VOID, reason="late")
    assert final.value.code == "purchases.cheque.bad_move"
    stale = cheques.change_status(issue(books), S.STALE)
    assert stale.stale_at is not None
    assert cheques.change_status(stale, S.CLEARED).cleared_on is not None  # a late deposit
    with org_context(books["org"]):
        assert AuditEvent.objects.filter(action="purchases.cheque.cleared").count() == 2


def test_void_needs_a_reason_and_frees_pending_payments(books: dict[str, Any]) -> None:
    made = batch(books)
    pay = add_payment(made, posted_bill(books, "50.00", "V-1"), "50.00")
    cheque = issue(books, "50.00", payments=[pay])
    with pytest.raises(cheques.ChequeRefused) as missing:
        cheques.change_status(cheque, S.VOID, reason="  ")
    assert missing.value.code == "purchases.cheque.reason_required"
    void = cheques.change_status(cheque, S.VOID, books["owner"], reason="Printer misfeed")
    assert (void.status, void.void_reason) == (S.VOID, "Printer misfeed")
    with org_context(books["org"]):
        assert BillPayment.objects.get(pk=pay.pk).cheque_id is None  # ready to reprint
        event = AuditEvent.objects.get(action="purchases.cheque.void")
        assert event.meta["reason"] == "Printer misfeed"
    again = issue(books, "50.00", payments=[pay], reissue_of=void)
    assert again.number == 2 and again.reissue_of == void


def test_void_refused_while_its_payments_are_posted(books: dict[str, Any]) -> None:
    made = batch(books)
    pay = add_payment(made, posted_bill(books, "75.00", "P-1"), "75.00")
    cheque = issue(books, "75.00", payments=[pay])
    with org_context(books["org"]):
        posted = posted_bill(books, "1.00", "J-1")  # any journal to satisfy the check
        BillPayment.objects.filter(pk=pay.pk).update(
            status=BillPaymentStatus.POSTED, journal_entry=posted.journal_entry
        )
    with pytest.raises(cheques.ChequeRefused) as refused:
        cheques.change_status(cheque, S.VOID, reason="Lost")
    assert refused.value.code == "purchases.cheque.void_posted"


def test_stale_rule() -> None:
    cheque = Cheque(status=S.PRINTED, date=dt.date(2026, 1, 1))
    assert not cheques.is_stale(cheque, dt.date(2026, 6, 30))  # 180 days
    assert cheques.is_stale(cheque, dt.date(2026, 7, 1))
    assert not cheques.is_stale(Cheque(status=S.CLEARED, date=dt.date(2025, 1, 1)), DAY)
