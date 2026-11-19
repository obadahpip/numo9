"""Contact activity, statements and supplier reconciliation API (B-02-T09), under
``/api/v1/o/<org>/contacts/<id>/``:

- ``GET activity`` ``?type=&from=&to=`` — the timeline, newest first; ``POST activity``
  ``{title}`` — add a note;
- ``GET statement`` ``?kind=outstanding|activity&as_at=&from=&side=`` — the statement as data (the
  preview); ``GET statement.pdf`` — the same as the PDF; ``POST statement/send``
  ``{kind, as_at, from, to}`` — email it (A-07) and keep it in the history;
  ``GET statements`` — what was sent;
- ``GET`` / ``POST supplier-statements`` — the supplier's statements, add one from a CSV/XLSX file
  (multipart ``file``, ``statement_date``); ``GET supplier-statements/<sid>/reconciliation`` —
  pairs, unmatched on both sides, totals; ``PATCH supplier-statements/<sid>/lines/<lid>``
  ``{manual_ref, note}`` — match by hand and annotate.

Permissions ``contacts.contacts.view`` / ``.manage``; features ``accounting.contacts.read`` /
``.write``.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.rbac.drf import requires_permission

from .activity import emit, timeline
from .api import READ, WRITE, _one
from .models import ActivityType, Contact, StatementSend, SupplierStatement, SupplierStatementLine
from .permissions import CONTACTS_MANAGE, CONTACTS_VIEW
from .reconciliation import reconcile
from .statement_engine import build_statement
from .statements import (
    StatementDocument,
    StatementError,
    StatementKind,
    render_statement_pdf,
    send_statement,
)


def _date(params: Any, name: str, default: dt.date | None = None) -> dt.date | None:
    raw = params.get(name)
    if not raw:
        return default
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        raise ValidationError({name: [_("Use a date like 2026-03-31.")]}) from None


def _money(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


def _statement(contact: Contact, params: Any) -> StatementDocument:
    kind = params.get("kind", "outstanding")
    if kind not in StatementKind.__members__.values():
        raise ValidationError({"kind": [_("Choose outstanding or activity.")]})
    as_at = _date(params, "as_at", timezone.localdate()) or timezone.localdate()
    start = _date(params, "from")
    side = params.get("side") or None
    if side not in (None, "receivables", "payables"):
        raise ValidationError({"side": [_("Choose receivables or payables.")]})
    try:
        return build_statement(contact, kind, as_at, start=start, side=side)
    except ValueError as error:
        raise ValidationError({"from": [str(error)]}) from None


def statement_json(document: StatementDocument) -> dict[str, Any]:
    return {
        "kind": document.kind.value,
        "as_at": document.as_at,
        "period_start": document.period_start,
        "currency": document.currency,
        "issuer": document.issuer.legal_name,
        "contact": document.contact.legal_name,
        "contact_number": document.contact_number,
        "opening_balance": _money(document.opening_balance),
        "lines": [
            {
                "date": line.date,
                "document": line.document,
                "description": line.description,
                "due_date": line.due_date,
                "amount": _money(line.amount),
                "balance": _money(line.balance),
            }
            for line in document.lines
        ],
        "aging": {key: _money(value) for key, value in document.aging.items()},
        "amount_due": _money(document.amount_due),
    }


STATEMENT_PARAMS = [
    OpenApiParameter("kind", str, enum=["outstanding", "activity"]),
    OpenApiParameter("as_at", OpenApiTypes.DATE),
    OpenApiParameter("from", OpenApiTypes.DATE),
    OpenApiParameter("side", str, enum=["receivables", "payables"]),
]


class ActivityView(APIView):
    queryset = Contact._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="contacts_activity",
        summary="A contact's activity timeline, newest first",
        parameters=[
            OpenApiParameter("type", str, many=True),
            OpenApiParameter("from", OpenApiTypes.DATE),
            OpenApiParameter("to", OpenApiTypes.DATE),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        contact = _one(public_id)
        types = [t for t in request.query_params.getlist("type") if t]
        events = timeline(
            contact,
            types=types or None,
            start=_date(request.query_params, "from"),
            end=_date(request.query_params, "to"),
        )[:500]
        return Response(
            {
                "results": [
                    {
                        "id": str(e.public_id),
                        "type": e.type,
                        "title": e.title,
                        "ref_type": e.ref_type,
                        "ref_id": e.ref_id,
                        "amount": _money(e.amount),
                        "currency": e.currency,
                        "occurred_at": e.occurred_at,
                        "by": e.actor_label,
                    }
                    for e in events
                ],
                "types": [{"value": v, "label": str(label)} for v, label in ActivityType.choices],
            }
        )

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="contacts_activity_note",
        summary="Add a note to a contact's timeline",
        request=OpenApiTypes.OBJECT,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        contact = _one(public_id)
        body: Any = request.data
        title = str(body.get("title", "")).strip()
        if not title:
            raise ValidationError({"title": [_("Write the note.")]})
        event = emit(contact, ActivityType.NOTE, title, actor=request.user)
        return Response({"id": str(event.public_id), "title": event.title}, status=201)


class StatementView(APIView):
    queryset = Contact._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="contacts_statement",
        summary="A contact's statement (preview data)",
        parameters=STATEMENT_PARAMS,
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(statement_json(_statement(_one(public_id), request.query_params)))


class StatementPdfView(APIView):
    queryset = Contact._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="contacts_statement_pdf",
        summary="A contact's statement as a PDF (Letter)",
        parameters=STATEMENT_PARAMS,
        responses={200: OpenApiTypes.BINARY},
    )
    def get(self, request: Request, org: Any, public_id: Any) -> HttpResponse:
        contact = _one(public_id)
        document = _statement(contact, request.query_params)
        pdf = render_statement_pdf(document, locale=contact.language or "en-ca")
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="statement-{contact.number}-{document.as_at:%Y-%m-%d}.pdf"'
        )
        return response


class SendSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(
        choices=[("outstanding", "outstanding"), ("activity", "activity")]
    )
    as_at = serializers.DateField()
    start = serializers.DateField(required=False, allow_null=True)
    side = serializers.ChoiceField(
        choices=[("receivables", "receivables"), ("payables", "payables")], required=False
    )
    to = serializers.ListField(child=serializers.EmailField(), required=False)


def _send_row(send: StatementSend) -> dict[str, Any]:
    return {
        "id": str(send.public_id),
        "kind": send.kind,
        "as_at": send.as_at,
        "period_start": send.period_start,
        "amount_due": _money(send.amount_due),
        "currency": send.currency,
        "recipients": send.recipients,
        "sent_at": send.created_at,
    }


class StatementSendView(APIView):
    parser_classes = (JSONParser,)
    queryset = Contact._base_manager.none()

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="contacts_statement_send",
        summary="Email the statement to the contact and keep it in the history",
        request=SendSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        contact = _one(public_id)
        incoming = SendSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        data = incoming.validated_data
        params = {
            "kind": data["kind"],
            "as_at": data["as_at"].isoformat(),
            "from": data["start"].isoformat() if data.get("start") else "",
            "side": data.get("side") or "",
        }
        document = _statement(contact, params)
        try:
            send = send_statement(contact, document, to=data.get("to") or None, user=request.user)
        except StatementError:
            raise ValidationError(
                {"to": [_("Nobody at this contact receives emails: add an address to send to.")]}
            ) from None
        return Response(_send_row(send), status=201)


class StatementHistoryView(APIView):
    queryset = Contact._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="contacts_statements_sent", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        contact = _one(public_id)
        sends = StatementSend.objects.filter(contact=contact).order_by("-created_at")[:200]
        return Response({"results": [_send_row(s) for s in sends]})


def _supplier_statement(contact: Contact, statement_id: Any) -> SupplierStatement:
    found: SupplierStatement | None = SupplierStatement.objects.filter(
        contact=contact, public_id=statement_id
    ).first()
    if found is None:
        raise NotFound
    return found


class SupplierStatementsView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    queryset = Contact._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="contacts_supplier_statements", responses={200: OpenApiTypes.OBJECT}
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        contact = _one(public_id)
        rows = SupplierStatement.objects.filter(contact=contact).order_by("-statement_date")[:100]
        return Response(
            {
                "results": [
                    {
                        "id": str(s.public_id),
                        "statement_date": s.statement_date,
                        "their_balance": _money(s.their_balance),
                        "file_name": s.file_name,
                    }
                    for s in rows
                ]
            }
        )

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="contacts_supplier_statement_upload",
        summary="Add a supplier statement from a CSV or XLSX file",
        request={"multipart/form-data": OpenApiTypes.OBJECT},
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from .supplier_statements import import_supplier_statement

        contact = _one(public_id)
        upload = request.FILES.get("file")
        statement_date = _date(request.data, "statement_date")
        if upload is None or statement_date is None:
            raise ValidationError({"file": [_("Choose the statement file and its date.")]})
        try:
            statement = import_supplier_statement(
                contact, upload.read(), upload.name or "statement.csv", statement_date
            )
        except DjangoValidationError as error:
            raise ValidationError({"file": [str(m) for m in error.messages]}) from None
        return Response({"id": str(statement.public_id)}, status=status.HTTP_201_CREATED)


def _line(line: SupplierStatementLine) -> dict[str, Any]:
    return {
        "id": str(line.public_id),
        "date": line.date,
        "invoice_number": line.invoice_number,
        "reference": line.reference,
        "description": line.description,
        "amount": _money(line.amount),
        "note": line.note,
        "manual_ref": line.manual_ref,
    }


def _ours(item: Any) -> dict[str, Any]:
    return {
        "ref": item.ref,
        "date": item.date,
        "document": item.document,
        "amount": _money(item.amount),
        "description": item.description,
    }


class ReconciliationView(APIView):
    queryset = Contact._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="contacts_supplier_reconciliation",
        summary="Their statement against our documents: pairs, unmatched, totals",
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any, public_id: Any, statement_id: Any) -> Response:
        statement = _supplier_statement(_one(public_id), statement_id)
        report = reconcile(statement)
        lines = {
            line.pk: line for line in SupplierStatementLine.objects.filter(statement=statement)
        }
        return Response(
            {
                "statement_date": statement.statement_date,
                "pairs": [
                    {
                        "theirs": _line(lines[p.line_id]),
                        "ours": _ours(p.ours),
                        "how": p.how,
                        "difference": _money(p.difference),
                    }
                    for p in report.pairs
                ],
                "unmatched_theirs": [_line(line) for line in report.unmatched_theirs],
                "unmatched_ours": [_ours(item) for item in report.unmatched_ours],
                "their_total": _money(report.their_total),
                "our_total": _money(report.our_total),
                "difference": _money(report.difference),
            }
        )


class LineSerializer(serializers.Serializer[Any]):
    manual_ref = serializers.CharField(max_length=100, allow_blank=True, required=False)
    note = serializers.CharField(max_length=500, allow_blank=True, required=False)


class ReconciliationLineView(APIView):
    parser_classes = (JSONParser,)
    queryset = Contact._base_manager.none()

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="contacts_supplier_line_update",
        summary="Match a supplier statement line by hand or annotate it",
        request=LineSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def patch(
        self, request: Request, org: Any, public_id: Any, statement_id: Any, line_id: Any
    ) -> Response:
        statement = _supplier_statement(_one(public_id), statement_id)
        line = SupplierStatementLine.objects.filter(statement=statement, public_id=line_id).first()
        if line is None:
            raise NotFound
        incoming = LineSerializer(data=request.data, partial=True)
        incoming.is_valid(raise_exception=True)
        for field, value in incoming.validated_data.items():
            setattr(line, field, value)
        line.save()
        return Response(_line(line))
