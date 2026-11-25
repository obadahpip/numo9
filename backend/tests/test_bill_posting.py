"""E-02-T05 — bill posting: approve posts the preview's journal (Dr expense incl. non-claimable
tax, Dr ITC, Cr AP, Cr Holdbacks payable), balanced, numbered BILL-0001, awaiting payment; the
rules: supplier invoice number required (configurable) and unique per supplier, approval limit,
self-approval, totals, AP lock date; all or nothing."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.models import Account, JournalLine, SystemRole
from numo9.orgsettings.models import TaxRegistration
from numo9.orgsettings.service import get_settings
from numo9.purchases.bill_posting import BillRefused, approve, bill_spec
from numo9.purchases.bills import bill_preview
from numo9.purchases.models import Bill, BillStatus, HoldbackType
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    with org_context(books["org"]):
        TaxRegistration(
            organisation=books["org"],
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
    return books


def posted(entry: Any) -> dict[str, tuple[Decimal, Decimal]]:
    out: dict[str, tuple[Decimal, Decimal]] = {}
    for line in JournalLine.objects.filter(entry=entry).select_related("account"):
        key = line.account.system_role or line.account.code
        debit, credit = out.get(key, (Decimal("0"), Decimal("0")))
        out[key] = (debit + line.debit, credit + line.credit)
    return out


def test_approval_posts_the_preview_balanced_and_numbers_the_bill(books: dict[str, Any]) -> None:
    draft = bill(books, [("2", "500.00")], tax="purchase.ON.standard", supplier_invoice_no="C-1")
    with org_context(books["org"]):
        shown = bill_spec(draft)
    done = approve(draft, books["owner"])
    assert (done.status, done.number) == (BillStatus.AWAITING_PAYMENT, "BILL-0001")
    with org_context(books["org"]):
        lines = posted(done.journal_entry)
        assert lines[books["expense"].code] == (Decimal("1000.00"), Decimal("0"))
        assert lines[SystemRole.ITC_RECEIVABLE] == (Decimal("130.00"), Decimal("0"))
        assert lines[SystemRole.AP] == (Decimal("0"), Decimal("1130.00"))
        assert sum(d for d, _c in lines.values()) == sum(c for _d, c in lines.values())
        journal = [
            (line.debit, line.credit)
            for line in JournalLine.objects.filter(entry=done.journal_entry).order_by("line_no")
        ]
        assert journal == [(line.debit, line.credit) for line in shown.lines]
        assert done.journal_entry is not None
        assert done.journal_entry.source_type == "purchases.bill"


def test_holdback_posts_to_holdbacks_payable(books: dict[str, Any]) -> None:
    draft = bill(
        books,
        [("1", "10000.00")],
        tax="purchase.ON.standard",
        supplier_invoice_no="H-1",
        holdback_type=HoldbackType.PERCENT,
        holdback_value=Decimal("10"),
    )
    assert draft.holdback_amount == Decimal("1130.00")
    done = approve(draft, books["owner"])
    with org_context(books["org"]):
        lines = posted(done.journal_entry)
        holdback = Account.objects.get(system_role=SystemRole.HOLDBACK_PAYABLE)
    assert lines[SystemRole.AP] == (Decimal("0"), Decimal("10170.00"))
    assert lines[SystemRole.HOLDBACK_PAYABLE] == (Decimal("0"), Decimal("1130.00"))
    assert holdback.code == "2030"
    assert done.amount_due == Decimal("10170.00")


def test_supplier_invoice_number_required_and_unique(books: dict[str, Any]) -> None:
    missing = bill(books, [("1", "10.00")])
    with pytest.raises(BillRefused) as refused:
        approve(missing, books["owner"])
    assert refused.value.code == "purchases.bill.supplier_invoice_required"
    with org_context(books["org"]):
        settings = get_settings(books["org"])
        settings.bill_requires_supplier_invoice_no = False
        settings.save()
    assert approve(missing, books["owner"]).status == BillStatus.AWAITING_PAYMENT
    approve(bill(books, [("1", "10.00")], supplier_invoice_no="X-9"), books["owner"])
    with org_context(books["org"]):
        twin = bill(books, [("1", "10.00")], supplier="other", supplier_invoice_no="X-9")
        # Same number, other supplier: fine. A draft copy for the same supplier is caught:
        copy = Bill.objects.get(pk=twin.pk)
        Bill._base_manager.filter(pk=copy.pk).update(
            contact=books["supplier"], supplier_invoice_no="x-9 "
        )
    with pytest.raises(BillRefused) as duplicate:
        approve(copy, books["owner"])
    assert duplicate.value.code == "purchases.bill.duplicate_number"


def test_limits_self_approval_and_totals(books: dict[str, Any]) -> None:
    from numo9.rbac.approvals import ApprovalLimitExceeded

    big = bill(books, [("1", "9000.00")], supplier_invoice_no="L-1")
    with pytest.raises(ApprovalLimitExceeded):
        approve(big, books["buyer"])  # limit 5,000
    with org_context(books["org"]):
        Bill._base_manager.filter(pk=big.pk).update(
            status=BillStatus.AWAITING_APPROVAL, created_by=books["owner"]
        )
    with pytest.raises(BillRefused) as mine:
        approve(big, books["owner"])
    assert mine.value.code == "purchases.bill.self_approval"
    zero = bill(books, [("1", "0.00")], supplier_invoice_no="Z-1")
    with pytest.raises(BillRefused) as empty:
        approve(zero, books["owner"])
    assert empty.value.code == "purchases.bill.total_not_positive"
    with org_context(books["org"]):
        assert Bill.objects.get(pk=zero.pk).number == ""  # all or nothing


def test_ap_lock_date_refuses_and_leaves_a_draft(books: dict[str, Any]) -> None:
    from numo9.orgsettings.locks import LockedPeriod
    from numo9.orgsettings.models import LockDate

    draft = bill(books, [("1", "10.00")], supplier_invoice_no="P-1")
    with org_context(books["org"]):
        LockDate(organisation=books["org"], module="ap", level="everyone", date=draft.date).save()
    with pytest.raises(LockedPeriod) as locked:
        approve(draft, books["owner"])
    assert locked.value.violation.module == "ap"
    with org_context(books["org"]):
        again = Bill.objects.get(pk=draft.pk)
    assert (again.status, again.number, again.journal_entry_id) == (BillStatus.DRAFT, "", None)
    assert bill_preview(again).complete
