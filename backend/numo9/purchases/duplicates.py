"""Duplicate-bill suspects (E-02-T03): a bill that looks like one already entered — the **same
supplier**, a total within **±1 %** and a date within **±10 days**, among the organisation's other
bills that aren't void or deleted (drafts included: two people keying the same bill). A soft
warning beside the bill, never a block: only the supplier invoice number is unique (E-02-T02).

- ``suspects_for(bill)`` → the look-alikes of one bill, closest first (the editor's panel);
- ``review_list()`` → every pair of look-alikes among the open bills (draft, awaiting approval or
  awaiting payment), each pair once, newest bill first — the duplicate review list.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet
from django.utils.translation import gettext as _

from .models import Bill, BillStatus

WINDOW_DAYS = 10
TOLERANCE = Decimal("0.01")  # ±1 % of the bill's total
OPEN = (BillStatus.DRAFT, BillStatus.AWAITING_APPROVAL, BillStatus.AWAITING_PAYMENT)


def _band(total: Decimal) -> tuple[Decimal, Decimal]:
    spread = abs(total) * TOLERANCE
    return total - spread, total + spread


def _candidates(bill: Bill, total: Decimal) -> QuerySet[Bill]:
    low, high = _band(total)
    window = dt.timedelta(days=WINDOW_DAYS)
    return (
        Bill.objects.filter(
            contact_id=bill.contact_id,
            total__gte=low,
            total__lte=high,
            date__gte=bill.date - window,
            date__lte=bill.date + window,
            deleted_at__isnull=True,
        )
        .exclude(status=BillStatus.VOID)
        .exclude(pk=bill.pk)
    )


def _row(bill: Bill, other: Bill) -> dict[str, Any]:
    return {
        "id": str(other.public_id),
        "number": other.number,
        "supplier_invoice_no": other.supplier_invoice_no,
        "date": other.date.isoformat(),
        "total": f"{other.total:.2f}",
        "status": other.status,
        "days_apart": abs((other.date - bill.date).days),
        "message": _("%(bill)s from %(supplier)s on %(date)s for %(total)s looks like this bill.")
        % {
            "bill": other.number or other.supplier_invoice_no or _("A draft bill"),
            "supplier": bill.contact.display_name,
            "date": other.date.isoformat(),
            "total": f"{other.total:.2f}",
        },
    }


def suspects_for(bill: Bill, total: Decimal | None = None) -> list[dict[str, Any]]:
    """The look-alikes of ``bill`` (its stored total unless ``total`` is given), closest first."""
    amount = Decimal(bill.total if total is None else total)
    found = list(_candidates(bill, amount).select_related("contact"))
    found.sort(key=lambda other: (abs(other.total - amount), abs((other.date - bill.date).days)))
    return [_row(bill, other) for other in found[:5]]


def review_list(limit: int = 100) -> list[dict[str, Any]]:
    """Pairs of look-alike open bills (module docstring)."""
    bills = list(
        Bill.objects.filter(status__in=OPEN, deleted_at__isnull=True)
        .select_related("contact")
        .order_by("-date", "-pk")
    )
    seen: set[frozenset[int]] = set()
    pairs: list[dict[str, Any]] = []
    for bill in bills:
        for other in _candidates(bill, Decimal(bill.total)).filter(status__in=OPEN):
            key = frozenset((bill.pk, other.pk))
            if key in seen:
                continue
            seen.add(key)
            pairs.append(
                {
                    "bill": {
                        "id": str(bill.public_id),
                        "number": bill.number,
                        "supplier_invoice_no": bill.supplier_invoice_no,
                        "supplier": bill.contact.display_name,
                        "date": bill.date.isoformat(),
                        "total": f"{bill.total:.2f}",
                    },
                    "suspect": _row(bill, other),
                }
            )
            if len(pairs) >= limit:
                return pairs
    return pairs
