"""The payment status of a posted invoice (D-05-T07): **Partially paid** / **Paid**, from its
**current revision** (D-03b-T12 ``InvoiceCurrent``).

``payment_status(invoice)`` is what the invoice's status should be, ``refresh_status(invoice)``
writes it (call it in the transaction that changed the money, with the invoice row locked):

- what covers the invoice = payments and customer credits allocated + credit notes applied;
- covered ≥ the current revision's total → **Paid**; something covered but less → **Partially
  paid**; nothing → back to **Sent** if it was ever sent, else **Approved**;
- a draft, an invoice awaiting approval and a void invoice keep their status.

It runs after every allocation and removal of one (D-05-T02, T05), every credit used on an
invoice (D-05-T04) and every revision (D-03b): a revision that raises a paid invoice's total
makes it Partially paid again; one that lowers a partially paid invoice to what is paid makes
it Paid.
"""

from __future__ import annotations

from typing import Any

from .models import Invoice, InvoiceStatus

#: Statuses this module moves between (the others are left alone).
PAYMENT_STATUSES = (
    InvoiceStatus.APPROVED,
    InvoiceStatus.SENT,
    InvoiceStatus.PARTIALLY_PAID,
    InvoiceStatus.PAID,
)


def payment_status(invoice: Invoice) -> str:
    """The status the invoice's current revision and its allocations give (module docstring)."""
    from .current import ZERO, current_of

    if invoice.status not in PAYMENT_STATUSES:
        return str(invoice.status)
    current = current_of(invoice)
    if current is None:  # pragma: no cover — a payment status means a posted invoice
        return str(invoice.status)
    covered = current.paid + current.credited
    if covered >= current.total > ZERO:
        return InvoiceStatus.PAID
    if covered > ZERO:
        return InvoiceStatus.PARTIALLY_PAID
    return InvoiceStatus.SENT if invoice.sent_at else InvoiceStatus.APPROVED


def refresh_status(invoice: Invoice | Any) -> str:
    """Write the payment status on the invoice row (and the instance given); returns it."""
    from numo9.tenancy.context import org_context

    with org_context(invoice.organisation):
        row: Invoice = Invoice._base_manager.get(pk=invoice.pk)
        status = payment_status(row)
        if status != row.status:
            row.status = status
            row.save(update_fields=["status"])
        invoice.status = status
        return status
