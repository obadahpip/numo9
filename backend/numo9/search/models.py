"""The global search index (A-09-T01).

``SearchDocument`` — one row per searchable record of an organisation (contact, account, journal,
document, user …), written by the record's provider (``registry.py``) in the record's own
transaction, so a record is findable as soon as it is saved:

- ``object_type`` / ``object_id`` — what it points to (``contacts.contact`` + the public id);
- ``title`` (the name, weighted most), ``subtitle`` (a second line: email, account type …),
  ``code`` (account code, journal number, BN — matched exactly and by prefix: "54" → 5400) and
  ``body`` (the rest: narration, line descriptions, notes);
- ``amount`` / ``date`` — for "1,130" and date searches; ``url`` — where the result opens;
- ``permission_key`` / ``feature_key`` — the result is shown only to users holding the
  permission, and gated (lock + explanation) when the organisation's package lacks the feature.

``search_vector`` is computed by PostgreSQL (``simple`` over ``unaccent``: title A, code and
subtitle B, body C) with a GIN index; ``title`` and ``code`` also have trigram indexes (typo
tolerance). Organisation-owned with row-level security, like the records it indexes.
"""

from __future__ import annotations

from typing import ClassVar

from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import OrgOwnedModel


class SearchDocument(OrgOwnedModel):
    object_type = models.CharField(_("record type"), max_length=64)
    object_id = models.CharField(_("record id"), max_length=64)
    title = models.CharField(_("title"), max_length=300)
    subtitle = models.CharField(_("subtitle"), max_length=300, blank=True)
    code = models.CharField(_("code or number"), max_length=64, blank=True)
    body = models.TextField(_("text"), blank=True)
    amount = models.DecimalField(
        _("amount"), max_digits=18, decimal_places=2, null=True, blank=True
    )
    date = models.DateField(_("date"), null=True, blank=True)
    url = models.CharField(_("link"), max_length=300)
    permission_key = models.CharField(_("permission"), max_length=100, blank=True)
    feature_key = models.CharField(_("feature"), max_length=100, blank=True)
    search_vector = SearchVectorField(_("search vector"), null=True, editable=False)

    class Meta:
        verbose_name = _("search document")
        verbose_name_plural = _("search documents")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "object_type", "object_id"),
                name="search_document_once_per_record",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "object_type"), name="search_doc_type_idx"),
            models.Index(fields=("organisation", "code"), name="search_doc_code_idx"),
            models.Index(fields=("organisation", "amount"), name="search_doc_amount_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.object_type} · {self.title}"
