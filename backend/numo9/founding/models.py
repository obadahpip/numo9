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


class FoundingCounter(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    cap = models.PositiveIntegerField(_("founding slots"), default=DEFAULT_CAP)
    allocated = models.PositiveIntegerField(_("allocated"), default=0)
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
