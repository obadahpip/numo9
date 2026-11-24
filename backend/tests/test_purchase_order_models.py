"""E-01-T01 — PurchaseOrder and PurchaseOrderLine on the document base (purchase side): a draft
has no number and shows "Draft purchase order"; an approved status needs a number (database
check); numbers are unique per organisation; statuses are checked; received and billed
quantities can't be negative; outstanding = ordered − received; the PO is audited.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.audit.models import AuditEvent
from numo9.purchases.models import PurchaseOrder, PurchaseOrderLine, PurchaseOrderStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.journal_helpers import chart

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        supplier = contact(org, "Cedar Supply Co.", roles=["supplier"])
    return {"org": org, "supplier": supplier, **accounts}


def po(books: dict[str, Any], **fields: Any) -> PurchaseOrder:
    item = PurchaseOrder(
        organisation=books["org"], contact=books["supplier"], date=dt.date(2026, 6, 15), **fields
    )
    item.save()
    return item


def test_draft_lines_and_outstanding(books: dict[str, Any]) -> None:
    expense = next(a for k, a in books.items() if k not in ("org", "supplier"))
    with org_context(books["org"]):
        draft = po(books, delivery_address="200 King St W, Toronto ON")
        assert (draft.status, draft.number, str(draft)) == ("draft", "", "Draft purchase order")
        line = PurchaseOrderLine(
            organisation=books["org"],
            document=draft,
            description="Oak boards",
            quantity=Decimal("10"),
            unit_price=Decimal("25.00"),
            account=expense,
        )
        line.save()
        assert line.outstanding == Decimal("10")
        line.quantity_received = Decimal("6")
        line.save()
        assert line.outstanding == Decimal("4")
        line.quantity_received = Decimal("12")  # over-received: nothing outstanding
        assert line.outstanding == Decimal("0")
        assert AuditEvent.objects.filter(
            object_type="purchases.PurchaseOrder", object_id=str(draft.public_id)
        ).exists()


def test_database_rules(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        with pytest.raises(IntegrityError), transaction.atomic():
            po(books, status=PurchaseOrderStatus.APPROVED)  # approved without a number
        with pytest.raises(IntegrityError), transaction.atomic():
            po(books, status="shipped")
        po(books, status=PurchaseOrderStatus.APPROVED, number="PO-0001")
        with pytest.raises(IntegrityError), transaction.atomic():
            po(books, status=PurchaseOrderStatus.APPROVED, number="PO-0001")
        po(books)
        po(books)  # empty numbers aren't unique
        draft = po(books)
        with pytest.raises(IntegrityError), transaction.atomic():
            PurchaseOrderLine(
                organisation=books["org"],
                document=draft,
                description="x",
                quantity=Decimal("1"),
                unit_price=Decimal("1"),
                quantity_received=Decimal("-1"),
            ).save()
