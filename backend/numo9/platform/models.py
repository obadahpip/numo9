"""Platform console models (U-06).

``ImpersonationSession`` (U-06-T08) — one row per support session in which a platform staff
member (``actor``) acts as a user (``target_user``) of **one** organisation, with the reason they
gave, when it started, when it expires (default 30 minutes, at most 2 hours) and when it ended
(by the actor, by expiry or by the platform). A staff member has at most one open session.

``PlatformMetricDaily`` (U-06-T05) — one row per day: the platform's metrics as the nightly job
computed them (MRR, active organisations, trials, conversion, churn), so the console's trend
charts read history instead of recomputing it. Demo organisations are never counted. Platform
data (no organisation).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation

DEFAULT_MINUTES = 30
MAX_MINUTES = 120


class PlatformMetricDaily(models.Model):
    date = models.DateField(_("date"), unique=True)
    mrr_cents = models.BigIntegerField(_("MRR (CAD cents)"), default=0)
    active = models.PositiveIntegerField(_("active organisations"), default=0)
    trials = models.PositiveIntegerField(_("trials"), default=0)
    conversion_rate = models.DecimalField(
        _("conversion rate (30 days)"), max_digits=6, decimal_places=4, null=True, blank=True
    )
    churn_rate = models.DecimalField(
        _("churn rate (30 days)"), max_digits=6, decimal_places=4, null=True, blank=True
    )
    computed_at = models.DateTimeField(_("computed at"), auto_now=True)

    class Meta:
        ordering = ("-date",)
        verbose_name = _("daily platform metrics")
        verbose_name_plural = _("daily platform metrics")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(mrr_cents__gte=0), name="platform_metric_mrr_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.date:%Y-%m-%d}"


class ImpersonationEndReason(models.TextChoices):
    ENDED = "ended", _("Ended by the staff member")
    EXPIRED = "expired", _("Time limit reached")
    REVOKED = "revoked", _("Ended by the platform")


class ImpersonationSession(models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="impersonations_started",
        verbose_name=_("platform staff member"),
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="impersonations_received",
        verbose_name=_("user acted as"),
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("organisation"),
    )
    reason = models.TextField(_("reason"), max_length=500)
    started_at = models.DateTimeField(_("started"), default=timezone.now)
    expires_at = models.DateTimeField(_("expires"))
    ended_at = models.DateTimeField(_("ended"), null=True, blank=True)
    end_reason = models.CharField(
        _("how it ended"), max_length=8, choices=ImpersonationEndReason.choices, blank=True
    )

    class Meta:
        ordering = ("-started_at",)
        verbose_name = _("impersonation session")
        verbose_name_plural = _("impersonation sessions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("started_at"))
                & models.Q(
                    expires_at__lte=models.F("started_at") + dt.timedelta(minutes=MAX_MINUTES)
                ),
                name="platform_impersonation_time_box",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""), name="platform_impersonation_reason_required"
            ),
            models.CheckConstraint(
                condition=~models.Q(actor=models.F("target_user")),
                name="platform_impersonation_not_self",
            ),
            models.CheckConstraint(
                condition=(models.Q(ended_at__isnull=True) & models.Q(end_reason=""))
                | (models.Q(ended_at__isnull=False) & ~models.Q(end_reason="")),
                name="platform_impersonation_end_has_reason",
            ),
            models.UniqueConstraint(
                fields=("actor",),
                condition=models.Q(ended_at__isnull=True),
                name="platform_impersonation_one_open_per_actor",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "-started_at"), name="platform_imp_org_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.actor} as {self.target_user} @ {self.organisation}"

    def is_open(self, now: dt.datetime | None = None) -> bool:
        return self.ended_at is None and (now or timezone.now()) < self.expires_at

    def end(self, reason: str, at: dt.datetime | None = None) -> bool:
        """Close the session (once): ``True`` when this call ended it."""
        if self.ended_at is not None:
            return False
        at = at or timezone.now()
        self.ended_at = min(at, self.expires_at) if reason == ImpersonationEndReason.EXPIRED else at
        self.end_reason = reason
        self.save(update_fields=["ended_at", "end_reason"])
        return True
