"""Purchase orders, goods receipts, the 3-way match and the commitment report API (E-01-T10),
under ``/api/v1/o/<org>/``. Feature keys ``accounting.purchase_orders.read`` / ``.write`` /
``.approve`` (the catalogue's purchase-order area — the plan's ``accounting.purchases.po``);
permissions ``purchases.orders.view`` / ``.write`` / ``.approve`` / ``.receive``.

- ``GET purchase-orders`` — the list: ``status`` (one or comma-separated), ``supplier``, ``q``
  (number, reference, supplier name), ``page``; 50 a page, newest first, with ``counts`` per
  status (the list tabs);
- ``POST purchase-orders`` — a draft: ``supplier``, ``date``, ``reference``, ``terms``,
  ``tax_mode``, discount, ``notes``, the delivery block (``delivery_attention``,
  ``delivery_address``, ``delivery_date``, ``delivery_instructions``) and ``lines``;
- ``GET purchase-orders/approval-limit`` — the person's purchase-order approval limit;
- ``GET`` / ``PATCH`` / ``DELETE purchase-orders/<id>`` — a PO (with the person's approval limit:
  the editor's limit indicator). A draft or a PO awaiting approval is edited freely; an approved
  or partially received PO keeps its lines by ``id`` — a line with receipts or bills can't go, nor
  drop below what was received or billed — and a higher total sends it back to Awaiting approval
  (E-01-T03). 409 when the ``version`` sent isn't the PO's. Delete: drafts only (soft);
- ``POST purchase-orders/<id>/submit`` · ``/approve`` (within the approval limit, 403 beyond it)
  · ``/cancel`` (a PO with receipts or bills is closed instead) · ``/close``;
- ``GET purchase-orders/<id>/pdf`` · ``GET`` / ``POST purchase-orders/<id>/send`` (E-01-T09);
- ``GET purchase-orders/<id>/match`` — the 3-way match per line (E-01-T07);
- ``GET receipts`` (``purchase_order``) · ``POST receipts`` — ``purchase_order``, ``date``,
  ``notes``, ``lines`` [{``po_line``, ``quantity``}], ``confirm_over``; beyond the tolerance 400
  ``purchases.receipt.over_tolerance_confirm`` (or ``.over_tolerance`` when blocked) with the
  lines in ``over`` · ``GET receipts/<id>`` · ``POST receipts/<id>/reverse`` (``reason``);
- ``GET reports/commitments`` — ``by`` (account / supplier / month), ``from``, ``to``;
  ``export=csv`` or ``xlsx`` downloads the same rows and total (E-01-T08).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.documents.calculator import AMOUNT, NONE, PERCENT
from numo9.documents.models import TaxMode
from numo9.ledger.models import LedgerError
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .models import (
    BillLine,
    GoodsReceipt,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)
from .permissions import PO_APPROVE, PO_RECEIVE, PO_VIEW, PO_WRITE

READ = "accounting.purchase_orders.read"
WRITE = "accounting.purchase_orders.write"
APPROVE = "accounting.purchase_orders.approve"

PAGE_SIZE = 50
DISCOUNTS = (NONE, AMOUNT, PERCENT)
#: A PO whose header and lines may change (an approved one through ``revise``).
EDITABLE = (
    PurchaseOrderStatus.DRAFT,
    PurchaseOrderStatus.AWAITING_APPROVAL,
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
)


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _uuid(value: Any) -> str | None:
    import uuid

    try:
        return str(uuid.UUID(str(value))) if value else None
    except ValueError:
        return None


def _money(value: Any) -> str:
    return f"{Decimal(value):.2f}"


def _q(value: Any) -> str:
    return f"{Decimal(value):.4f}"


def order_url(order: PurchaseOrder) -> str:
    return f"/o/{order.organisation.public_id}/purchases/orders/{order.public_id}"


def _refused(error: Any) -> Response:
    messages = getattr(error, "messages", None) or [str(error)]
    body: dict[str, Any] = {
        "code": getattr(error, "code", "invalid"),
        "detail": " ".join(str(m) for m in messages),
    }
    over = getattr(error, "over", None)
    if over is not None:
        body["over"] = [o.as_dict() for o in over]
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


# ---- payloads ------------------------------------------------------------------------------


def line_row(line: PurchaseOrderLine) -> dict[str, Any]:
    return {
        "id": str(line.public_id),
        "position": line.position,
        "description": line.description,
        "quantity": _q(line.quantity),
        "unit_price": _q(line.unit_price),
        "discount_type": line.discount_type,
        "discount_value": _q(line.discount_value),
        "account": None
        if line.account is None
        else {
            "id": str(line.account.public_id),
            "code": line.account.code,
            "name": line.account.name,
        },
        "tax_code": None
        if line.tax_code is None
        else {"id": str(line.tax_code.public_id), "code": line.tax_code.code},
        "tracking": dict(line.tracking or {}),
        "quantity_received": _q(line.quantity_received),
        "quantity_billed": _q(line.quantity_billed),
        "outstanding": _q(line.outstanding),
        "net": _money(line.net),
        "tax_amount": _money(line.tax_amount),
        "amount": _money(line.amount),
    }


def order_row(order: PurchaseOrder) -> dict[str, Any]:
    return {
        "id": str(order.public_id),
        "number": order.number,
        "status": order.status,
        "status_label": str(PurchaseOrderStatus(order.status).label),
        "supplier": {"id": str(order.contact.public_id), "name": order.contact.display_name},
        "reference": order.reference,
        "date": order.date.isoformat(),
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "total": _money(order.total),
        "url": order_url(order),
    }


def approval_limit(order: PurchaseOrder, user: Any) -> dict[str, Any]:
    """The limit indicator: the person's purchase-order approval limit against the total."""
    from numo9.rbac.approvals import effective_limit

    from .approvals import DOC_TYPE

    limit = effective_limit(_person(user), DOC_TYPE, organisation=order.organisation)
    return {
        "limit": None if limit is None else _money(limit),
        "within": limit is not None and Decimal(order.total) <= limit,
    }


