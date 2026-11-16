"""Saved column mappings (B-03-T03).

``ImportMapping`` — a named column → field mapping an organisation saved for one entity
(``contacts.contact``, ``ledger.account``…), so the next file with the same headers maps itself:

- ``columns`` — ``{"Courriel": "email", "Nom": "display_name", "Notes internes": ""}``: every
  header of the file it was saved from, ``""`` meaning "don't import";
- ``header_key`` — fingerprint of the file's headers (normalised, order-free): a new file with the
  same headers finds the mapping without being asked (``mapping.find_saved``);
- ``use_count`` / ``last_used_at`` — shown in the upload step ("used 3 times");
- names are unique per organisation and entity, case-insensitive.

An organisation record (``OrgOwnedModel``) with its changes in the audit log. Not sensitive (it
holds header names, not data), so no row-level security beyond the scoped manager.
"""

from __future__ import annotations

from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel

NAME_MAX = 80


def _name_error(message: Any, code: str) -> ValidationError:
    return ValidationError({"name": ValidationError(message, code=code)})


class ImportMapping(AuditedModel, OrgOwnedModel):
    entity = models.CharField(_("record type"), max_length=40)
    name = models.CharField(_("name"), max_length=NAME_MAX)
    columns = models.JSONField(
        _("columns"),
        default=dict,
        help_text=_('Column header → field, "" for a column that is not imported.'),
    )
    header_key = models.CharField(_("headers fingerprint"), max_length=64, editable=False)
    use_count = models.PositiveIntegerField(_("times used"), default=0)
    last_used_at = models.DateTimeField(_("last used"), null=True, blank=True)

    audit_exclude: ClassVar[frozenset[str]] = frozenset({"header_key", "use_count", "last_used_at"})

    class Meta:
        ordering = ("-last_used_at", "name")
        verbose_name = _("saved import mapping")
        verbose_name_plural = _("saved import mappings")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "organisation",
                "entity",
                Lower("name"),
                condition=models.Q(deleted_at__isnull=True),
                name="imports_mapping_name_unique",
            ),
            models.CheckConstraint(
                condition=~models.Q(name=""), name="imports_mapping_name_required"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organisation", "entity", "header_key"), name="imports_mapping_headers_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.entity} · {self.name}"

    def clean(self) -> None:
        from .mapping import check_mapping, header_key

        self.name = " ".join((self.name or "").split())
        if not self.name:
            raise _name_error(_("Give the mapping a name."), "imports.mapping.name_required")
        if len(self.name) > NAME_MAX:
            raise _name_error(
                _("A mapping name is at most %(max)d characters.") % {"max": NAME_MAX},
                "imports.mapping.name_too_long",
            )
        check_mapping(self.entity, self.columns)
        if self._name_taken():
            raise _name_error(
                _(
                    "There is already a mapping named %(name)s. Choose another name or update "
                    "that one."
                )
                % {"name": self.name},
                "imports.mapping.name_taken",
            )
        self.header_key = header_key(list(self.columns))

    def _name_taken(self) -> bool:
        return (
            type(self)
            .objects.filter(
                organisation_id=self.organisation_id,
                entity=self.entity,
                name__iexact=self.name,
                deleted_at__isnull=True,
            )
            .exclude(pk=self.pk)
            .exists()
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("update_fields") is None or {"name", "columns", "entity"} & set(
            kwargs["update_fields"]
        ):
            self.clean()
        super().save(*args, **kwargs)
