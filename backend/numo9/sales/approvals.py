"""Invoice approval rule (D-03a-T05): optional, per organisation, **never product-gated** —
every package with invoices can use it (gap-6).

An invoice needs approval when:

- **threshold** — the organisation set ``invoice_approval_threshold`` and the total is at or above
  it; or
- **limit** — the person approving has an approval limit for invoices (A-03, by user or role)
  and the total is above it.

``approval_needed(invoice, user)`` says which (or ``None``). ``submit_or_approve(invoice, user)`` —
what the editor's Approve does: posts at once when no approval is needed (D-03a-T03), otherwise
sends the invoice to Awaiting approval (who submitted it, when). ``approve_waiting(invoice,
user)`` — an approver posts it: never the person who submitted or wrote it, and within their own
invoice limit when they have one (``approval.limit_exceeded`` names who may).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.orgsettings.service import get_settings
from numo9.rbac.approvals import assert_can_approve, effective_limit
from numo9.rbac.models import ApprovalDocumentType
from numo9.tenancy.context import org_context

from .models import Invoice, InvoiceStatus
from .posting import InvoiceRefused, approve, invoice_preview


def approval_needed(invoice: Invoice, user: Any) -> str | None:
    total = invoice_preview(invoice).result.total
    threshold = get_settings(invoice.organisation).invoice_approval_threshold
    if threshold is not None and total >= Decimal(threshold):
        return "threshold"
    limit = effective_limit(user, ApprovalDocumentType.INVOICE, organisation=invoice.organisation)
    if limit is not None and total > limit:
        return "limit"
    return None


def submit_or_approve(invoice: Invoice, user: Any) -> Invoice:
    """Approve now, or route to Awaiting approval (module docstring)."""
    with org_context(invoice.organisation), transaction.atomic():
        locked = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
        if locked.status != InvoiceStatus.DRAFT:
            raise InvoiceRefused(
                _("%(invoice)s isn't a draft."),
                code="sales.invoice.not_draft",
                params={"invoice": str(locked)},
            )
        if approval_needed(locked, user) is None:
            return approve(locked, user)
        locked.status = InvoiceStatus.AWAITING_APPROVAL
        locked.submitted_by = user if getattr(user, "is_authenticated", False) else None
        locked.submitted_at = timezone.now()
        locked.save()
        return locked


def approve_waiting(invoice: Invoice, user: Any) -> Invoice:
    """An approver approves and posts an invoice awaiting approval."""
    with org_context(invoice.organisation), transaction.atomic():
        locked = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
        if locked.status != InvoiceStatus.AWAITING_APPROVAL:
            raise InvoiceRefused(
                _("%(invoice)s isn't waiting for approval."),
                code="sales.invoice.not_awaiting",
                params={"invoice": str(locked)},
            )
        authors = {locked.created_by_id, locked.submitted_by_id} - {None}
        if getattr(user, "pk", None) in authors:
            raise InvoiceRefused(
                _("You wrote or submitted this invoice: someone else must approve it."),
                code="sales.invoice.self_approval",
            )
        total = invoice_preview(locked).result.total
        if effective_limit(user, ApprovalDocumentType.INVOICE, organisation=locked.organisation):
            assert_can_approve(
                user,
                ApprovalDocumentType.INVOICE,
                total,
                organisation=locked.organisation,
                exclude=[p for p in (locked.created_by, locked.submitted_by) if p is not None],
            )
        return approve(locked, user)
