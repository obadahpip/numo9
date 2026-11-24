"""Approval routing of bills (E-02-T07): ``ApprovalRoutingRule`` → who approves a bill.

``route(bill)`` → ``Routing``: the first active rule (in ``position`` order) whose amount band
(``min_amount`` < total ≤ ``max_amount``, an empty bound is open) and department (empty = any)
match the bill, the role whose holders approve it and the **explanation** the editor shows —
"Routed to Finance approvers (amount over $2,000.00)". No rule matching → ``rule`` None: anyone
whose bill approval limit covers it may approve (A-03).

``may_approve(bill, user)`` — whether ``user`` holds the routed role (always true when no rule
matches); ``approve`` (E-02-T05) refuses anyone else with ``purchases.bill.not_routed_to_you``.
``submit(bill, user)`` — send a draft to Awaiting approval (who, when), with its routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.documents.formatting import format_money
from numo9.tenancy.context import org_context

from .models import ApprovalRoutingRule, Bill, BillStatus


@dataclass(frozen=True)
class Routing:
    rule: ApprovalRoutingRule | None
    explanation: str

    @property
    def role(self) -> Any:
        return self.rule.approver_role if self.rule is not None else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule": None if self.rule is None else str(self.rule.public_id),
            "role": None if self.rule is None else str(self.rule.approver_role.public_id),
            "role_name": None if self.rule is None else str(self.rule.approver_role.name),
            "explanation": self.explanation,
        }


def matches(rule: ApprovalRoutingRule, total: Decimal, department: str) -> bool:
    if rule.min_amount is not None and not total > rule.min_amount:
        return False
    if rule.max_amount is not None and not total <= rule.max_amount:
        return False
    return not rule.department or rule.department.casefold() == (department or "").casefold()


def explain(rule: ApprovalRoutingRule, locale: str | None = None) -> str:
    role = str(rule.approver_role.name)
    low = format_money(rule.min_amount, locale) if rule.min_amount is not None else ""
    high = format_money(rule.max_amount, locale) if rule.max_amount is not None else ""
    if low and high:
        band = _("amount over %(low)s up to %(high)s") % {"low": low, "high": high}
    elif low:
        band = _("amount over %(low)s") % {"low": low}
    elif high:
        band = _("amount up to %(high)s") % {"high": high}
    else:
        band = _("any amount")
    if rule.department:
        band = _("%(band)s, department %(department)s") % {
            "band": band,
            "department": rule.department,
        }
    return _("Routed to %(role)s approvers (%(band)s)") % {"role": role, "band": band}


def route(bill: Bill, *, total: Decimal | None = None, locale: str | None = None) -> Routing:
    amount = Decimal(bill.total if total is None else total)
    with org_context(bill.organisation):
        rules = ApprovalRoutingRule.objects.filter(
            doc_type="bill", is_active=True, deleted_at__isnull=True
        ).select_related("approver_role")
        for rule in rules.order_by("position", "pk"):
            if matches(rule, amount, bill.department):
                return Routing(rule, explain(rule, locale))
    return Routing(None, "")


def may_approve(bill: Bill, user: Any, routing: Routing | None = None) -> bool:
    from numo9.rbac.resolver import organisation_roles

    routing = routing or route(bill)
    if routing.rule is None:
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    return (
        organisation_roles(user, bill.organisation)
        .filter(pk=routing.rule.approver_role_id)
        .exists()
    )


def submit(bill: Bill, user: Any) -> Bill:
    """Send a draft bill to Awaiting approval (the approvals inbox, E-02-T14)."""
    from numo9.audit import service as audit

    from .bill_posting import BillRefused, _check_supplier_invoice
    from .bills import recalculate

    person = user if getattr(user, "is_authenticated", False) else None
    with org_context(bill.organisation), transaction.atomic():
        locked = Bill._base_manager.select_for_update().get(pk=bill.pk)
        if locked.status != BillStatus.DRAFT:
            raise BillRefused(
                _("Only a draft bill can be submitted for approval."),
                code="purchases.bill.not_draft",
            )
        _check_supplier_invoice(locked)
        recalculate(locked)
        locked.status = BillStatus.AWAITING_APPROVAL
        locked.submitted_by = person
        locked.submitted_at = timezone.now()
        locked.version += 1
        locked.save()
        routing = route(locked)
        audit.record(
            "purchases.bill.submitted",
            obj=locked,
            changes={"status": [BillStatus.DRAFT, BillStatus.AWAITING_APPROVAL]},
            meta={"routing": routing.explanation, "total": f"{locked.total:.2f}"},
            actor=person,
        )
        return locked