def order_detail(order: PurchaseOrder, user: Any = None) -> dict[str, Any]:
    lines = order.lines.select_related("account", "tax_code").order_by("position", "pk")
    receipts = order.receipts.select_related("received_by").order_by("-date", "-pk")
    return {
        **order_row(order),
        "terms": str(order.terms.public_id) if order.terms_id and order.terms else None,
        "currency": order.currency,
        "tax_mode": order.tax_mode,
        "discount_type": order.discount_type,
        "discount_value": _q(order.discount_value),
        "notes": order.notes,
        "delivery_attention": order.delivery_attention,
        "delivery_address": order.delivery_address,
        "delivery_instructions": order.delivery_instructions,
        "subtotal": _money(order.subtotal),
        "discount_total": _money(order.discount_total),
        "tax_total": _money(order.tax_total),
        "approved_total": None if order.approved_total is None else _money(order.approved_total),
        "version": order.version,
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "approved_at": order.approved_at.isoformat() if order.approved_at else None,
        "approved_by": order.approved_by.get_full_name() if order.approved_by else "",
        "sent_at": order.sent_at.isoformat() if order.sent_at else None,
        "approval": approval_limit(order, user),
        "lines": [line_row(line) for line in lines],
        "receipts": [receipt_row(r, lines=False) for r in receipts],
    }


def receipt_row(receipt: GoodsReceipt, *, lines: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": str(receipt.public_id),
        "purchase_order": {
            "id": str(receipt.purchase_order.public_id),
            "number": receipt.purchase_order.number,
        },
        "date": receipt.date.isoformat(),
        "received_by": receipt.received_by.get_full_name() if receipt.received_by else "",
        "notes": receipt.notes,
        "reversed_at": receipt.reversed_at.isoformat() if receipt.reversed_at else None,
        "reversal_reason": receipt.reversal_reason,
    }
    if lines:
        row["lines"] = [
            {
                "po_line": str(r.po_line.public_id),
                "description": r.po_line.description,
                "quantity": _q(r.quantity),
            }
            for r in receipt.lines.select_related("po_line").order_by("pk")
        ]
    return row


def _order(public_id: Any) -> PurchaseOrder:
    found: PurchaseOrder | None = (
        PurchaseOrder.objects.select_related("contact", "organisation", "approved_by")
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if found is None:
        raise NotFound(_("There's no purchase order with this id in this organisation."))
    return found


# ---- serializers ---------------------------------------------------------------------------


class OrderLineSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(required=False, allow_null=True, default=None)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    quantity = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("1")
    )
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    discount_type = serializers.ChoiceField(choices=DISCOUNTS, default=NONE)
    discount_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    account = serializers.UUIDField(required=False, allow_null=True, default=None)
    tax_code = serializers.UUIDField(required=False, allow_null=True, default=None)
    tracking = serializers.DictField(child=serializers.CharField(), required=False, default=dict)


