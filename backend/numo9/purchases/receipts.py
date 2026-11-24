"""Goods receipts (E-01-T04, T05): receive against an approved purchase order, partially or in full.

    result = receive(order, user, [(po_line, Decimal("6"))], date=…, notes="…")

- the PO must be approved (or partially received / received — a further delivery); lines must be
  the PO's own, each quantity above zero;
- **tolerance** (organisation settings): a line may receive up to ordered ×
  (1 + ``po_receipt_tolerance_percent`` %) without a word. Beyond it, ``po_over_receipt`` decides:
  ``warn`` — refused with ``purchases.receipt.over_tolerance_confirm`` until the person confirms
  (``confirm_over=True``), then received with the warning; ``block`` — refused
  (``purchases.receipt.over_tolerance``). Untracked items (every Phase 1 item) are received the
  same way: the quantity is recorded, no stock;
- each line's ``quantity_received`` grows; the PO's status follows (``refresh_status``): nothing
  received → Approved, some → **Partially received**, every line in full → **Received**;
- the receipt is audited ``purchases.goodsreceipt.received``; each line of a **tracked** item is
  sent to the stock movement sink (E-01-T05, ``numo9.purchases.stock``) as +quantity.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.tenancy.context import org_context

from .approvals import PurchaseOrderRefused
from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)

RECEIVABLE = (
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
    PurchaseOrderStatus.RECEIVED,
)
#: The statuses ``refresh_status`` may move between (billed, closed and cancelled are kept).
RECEIPT_STATUSES = RECEIVABLE


@dataclass(frozen=True)
class OverReceipt:
    line: str
    ordered: Decimal
    received: Decimal
    allowed: Decimal

    def as_dict(self) -> dict[str, str]:
        return {
            "line": self.line,
            "ordered": f"{self.ordered:.4f}",
            "received": f"{self.received:.4f}",
            "allowed": f"{self.allowed:.4f}",
        }


@dataclass
class ReceiptResult:
    receipt: GoodsReceipt
    warnings: list[OverReceipt] = field(default_factory=list)


class OverReceiptRefused(PurchaseOrderRefused):
    """Receiving more than the tolerance: ``over`` lists the lines."""

    def __init__(self, message: str, *, code: str, over: list[OverReceipt]) -> None:
        super().__init__(message, code=code)
        self.over = over


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def refresh_status(order: PurchaseOrder) -> PurchaseOrder:
    """Approved / Partially received / Received from the lines (other statuses are kept)."""
    if order.status not in RECEIPT_STATUSES:
        return order
    lines = list(order.lines.all())
    received = [Decimal(line.quantity_received) for line in lines]
    if lines and all(r >= Decimal(line.quantity) for r, line in zip(received, lines, strict=True)):
        status = PurchaseOrderStatus.RECEIVED
    elif any(r > 0 for r in received):
        status = PurchaseOrderStatus.PARTIALLY_RECEIVED
    else:
        status = PurchaseOrderStatus.APPROVED
    if status != order.status:
        order.status = status
        order.save(update_fields=["status", "updated_at"])
    return order


def _tolerance(organisation: Any) -> tuple[Decimal, str]:
    from numo9.orgsettings.service import get_settings

    settings = get_settings(organisation)
    return Decimal(settings.po_receipt_tolerance_percent), str(settings.po_over_receipt)


def receive(
    order: PurchaseOrder,
    user: Any,
    quantities: Sequence[tuple[PurchaseOrderLine, Decimal]],
    *,
    date: dt.date | None = None,
    notes: str = "",
    confirm_over: bool = False,
) -> ReceiptResult:
    from numo9.audit import service as audit
    from numo9.orgsettings.locks import local_date

    from .stock import Movement, sink, tracked

    person = _person(user)
    with org_context(order.organisation), transaction.atomic():
        locked = PurchaseOrder._base_manager.select_for_update().get(pk=order.pk)
        if locked.status not in RECEIVABLE:
            raise PurchaseOrderRefused(
                _("Only an approved purchase order can be received: %(order)s is %(status)s."),
                code="purchases.receipt.not_receivable",
                params={
                    "order": str(locked),
                    "status": str(PurchaseOrderStatus(locked.status).label).lower(),
                },
            )
        wanted = [(line, Decimal(qty)) for line, qty in quantities if Decimal(qty) != 0]
        if not wanted:
            raise PurchaseOrderRefused(
                _("Enter the quantity received on at least one line."),
                code="purchases.receipt.empty",
            )
        lines = {
            line.pk: line
            for line in PurchaseOrderLine.objects.select_for_update().filter(document=locked)
        }
        percent, mode = _tolerance(locked.organisation)
        over: list[OverReceipt] = []
        for line, qty in wanted:
            if line.pk not in lines:
                raise PurchaseOrderRefused(
                    _("A line isn't on %(order)s."),
                    code="purchases.receipt.foreign_line",
                    params={"order": str(locked)},
                )
            if qty < 0:
                raise PurchaseOrderRefused(
                    _("Quantities received can't be negative: reverse the receipt instead."),
                    code="purchases.receipt.negative",
                )
            current = lines[line.pk]
            ordered = Decimal(current.quantity)
            after = Decimal(current.quantity_received) + qty
            allowed = ordered * (1 + percent / 100)
            if after > allowed:
                over.append(
                    OverReceipt(current.description or str(current), ordered, after, allowed)
                )
        if over and mode == "block":
            raise OverReceiptRefused(
                _("More than ordered (beyond the tolerance) can't be received."),
                code="purchases.receipt.over_tolerance",
                over=over,
            )
        if over and not confirm_over:
            raise OverReceiptRefused(
                _("This receives more than ordered: confirm to receive it anyway."),
                code="purchases.receipt.over_tolerance_confirm",
                over=over,
            )
        receipt = GoodsReceipt(
            organisation=locked.organisation,
            purchase_order=locked,
            date=date or local_date(locked.organisation, timezone.now()),
            received_by=person,
            notes=notes.strip(),
        )
        receipt.save()
        movements: list[Movement] = []
        for line, qty in wanted:
            current = lines[line.pk]
            GoodsReceiptLine(
                organisation=locked.organisation, receipt=receipt, po_line=current, quantity=qty
            ).save()
            current.quantity_received = Decimal(current.quantity_received) + qty
            current.save(update_fields=["quantity_received", "updated_at"])
            if tracked(current):
                movements.append(Movement.of(receipt, current, qty))
        refresh_status(locked)
        audit.record(
            "purchases.goodsreceipt.received",
            obj=receipt,
            meta={
                "purchase_order": locked.number,
                "lines": {str(lines[line.pk].public_id): f"{qty:.4f}" for line, qty in wanted},
                "over_tolerance": [o.as_dict() for o in over],
            },
            actor=person,
        )
        if movements:
            sink().record(movements)
        return ReceiptResult(receipt, over)
