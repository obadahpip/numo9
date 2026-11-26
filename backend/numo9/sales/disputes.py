"""Disputed invoices and customers who opted out of reminders (D-07-T07).

- ``set_disputed(invoice, disputed, user, reason="")`` — flag a posted invoice as disputed by
  the customer (with what is disputed) or resolve the dispute; the change is audited (the
  invoice is an audited record) — reminders and late fees (D-07-T06) stop while it is disputed;
- ``Contact.reminders_opt_out`` — the customer asked for no invoice reminders;
- ``reminder_block(invoice)`` — why no reminder may go out for the invoice, or ``None``:
  ``disputed`` or ``opted_out`` (checked first by every reminder: the eligibility engine and
  the daily job, D-07-T03/T04, and any manual send).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError
from numo9.tenancy.context import org_context

from .models import POSTED_STATUSES, Invoice, InvoiceStatus

DISPUTED = "disputed"
OPTED_OUT = "opted_out"


class DisputeRefused(LedgerError):
    """A dispute change the rules refuse (``code`` names the rule)."""


def set_disputed(
    invoice: Invoice, disputed: bool, user: Any = None, *, reason: str = ""
) -> Invoice:
    """Flag or resolve the invoice's dispute (module docstring); returns the invoice."""
    text = " ".join((reason or "").split())
    with org_context(invoice.organisation), transaction.atomic():
        locked: Invoice = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
        if locked.status not in POSTED_STATUSES or locked.status == InvoiceStatus.VOID:
            raise DisputeRefused(
                _("Only a posted invoice that isn't void can be disputed."),
                code="sales.dispute.not_posted",
            )
        if disputed and not text:
            raise DisputeRefused(
                _("Say what the customer disputes."), code="sales.dispute.reason_required"
            )
        locked.disputed = disputed
        locked.disputed_at = timezone.now() if disputed else None
        locked.dispute_reason = text if disputed else ""
        locked.save(update_fields=["disputed", "disputed_at", "dispute_reason", "updated_at"])
        invoice.disputed = locked.disputed
        invoice.disputed_at = locked.disputed_at
        invoice.dispute_reason = locked.dispute_reason
        return locked


def reminder_block(invoice: Invoice) -> str | None:
    """``disputed`` / ``opted_out`` — why no reminder may be sent — or ``None``."""
    if invoice.disputed:
        return DISPUTED
    if getattr(invoice.contact, "reminders_opt_out", False):
        return OPTED_OUT
    return None
