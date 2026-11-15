"""Document services (A-06): upload, finalise, store received files.

Uploads go straight from the browser to the bucket (A-06-T03), never through the API:

1. ``create_upload(name, size)`` — checks the name's type and the declared size (≤ 25 MB), makes
   the ``Document`` (status ``uploading``) with a key under the organisation's prefix and returns
   a presigned POST form valid 5 minutes (1 byte … 25 MB);
2. the browser posts the file to the bucket;
3. ``finalize_upload(document)`` — reads what arrived: real size (≤ 25 MB), SHA-256 and the type
   detected from the content (libmagic) against the extension (``filetypes``). A file that fails is
   deleted from the bucket and its document removed; one that passes moves on to the virus scan
   (status ``scanning``) — unless the organisation already has the same file (same SHA-256):
   then the new copy is dropped and the existing document is returned (A-06-T08).

``store_received(...)`` does steps 1–3 for a file the server already holds (inbound email,
A-06-T07).
"""

from __future__ import annotations

import hashlib
from typing import Any

from django.db import connection, transaction
from django.utils import timezone

from numo9.audit.service import record
from numo9.i18n import errors
from numo9.i18n.errors import CatalogueError, api_error
from numo9.tenancy.context import TenantContextMissing, current_org
from numo9.tenancy.models import Organisation

from . import storage
from .filetypes import detect, extension_of, is_accepted_name
from .models import MAX_FILE_SIZE, Document, DocumentSource, DocumentStatus
from .scanning import queue_scan


def human_size(size: int) -> str:
    """``26.2 MB``, ``740 KB``, ``12 bytes``."""
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} bytes"


def _organisation() -> Organisation:
    organisation = current_org()
    if organisation is None:
        raise TenantContextMissing("Documents need an active organisation.")
    return organisation


def check_name_and_size(name: str, size: int) -> None:
    if not is_accepted_name(name):
        raise api_error(errors.FILES_TYPE_NOT_ALLOWED, name=name)
    if size <= 0:
        raise api_error(errors.FILES_EMPTY, name=name)
    if size > MAX_FILE_SIZE:
        raise api_error(errors.FILES_TOO_LARGE, name=name, size=human_size(size))


def create_upload(name: str, size: int, *, user: Any = None) -> tuple[Document, dict[str, Any]]:
    """Step 1: the document (``uploading``) and the browser's presigned POST form."""
    organisation = _organisation()
    name = " ".join((name or "").split())
    check_name_and_size(name, size)
    document = Document(
        organisation=organisation,
        name=name,
        file_key=storage.new_key(organisation, name),
        size=size,
        status=DocumentStatus.UPLOADING,
        source=DocumentSource.UPLOAD,
        created_by=user,
    )
    document.save()
    form = storage.presigned_post(document.file_key, MAX_FILE_SIZE)
    return document, form


def _reject(document: Document, error: CatalogueError) -> CatalogueError:
    """Remove a refused file: its object leaves the bucket, its document is soft-deleted."""
    try:
        storage.delete_object(document.file_key)
    finally:
        document.soft_delete()
    return error


def finalize_upload(document: Document) -> Document:
    """Step 3: check what arrived and send it to the virus scan. Returns the document to show —
    the existing one when the same file is already in the organisation (A-06-T08)."""
    organisation = _organisation()
    if document.organisation_id != organisation.pk:
        raise storage.ForeignDocument(str(document.public_id))
    storage.check_key(organisation, document.file_key)
    if document.status != DocumentStatus.UPLOADING:
        raise api_error(errors.FILES_NOT_PENDING, name=document.name)
    size = storage.object_size(document.file_key)
    if size is None:
        raise api_error(errors.FILES_UPLOAD_MISSING, name=document.name)
    if size > MAX_FILE_SIZE:
        raise _reject(
            document, api_error(errors.FILES_TOO_LARGE, name=document.name, size=human_size(size))
        )
    data = storage.open_object(document.file_key).read()
    return _accept(document, data)


def _accept(document: Document, data: bytes) -> Document:
    if not data:
        raise _reject(document, api_error(errors.FILES_EMPTY, name=document.name))
    detection = detect(document.name, data)
    if not detection.ok:
        raise _reject(
            document,
            api_error(errors.FILES_TYPE_MISMATCH, name=document.name, detected=detection.detected),
        )
    sha256 = hashlib.sha256(data).hexdigest()
    with transaction.atomic():
        _lock_hash(document.organisation_id, sha256)
        existing = find_duplicate(document, sha256)
        if existing is not None:
            return _link_duplicate(document, existing)
        document.size = len(data)
        document.sha256 = sha256
        document.mime = detection.stored_type
        document.status = DocumentStatus.SCANNING
        document.save(update_fields=["size", "sha256", "mime", "status", "updated_at"])
        queue_scan(document, user=document.created_by)  # sent when the transaction commits
    return document


# ---- duplicates (A-06-T08) ----------------------------------------------------------------------


def _lock_hash(organisation_id: int, sha256: str) -> None:
    """Two copies of one file finalised at the same moment: the second waits for the first."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [f"numo9.files:{organisation_id}:{sha256}"],
            )


def find_duplicate(document: Document, sha256: str) -> Document | None:
    """The organisation's document with the same content (not removed, not quarantined)."""
    found: Document | None = (
        Document._base_manager.filter(
            organisation_id=document.organisation_id,
            sha256=sha256,
            deleted_at__isnull=True,
            status__in=[DocumentStatus.SCANNING, DocumentStatus.CLEAN],
        )
        .exclude(pk=document.pk)
        .order_by("created_at")
        .first()
    )
    return found


def _link_duplicate(document: Document, existing: Document) -> Document:
    """Don't store the same file twice: drop the new copy, keep the existing document."""
    storage.delete_object(document.file_key)
    document.soft_delete()
    record(
        "files.document.duplicate_received",
        obj=existing,
        meta={"name": document.name, "source": document.source, "sender": document.sender},
    )
    return existing


def store_received(
    organisation: Organisation,
    name: str,
    data: bytes,
    *,
    source: str = DocumentSource.EMAIL,
    sender: str = "",
    sender_known: bool = True,
    inbound_message: Any = None,
) -> Document:
    """A file the server holds (an email attachment): stored under the organisation's prefix,
    then checked like an upload. Raises the same errors (the caller decides what to report)."""
    name = " ".join((name or "").split()) or f"attachment.{extension_of(name) or 'bin'}"
    check_name_and_size(name, len(data))
    document = Document(
        organisation=organisation,
        name=name,
        file_key=storage.new_key(organisation, name, now=timezone.now()),
        size=len(data),
        status=DocumentStatus.UPLOADING,
        source=source,
        sender=sender,
        sender_known=sender_known,
        inbound_message=inbound_message,
    )
    document.save()
    storage.put_bytes(document.file_key, data, "application/octet-stream")
    return _accept(document, data)
