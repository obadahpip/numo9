"""Bills for the E-02 tests: the purchase books of E-01 (Ontario template chart, two suppliers,
an owner and a buyer) and a ``bill()`` builder of drafts."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.purchases.models import Bill, BillLine
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from tests.purchase_helpers import DAY, member, purchase_books

__all__ = ["DAY", "bill", "bill_books", "member"]


def bill_books(name: str = "Refined Interiors Inc.") -> dict[str, Any]:
    books = purchase_books(name)
    from numo9.rbac.models import ApprovalLimit

    with org_context(books["org"]):
        for user, limit in ((books["owner"], "100000"), (books["buyer"], "5000")):
            ApprovalLimit.objects.create(user=user, doc_type="bill", max_amount=Decimal(limit))
    return books


def bill(
    books: dict[str, Any],
    lines: list[tuple[str, str]],
    *,
    tax: str = "",
    supplier: str = "supplier",
    date: dt.date = DAY,
    account: Any = None,
    user: Any = None,
    supplier_invoice_no: str = "",
    **fields: Any,
) -> Bill:
    """A draft bill: ``lines`` = (quantity, unit price); ``tax`` = a purchase tax code key."""
    from numo9.purchases.bills import recalculate

    org = books["org"]
    with org_context(org):
        draft = Bill(
            organisation=org,
            contact=books[supplier],
            date=date,
            due_date=fields.pop("due_date", date + dt.timedelta(days=30)),
            created_by=user,
            supplier_invoice_no=supplier_invoice_no,
            tax_mode=fields.pop("tax_mode", "no_tax" if not tax else "exclusive"),
            **fields,
        )
        draft.save()
        for position, (quantity, price) in enumerate(lines):
            BillLine(
                organisation=org,
                document=draft,
                position=position,
                description=f"Line {position + 1}",
                quantity=Decimal(quantity),
                unit_price=Decimal(price),
                account=account or books["expense"],
                tax_code=code_for(tax, "purchase", date, org) if tax else None,
            ).save()
        return recalculate(draft)
