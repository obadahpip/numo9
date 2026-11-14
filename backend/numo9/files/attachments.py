"""Attach documents to records (A-06-T09).

Any organisation record — any ``OrgOwnedModel``: a contact now, invoices, bills and assets later —
can carry documents. A record is named by its model label and public id
(``record_type = "contacts.Contact"``, ``record_id = <uuid>``), the same pair the audit log uses.

- ``attach(document, record_type, record_id)`` — the record must exist in the active organisation
  (else ``RecordNotFound`` → 404); a quarantined document can't be attached; attaching twice
  returns the existing link;
- ``detach(attachment)`` — a soft delete: the link's history stays in the audit log;
- ``attachments_of(record_type, record_id)`` — the record's documents, newest first.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, models, transaction

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.context import current_org
from numo9.tenancy.models import OrgOwnedModel

from .models import Attachment, Document, DocumentStatus, InboundMessage

#: Records documents are never attached to (they are the documents machinery itself).
NOT_ATTACHABLE = frozenset({Attachment, InboundMessage})


class RecordNotFound(LookupError):
    pass


def record_model(record_type: str) -> type[OrgOwnedModel]:
    try:
        model = apps.get_model(record_type)
    except (LookupError, ValueError) as exc:
        raise api_error(errors.FILES_RECORD_TYPE, record_type=record_type) from exc
    if not issubclass(model, OrgOwnedModel) or model in NOT_ATTACHABLE:
        raise api_error(errors.FILES_RECORD_TYPE, record_type=record_type)
    return model


def get_record(record_type: str, record_id: Any) -> models.Model:
    model = record_model(record_type)
    try:
        public_id = uuid.UUID(str(record_id))
    except ValueError as exc:
        raise RecordNotFound(record_id) from exc
    found = (
        model._base_manager.filter(
            organisation=current_org(), public_id=public_id, deleted_at__isnull=True
        ).first()
        if current_org() is not None
        else None
    )
    if found is None:
        raise RecordNotFound(record_id)
    return found


def attach(document: Document, record_type: str, record_id: Any, *, user: Any = None) -> Attachment:
    record = get_record(record_type, record_id)
    if document.status == DocumentStatus.INFECTED:
        raise api_error(errors.FILES_QUARANTINED, name=document.name)
    content_type = ContentType.objects.get_for_model(type(record))
    existing: Attachment | None = Attachment.objects.filter(
        document=document,
        content_type=content_type,
        object_public_id=record.public_id,  # type: ignore[attr-defined]
        deleted_at__isnull=True,
    ).first()
    if existing is not None:
        return existing
    link = Attachment(
        organisation=document.organisation,
        document=document,
        content_type=content_type,
        object_public_id=record.public_id,  # type: ignore[attr-defined]
        created_by=user,
    )
    try:
        with transaction.atomic():
            link.save()
    except IntegrityError:  # the same link made at the same moment
        found: Attachment = Attachment.objects.get(
            document=document,
            content_type=content_type,
            object_public_id=record.public_id,  # type: ignore[attr-defined]
            deleted_at__isnull=True,
        )
        return found
    return link


def detach(attachment: Attachment) -> None:
    attachment.soft_delete()


def attachments_of(record_type: str, record_id: Any) -> models.QuerySet[Attachment]:
    record = get_record(record_type, record_id)
    return (
        Attachment.objects.filter(
            content_type=ContentType.objects.get_for_model(type(record)),
            object_public_id=record.public_id,  # type: ignore[attr-defined]
            deleted_at__isnull=True,
            document__deleted_at__isnull=True,
        )
        .select_related("document", "document__created_by", "created_by", "content_type")
        .order_by("-created_at", "-id")
    )
