"""3-way match engine (E-01-T07): per purchase order line, the PO (quantity and price) against
what was received (goods receipts) and what was billed (bills).

One rule, used everywhere — the bill's match panel (E-02-T13), "approve with variance"
(E-02-T08) and the PO's own match view (``GET purchase-orders/<id>/match``, E-01-T10):

- **quantity**: the quantity billed (this bill plus every other bill on the line that isn't a
  draft or void) is compared with what was **ordered** and with what was **received**. Billing
  more than either is a variance — a bill for 12 against a PO for 10 is flagged even when 12
  were received (an over-receipt confirmed at the dock is still more than was ordered);
- **price**: the bill's unit price against the PO's, as a percentage of the PO price (a PO price
  of zero: any price is 100 %);
- **tolerance** (organisation settings): ``po_match_quantity_tolerance_percent`` and
  ``po_match_price_tolerance_percent``; empty → the over-receipt tolerance
  (``po_receipt_tolerance_percent``, E-01-T04);
- each check is **green** (no variance), **amber** (a variance within the tolerance) or **red**
  (beyond it); a line takes its worst check. Amber and red need an approver ("approve with
  variance");
- **bill before receipt** is allowed: when nothing at all has been received on the PO (a service
  order, or goods not arrived yet), the quantity is matched against what was ordered only and the
  line says ``received_later`` (match pending the receipt) — it is not a variance by itself.

``evaluate(figures, tolerance)`` is the pure rule (parameterised unit tests);
``tolerance_for(organisation)`` reads the settings; ``match_order(order)`` is the PO view: per
line ordered / received / outstanding / billed / pending (on bills not approved yet) / to bill,
the bills on it with their quantity, price and result, and the line's result.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from numo9.tenancy.context import org_context

ZERO = Decimal("0")
HUNDRED = Decimal("100")
GREEN, AMBER, RED = "green", "amber", "red"
_RANK = {GREEN: 0, AMBER: 1, RED: 2}

#: Flags a line can carry.
OVER_ORDERED = "over_ordered"
OVER_RECEIVED = "over_received"
PRICE = "price"
RECEIVED_LATER = "received_later"

#: Bill statuses whose quantities count as billed or pending for a match.
_NOT_COUNTED = ("void", "draft")


@dataclass(frozen=True)
class Tolerance:
    quantity: Decimal = ZERO
    price: Decimal = ZERO


@dataclass(frozen=True)
class Figures:
    """One PO line against one bill quantity and price.

    ``billed`` — the quantity billed in all (the bill being matched plus the other bills);
    ``received_any`` — something was received on the PO (any line): otherwise the receipt check
    waits (``received_later``)."""

    ordered: Decimal
    received: Decimal
    billed: Decimal
    po_price: Decimal
    price: Decimal
    received_any: bool = True


@dataclass(frozen=True)
class LineMatch:
    status: str
    flags: tuple[str, ...]
    quantity_over: Decimal
    quantity_over_pct: Decimal
    price_difference_pct: Decimal

    @property
    def received_later(self) -> bool:
        return RECEIVED_LATER in self.flags

    @property
    def variance(self) -> bool:
        return self.status != GREEN


def grade(pct: Decimal, tolerance: Decimal) -> str:
    """No variance → green; a variance up to the tolerance → amber; beyond it → red."""
    if pct <= 0:
        return GREEN
    return AMBER if pct <= tolerance else RED


def worst(*statuses: str) -> str:
    return max(statuses, key=lambda s: _RANK[s], default=GREEN)


def _over(billed: Decimal, basis: Decimal) -> tuple[Decimal, Decimal]:
    over = billed - basis
    if over <= 0:
        return ZERO, ZERO
    return over, (over * HUNDRED / basis if basis else HUNDRED)


def price_difference(po_price: Decimal, price: Decimal) -> Decimal:
    if po_price:
        return abs(price - po_price) * HUNDRED / abs(po_price)
    return ZERO if price == 0 else HUNDRED


def evaluate(figures: Figures, tolerance: Tolerance) -> LineMatch:
    flags: list[str] = []
    ordered_over, ordered_pct = _over(figures.billed, figures.ordered)
    statuses = [grade(ordered_pct, tolerance.quantity)]
    if ordered_over:
        flags.append(OVER_ORDERED)
    over, over_pct = ordered_over, ordered_pct
    if figures.received_any:
        received_over, received_pct = _over(figures.billed, figures.received)
        statuses.append(grade(received_pct, tolerance.quantity))
        if received_over:
            flags.append(OVER_RECEIVED)
        if received_over > over:
            over, over_pct = received_over, received_pct
    else:
        flags.append(RECEIVED_LATER)
    diff = price_difference(figures.po_price, figures.price)
    statuses.append(grade(diff, tolerance.price))
    if diff:
        flags.append(PRICE)
    return LineMatch(worst(*statuses), tuple(flags), over, over_pct, diff)


def tolerance_for(organisation: Any) -> Tolerance:
    from numo9.orgsettings.service import get_settings

    settings = get_settings(organisation)
    receipt = Decimal(settings.po_receipt_tolerance_percent)
    quantity = settings.po_match_quantity_tolerance_percent
    price = settings.po_match_price_tolerance_percent
    return Tolerance(
        quantity=receipt if quantity is None else Decimal(quantity),
        price=receipt if price is None else Decimal(price),
    )


def _q(value: Decimal) -> str:
    return f"{value:.4f}"


def match_order(order: Any) -> dict[str, Any]:
    """The PO's 3-way match: every line, its receipts and bills, and the result."""
    with org_context(order.organisation):
        return _match_order(order)


