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


# ---- Bills (E-02-T14) ----------------------------------------------------------------------

BILL_PERMISSION = "purchases.bills.approve"
BILL_FEATURE = "accounting.bills.approve"


def bill_items(user: Any, organisation: Any, may_approve: bool) -> list[dict[str, Any]]:
    """Bills awaiting approval for ``user``: those **routed to a role they hold** (E-02-T07) — or
    with no routing rule — and within their bill approval limit; plus the ones they wrote or
    submitted ("You created this", never theirs to approve). The subtitle says why the bill is
    theirs: the routing explanation."""
    from .models import Bill, BillStatus
    from .routing import may_approve as routed_to
    from .routing import route

    bills = Bill.objects.filter(
        status=BillStatus.AWAITING_APPROVAL, deleted_at__isnull=True
    ).select_related("contact", "created_by", "submitted_by", "organisation")
    limit = effective_limit(user, ApprovalDocumentType.BILL, organisation=organisation)
    out: list[dict[str, Any]] = []
    for bill in bills.order_by("submitted_at", "pk"):
        authors = {bill.created_by_id, bill.submitted_by_id} - {None}
        mine = user.pk in authors
        routing = route(bill)
        within = limit is not None and Decimal(bill.total) <= limit
        theirs = may_approve and within and routed_to(bill, user, routing)
        if not (mine or theirs):
            continue
        out.append(
            item(
                kind="bill",
                id=str(bill.public_id),
                title=bill.contact.display_name,
                subtitle=" · ".join(
                    part
                    for part in (
                        bill.supplier_invoice_no or str(_("Bill without a supplier number")),
                        routing.explanation,
                    )
                    if part
                ),
                amount=Decimal(bill.total),
                date=bill.date,
                url=f"/o/{organisation.public_id}/purchases/bills/{bill.public_id}",
                submitted_by=bill.submitted_by,
                submitted_at=bill.submitted_at,
                created_by=bill.created_by,
                blocked="self" if mine or not theirs else None,
                limit=limit,
            )
        )
    return out


def register_bill_approvals() -> None:
    approvables.register(
        Approvable(
            kind="bill",
            label=_("Bills"),
            permission=BILL_PERMISSION,
            feature=BILL_FEATURE,
            items=bill_items,
        )
    )


# ---- Expense claims (E-04-T11) -------------------------------------------------------------

EXPENSE_PERMISSION = "purchases.expenses.approve"
EXPENSE_FEATURE = "accounting.expense_claims.approve"


def expense_claim_items(user: Any, organisation: Any, may_approve: bool) -> list[dict[str, Any]]:
    """Expense claims awaiting approval: within the approver's expense-claim limit (A-03), plus
    the claims they made or submitted ("You created this" — never theirs to approve, E-04-T05)."""
    from .models import ExpenseClaim, ExpenseClaimStatus

    claims = ExpenseClaim.objects.filter(
        status=ExpenseClaimStatus.SUBMITTED, deleted_at__isnull=True
    ).select_related("claimant", "created_by", "submitted_by")
    own = Q(claimant=user) | Q(created_by=user) | Q(submitted_by=user)
    limit = effective_limit(user, ApprovalDocumentType.EXPENSE_CLAIM, organisation=organisation)
    if not may_approve or limit is None:
        claims = claims.filter(own)
    else:
        claims = claims.filter(own | Q(total__lte=limit))
    out: list[dict[str, Any]] = []
    for claim in claims.order_by("submitted_at", "pk"):
        authors = {claim.claimant_id, claim.created_by_id, claim.submitted_by_id} - {None}
        mine = user.pk in authors
        out.append(
            item(
                kind="expense_claim",
                id=str(claim.public_id),
                title=claim.claimant.name or claim.claimant.email,
                subtitle=f"{claim.number} · {claim.title}",
                amount=Decimal(claim.total),
                date=claim.submitted_at.date() if claim.submitted_at else None,
                url=f"/o/{organisation.public_id}/purchases/expense-claims/{claim.public_id}",
                submitted_by=claim.submitted_by,
                submitted_at=claim.submitted_at,
                created_by=claim.created_by,
                blocked="self" if mine or not may_approve else None,
                limit=limit,
            )
        )
    return out


def register_expense_claim_approvals() -> None:
    approvables.register(
        Approvable(
            kind="expense_claim",
            label=_("Expense claims"),
            permission=EXPENSE_PERMISSION,
            feature=EXPENSE_FEATURE,
            items=expense_claim_items,
        )
    )