class OrderSerializer(serializers.Serializer[Any]):
    supplier = serializers.UUIDField()
    date = serializers.DateField()
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    terms = serializers.UUIDField(required=False, allow_null=True, default=None)
    tax_mode = serializers.ChoiceField(choices=TaxMode.choices, default=TaxMode.EXCLUSIVE)
    discount_type = serializers.ChoiceField(choices=DISCOUNTS, default=NONE)
    discount_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    delivery_attention = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=100
    )
    delivery_address = serializers.CharField(required=False, allow_blank=True, default="")
    delivery_date = serializers.DateField(required=False, allow_null=True, default=None)
    delivery_instructions = serializers.CharField(required=False, allow_blank=True, default="")
    lines = OrderLineSerializer(many=True, max_length=500)  # type: ignore[call-arg]
    version = serializers.IntegerField(required=False, allow_null=True, default=None)


HEADER = (
    "date",
    "reference",
    "tax_mode",
    "discount_type",
    "discount_value",
    "notes",
    "delivery_attention",
    "delivery_address",
    "delivery_date",
    "delivery_instructions",
)
LINE_FIELDS = (
    "description",
    "quantity",
    "unit_price",
    "discount_type",
    "discount_value",
    "account",
    "tax_code",
    "tracking",
)


def _resolve(values: dict[str, Any]) -> dict[str, Any]:
    """Public ids → records (the supplier, terms, accounts, tax codes)."""
    from numo9.contacts.models import Contact, PaymentTerm
    from numo9.ledger.models import Account
    from numo9.tax.models import TaxCode

    errors: dict[str, Any] = {}
    supplier = Contact.objects.filter(public_id=values["supplier"], deleted_at__isnull=True).first()
    if supplier is None:
        errors["supplier"] = [_("That supplier doesn't exist.")]
    terms = None
    if values.get("terms"):
        terms = PaymentTerm.objects.filter(public_id=values["terms"]).first()
        if terms is None:
            errors["terms"] = [_("Those payment terms don't exist.")]
    lines = values["lines"]
    accounts = {
        a.public_id: a
        for a in Account.objects.filter(public_id__in={x["account"] for x in lines if x["account"]})
    }
    codes = {
        c.public_id: c
        for c in TaxCode.objects.filter(
            public_id__in={x["tax_code"] for x in lines if x["tax_code"]}
        )
    }
    for number, line in enumerate(lines):
        for field, found in (("account", accounts), ("tax_code", codes)):
            if line[field] and line[field] not in found:
                errors.setdefault("lines", {}).setdefault(str(number), {})[field] = [
                    _("That %(field)s doesn't exist.") % {"field": field.replace("_", " ")}
                ]
    if values.get("delivery_date") and values["delivery_date"] < values["date"]:
        errors["delivery_date"] = [_("The delivery date is before the order date.")]
    if errors:
        raise serializers.ValidationError(errors)
    return {
        "supplier": supplier,
        "terms": terms,
        "lines": [
            {
                **line,
                "account": accounts.get(line["account"]),
                "tax_code": codes.get(line["tax_code"]),
            }
            for line in lines
        ],
    }


def _keep_lines(order: PurchaseOrder, wanted: list[dict[str, Any]]) -> None:
    """Lines by id: update the ones sent, add the new, remove the rest — never a line with
    receipts or bills, nor below what was received or billed."""
    existing = {line.public_id: line for line in order.lines.all()}
    billed_lines = set(
        BillLine.objects.filter(po_line__document=order)
        .exclude(document__status="void")
        .values_list("po_line_id", flat=True)
    )
    errors: dict[str, Any] = {}
    kept: set[Any] = set()
    for number, values in enumerate(wanted):
        current = existing.get(values["id"]) if values["id"] else None
        if values["id"] and current is None:
            errors[str(number)] = {"id": [_("That line isn't on this purchase order.")]}
            continue
        if current is not None:
            kept.add(current.public_id)
            floor = max(Decimal(current.quantity_received), Decimal(current.quantity_billed))
            if Decimal(values["quantity"]) < floor:
                errors[str(number)] = {
                    "quantity": [
                        _("%(quantity)s are received or billed on this line already.")
                        % {"quantity": f"{floor.normalize():f}"}
                    ]
                }
    for public_id, old in existing.items():
        if public_id in kept:
            continue
        if old.quantity_received or old.quantity_billed or old.pk in billed_lines:
            errors.setdefault("removed", []).append(
                _("“%(line)s” has receipts or bills: it can't be removed.")
                % {"line": old.description or old.position + 1}
            )
    if errors:
        raise serializers.ValidationError({"lines": errors})
    for public_id, old in existing.items():
        if public_id not in kept:
            old.delete()
    for position, values in enumerate(wanted):
        found = existing.get(values["id"]) if values["id"] else None
        line = found or PurchaseOrderLine(organisation=order.organisation, document=order)
        line.position = position
        for field in LINE_FIELDS:
            setattr(line, field, values[field])
        line.tracking = dict(values["tracking"] or {})
        line.save()


