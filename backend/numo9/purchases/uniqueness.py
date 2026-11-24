"""Supplier invoice number check (E-02-T02, gap-24): is a supplier invoice number free for this
supplier? A number is taken by another bill of the **same supplier** that isn't void or deleted;
the same number from another supplier is fine. Letter case and extra spaces don't make a number
new ("inv-7 " is "INV-7"); other characters do ("INV7" is not "INV-7": suppliers' formats differ).

``number_conflict(supplier, number, exclude=None)`` → the bill that has it, or None. The editor
asks the API on every change (live check) and the save refuses a taken number
(``purchases.bill.duplicate_number``) — the database's unique constraint is the last word.
"""

from __future__ import annotations

from typing import Any

from .models import Bill, BillStatus


def normalise(number: str) -> str:
    return " ".join((number or "").split())


def number_conflict(supplier: Any, number: str, *, exclude: Any = None) -> Bill | None:
    wanted = normalise(number)
    if not wanted or supplier is None:
        return None
    bills = Bill.objects.filter(
        contact=supplier, supplier_invoice_no__iexact=wanted, deleted_at__isnull=True
    ).exclude(status=BillStatus.VOID)
    if exclude is not None:
        bills = bills.exclude(pk=exclude.pk)
    found: Bill | None = bills.order_by("date", "pk").first()
    return found
