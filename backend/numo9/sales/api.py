"""Invoice email API (D-03a-T12), under ``/api/v1/``.

- ``GET o/<org>/invoices/<id>/email`` — the composer's defaults (recipients, subject, message,
  language, PDF file name) and the earlier sends (``sales.invoices.view``).
- ``POST o/<org>/invoices/<id>/email`` ``{to, subject, message}`` — send it
  (``sales.invoices.send``; feature ``accounting.sales_invoices.write``): 201 with the logged
  send; 400 ``sales.invoice.not_sendable`` / ``sales.invoice.no_recipient``.
- ``GET o/<org>/invoices/<id>/pdf`` — the PDF as the customer gets it (preview in the composer).
- ``GET o/<org>/invoices/<id>/credit`` — the customer's credit check for the invoice as it
  stands (D-03a-T16 editor banner): ``outcome`` ``no_limit`` / ``within`` / ``warn`` / ``block`` /
  ``override``, the figures, the warning ``message`` and any override request still waiting.
- ``POST o/<org>/invoices/<id>/credit/override`` ``{reason}`` — ask to go over the limit for this
  invoice (``sales.invoices.write``); the people who may approve overrides are notified (B-01).
- ``GET invoice-view/<token>`` — public: the "View invoice" link of an email; records the first
  view and answers the PDF; 404 for a bad, expired or voided link.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.ledger.models import LedgerError
from numo9.rbac.drf import PUBLIC, RequiresPermission, requires_permission

from . import email as service
from .models import Invoice, InvoiceEmail
from .permissions import INVOICES_SEND, INVOICES_VIEW, INVOICES_WRITE
from .posting import InvoiceRefused

READ = "accounting.sales_invoices.read"
WRITE = "accounting.sales_invoices.write"


def _invoice(public_id: Any) -> Invoice:
    invoice: Invoice | None = (
        Invoice.objects.select_related("contact", "organisation")
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if invoice is None:
        raise NotFound(_("There's no invoice with this id in this organisation."))
    return invoice


def send_row(row: InvoiceEmail) -> dict[str, Any]:
    return {
        "id": str(row.public_id),
        "recipients": list(row.recipients),
        "subject": row.subject,
        "language": row.language,
        "file_name": row.file_name,
        "sent_at": row.created_at.isoformat(),
        "sent_by": row.sent_by.get_full_name() if row.sent_by else "",
        "viewed_at": row.viewed_at.isoformat() if row.viewed_at else None,
    }


def _refused(error: InvoiceRefused) -> Response:
    return Response(
        {"code": error.code, "detail": " ".join(str(m) for m in error.messages)},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _pdf(data: bytes, name: str) -> HttpResponse:
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{name}"'
    response["Cache-Control"] = "private, no-store"
    return response


class InvoiceSendSerializer(serializers.Serializer[Any]):
    to = serializers.ListField(
        child=serializers.EmailField(max_length=254), min_length=1, max_length=20
    )
    subject = serializers.CharField(max_length=300)
    message = serializers.CharField(max_length=5000, allow_blank=True, required=False)


class InvoiceEmailView(APIView):
    queryset = Invoice._base_manager.none()

    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="invoice_email_defaults", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        invoice = _invoice(public_id)
        defaults = service.default_email(invoice)
        sends = InvoiceEmail.objects.select_related("sent_by").filter(invoice=invoice)
        return Response(
            {
                "to": defaults.to,
                "subject": defaults.subject,
                "message": defaults.message,
                "language": defaults.language,
                "file_name": service.pdf_file_name(invoice),
                "sendable": invoice.status in service.SENDABLE,
                "sent_at": invoice.sent_at.isoformat() if invoice.sent_at else None,
                "viewed_at": invoice.viewed_at.isoformat() if invoice.viewed_at else None,
                "sends": [send_row(row) for row in sends],
            }
        )

    @requires_permission(INVOICES_SEND.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="invoice_email_send", request=InvoiceSendSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        invoice = _invoice(public_id)  # another organisation's invoice: 404 before anything
        data = InvoiceSendSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        try:
            with transaction.atomic():
                row = service.send_invoice(
                    invoice,
                    request.user,
                    to=values["to"],
                    subject=values["subject"],
                    message=values.get("message", ""),
                )
        except InvoiceRefused as error:
            return _refused(error)
        return Response(send_row(row), status=status.HTTP_201_CREATED)


def _money(value: Any) -> str | None:
    return None if value is None else f"{value:.2f}"


def credit_payload(invoice: Invoice) -> dict[str, Any]:
    from django.utils import timezone

    from numo9.contacts.models import CreditOverride, CreditOverrideStatus

    from .credit import DOCUMENT_TYPE, invoice_credit

    check = invoice_credit(invoice)
    pending = (
        CreditOverride.objects.filter(
            contact=invoice.contact,
            document_type=DOCUMENT_TYPE,
            document_ref=str(invoice.public_id),
            status=CreditOverrideStatus.PENDING,
            expires_at__gt=timezone.now(),
            deleted_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    return {
        "outcome": check.outcome,
        "mode": check.mode,
        "limit": _money(check.limit),
        "exposure": _money(check.exposure),
        "amount": _money(check.amount),
        "projected": _money(check.projected),
        "over_by": _money(check.over_by),
        "message": check.message,
        "contact": {"id": str(invoice.contact.public_id), "name": invoice.contact.display_name},
        "pending_override": (
            {
                "id": str(pending.public_id),
                "amount": _money(pending.amount),
                "requested_at": pending.created_at.isoformat(),
            }
            if pending
            else None
        ),
    }


class InvoiceCreditView(APIView):
    queryset = Invoice._base_manager.none()

    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="invoice_credit_check", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        invoice = _invoice(public_id)
        try:
            return Response(credit_payload(invoice))
        except LedgerError as error:
            return Response(
                {"code": error.code, "detail": " ".join(str(m) for m in error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class OverrideRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(max_length=500)


class InvoiceCreditOverrideView(APIView):
    queryset = Invoice._base_manager.none()

    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="invoice_credit_override_request",
        request=OverrideRequestSerializer,
        responses={201: dict},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from numo9.contacts.credit import request_override

        from .credit import DOCUMENT_TYPE, invoice_credit

        invoice = _invoice(public_id)
        data = OverrideRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        check = invoice_credit(invoice)
        if check.outcome != "block":
            return Response(
                {
                    "code": "sales.invoice.override_not_needed",
                    "detail": _("This invoice is within the customer's credit limit."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            request_override(
                invoice.contact,
                check.amount,
                user=request.user,
                reason=data.validated_data["reason"],
                document_type=DOCUMENT_TYPE,
                document_ref=str(invoice.public_id),
            )
        return Response(credit_payload(invoice), status=status.HTTP_201_CREATED)


class InvoicePdfView(APIView):
    queryset = Invoice._base_manager.none()

    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="invoice_pdf", responses={(200, "application/pdf"): bytes})
    def get(self, request: Request, org: Any, public_id: Any) -> HttpResponse | Response:
        from .pdf import render_invoice_pdf

        invoice = _invoice(public_id)
        try:
            data = render_invoice_pdf(invoice)
        except LedgerError as error:  # the books can't price it yet (no receivable account…)
            return Response(
                {"code": error.code, "detail": " ".join(str(m) for m in error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _pdf(data, service.pdf_file_name(invoice))


class InvoiceViewLinkView(APIView):
    # AllowAny marks the OpenAPI operation as open to signed-out callers (the email's link).
    permission_classes = [RequiresPermission, AllowAny]
    authentication_classes: list[Any] = []

    @requires_permission(PUBLIC)  # the signed token is the credential
    @extend_schema(
        operation_id="invoice_view_link",
        summary="The 'View invoice' link of an invoice email (records the first view)",
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, token: str) -> HttpResponse:
        from numo9.files.storage import open_object

        row = service.mark_viewed(token)
        if row is None:
            raise NotFound(_("This invoice link isn't valid any more."))
        handle = open_object(row.file_key)
        try:
            data = handle.read()
        finally:
            handle.close()
        return _pdf(data, row.file_name)
