"""Invoices in the global search (D-03a-T17, A-09).

An invoice is found by its **number** (``INV-0001`` — a code: exact and prefix matches rank first),
its **contact**, its **reference** (the customer's PO), its **total** ("339" / "$339.00") and the
words of its lines; drafts (no number yet) are found by contact, reference and amount and say
"Draft". The result opens the invoice; it follows ``sales.invoices.view`` and the
``accounting.sales_invoices.read`` feature.
"""

from __future__ import annotations

import re
from typing import Any

from django.utils.translation import gettext as _

from numo9.search.registry import Doc

VIEW = "sales.invoices.view"
READ = "accounting.sales_invoices.read"


def invoice_url(invoice: Any) -> str:
    # The email page is the invoice's screen until the editor (D-03a-T13) takes this URL over.
    return f"/o/{invoice.organisation.public_id}/sales/invoices/{invoice.public_id}/email"


def _words(value: str) -> str:
    """``PO-77812`` → ``PO 77812``: the text parser reads ``-77812`` as a negative number, so the
    parts are indexed as words too ("PO-77812" and "77812" then find it)."""
    return re.sub(r"[-_/.#]+", " ", value).strip()


def invoice_document(invoice: Any) -> Doc | None:
    if invoice.deleted_at is not None:
        return None
    contact = invoice.contact.display_name if invoice.contact_id else ""
    name = invoice.number or _("Draft invoice")
    return Doc(
        title=" — ".join(x for x in (str(name), contact) if x),
        subtitle=" · ".join(str(x) for x in (invoice.get_status_display(), invoice.reference) if x),
        code=invoice.number,
        body=" ".join(
            x
            for x in (
                invoice.reference,
                _words(invoice.reference),
                *(line.description for line in invoice.lines.all() if line.description),
            )
            if x
        )
        if invoice.pk
        else _words(invoice.reference),
        amount=invoice.total,
        date=invoice.date,
        url=invoice_url(invoice),
        permission_key=VIEW,
        feature_key=READ,
    )


def register_sales_search() -> None:
    from numo9.search.registry import register_dependent, register_provider

    from .models import Invoice, InvoiceLine

    register_provider(Invoice, invoice_document)
    register_dependent(InvoiceLine, lambda line: line.document)
