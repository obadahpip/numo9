"""Purchase order approval (E-01-T02, T03), with the A-03 purchase-order approval limits.

- ``recalculate(order)`` — the calculator's figures on the PO and its lines (purchase side,
  server-authoritative; what the editor does on save).
- ``approve(order, user)`` — approve a draft or a PO awaiting approval: the total must be within
  the person's **purchase-order approval limit** (A-03 ``assert_can_approve``: no limit → no
  approval; above it → 403 ``approval.limit_exceeded`` naming who may). Whoever wrote or submitted
  a PO waiting for approval can't approve it. Approval takes the number (``PO-0001``), records who
  and when and the **approved total**, and audits ``purchases.purchaseorder.approved``.
- ``submit_or_approve(order, user)`` — the editor's Approve: approves at once when the total is
  within the person's limit, otherwise sends the PO to Awaiting approval (who, when).
- ``reapproval_needed(order)`` / ``revise(order, user)`` (E-01-T03) — after an approved PO is
  edited: its total above the approved total → back to **Awaiting approval** (the number is
  kept; audited ``purchases.purchaseorder.reapproval``); equal or lower stays approved.
- ``cancel(order, user)`` / ``close(order, user)`` (E-01-T10) — a draft, awaiting or approved PO
  with nothing received or billed is **Cancelled**; one with receipts or bills is **Closed** (its
  outstanding quantities no longer commit anything). Audited ``purchases.purchaseorder.cancelled``
  / ``.closed``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError
from numo9.rbac.approvals import assert_can_approve, can_approve
from numo9.rbac.models import ApprovalDocumentType
from numo9.tenancy.context import org_context

from .models import PurchaseOrder, PurchaseOrderStatus
from .numbering import assign_number

DOC_TYPE = ApprovalDocumentType.PURCHASE_ORDER
APPROVABLE = (PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.AWAITING_APPROVAL)
#: Statuses an approved PO's edit can send back to Awaiting approval (nothing received yet
#: or partly: the outstanding part is still a commitment).
REVISABLE = (PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.PARTIALLY_RECEIVED)


class PurchaseOrderRefused(LedgerError):
    """A purchase-order action the rules refuse (``code`` names the rule)."""


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def recalculate(order: PurchaseOrder) -> PurchaseOrder:
    from numo9.documents.posting import PreviewLine, result_for

    with org_context(order.organisation), transaction.atomic():
        lines = list(order.lines.select_related("account", "tax_code").order_by("position", "pk"))
        result = result_for(
            "purchase_order",
            [
                PreviewLine(
                    account=line.account,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_type=line.discount_type,
                    discount_value=line.discount_value,
                    tax_code=line.tax_code,
                    description=line.description,
                    tracking=dict(line.tracking or {}),
                )
                for line in lines
            ],
            tax_mode=order.tax_mode,
            discount_type=order.discount_type,
            discount_value=order.discount_value,
        )
        for line, figures in zip(lines, result.lines, strict=True):
            line.net = figures.exclusive
            line.tax_amount = figures.tax
            line.amount = figures.net
            line.save(update_fields=["net", "tax_amount", "amount", "updated_at"])
        order.subtotal = result.subtotal
        order.discount_total = result.discount_total
        order.tax_total = result.tax_total
        order.total = result.total
        order.save(update_fields=["subtotal", "discount_total", "tax_total", "total", "updated_at"])
        return order


def _locked(order: PurchaseOrder) -> PurchaseOrder:
    return PurchaseOrder._base_manager.select_for_update().get(pk=order.pk)


def approve(order: PurchaseOrder, user: Any) -> PurchaseOrder:
    from numo9.audit import service as audit

    person = _person(user)
    with org_context(order.organisation), transaction.atomic():
        locked = _locked(order)
        if locked.status not in APPROVABLE:
            raise PurchaseOrderRefused(
                _("%(order)s isn't waiting for approval."),
                code="purchases.po.not_approvable",
                params={"order": str(locked)},
            )
        if not locked.lines.exists() or Decimal(locked.total) <= 0:
            raise PurchaseOrderRefused(
                _("Add at least one line with an amount before approving."),
                code="purchases.po.empty",
            )
        if locked.status == PurchaseOrderStatus.AWAITING_APPROVAL:
            authors = {locked.created_by_id, locked.submitted_by_id} - {None}
            if getattr(person, "pk", None) in authors:
                raise PurchaseOrderRefused(
                    _("You wrote or submitted this purchase order: someone else must approve it."),
                    code="purchases.po.self_approval",
                )
        assert_can_approve(
            person,
            DOC_TYPE,
            Decimal(locked.total),
            organisation=locked.organisation,
            exclude=[p for p in (locked.created_by, locked.submitted_by) if p is not None],
        )
        assign_number(locked)
        previous = locked.status
        locked.status = PurchaseOrderStatus.APPROVED
        locked.approved_by = person
        locked.approved_at = timezone.now()
        locked.approved_total = locked.total
        locked.version += 1
        locked.save()
        from .receipts import refresh_status

        refresh_status(locked)  # re-approved after receipts: partially received again
        audit.record(
            "purchases.purchaseorder.approved",
            obj=locked,
            changes={"status": [previous, PurchaseOrderStatus.APPROVED]},
            meta={"number": locked.number, "total": f"{locked.total:.2f}"},
            actor=person,
        )
        return locked


def submit(order: PurchaseOrder, user: Any) -> PurchaseOrder:
    with org_context(order.organisation), transaction.atomic():
        locked = _locked(order)
        if locked.status != PurchaseOrderStatus.DRAFT:
            raise PurchaseOrderRefused(
                _("%(order)s isn't a draft."),
                code="purchases.po.not_draft",
                params={"order": str(locked)},
            )
        locked.status = PurchaseOrderStatus.AWAITING_APPROVAL
        locked.submitted_by = _person(user)
        locked.submitted_at = timezone.now()
        locked.save()
        return locked


def submit_or_approve(order: PurchaseOrder, user: Any) -> PurchaseOrder:
    if can_approve(_person(user), DOC_TYPE, Decimal(order.total), organisation=order.organisation):
        return approve(order, user)
    return submit(order, user)


def reapproval_needed(order: PurchaseOrder) -> bool:
    return (
        order.status in REVISABLE
        and order.approved_total is not None
        and Decimal(order.total) > Decimal(order.approved_total)
    )


def revise(order: PurchaseOrder, user: Any) -> PurchaseOrder:
    """After an approved PO's lines changed: recalculate; a higher total needs approval again."""
    from numo9.audit import service as audit

    order = recalculate(order)
    with org_context(order.organisation), transaction.atomic():
        locked = _locked(order)
        if not reapproval_needed(locked):
            return locked
        previous = locked.status
        locked.status = PurchaseOrderStatus.AWAITING_APPROVAL
        locked.submitted_by = _person(user)
        locked.submitted_at = timezone.now()
        locked.version += 1
        locked.save()
        audit.record(
            "purchases.purchaseorder.reapproval",
            obj=locked,
            changes={"status": [previous, PurchaseOrderStatus.AWAITING_APPROVAL]},
            meta={
                "number": locked.number,
                "approved_total": f"{locked.approved_total:.2f}",
                "total": f"{locked.total:.2f}",
            },
            actor=_person(user),
        )
        return locked


