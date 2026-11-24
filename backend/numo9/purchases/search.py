"""Bills in the global search (E-02-T16, A-09).

A bill is found by its **number** (``BILL-0001`` — a code: exact and prefix matches rank first),
the **supplier invoice number** (``CS-1001``, also as words: "1001" finds it), its **supplier**,
its **reference**, its **total** and the words of its lines; drafts (no number yet) say "Draft
bill". The result opens the bill; it follows ``purchases.bills.view`` and the
``accounting.bills.read`` feature.
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext as _

from numo9.sales.search import _words
from numo9.search.registry import Doc

VIEW = "purchases.bills.view"
READ = "accounting.bills.read"


def bill_url(bill: Any) -> str:
    return f"/o/{bill.organisation.public_id}/purchases/bills/{bill.public_id}"


def bill_document(bill: Any) -> Doc | None:
    if bill.deleted_at is not None:
        return None
    supplier = bill.contact.display_name if bill.contact_id else ""
    name = bill.number or _("Draft bill")
    return Doc(
        title=" — ".join(x for x in (str(name), supplier) if x),
        subtitle=" · ".join(
            str(x)
            for x in (bill.get_status_display(), bill.supplier_invoice_no, bill.reference)
            if x
        ),
        code=bill.number or bill.supplier_invoice_no,
        body=" ".join(
            x
            for x in (
                bill.supplier_invoice_no,
                _words(bill.supplier_invoice_no),
                bill.reference,
                _words(bill.reference),
                *(line.description for line in bill.lines.all() if line.description and bill.pk),
            )
            if x
        ),
        amount=bill.total,
        date=bill.date,
        url=bill_url(bill),
        permission_key=VIEW,
        feature_key=READ,
    )


def register_bill_search() -> None:
    from numo9.search.registry import register_dependent, register_provider

    from .models import Bill, BillLine

    register_provider(Bill, bill_document)
    register_dependent(BillLine, lambda line: line.document)
