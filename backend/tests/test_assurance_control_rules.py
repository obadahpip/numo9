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
