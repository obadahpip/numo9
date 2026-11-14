"""Documents and attachments (A-06).

``Document`` (A-06-T01) is one stored file of an organisation — uploaded in the app or received by
email at the organisation's inbound address — with its scan state, preview and tags. It is an
organisation record (``OrgOwnedModel``: scoped, public UUID, soft delete) with every change in
the audit log (``AuditedModel``) and PostgreSQL row-level security.

- ``file_key`` — the object's key in the files bucket, always under the organisation's prefix
  (``org/<organisation public id>/…``, ``numo9.files.storage``); the file itself never passes
  through the database;
- ``name``, ``mime``, ``size``, ``sha256`` — what was received: the MIME type is the one detected
  from the content (libmagic), not the one the browser claimed; ``sha256`` finds duplicates in
  the organisation (A-06-T08);
- ``status`` — ``uploading`` (presigned upload handed out, not finalised) → ``scanning`` (virus
  scan queued) → ``clean`` (downloadable, previewable) or ``infected`` (moved to the quarantine
  bucket, never served);
- ``source`` — ``upload`` or ``email``; for email: ``sender``, ``sender_known`` (the sender is a
  member of the organisation or a person of one of its contacts — unknown senders are accepted and
  flagged) and the inbound message it came with;
- tags — ``period`` (``YYYY-MM``), ``tax_year``, free ``tags`` (A-06-T10); ``folder`` — ``inbox``
  or ``archived``;
- preview — ``preview_status`` and the keys of the preview and thumbnail images (A-06-T05).

``Attachment`` links a document to any business record (any ``OrgOwnedModel``: a contact, later
an invoice or a bill) by content type and the record's public id (A-06-T09).
"""

from __future__ import annotations

import re
import string
from typing import Any, ClassVar

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.contacts.fields import PortableArrayField
from numo9.tenancy.models import OrgOwnedModel

#: 25 MB per file (A-06 business rule).
MAX_FILE_SIZE = 25 * 1024 * 1024
NAME_MAX = 255
TAG_MAX = 40
TAGS_PER_DOCUMENT = 20
PERIOD = re.compile(r"^(19|20)\d{2}-(0[1-9]|1[0-2])$")
TAG = re.compile(r"^[\w][\w .&/-]{0,39}$")
TAX_YEAR_MIN, TAX_YEAR_MAX = 1990, 2100


class DocumentStatus(models.TextChoices):
    UPLOADING = "uploading", _("Uploading")
    SCANNING = "scanning", _("Checking for viruses")
    CLEAN = "clean", _("Ready")
    INFECTED = "infected", _("Quarantined (virus found)")


class DocumentSource(models.TextChoices):
    UPLOAD = "upload", _("Uploaded")
    EMAIL = "email", _("Emailed to the inbox")


class Folder(models.TextChoices):
    INBOX = "inbox", _("Inbox")
    ARCHIVED = "archived", _("Archived")


class PreviewStatus(models.TextChoices):
    PENDING = "pending", _("Preview being made")
    READY = "ready", _("Preview ready")
    UNSUPPORTED = "unsupported", _("No preview for this type")
    PASSWORD = "password", _("Password-protected PDF: no preview")
    FAILED = "failed", _("Preview failed")


def _in(field: str, choices: type[models.TextChoices]) -> models.Q:
    return models.Q(**{f"{field}__in": choices.values})


def normalise_tags(tags: Any) -> list[str]:
    """Each tag once (case-insensitive), trimmed, in the order given."""
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags or []:
        text = " ".join(str(tag).split())
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out