#: Statuses a PO can be closed from (its outstanding quantities dropped).
CLOSABLE = (
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
    PurchaseOrderStatus.RECEIVED,
)
CANCELLABLE = (*APPROVABLE, *CLOSABLE)


def _end(order: PurchaseOrder, user: Any, wanted: str) -> PurchaseOrder:
    """Cancel (``wanted`` cancelled) or close a PO. A PO with anything received or billed is
    **closed** instead of cancelled: what arrived stays on record, the outstanding is dropped
    (E-01 business rule "cancelling a partially received PO closes outstanding")."""
    from numo9.audit import service as audit

    person = _person(user)
    allowed = CANCELLABLE if wanted == PurchaseOrderStatus.CANCELLED else CLOSABLE
    with org_context(order.organisation), transaction.atomic():
        locked = _locked(order)
        if locked.status not in allowed:
            raise PurchaseOrderRefused(
                _("%(order)s is %(status)s: it can't be cancelled or closed."),
                code="purchases.po.not_closable",
                params={
                    "order": str(locked),
                    "status": str(PurchaseOrderStatus(locked.status).label).lower(),
                },
            )
        touched = locked.lines.filter(
            models.Q(quantity_received__gt=0) | models.Q(quantity_billed__gt=0)
        ).exists()
        status = PurchaseOrderStatus.CLOSED if touched else wanted
        previous = locked.status
        locked.status = status
        now = timezone.now()
        if status == PurchaseOrderStatus.CLOSED:
            locked.closed_at = now
        else:
            locked.cancelled_at = now
        locked.version += 1
        locked.save()
        audit.record(
            f"purchases.purchaseorder.{status}",
            obj=locked,
            changes={"status": [previous, status]},
            meta={"number": locked.number},
            actor=person,
        )
        return locked


def cancel(order: PurchaseOrder, user: Any) -> PurchaseOrder:
    """Cancel a PO; one with receipts or bills is closed instead (E-01-T10)."""
    return _end(order, user, PurchaseOrderStatus.CANCELLED)


def close(order: PurchaseOrder, user: Any) -> PurchaseOrder:
    """Close an approved PO: nothing more to receive or bill on it (E-01-T10)."""
    return _end(order, user, PurchaseOrderStatus.CLOSED)
