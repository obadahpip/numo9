"""Bills (E-02): figures, preview and posting.

``recalculate(bill)`` — the calculator's figures (D-01 ``DocumentCalculator``, purchase side) on a
draft's header and lines, as the editor does on save: totals for the lists, the duplicate finder
(E-02-T03) and the routing rules (E-02-T07). ``holdback_amount`` follows from the total.

Purchase-side tax (E-02-T04): each line's tax splits into the **claimable** part (ITC / ITR,
debited to the input tax control account) and the **cost** (added to the line's expense or asset)
by the G-01-T05 order — the account's restriction (Meals and entertainment: 50 %), the tax code's
(``…itc50``), the component's, else 100 %. A bill dated when the organisation **isn't registered
for GST/HST** (no active RT program account on that date) claims nothing: the whole tax is cost.
``itc_split(bill)`` gives, per line, the tax, its claimable part and its cost.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction

from numo9.documents.posting import Preview, PreviewLine, preview, result_for
from numo9.tenancy.context import org_context

from .models import Bill, HoldbackType, SupplierCredit

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def gst_registered(organisation: Any, day: Any) -> bool:
    """The organisation has an active GST/HST (RT) registration on ``day``."""
    from numo9.orgsettings.models import RegistrationType
    from numo9.tax.supply_context import registrations

    return any(
        r.type == RegistrationType.RT and r.active_on(day) for r in registrations(organisation)
    )


def preview_lines(bill: Bill | SupplierCredit) -> list[PreviewLine]:
    itc = None if gst_registered(bill.organisation, bill.date) else Decimal("0")
    return [
        PreviewLine(
            account=line.account,
            quantity=line.quantity,
            unit_price=line.unit_price,
            discount_type=line.discount_type,
            discount_value=line.discount_value,
            tax_code=line.tax_code,
            description=line.description,
            tracking=dict(line.tracking or {}),
            itc_pct=itc,
        )
        for line in bill.lines.select_related("account", "tax_code").order_by("position", "pk")
    ]


def holdback_for(bill: Bill, total: Decimal) -> Decimal:
    """The holdback of a bill whose total is ``total``: an amount (at most the total) or a
    percentage of the total, rounded half-up to the cent."""
    value = Decimal(bill.holdback_value)
    if bill.holdback_type == HoldbackType.AMOUNT:
        return min(value, total).quantize(CENT, rounding=ROUND_HALF_UP)
    if bill.holdback_type == HoldbackType.PERCENT:
        return (total * value / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
    return ZERO


def store_figures(bill: Bill, result: Any) -> None:
    """The calculator's figures on the header and each line (server-authoritative)."""
    lines = list(bill.lines.order_by("position", "pk"))
    for line, figures in zip(lines, result.lines, strict=True):
        line.net = figures.exclusive
        line.tax_amount = figures.tax
        line.amount = figures.net
        line.save(update_fields=["net", "tax_amount", "amount", "updated_at"])
    bill.subtotal = result.subtotal
    bill.discount_total = result.discount_total
    bill.tax_total = result.tax_total
    bill.total = result.total
    bill.holdback_amount = max(holdback_for(bill, Decimal(result.total)), ZERO)


def recalculate(bill: Bill) -> Bill:
    with org_context(bill.organisation), transaction.atomic():
        result = result_for(
            "bill",
            preview_lines(bill),
            tax_mode=bill.tax_mode,
            discount_type=bill.discount_type,
            discount_value=bill.discount_value,
        )
        store_figures(bill, result)
        bill.save(
            update_fields=[
                "subtotal",
                "discount_total",
                "tax_total",
                "total",
                "holdback_amount",
                "updated_at",
            ]
        )
        return bill


def bill_preview(bill: Bill) -> Preview:
    with org_context(bill.organisation):
        return preview(
            "bill",
            bill.date,
            preview_lines(bill),
            tax_mode=bill.tax_mode,
            discount_type=bill.discount_type,
            discount_value=bill.discount_value,
            contact=bill.contact,
        )


def itc_split(bill: Bill) -> list[dict[str, Any]]:
    """Per line: its tax, the claimable part (ITC/ITR) and the cost added to the line's account."""
    from numo9.documents.calculator import DocumentResult

    with org_context(bill.organisation):
        result: DocumentResult = result_for(
            "bill",
            preview_lines(bill),
            tax_mode=bill.tax_mode,
            discount_type=bill.discount_type,
            discount_value=bill.discount_value,
        )
    rows = []
    for figures in result.lines:
        claimable = sum((t.claimable for t in figures.taxes), ZERO)
        cost = sum((t.cost for t in figures.taxes), ZERO)
        rows.append(
            {
                "tax": f"{figures.tax:.2f}",
                "claimable": f"{claimable:.2f}",
                "cost": f"{cost:.2f}",
            }
        )
    return rows
