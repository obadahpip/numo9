"""Billing records (U-04).

``StripeEvent`` (U-04-T03) — every webhook event Stripe sent, kept once: ``event_id`` (``evt_…``)
is unique, so a replayed or re-delivered event is recognised and never processed twice
(idempotency). The row keeps the event's ``type``, the whole ``payload`` as received, Stripe's
``created`` time (out-of-order resolution, U-04-T15), when it was processed (``processed_at``) or
why processing failed (``error``, ``attempts``). It is platform data: an event arrives before
Numo9 knows which organisation it concerns; ``organisation`` is filled once it is resolved.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class StripeEvent(models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    event_id = models.CharField(_("Stripe event"), max_length=255, unique=True)
    type = models.CharField(_("event type"), max_length=100)
    payload = models.JSONField(_("payload"))
    stripe_created = models.DateTimeField(_("created at Stripe"))
    livemode = models.BooleanField(_("live mode"), default=False)
    organisation = models.ForeignKey(
        "tenancy.Organisation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("organisation"),
    )
    received_at = models.DateTimeField(_("received at"), default=timezone.now)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)
    error = models.TextField(_("last error"), blank=True)

    class Meta:
        ordering = ("-stripe_created", "-id")
        verbose_name = _("Stripe event")
        verbose_name_plural = _("Stripe events")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(event_id__startswith="evt_"),
                name="billing_stripe_event_id_format",
            ),
            models.CheckConstraint(condition=~models.Q(type=""), name="billing_event_type"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("processed_at",),
                condition=models.Q(processed_at__isnull=True),
                name="billing_event_unprocessed",
            ),
            models.Index(fields=("organisation", "stripe_created"), name="billing_event_org"),
        ]

    def __str__(self) -> str:
        return f"{self.event_id} {self.type}"

    @property
    def data_object(self) -> dict[str, Any]:
        """The event's ``data.object`` (the Stripe object the event is about)."""
        data = (self.payload or {}).get("data") or {}
        obj = data.get("object") or {}
        return obj if isinstance(obj, dict) else {}
