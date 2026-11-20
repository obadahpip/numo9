"""Search providers (A-09-T02): each searchable model registers how it becomes a document.

``register_provider(Model, to_document)`` — ``to_document(instance) -> Doc | None`` describes the
record (``None``: not searchable, e.g. a merged contact). From then on every save of the model
updates its ``SearchDocument`` and every delete — or soft delete (``deleted_at`` set) — removes
it, **in the saving transaction** (signals run inside it): a record is findable the moment its
transaction commits, and a rolled-back save leaves no document. ``index(instance)`` /
``unindex(instance)`` do the same by hand (related records: a journal line indexes its journal).

The search vector is written by PostgreSQL right after the row (``simple`` + ``unaccent``:
title A; code and subtitle B; body C).
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import connection, models
from django.db.models.signals import post_delete, post_save

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import SearchDocument

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Doc:
    title: str
    url: str
    subtitle: str = ""
    code: str = ""
    body: str = ""
    amount: Decimal | None = None
    date: dt.date | None = None
    permission_key: str = ""
    feature_key: str = ""
    #: Overrides for models that aren't organisation-owned (a membership indexes its user).
    organisation_id: int | None = None
    object_type: str = ""
    object_id: str = ""


ToDocument = Callable[[Any], Doc | None]


@dataclass(frozen=True)
class Provider:
    model: type[models.Model]
    to_document: ToDocument

    @property
    def object_type(self) -> str:
        return self.model._meta.label_lower


_providers: dict[type[models.Model], Provider] = {}

_VECTOR_SQL = """
UPDATE search_searchdocument SET search_vector =
    setweight(to_tsvector('simple', unaccent(title)), 'A')
    || setweight(to_tsvector('simple', unaccent(code || ' ' || subtitle)), 'B')
    || setweight(to_tsvector('simple', unaccent(body)), 'C')
WHERE id = %s
"""


def register_provider(model: type[models.Model], to_document: ToDocument) -> Provider:
    provider = Provider(model, to_document)
    _providers[model] = provider
    uid = f"numo9.search.{model._meta.label_lower}"
    post_save.connect(_saved, sender=model, dispatch_uid=f"{uid}.save", weak=False)
    post_delete.connect(_deleted, sender=model, dispatch_uid=f"{uid}.delete", weak=False)
    return provider


def register_dependent(model: type[models.Model], parent: Callable[[Any], Any]) -> None:
    """A child record (a contact's person) re-indexes its parent's document when it changes."""

    def changed(sender: Any, instance: Any, raw: bool = False, **kwargs: Any) -> None:
        if raw:
            return
        owner = parent(instance)
        if owner is not None:
            index(owner)

    uid = f"numo9.search.dependent.{model._meta.label_lower}"
    post_save.connect(changed, sender=model, dispatch_uid=f"{uid}.save", weak=False)
    post_delete.connect(changed, sender=model, dispatch_uid=f"{uid}.delete", weak=False)


def unregister_provider(model: type[models.Model]) -> None:
    _providers.pop(model, None)
    uid = f"numo9.search.{model._meta.label_lower}"
    post_save.disconnect(sender=model, dispatch_uid=f"{uid}.save")
    post_delete.disconnect(sender=model, dispatch_uid=f"{uid}.delete")


def providers() -> list[Provider]:
    return list(_providers.values())


def provider_for(model: type[models.Model]) -> Provider | None:
    return _providers.get(model)


def _identity(provider: Provider, instance: Any, doc: Doc | None) -> tuple[int | None, str, str]:
    organisation_id = (doc.organisation_id if doc else None) or getattr(
        instance, "organisation_id", None
    )
    object_type = (doc.object_type if doc else "") or provider.object_type
    object_id = (doc.object_id if doc else "") or str(
        getattr(instance, "public_id", None) or instance.pk
    )
    return organisation_id, object_type, object_id


def _write_vector(row_id: int) -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(_VECTOR_SQL, [row_id])


def _build(provider: Provider, instance: Any) -> Doc | None:
    """The provider's document, built inside the instance's organisation (its related rows are
    tenant-scoped, and a save may happen outside any request context)."""
    if getattr(instance, "deleted_at", None):
        return None
    own = getattr(instance, "organisation_id", None)
    organisation = Organisation.objects.filter(pk=own).first() if own else None
    if organisation is None:
        return provider.to_document(instance)
    with org_context(organisation):
        return provider.to_document(instance)


def index(instance: Any) -> SearchDocument | None:
    """Write (or remove) the instance's document now, in the current transaction."""
    provider = _providers.get(type(instance))
    if provider is None:
        return None
    doc = _build(provider, instance)
    organisation_id, object_type, object_id = _identity(provider, instance, doc)
    if organisation_id is None:
        return None
    organisation = Organisation.objects.filter(pk=organisation_id).first()
    if organisation is None:
        return None
    with org_context(organisation):
        if doc is None:
            SearchDocument.objects.filter(object_type=object_type, object_id=object_id).delete()
            return None
        row: SearchDocument
        row, _created = SearchDocument.objects.update_or_create(
            organisation=organisation,
            object_type=object_type,
            object_id=object_id,
            defaults={
                "title": doc.title[:300],
                "subtitle": doc.subtitle[:300],
                "code": doc.code[:64],
                "body": doc.body,
                "amount": doc.amount,
                "date": doc.date,
                "url": doc.url[:300],
                "permission_key": doc.permission_key,
                "feature_key": doc.feature_key,
            },
        )
        _write_vector(row.pk)
    return row


def unindex(instance: Any) -> None:
    provider = _providers.get(type(instance))
    if provider is None:
        return
    try:
        doc = _build(provider, instance)  # its identity overrides (a membership → its user)
    except Exception:  # the record may be half gone: fall back to the model's identity
        doc = None
    organisation_id, object_type, object_id = _identity(provider, instance, doc)
    if organisation_id is None:
        return
    organisation = Organisation.objects.filter(pk=organisation_id).first()
    if organisation is None:
        return
    with org_context(organisation):
        SearchDocument.objects.filter(object_type=object_type, object_id=object_id).delete()


def _saved(sender: Any, instance: Any, raw: bool = False, **kwargs: Any) -> None:
    if raw:
        return  # fixtures: reindex_search builds the documents
    index(instance)


def _deleted(sender: Any, instance: Any, **kwargs: Any) -> None:
    unindex(instance)
