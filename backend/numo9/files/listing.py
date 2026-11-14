"""Inbox list, tags, archive and bulk changes (A-06-T10).

**List** — ``list_documents(params)``: the organisation's documents, newest first, keyset pages
(``cursor``; up to 1,000 per page so the inbox paints a large list at once), filtered by:

| Parameter | Meaning |
|---|---|
| ``folder`` | ``inbox`` (default) or ``archived`` |
| ``status`` | ``uploading``, ``scanning``, ``clean``, ``infected`` |
| ``source`` | ``upload`` or ``email`` |
| ``period`` | ``YYYY-MM``; ``none`` = untagged |
| ``tax_year`` | a year; ``none`` = untagged |
| ``tag`` | a custom tag, any case (repeatable: every tag must be present) |
| ``q`` | text in the file name, sender or tags |

**Changes** — one document via PATCH (name, period, tax year, tags, folder), or many at once with
``bulk(ids, action, …)``: ``archive``, ``unarchive``, ``add_tags``, ``remove_tags``, ``set_period``,
``set_tax_year`` (up to 1,000 documents, one transaction, one audit batch with every change).
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import BooleanField, Q, QuerySet
from django.db.models.expressions import RawSQL

from numo9.audit.batch import audit_batch
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.context import current_org

from .models import (
    PERIOD,
    TAX_YEAR_MAX,
    TAX_YEAR_MIN,
    Document,
    DocumentSource,
    DocumentStatus,
    Folder,
    normalise_tags,
)

DEFAULT_LIMIT = 200
MAX_LIMIT = 1000
BULK_MAX = 1000
#: Bulk actions, in the order the API documents them (``BulkActionEnum``).
BULK_ACTION_CHOICES = (
    "archive",
    "unarchive",
    "add_tags",
    "remove_tags",
    "set_period",
    "set_tax_year",
)
BULK_ACTIONS = frozenset(BULK_ACTION_CHOICES)


def _choice(params: Mapping[str, Any], name: str, allowed: Any) -> str:
    value = str(params.get(name, "") or "")
    if value and value not in allowed:
        raise api_error(errors.FILES_BAD_FILTER, name=name, value=value)
    return value


def filtered(params: Mapping[str, Any]) -> QuerySet[Document]:
    documents = Document.objects.filter(deleted_at__isnull=True).select_related("created_by")
    folder = _choice(params, "folder", Folder.values) or Folder.INBOX
    documents = documents.filter(folder=folder)
    if status := _choice(params, "status", DocumentStatus.values):
        documents = documents.filter(status=status)
    if source := _choice(params, "source", DocumentSource.values):
        documents = documents.filter(source=source)
    period = str(params.get("period", "") or "")
    if period == "none":
        documents = documents.filter(period="")
    elif period:
        if not PERIOD.match(period):
            raise api_error(errors.FILES_BAD_FILTER, name="period", value=period)
        documents = documents.filter(period=period)
    tax_year = str(params.get("tax_year", "") or "")
    if tax_year == "none":
        documents = documents.filter(tax_year__isnull=True)
    elif tax_year:
        if not tax_year.isdigit() or not TAX_YEAR_MIN <= int(tax_year) <= TAX_YEAR_MAX:
            raise api_error(errors.FILES_BAD_FILTER, name="tax_year", value=tax_year)
        documents = documents.filter(tax_year=int(tax_year))
    getlist = getattr(params, "getlist", None)
    tags = getlist("tag") if callable(getlist) else [params.get("tag")]
    for tag in normalise_tags(t for t in tags if t):
        documents = documents.filter(has_tag(tag))
    if text := str(params.get("q", "") or "").strip():
        documents = documents.filter(
            Q(name__icontains=text) | Q(sender__icontains=text) | Q(tags__icontains=text)
        )
    return documents.order_by("-created_at", "-id")


def has_tag(tag: str) -> RawSQL:
    """The document has ``tag``, any case (``Utilities`` = ``utilities``)."""
    return RawSQL(
        "EXISTS (SELECT 1 FROM unnest(files_document.tags) AS t WHERE lower(t) = lower(%s))",
        (tag,),
        output_field=BooleanField(),
    )


def encode_cursor(document: Document) -> str:
    raw = f"{document.created_at.isoformat()}|{document.pk}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _after(documents: QuerySet[Document], token: str | None) -> QuerySet[Document]:
    if not token:
        return documents
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        moment, pk = raw.split("|")
        created_at, last_id = datetime.fromisoformat(moment), int(pk)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise api_error(errors.FILES_BAD_CURSOR) from exc
    return documents.filter(Q(created_at__lt=created_at) | Q(created_at=created_at, pk__lt=last_id))


def limit_of(params: Mapping[str, Any]) -> int:
    raw = params.get("limit")
    if raw in (None, ""):
        return DEFAULT_LIMIT
    value = int(str(raw)) if str(raw).isdigit() else 0
    if not 1 <= value <= MAX_LIMIT:
        raise api_error(errors.FILES_BAD_LIMIT, max=MAX_LIMIT)
    return value


def list_documents(params: Mapping[str, Any]) -> tuple[list[Document], str | None, int]:
    """One page, the next cursor and the number of documents matching the filters."""
    documents = filtered(params)
    limit = limit_of(params)
    rows = list(_after(documents, params.get("cursor"))[: limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, (encode_cursor(rows[-1]) if more and rows else None), documents.count()


def tag_counts() -> list[dict[str, Any]]:
    """Custom tags in use in the organisation (documents not removed), most used first."""
    counts: dict[str, int] = {}
    spelling: dict[str, str] = {}  # first spelling seen of each tag (tags match in any case)
    for tags in Document.objects.filter(deleted_at__isnull=True).values_list("tags", flat=True):
        for tag in tags or []:
            key = tag.lower()
            spelling.setdefault(key, tag)
            counts[key] = counts.get(key, 0) + 1
    ordered = sorted(counts.items(), key=lambda i: (-i[1], i[0]))
    return [{"tag": spelling[key], "count": count} for key, count in ordered]


# ---- changes ------------------------------------------------------------------------------------


def _apply(document: Document, action: str, value: Any) -> list[str]:
    """Change one document in memory; returns the fields changed."""
    if action == "archive" and document.folder != Folder.ARCHIVED:
        document.folder = Folder.ARCHIVED
        return ["folder"]
    if action == "unarchive" and document.folder != Folder.INBOX:
        document.folder = Folder.INBOX
        return ["folder"]
    if action == "add_tags":
        tags = normalise_tags([*document.tags, *value])
        if tags != document.tags:
            document.tags = tags
            return ["tags"]
    if action == "remove_tags":
        drop = {t.lower() for t in normalise_tags(value)}
        tags = [t for t in document.tags if t.lower() not in drop]
        if tags != document.tags:
            document.tags = tags
            return ["tags"]
    if action == "set_period" and document.period != (value or ""):
        document.period = value or ""
        return ["period"]
    if action == "set_tax_year" and document.tax_year != value:
        document.tax_year = value
        return ["tax_year"]
    return []


def bulk(ids: list[Any], action: str, value: Any = None) -> int:
    """Apply one change to many documents of the organisation (all or nothing)."""
    if action not in BULK_ACTIONS:
        raise api_error(errors.FILES_BULK_ACTION)
    if len(ids) > BULK_MAX:
        raise api_error(errors.FILES_BULK_TOO_MANY, max=BULK_MAX)
    documents = list(Document.objects.filter(public_id__in=ids, deleted_at__isnull=True))
    changed = 0
    with (
        transaction.atomic(),
        audit_batch(
            f"files.bulk.{action}", organisation=current_org(), meta={"documents": len(documents)}
        ),
    ):
        for document in documents:
            fields = _apply(document, action, value)
            if fields:
                document.save(update_fields=[*fields, "updated_at"])
                changed += 1
    return changed


def update(document: Document, data: Mapping[str, Any]) -> Document:
    """PATCH one document: ``name``, ``period``, ``tax_year``, ``tags``, ``folder``."""
    fields: list[str] = []
    for name in ("name", "period", "tax_year", "tags", "folder"):
        if name in data:
            setattr(document, name, data[name])
            fields.append(name)
    if "folder" in data and data["folder"] not in Folder.values:
        raise ValidationError(
            {"folder": [ValidationError("inbox or archived", code="files.folder.invalid")]}
        )
    if fields:
        document.save(update_fields=[*fields, "updated_at"])
    return document
