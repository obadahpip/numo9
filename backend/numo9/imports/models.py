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


class ImportRunStatus(models.TextChoices):
    UPLOADED = "uploaded", _("Uploaded")
    REVIEWED = "reviewed", _("Checked (dry run)")
    APPLYING = "applying", _("Importing")
    APPLIED = "applied", _("Imported")
    FAILED = "failed", _("Failed")


class ImportRun(OrgOwnedModel):
    """One import of a file (B-03-T07): its rows as read, the mapping, the options and the latest
    report — a dry run (``reviewed``) or the applied outcome (``applied``). The rows are kept as
    cells so the dry run and the import read exactly the same data."""

    entity = models.CharField(_("record type"), max_length=40)
    filename = models.CharField(_("file"), max_length=255, blank=True)
    sheet = models.CharField(_("sheet"), max_length=100, blank=True)
    headers = models.JSONField(_("column headers"), default=list)
    cells = models.JSONField(_("rows"), default=list, help_text=_("[[row number, [cell, …]], …]"))
    columns = models.JSONField(_("mapping"), default=dict)
    options = models.JSONField(_("options"), default=dict, blank=True)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=ImportRunStatus.choices,
        default=ImportRunStatus.UPLOADED,
    )
    counts = models.JSONField(_("totals"), default=dict, blank=True)
    job_id = models.UUIDField(_("background job"), null=True, blank=True)
    applied_at = models.DateTimeField(_("imported at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("import")
        verbose_name_plural = _("imports")

    def __str__(self) -> str:
        return f"{self.entity} · {self.filename}"


class ImportRunRow(OrgOwnedModel):
    """One data row's outcome in the run's latest report: action, changes ``{field: [before,
    after]}`` and errors ``[{field, code, message}]``."""

    run = models.ForeignKey(
        ImportRun, on_delete=models.CASCADE, related_name="rows", verbose_name=_("import")
    )
    row = models.PositiveIntegerField(_("row"))
    key = models.CharField(_("match key"), max_length=255, blank=True)
    label = models.CharField(_("record"), max_length=300, blank=True)
    action = models.CharField(_("action"), max_length=10)
    changes = models.JSONField(_("changes"), default=dict, blank=True)
    errors = models.JSONField(_("errors"), default=list, blank=True)

    class Meta:
        ordering = ("run", "row")
        verbose_name = _("import row")
        verbose_name_plural = _("import rows")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("run", "action"), name="imports_row_action_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.run_id} #{self.row} {self.action}"
