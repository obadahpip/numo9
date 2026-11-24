"""E-02-T06 — holdback release: Dr Holdbacks payable / Cr AP (the supplier on both), partial or
whole, the bill's amount due grows by it; refused when nothing is held, more than held, or the
bill isn't posted; the AP lock date applies."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.ledger.models import JournalEntry, JournalLine, SystemRole
from numo9.purchases.bill_posting import BillRefused, approve, release_holdback
from numo9.purchases.models import HoldbackType
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books

pytestmark = pytest.mark.django_db
RELEASE_DAY = dt.date(2026, 9, 1)


@pytest.fixture
def books() -> dict[str, Any]:
    return bill_books()


def held(books: dict[str, Any], amount: str = "5000.00") -> Any:
    draft = bill(
        books,
        [("1", amount)],
        supplier_invoice_no="HB-1",
        holdback_type=HoldbackType.PERCENT,
        holdback_value=Decimal("10"),
    )
    return approve(draft, books["owner"])


def test_release_posts_holdback_to_ap(books: dict[str, Any]) -> None:
    posted = held(books)
    assert (posted.holdback_amount, posted.amount_due) == (Decimal("500.00"), Decimal("4500.00"))
    first = release_holdback(posted, books["owner"], amount=Decimal("200"), date=RELEASE_DAY)
    assert (first.holdback_released, first.amount_due) == (Decimal("200.00"), Decimal("4700.00"))
    with org_context(books["org"]):
        entry = JournalEntry.objects.filter(source_id=str(posted.public_id)).order_by("-pk").first()
        assert entry is not None and entry.date == RELEASE_DAY
        lines = list(JournalLine.objects.filter(entry=entry).select_related("account", "contact"))
        assert [(line.account.system_role, line.debit, line.credit) for line in lines] == [
            (SystemRole.HOLDBACK_PAYABLE, Decimal("200.00"), Decimal("0.00")),
            (SystemRole.AP, Decimal("0.00"), Decimal("200.00")),
        ]
        assert {line.contact_id for line in lines} == {books["supplier"].pk}
        assert AuditEvent.objects.filter(action="purchases.bill.holdback_released").count() == 1
    rest = release_holdback(first, books["owner"], date=RELEASE_DAY)
    assert (rest.holdback_outstanding, rest.amount_due) == (Decimal("0.00"), Decimal("5000.00"))


def test_refusals(books: dict[str, Any]) -> None:
    posted = held(books, "1000.00")
    with pytest.raises(BillRefused) as too_much:
        release_holdback(posted, books["owner"], amount=Decimal("100.01"), date=RELEASE_DAY)
    assert too_much.value.code == "purchases.bill.holdback_amount"
    release_holdback(posted, books["owner"], date=RELEASE_DAY)
    with pytest.raises(BillRefused) as none_left:
        release_holdback(posted, books["owner"], date=RELEASE_DAY)
    assert none_left.value.code == "purchases.bill.no_holdback"
    draft = bill(
        books,
        [("1", "10.00")],
        supplier_invoice_no="D-1",
        holdback_type="amount",
        holdback_value=Decimal("5"),
    )
    with pytest.raises(BillRefused) as not_posted:
        release_holdback(draft, books["owner"])
    assert not_posted.value.code == "purchases.bill.no_holdback"