def _match_order(order: Any) -> dict[str, Any]:
    from .models import BillLine

    tolerance = tolerance_for(order.organisation)
    lines = list(order.lines.order_by("position", "pk"))
    received_any = any(Decimal(line.quantity_received) > 0 for line in lines)
    bill_lines = (
        BillLine.objects.filter(po_line__document=order, document__deleted_at__isnull=True)
        .exclude(document__status="void")
        .select_related("document")
        .order_by("document__date", "document_id", "position", "pk")
    )
    by_line: dict[int, list[Any]] = {}
    for bill_line in bill_lines:
        assert bill_line.po_line_id is not None  # noqa: S101 — filtered above
        by_line.setdefault(bill_line.po_line_id, []).append(bill_line)
    rows: list[dict[str, Any]] = []
    for line in lines:
        ordered = Decimal(line.quantity)
        received = Decimal(line.quantity_received)
        po_price = Decimal(line.unit_price)
        on_line = by_line.get(line.pk, [])
        counted = [b for b in on_line if b.document.status not in _NOT_COUNTED]
        billed = sum((Decimal(b.quantity) for b in counted), ZERO)
        approved = Decimal(line.quantity_billed)
        bills: list[dict[str, Any]] = []
        statuses: list[str] = []
        flags: list[str] = []
        for bill_line in on_line:
            others = sum((Decimal(b.quantity) for b in counted if b.pk != bill_line.pk), ZERO)
            result = evaluate(
                Figures(
                    ordered=ordered,
                    received=received,
                    billed=others + Decimal(bill_line.quantity),
                    po_price=po_price,
                    price=Decimal(bill_line.unit_price),
                    received_any=received_any,
                ),
                tolerance,
            )
            statuses.append(result.status)
            flags.extend(f for f in result.flags if f not in flags)
            bill = bill_line.document
            bills.append(
                {
                    "id": str(bill.public_id),
                    "number": bill.number,
                    "status": bill.status,
                    "supplier_invoice_no": bill.supplier_invoice_no,
                    "date": bill.date.isoformat(),
                    "url": f"/o/{order.organisation.public_id}/purchases/bills/{bill.public_id}",
                    "quantity": _q(Decimal(bill_line.quantity)),
                    "price": _q(Decimal(bill_line.unit_price)),
                    "price_difference_pct": f"{result.price_difference_pct:.2f}",
                    "match": result.status,
                }
            )
        if not on_line and not received_any:
            flags.append(RECEIVED_LATER)
        rows.append(
            {
                "line": str(line.public_id),
                "description": line.description,
                "ordered": _q(ordered),
                "received": _q(received),
                "outstanding": _q(line.outstanding),
                "billed": _q(approved),
                "pending": _q(max(billed - approved, ZERO)),
                "to_bill": _q(max(received - billed, ZERO)),
                "po_price": _q(po_price),
                "bills": bills,
                "flags": flags,
                "status": worst(*statuses),
            }
        )
    return {
        "purchase_order": {
            "id": str(order.public_id),
            "number": order.number,
            "status": order.status,
        },
        "tolerance": {
            "quantity": f"{tolerance.quantity:.2f}",
            "price": f"{tolerance.price:.2f}",
        },
        "status": worst(*(row["status"] for row in rows)),
        "lines": rows,
    }
