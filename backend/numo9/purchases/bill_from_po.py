"""Bill from a purchase order or a goods receipt (E-02-T08), and the match panel's data.

``bill_from_purchase_order(order, user, receipt=None)`` → a **draft bill** for the PO's supplier
with one line per PO line still to bill, linked to it (``po_line``), at the PO's price, account,
tax code, discount and tracking:

- quantity = **received − billed** (what has arrived and isn't on a bill yet); a line with nothing
  received yet is left out — unless nothing at all has been received (a service PO): then
  ordered − billed;
- from one receipt: that receipt's quantities (less what is already billed on those lines).

Billed quantities (``PurchaseOrderLine.quantity_billed``) move when a bill is approved and come
back when it is voided (``apply_billed``); every line billed in full makes the PO **Billed**.

``match_panel(bill)`` — per bill line linked to a PO line: ordered, received, billed on other
bills, this bill's quantity and price against the PO's, and a status — ``green`` (quantity within
what was received and not billed yet, price equal), ``amber`` (within the receipt tolerance of
the organisation settings, E-01), ``red`` (beyond it: over-billed or over-priced). Approving a
bill with an amber or red line needs ``with_variance`` ("Approve with variance", E-02-T13).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from numo9.tenancy.context import org_context

from .models import (
    Bill,
    BillLine,
    GoodsReceipt,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)

ZERO = Decimal("0")
BILLABLE = (
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
    PurchaseOrderStatus.RECEIVED,
)


class BillFromOrderRefused(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _to_bill(order: PurchaseOrder, receipt: GoodsReceipt | None) -> list[tuple[Any, Decimal]]:
    lines = list(order.lines.order_by("position", "pk"))
    if receipt is not None:
        received = {r.po_line_id: Decimal(r.quantity) for r in receipt.lines.all()}
        return [
            (line, min(received[line.pk], Decimal(line.quantity_received) - line.quantity_billed))
            for line in lines
            if line.pk in received
        ]
    nothing_received = all(Decimal(line.quantity_received) == 0 for line in lines)
    out = []
    for line in lines:
        base = Decimal(line.quantity if nothing_received else line.quantity_received)
        out.append((line, base - Decimal(line.quantity_billed)))
    return out


def bill_from_purchase_order(
    order: PurchaseOrder, user: Any, *, receipt: GoodsReceipt | None = None
) -> Bill:
    from .bills import recalculate

    person = user if getattr(user, "is_authenticated", False) else None
    with org_context(order.organisation), transaction.atomic():
        if order.status not in BILLABLE:
            raise BillFromOrderRefused(
                _("Only an approved purchase order can be billed."),
                code="purchases.bill.po_not_billable",
            )
        if receipt is not None and (receipt.purchase_order_id != order.pk or receipt.reversed_at):
            raise BillFromOrderRefused(
                _("That receipt isn't one of this purchase order's."),
                code="purchases.bill.receipt_mismatch",
            )
        wanted = [(line, qty) for line, qty in _to_bill(order, receipt) if qty > 0]
        if not wanted:
            raise BillFromOrderRefused(
                _("Everything received on this purchase order is billed already."),
                code="purchases.bill.nothing_to_bill",
            )
        bill = Bill(
            organisation=order.organisation,
            contact=order.contact,
            date=order.date if receipt is None else receipt.date,
            terms=order.terms,
            reference=order.number,
            currency=order.currency,
            tax_mode=order.tax_mode,
            ship_to_country=order.ship_to_country,
            ship_to_province=order.ship_to_province,
            purchase_order=order,
            created_by=person,
        )
        from numo9.documents.due_dates import resolve

        bill.due_date = resolve(bill.date, order.terms).due if order.terms else bill.date
        bill.save()
        for position, (line, quantity) in enumerate(wanted):
            BillLine(
                organisation=order.organisation,
                document=bill,
                position=position,
                item=line.item,
                description=line.description,
                quantity=quantity,
                unit_price=line.unit_price,
                discount_type=line.discount_type,
                discount_value=line.discount_value,
                account=line.account,
                tax_code=line.tax_code,
                tracking=dict(line.tracking or {}),
                po_line=line,
            ).save()
        return recalculate(bill)


def apply_billed(bill: Bill, sign: int) -> None:
    """Add (``sign`` 1, approval) or take back (−1, void) the bill's quantities on its PO lines;
    the PO becomes Billed when every line is billed in full, and goes back when not."""
    from .receipts import refresh_status

    orders: set[int] = set()
    for line in bill.lines.filter(po_line__isnull=False).select_related("po_line"):
        assert line.po_line_id is not None  # noqa: S101 — filtered above
        po_line = PurchaseOrderLine._base_manager.select_for_update().get(pk=line.po_line_id)
        po_line.quantity_billed = max(
            Decimal(po_line.quantity_billed) + sign * Decimal(line.quantity), ZERO
        )
        po_line.save(update_fields=["quantity_billed", "updated_at"])
        orders.add(po_line.document_id)
    for order in PurchaseOrder._base_manager.filter(pk__in=orders):
        lines = list(order.lines.all())
        full = bool(lines) and all(
            Decimal(line.quantity_billed) >= Decimal(line.quantity) for line in lines
        )
        if full and order.status in BILLABLE:
            order.status = PurchaseOrderStatus.BILLED
            order.save(update_fields=["status", "updated_at"])
        elif not full and order.status == PurchaseOrderStatus.BILLED:
            order.status = PurchaseOrderStatus.APPROVED
            order.save(update_fields=["status", "updated_at"])
            refresh_status(order)


def line_status(over_pct: Decimal, price_diff_pct: Decimal, tolerance: Decimal) -> str:
    """``green`` — quantity within what can be billed and the PO's price; ``amber`` — over either
    by no more than the tolerance; ``red`` — beyond it."""
    if over_pct <= 0 and price_diff_pct == 0:
        return "green"
    if over_pct <= tolerance and price_diff_pct <= tolerance:
        return "amber"
    return "red"


def match_panel(bill: Bill) -> list[dict[str, Any]]:
    with org_context(bill.organisation):
        return _match_panel(bill)


def _match_panel(bill: Bill) -> list[dict[str, Any]]:
    from .receipts import _tolerance

    tolerance, _mode = _tolerance(bill.organisation)
    rows: list[dict[str, Any]] = []
    lines = bill.lines.filter(po_line__isnull=False).select_related("po_line__document")
    for line in lines.order_by("position", "pk"):
        po_line = line.po_line
        assert po_line is not None  # noqa: S101 — filtered above
        others = sum(
            (
                Decimal(other.quantity)
                for other in BillLine.objects.filter(po_line=po_line)
                .exclude(document=bill)
                .exclude(document__status__in=("void", "draft"))
                .filter(document__deleted_at__isnull=True)
            ),
            ZERO,
        )
        received = Decimal(po_line.quantity_received)
        ordered = Decimal(po_line.quantity)
        # Nothing received at all on the PO (a service order): match against what was ordered.
        basis = (
            received if po_line.document.lines.filter(quantity_received__gt=0).exists() else ordered
        )
        quantity = Decimal(line.quantity)
        over = quantity - (basis - others)
        po_price = Decimal(po_line.unit_price)
        price = Decimal(line.unit_price)
        diff = (
            abs(price - po_price) * 100 / po_price
            if po_price
            else (ZERO if price == 0 else Decimal(100))
        )
        over_pct = ZERO if over <= 0 else (over * 100 / basis if basis else Decimal(100))
        status = line_status(over_pct, diff, tolerance)
        rows.append(
            {
                "line": str(line.public_id),
                "po_line": str(po_line.public_id),
                "po": po_line.document.number,
                "description": line.description,
                "ordered": f"{ordered:.4f}",
                "received": f"{received:.4f}",
                "billed_elsewhere": f"{others:.4f}",
                "quantity": f"{quantity:.4f}",
                "po_price": f"{po_price:.4f}",
                "price": f"{price:.4f}",
                "quantity_over": f"{max(over, ZERO):.4f}",
                "price_difference_pct": f"{diff:.2f}",
                "status": status,
            }
        )
    return rows


def has_variance(bill: Bill) -> bool:
    return any(row["status"] != "green" for row in match_panel(bill))
