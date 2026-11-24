"""E-01-T08 — commitment report query: open PO value (before tax, not yet billed) by account,
supplier and month; drafts, POs awaiting approval, billed, closed and cancelled POs commit
nothing; a partly billed line commits its unbilled part; the report total equals the open PO
lines whatever the grouping.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.models import Account
from numo9.purchases.approvals import approve, submit
from numo9.purchases.commitments import commitments, open_value
from numo9.purchases.models import PurchaseOrderLine, PurchaseOrderStatus
from numo9.tenancy.context import org_context
from tests.purchase_helpers import po, purchase_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = purchase_books()
    with org_context(books["org"]):
        books["second"] = (
            Account.objects.filter(type="expense").exclude(pk=books["expense"].pk).order_by("code")
        ).first()
    owner = books["owner"]
    june, july = dt.date(2026, 6, 15), dt.date(2026, 7, 2)
    approve(po(books, [("10", "25.00")], tax="purchase.ON.standard", date=june), owner)  # 250
    approve(
        po(books, [("4", "100.00")], supplier="other", account=books["second"], date=june), owner
    )  # 400
    partly = approve(po(books, [("10", "10.00")], date=july), owner)  # 100, 4 billed → 60
    with org_context(books["org"]):
        line = partly.lines.get()
        line.quantity_billed = Decimal("4")
        line.save()
    po(books, [("1", "999.00")], date=june)  # draft
    submit(po(books, [("1", "888.00")], date=june), books["buyer"])  # awaiting approval
    for status in (PurchaseOrderStatus.BILLED, PurchaseOrderStatus.CLOSED):
        closed = approve(po(books, [("1", "777.00")], date=june), owner)
        with org_context(books["org"]):
            closed.status = status
            closed.save()
    return books


def test_total_equals_the_open_lines(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        expected = sum(
            (
                open_value(line)
                for line in PurchaseOrderLine.objects.filter(
                    document__status__in=["approved", "partially_received", "received"]
                )
            ),
            Decimal("0"),
        )
    assert expected == Decimal("710.00")  # 250 + 400 + 60, tax excluded
    for by in ("account", "supplier", "month"):
        report = commitments(org, by=by)
        assert report.total == expected
        assert sum((row.amount for row in report.rows), Decimal("0")) == expected


def test_groupings(books: dict[str, Any]) -> None:
    org = books["org"]
    by_supplier = commitments(org, by="supplier")
    assert [(r.label, r.amount, len(r.orders)) for r in by_supplier.rows] == [
        ("Maple Hardware Ltd", Decimal("400.00"), 1),
        ("Cedar Supply Co.", Decimal("310.00"), 2),
    ]
    by_month = commitments(org, by="month")
    assert [(r.key, r.amount) for r in by_month.rows] == [
        ("2026-06", Decimal("650.00")),
        ("2026-07", Decimal("60.00")),
    ]
    by_account = commitments(org, by="account")
    assert [r.amount for r in by_account.rows] == [Decimal("400.00"), Decimal("310.00")]
    assert by_account.rows[0].label.startswith(books["second"].code)
    assert all(row.budget is None for row in by_account.rows)  # budgets arrive with K-04
    june_only = commitments(org, by="month", date_to=dt.date(2026, 6, 30))
    assert june_only.total == Decimal("650.00")
