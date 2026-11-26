"""Conversion balances API (C-05-T09), under ``/api/v1/o/<org>/conversion/``. Feature keys
``accounting.conversion_balances.read`` / ``.write`` (the catalogue's conversion feature);
permissions ``accounting.conversion.view`` / ``.manage`` (corrections after finalising: advisers
only, refused by the service for anyone else).

- ``GET conversion/`` — the organisation's conversion (``session``: date, status, lock balances,
  the wizard's ``step`` and ``completed_steps``, the opening journal, the corrections; ``null``
  before one is started), the ``difference`` (C-05-T04), the wizard's ``steps`` and
  ``is_adviser``;
- ``POST conversion/`` ``{conversion_date}`` — start it (201; a second is refused);
- ``PATCH conversion/`` ``{conversion_date?, lock_balances?, step?, completed_steps?}`` — the
  wizard saves its progress here at every step;
- ``GET conversion/lines`` · ``PUT conversion/lines`` ``{lines: [{account, debit, credit,
  description, contact}]}`` — set the opening balances of those accounts (a line with neither a
  debit nor a credit removes the account's balance); all or nothing, problems per row;
- ``GET conversion/documents?kind=invoice|bill`` · ``POST conversion/documents`` ``{kind,
  rows, dry_run}`` — add open documents (the paste-friendly grids: ``contact`` by id or name);
  all or nothing, problems per row (``dry_run`` validates only) ·
  ``POST conversion/documents/remove`` ``{ids}``;
- ``GET conversion/difference`` — the difference meter;
- ``POST conversion/finalise`` ``{lock_balances?}`` — finalise (C-05-T05, T06);
- ``POST conversion/import/mapping`` (multipart ``file``) — the trial balance's columns and the
  suggested mapping · ``POST conversion/import`` (multipart ``file``, ``mapping`` JSON,
  ``dry_run``) — import it (C-05-T08);
- ``GET`` / ``POST conversion/corrections`` ``{reason, lines}`` — correcting opening journals
  (C-05-T07, advisers).

A refusal is a ``400`` ``{code, detail}`` (``conversion.unbalanced`` with ``params`` naming the
difference, ``conversion.control_mismatch``, ``conversion.session.finalised``…); a lock date
refusal of the posting engine is its ``409`` (``lock.violation``).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.orgsettings.locks import is_adviser
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from . import corrections, documents, finalise, services, tb_import
from .difference import difference
from .models import (
    ConversionCorrection,
    ConversionLine,
    ConversionSession,
    ConversionStep,
    OpeningDocument,
)
from .permissions import CONVERSION_MANAGE, CONVERSION_VIEW

READ = "accounting.conversion_balances.read"
WRITE = "accounting.conversion_balances.write"
MAX_FILE_SIZE = 25 * 1024 * 1024


# ---- shapes -------------------------------------------------------------------------------------


def _money(value: Any) -> str:
    return f"{value:.2f}"


def _person(user: Any) -> dict[str, str] | None:
    return {"id": str(user.public_id), "name": user.name or user.email} if user else None


def _entry(entry: Any) -> dict[str, Any] | None:
    if entry is None:
        return None
    return {
        "id": str(entry.public_id),
        "number": entry.number,
        "date": entry.date.isoformat(),
        "url": f"/o/{entry.organisation.public_id}/accounting/journals/{entry.public_id}",
    }


def _contact(contact: Any) -> dict[str, str] | None:
    return {"id": str(contact.public_id), "name": contact.display_name} if contact else None


def correction_row(row: ConversionCorrection) -> dict[str, Any]:
    return {
        "id": str(row.public_id),
        "reason": row.reason,
        "entry": _entry(row.entry),
        "created_by": _person(row.created_by),
        "created_at": row.created_at.isoformat(),
    }


def session_row(session: ConversionSession) -> dict[str, Any]:
    return {
        "id": str(session.public_id),
        "conversion_date": session.conversion_date.isoformat(),
        "status": session.status,
        "lock_balances": session.lock_balances,
        "step": session.step,
        "completed_steps": list(session.completed_steps or []),
        "finalised_by": _person(session.finalised_by),
        "finalised_at": session.finalised_at.isoformat() if session.finalised_at else None,
        "opening_entry": _entry(session.opening_entry),
        "corrections": [
            correction_row(c)
            for c in session.corrections.select_related("entry", "created_by").order_by("pk")
        ],
    }


def line_row(line: ConversionLine) -> dict[str, Any]:
    account = line.account
    return {
        "id": str(line.public_id),
        "account": {
            "id": str(account.public_id),
            "code": account.code,
            "name": account.name,
            "type": account.type,
            "subtype": account.subtype,
            "system_role": account.system_role,
            "is_bank": account.is_bank,
            "require_contact": account.require_contact,
        },
        "debit": _money(line.debit),
        "credit": _money(line.credit),
        "description": line.description,
        "contact": _contact(line.contact),
    }


def document_row(link: OpeningDocument) -> dict[str, Any]:
    document = link.document
    return {
        "id": str(link.public_id),
        "kind": link.kind,
        "document_id": str(document.public_id),
        "number": document.number,
        "supplier_invoice_no": getattr(document, "supplier_invoice_no", ""),
        "contact": _contact(document.contact),
        "date": document.date.isoformat(),
        "due_date": document.due_date.isoformat() if document.due_date else None,
        "reference": document.reference,
        "total": _money(document.total),
        "outstanding": _money(link.outstanding),
        "amount_due": _money(document.amount_due),
        "status": document.status,
    }


def steps() -> list[dict[str, str]]:
    return [{"key": s.value, "label": str(s.label)} for s in ConversionStep]


def _refused(error: Any) -> Response:
    messages = getattr(error, "messages", None) or [str(error)]
    body: dict[str, Any] = {
        "code": getattr(error, "code", None) or "invalid",
        "detail": " ".join(str(m) for m in messages),
    }
    if getattr(error, "params", None):
        body["params"] = error.params
    if hasattr(error, "error_dict"):
        body["errors"] = documents._errors(error)
        body["code"] = body["errors"][0]["code"]
    elif getattr(error, "error_list", None) and len(error.error_list) > 1:
        body["code"] = error.error_list[0].code or body["code"]
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def _session() -> ConversionSession | None:
    found: ConversionSession | None = (
        ConversionSession.objects.filter(deleted_at__isnull=True)
        .select_related("finalised_by", "opening_entry__organisation")
        .first()
    )
    return found


class SessionMissing(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "conversion.session.missing"


def _require_session() -> ConversionSession:
    session = _session()
    if session is None:
        raise SessionMissing(
            {"code": "conversion.session.missing", "detail": _("Start the conversion first.")}
        )
    return session


def _overview(session: ConversionSession | None, user: Any) -> dict[str, Any]:
    organisation = current_org()
    return {
        "session": session_row(session) if session else None,
        "difference": difference(session).as_dict() if session else None,
        "steps": steps(),
        "is_adviser": organisation is not None and is_adviser(user, organisation),
    }


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _account(value: Any) -> Any:
    from numo9.ledger.models import Account

    key = _uuid(value)
    return Account.objects.filter(public_id=key).first() if key else None


# ---- session ------------------------------------------------------------------------------------


class StartSerializer(serializers.Serializer[Any]):
    conversion_date = serializers.DateField()


class SessionPatchSerializer(serializers.Serializer[Any]):
    conversion_date = serializers.DateField(required=False)
    lock_balances = serializers.BooleanField(required=False)
    step = serializers.ChoiceField(choices=ConversionStep.values, required=False)
    completed_steps = serializers.ListField(
        child=serializers.ChoiceField(choices=ConversionStep.values), required=False
    )


class ConversionView(APIView):
    @requires_permission(CONVERSION_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="conversion_get", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any) -> Response:
        return Response(_overview(_session(), request.user))

    @requires_permission(CONVERSION_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="conversion_start",
        request=StartSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = StartSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            session = services.start_conversion(
                current_org(), payload.validated_data["conversion_date"], user=request.user
            )
        except DjangoValidationError as error:
            return _refused(error)
        return Response(_overview(session, request.user), status=status.HTTP_201_CREATED)

    @requires_permission(CONVERSION_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="conversion_update",
        request=SessionPatchSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def patch(self, request: Request, org: Any) -> Response:
        payload = SessionPatchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            session = services.update_session(_require_session(), **payload.validated_data)
        except DjangoValidationError as error:
            return _refused(error)
        return Response(_overview(session, request.user))


# ---- lines --------------------------------------------------------------------------------------


class LineInSerializer(serializers.Serializer[Any]):
    account = serializers.CharField()
    debit = serializers.CharField(required=False, allow_blank=True, default="")
    credit = serializers.CharField(required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    contact = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class LinesSerializer(serializers.Serializer[Any]):
    lines = LineInSerializer(many=True)


def _amount_or_zero(text: str) -> str:
    return (text or "").replace(",", "").strip() or "0"


class ConversionLinesView(APIView):
    @requires_permission(CONVERSION_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="conversion_lines", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any) -> Response:
        session = _session()
        rows = (
            ConversionLine.objects.filter(session=session, deleted_at__isnull=True)
            .select_related("account", "contact")
            .order_by("account__code")
            if session
            else []
        )
        return Response({"lines": [line_row(line) for line in rows]})

    @requires_permission(CONVERSION_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="conversion_lines_set",
        request=LinesSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def put(self, request: Request, org: Any) -> Response:
        payload = LinesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        session = _require_session()
        problems: list[dict[str, Any]] = []
        with transaction.atomic():
            for index, row in enumerate(payload.validated_data["lines"], start=1):
                account = _account(row["account"])
                if account is None:
                    problems.append(
                        {
                            "row": index,
                            "field": "account",
                            "code": "conversion.line.account",
                            "message": _("Choose an account of the chart."),
                        }
                    )
                    continue
                contact = None
                if row.get("contact"):
                    contact = documents._find_contact(row["contact"], "")
                    if contact is None:
                        problems.append(
                            {
                                "row": index,
                                "field": "contact",
                                "code": "conversion.line.contact",
                                "message": _("Choose a contact."),
                            }
                        )
                        continue
                debit, credit = _amount_or_zero(row["debit"]), _amount_or_zero(row["credit"])
                try:
                    with transaction.atomic():
                        if debit in ("0", "0.00") and credit in ("0", "0.00"):
                            services.remove_line(session, account)
                        else:
                            services.set_line(
                                session,
                                account,
                                debit=debit,
                                credit=credit,
                                description=row["description"],
                                contact=contact,
                            )
                except (DjangoValidationError, ArithmeticError) as error:
                    found = (
                        documents._errors(error)
                        if isinstance(error, DjangoValidationError)
                        else [{"field": "debit", "code": "conversion.line.amount", "message": ""}]
                    )
                    for item in found:
                        if not item["message"]:
                            item["message"] = _("Enter an amount.")
                        problems.append({"row": index, **item})
            if problems:
                transaction.set_rollback(True)
        if problems:
            return Response(
                {
                    "code": problems[0]["code"],
                    "detail": _("Nothing was saved: fix the rows listed."),
                    "rows": problems,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows = (
            ConversionLine.objects.filter(session=session, deleted_at__isnull=True)
            .select_related("account", "contact")
            .order_by("account__code")
        )
        return Response(
            {
                "lines": [line_row(line) for line in rows],
                "difference": difference(session).as_dict(),
            }
        )


# ---- documents ----------------------------------------------------------------------------------


class DocumentsSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=["invoice", "bill"])
    rows = serializers.ListField(child=serializers.DictField(), allow_empty=False, max_length=500)
    dry_run = serializers.BooleanField(required=False, default=False)


class RemoveSerializer(serializers.Serializer[Any]):
    ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


def _documents(session: ConversionSession | None, kind: str | None) -> list[dict[str, Any]]:
    if session is None:
        return []
    links = OpeningDocument.objects.filter(session=session, deleted_at__isnull=True).select_related(
        "invoice__contact", "bill__contact"
    )
    if kind:
        links = links.filter(kind=kind)
    rows = [document_row(link) for link in links]
    return sorted(rows, key=lambda r: (r["date"], r["number"]))


class ConversionDocumentsView(APIView):
    @requires_permission(CONVERSION_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="conversion_documents",
        parameters=[OpenApiParameter("kind", str, enum=["invoice", "bill"])],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        kind = request.query_params.get("kind") or None
        if kind not in (None, "invoice", "bill"):
            raise serializers.ValidationError({"kind": [_("Choose invoices or bills.")]})
        return Response({"documents": _documents(_session(), kind)})

    @requires_permission(CONVERSION_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="conversion_documents_add",
        request=DocumentsSerializer,
        responses={200: OpenApiTypes.OBJECT, 201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = DocumentsSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        session = _require_session()
        data = payload.validated_data
        try:
            report = documents.add_opening_rows(
                session, data["kind"], data["rows"], dry_run=data["dry_run"], user=request.user
            )
        except DjangoValidationError as error:
            return _refused(error)
        if report["errors"]:
            return Response(
                {
                    "code": "conversion.document.rows",
                    "detail": _("Nothing was saved: fix the rows listed."),
                    **report,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not data["dry_run"]:
            report["documents"] = _documents(session, data["kind"])
            report["difference"] = difference(session).as_dict()
        return Response(
            report, status=status.HTTP_200_OK if data["dry_run"] else status.HTTP_201_CREATED
        )


class ConversionDocumentsRemoveView(APIView):
    @requires_permission(CONVERSION_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="conversion_documents_remove",
        request=RemoveSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = RemoveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        session = _require_session()
        links = list(
            OpeningDocument.objects.filter(
                session=session,
                public_id__in=payload.validated_data["ids"],
                deleted_at__isnull=True,
            ).select_related("session", "invoice", "bill")
        )
        try:
            with transaction.atomic():
                for link in links:
                    documents.remove_opening_document(link)
        except DjangoValidationError as error:
            return _refused(error)
        return Response(
            {
                "removed": len(links),
                "documents": _documents(session, None),
                "difference": difference(session).as_dict(),
            }
        )


# ---- difference, finalise -----------------------------------------------------------------------


class ConversionDifferenceView(APIView):
    @requires_permission(CONVERSION_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="conversion_difference", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any) -> Response:
        session = _session()
        return Response({"difference": difference(session).as_dict() if session else None})


class FinaliseSerializer(serializers.Serializer[Any]):
    lock_balances = serializers.BooleanField(required=False, allow_null=True, default=None)


class ConversionFinaliseView(APIView):
    @requires_permission(CONVERSION_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="conversion_finalise",
        request=FinaliseSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = FinaliseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            session = finalise.finalise(
                _require_session(), request.user, lock=payload.validated_data["lock_balances"]
            )
        except DjangoValidationError as error:
            return _refused(error)
        return Response(_overview(session, request.user))


# ---- trial balance import -----------------------------------------------------------------------


class FileSerializer(serializers.Serializer[Any]):
    file = serializers.FileField()


class ImportSerializer(FileSerializer):
    mapping = serializers.CharField()
    dry_run = serializers.BooleanField(required=False, default=True)


def _read(upload: Any) -> bytes:
    if upload.size > MAX_FILE_SIZE:
        raise serializers.ValidationError(
            {"file": [_("The file is over 25 MB: split it or remove what isn't needed.")]}
        )
    data: bytes = upload.read()
    return data


class ConversionImportMappingView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    @requires_permission(CONVERSION_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="conversion_import_mapping",
        request={"multipart/form-data": FileSerializer},
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = FileSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        upload = payload.validated_data["file"]
        try:
            return Response(tb_import.suggest_mapping(_read(upload), upload.name))
        except DjangoValidationError as error:
            return _refused(error)
        except Exception as error:  # an unreadable file (ImportFileError and the like)
            if isinstance(error, serializers.ValidationError):
                raise
            return Response(
                {"code": "conversion.import.file", "detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ConversionImportView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    @requires_permission(CONVERSION_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="conversion_import",
        request={"multipart/form-data": ImportSerializer},
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = ImportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            mapping = json.loads(data["mapping"])
            if not isinstance(mapping, dict):
                raise ValueError
        except ValueError:
            raise serializers.ValidationError(
                {"mapping": [_("The mapping is a JSON object of field → column.")]}
            ) from None
        session = _require_session()
        try:
            report = tb_import.import_tb(
                session,
                _read(data["file"]),
                data["file"].name,
                mapping,
                dry_run=data["dry_run"],
            )
        except DjangoValidationError as error:
            return _refused(error)
        report["difference"] = difference(session).as_dict()
        code = status.HTTP_400_BAD_REQUEST if report["refused"] else status.HTTP_200_OK
        return Response(report, status=code)


# ---- corrections --------------------------------------------------------------------------------


class CorrectionSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(allow_blank=True)
    lines = LineInSerializer(many=True)


class ConversionCorrectionsView(APIView):
    @requires_permission(CONVERSION_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="conversion_corrections", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any) -> Response:
        session = _session()
        rows = (
            ConversionCorrection.objects.filter(session=session)
            .select_related("entry__organisation", "created_by")
            .order_by("pk")
            if session
            else []
        )
        return Response({"corrections": [correction_row(row) for row in rows]})

    @requires_permission(CONVERSION_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="conversion_correct",
        request=CorrectionSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = CorrectionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        session = _require_session()
        lines = []
        for row in payload.validated_data["lines"]:
            account = _account(row["account"])
            if account is None:
                raise serializers.ValidationError(
                    {"lines": [_("Choose an account of the chart for every line.")]}
                )
            contact = documents._find_contact(row["contact"], "") if row.get("contact") else None
            lines.append(
                {
                    "account": account,
                    "debit": _amount_or_zero(row["debit"]),
                    "credit": _amount_or_zero(row["credit"]),
                    "contact": contact,
                    "description": row["description"],
                }
            )
        try:
            made = corrections.correct(
                session, lines, payload.validated_data["reason"], request.user
            )
        except DjangoValidationError as error:
            return _refused(error)
        return Response(correction_row(made), status=status.HTTP_201_CREATED)
