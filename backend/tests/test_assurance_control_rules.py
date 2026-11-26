"""K-09-T12, T13 — control rules: SOD_SAME_CREATOR_APPROVER, DUPLICATE_PAYMENT,
DUPLICATE_SUPPLIER_INVOICE.

Acceptance: the same user creating and approving a journal or a bill is flagged (rows as a
legacy import brings them — Numo9 itself refuses it); a different approver is not.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from numo9.assurance.rules.base import evaluate
from numo9.ledger.models import JournalApproval
from numo9.tenancy.context import org_context
from tests.assurance_helpers import NOW, post, refined

pytestmark = pytest.mark.django_db


def _approval(entry: object, submitted_by: object, decided_by: object) -> None:
    JournalApproval.objects.create(
        organisation=entry.organisation,  # type: ignore[attr-defined]
        entry=entry,
        total=Decimal("417.22"),
        submitted_by=submitted_by,
        decision="approved",
        decided_by=decided_by,
        decided_at=timezone.now(),
    )


def test_same_user_create_and_approve_journal_is_flagged() -> None:
    from tests.journal_helpers import people

    books = refined()
    org = books["org"]
    with org_context(org):
        staff = people(org)
        _approval(books["journal1"], staff["owner"], staff["owner"])  # legacy import
        _approval(books["journal2"], staff["owner"], staff["adviser"])
    (hit,) = evaluate(org, "SOD_SAME_CREATOR_APPROVER", now=NOW)
    assert hit.subject_id == str(books["journal1"].public_id)
    assert hit.details["person"] == "Dana Lee"


def test_bill_created_and_approved_by_one_person() -> None:
    from numo9.purchases.bill_posting import approve
    from numo9.purchases.models import Bill
    from tests.bill_helpers import bill, bill_books

    books = bill_books()
    own = bill(books, [("1", "80.00")], user=books["owner"], supplier_invoice_no="A-1")
    other = bill(books, [("1", "90.00")], user=books["buyer"], supplier_invoice_no="A-2")
    approve(own, books["owner"])
    approve(other, books["owner"])
    with org_context(books["org"]):
        # Numo9 allows the creator to approve within a limit today; a legacy row also counts.
        own = Bill.objects.get(pk=own.pk)
    hits = evaluate(books["org"], "SOD_SAME_CREATOR_APPROVER", now=NOW)
    assert [h.subject_id for h in hits] == [str(own.public_id)]
    assert hits[0].subject_type == "purchases.Bill"


def test_no_approval_no_finding() -> None:
    books = refined()
    with org_context(books["org"]):
        post(
            books["accounts"],
            dt.date(2026, 7, 1),
            "Plain",
            (("5920", "10.00", "0"), ("2900", "0", "10.00")),
        )
    assert evaluate(books["org"], "SOD_SAME_CREATOR_APPROVER", now=NOW) == []


# ---- DUPLICATE_PAYMENT / DUPLICATE_SUPPLIER_INVOICE (K-09-T13) ---------------------------


def test_same_supplier_same_amount_within_the_window_is_a_duplicate_payment() -> None:
    from tests.contact_helpers import contact
    from tests.ledger_helpers import account

    books = refined()
    org = books["org"]
    acc = books["accounts"]
    with org_context(org):
        acc["1010"] = account(org, "1010", "Chequing", subtype="bank")
        acc["2100"] = account(org, "2100", "Accounts payable", subtype="current_liability")
        post(
            acc,
            dt.date(2026, 6, 1),
            "Deposit",
            (("1010", "5000.00", "0"), ("4000", "0", "5000.00")),
        )
        cedar = contact(org, "Cedar Supply Co.", roles=["supplier"])
        maple = contact(org, "Maple Hardware Ltd", roles=["supplier"])
        from numo9.ledger.services import post_journal
        from numo9.ledger.validation import JournalSpec, LineSpec

        def pay(day: dt.date, who: object, amount: str = "250.00") -> object:
            return post_journal(
                JournalSpec(
                    date=day,
                    type="payment",
                    lines=(
                        LineSpec(acc["2100"], debit=Decimal(amount), contact=who),
                        LineSpec(acc["1010"], credit=Decimal(amount)),
                    ),
                ),
                user=None,
            )

        first = pay(dt.date(2026, 7, 1), cedar)
        second = pay(dt.date(2026, 7, 3), cedar)
        pay(dt.date(2026, 7, 20), cedar)  # 17 days later: not within 3
        pay(dt.date(2026, 7, 2), maple)  # another supplier
        pay(dt.date(2026, 7, 2), cedar, "251.00")  # another amount
    (hit,) = evaluate(org, "DUPLICATE_PAYMENT", now=NOW)
    assert hit.subject_id == str(second.public_id)  # type: ignore[attr-defined]
    assert hit.details["other_entry"] == str(first.public_id)  # type: ignore[attr-defined]
    assert hit.amount == Decimal("250.00") and hit.details["contact"] == "Cedar Supply Co."
    assert len(evaluate(org, "DUPLICATE_PAYMENT", now=NOW, params={"window_days": 20})) == 2


def test_duplicate_supplier_invoices_by_number_and_by_look_alike() -> None:
    from numo9.assurance.rules.controls import normalise_invoice_no
    from tests.bill_helpers import bill, bill_books

    assert normalise_invoice_no("INV-00123") == normalise_invoice_no("inv 123") == "INV123"
    books = bill_books()
    first = bill(books, [("1", "100.00")], supplier_invoice_no="INV-00123", user=books["buyer"])
    renumbered = bill(
        books,
        [("1", "40.00")],
        supplier_invoice_no="inv 123",
        date=dt.date(2026, 8, 1),
        user=books["buyer"],
    )
    look_alike = bill(
        books,
        [("1", "100.50")],
        supplier_invoice_no="X-9",
        date=dt.date(2026, 6, 20),
        user=books["buyer"],
    )
    bill(books, [("1", "100.00")], supplier="other", supplier_invoice_no="INV-00123")
    bill(books, [("1", "300.00")], supplier_invoice_no="Y-1", date=dt.date(2026, 6, 16))
    hits = {h.subject_id: h for h in evaluate(books["org"], "DUPLICATE_SUPPLIER_INVOICE", now=NOW)}
    assert set(hits) == {str(renumbered.public_id), str(look_alike.public_id)}
    assert hits[str(renumbered.public_id)].details["other_id"] == str(first.public_id)
    assert hits[str(renumbered.public_id)].details["why"] == "the same invoice number"
    assert hits[str(look_alike.public_id)].details["why"] == "a similar total within a few days"
