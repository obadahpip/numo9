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
