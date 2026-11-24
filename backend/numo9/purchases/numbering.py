"""Purchase order numbers (E-01-T02): ``PO-0001`` from the organisation's purchase-order sequence
(A-05 ``allocate_number``; prefix and padding editable), taken **at approval** in the approving
transaction — a refused approval gives the number back. A PO keeps its number when it is closed;
calling this again returns the number it has.
"""

from __future__ import annotations

from django.db import transaction

from numo9.orgsettings.models import DocType
from numo9.orgsettings.numbering import allocate_number
from numo9.tenancy.context import org_context

from .models import PurchaseOrder


def assign_number(order: PurchaseOrder) -> str:
    with org_context(order.organisation), transaction.atomic():
        locked = PurchaseOrder._base_manager.select_for_update().get(pk=order.pk)
        if locked.number:
            order.number = locked.number
            return locked.number
        number = allocate_number(DocType.PURCHASE_ORDER, order.organisation)
        PurchaseOrder._base_manager.filter(pk=order.pk).update(number=number)
        order.number = number
        return number