class Document(AuditedModel, OrgOwnedModel):
    file_key = models.CharField(_("storage key"), max_length=512, editable=False)
    name = models.CharField(_("file name"), max_length=NAME_MAX)
    mime = models.CharField(_("file type"), max_length=127, blank=True)
    size = models.BigIntegerField(
        _("size (bytes)"),
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(MAX_FILE_SIZE)],
    )
    sha256 = models.CharField(_("SHA-256"), max_length=64, blank=True, editable=False)
    status = models.CharField(
        _("status"),
        max_length=12,
        choices=DocumentStatus.choices,
        default=DocumentStatus.UPLOADING,
    )
    source = models.CharField(
        _("source"), max_length=8, choices=DocumentSource.choices, default=DocumentSource.UPLOAD
    )
    sender = models.EmailField(_("sender"), max_length=254, blank=True)
    sender_known = models.BooleanField(
        _("known sender"),
        default=True,
        help_text=_(
            "False when an emailed document came from an address the organisation "
            "doesn't know (accepted and flagged)."
        ),
    )
    inbound_message = models.ForeignKey(
        "files.InboundMessage",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documents",
        verbose_name=_("inbound email"),
    )
    period = models.CharField(
        _("period"),
        max_length=7,
        blank=True,
        help_text=_("Month the document belongs to, YYYY-MM."),
    )
    tax_year = models.PositiveSmallIntegerField(_("tax year"), null=True, blank=True)
    tags = PortableArrayField(
        models.CharField(max_length=TAG_MAX), verbose_name=_("tags"), default=list, blank=True
    )
    folder = models.CharField(
        _("folder"), max_length=10, choices=Folder.choices, default=Folder.INBOX
    )
    scan_result = models.CharField(_("scan result"), max_length=200, blank=True)
    scanned_at = models.DateTimeField(_("scanned at"), null=True, blank=True)
    preview_status = models.CharField(
        _("preview"), max_length=12, choices=PreviewStatus.choices, default=PreviewStatus.PENDING
    )
    preview_key = models.CharField(_("preview key"), max_length=512, blank=True, editable=False)
    thumbnail_key = models.CharField(_("thumbnail key"), max_length=512, blank=True, editable=False)
    password_protected = models.BooleanField(_("password-protected"), default=False)

    audit_exclude: ClassVar[frozenset[str]] = frozenset(
        {"file_key", "preview_key", "thumbnail_key", "scanned_at"}
    )

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = _("document")
        verbose_name_plural = _("documents")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=_in("status", DocumentStatus), name="files_document_status_valid"
            ),
            models.CheckConstraint(
                condition=_in("source", DocumentSource), name="files_document_source_valid"
            ),
            models.CheckConstraint(
                condition=_in("folder", Folder), name="files_document_folder_valid"
            ),
            models.CheckConstraint(
                condition=_in("preview_status", PreviewStatus),
                name="files_document_preview_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(size__gte=0, size__lte=MAX_FILE_SIZE),
                name="files_document_size_limit",
            ),
            models.CheckConstraint(
                condition=models.Q(period="") | models.Q(period__regex=PERIOD.pattern),
                name="files_document_period_format",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_year__isnull=True)
                | models.Q(tax_year__gte=TAX_YEAR_MIN, tax_year__lte=TAX_YEAR_MAX),
                name="files_document_tax_year_range",
            ),
            models.CheckConstraint(
                condition=~models.Q(file_key=""), name="files_document_key_required"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organisation", "folder", "-created_at"), name="files_document_inbox_idx"
            ),
            models.Index(fields=("organisation", "sha256"), name="files_document_sha_idx"),
            models.Index(fields=("organisation", "period"), name="files_document_period_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def audit_label(self) -> str:
        return self.name

    @property
    def is_clean(self) -> bool:
        return self.status == DocumentStatus.CLEAN

    @property
    def extension(self) -> str:
        return self.name.rsplit(".", 1)[-1].lower() if "." in self.name else ""

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}

        def add(field: str, message: Any, code: str, **params: Any) -> None:
            errors.setdefault(field, []).append(ValidationError(message, code=code, params=params))

        if self.period and not PERIOD.match(self.period):
            add("period", _("Enter the period as YYYY-MM, e.g. 2026-10."), "files.period.format")
        if self.tax_year is not None and not TAX_YEAR_MIN <= self.tax_year <= TAX_YEAR_MAX:
            add(
                "tax_year",
                _("Enter a tax year from %(min)d to %(max)d."),
                "files.tax_year.range",
                min=TAX_YEAR_MIN,
                max=TAX_YEAR_MAX,
            )
        self.tags = normalise_tags(self.tags)
        if len(self.tags) > TAGS_PER_DOCUMENT:
            add(
                "tags",
                _("A document has up to %(max)d tags."),
                "files.tags.limit",
                max=TAGS_PER_DOCUMENT,
            )
        bad = [t for t in self.tags if not TAG.match(t)]
        if bad:
            add(
                "tags",
                _("Tags use letters, digits, spaces and . & / - (up to 40 characters): %(tags)s."),
                "files.tags.format",
                tags=", ".join(bad),
            )
        if self.size > MAX_FILE_SIZE:
            add("size", _("Files are limited to 25 MB."), "files.size.too_large")
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.name = " ".join((self.name or "").split())[:NAME_MAX]
        self.period = (self.period or "").strip()
        update_fields = kwargs.get("update_fields")
        if update_fields is None or {"period", "tax_year", "tags", "size", "name"} & set(
            update_fields
        ):
            self.clean()
        super().save(*args, **kwargs)


