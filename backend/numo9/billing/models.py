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

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel


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


class PlatformInvoiceStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    OPEN = "open", _("Due")
    PAID = "paid", _("Paid")
    UNCOLLECTIBLE = "uncollectible", _("Uncollectible")
    VOID = "void", _("Void")


class PlatformInvoice(AuditedModel, OrgOwnedModel):
    """Numo9's invoice to the organisation — a mirror of the Stripe invoice (U-04-T08).

    Stripe numbers and issues the invoice; Numo9 keeps a copy for the billing page (list, PDF
    link) and for its reports: one row per Stripe invoice (``stripe_invoice_id`` unique), updated
    by every ``invoice.finalized`` / ``.paid`` / ``.payment_failed`` event. Amounts are in cents
    of ``currency`` (CAD), as Stripe gives them.
    """

    stripe_invoice_id = models.CharField(_("Stripe invoice"), max_length=64, unique=True)
    number = models.CharField(_("number"), max_length=64, blank=True)
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=PlatformInvoiceStatus.choices,
        default=PlatformInvoiceStatus.DRAFT,
    )
    currency = models.CharField(_("currency"), max_length=3, default="CAD")
    subtotal_cents = models.BigIntegerField(_("subtotal"), default=0)
    tax_cents = models.BigIntegerField(_("tax"), default=0)
    total_cents = models.BigIntegerField(_("total"), default=0)
    amount_paid_cents = models.BigIntegerField(_("paid"), default=0)
    amount_due_cents = models.BigIntegerField(_("due"), default=0)
    period_start = models.DateTimeField(_("period from"), null=True, blank=True)
    period_end = models.DateTimeField(_("period to"), null=True, blank=True)
    issued_at = models.DateTimeField(_("issued at"), null=True, blank=True)
    paid_at = models.DateTimeField(_("paid at"), null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(_("payment attempts"), default=0)
    next_attempt_at = models.DateTimeField(_("next payment attempt"), null=True, blank=True)
    hosted_url = models.URLField(_("invoice page"), max_length=500, blank=True)
    pdf_url = models.URLField(_("PDF"), max_length=500, blank=True)
    stripe_subscription_id = models.CharField(_("Stripe subscription"), max_length=64, blank=True)
    receipt_sent_at = models.DateTimeField(_("receipt sent at"), null=True, blank=True)
    #: Stripe ``created`` of the last event applied (an older event never overwrites, U-04-T15).
    stripe_event_created = models.DateTimeField(_("last event at"), null=True, blank=True)

    class Meta:
        ordering = ("-issued_at", "-id")
        verbose_name = _("Numo9 invoice")
        verbose_name_plural = _("Numo9 invoices")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(status__in=PlatformInvoiceStatus.values),
                name="billing_invoice_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.number or self.stripe_invoice_id


class DunningReminder(OrgOwnedModel):
    """One dunning step taken for a failed payment (U-04-T09) — so each is taken once.

    A dunning cycle is one grace period of a subscription (``grace_until``); ``day`` is 0, 3, 5 or
    7 days after the failure (day 7 = the grace ends: read-only). The unique constraint makes the
    scheduler idempotent: a step already taken for that grace period is never taken again.
    """

    subscription = models.ForeignKey(
        "entitlements.Subscription",
        on_delete=models.PROTECT,
        related_name="dunning_reminders",
        verbose_name=_("subscription"),
    )
    grace_until = models.DateTimeField(_("grace period ends"))
    day = models.PositiveSmallIntegerField(_("day"))
    sent_at = models.DateTimeField(_("sent at"), default=timezone.now)
    recipients = models.PositiveSmallIntegerField(_("recipients"), default=0)

    class Meta:
        ordering = ("subscription", "grace_until", "day")
        verbose_name = _("dunning reminder")
        verbose_name_plural = _("dunning reminders")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("subscription", "grace_until", "day"), name="billing_dunning_once"
            ),
            models.CheckConstraint(
                condition=models.Q(day__in=(0, 3, 5, 7)), name="billing_dunning_day_valid"
            ),
        ]


class ScheduledChange(OrgOwnedModel):
    """A downgrade waiting for the end of the paid period (U-04-T10).

    Upgrades apply at once (prorated); a downgrade keeps the current package until
    ``effective_at`` (the period end), then moves the Stripe subscription to the new price without
    proration so the renewal is billed at it. One pending change per subscription.
    """

    subscription = models.ForeignKey(
        "entitlements.Subscription",
        on_delete=models.PROTECT,
        related_name="scheduled_changes",
        verbose_name=_("subscription"),
    )
    package = models.ForeignKey(
        "packages.Package", on_delete=models.PROTECT, related_name="+", verbose_name=_("package")
    )
    interval = models.CharField(_("billing interval"), max_length=8)
    effective_at = models.DateTimeField(_("takes effect at"))
    applied_at = models.DateTimeField(_("applied at"), null=True, blank=True)
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)

    class Meta:
        ordering = ("-effective_at", "-id")
        verbose_name = _("scheduled package change")
        verbose_name_plural = _("scheduled package changes")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("subscription",),
                condition=models.Q(applied_at__isnull=True, cancelled_at__isnull=True),
                name="billing_one_pending_change",
            ),
        ]
