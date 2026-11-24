"""Invoices and the customer's credit limit (D-03a-T06; the rules: B-01-T13 ``contacts.credit``).

- **Exposure** — what a customer owes from invoices: the amount due of every posted invoice not
  paid or void (approved, sent, partially paid), registered as the ``sales.invoices`` exposure
  source; the invoice being checked is left out (``exclude`` = its id) so it isn't counted twice.
- ``invoice_credit(invoice)`` — the check for the editor's banner (D-03a-T16), nothing changed:
  ``within`` / ``no_limit``, ``warn`` (a warning), ``block`` (refused unless an approved override
  covers it), ``override``.
- **At approval** (``approve``, D-03a-T03) ``assert_credit`` runs in the posting transaction: a
  warn-mode customer posts with the warning (``Invoice.credit_warning``, not stored); a
  block-mode customer over the limit is refused (409 ``contact.credit_limit_blocked``) unless an
  override was approved for this invoice — someone with ``contacts.credit_limit.override``, never
  the requester — which is then used up.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import F, Sum

from numo9.contacts.credit import CreditCheck, check_credit, register_exposure

from .models import Invoice, InvoiceStatus

DOCUMENT_TYPE = "invoice"
OPEN = (InvoiceStatus.APPROVED, InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID)


def invoice_exposure(contact: Any, *, exclude: str = "") -> Decimal:
    rows = Invoice.objects.filter(contact=contact, status__in=OPEN, deleted_at__isnull=True)
    if exclude:
        rows = rows.exclude(public_id=exclude) if _is_uuid(exclude) else rows
    owed = rows.aggregate(owed=Sum(F("total") - F("amount_paid")))["owed"]
    return Decimal(owed or 0)


def _is_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


def invoice_credit(invoice: Invoice, total: Decimal | None = None) -> CreditCheck:
    """The credit check of the invoice as it stands (its calculated total unless given)."""
    if total is None:
        from .posting import invoice_preview

        total = invoice_preview(invoice).result.total
    return check_credit(
        invoice.contact,
        total,
        document_type=DOCUMENT_TYPE,
        document_ref=str(invoice.public_id),
    )


def register_invoice_exposure() -> None:
    register_exposure("sales.invoices", invoice_exposure)
