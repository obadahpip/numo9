"""Duplicate-invoice soft warning (D-03a-T08) [EXTRA]: before approving, the editor asks whether
the invoice looks like one already there — the **same customer**, the **same total** (to the
cent) and a date **within 7 days** either side, among the organisation's other invoices that
aren't void (drafts included: two people typing the same invoice). It is a warning: approval is
never blocked by it.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from .models import Invoice, InvoiceStatus

WINDOW_DAYS = 7


def possible_duplicates(invoice: Invoice, total: Decimal | None = None) -> list[dict[str, Any]]:
    """The look-alikes of ``invoice`` (its calculated total unless ``total`` is given)."""
    if total is None:
        from .posting import invoice_preview

        total = invoice_preview(invoice).result.total
    window = dt.timedelta(days=WINDOW_DAYS)
    found = (
        Invoice.objects.filter(
            contact=invoice.contact,
            total=total,
            date__gte=invoice.date - window,
            date__lte=invoice.date + window,
            deleted_at__isnull=True,
        )
        .exclude(status=InvoiceStatus.VOID)
        .exclude(pk=invoice.pk)
        .order_by("date", "pk")
    )
    return [
        {
            "id": str(other.public_id),
            "number": other.number,
            "date": other.date.isoformat(),
            "total": f"{other.total:.2f}",
            "status": other.status,
            "message": _("%(invoice)s for %(contact)s on %(date)s has the same total, %(total)s.")
            % {
                "invoice": other.number or _("A draft invoice"),
                "contact": invoice.contact.display_name,
                "date": other.date.isoformat(),
                "total": f"{other.total:.2f}",
            },
        }
        for other in found[:5]
    ]
