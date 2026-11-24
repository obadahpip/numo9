"""E-02-T01 — Bill and BillLine: migrate, statuses, supplier invoice number unique per supplier
among bills that aren't void or deleted (the same number from two suppliers is fine), holdback
fields and checks, department; a posted bill needs its number and journal."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.purchases.models import Bill, BillStatus, HoldbackType
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return bill_books()


def test_a_draft_bill_with_lines_and_figures(books: dict[str, Any]) -> None:
    draft = bill(books, [("2", "50.00"), ("1", "25.00")], supplier_invoice_no="A-100")
    assert (draft.status, draft.number, str(draft)) == (BillStatus.DRAFT, "", "Draft bill")
    assert draft.total == Decimal("125.00")
    with org_context(books["org"]):
        assert draft.lines.count() == 2
        assert draft.amount_due == Decimal("125.00")


def test_supplier_invoice_number_is_unique_per_supplier(books: dict[str, Any]) -> None:
    bill(books, [("1", "10.00")], supplier_invoice_no="INV-7")
    bill(books, [("1", "10.00")], supplier="other", supplier_invoice_no="INV-7")  # other supplier
    bill(books, [("1", "10.00")])  # no number: never collides
    bill(books, [("1", "10.00")])
    with pytest.raises(IntegrityError), transaction.atomic():
        bill(books, [("1", "10.00")], supplier_invoice_no="INV-7")


def test_a_deleted_draft_frees_its_number(books: dict[str, Any]) -> None:
    # A void bill frees it too (E-02-T09 voids a posted bill; a void bill needs its journal).
    first = bill(books, [("1", "10.00")], supplier_invoice_no="INV-8")
    with org_context(books["org"]):
        first.soft_delete()
    bill(books, [("1", "10.00")], supplier_invoice_no="INV-8")


def test_holdback_amount_or_percent(books: dict[str, Any]) -> None:
    pct = bill(
        books, [("1", "1000.00")], holdback_type=HoldbackType.PERCENT, holdback_value=Decimal("10")
    )
    assert pct.holdback_amount == Decimal("100.00")
    assert pct.amount_due == Decimal("900.00")
    fixed = bill(
        books, [("1", "300.00")], holdback_type=HoldbackType.AMOUNT, holdback_value=Decimal("500")
    )
    assert fixed.holdback_amount == Decimal("300.00")  # never more than the total
    with pytest.raises(IntegrityError), transaction.atomic(), org_context(books["org"]):
        Bill._base_manager.filter(pk=pct.pk).update(holdback_released=Decimal("200.00"))


def test_department_and_checks(books: dict[str, Any]) -> None:
    draft = bill(books, [("1", "10.00")], department="Operations")
    assert draft.department == "Operations"
    with pytest.raises(IntegrityError), transaction.atomic(), org_context(books["org"]):
        Bill._base_manager.filter(pk=draft.pk).update(status=BillStatus.AWAITING_PAYMENT)
    with pytest.raises(IntegrityError), transaction.atomic(), org_context(books["org"]):
        Bill._base_manager.filter(pk=draft.pk).update(holdback_type="half")