class Attachment(AuditedModel, OrgOwnedModel):
    """A document attached to a business record (A-06-T09): the record is any ``OrgOwnedModel``,
    named by its content type and public id. Detaching is a soft delete (history kept)."""

    document = models.ForeignKey(
        Document, on_delete=models.PROTECT, related_name="attachments", verbose_name=_("document")
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name="+", verbose_name=_("record type")
    )
    object_public_id = models.UUIDField(_("record"))

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = _("attachment")
        verbose_name_plural = _("attachments")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("document", "content_type", "object_public_id"),
                condition=models.Q(deleted_at__isnull=True),
                name="files_attachment_once_per_record",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organisation", "content_type", "object_public_id"),
                name="files_attachment_record_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.document} → {self.content_type.app_label}.{self.content_type.model}"

    def audit_label(self) -> str:
        return str(self)

    @property
    def record_type(self) -> str:
        """``contacts.Contact`` — the record's model label."""
        model = self.content_type.model_class()
        return model._meta.label if model is not None else ""

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.document_id and self.document.organisation_id != self.organisation_id:
            raise ValidationError(
                {
                    "document": [
                        ValidationError(
                            _("Choose a document of this organisation."),
                            code="files.attachment.document",
                        )
                    ]
                }
            )
        super().save(*args, **kwargs)


class InboundMessage(OrgOwnedModel):
    """One email received at an organisation's inbound address (A-06-T07): idempotent by
    ``message_id`` per organisation; its attachments become documents."""

    message_id = models.CharField(_("Message-ID"), max_length=998)
    sender = models.EmailField(_("sender"), max_length=254, blank=True)
    subject = models.CharField(_("subject"), max_length=300, blank=True)
    recipient = models.CharField(_("recipient"), max_length=254)
    raw_key = models.CharField(_("raw message key"), max_length=512, blank=True, editable=False)
    attachment_count = models.PositiveSmallIntegerField(_("attachments"), default=0)
    rejected = models.JSONField(
        _("refused attachments"),
        default=list,
        blank=True,
        help_text=_("Attachments that were not stored: name and reason code."),
    )
    received_at = models.DateTimeField(_("received at"))
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)

    class Meta:
        ordering = ("-received_at",)
        verbose_name = _("inbound email")
        verbose_name_plural = _("inbound emails")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "message_id"), name="files_inbound_message_once"
            ),
        ]

    def __str__(self) -> str:
        return self.subject or self.message_id


# ---- inbound email address (A-06-T06) ----------------------------------------------------------

#: Letters and digits that can't be confused when read aloud or typed (no 0/o, 1/l/i).
TOKEN_ALPHABET = "".join(c for c in string.ascii_lowercase + string.digits if c not in "01ilo")
TOKEN_LENGTH = 12


class InboundAddressStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    RETIRED = "retired", _("Retired")


class InboundAddress(AuditedModel, OrgOwnedModel):
    """The organisation's documents inbox address (A-06-T06): ``docs+<token>@<inbound domain>``.

    One active address per organisation (database constraint); ``rotate`` retires it — mail to a
    retired address is still accepted for 7 days so senders can update their records — and makes
    a new one. Tokens are random, unique across Numo9 and never reused. Not under row-level
    security: inbound mail is routed by token before any organisation is known.
    """

    token = models.CharField(_("token"), max_length=32, unique=True, editable=False)
    status = models.CharField(
        _("status"),
        max_length=8,
        choices=InboundAddressStatus.choices,
        default=InboundAddressStatus.ACTIVE,
    )
    retired_at = models.DateTimeField(_("retired at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("inbound address")
        verbose_name_plural = _("inbound addresses")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation",),
                condition=models.Q(status="active"),
                name="files_inbound_one_active_per_org",
            ),
            models.CheckConstraint(
                condition=_in("status", InboundAddressStatus),
                name="files_inbound_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(token__regex=rf"^[{TOKEN_ALPHABET}]{{{TOKEN_LENGTH}}}$"),
                name="files_inbound_token_format",
            ),
        ]

    def __str__(self) -> str:
        return self.address

    def audit_label(self) -> str:
        return self.address

    @property
    def address(self) -> str:
        from django.conf import settings

        return f"docs+{self.token}@{settings.NUMO9_INBOUND_DOMAIN}"
