"""Documents API (A-06), under ``/api/v1/o/<org>/files/``.

- ``uploads`` — POST ``{name, size}`` → the document (``uploading``) and a presigned POST form for
  the browser to send the file straight to the bucket (A-06-T03);
- ``<id>/finalize`` — POST once the browser's upload finished: size, type from the content,
  SHA-256, then the virus scan; a refused file is removed (413 too large, 415 wrong type);
- (no suffix) — GET the inbox or archive, newest first, with filters (A-06-T10);
- ``<id>`` — GET the document; PATCH name, period, tax year, tags, folder (A-06-T10);
- ``bulk`` — POST one change to many documents; ``tags`` — GET the tags in use (A-06-T10);
- ``<id>/actions`` — GET the "create from file" actions with their state (A-06-T11);
- ``<id>/url?download=1&variant=file|preview|thumbnail`` — GET a 5-minute signed URL (clean
  documents only; 409 while scanning or quarantined);
- ``inbound-address`` — GET the inbox's email address; ``inbound-address/rotate`` — POST a new one
  (A-06-T06);
- ``attachments?record_type=contacts.Contact&record_id=<uuid>`` — GET a record's documents; POST
  ``{document, record_type, record_id}`` attaches; ``attachments/<id>`` — DELETE detaches
  (A-06-T09).

Every route is organisation-scoped: another organisation's document is a 404 (A-06-T14).
Storage outages answer 503 ``files.storage_unavailable`` instead of a server error.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from django.core.exceptions import ValidationError
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.audit.service import record
from numo9.catalogue.drf import CORE, requires_feature
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.packages.services import field_errors
from numo9.rbac.drf import PUBLIC, requires_permission
from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation

from . import attachments, inbound, listing, services, storage
from .models import MAX_FILE_SIZE, Attachment, Document, InboundAddress
from .permissions import FILES_MANAGE, FILES_UPLOAD, FILES_VIEW
from .serializers import (
    AttachmentListSerializer,
    AttachmentSerializer,
    AttachRequestSerializer,
    BulkRequestSerializer,
    BulkResultSerializer,
    DocumentPageSerializer,
    DocumentSerializer,
    DocumentUpdateSerializer,
    FileActionListSerializer,
    FinalizeResponseSerializer,
    InboundAddressSerializer,
    SignedUrlSerializer,
    TagListSerializer,
    UploadRequestSerializer,
    UploadResponseSerializer,
)

READ = "accounting.documents.read"
WRITE = "accounting.documents.write"


@contextmanager
def storage_errors() -> Iterator[None]:
    """Object-storage failures answer 503 with a message, never a server error."""
    try:
        yield
    except (BotoCoreError, ClientError) as exc:
        raise api_error(errors.FILES_STORAGE_UNAVAILABLE) from exc


def with_storage[F: Callable[..., Any]](handler: F) -> F:
    @wraps(handler)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        with storage_errors():
            return handler(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


def current_organisation() -> Organisation:
    organisation = current_org()
    if organisation is None:  # pragma: no cover - RequiresPermission answers 404 first
        raise NotFound
    return organisation


def get_document(public_id: Any) -> Document:
    """A document of the active organisation (scoped manager), never a removed one; else 404."""
    document: Document | None = (
        Document.objects.select_related("created_by")
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if document is None:
        raise NotFound
    return document


class UploadView(APIView):
    queryset = Document._base_manager.none()  # tenant sweep: rows of Document

    @requires_permission(FILES_UPLOAD.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="files_upload_create",
        summary="Start an upload: the document and a presigned POST form (5 minutes, ≤ 25 MB)",
        request=UploadRequestSerializer,
        responses={201: UploadResponseSerializer},
    )
    @with_storage
    def post(self, request: Request, org: Any) -> Response:
        payload = UploadRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        document, form = services.create_upload(
            payload.validated_data["name"], payload.validated_data["size"], user=request.user
        )
        body = {
            "document": DocumentSerializer(document).data,
            "upload": {"url": form["url"], "fields": form["fields"]},
            "max_size": MAX_FILE_SIZE,
        }
        return Response(body, status=status.HTTP_201_CREATED)


class FinalizeView(APIView):
    queryset = Document._base_manager.none()

    @requires_permission(FILES_UPLOAD.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="files_upload_finalize",
        summary="Finish an upload: size, type from the content, SHA-256, then the virus scan",
        request=None,
        responses=FinalizeResponseSerializer,
    )
    @with_storage
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        document = get_document(public_id)
        try:
            shown = services.finalize_upload(document)
        except storage.ForeignDocument as exc:
            raise NotFound from exc
        body = dict(DocumentSerializer(shown).data)
        body["duplicate"] = shown.pk != document.pk
        return Response(body)


class DocumentDetailView(APIView):
    queryset = Document._base_manager.none()

    @requires_permission(FILES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="files_get", summary="One document", responses=DocumentSerializer)
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(DocumentSerializer(get_document(public_id)).data)

    @requires_permission(FILES_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="files_update",
        summary="Rename, tag (period, tax year, tags) or archive/unarchive a document",
        request=DocumentUpdateSerializer,
        responses=DocumentSerializer,
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        document = get_document(public_id)
        payload = DocumentUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        try:
            listing.update(document, payload.validated_data)
        except ValidationError as exc:
            raise field_errors(exc) from exc
        return Response(DocumentSerializer(document).data)


# ---- list, tags, bulk (A-06-T10) -----------------------------------------------------------


LIST_PARAMETERS = [
    OpenApiParameter("folder", OpenApiTypes.STR, enum=["inbox", "archived"]),
    OpenApiParameter("status", OpenApiTypes.STR),
    OpenApiParameter("source", OpenApiTypes.STR, enum=["upload", "email"]),
    OpenApiParameter("period", OpenApiTypes.STR, description="YYYY-MM or none"),
    OpenApiParameter("tax_year", OpenApiTypes.STR, description="a year or none"),
    OpenApiParameter("tag", OpenApiTypes.STR, many=True),
    OpenApiParameter("q", OpenApiTypes.STR),
    OpenApiParameter("cursor", OpenApiTypes.STR),
    OpenApiParameter("limit", OpenApiTypes.INT, description="1–1000, default 200"),
]


class DocumentListView(APIView):
    queryset = Document._base_manager.none()

    @requires_permission(FILES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="files_list",
        summary="The documents inbox (or archive), newest first, with filters",
        parameters=LIST_PARAMETERS,
        responses=DocumentPageSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        rows, cursor, total = listing.list_documents(request.query_params)
        return Response(
            {
                "results": DocumentSerializer(rows, many=True).data,  # type: ignore[arg-type]
                "next": cursor,
                "total": total,
            }
        )


class TagListView(APIView):
    queryset = Document._base_manager.none()

    @requires_permission(FILES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="files_tags",
        summary="Custom tags in use, most used first",
        responses=TagListSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        return Response({"results": listing.tag_counts()})


class BulkView(APIView):
    queryset = Document._base_manager.none()

    @requires_permission(FILES_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="files_bulk",
        summary="Archive, unarchive or tag many documents at once (all or nothing)",
        request=BulkRequestSerializer,
        responses=BulkResultSerializer,
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = BulkRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        value = {
            "add_tags": data.get("tags", []),
            "remove_tags": data.get("tags", []),
            "set_period": data.get("period", ""),
            "set_tax_year": data.get("tax_year"),
        }.get(data["action"])
        try:
            updated = listing.bulk(data["ids"], data["action"], value)
        except ValidationError as exc:
            raise field_errors(exc) from exc
        return Response({"updated": updated})


class SignedUrlView(APIView):
    queryset = Document._base_manager.none()

    @requires_permission(FILES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="files_signed_url",
        summary="A 5-minute signed URL to view or download a clean document (or its preview)",
        parameters=[
            OpenApiParameter("download", OpenApiTypes.BOOL, description="attachment, not inline"),
            OpenApiParameter("variant", OpenApiTypes.STR, enum=["file", "preview", "thumbnail"]),
        ],
        responses=SignedUrlSerializer,
    )
    @with_storage
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        document = get_document(public_id)
        variant = request.query_params.get("variant", "file")
        if variant not in ("file", "preview", "thumbnail"):
            variant = "file"
        download = request.query_params.get("download") in ("1", "true", "yes")
        try:
            signed = storage.signed_url(document, download=download, variant=variant)
        except storage.ForeignDocument as exc:
            raise NotFound from exc
        except storage.DocumentNotReady as exc:
            raise api_error(errors.FILES_NOT_READY, name=document.name) from exc
        if variant == "file":
            # Who opened the original, and when (A-06-T15); previews and thumbnails aren't logged.
            record(
                "files.document.downloaded",
                obj=document,
                meta={"download": download, "expires_at": signed.expires_at},
            )
        return Response({"url": signed.url, "expires_at": signed.expires_at})


# ---- inbound address (A-06-T06) ------------------------------------------------------------


def address_body(current: Any) -> dict[str, Any]:
    from .inbound import RETIRED_GRACE
    from .models import InboundAddress, InboundAddressStatus

    previous = (
        InboundAddress._base_manager.filter(
            organisation_id=current.organisation_id,
            status=InboundAddressStatus.RETIRED,
            retired_at__gte=timezone.now() - RETIRED_GRACE,
        )
        .order_by("-retired_at")
        .first()
    )
    return {
        "address": current.address,
        "created_at": current.created_at,
        "previous": (
            {"address": previous.address, "accepted_until": previous.retired_at + RETIRED_GRACE}
            if previous is not None and previous.retired_at is not None
            else None
        ),
    }


class InboundAddressView(APIView):
    queryset = InboundAddress._base_manager.none()

    @requires_permission(FILES_UPLOAD.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="files_inbound_address",
        summary="The organisation's documents inbox address (created on first use)",
        responses=InboundAddressSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        return Response(address_body(inbound.inbound_address(current_organisation())))


class InboundAddressRotateView(APIView):
    queryset = InboundAddress._base_manager.none()

    @requires_permission(FILES_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="files_inbound_address_rotate",
        summary="Change the inbox address; the old one keeps working for 7 days",
        request=None,
        responses=InboundAddressSerializer,
    )
    def post(self, request: Request, org: Any) -> Response:
        current = inbound.rotate(current_organisation(), request.user)
        return Response(address_body(current))


# ---- inbound email webhook (A-06-T07) ------------------------------------------------------


class InboundEmailWebhookView(APIView):
    """``POST /api/v1/inbound/email`` — the provider posts one raw message (``message/rfc822``),
    signed with HMAC-SHA256. No session, no organisation in the URL: the ``docs+<token>@`` address
    routes it. Always 202 once the signature is valid (unknown address, duplicate or not in the
    package are reported in ``status``) so the provider doesn't retry what can't change."""

    authentication_classes: list[type] = []
    parser_classes: list[type] = []
    required_feature = CORE  # the organisation's package is checked once the address routes it

    @requires_permission(PUBLIC)
    @extend_schema(
        operation_id="inbound_email_webhook",
        summary="Inbound email from the provider (raw RFC 822, HMAC-signed)",
        request={"message/rfc822": OpenApiTypes.BINARY},
        responses={202: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT, 413: OpenApiTypes.OBJECT},
        auth=[],
    )
    @with_storage
    def post(self, request: Request) -> Response:
        from . import inbound_email

        body = request.stream.read(inbound_email.MAX_MESSAGE_BYTES + 1) if request.stream else b""
        if len(body) > inbound_email.MAX_MESSAGE_BYTES:
            return Response(
                {"detail": "Message too large.", "code": "files.inbound_too_large"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        try:
            inbound_email.verify(
                body,
                request.headers.get("X-Numo9-Timestamp", ""),
                request.headers.get("X-Numo9-Signature", ""),
            )
        except inbound_email.BadSignature:
            return Response(
                {"detail": "Invalid signature.", "code": "files.inbound_signature"},
                status=status.HTTP_403_FORBIDDEN,
            )
        received = inbound_email.receive(body, request.headers.get("X-Numo9-Recipient", ""))
        payload: dict[str, Any] = {"status": received.status}
        if received.message is not None:
            payload["message"] = str(received.message.public_id)
        return Response(payload, status=status.HTTP_202_ACCEPTED)


# ---- attachments (A-06-T09) ----------------------------------------------------------------


RECORD_PARAMETERS = [
    OpenApiParameter(
        "record_type", OpenApiTypes.STR, required=True, description="contacts.Contact"
    ),
    OpenApiParameter("record_id", OpenApiTypes.UUID, required=True),
]


class AttachmentListView(APIView):
    queryset = Attachment._base_manager.none()

    @requires_permission(FILES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="files_attachments_list",
        summary="The documents attached to a record, newest first",
        parameters=RECORD_PARAMETERS,
        responses=AttachmentListSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        try:
            links = attachments.attachments_of(
                request.query_params.get("record_type", ""),
                request.query_params.get("record_id", ""),
            )
        except attachments.RecordNotFound as exc:
            raise NotFound from exc
        return Response({"results": AttachmentSerializer(links, many=True).data})

    @requires_permission(FILES_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="files_attachments_create",
        summary="Attach a document to a record (any organisation record)",
        request=AttachRequestSerializer,
        responses={201: AttachmentSerializer, 200: AttachmentSerializer},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = AttachRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        document = get_document(payload.validated_data["document"])
        before = Attachment.objects.filter(document=document, deleted_at__isnull=True).count()
        try:
            link = attachments.attach(
                document,
                payload.validated_data["record_type"],
                payload.validated_data["record_id"],
                user=request.user,
            )
        except attachments.RecordNotFound as exc:
            raise NotFound from exc
        created = Attachment.objects.filter(document=document, deleted_at__isnull=True).count()
        code = status.HTTP_201_CREATED if created > before else status.HTTP_200_OK
        return Response(AttachmentSerializer(link).data, status=code)


class AttachmentDetailView(APIView):
    queryset = Attachment._base_manager.none()

    @requires_permission(FILES_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="files_attachments_delete",
        summary="Detach a document from its record (the document stays in the inbox)",
        responses={204: None},
    )
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        link = Attachment.objects.filter(public_id=public_id, deleted_at__isnull=True).first()
        if link is None:
            raise NotFound
        attachments.detach(link)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---- create from file (A-06-T11) -----------------------------------------------------------


class FileActionsView(APIView):
    queryset = Document._base_manager.none()

    @requires_permission(FILES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="files_actions",
        summary="What this document can become (bill, expense claim, asset), each with its state",
        responses=FileActionListSerializer,
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        from .actions import actions_for

        return Response({"results": actions_for(get_document(public_id))})
