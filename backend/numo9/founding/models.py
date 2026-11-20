"""Founding offer models (U-08-T01).

``FoundingCounter`` — the one row that counts founding slots: ``cap`` (1,000) and ``allocated``.
Allocation (U-08-T02) is a single ``UPDATE … SET allocated = allocated + 1 WHERE allocated < cap
RETURNING allocated`` on this row, in the transaction that records the first payment, so it can
never pass the cap under concurrency. The database holds the invariants: the row's id is always
1 (a second row is refused), ``0 ≤ allocated ≤ cap``.

``FoundingSlot`` — which organisation holds which slot: one slot per organisation (a webhook
replay can't allocate twice) and each slot number once (``1…cap``). Released slots (refund within
the release window, churn rules — U-08-T03/T04) keep their row with ``released_at``; a released
number is never handed out again.
"""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation

DEFAULT_CAP = 1000
DEFAULT_RETURN_WINDOW_DAYS = 90
DEFAULT_REFUND_RELEASE_HOURS = 24


class ChurnRule(models.TextChoices):
    """What happens to a founding slot when its organisation cancels (U-08-T06)."""

    KEEP_ON_RETURN = "keep_on_return", _("Keep founding status whenever the organisation returns")
    LOSE_ON_CANCEL = "lose_on_cancel", _("Lose founding status on cancellation")
    KEEP_IF_RETURNS_WITHIN_DAYS = (
        "keep_if_returns_within_days",
        _("Keep founding status if the organisation returns within N days"),
    )


class FoundingCounter(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    cap = models.PositiveIntegerField(_("founding slots"), default=DEFAULT_CAP)
    allocated = models.PositiveIntegerField(_("allocated"), default=0)
    churn_rule = models.CharField(
        _("churn rule"),
        max_length=32,
        choices=ChurnRule.choices,
        default=ChurnRule.KEEP_IF_RETURNS_WITHIN_DAYS,
    )
    return_window_days = models.PositiveIntegerField(
        _("return window (days)"),
        default=DEFAULT_RETURN_WINDOW_DAYS,
        help_text=_("For the keep-if-returns-within-days rule."),
    )
    refund_release_hours = models.PositiveIntegerField(
        _("refund release window (hours)"),
        default=DEFAULT_REFUND_RELEASE_HOURS,
        help_text=_("A first payment refunded within this window releases the slot; 0 = never."),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("founding counter")
        verbose_name_plural = _("founding counter")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(condition=models.Q(id=1), name="founding_counter_single_row"),
            models.CheckConstraint(
                condition=models.Q(allocated__lte=models.F("cap")),
                name="founding_counter_within_cap",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.allocated} of {self.cap}"

    @property
    def remaining(self) -> int:
        return max(self.cap - self.allocated, 0)

    @classmethod
    def current(cls) -> FoundingCounter:
        counter, _created = cls.objects.get_or_create(id=1)
        return counter


class FoundingSlot(models.Model):
    organisation = models.OneToOneField(
        Organisation,
        on_delete=models.PROTECT,
        related_name="founding_slot",
        verbose_name=_("organisation"),
    )
    slot_no = models.PositiveIntegerField(_("slot number"), unique=True)
    allocated_at = models.DateTimeField(_("allocated at"), auto_now_add=True)
    payment_ref = models.CharField(
        _("first payment"), max_length=255, blank=True, help_text=_("Stripe invoice or payment id.")
    )
    lapsed_at = models.DateTimeField(
        _("cancelled at"),
        null=True,
        blank=True,
        help_text=_("When the organisation cancelled; cleared when it returns (churn rules)."),
    )
    released_at = models.DateTimeField(_("released at"), null=True, blank=True)
    release_reason = models.CharField(_("release reason"), max_length=64, blank=True)

    class Meta:
        verbose_name = _("founding slot")
        verbose_name_plural = _("founding slots")
        ordering = ("slot_no",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(slot_no__gte=1), name="founding_slot_number_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"Founding organisation #{self.slot_no:04d}"


class AcquisitionSource(models.TextChoices):
    """How the organisation (or practice) came to Numo9 (U-08-T07)."""

    SELF_SIGNUP = "self_signup", _("Self sign-up")
    ACCOUNTANT_SIGNUP = "accountant_signup", _("Accountant sign-up")
    IN_APP = "in_app", _("Created in the app")
    PRACTICE = "practice", _("Created by a practice")
    DEMO_CONVERSION = "demo_conversion", _("Converted from a demo")


class AcquisitionAttribution(models.Model):
    """Marketing hooks stored at sign-up (U-08-T07): where a new organisation (or the practice of
    an accountant signing up) came from — the referral source it gave, the UTM parameters of the
    link it arrived by, the promo code it entered and the referring page. One row per
    organisation (or practice), written in the transaction that creates it."""

    organisation = models.OneToOneField(
        Organisation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="acquisition",
        verbose_name=_("organisation"),
    )
    practice = models.OneToOneField(
        "tenancy.Practice",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="acquisition",
        verbose_name=_("practice"),
    )
    source = models.CharField(_("source"), max_length=32, choices=AcquisitionSource.choices)
    referral_source = models.CharField(_("referral source"), max_length=100, blank=True)
    utm_source = models.CharField(_("UTM source"), max_length=100, blank=True)
    utm_medium = models.CharField(_("UTM medium"), max_length=100, blank=True)
    utm_campaign = models.CharField(_("UTM campaign"), max_length=100, blank=True)
    utm_term = models.CharField(_("UTM term"), max_length=100, blank=True)
    utm_content = models.CharField(_("UTM content"), max_length=100, blank=True)
    promo_code = models.CharField(_("promo code"), max_length=64, blank=True)
    referrer = models.CharField(_("referring page"), max_length=500, blank=True)
    captured_at = models.DateTimeField(_("captured at"), auto_now_add=True)

    class Meta:
        verbose_name = _("acquisition attribution")
        verbose_name_plural = _("acquisition attributions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=(
                    models.Q(organisation__isnull=False, practice__isnull=True)
                    | models.Q(organisation__isnull=True, practice__isnull=False)
                ),
                name="acquisition_one_subject",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source} · {self.utm_source or self.referral_source or '-'}"
