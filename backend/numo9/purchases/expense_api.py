"""Expense claims API — the approver's view (E-04-T11), under ``/api/v1/o/<org>/``.

Feature keys ``accounting.expense_claims.read`` / ``.approve``; permissions
``purchases.expenses.view`` / ``.approve``. The full claims API (list, create, edit, submit, an
employee's own claims) is E-04-T08.

- ``GET expense-claims/<id>`` — the claim, its lines with the tax split of each receipt (E-04-T04)
  and the mileage tiers, duplicate-receipt warnings (E-04-T07) and ``can_approve``: false for the
  claimant, whoever entered or submitted it (E-04-T05), someone without the approve permission or
  a high enough limit — the page then hides Approve and Reject and says why (``blocked``);
- ``POST expense-claims/<id>/approve`` · ``/reject`` (``reason``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.rbac.approvals import effective_limit
from numo9.rbac.drf import requires_permission
from numo9.rbac.models import ApprovalDocumentType

from .expense_tax import receipt_split
from .models import ExpenseClaim, ExpenseClaimStatus, ExpenseLineKind
from .permissions import EXPENSES_APPROVE, EXPENSES_VIEW
from .receipt_duplicates import claim_warnings

READ = "accounting.expense_claims.read"
APPROVE = "accounting.expense_claims.approve"


def _claim(public_id: Any) -> ExpenseClaim:
    found: ExpenseClaim | None = (
        ExpenseClaim.objects.select_related(
            "claimant", "submitted_by", "decided_by", "organisation"
        )
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if found is None:
        raise NotFound(_("There's no expense claim with this id in this organisation."))
    return found


def _person(user: Any) -> dict[str, str] | None:
    return {"id": str(user.public_id), "name": user.name or user.email} if user else None


def _blocked(claim: ExpenseClaim, user: Any) -> str | None:
    """Why ``user`` can't approve ``claim`` now (None: they can)."""
    from numo9.rbac.resolver import has_perm

    if claim.status != ExpenseClaimStatus.SUBMITTED:
        return "status"
    authors = {claim.claimant_id, claim.created_by_id, claim.submitted_by_id} - {None}
    if user.pk in authors:
        return "self"
    if not has_perm(user, claim.organisation, EXPENSES_APPROVE.key):
        return "permission"
    limit = effective_limit(
        user, ApprovalDocumentType.EXPENSE_CLAIM, organisation=claim.organisation
    )
    if limit is None or Decimal(claim.total) > limit:
        return "limit"
    return None


def claim_detail(claim: ExpenseClaim, user: Any) -> dict[str, Any]:
    lines = []
    for line in claim.lines.select_related("account", "tax_code", "receipt").all():
        row: dict[str, Any] = {
            "id": str(line.public_id),
            "kind": line.kind,
            "date": line.date.isoformat(),
            "description": line.description,
            "account": (
                {
                    "id": str(line.account.public_id),
                    "code": line.account.code,
                    "name": line.account.name,
                }
                if line.account
                else None
            ),
            "amount": f"{line.amount:.2f}",
        }
        if line.kind == ExpenseLineKind.MILEAGE:
            row.update(
                {
                    "from_place": line.from_place,
                    "to_place": line.to_place,
                    "distance_km": f"{line.distance_km}",
                    "rate_detail": line.rate_detail,
                }
            )
        else:
            row.update(
                {
                    "merchant": line.merchant,
                    "tax_code": {"id": str(line.tax_code.public_id), "code": line.tax_code.code}
                    if line.tax_code
                    else None,
                    "receipt": {"id": str(line.receipt.public_id), "name": line.receipt.name}
                    if line.receipt
                    else None,
                    "split": receipt_split(line).as_dict(),
                }
            )
        lines.append(row)
    blocked = _blocked(claim, user)
    return {
        "id": str(claim.public_id),
        "number": claim.number,
        "title": claim.title,
        "status": claim.status,
        "status_label": claim.get_status_display(),
        "claimant": _person(claim.claimant),
        "submitted_by": _person(claim.submitted_by),
        "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
        "decided_by": _person(claim.decided_by),
        "decided_at": claim.decided_at.isoformat() if claim.decided_at else None,
        "rejection_reason": claim.rejection_reason,
        "currency": claim.currency,
        "total": f"{claim.total:.2f}",
        "notes": claim.notes,
        "lines": lines,
        "warnings": claim_warnings(claim),
        "can_approve": blocked is None,
        "blocked": blocked,
    }


def _refused(error: Any) -> Response:
    messages = getattr(error, "messages", None) or [str(error)]
    return Response(
        {"code": getattr(error, "code", "invalid"), "detail": " ".join(str(m) for m in messages)},
        status=status.HTTP_400_BAD_REQUEST,
    )


class ExpenseClaimDetailView(APIView):
    @requires_permission(EXPENSES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="expense_claims_detail", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(claim_detail(_claim(public_id), request.user))


class RejectSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(max_length=2000, allow_blank=True)


class ExpenseClaimApproveView(APIView):
    @requires_permission(EXPENSES_APPROVE.key)
    @requires_feature(APPROVE)
    @extend_schema(
        operation_id="expense_claims_approve", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from .expense_claims import ExpenseClaimRefused, approve

        claim = _claim(public_id)
        try:
            approve(claim, request.user)
        except ExpenseClaimRefused as error:
            return _refused(error)
        return Response(claim_detail(_claim(public_id), request.user))


class ExpenseClaimRejectView(APIView):
    @requires_permission(EXPENSES_APPROVE.key)
    @requires_feature(APPROVE)
    @extend_schema(
        operation_id="expense_claims_reject",
        request=RejectSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from .expense_claims import ExpenseClaimRefused, reject

        incoming = RejectSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        claim = _claim(public_id)
        try:
            reject(claim, request.user, incoming.validated_data["reason"])
        except ExpenseClaimRefused as error:
            return _refused(error)
        return Response(claim_detail(_claim(public_id), request.user))
