"""Platform console models (U-06).

``PlatformMetricDaily`` (U-06-T05) — one row per day: the platform's metrics as the nightly job
computed them (MRR, active organisations, trials, conversion, churn), so the console's trend
charts read history instead of recomputing it. Demo organisations are never counted. Platform
data (no organisation).
"""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _


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
