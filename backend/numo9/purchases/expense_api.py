"""Expense claims API (E-04-T08, approver's view E-04-T11), under ``/api/v1/o/<org>/``.

Feature keys ``accounting.expense_claims.read`` / ``.write`` / ``.approve`` (the catalogue's
family for gap 51: expense claims are in Accounting). Permissions:

- ``purchases.expenses.own`` — enter, submit and see **your own** claims (every organisation
  role, the employee role included: self-service);
- ``purchases.expenses.view`` — see everyone's claims; ``.write`` — enter, edit and submit
  claims for someone else; ``.approve`` — approve or reject, within an approval limit.

Reads are open to anyone in the organisation (``AUTHENTICATED`` + organisation access, checked
here) and **scoped by the rows**: without ``purchases.expenses.view`` a person sees only the
claims they are the claimant of — someone else's claim is a 404, not a 403 (it doesn't exist
for them).

- ``GET expense-claims`` — the list: ``status`` (one or comma-separated), ``mine=1``, ``q``
  (number, title, claimant), ``page``; 50 a page, newest first, counts per status;
- ``POST expense-claims`` — a draft: ``title``, ``notes``, ``claimant`` (a user id; someone else
  needs ``.write``) and ``lines`` (receipt: ``date``, ``merchant``, ``description``, ``account``,
  ``tax_code``, ``amount`` tax included, ``receipt`` — a stored document; mileage: ``date``,
  ``from_place``, ``to_place``, ``distance_km``, ``account`` — priced at the CRA rate on save);
- ``GET`` / ``PATCH`` / ``DELETE expense-claims/<id>`` — a claim; draft and rejected claims are
  edited (the lines are replaced) and drafts deleted (soft), by the claimant or with ``.write``;
- ``POST expense-claims/<id>/submit`` · ``/approve`` · ``/reject`` (``reason``) — the workflow
  (E-04-T05; approval creates the reimbursement bill, E-04-T06);
- ``GET expense-claims/categories`` — the expense accounts, **most used first** (the person's
  own claim lines, then the organisation's, then by code), the purchase tax codes in force and
  the default one (the form's chips and tax picker);
- ``GET expense-claims/mileage-rate?date=&claim=`` — the CRA rate on ``date`` and the business
  kilometres the claimant already claimed that year before it (other claims, not rejected): what
  the mileage calculator needs to show the amount live, tiers included (E-04-T10);
- ``POST expense-claims/receipts`` (``name``, ``size``) · ``POST expense-claims/receipts/<id>/
  finalize`` — upload a receipt photo or PDF (the A-06 presigned flow) with ``.own``, so an
  employee doesn't need the documents inbox.

The claim detail (``claim_detail``) also says ``can_approve`` (false for the claimant, whoever
entered or submitted it, someone without the approve permission or a high enough limit — the
page then hides Approve and Reject and says why, ``blocked``), ``can_edit`` and the
reimbursement ``bill``.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.rbac.approvals import effective_limit
from numo9.rbac.drf import AUTHENTICATED, requires_permission
from numo9.rbac.models import ApprovalDocumentType
from numo9.tenancy.context import current_org

from .expense_tax import receipt_split
from .models import ExpenseClaim, ExpenseClaimLine, ExpenseClaimStatus, ExpenseLineKind
from .permissions import EXPENSES_APPROVE, EXPENSES_OWN, EXPENSES_VIEW, EXPENSES_WRITE
from .receipt_duplicates import claim_warnings

READ = "accounting.expense_claims.read"
WRITE = "accounting.expense_claims.write"
APPROVE = "accounting.expense_claims.approve"
PAGE_SIZE = 50
EDITABLE = (ExpenseClaimStatus.DRAFT, ExpenseClaimStatus.REJECTED)


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _has(user: Any, key: str) -> bool:
    from numo9.rbac.resolver import has_perm

    organisation = current_org()
    return organisation is not None and has_perm(user, organisation, key)


def _member(user: Any) -> None:
    """``AUTHENTICATED`` reads: the organisation must be one the person may access (404)."""
    from numo9.tenancy.access import can_access

    organisation = current_org()
    if organisation is None or not can_access(user, organisation):
        raise NotFound


def visible_claims(user: Any) -> QuerySet[ExpenseClaim]:
    """The claims ``user`` may see: all of them with ``purchases.expenses.view``, else their own."""
    claims = ExpenseClaim.objects.filter(deleted_at__isnull=True)
    if _has(user, EXPENSES_VIEW.key):
        return claims
    return claims.filter(claimant_id=getattr(user, "pk", None))


def _claim(public_id: Any, user: Any = None) -> ExpenseClaim:
    rows = (
        visible_claims(user) if user is not None else ExpenseClaim.objects.filter(deleted_at=None)
    )
    found: ExpenseClaim | None = (
        rows.select_related("claimant", "submitted_by", "decided_by", "organisation", "bill")
        .filter(public_id=public_id)
        .first()
    )
    if found is None:
        raise NotFound(_("There's no expense claim with this id in this organisation."))
    return found


def _people(user: Any) -> dict[str, str] | None:
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


def may_edit(claim: ExpenseClaim, user: Any) -> bool:
    """The claim is a draft or rejected, and ``user`` is its claimant (``.own``) or may enter
    claims for others (``.write``)."""
    if claim.status not in EDITABLE:
        return False
    if claim.claimant_id == getattr(user, "pk", None):
        return _has(user, EXPENSES_OWN.key)
    return _has(user, EXPENSES_WRITE.key)


def claim_row(claim: ExpenseClaim) -> dict[str, Any]:
    return {
        "id": str(claim.public_id),
        "number": claim.number,
        "title": claim.title,
        "status": claim.status,
        "status_label": claim.get_status_display(),
        "claimant": _people(claim.claimant),
        "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
        "currency": claim.currency,
        "total": f"{claim.total:.2f}",
        "url": f"/o/{claim.organisation.public_id}/purchases/expense-claims/{claim.public_id}",
    }


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
            "tracking": dict(line.tracking or {}),
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
    bill = claim.bill
    return {
        **claim_row(claim),
        "submitted_by": _people(claim.submitted_by),
        "decided_by": _people(claim.decided_by),
        "decided_at": claim.decided_at.isoformat() if claim.decided_at else None,
        "rejection_reason": claim.rejection_reason,
        "notes": claim.notes,
        "lines": lines,
        "warnings": claim_warnings(claim),
        "can_approve": blocked is None,
        "blocked": blocked,
        "can_edit": may_edit(claim, user),
        "bill": None
        if bill is None
        else {
            "id": str(bill.public_id),
            "number": bill.number,
            "status": bill.status,
            "amount_due": f"{bill.amount_due:.2f}",
            "url": f"/o/{claim.organisation.public_id}/purchases/bills/{bill.public_id}",
        },
    }


def _refused(error: Any) -> Response:
    messages = getattr(error, "messages", None) or [str(error)]
    return Response(
        {"code": getattr(error, "code", "invalid"), "detail": " ".join(str(m) for m in messages)},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ---- payloads ------------------------------------------------------------------------------


class ClaimLineSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=ExpenseLineKind.choices, default=ExpenseLineKind.RECEIPT)
    date = serializers.DateField()
    description = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=500
    )
    account = serializers.UUIDField(required=False, allow_null=True, default=None)
    amount = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0"), default=Decimal("0")
    )
    tracking = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    merchant = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)
    tax_code = serializers.UUIDField(required=False, allow_null=True, default=None)
    receipt = serializers.UUIDField(required=False, allow_null=True, default=None)
    from_place = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)
    to_place = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)
    distance_km = serializers.DecimalField(
        max_digits=9, decimal_places=1, min_value=Decimal("0.1"), required=False, allow_null=True
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["kind"] == ExpenseLineKind.MILEAGE and not attrs.get("distance_km"):
            raise serializers.ValidationError({"distance_km": [_("Enter the kilometres driven.")]})
        return attrs


class ClaimSerializer(serializers.Serializer[Any]):
    title = serializers.CharField(max_length=200)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    claimant = serializers.UUIDField(required=False, allow_null=True, default=None)
    lines = ClaimLineSerializer(many=True, max_length=200)  # type: ignore[call-arg]


def _claimant(values: dict[str, Any], user: Any) -> Any:
    """The claimant: the person themself, or — with ``.write`` — a member of the organisation."""
    from numo9.accounts.models import User
    from numo9.tenancy.access import can_access

    wanted = values.get("claimant")
    if wanted is None or str(wanted) == str(user.public_id):
        return user
    if not _has(user, EXPENSES_WRITE.key):
        raise PermissionDenied(_("You can enter expense claims for yourself only."))
    found = User.objects.filter(public_id=wanted).first()
    organisation = current_org()
    if found is None or organisation is None or not can_access(found, organisation):
        raise serializers.ValidationError(
            {"claimant": [_("That person isn't in this organisation.")]}
        )
    return found


def _resolve_lines(lines: list[dict[str, Any]], user: Any) -> list[dict[str, Any]]:
    """Public ids → records. A receipt is a document the person uploaded (or, with the documents
    inbox permission, any document of the organisation)."""
    from numo9.files.models import Document
    from numo9.ledger.models import Account, AccountType
    from numo9.tax.models import TaxCode

    def ids(field: str) -> set[Any]:
        return {x[field] for x in lines if x.get(field)}

    accounts = {
        a.public_id: a
        for a in Account.objects.filter(public_id__in=ids("account"), type=AccountType.EXPENSE)
    }
    codes = {
        c.public_id: c
        for c in TaxCode.objects.filter(public_id__in=ids("tax_code"), side="purchase")
    }
    documents = Document.objects.filter(public_id__in=ids("receipt"), deleted_at__isnull=True)
    if not _has(user, "documents.file.view"):
        documents = documents.filter(created_by=user)
    receipts = {d.public_id: d for d in documents}
    errors: dict[str, Any] = {}
    for number, line in enumerate(lines):
        for field, found, label in (
            ("account", accounts, _("That category doesn't exist.")),
            ("tax_code", codes, _("That tax code doesn't exist.")),
            ("receipt", receipts, _("That receipt file doesn't exist.")),
        ):
            if line.get(field) and line[field] not in found:
                errors.setdefault(str(number), {})[field] = [label]
    if errors:
        raise serializers.ValidationError({"lines": errors})
    return [
        {
            **line,
            "account": accounts.get(line["account"]) if line.get("account") else None,
            "tax_code": codes.get(line["tax_code"]) if line.get("tax_code") else None,
            "receipt": receipts.get(line["receipt"]) if line.get("receipt") else None,
        }
        for line in lines
    ]


def _save(claim: ExpenseClaim, values: dict[str, Any], lines: list[dict[str, Any]]) -> ExpenseClaim:
    from .mileage import price_mileage

    claim.title = values["title"]
    claim.notes = values["notes"]
    claim.save()
    claim.lines.all().delete()
    for position, line in enumerate(lines):
        mileage = line["kind"] == ExpenseLineKind.MILEAGE
        ExpenseClaimLine(
            organisation=claim.organisation,
            claim=claim,
            position=position,
            kind=line["kind"],
            date=line["date"],
            description=line["description"],
            account=line["account"],
            amount=Decimal("0") if mileage else line["amount"],
            tracking=dict(line["tracking"] or {}),
            merchant="" if mileage else line["merchant"],
            tax_code=None if mileage else line["tax_code"],
            receipt=None if mileage else line["receipt"],
            from_place=line["from_place"] if mileage else "",
            to_place=line["to_place"] if mileage else "",
            distance_km=line.get("distance_km") if mileage else None,
        ).save()
    try:
        price_mileage(claim)
    except DjangoValidationError as error:
        raise serializers.ValidationError(
            {"code": "purchases.expense.mileage_rate", "detail": " ".join(error.messages)}
        ) from None
    claim.recalculate()
    claim.save(update_fields=["total", "updated_at"])
    return claim


def _status_filter(text: str | None) -> list[str]:
    wanted = [s.strip() for s in (text or "").split(",") if s.strip()]
    return [s for s in wanted if s in ExpenseClaimStatus.values]


# ---- views ---------------------------------------------------------------------------------


class ExpenseClaimListView(APIView):
    @requires_permission(AUTHENTICATED)  # own claims for everyone, all with .view (rows scoped)
    @requires_feature(READ)
    @extend_schema(
        operation_id="expense_claims_list",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("mine", bool),
            OpenApiParameter("q", str),
            OpenApiParameter("page", int),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        _member(request.user)
        query = request.query_params
        claims = visible_claims(request.user).select_related("claimant", "organisation")
        if query.get("mine") in ("1", "true"):
            claims = claims.filter(claimant_id=request.user.pk)
        counts = dict(
            claims.values_list("status").annotate(n=Count("pk")).values_list("status", "n")
        )
        statuses = _status_filter(query.get("status"))
        if statuses:
            claims = claims.filter(status__in=statuses)
        text = (query.get("q") or "").strip()
        if text:
            claims = claims.filter(
                Q(number__icontains=text)
                | Q(title__icontains=text)
                | Q(claimant__name__icontains=text)
                | Q(claimant__email__icontains=text)
            )
        raw = str(query.get("page") or "1")
        page = max(1, int(raw)) if raw.isdigit() else 1
        total = claims.count()
        chunk = claims.order_by("-created_at", "-pk")[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        return Response(
            {
                "count": total,
                "page": page,
                "pages": max(1, -(-total // PAGE_SIZE)),
                "counts": {key: counts.get(key, 0) for key in ExpenseClaimStatus.values},
                "can_view_all": _has(request.user, EXPENSES_VIEW.key),
                "results": [claim_row(claim) for claim in chunk],
            }
        )

    @requires_permission(EXPENSES_OWN.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="expense_claims_create",
        request=ClaimSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = ClaimSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        claimant = _claimant(values, request.user)
        lines = _resolve_lines(values["lines"], request.user)
        with transaction.atomic():
            draft = ExpenseClaim(
                organisation=current_org(),
                claimant=claimant,
                created_by=_person(request.user),
            )
            claim = _save(draft, values, lines)
        return Response(
            claim_detail(_claim(claim.public_id), request.user), status=status.HTTP_201_CREATED
        )


class ExpenseClaimDetailView(APIView):
    @requires_permission(AUTHENTICATED)  # visible_claims: own claims, or all with .view
    @requires_feature(READ)
    @extend_schema(operation_id="expense_claims_detail", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        _member(request.user)
        return Response(claim_detail(_claim(public_id, request.user), request.user))

    @requires_permission(EXPENSES_OWN.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="expense_claims_update",
        request=ClaimSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        claim = _claim(public_id, request.user)
        if not may_edit(claim, request.user):
            return Response(
                {
                    "code": "purchases.expense.not_editable",
                    "detail": _("Only your own draft or rejected claims can be edited."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        incoming = ClaimSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        lines = _resolve_lines(values["lines"], request.user)
        with transaction.atomic():
            locked = ExpenseClaim._base_manager.select_for_update().get(pk=claim.pk)
            _save(locked, values, lines)
        return Response(claim_detail(_claim(public_id), request.user))

    @requires_permission(EXPENSES_OWN.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="expense_claims_delete", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        claim = _claim(public_id, request.user)
        if claim.status != ExpenseClaimStatus.DRAFT or not may_edit(claim, request.user):
            return Response(
                {
                    "code": "purchases.expense.not_deletable",
                    "detail": _("Only a draft claim can be deleted."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        claim.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpenseClaimSubmitView(APIView):
    @requires_permission(EXPENSES_OWN.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="expense_claims_submit", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from .expense_claims import ExpenseClaimRefused, submit

        claim = _claim(public_id, request.user)
        if not may_edit(claim, request.user) and claim.status in EDITABLE:
            raise PermissionDenied(_("You can submit your own expense claims only."))
        try:
            submit(claim, request.user)
        except ExpenseClaimRefused as error:
            return _refused(error)
        except DjangoValidationError as error:
            return _refused(error)
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
        from numo9.ledger.models import LedgerError

        from .expense_claims import approve

        claim = _claim(public_id, request.user)
        try:
            approve(claim, request.user)
        except LedgerError as error:  # the workflow's refusals, the reimbursement bill's posting
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
        claim = _claim(public_id, request.user)
        try:
            reject(claim, request.user, incoming.validated_data["reason"])
        except ExpenseClaimRefused as error:
            return _refused(error)
        return Response(claim_detail(_claim(public_id), request.user))


# ---- the form's helpers ----------------------------------------------------------------------


def categories(user: Any) -> list[dict[str, Any]]:
    """Expense accounts, most used first: the person's claim lines, then everyone's, then code."""
    from numo9.ledger.models import Account, AccountStatus, AccountType

    accounts = Account.objects.filter(type=AccountType.EXPENSE, system_role="").exclude(
        status=AccountStatus.ARCHIVED
    )
    lines = ExpenseClaimLine.objects.filter(
        claim__deleted_at__isnull=True, account__isnull=False
    ).values_list("account_id", "claim__claimant_id")
    mine: dict[int, int] = {}
    everyone: dict[int, int] = {}
    for account_id, claimant_id in lines:
        everyone[account_id] = everyone.get(account_id, 0) + 1
        if claimant_id == user.pk:
            mine[account_id] = mine.get(account_id, 0) + 1
    ordered = sorted(accounts, key=lambda a: (-mine.get(a.pk, 0), -everyone.get(a.pk, 0), a.code))
    return [
        {
            "id": str(a.public_id),
            "code": a.code,
            "name": a.name,
            "used": mine.get(a.pk, 0),
            "itc_restriction_pct": None
            if a.itc_restriction_pct is None
            else f"{a.itc_restriction_pct.normalize():f}",
        }
        for a in ordered
    ]


def tax_codes(day: dt.date) -> tuple[list[dict[str, Any]], str | None]:
    from numo9.orgsettings.service import get_settings
    from numo9.tax.resolver import codes_available

    organisation = current_org()
    found = list(codes_available("purchase", day, organisation))
    province = (get_settings(organisation).physical_province or "").upper()
    default = next((c for c in found if c.code == f"purchase.{province}.standard"), None)
    rows = [{"id": str(c.public_id), "code": c.code, "name": c.name} for c in found]
    return rows, str(default.public_id) if default else None


class ExpenseCategoriesView(APIView):
    @requires_permission(EXPENSES_OWN.key)
    @requires_feature(READ)
    @extend_schema(operation_id="expense_claims_categories", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any) -> Response:
        codes, default = tax_codes(timezone.localdate())
        return Response(
            {
                "categories": categories(request.user),
                "tax_codes": codes,
                "default_tax_code": default,
            }
        )


def _day(text: str | None) -> dt.date:
    try:
        return dt.date.fromisoformat(text) if text else timezone.localdate()
    except ValueError:
        raise serializers.ValidationError({"date": [_("Enter a date as YYYY-MM-DD.")]}) from None


class MileageRateView(APIView):
    @requires_permission(EXPENSES_OWN.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="expense_claims_mileage_rate",
        parameters=[OpenApiParameter("date", OpenApiTypes.DATE), OpenApiParameter("claim", str)],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        from .mileage import rate_on

        day = _day(request.query_params.get("date"))
        claim = None
        if request.query_params.get("claim"):
            import uuid

            try:
                claim = _claim(uuid.UUID(request.query_params["claim"]), request.user)
            except ValueError:
                raise NotFound from None
        claimant = claim.claimant if claim is not None else request.user
        try:
            rate = rate_on(day)
        except DjangoValidationError as error:
            return Response(
                {"code": "purchases.expense.mileage_rate", "detail": " ".join(error.messages)},
                status=status.HTTP_404_NOT_FOUND,
            )
        from django.db.models import Sum

        earlier = (
            ExpenseClaimLine.objects.filter(
                claim__claimant=claimant,
                claim__deleted_at__isnull=True,
                kind=ExpenseLineKind.MILEAGE,
                date__gte=dt.date(day.year, 1, 1),
                date__lt=day,
            )
            .exclude(claim__status=ExpenseClaimStatus.REJECTED)
            .exclude(claim=claim)
            .aggregate(km=Sum("distance_km"))["km"]
        ) or Decimal("0")
        return Response(
            {
                "date": day.isoformat(),
                "region": rate.region,
                "first_tier_rate": f"{rate.first_tier_rate.normalize():f}",
                "second_tier_rate": f"{rate.second_tier_rate.normalize():f}",
                "tier_threshold_km": rate.tier_threshold_km,
                "year_to_date_km": f"{Decimal(earlier).normalize():f}",
            }
        )


class UploadSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=255)
    size = serializers.IntegerField(min_value=0)


class ReceiptUploadView(APIView):
    @requires_permission(EXPENSES_OWN.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="expense_claims_receipt_upload",
        summary="Start a receipt upload (photo or PDF): the document and a presigned POST form",
        request=UploadSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        from numo9.files import services
        from numo9.files.api import storage_errors
        from numo9.files.models import MAX_FILE_SIZE
        from numo9.files.serializers import DocumentSerializer

        incoming = UploadSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        with storage_errors():
            document, form = services.create_upload(
                incoming.validated_data["name"],
                incoming.validated_data["size"],
                user=request.user,
            )
        return Response(
            {
                "document": DocumentSerializer(document).data,
                "upload": {"url": form["url"], "fields": form["fields"]},
                "max_size": MAX_FILE_SIZE,
            },
            status=status.HTTP_201_CREATED,
        )


class ReceiptFinalizeView(APIView):
    @requires_permission(EXPENSES_OWN.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="expense_claims_receipt_finalize",
        summary="Finish a receipt upload: size, type, SHA-256 (duplicate check), virus scan",
        request=None,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from numo9.files import services, storage
        from numo9.files.api import storage_errors
        from numo9.files.models import Document
        from numo9.files.serializers import DocumentSerializer

        document = Document.objects.filter(
            public_id=public_id, deleted_at__isnull=True, created_by=request.user
        ).first()
        if document is None:
            raise NotFound
        with storage_errors():
            try:
                shown = services.finalize_upload(document)
            except storage.ForeignDocument as exc:
                raise NotFound from exc
        body = dict(DocumentSerializer(shown).data)
        body["duplicate"] = shown.pk != document.pk
        return Response(body)
