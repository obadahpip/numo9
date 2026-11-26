"""Expense claim workflow (E-04-T05): submit → approve or reject.

- ``submit(claim, user)`` — a draft (or a rejected claim being sent again): it needs at least one
  line with an amount; every receipt line needs its category; a receipt line above the
  organisation's ``expense_receipt_required_above`` needs the receipt attached. Mileage lines are
  priced at the CRA rate (E-04-T03) and the total recalculated. The claim takes its number
  (``EXP-0001``, kept when it is sent again) and is **Awaiting approval**.
- ``approve(claim, user)`` — only a claim awaiting approval; **never by its claimant or by whoever
  submitted it** (``purchases.expense.self_approval``), and only within the approver's
  expense-claim approval limit (A-03: no limit → no approval, above it → the people who may).
  In the same transaction the **reimbursement bill** to the employee's contact is created and
  posted, crediting Unpaid expense claims (E-04-T06, ``expense_reimbursement``); if it can't be
  posted (a locked period, a missing category) the approval is refused as a whole.
- ``reject(claim, user, reason)`` — a reason is required; the same segregation rule applies.

Each step is audited (``purchases.expenseclaim.submitted`` / ``approved`` / ``rejected``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError
from numo9.orgsettings.models import DocType
from numo9.orgsettings.numbering import allocate_number
from numo9.rbac.approvals import assert_can_approve
from numo9.rbac.models import ApprovalDocumentType
from numo9.tenancy.context import org_context

from .mileage import price_mileage
from .models import ExpenseClaim, ExpenseClaimStatus, ExpenseLineKind

DOC_TYPE = ApprovalDocumentType.EXPENSE_CLAIM
SUBMITTABLE = (ExpenseClaimStatus.DRAFT, ExpenseClaimStatus.REJECTED)


class ExpenseClaimRefused(LedgerError):
    """An expense-claim action the rules refuse (``code`` names the rule)."""


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _locked(claim: ExpenseClaim) -> ExpenseClaim:
    return ExpenseClaim._base_manager.select_for_update().get(pk=claim.pk)


def receipt_threshold(organisation: Any) -> Decimal | None:
    from numo9.orgsettings.service import get_settings

    value = get_settings(organisation).expense_receipt_required_above
    return Decimal(value) if value is not None else None


def check_lines(claim: ExpenseClaim) -> None:
    """The rules a claim's lines must meet to be submitted (module docstring)."""
    lines = list(claim.lines.all())
    if not lines or not any(Decimal(line.amount) > 0 for line in lines):
        raise ExpenseClaimRefused(
            _("Add at least one receipt or trip with an amount before submitting."),
            code="purchases.expense.empty",
        )
    threshold = receipt_threshold(claim.organisation)
    for line in lines:
        if line.kind != ExpenseLineKind.RECEIPT:
            continue
        if line.account_id is None:
            raise ExpenseClaimRefused(
                _("Choose a category for every receipt."),
                code="purchases.expense.category_missing",
            )
        if threshold is not None and line.receipt_id is None and Decimal(line.amount) > threshold:
            raise ExpenseClaimRefused(
                _("Attach the receipt for %(line)s: receipts are required above %(limit)s."),
                code="purchases.expense.receipt_required",
                params={"line": str(line), "limit": f"{threshold:.2f}"},
            )


def submit(claim: ExpenseClaim, user: Any) -> ExpenseClaim:
    from numo9.audit import service as audit

    person = _person(user)
    with org_context(claim.organisation), transaction.atomic():
        locked = _locked(claim)
        if locked.status not in SUBMITTABLE:
            raise ExpenseClaimRefused(
                _("%(claim)s has already been submitted."),
                code="purchases.expense.not_draft",
                params={"claim": str(locked)},
            )
        price_mileage(locked)
        check_lines(locked)
        locked.recalculate()
        previous = locked.status
        locked.number = locked.number or allocate_number(DocType.EXPENSE_CLAIM, locked.organisation)
        locked.status = ExpenseClaimStatus.SUBMITTED
        locked.submitted_by = person
        locked.submitted_at = timezone.now()
        locked.decided_by, locked.decided_at, locked.rejection_reason = None, None, ""
        locked.save()
        audit.record(
            "purchases.expenseclaim.submitted",
            obj=locked,
            changes={"status": [previous, locked.status]},
            meta={"number": locked.number, "total": f"{locked.total:.2f}"},
            actor=person,
        )
        return locked


def _decidable(locked: ExpenseClaim, person: Any) -> None:
    if locked.status != ExpenseClaimStatus.SUBMITTED:
        raise ExpenseClaimRefused(
            _("%(claim)s isn't waiting for approval."),
            code="purchases.expense.not_submitted",
            params={"claim": str(locked)},
        )
    authors = {locked.claimant_id, locked.submitted_by_id, locked.created_by_id} - {None}
    if person is None or person.pk in authors:
        raise ExpenseClaimRefused(
            _("This is your own expense claim: someone else must approve or reject it."),
            code="purchases.expense.self_approval",
        )


def approve(claim: ExpenseClaim, user: Any) -> ExpenseClaim:
    from numo9.audit import service as audit

    person = _person(user)
    with org_context(claim.organisation), transaction.atomic():
        locked = _locked(claim)
        _decidable(locked, person)
        assert_can_approve(
            person,
            DOC_TYPE,
            Decimal(locked.total),
            organisation=locked.organisation,
            exclude=[p for p in (locked.claimant, locked.submitted_by) if p is not None],
        )
        from .expense_reimbursement import create_reimbursement_bill

        bill = create_reimbursement_bill(locked, person)
        locked.status = ExpenseClaimStatus.APPROVED
        locked.decided_by = person
        locked.decided_at = timezone.now()
        locked.save()
        audit.record(
            "purchases.expenseclaim.approved",
            obj=locked,
            changes={"status": [ExpenseClaimStatus.SUBMITTED, locked.status]},
            meta={"number": locked.number, "total": f"{locked.total:.2f}", "bill": bill.number},
            actor=person,
        )
        return locked


def reject(claim: ExpenseClaim, user: Any, reason: str) -> ExpenseClaim:
    from numo9.audit import service as audit

    person = _person(user)
    reason = (reason or "").strip()
    if not reason:
        raise ExpenseClaimRefused(
            _("Say why the claim is rejected."), code="purchases.expense.reason_required"
        )
    with org_context(claim.organisation), transaction.atomic():
        locked = _locked(claim)
        _decidable(locked, person)
        locked.status = ExpenseClaimStatus.REJECTED
        locked.decided_by = person
        locked.decided_at = timezone.now()
        locked.rejection_reason = reason[:2000]
        locked.save()
        audit.record(
            "purchases.expenseclaim.rejected",
            obj=locked,
            changes={"status": [ExpenseClaimStatus.SUBMITTED, locked.status]},
            meta={"number": locked.number, "reason": locked.rejection_reason},
            actor=person,
        )
        return locked
