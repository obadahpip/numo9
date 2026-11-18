"""Daily usage aggregates and the aggregator's stream offset (S-06-T07)."""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import OrgOwnedModel


class UsageDaily(OrgOwnedModel):
    """How much of one metered thing an organisation used on one UTC day.

    Written only by the aggregator (``numo9.metering.aggregate``), which adds each batch with
    ``INSERT … ON CONFLICT DO UPDATE SET quantity = quantity + excluded.quantity``.
    """

    key = models.CharField(_("meter"), max_length=100)
    day = models.DateField(_("day (UTC)"))
    quantity = models.BigIntegerField(_("quantity"), default=0)

    class Meta:
        verbose_name = _("daily usage")
        verbose_name_plural = _("daily usage")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation", "key", "day"], name="metering_usage_org_key_day_uniq"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["key", "day"], name="metering_usage_key_day_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.key} {self.day}: {self.quantity}"


class StreamOffset(models.Model):
    """Last stream entry already summed into ``UsageDaily`` (one row per stream).

    Saved in the same transaction as the sums, so an entry is counted exactly once even if the
    aggregator stops between the database commit and trimming the stream.
    """

    stream = models.CharField(_("stream"), max_length=100, unique=True)
    last_id = models.CharField(_("last entry"), max_length=40, default="0-0")
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("metering stream offset")
        verbose_name_plural = _("metering stream offsets")

    def __str__(self) -> str:
        return f"{self.stream} @ {self.last_id}"
