"""In-app notifications (A-07-T01).

``Notification`` — one message to one person in one organisation:

- ``recipient`` — the person it is for; nobody else lists, reads or marks it (the API answers 404);
- ``category`` — what it is about (``NotificationCategory``); people choose per category whether
  they get it in the app and by email (preferences, A-07-T02);
- ``title_key`` and ``body_params`` — the message is stored as a key of the message catalogue
  (``numo9.notifications.texts``) and its parameters, never as rendered text, so it is shown in the
  reader's language at read time (``{"job": "Import contacts", "rows": 512}``);
- ``link`` — where opening it takes the person: a path inside the app (``/o/<org>/contacts``),
  never another site;
- ``read_at`` — when it was read; empty = unread (the bell's count).

An organisation record (``OrgOwnedModel``: scoped manager, public id, soft delete). Not audited:
notifications are personal, high-volume messages about events that are audited where they
happen.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import OrgOwnedModel

TITLE_KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+){1,4}$")
LINK_MAX = 500


def _field_error(field: str, message: Any, code: str) -> ValidationError:
    return ValidationError({field: ValidationError(message, code=code)})


class NotificationCategory(models.TextChoices):
    """Groups of notifications people set preferences for (A-07-T02, T09)."""

    SYSTEM = "system", _("Account and system")
    SECURITY = "security", _("Security")
    JOBS = "jobs", _("Background jobs")
    DOCUMENTS = "documents", _("Documents")
    APPROVALS = "approvals", _("Approvals")
    REMINDERS = "reminders", _("Reminders")
    BILLING = "billing", _("Billing and subscription")


class Notification(OrgOwnedModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # personal messages go with the person
        related_name="notifications",
        verbose_name=_("recipient"),
    )
    category = models.CharField(_("category"), max_length=20, choices=NotificationCategory.choices)
    title_key = models.CharField(_("message"), max_length=120)
    body_params = models.JSONField(_("message details"), default=dict, blank=True)
    link = models.CharField(_("link"), max_length=LINK_MAX, blank=True)
    read_at = models.DateTimeField(_("read at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(category__in=NotificationCategory.values),
                name="notifications_category_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(title_key=""), name="notifications_title_key_required"
            ),
            models.CheckConstraint(
                condition=models.Q(link="") | models.Q(link__startswith="/"),
                name="notifications_link_in_app",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            # The bell's unread count and the drawer's newest-first list.
            models.Index(
                fields=("organisation", "recipient", "read_at"),
                name="notifications_unread_idx",
            ),
            models.Index(
                fields=("organisation", "recipient", "-created_at"),
                name="notifications_recent_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.recipient_id} · {self.title_key}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def clean(self) -> None:
        if not TITLE_KEY.match(self.title_key or ""):
            raise _field_error(
                "title_key",
                _("A message key looks like notifications.job.finished."),
                "notifications.title_key_invalid",
            )
        if self.link and (
            not self.link.startswith("/") or self.link.startswith("//") or "\\" in self.link
        ):
            raise _field_error(
                "link",
                _("A notification links to a page of the app (a path such as /o/…)."),
                "notifications.link_external",
            )
        if not isinstance(self.body_params, dict):
            raise _field_error(
                "body_params",
                _("Message details are a set of named values."),
                "notifications.body_params_invalid",
            )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("update_fields") is None:
            self.clean()
        super().save(*args, **kwargs)


class NotificationChannel(models.TextChoices):
    """Where a notification is delivered (A-07-T02; SMS/WhatsApp interface: A-07-T12)."""

    IN_APP = "in_app", _("In the app")
    EMAIL = "email", _("Email")


class NotificationPreference(OrgOwnedModel):
    """One person's choice for one category in one organisation (A-07-T02).

    No row = the category's default (``numo9.notifications.events.DEFAULTS``). Categories marked
    *locked* there (security) ignore the row: those messages always arrive.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        verbose_name=_("person"),
    )
    category = models.CharField(_("category"), max_length=20, choices=NotificationCategory.choices)
    in_app = models.BooleanField(_("in the app"), default=True)
    email = models.BooleanField(_("by email"), default=True)

    class Meta:
        verbose_name = _("notification preference")
        verbose_name_plural = _("notification preferences")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "user", "category"),
                condition=models.Q(deleted_at__isnull=True),
                name="notifications_one_preference_per_category",
            ),
            models.CheckConstraint(
                condition=models.Q(category__in=NotificationCategory.values),
                name="notifications_preference_category_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.category}"


class EmailStatus(models.TextChoices):
    """Where an outgoing email stands (A-07-T03; bounced/complained from A-07-T08)."""

    QUEUED = "queued", _("Waiting to send")
    SENDING = "sending", _("Sending")
    RETRYING = "retrying", _("Waiting to try again")
    SENT = "sent", _("Sent")
    FAILED = "failed", _("Not sent")
    BOUNCED = "bounced", _("Bounced")
    COMPLAINED = "complained", _("Marked as spam")


#: An email in one of these states may still be sent by the worker.
EMAIL_SENDABLE: frozenset[str] = frozenset({EmailStatus.QUEUED, EmailStatus.RETRYING})


class EmailMessage(OrgOwnedModel):
    """The message log: one row per outgoing email to one address (A-07-T03).

    Written before the Celery message is sent, updated by the sending task: ``queued`` →
    ``sending`` → ``sent`` (or ``retrying`` → … → ``failed`` once the retries are used up). The
    provider's message id (``provider_message_id``) and the row's ``public_id`` (sent as message
    metadata) let delivery webhooks find it again (A-07-T08 bounces and complaints).

    Emails of an organisation (invoices, reminders, notifications) carry it; account emails that
    belong to no organisation (sign-up, password reset) leave it empty — read through
    ``platform_messages`` by the sending task, webhooks and the platform console only.
    """

    organisation = models.ForeignKey(  # type: ignore[assignment]  # nullable here
        "tenancy.Organisation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="email_messages",
        verbose_name=_("organisation"),
    )
    kind = models.CharField(_("message type"), max_length=120, blank=True)
    to_email = models.EmailField(_("to"))
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("recipient"),
    )
    from_email = models.CharField(_("from"), max_length=320)
    reply_to = models.CharField(_("reply to"), max_length=320, blank=True)
    subject = models.CharField(_("subject"), max_length=998)
    text_body = models.TextField(_("text"))
    html_body = models.TextField(_("HTML"), blank=True)
    language = models.CharField(_("language"), max_length=10, blank=True)
    headers = models.JSONField(_("headers"), default=dict, blank=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)
    status = models.CharField(
        _("status"), max_length=16, choices=EmailStatus.choices, default=EmailStatus.QUEUED
    )
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)
    max_retries = models.PositiveSmallIntegerField(_("maximum retries"), default=5)
    provider = models.CharField(_("provider"), max_length=60, blank=True)
    provider_message_id = models.CharField(_("provider message id"), max_length=255, blank=True)
    error = models.TextField(_("error"), blank=True)
    last_attempt_at = models.DateTimeField(_("last try at"), null=True, blank=True)
    next_retry_at = models.DateTimeField(_("next try at"), null=True, blank=True)
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)
    event_at = models.DateTimeField(_("delivery event at"), null=True, blank=True)

    # Sending task, delivery webhooks and the platform console only (see the docstring).
    platform_messages = models.Manager["EmailMessage"]()

    class Meta:
        verbose_name = _("email message")
        verbose_name_plural = _("email messages")
        default_manager_name = "objects"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(status__in=EmailStatus.values),
                name="notifications_email_status_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "-created_at"), name="notif_email_org_idx"),
            models.Index(fields=("status", "-created_at"), name="notif_email_status_idx"),
            models.Index(fields=("provider_message_id",), name="notif_email_provider_idx"),
            models.Index(fields=("to_email", "-created_at"), name="notif_email_to_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.to_email} · {self.subject[:40]} [{self.status}]"


# ---- email branding (A-07-T04) ---------------------------------------------------------------

HEX_COLOUR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_colour(value: str) -> None:
    if not HEX_COLOUR.match(value or ""):
        raise ValidationError(
            _("Enter the colour as # and six hexadecimal digits, e.g. #1F4E79."),
            code="notifications.colour_invalid",
        )


def validate_logo_url(value: str) -> None:
    if value and not value.startswith("https://"):
        raise ValidationError(
            _("The logo must be an https:// address so email apps can show it."),
            code="notifications.logo_not_https",
        )


class BrandingFields(models.Model):
    """What a branded email shows: the sender's name, logo and accent colour."""

    display_name = models.CharField(_("name in emails"), max_length=120, blank=True)
    logo_url = models.URLField(
        _("logo"), max_length=500, blank=True, validators=[validate_logo_url]
    )
    colour = models.CharField(
        _("accent colour"), max_length=7, blank=True, validators=[validate_colour]
    )

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.colour:
            validate_colour(self.colour)
        validate_logo_url(self.logo_url)


class OrganisationBranding(BrandingFields, OrgOwnedModel):
    """An organisation's own email branding (wins over its practice's)."""

    class Meta:
        verbose_name = _("organisation email branding")
        verbose_name_plural = _("organisation email branding")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation",),
                condition=models.Q(deleted_at__isnull=True),
                name="notifications_one_branding_per_organisation",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organisation_id} · {self.display_name or '—'}"


class PracticeBranding(BrandingFields):
    """A practice's email branding: used for its client organisations without their own."""

    practice = models.OneToOneField(
        "tenancy.Practice",
        on_delete=models.CASCADE,
        related_name="email_branding",
        verbose_name=_("practice"),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("practice email branding")
        verbose_name_plural = _("practice email branding")

    def __str__(self) -> str:
        return f"{self.practice_id} · {self.display_name or '—'}"
