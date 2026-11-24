"""Purchase orders in the approvals inbox (E-01-T15): POs awaiting approval.

An approver (``purchases.orders.approve``) sees the POs **within their purchase-order approval
limit** (A-03) — a PO above it, or with no limit at all, is not theirs to approve and isn't
listed — plus the ones they wrote or submitted (listed as "You created this", never approvable by
them). Everyone else sees only the POs they wrote or submitted.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from numo9.rbac.approvals import effective_limit
from numo9.rbac.inbox import Approvable, approvables, item
from numo9.rbac.models import ApprovalDocumentType

from .models import PurchaseOrder, PurchaseOrderStatus

PERMISSION = "purchases.orders.approve"
FEATURE = "accounting.purchase_orders.approve"


def purchase_order_items(user: Any, organisation: Any, may_approve: bool) -> list[dict[str, Any]]:
    orders = PurchaseOrder.objects.filter(
        status=PurchaseOrderStatus.AWAITING_APPROVAL, deleted_at__isnull=True
    ).select_related("contact", "created_by", "submitted_by")
    own = Q(created_by=user) | Q(submitted_by=user)
    limit = effective_limit(user, ApprovalDocumentType.PURCHASE_ORDER, organisation=organisation)
    if not may_approve or limit is None:
        orders = orders.filter(own)
    else:
        orders = orders.filter(own | Q(total__lte=limit))
    out: list[dict[str, Any]] = []
    for order in orders.order_by("submitted_at", "pk"):
        authors = {order.created_by_id, order.submitted_by_id} - {None}
        mine = user.pk in authors
        out.append(
            item(
                kind="purchase_order",
                id=str(order.public_id),
                title=order.contact.display_name,
                subtitle=order.number or str(_("Draft purchase order")),
                amount=Decimal(order.total),
                date=order.date,
                url=f"/o/{organisation.public_id}/purchases/orders/{order.public_id}",
                submitted_by=order.submitted_by,
                submitted_at=order.submitted_at,
                created_by=order.created_by,
                blocked="self" if mine or not may_approve else None,
                limit=limit,
            )
        )
    return out


def register_purchase_order_approvals() -> None:
    approvables.register(
        Approvable(
            kind="purchase_order",
            label=_("Purchase orders"),
            permission=PERMISSION,
            feature=FEATURE,
            items=purchase_order_items,
        )
    )