def _save(order: PurchaseOrder, values: dict[str, Any], records: dict[str, Any], user: Any) -> Any:
    from .approvals import REVISABLE, recalculate, revise

    revising = order.pk is not None and order.status in REVISABLE
    order.contact = records["supplier"]
    order.terms = records["terms"]
    for field in HEADER:
        setattr(order, field, values[field])
    if order.pk:
        order.version += 1
    order.save()
    _keep_lines(order, records["lines"])
    if revising:
        return revise(order, user)
    return recalculate(order)


def _status_filter(text: str | None) -> list[str]:
    wanted = [s.strip() for s in (text or "").split(",") if s.strip()]
    return [s for s in wanted if s in PurchaseOrderStatus.values]


class PurchaseOrderListView(APIView):
    @requires_permission(PO_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="purchase_orders_list",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("supplier", OpenApiTypes.UUID),
            OpenApiParameter("q", str),
            OpenApiParameter("page", int),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        query = request.query_params
        orders = PurchaseOrder.objects.filter(deleted_at__isnull=True).select_related(
            "contact", "organisation"
        )
        supplier = _uuid(query.get("supplier"))
        if supplier:
            orders = orders.filter(contact__public_id=supplier)
        text = (query.get("q") or "").strip()
        if text:
            orders = orders.filter(
                Q(number__icontains=text)
                | Q(reference__icontains=text)
                | Q(contact__display_name__icontains=text)
            )
        counts = dict(
            orders.order_by()
            .values_list("status")
            .annotate(n=Count("pk"))
            .values_list("status", "n")
        )
        statuses = _status_filter(query.get("status"))
        if statuses:
            orders = orders.filter(status__in=statuses)
        raw = str(query.get("page") or "1")
        page = max(int(raw), 1) if raw.isdigit() else 1
        total = orders.count()
        chunk = orders.order_by("-date", "-pk")[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        return Response(
            {
                "count": total,
                "page": page,
                "pages": max(1, -(-total // PAGE_SIZE)),
                "counts": {key: counts.get(key, 0) for key in PurchaseOrderStatus.values},
                "results": [order_row(order) for order in chunk],
            }
        )

    @requires_permission(PO_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="purchase_orders_create",
        request=OrderSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = OrderSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        for line in values["lines"]:
            line["id"] = None  # a new PO has no lines yet
        records = _resolve(values)
        with transaction.atomic():
            draft = PurchaseOrder(organisation=current_org(), created_by=_person(request.user))
            order = _save(draft, values, records, request.user)
        return Response(order_detail(order, request.user), status=status.HTTP_201_CREATED)


class ApprovalLimitView(APIView):
    @requires_permission(PO_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="purchase_orders_approval_limit", responses={200: OpenApiTypes.OBJECT}
    )
    def get(self, request: Request, org: Any) -> Response:
        """The person's purchase-order approval limit (the new PO editor's limit indicator)."""
        from numo9.rbac.approvals import effective_limit

        from .approvals import DOC_TYPE

        limit = effective_limit(_person(request.user), DOC_TYPE, organisation=current_org())
        return Response({"limit": None if limit is None else _money(limit)})


class PurchaseOrderDetailView(APIView):
    @requires_permission(PO_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="purchase_orders_detail", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(order_detail(_order(public_id), request.user))

    @requires_permission(PO_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="purchase_orders_update",
        request=OrderSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        order = _order(public_id)
        if order.status not in EDITABLE:
            return Response(
                {
                    "code": "purchases.po.not_editable",
                    "detail": _("%(order)s is %(status)s: it can't be edited.")
                    % {
                        "order": str(order),
                        "status": str(PurchaseOrderStatus(order.status).label).lower(),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        incoming = OrderSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        if values.get("version") is not None and values["version"] != order.version:
            return Response(
                {
                    "code": "purchases.po.stale",
                    "detail": _(
                        "Someone else saved this purchase order: reload it to see their changes."
                    ),
                    "version": order.version,
                },
                status=status.HTTP_409_CONFLICT,
            )
        records = _resolve(values)
        with transaction.atomic():
            locked = PurchaseOrder._base_manager.select_for_update().get(pk=order.pk)
            saved = _save(locked, values, records, request.user)
        return Response(order_detail(_order(saved.public_id), request.user))

    @requires_permission(PO_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="purchase_orders_delete", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        order = _order(public_id)
        if order.status != PurchaseOrderStatus.DRAFT:
            return Response(
                {
                    "code": "purchases.po.not_deletable",
                    "detail": _("Only a draft purchase order can be deleted: cancel it instead."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class _ActionView(APIView):
    def act(self, order: PurchaseOrder, request: Request) -> PurchaseOrder:
        raise NotImplementedError

    def run(self, request: Request, public_id: Any) -> Response:
        order = _order(public_id)
        try:
            done = self.act(order, request)
        except LedgerError as error:
            return _refused(error)
        return Response(order_detail(_order(done.public_id), request.user))


class PurchaseOrderSubmitView(_ActionView):
    @requires_permission(PO_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="purchase_orders_submit", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, order: PurchaseOrder, request: Request) -> PurchaseOrder:
        from .approvals import submit

        return submit(order, request.user)


class PurchaseOrderApproveView(_ActionView):
    @requires_permission(PO_APPROVE.key)
    @requires_feature(APPROVE)
    @extend_schema(
        operation_id="purchase_orders_approve", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, order: PurchaseOrder, request: Request) -> PurchaseOrder:
        from .approvals import approve

        return approve(order, request.user)


class PurchaseOrderCancelView(_ActionView):
    @requires_permission(PO_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="purchase_orders_cancel", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, order: PurchaseOrder, request: Request) -> PurchaseOrder:
        from .approvals import cancel

        return cancel(order, request.user)


class PurchaseOrderCloseView(_ActionView):
    @requires_permission(PO_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="purchase_orders_close", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, order: PurchaseOrder, request: Request) -> PurchaseOrder:
        from .approvals import close

        return close(order, request.user)


class PurchaseOrderMatchView(APIView):
    @requires_permission(PO_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="purchase_orders_match", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        from .matching import match_order

        return Response(match_order(_order(public_id)))


class PurchaseOrderPdfView(APIView):
    @requires_permission(PO_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="purchase_orders_pdf", responses={(200, "application/pdf"): bytes})
    def get(self, request: Request, org: Any, public_id: Any) -> HttpResponse:
        from .email import pdf_file_name
        from .pdf import render_purchase_order_pdf

        order = _order(public_id)
        response = HttpResponse(render_purchase_order_pdf(order), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{pdf_file_name(order)}"'
        response["Cache-Control"] = "private, no-store"
        return response


class OrderSendSerializer(serializers.Serializer[Any]):
    to = serializers.ListField(
        child=serializers.EmailField(max_length=254), min_length=1, max_length=20
    )
    subject = serializers.CharField(max_length=300, required=False, allow_blank=True)
    message = serializers.CharField(max_length=5000, allow_blank=True, required=False)


class PurchaseOrderSendView(APIView):
    @requires_permission(PO_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="purchase_orders_email_defaults", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        from .email import default_email, pdf_file_name

        order = _order(public_id)
        defaults = default_email(order)
        return Response(
            {
                "to": defaults.to,
                "subject": defaults.subject,
                "message": defaults.message,
                "language": defaults.language,
                "file_name": pdf_file_name(order),
                "sent_at": order.sent_at.isoformat() if order.sent_at else None,
            }
        )

    @requires_permission(PO_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="purchase_orders_send", request=OrderSendSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from .email import send_purchase_order

        order = _order(public_id)
        data = OrderSendSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        try:
            with transaction.atomic():
                sent = send_purchase_order(
                    order,
                    request.user,
                    to=values["to"],
                    subject=values.get("subject") or None,
                    message=values.get("message"),
                )
        except LedgerError as error:
            return _refused(error)
        return Response({"sent": len(sent), **order_detail(_order(order.public_id), request.user)})


# ---- goods receipts ------------------------------------------------------------------------


class ReceiptLineSerializer(serializers.Serializer[Any]):
    po_line = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4)


class ReceiptSerializer(serializers.Serializer[Any]):
    purchase_order = serializers.UUIDField()
    date = serializers.DateField(required=False, allow_null=True, default=None)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = ReceiptLineSerializer(many=True, min_length=1, max_length=500)  # type: ignore[call-arg]
    confirm_over = serializers.BooleanField(required=False, default=False)


def _receipt(public_id: Any) -> GoodsReceipt:
    found: GoodsReceipt | None = (
        GoodsReceipt.objects.select_related("purchase_order", "received_by")
        .filter(public_id=public_id)
        .first()
    )
    if found is None:
        raise NotFound(_("There's no goods receipt with this id in this organisation."))
    return found


class ReceiptListView(APIView):
    @requires_permission(PO_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="receipts_list",
        parameters=[OpenApiParameter("purchase_order", OpenApiTypes.UUID)],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        receipts = GoodsReceipt.objects.select_related("purchase_order", "received_by")
        order = _uuid(request.query_params.get("purchase_order"))
        if order:
            receipts = receipts.filter(purchase_order__public_id=order)
        chunk = receipts.order_by("-date", "-pk")[:200]
        return Response({"results": [receipt_row(r) for r in chunk]})

    @requires_permission(PO_RECEIVE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="receipts_create",
        request=ReceiptSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        from .receipts import receive

        incoming = ReceiptSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = incoming.validated_data
        order = _order(values["purchase_order"])
        lines = {
            line.public_id: line
            for line in order.lines.filter(public_id__in=[x["po_line"] for x in values["lines"]])
        }
        missing = [str(x["po_line"]) for x in values["lines"] if x["po_line"] not in lines]
        if missing:
            raise serializers.ValidationError(
                {"lines": [_("A line isn't on %(order)s.") % {"order": str(order)}]}
            )
        try:
            result = receive(
                order,
                request.user,
                [(lines[x["po_line"]], x["quantity"]) for x in values["lines"]],
                date=values["date"],
                notes=values["notes"],
                confirm_over=values["confirm_over"],
            )
        except LedgerError as error:
            return _refused(error)
        return Response(
            {
                **receipt_row(_receipt(result.receipt.public_id)),
                "warnings": [w.as_dict() for w in result.warnings],
                "purchase_order_status": PurchaseOrder.objects.get(pk=order.pk).status,
            },
            status=status.HTTP_201_CREATED,
        )


class ReceiptDetailView(APIView):
    @requires_permission(PO_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="receipts_detail", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(receipt_row(_receipt(public_id)))


class ReceiptReverseView(APIView):
    @requires_permission(PO_RECEIVE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="receipts_reverse", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from .receipts import reverse_receipt

        receipt = _receipt(public_id)
        data = request.data if isinstance(request.data, dict) else {}
        try:
            done = reverse_receipt(receipt, request.user, str(data.get("reason") or ""))
        except LedgerError as error:
            return _refused(error)
        return Response(receipt_row(_receipt(done.public_id)))


# ---- commitment report ---------------------------------------------------------------------


class CommitmentReportView(APIView):
    @requires_permission(PO_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="reports_commitments",
        parameters=[
            OpenApiParameter("by", str, enum=["account", "supplier", "month"]),
            OpenApiParameter("from", OpenApiTypes.DATE),
            OpenApiParameter("to", OpenApiTypes.DATE),
            OpenApiParameter("export", str, enum=["csv", "xlsx"]),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response | HttpResponse:
        from .commitments import GROUPINGS, commitments, export_commitments

        query = request.query_params
        by = query.get("by") or "account"
        if by not in GROUPINGS:
            raise serializers.ValidationError({"by": [_("Group by account, supplier or month.")]})
        day = serializers.DateField(allow_null=True)
        try:
            date_from = day.to_internal_value(query["from"]) if query.get("from") else None
            date_to = day.to_internal_value(query["to"]) if query.get("to") else None
        except serializers.ValidationError:
            raise serializers.ValidationError({"from": [_("Enter dates as YYYY-MM-DD.")]}) from None
        result = commitments(current_org(), by=by, date_from=date_from, date_to=date_to)
        fmt = query.get("export") or ""
        if fmt in ("csv", "xlsx"):
            locale = getattr(request, "LANGUAGE_CODE", None)
            content, content_type, name = export_commitments(result, fmt, locale=locale)
            response = HttpResponse(content, content_type=content_type)
            response["Content-Disposition"] = f'attachment; filename="{name}"'
            response["Cache-Control"] = "private, no-store"
            return response
        return Response(
            {
                **result.as_dict(),
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            }
        )
